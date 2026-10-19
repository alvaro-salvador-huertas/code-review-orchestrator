"""Aceptación HTTP 007: candidato solo en hijos; clientes exclusivamente loopback.

Una suite principal, oráculos explícitos y trazas de procesos/transporte. No es
un sandbox. Los errores técnicos se propagan; nunca se convierten en omisiones.
"""

import argparse
from contextlib import contextmanager
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from process_environment import process_environment

HOST = "127.0.0.1"
START_TIMEOUT = 5
IO_TIMEOUT = 5
STOP_TIMEOUT = 3
BODY_TIMEOUT = 2
BODY_MEASUREMENT_MARGIN = 0.5
FRAGMENT_INTERVAL = 0.4
TRACE = []
PRIVATE = {".git", "runs", ".agents", ".codex", ".aws", ".venv", ".env"}


def snapshot(root):
    found = {}
    def visit(path):
        info = path.lstat()
        hidden = path != root and (path.name in PRIVATE or path.name.startswith(".env."))
        value = None
        if stat.S_ISREG(info.st_mode) and not hidden:
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            value = os.readlink(path)
        found[str(path.relative_to(root))] = (info.st_mode, info.st_mtime_ns, value)
        if stat.S_ISDIR(info.st_mode) and not hidden:
            for child in sorted(path.iterdir()):
                visit(child)
    visit(root)
    return found


def unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Clave JSON duplicada")
        result[name] = value
    return result


def invalid_constant(value):
    raise ValueError("Constante no JSON: " + value)


def decode(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant)


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def document(reservations=(), resource="Sala Norte"):
    return {"solicitud": {"recurso": resource, "inicio": "2026-10-20T10:00:00Z",
                          "fin": "2026-10-20T11:00:00Z"},
            "reservas": copy.deepcopy(list(reservations))}


def booking(identifier, start="10:00:00", end="11:00:00", resource="Sala Norte"):
    return {"id": identifier, "recurso": resource, "inicio": "2026-10-20T" + start + "Z",
            "fin": "2026-10-20T" + end + "Z"}


def validate_ready(raw):
    value = decode(raw)
    if (type(value) is not dict or set(value) != {"host", "port"}
            or value["host"] != HOST or type(value["port"]) is not int
            or not 1 <= value["port"] <= 65535):
        raise AssertionError("Anuncio de host/puerto inválido; no se conecta")
    return value["port"]


def read_ready(path, process, timeout=START_TIMEOUT):
    deadline = time.monotonic() + timeout
    pending = bytearray()
    with path.open("rb") as stream:
        while time.monotonic() < deadline:
            part = stream.readline(8192)
            pending.extend(part)
            if pending.endswith(b"\n"):
                raw = bytes(pending)
                return raw, validate_ready(raw)
            if process.poll() is not None:
                raise RuntimeError("El proceso terminó sin anuncio completo")
            time.sleep(0.01)
    raise TimeoutError("No llegó un anuncio vaciado dentro del plazo")


def stop(process):
    """Recoger el hijo directo, incluso si ignora Ctrl+C o terminate."""
    forced = False
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            forced = True
            process.terminate()
            try:
                process.wait(timeout=STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=STOP_TIMEOUT)
    else:
        process.wait(timeout=STOP_TIMEOUT)
    return {"codigo": process.returncode, "forzado": forced, "recogido": True}


def read_closed(sock):
    deadline = time.monotonic() + IO_TIMEOUT
    chunks = []
    size = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("La respuesta no cerró dentro del plazo")
        sock.settimeout(remaining)
        chunk = sock.recv(8192)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > 262144:
            raise AssertionError("Respuesta desmesurada para las entradas sintéticas")


def response(raw):
    header, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        raise AssertionError("Respuesta HTTP incompleta")
    class MemorySocket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(header + separator)
    parsed = http.client.HTTPResponse(MemorySocket())
    try:
        parsed.begin()
        return {"status": parsed.status, "version": parsed.version,
                "headers": parsed.getheaders(), "body": body, "raw": raw}
    finally:
        parsed.close()


def read_while_trickling(sock, raw, item):
    """Cuerpo incompleto; envío y recepción concurrentes sin hilos adicionales.

    El plazo observado incluye cabeceras, respuesta y EOF. El margen de 0,5 s
    no amplía los 2 s del servidor. Un timeout reiniciable sigue recibiendo
    fragmentos cada 0,4 s hasta que vence este límite global.
    """
    start = time.monotonic()
    deadline = start + BODY_TIMEOUT + BODY_MEASUREMENT_MARGIN
    timing = item["goteo"] = {"plazo_contractual": BODY_TIMEOUT,
        "margen_medicion": BODY_MEASUREMENT_MARGIN, "intervalo": FRAGMENT_INTERVAL,
        "fragmentos": [], "primera_respuesta_segundos": None, "cierre_segundos": None}
    sock.settimeout(BODY_TIMEOUT + BODY_MEASUREMENT_MARGIN)
    sock.sendall(raw)
    # raw contiene las cabeceras y el primer byte del cuerpo, todavía incompleto.
    timing["fragmentos"].append({"segundos": time.monotonic() - start,
                                "hex": raw.partition(b"\r\n\r\n")[2].hex()})
    sock.setblocking(False)
    next_send = start + FRAGMENT_INTERVAL
    sending = True
    chunks = []
    size = 0
    while True:
        now = time.monotonic()
        if now >= deadline:
            raise AssertionError("Sin respuesta y cierre dentro del plazo total observado de 2,5 s")
        due = sending and now >= next_send
        wait = min(deadline - now, max(0, next_send - now)) if sending and not due else deadline - now
        readable, writable, _ = select.select([sock], [sock] if due else [], [], wait)
        if readable:
            try:
                chunk = sock.recv(8192)
            except BlockingIOError:
                continue
            except ConnectionResetError as exc:
                # Un cierre con datos no leídos puede resetear TCP. Los bytes ya
                # recibidos deben superar igualmente la validación HTTP completa.
                timing["cierre_reset"] = str(exc)
                chunk = b""
            elapsed = time.monotonic() - start
            if timing["primera_respuesta_segundos"] is None:
                timing["primera_respuesta_segundos"] = elapsed
                gaps = [x["segundos"] for x in timing["fragmentos"]] + [elapsed]
                if any(b - a > 2 * FRAGMENT_INTERVAL for a, b in zip(gaps, gaps[1:])):
                    raise RuntimeError("El cliente no mantuvo los intervalos de goteo; medición inválida")
            # Recibir cabeceras parciales no detiene el goteo: podría ocultar un
            # timeout reiniciable mientras el servidor aún no termina el cuerpo.
            if elapsed > BODY_TIMEOUT + BODY_MEASUREMENT_MARGIN:
                raise AssertionError("Respuesta o cierre posterior al plazo total observado de 2,5 s")
            if not chunk:
                timing["cierre_segundos"] = elapsed
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > 262144:
                raise AssertionError("Respuesta desmesurada para las entradas sintéticas")
        if writable and sending:
            try:
                sent = sock.send(b" ")
            except BlockingIOError:
                continue
            except (BrokenPipeError, ConnectionResetError) as exc:
                # No sustituye la recepción: todavía se exigen 408, JSON válido
                # y cierre dentro del mismo plazo, incluso tras un error al enviar.
                timing["cierre_durante_envio"] = type(exc).__name__ + ": " + str(exc)
                sending = False
                continue
            if sent != 1:
                raise RuntimeError("No se pudo enviar el fragmento de un byte")
            elapsed = time.monotonic() - start
            if elapsed - timing["fragmentos"][-1]["segundos"] > 2 * FRAGMENT_INTERVAL:
                raise RuntimeError("El cliente no mantuvo los intervalos de goteo; medición inválida")
            timing["fragmentos"].append({"segundos": elapsed, "hex": "20"})
            next_send = time.monotonic() + FRAGMENT_INTERVAL


def raw_target(raw):
    """Metadatos derivados solo de la línea enviada; bytes crudos son la autoridad."""
    try:
        method, target, version = raw.split(b"\r\n", 1)[0].decode("ascii").split(" ")
    except (UnicodeError, ValueError):
        return None, None
    if not method or not target or version not in ("HTTP/1.0", "HTTP/1.1"):
        return None, None
    return method, target


def json_type(value):
    return re.fullmatch(r'application/json(?:[ \t]*;[ \t]*charset[ \t]*=[ \t]*(?:utf-8|"utf-8"))?',
                        value.strip(" \t"), re.IGNORECASE) is not None


class Server:
    def __init__(self, project, cwd, command=None):
        self.project, self.cwd = project, cwd
        self.command = command or [str(Path(sys.executable).resolve()), "-B",
                                   str(project / "booking_http.py"), "--port", "0"]
        self.process = None
        self.port = None
        self.record = {"tipo": "servidor", "comando": self.command, "cwd": str(cwd),
                       "politica_entorno": "evaluation", "peticiones": [],
                       "limites_segundos": {"arranque": START_TIMEOUT, "respuesta": IO_TIMEOUT,
                                            "cada_espera_de_terminacion": STOP_TIMEOUT}}

    @contextmanager
    def running(self):
        TRACE.append(self.record)
        start = time.monotonic()
        ready = None
        clean = False
        with tempfile.TemporaryDirectory(prefix="transporte-http-") as tmp:
            stdout, stderr = Path(tmp) / "stdout", Path(tmp) / "stderr"
            # Los archivos evitan bloquear al hijo por llenar un PIPE. El lector
            # de disponibilidad usa otro descriptor, sin mover el offset escritor.
            with process_environment("evaluation") as environment:
                environment["PATH"] = ""
                with stdout.open("wb") as out, stderr.open("wb") as err:
                    try:
                        self.process = subprocess.Popen(self.command, cwd=self.cwd, env=environment,
                            stdin=subprocess.DEVNULL, stdout=out, stderr=err, shell=False)
                        ready, self.port = read_ready(stdout, self.process)
                        self.record["anuncio_hex"] = ready.hex()
                        self.record["arranque_segundos"] = time.monotonic() - start
                        yield self
                        if self.process.poll() is not None:
                            raise AssertionError("El servidor terminó antes de Ctrl+C")
                        clean = True
                    except BaseException as exc:
                        self.record["error"] = type(exc).__name__ + ": " + str(exc)
                        raise
                    finally:
                        if self.process is not None:
                            self.record["terminacion"] = stop(self.process)
                        out.flush()
                        err.flush()
                        self.record.update(stdout_hex=stdout.read_bytes().hex(),
                                           stderr_hex=stderr.read_bytes().hex(),
                                           duracion_segundos=time.monotonic() - start)
        if clean:
            if bytes.fromhex(self.record["stdout_hex"]) != ready:
                raise AssertionError("stdout contiene salida además del anuncio")
            if self.record["terminacion"]["forzado"]:
                raise AssertionError("El servidor no cerró ante Ctrl+C")
            if b"Traceback (most recent call last)" in bytes.fromhex(self.record["stderr_hex"]):
                raise AssertionError("Traceback durante el servicio o Ctrl+C")

    def request(self, method="GET", target="/health", body=None, headers=None, *, raw=None, eof=False, trickle=False):
        # El host no se toma del candidato: validate_ready ya exigió el literal.
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise AssertionError("Puerto sin validar")
        if trickle and (raw is None or eof):
            raise ValueError("El goteo requiere petición cruda sin EOF enviado")
        headers = {} if headers is None else headers
        sent_method, sent_target = (method, target) if raw is None else raw_target(raw)
        item = {"metodo": sent_method, "ruta": sent_target, "cabeceras": headers if raw is None else None,
                "cuerpo_hex": None if raw is not None or body is None else body.hex(),
                "peticion_cruda_hex": None if raw is None else raw.hex(), "eof_enviado": eof}
        self.record["peticiones"].append(item)
        started = time.monotonic()
        try:
            if raw is None:
                connection = http.client.HTTPConnection(HOST, self.port, timeout=IO_TIMEOUT)
                try:
                    connection.request(method, target, body=body, headers=headers)
                    wire = read_closed(connection.sock)
                finally:
                    connection.close()
            else:
                with socket.create_connection((HOST, self.port), timeout=IO_TIMEOUT) as connection:
                    if trickle:
                        wire = read_while_trickling(connection, raw, item)
                    else:
                        connection.sendall(raw)
                        if eof:
                            connection.shutdown(socket.SHUT_WR)
                        wire = read_closed(connection)
            result = response(wire)
            item.update(respuesta_hex=wire.hex(), status=result["status"])
            return result
        except Exception as exc:
            item["error"] = type(exc).__name__ + ": " + str(exc)
            raise
        finally:
            item["duracion_segundos"] = time.monotonic() - started


IMPORT_CHILD = r'''
import importlib, json, os, sys
sys.path.insert(0, sys.argv[1])
events = []
def audit(event, args):
    forbidden = event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.fork", "os.posix_spawn")
    forbidden = forbidden or (event == "open" and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR))
    if forbidden:
        events.append(event)
        raise RuntimeError("Efecto propio durante importación")
class NoInput:
    def read(self, *args):
        events.append("stdin.read")
        raise RuntimeError("Lectura de stdin")
    readline = read
    readlines = read
sys.stdin = NoInput()
sys.addaudithook(audit)
importlib.import_module("booking_http")
print(json.dumps({"efectos": events}))
'''

DELEGATION_CHILD = r'''
import json, runpy, sys
from pathlib import Path
project, log = map(Path, sys.argv[1:])
sys.path.insert(0, str(project))
import booking_core
def fixed(document):
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(document) + "\n")
    if document == {"sonda": "error"}:
        raise booking_core.InvalidInput("causa centinela")
    return {"disponible": False, "conflictos": ["núcleo delegado"]}
booking_core.check_booking = fixed
sys.argv = [str(project / "booking_http.py"), "--port", "0"]
runpy.run_path(sys.argv[0], run_name="__main__")
'''

BIND_CHILD = r'''
import json, runpy, socket, sys
from pathlib import Path
project, log = map(Path, sys.argv[1:3])
options = sys.argv[3:]
sys.path.insert(0, str(project))
def bound(sock, address):
    log.write_text(json.dumps({"familia": sock.family, "direccion": address}))
    raise OSError("Fallo de bind prefijado por la sonda")
socket.socket.bind = bound
sys.argv = [str(project / "booking_http.py"), *options]
runpy.run_path(sys.argv[0], run_name="__main__")
'''


class AcceptanceTests(unittest.TestCase):
    project = None

    def setUp(self):
        self.script = self.project / "booking_http.py"
        self.assertTrue(self.script.is_file() and not self.script.is_symlink(),
                        "Funcionalidad pendiente: falta booking_http.py regular; proceso no invocado")
        self.assertEqual(stat.S_IMODE(self.script.stat().st_mode), 0o644)
        tmp = tempfile.TemporaryDirectory(prefix="entradas-booking-http-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "entrada-intacta.json").write_bytes(encode(document()))

    @contextmanager
    def preserved(self):
        project, inputs = snapshot(self.project), snapshot(self.root)
        try:
            yield
        finally:
            with self.subTest(conservacion="proyecto"):
                self.assertEqual(snapshot(self.project), project, "Proyecto alterado")
            with self.subTest(conservacion="entradas"):
                self.assertEqual(snapshot(self.root), inputs, "Entradas alteradas")

    @contextmanager
    def server(self, command=None):
        with self.preserved():
            with Server(self.project, self.root, command).running() as service:
                yield service

    def once(self, arguments=(), *, code=None):
        command = [str(Path(sys.executable).resolve()), "-B"]
        command += [str(self.script), *arguments] if code is None else ["-c", code, str(self.project), *arguments]
        item = {"tipo": "proceso_corto", "comando": command, "cwd": str(self.root),
                "timeout": START_TIMEOUT, "politica_entorno": "evaluation"}
        TRACE.append(item)
        start = time.monotonic()
        with self.preserved(), process_environment("evaluation") as environment:
            environment["PATH"] = ""
            try:
                result = subprocess.run(command, cwd=self.root, env=environment, stdin=subprocess.DEVNULL,
                                        capture_output=True, timeout=START_TIMEOUT, shell=False)
                item.update(codigo=result.returncode, stdout_hex=result.stdout.hex(), stderr_hex=result.stderr.hex())
                return result
            except Exception as exc:
                item["error"] = type(exc).__name__ + ": " + str(exc)
                raise
            finally:
                item["duracion_segundos"] = time.monotonic() - start

    def assert_response(self, result, status, expected=None, *, head=False, allow=None):
        self.assertEqual(result["status"], status)
        self.assertIn(result["version"], (10, 11))
        headers = {}
        for name, value in result["headers"]:
            headers.setdefault(name.lower(), []).append(value)
        self.assertEqual(len(headers.get("content-type", [])), 1)
        self.assertTrue(json_type(headers["content-type"][0]))
        lengths = headers.get("content-length", [])
        self.assertEqual(len(lengths), 1)
        length = lengths[0].strip(" \t")
        self.assertIsNotNone(re.fullmatch(r"[0-9]+", length))
        if allow is not None:
            self.assertEqual([value.strip(" \t") for value in headers.get("allow", [])], [allow])
        if head:
            self.assertEqual(result["body"], b"")
            return
        self.assertEqual(int(length), len(result["body"]))
        try:
            value = decode(result["body"])
        except (ValueError, UnicodeError, RecursionError) as exc:
            self.fail("Respuesta no JSON UTF-8 único: " + str(exc))
        self.assertIs(type(value), dict)
        if status >= 400:
            self.assertEqual(set(value), {"error"})
            self.assertIs(type(value["error"]), str)
            self.assertTrue(value["error"].strip())
        else:
            self.assertEqual(value, expected)
            if "disponible" in expected:
                self.assertIs(type(value["disponible"]), bool)
                self.assertIs(type(value["conflictos"]), list)
                self.assertTrue(all(type(x) is str for x in value["conflictos"]))

    def health(self, server):
        self.assert_response(server.request(), 200, {"estado": "ok"})

    def post(self, server, value, expected):
        self.assert_response(server.request("POST", "/availability", encode(value),
                                            {"Content-Type": "application/json"}), 200, expected)

    def bad_document(self, server, raw):
        self.assert_response(server.request("POST", "/availability", raw,
                                            {"Content-Type": "application/json"}), 400)
        self.health(server)

    def raw_post(self, server, headers, body=b"", *, eof=False):
        wire = b"POST /availability HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        wire += b"".join(name.encode("ascii") + b": " + value.encode("ascii") + b"\r\n"
                         for name, value in headers) + b"\r\n" + body
        return server.request("POST", "/availability", raw=wire, eof=eof)

    def test_01_arranque_salud_y_cierre(self):
        with self.server() as server:
            self.health(server)
            self.health(server)

    def test_02_ayuda(self):
        for flag in ("-h", "--help"):
            with self.subTest(opcion=flag):
                result = self.once([flag])
                self.assertEqual(result.returncode, 0)
                self.assertTrue(result.stdout.strip())
                self.assertEqual(result.stderr, b"")

    def test_03_argumentos_invalidos(self):
        for args in (["--port"], ["--port", "-1"], ["--port", "65536"], ["--port", "1.0"],
                     ["--port", "abc"], ["--host", "0.0.0.0"], ["sobrante"]):
            with self.subTest(argumentos=args):
                result = self.once(args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr.strip())

    def test_04_puerto_ocupado(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, 0))
            occupied.listen(1)
            # Se mantiene la reserva abierta durante el arranque; no hay TOCTOU.
            result = self.once(["--port", str(occupied.getsockname()[1])])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertTrue(result.stderr.strip())

    def test_05_importacion_sin_efectos(self):
        result = self.once(code=IMPORT_CHILD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(decode(result.stdout), {"efectos": []})

    def test_06_puerto_predeterminado_y_extremo(self):
        with tempfile.TemporaryDirectory(prefix="sonda-bind-") as tmp:
            log = Path(tmp) / "direccion.json"
            for args, port in (([], 8000), (["--port", "65535"], 65535)):
                with self.subTest(puerto=port):
                    if log.exists():
                        log.unlink()
                    result = self.once([str(log), *args], code=BIND_CHILD)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b"")
                    self.assertTrue(result.stderr.strip())
                    self.assertEqual(decode(log.read_bytes()), {"familia": socket.AF_INET, "direccion": [HOST, port]})

    def test_07_disponibilidad(self):
        with self.server() as server:
            self.post(server, document(), {"disponible": True, "conflictos": []})

    def test_08_conflictos_igualdad_y_contencion(self):
        with self.server() as server:
            for start, end in (("10:00:00", "11:00:00"), ("09:00:00", "12:00:00"),
                               ("10:15:00", "10:45:00"), ("10:30:00", "11:30:00")):
                with self.subTest(intervalo=(start, end)):
                    self.post(server, document([booking("r", start, end)]), {"disponible": False, "conflictos": ["r"]})

    def test_09_adyacencia_y_recursos_literales(self):
        data = document([booking("a", "09:00:00", "10:00:00"), booking("b", "11:00:00", "12:00:00"),
                         booking("c", resource="sala norte"), booking("d", resource=" Sala Norte ")])
        with self.server() as server:
            self.post(server, data, {"disponible": True, "conflictos": []})

    def test_10_orden_unicode_y_escapes(self):
        resource = ' Sala É, "norte"\r\n🪑 '
        ids = ['z, "ñ"\r\n', "a🗓", "ID", "id"]
        data = document([booking(x, resource=resource) for x in ids] +
                        [booking("otro", resource=resource.strip())], resource)
        with self.server() as server:
            self.post(server, data, {"disponible": False, "conflictos": ids})

    def test_11_validacion_completa_y_recuperacion(self):
        data = document([booking("conflicto"), booking("otro", resource="otra")])
        data["reservas"][1]["inicio"] = "2026-02-30T10:00:00Z"
        with self.server() as server:
            self.bad_document(server, encode(data))
            self.post(server, document(), {"disponible": True, "conflictos": []})

    def test_12_tipos_claves_fechas_ids(self):
        variants = [None, True, [], {}, {**document(), "extra": 1},
                    document([booking("r"), booking("r", resource="otra")])]
        for field, value in (("recurso", " \t"), ("recurso", True), ("inicio", "２０２６-10-20T10:00:00Z"),
                             ("inicio", "2026-10-20T10:00:00+00:00"), ("fin", "2026-10-20T10:00:00Z")):
            item = document()
            item["solicitud"][field] = value
            variants.append(item)
        with self.server() as server:
            for item in variants:
                with self.subTest(documento=item):
                    self.bad_document(server, encode(item))

    def test_13_json_utf8_invalido(self):
        good = encode(document())
        with self.server() as server:
            for raw in (b"", b"{", good + good, b"\xff", b"\xef\xbb\xbf" + good,
                        b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}'):
                with self.subTest(cuerpo=raw):
                    self.bad_document(server, raw)

    def test_14_duplicados_json(self):
        text = encode(document([booking("r")])).decode()
        variants = ['{"solicitud": {}, "solicitud": {}, "reservas": []}',
                    text.replace('"recurso": "Sala Norte"', '"recurso": "Sala Norte", "recurso": "Sala Norte"', 1),
                    text.replace('"id": "r"', '"id": "r", "\\u0069d": "r"')]
        with self.server() as server:
            for text in variants:
                with self.subTest(cuerpo=text):
                    self.bad_document(server, text.encode())

    def test_15_rutas_exactas_y_precedencia(self):
        with self.server() as server:
            for target in ("/", "/otra", "/health/", "/health?x=1", "/availability/", "/availability?x=1"):
                for method in ("GET", "POST", "HEAD"):
                    with self.subTest(ruta=target, metodo=method):
                        self.assert_response(server.request(method, target), 404, head=method == "HEAD")
            self.health(server)

    def test_16_metodos_allow_y_head(self):
        with self.server() as server:
            for target, allow in (("/health", "GET"), ("/availability", "POST")):
                for method in ("GET", "POST", "HEAD", "PUT", "DELETE", "PATCH", "OPTIONS", "BREW"):
                    if method == allow:
                        continue
                    with self.subTest(ruta=target, metodo=method):
                        self.assert_response(server.request(method, target), 405, head=method == "HEAD", allow=allow)
            self.health(server)

    def test_17_http_10(self):
        with self.server() as server:
            self.assert_response(server.request(raw=b"GET /health HTTP/1.0\r\n\r\n"), 200, {"estado": "ok"})
            body = encode(document())
            wire = b"POST /availability HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: "
            wire += str(len(body)).encode() + b"\r\n\r\n" + body
            self.assert_response(server.request(raw=wire), 200, {"disponible": True, "conflictos": []})

    def test_18_content_type_equivalente(self):
        body = b" \r\n" + encode(document()) + b"\t "
        with self.server() as server:
            for value in ('application/json', 'APPLICATION/JSON', 'Application/Json ; CHARSET = "UTF-8"',
                          '\tapplication/json; charset=utf-8 '):
                with self.subTest(tipo=value):
                    self.assert_response(self.raw_post(server, [("Content-Length", str(len(body))),
                        ("Content-Type", value)], body), 200, {"disponible": True, "conflictos": []})

    def test_19_content_type_incompatible(self):
        body = encode(document())
        with self.server() as server:
            for extra in ([], [("Content-Type", "text/plain")], [("Content-Type", "application/json; charset=latin1")],
                          [("Content-Type", "application/json; extra=1")],
                          [("Content-Type", "application/json"), ("Content-Type", "application/json")]):
                with self.subTest(cabeceras=extra):
                    self.assert_response(self.raw_post(server, [("Content-Length", str(len(body))), *extra], body), 415)
            self.health(server)

    def test_20_longitud_ausente(self):
        with self.server() as server:
            self.assert_response(self.raw_post(server, []), 411)
            self.health(server)

    def test_21_longitud_invalida_o_duplicada(self):
        with self.server() as server:
            for lengths in (["-1"], ["+1"], ["1.0"], ["1e2"], ["1, 1"], [""], ["0", "0"], ["1", "2"]):
                with self.subTest(longitudes=lengths):
                    self.assert_response(self.raw_post(server, [("Content-Length", n) for n in lengths]), 400)
            self.health(server)

    def test_22_longitud_decimal_y_cero(self):
        body = encode(document())
        with self.server() as server:
            self.assert_response(self.raw_post(server, [("Content-Type", "application/json"),
                ("Content-Length", " \t000" + str(len(body)) + " ")], body), 200, {"disponible": True, "conflictos": []})
            self.assert_response(self.raw_post(server, [("Content-Type", "application/json"), ("Content-Length", "0")]), 400)

    def test_23_limite_inclusivo_en_bytes(self):
        base = encode(document(resource="Sala ñ"))
        body = base + b" " * (65536 - len(base))
        with self.server() as server:
            self.assert_response(self.raw_post(server, [("Content-Type", "application/json"),
                ("Content-Length", str(len(body)))], body), 200, {"disponible": True, "conflictos": []})

    def test_24_exceso_antes_de_leer_y_precedencia(self):
        with self.server() as server:
            for length in ("65537", "9" * 5001):
                with self.subTest(longitud=len(length)):
                    self.assert_response(self.raw_post(server, [("Content-Length", length)]), 413)
            self.health(server)

    def test_25_transfer_encoding(self):
        with self.server() as server:
            for value in ("chunked", "identity", "gzip"):
                with self.subTest(transfer=value):
                    self.assert_response(self.raw_post(server, [("Transfer-Encoding", value)]), 501)
                    self.assert_response(self.raw_post(server, [("Transfer-Encoding", value), ("Content-Length", "99999")]), 400)
            self.health(server)

    def test_26_cuerpo_truncado(self):
        with self.server() as server:
            self.assert_response(self.raw_post(server, [("Content-Length", "100"), ("Content-Type", "application/json")],
                                              b"{", eof=True), 400)
            self.health(server)

    def test_27_plazo_cuerpo_y_recuperacion(self):
        with self.server() as server:
            start = time.monotonic()
            self.assert_response(self.raw_post(server, [("Content-Length", "100"), ("Content-Type", "application/json")], b"{"), 408)
            # El contrato fija 2 s; margen de transporte/planificación hasta 5 s.
            self.assertLess(time.monotonic() - start, IO_TIMEOUT)
            self.health(server)

    def test_28_tipo_prima_sobre_json(self):
        with self.server() as server:
            self.assert_response(self.raw_post(server, [("Content-Length", "1"), ("Content-Type", "text/plain")], b"{"), 415)
            self.health(server)

    def test_29_delegacion_real(self):
        with tempfile.TemporaryDirectory(prefix="sonda-delegacion-http-") as tmp:
            log = Path(tmp) / "llamadas.jsonl"
            command = [str(Path(sys.executable).resolve()), "-B", "-c", DELEGATION_CHILD, str(self.project), str(log)]
            with self.server(command) as server:
                value = {"sonda": "éxito"}
                self.post(server, value, {"disponible": False, "conflictos": ["núcleo delegado"]})
                self.bad_document(server, encode({"sonda": "error"}))
            calls = [decode(line) for line in log.read_bytes().splitlines()]
            self.assertIn(value, calls)
            self.assertIn({"sonda": "error"}, calls)

    def test_30_plazo_total_con_fragmentos_y_recuperacion(self):
        raw = (b"POST /availability HTTP/1.1\r\nHost: 127.0.0.1\r\n"
               b"Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{")
        with self.server() as server:
            self.assert_response(server.request(raw=raw, trickle=True), 408)
            self.health(server)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.project.is_dir():
        parser.error("--project debe existir")
    AcceptanceTests.project = args.project.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests))
    report = {"procesos": TRACE, "total_procesos": len(TRACE),
              "peticiones": sum(len(p.get("peticiones", [])) for p in TRACE)}
    raw = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

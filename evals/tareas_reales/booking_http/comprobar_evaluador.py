"""Controles del evaluador; respuestas prefijadas y un fixture de transporte.

No crea booking_http.py ni un segundo producto de reservas. El fixture real
requiere loopback: una restricción del entorno es un error, nunca un skip.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import evaluar


def wire(value=None, *, body=None, status=200, headers=None):
    body = evaluar.encode({"estado": "ok"} if value is None else value) if body is None else body
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))] if headers is None else headers
    return (f"HTTP/1.1 {status} Fixture\r\n".encode()
            + b"".join((k + ": " + v + "\r\n").encode() for k, v in headers) + b"\r\n" + body)


class FakeProcess:
    """Ciclo de vida prefijado; no ejecuta nada ni abre sockets."""
    def __init__(self, command, **options):
        self.command, self.options = command, options
        self.returncode = None
        self.actions = []
        self.output = b'{"host":"127.0.0.1","port":12345}\n'
        options["stdout"].write(self.output)
        options["stdout"].flush()

    def poll(self):
        return self.returncode

    def send_signal(self, sig):
        self.actions.append(("signal", sig))

    def terminate(self):
        self.actions.append(("terminate",))

    def kill(self):
        self.actions.append(("kill",))

    def wait(self, timeout):
        # El entorno debe seguir existiendo hasta recoger al hijo.
        assert Path(self.options["env"]["HOME"]).is_dir()
        self.actions.append(("wait", timeout))
        self.returncode = 0
        return 0


class TrickleSocket:
    """Transporte/reloj controlados, sin sockets ni lógica de reservas."""
    def __init__(self, *, idle=False, answer=None, at=2.1, close_at=None,
                 send_error=None, reset=False, lag=False, early_headers=False):
        self.now = 0.0
        self.last_sent = 0.0
        self.idle, self.at = idle, at
        self.answer = wire({"error": "plazo"}, status=408) if answer is None else answer
        self.close_at = at + 0.02 if close_at is None else close_at
        self.send_error, self.reset, self.lag = send_error, reset, lag
        self.delivered = self.closed = False
        self.early_headers = early_headers
        self.headers_delivered = False
        self.sent = []

    def settimeout(self, value):
        pass

    def setblocking(self, value):
        assert value is False

    def sendall(self, data):
        self.sent.append(data)
        self.last_sent = self.now

    def send(self, data):
        if self.send_error and self.now >= 2:
            raise self.send_error("cierre prefijado")
        self.sendall(data)
        return len(data)

    def select(self, readers, writers, errors, timeout):
        due = self.last_sent + 2 if self.idle else (self.close_at if self.delivered else self.at)
        if self.early_headers and not self.headers_delivered:
            due = 0.1
        if writers:
            return ([self] if self.now >= due else []), writers, []
        self.now = max(self.now, min(self.now + timeout, due))
        if self.lag:
            self.now += 0.9
            self.lag = False
        return ([self] if self.now >= due else []), [], []

    def recv(self, size):
        if self.early_headers and not self.headers_delivered:
            self.headers_delivered = True
            header, separator, self.answer = self.answer.partition(b"\r\n\r\n")
            return header + separator
        if not self.delivered:
            self.delivered = True
            return self.answer
        if self.reset:
            raise ConnectionResetError("cierre prefijado tras respuesta")
        return b""

    def close(self):
        self.closed = True


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="controles-booking-http-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "proyecto"
        self.project.mkdir()
        (self.project / "protegido.txt").write_text("Centinela conservada\n")
        self.inputs = self.root / "entradas"
        self.inputs.mkdir()
        self.case = evaluar.AcceptanceTests("test_07_disponibilidad")
        self.case.project, self.case.root = self.project, self.inputs
        self.case.script = self.project / "booking_http.py"

    def service(self):
        server = evaluar.Server(self.project, self.inputs)
        server.record["control"] = "Proceso simulado; no producto"
        return server

    def assert_answer(self, raw, status=200, expected=None, **options):
        expected = {"estado": "ok"} if expected is None else expected
        self.case.assert_response(evaluar.response(raw), status, expected, **options)

    def test_anuncio_valido_y_equivalente(self):
        for raw, port in ((b'{"host":"127.0.0.1","port":1}\n', 1),
                          (b' {"port":65535,"host":"127.0.0.1"} \r\n', 65535)):
            self.assertEqual(evaluar.validate_ready(raw), port)

    def test_anuncio_rechaza_host_puerto_y_claves(self):
        variants = [{"host": host, "port": 8000} for host in ("localhost", "0.0.0.0", "::1", "example.org", 127)]
        variants += [{"host": evaluar.HOST, "port": n} for n in (0, -1, 65536, True, 1.0, "8000", None)]
        variants += [{}, [], {"host": evaluar.HOST, "port": 80, "extra": 1}]
        for value in variants:
            with self.subTest(anuncio=value), self.assertRaises(AssertionError):
                evaluar.validate_ready(evaluar.encode(value))

    def test_anuncio_rechaza_json_ambiguo(self):
        for value in (b'{"host":"127.0.0.1","port":1,"port":2}', b'{"host":"127.0.0.1","port":NaN}',
                      b"\xff", b"{}{}", b"\xef\xbb\xbf{}"):
            with self.subTest(anuncio=value), self.assertRaises((ValueError, UnicodeError)):
                evaluar.validate_ready(value)

    def test_json_equivalente_y_cabeceras_ows(self):
        self.assert_answer(wire(body=b' { "estado" : "ok" }\n'))
        body = evaluar.encode({"estado": "ok"})
        self.assert_answer(wire(body=body, headers=[("CONTENT-TYPE", 'Application/JSON ; CHARSET = "UTF-8"'),
                                                   ("content-length", " " + str(len(body)) + " ")]))

    def test_resultados_explicitamente_correctos(self):
        for expected in ({"disponible": True, "conflictos": []},
                         {"disponible": False, "conflictos": ['z, "ñ"\r\n', "a🗓"]}):
            self.assert_answer(wire(expected), expected=expected)
            self.assert_answer(wire(body=json.dumps(expected, ensure_ascii=True).encode()), expected=expected)

    def test_rechaza_falsos_positivos_negativos_orden_y_booleanos(self):
        expected = {"disponible": False, "conflictos": ["z", "a"]}
        for value in ({"disponible": True, "conflictos": []}, {"disponible": False, "conflictos": ["a", "z"]},
                      {"disponible": False, "conflictos": ["z"]}, {"disponible": 0, "conflictos": ["z", "a"]}):
            with self.subTest(respuesta=value), self.assertRaises(AssertionError):
                self.assert_answer(wire(value), expected=expected)

    def test_error_sin_imponer_texto(self):
        for value in ("entrada inválida", " \téchec ñ\n", "causa centinela"):
            self.assert_answer(wire({"error": value}, status=400), status=400)

    def test_rechaza_error_vacio_tipo_campos_extra_y_codigo(self):
        for value in ({}, {"error": ""}, {"error": " \n\t"}, {"error": 1}, {"error": "causa", "otro": 1}):
            with self.subTest(error=value), self.assertRaises(AssertionError):
                self.assert_answer(wire(value, status=400), status=400)
        with self.assertRaises(AssertionError):
            self.assert_answer(wire({"error": "causa"}, status=200), status=400)

    def test_rechaza_json_duplicados_constantes_utf8_y_doble_objeto(self):
        for body in (b"{}{}", b"\xff", b"\xef\xbb\xbf{}", b'{"estado":"ok","estado":"ok"}',
                     b'{"estado":NaN}', b'{"estado":Infinity}', b'[]'):
            with self.subTest(cuerpo=body), self.assertRaises(AssertionError):
                self.assert_answer(wire(body=body))

    def test_longitud_en_bytes_no_caracteres(self):
        body = evaluar.encode({"error": "ñ"})
        with self.assertRaises(AssertionError):
            self.assert_answer(wire(body=body, status=400, headers=[("Content-Type", "application/json"),
                ("Content-Length", str(len(body.decode())))]), status=400)

    def test_rechaza_cabeceras_y_respuesta_incompleta(self):
        for headers in ([], [("Content-Type", "text/html"), ("Content-Length", "16")],
                        [("Content-Type", "application/json"), ("Content-Length", "-1")],
                        [("Content-Type", "application/json"), ("Content-Length", "1"), ("Content-Length", "1")]):
            with self.subTest(cabeceras=headers), self.assertRaises(AssertionError):
                self.assert_answer(wire(headers=headers))
        with self.assertRaises(AssertionError):
            evaluar.response(b"HTTP/1.1 200 OK\r\n")

    def test_head_sin_cuerpo_y_allow(self):
        for length in ("0", "29"):
            self.assert_answer(wire(body=b"", status=405, headers=[("Content-Type", "application/json"),
                ("Content-Length", length), ("Allow", " GET ")]), status=405, head=True, allow="GET")
        with self.assertRaises(AssertionError):
            self.assert_answer(wire({"error": "método"}, status=405), status=405, head=True)
        with self.assertRaises(AssertionError):
            self.assert_answer(wire({"error": "método"}, status=405), status=405, allow="GET")

    def test_ausencia_es_fallo_antes_de_invocar(self):
        result = unittest.TestResult()
        with patch.object(evaluar.subprocess, "Popen") as popen, patch.object(evaluar.socket, "socket") as sock:
            self.case.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.errors, [])
        self.assertIn("proceso no invocado", result.failures[0][1])
        popen.assert_not_called()
        sock.assert_not_called()
        self.assertFalse(self.case.script.exists())

    def test_identidades_estaticas_coinciden(self):
        from repair_project import static_test_ids
        found = [t.id() for t in unittest.TestLoader().loadTestsFromTestCase(evaluar.AcceptanceTests)]
        self.assertEqual(sorted(found), static_test_ids(Path(evaluar.__file__).read_bytes(), evaluar.__name__))
        self.assertTrue(found)
        self.assertEqual(len(found), len(set(found)))

    def test_entorno_vivo_hasta_recoger_y_stdout_unico(self):
        server = self.service()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SINTETICA_NO_HEREDAR", "PYTHONPATH": "SINTETICA"}), \
                patch.object(evaluar.subprocess, "Popen", side_effect=FakeProcess):
            with server.running():
                options = server.process.options
                home = Path(options["env"]["HOME"])
                self.assertTrue(home.is_dir())
                self.assertNotIn("OPENAI_API_KEY", options["env"])
                self.assertNotIn("PYTHONPATH", options["env"])
                self.assertEqual(options["cwd"], self.inputs)
                self.assertEqual(options["stdin"], subprocess.DEVNULL)
                self.assertFalse(options["shell"])
                self.assertEqual(server.command, [str(Path(sys.executable).resolve()), "-B",
                                                  str(self.case.script), "--port", "0"])
        self.assertFalse(home.exists())
        self.assertTrue(server.record["terminacion"]["recogido"])
        self.assertFalse(server.record["terminacion"]["forzado"])

    def test_fallo_dentro_del_ambito_limpia(self):
        server = self.service()
        with patch.object(evaluar.subprocess, "Popen", side_effect=FakeProcess):
            with self.assertRaisesRegex(AssertionError, "fallo prefijado"):
                with server.running():
                    raise AssertionError("fallo prefijado")
        self.assertTrue(server.record["terminacion"]["recogido"])
        self.assertEqual(server.process.returncode, 0)

    def test_fallo_de_popen_no_se_silencia(self):
        server = self.service()
        with patch.object(evaluar.subprocess, "Popen", side_effect=OSError("transporte bloqueado")):
            with self.assertRaisesRegex(OSError, "bloqueado"):
                with server.running():
                    self.fail("No debe entrar")
        self.assertIsNone(server.process)
        self.assertIn("stdout_hex", server.record)

    def test_anuncio_malformado_limpia_sin_conectar(self):
        server = self.service()
        def invalid(*args, **options):
            proc = FakeProcess(*args, **options)
            options["stdout"].seek(0)
            options["stdout"].truncate()
            options["stdout"].write(b'{"host":"example.org","port":80}\n')
            options["stdout"].flush()
            return proc
        with patch.object(evaluar.subprocess, "Popen", side_effect=invalid), \
                patch.object(evaluar.socket, "create_connection") as connect:
            with self.assertRaises(AssertionError):
                with server.running():
                    self.fail("No debe entrar")
        connect.assert_not_called()
        self.assertTrue(server.record["terminacion"]["recogido"])

    def test_salida_adicional_rechazada(self):
        server = self.service()
        with patch.object(evaluar.subprocess, "Popen", side_effect=FakeProcess):
            with self.assertRaisesRegex(AssertionError, "stdout"):
                with server.running():
                    server.process.options["stdout"].write(b"aviso\n")

    def test_logs_stderr_permitidos_y_traceback_rechazado(self):
        for raw, rejected in ((b"GET fixture 200\n", False), (b"Traceback (most recent call last)\n", True)):
            server = self.service()
            with patch.object(evaluar.subprocess, "Popen", side_effect=FakeProcess):
                if rejected:
                    with self.assertRaisesRegex(AssertionError, "Traceback"):
                        with server.running():
                            server.process.options["stderr"].write(raw)
                else:
                    with server.running():
                        server.process.options["stderr"].write(raw)

    def test_timeout_arranque_y_recogida(self):
        server = self.service()
        with patch.object(evaluar.subprocess, "Popen", side_effect=FakeProcess), \
                patch.object(evaluar, "read_ready", side_effect=TimeoutError("sin anuncio")):
            with self.assertRaises(TimeoutError):
                with server.running():
                    self.fail("No debe entrar")
        self.assertTrue(server.record["terminacion"]["recogido"])

    def test_lector_arranque_eof_y_plazo(self):
        path = self.root / "salida"
        path.write_bytes(b"{parcial")
        with self.assertRaises(RuntimeError):
            evaluar.read_ready(path, Mock(poll=Mock(return_value=1)))
        path.write_bytes(b"")
        with patch.object(evaluar.time, "monotonic", side_effect=[0, 0, 6]), patch.object(evaluar.time, "sleep"):
            with self.assertRaises(TimeoutError):
                evaluar.read_ready(path, Mock(poll=Mock(return_value=None)))

    def test_terminacion_forzada_y_kill_recogen(self):
        proc = Mock(returncode=None)
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired("fixture", 3), subprocess.TimeoutExpired("fixture", 3), 0]
        result = evaluar.stop(proc)
        self.assertTrue(result["forzado"])
        proc.send_signal.assert_called_once_with(evaluar.signal.SIGINT)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        self.assertEqual(proc.wait.call_count, 3)

    def test_terminacion_ya_finalizada_tambien_recoge(self):
        proc = Mock(returncode=1)
        proc.poll.return_value = 1
        self.assertEqual(evaluar.stop(proc), {"codigo": 1, "forzado": False, "recogido": True})
        proc.wait.assert_called_once()
        proc.send_signal.assert_not_called()

    def test_proceso_corto_aislado_y_error_tecnico(self):
        seen = {}
        def fixed(command, **options):
            seen.update(options)
            self.assertTrue(Path(options["env"]["HOME"]).is_dir())
            self.assertEqual(command[:2], [str(Path(sys.executable).resolve()), "-B"])
            self.assertEqual(options["timeout"], evaluar.START_TIMEOUT)
            return subprocess.CompletedProcess(command, 2, b"", "argumento inválido".encode())
        with patch.object(evaluar.subprocess, "run", side_effect=fixed):
            result = self.case.once(["--port", "abc"])
        self.assertEqual(result.returncode, 2)
        self.assertFalse(Path(seen["env"]["HOME"]).exists())
        with patch.object(evaluar.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 5)):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.case.once()

    def test_conservacion_detecta_mutacion_incluso_en_fallo(self):
        with self.assertRaisesRegex(AssertionError, "Proyecto alterado"):
            with self.case.preserved():
                (self.project / "protegido.txt").write_text("alterado")
                raise RuntimeError("fallo prefijado")

    def fake_socket(self, raw):
        sock = Mock()
        sock.recv.side_effect = [raw[:13], raw[13:], b""]
        return sock

    def test_http_client_solo_loopback_y_cierre(self):
        server = self.service()
        server.port = 12345
        connection = Mock(sock=self.fake_socket(wire()))
        with patch.object(evaluar.http.client, "HTTPConnection", return_value=connection) as factory:
            self.assert_answer(server.request()["raw"])
        factory.assert_called_once_with("127.0.0.1", 12345, timeout=evaluar.IO_TIMEOUT)
        connection.close.assert_called_once()

    def test_transporte_crudo_duplica_cabeceras_y_envia_eof(self):
        server = self.service()
        server.port = 12345
        sock = self.fake_socket(wire({"error": "longitud"}, status=400))
        @contextmanager
        def connection(*args, **kwargs):
            self.assertEqual(args[0], ("127.0.0.1", 12345))
            try:
                yield sock
            finally:
                sock.close()
        with patch.object(evaluar.socket, "create_connection", side_effect=connection):
            result = self.case.raw_post(server, [("Content-Length", "1"), ("Content-Length", "2")], b"{", eof=True)
        self.assertEqual(result["status"], 400)
        self.assertEqual(sock.sendall.call_args.args[0].count(b"Content-Length:"), 2)
        sock.shutdown.assert_called_once_with(socket.SHUT_WR)
        sock.close.assert_called_once()
        self.assertEqual(server.record["peticiones"][0]["metodo"], "POST")
        self.assertEqual(server.record["peticiones"][0]["ruta"], "/availability")

    def test_traza_cruda_usa_linea_enviada(self):
        for raw, expected in ((b"GET /fixture HTTP/1.0\r\n\r\n", ("GET", "/fixture")),
                              (b"POST /otro?x=1 HTTP/1.1\r\n\r\n", ("POST", "/otro?x=1")),
                              (b"linea incompleta\r\n", (None, None))):
            server = self.service()
            server.port = 12345
            sock = self.fake_socket(wire())
            @contextmanager
            def connection(*args, **kwargs):
                try:
                    yield sock
                finally:
                    sock.close()
            with self.subTest(raw=raw), patch.object(evaluar.socket, "create_connection", side_effect=connection):
                server.request("DELETE", "/predeterminado", b"no enviado", {"X": "no enviado"}, raw=raw)
            item = server.record["peticiones"][0]
            self.assertEqual((item["metodo"], item["ruta"]), expected)
            self.assertEqual(bytes.fromhex(item["peticion_cruda_hex"]), raw)
            self.assertIsNone(item["cabeceras"])
            self.assertIsNone(item["cuerpo_hex"])
            sock.sendall.assert_called_once_with(raw)
            sock.close.assert_called_once()

    @contextmanager
    def trickle_transport(self, sock):
        server = self.service()
        server.port = 12345
        server.record["control"] = "Goteo y reloj prefijados; no producto ni socket real"
        evaluar.TRACE.append(server.record)
        health = Mock(sock=self.fake_socket(wire()))
        @contextmanager
        def connection(*args, **kwargs):
            self.assertEqual(args[0], ("127.0.0.1", 12345))
            try:
                yield sock
            finally:
                sock.close()
        @contextmanager
        def service():
            yield server
        with patch.object(evaluar.socket, "create_connection", side_effect=connection), \
                patch.object(evaluar.select, "select", side_effect=sock.select), \
                patch.object(evaluar.time, "monotonic", side_effect=lambda: sock.now), \
                patch.object(evaluar.http.client, "HTTPConnection", return_value=health), \
                patch.object(self.case, "server", side_effect=service):
            yield server, health

    def test_goteo_acepta_408_en_plazo_y_recuperacion(self):
        for at in (2, 2.35):
            sock = TrickleSocket(at=at)
            with self.subTest(instante=at), self.trickle_transport(sock) as (server, health):
                self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                self.assertEqual(server.record["peticiones"][1]["status"], 200)
                health.request.assert_called_once_with("GET", "/health", body=None, headers={})
                health.close.assert_called_once()
            self.assertTrue(sock.closed)
            self.assertGreaterEqual(len(sock.sent), 5)
            self.assertLess(sum(len(x) for x in sock.sent[1:]) + 1, 100)

    def test_goteo_rechaza_timeout_reiniciado(self):
        sock = TrickleSocket(idle=True)
        with self.trickle_transport(sock) as (server, health):
            with self.assertRaisesRegex(AssertionError, "plazo total"):
                self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
            self.assertGreaterEqual(sock.last_sent, 2)
            self.assertFalse(sock.delivered)
            self.assertEqual(sock.now, 2.5)
            health.request.assert_not_called()
        self.assertTrue(sock.closed)

    def test_goteo_rechaza_cierre_tardio(self):
        sock = TrickleSocket(at=2, close_at=3)
        with self.trickle_transport(sock):
            with self.assertRaisesRegex(AssertionError, "plazo total"):
                self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
        self.assertTrue(sock.delivered)
        self.assertTrue(sock.closed)

    def test_goteo_cabeceras_tempranas_no_detienen_envio(self):
        sock = TrickleSocket(idle=True, early_headers=True)
        with self.trickle_transport(sock):
            with self.assertRaisesRegex(AssertionError, "plazo total"):
                self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
        self.assertTrue(sock.headers_delivered)
        self.assertFalse(sock.delivered)
        self.assertGreaterEqual(sock.last_sent, 2)
        self.assertTrue(sock.closed)

    def test_goteo_cierre_durante_envio_no_oculta_respuesta(self):
        for error in (BrokenPipeError, ConnectionResetError):
            for status in (408, 400):
                sock = TrickleSocket(send_error=error, answer=wire({"error": "plazo"}, status=status))
                with self.subTest(error=error, status=status), self.trickle_transport(sock) as (server, health):
                    if status == 408:
                        self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                    else:
                        with self.assertRaises(AssertionError):
                            self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                    self.assertIn(error.__name__, server.record["peticiones"][0]["goteo"]["cierre_durante_envio"])
                self.assertTrue(sock.closed)

    def test_goteo_reset_exige_respuesta_completa(self):
        for answer in (wire({"error": "plazo"}, status=408), b"HTTP/1.1 408 Parcial\r\n", b""):
            sock = TrickleSocket(answer=answer, reset=True)
            with self.subTest(answer=answer), self.trickle_transport(sock):
                if answer == b"" or answer.endswith(b"Parcial\r\n"):
                    with self.assertRaises(AssertionError):
                        self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                else:
                    self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
            self.assertTrue(sock.closed)

    def test_goteo_medicion_irregular_es_error(self):
        sock = TrickleSocket(lag=True)
        with self.trickle_transport(sock):
            with self.assertRaisesRegex(RuntimeError, "medición inválida"):
                self.case.test_30_plazo_total_con_fragmentos_y_recuperacion()
        self.assertTrue(sock.closed)

    def test_error_transporte_cierra_y_no_es_skip(self):
        server = self.service()
        server.port = 12345
        connection = Mock()
        connection.request.side_effect = socket.timeout("plazo agotado")
        with patch.object(evaluar.http.client, "HTTPConnection", return_value=connection):
            with self.assertRaises(socket.timeout):
                server.request()
        connection.close.assert_called_once()
        self.assertIn("error", server.record["peticiones"][0])

    def test_no_conecta_sin_puerto_validado(self):
        server = self.service()
        for port in (None, 0, True, "8000", 65536):
            server.port = port
            with patch.object(evaluar.http.client, "HTTPConnection") as conn, self.assertRaises(AssertionError):
                server.request()
            conn.assert_not_called()

    def test_lectura_respuesta_tiene_plazo_total(self):
        with patch.object(evaluar.time, "monotonic", side_effect=[0, 0, 6]):
            with self.assertRaises(TimeoutError):
                evaluar.read_closed(Mock(recv=Mock(return_value=b"x")))

    def test_sonda_delegacion_en_hijo_sin_producto(self):
        bootstrap = r'''
import json, runpy, sys, types
core = types.ModuleType("booking_core")
class InvalidInput(ValueError): pass
core.InvalidInput = InvalidInput
sys.modules["booking_core"] = core
def loaded(path, run_name):
    result = core.check_booking({"sonda": "éxito"})
    try:
        core.check_booking({"sonda": "error"})
    except core.InvalidInput:
        error = True
    else:
        error = False
    print(json.dumps({"resultado": result, "error": error}))
runpy.run_path = loaded
'''
        with tempfile.TemporaryDirectory(prefix="control-delegacion-") as tmp:
            log = Path(tmp) / "llamadas"
            result = self.case.once([str(log)], code=bootstrap + evaluar.DELEGATION_CHILD)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            self.assertEqual(evaluar.decode(result.stdout), {"resultado": {"disponible": False,
                "conflictos": ["núcleo delegado"]}, "error": True})
            self.assertEqual([evaluar.decode(x) for x in log.read_bytes().splitlines()],
                             [{"sonda": "éxito"}, {"sonda": "error"}])
        self.assertNotIn("booking_http", sys.modules)
        self.assertFalse(self.case.script.exists())

    def test_sonda_importacion_detecta_efecto_incluso_si_se_captura(self):
        for behavior, expected in (("pass", []),
                                   ("try:\n            sys.audit('socket.bind', None, ('127.0.0.1', 0))\n"
                                    "        except RuntimeError:\n            pass", ["socket.bind"])):
            bootstrap = '''import importlib, sys, types
original = importlib.import_module
def importing(name):
    if name == "booking_http":
        BEHAVIOR
        return types.ModuleType(name)
    return original(name)
importlib.import_module = importing
'''.replace("BEHAVIOR", behavior)
            result = self.case.once(code=bootstrap + evaluar.IMPORT_CHILD)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            self.assertEqual(evaluar.decode(result.stdout), {"efectos": expected})

    def test_proceso_real_sin_sockets_se_recoge(self):
        # Fixture de proceso, no servidor: nunca se contacta con el puerto anunciado.
        code = ('import json, signal, sys\n'
                'signal.signal(signal.SIGINT, lambda *args: sys.exit(0))\n'
                'print(json.dumps({"host":"127.0.0.1","port":12345}), flush=True)\n'
                'signal.pause()\n')
        service = evaluar.Server(self.project, self.inputs,
                                 [str(Path(sys.executable).resolve()), "-B", "-c", code])
        service.record["control"] = "Fixture real de proceso sin socket; no servidor ni producto"
        with service.running():
            self.assertIsNone(service.process.poll())
        self.assertEqual(service.process.returncode, 0)
        self.assertTrue(service.record["terminacion"]["recogido"])


FIXTURE = r'''
# Fixture de transporte con respuesta constante, sin dominio de reservas.
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
class Fixed(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"fixture": "ñ"}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True
server = HTTPServer(("127.0.0.1", 0), Fixed)
try:
    print(json.dumps({"host": "127.0.0.1", "port": server.server_port}), flush=True)
    server.serve_forever(poll_interval=0.01)
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
'''


TRICKLE_FIXTURE = r'''
# Fixture de dos políticas de lectura, sin producto ni dominio de reservas.
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, socket, sys, time
class Fixed(BaseHTTPRequestHandler):
    def reply(self, status, value):
        body = json.dumps(value).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # El control negativo ya puede haber cerrado su cliente.
        self.close_connection = True
    def do_GET(self):
        self.reply(200, {"estado": "ok"})
    def do_POST(self):
        deadline = time.monotonic() + 2
        try:
            while True:
                remaining = 2 if sys.argv[1] == "inactividad" else deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.connection.settimeout(remaining)
                if not self.rfile.read1(1):
                    break
        except (socket.timeout, ConnectionResetError):
            pass
        self.reply(408, {"error": "plazo del fixture"})
server = HTTPServer(("127.0.0.1", 0), Fixed)
try:
    print(json.dumps({"host": "127.0.0.1", "port": server.server_port}), flush=True)
    server.serve_forever(poll_interval=0.01)
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
'''


class TransportFixtureTests(unittest.TestCase):
    def test_fixture_real_loopback_y_limpieza(self):
        with tempfile.TemporaryDirectory(prefix="fixture-transporte-http-") as tmp:
            root = Path(tmp)
            server = evaluar.Server(root, root, [str(Path(sys.executable).resolve()), "-B", "-c", FIXTURE])
            server.record["control"] = "Fixture real de transporte constante; no producto"
            with server.running():
                result = server.request(target="/fixture")
                self.assertEqual(evaluar.decode(result["body"]), {"fixture": "ñ"})
                self.assertEqual(result["status"], 200)
                raw = server.request(raw=b"GET /fixture HTTP/1.0\r\n\r\n")
                self.assertEqual(evaluar.decode(raw["body"]), {"fixture": "ñ"})
                self.assertEqual(raw["status"], 200)
                self.assertEqual(server.record["peticiones"][1]["metodo"], "GET")
                self.assertEqual(server.record["peticiones"][1]["ruta"], "/fixture")
            self.assertTrue(server.record["terminacion"]["recogido"])
            self.assertEqual(server.process.returncode, 0)
            # No inferir propiedad de un puerto mediante conectar/rebind después:
            # otro proceso podría adquirirlo. Se comprueban nuestros recursos.
            self.assertFalse((root / "booking_http.py").exists())

    def check_trickle_fixture(self, policy):
        with tempfile.TemporaryDirectory(prefix="fixture-goteo-http-") as tmp:
            root = Path(tmp)
            server = evaluar.Server(root, root, [str(Path(sys.executable).resolve()), "-B", "-c", TRICKLE_FIXTURE, policy])
            server.record["control"] = "Fixture real de goteo " + policy + "; sin reservas"
            case = evaluar.AcceptanceTests("test_30_plazo_total_con_fragmentos_y_recuperacion")
            with server.running():
                @contextmanager
                def service():
                    yield server
                with patch.object(case, "server", side_effect=service):
                    if policy == "total":
                        case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                    else:
                        with self.assertRaisesRegex(AssertionError, "plazo total"):
                            case.test_30_plazo_total_con_fragmentos_y_recuperacion()
                        case.health(server)
            self.assertTrue(server.record["terminacion"]["recogido"])
            self.assertFalse(server.record["terminacion"]["forzado"])
            self.assertFalse((root / "booking_http.py").exists())

    def test_fixture_goteo_plazo_total(self):
        self.check_trickle_fixture("total")

    def test_fixture_goteo_rechaza_inactividad(self):
        self.check_trickle_fixture("inactividad")


if __name__ == "__main__":
    program = unittest.main(verbosity=2, exit=False)
    print(json.dumps({"alcance": "controles prefijados y fixture de transporte, sin producto",
                      "trazas": evaluar.TRACE}, ensure_ascii=True))
    sys.exit(0 if program.result.wasSuccessful() else 1)

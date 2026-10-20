"""Regresión de HEAD ante errores tempranos, con bytes TCP efectivos."""

from pathlib import Path
import select
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from evals.tareas_reales.booking_http import evaluar


def exchange(server, request):
    """Enviar y recibir hasta EOF/reset, conservando datos tras fallar el envío."""
    if type(server.port) is not int or not 1 <= server.port <= 65535:
        raise AssertionError("Puerto sin validar")
    item = {"peticion_cruda_hex": request.hex(), "cierre": None}
    server.record["peticiones"].append(item)
    start = time.monotonic()
    deadline = start + evaluar.IO_TIMEOUT
    received = bytearray()
    sent = 0
    sending = True
    try:
        with socket.create_connection((evaluar.HOST, server.port),
                                      timeout=evaluar.IO_TIMEOUT) as connection:
            connection.setblocking(False)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("La respuesta no cerró dentro del plazo total")
                readable, writable, _ = select.select(
                    [connection], [connection] if sending else [], [], remaining)
                if readable:
                    try:
                        chunk = connection.recv(8192)
                    except BlockingIOError:
                        chunk = None
                    except ConnectionResetError as exc:
                        item["cierre"] = "reset"
                        item["error_recepcion"] = str(exc)
                        break
                    if chunk == b"":
                        item["cierre"] = "eof"
                        break
                    if chunk:
                        received.extend(chunk)
                        if len(received) > 262144:
                            raise AssertionError("Respuesta desmesurada")
                if writable and sending:
                    try:
                        count = connection.send(request[sent:sent + 4096])
                    except BlockingIOError:
                        continue
                    except (BrokenPipeError, ConnectionResetError) as exc:
                        item["error_envio"] = type(exc).__name__ + ": " + str(exc)
                        sending = False
                        continue
                    if count == 0:
                        raise RuntimeError("Envío sin progreso")
                    sent += count
                    sending = sent < len(request)
        # response solo interpreta las cabeceras: el cuerpo conserva TODOS los
        # bytes recibidos, también con HEAD o después de un cierre por reset.
        result = evaluar.response(bytes(received))
        item["status"] = result["status"]
        return result
    except BaseException as exc:
        item["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        item.update(respuesta_hex=received.hex(), bytes_enviados=sent,
                    duracion_segundos=time.monotonic() - start)


class TestBookingHttpHeadRegression(unittest.TestCase):
    def check_version(self, version):
        project = Path(__file__).resolve().parents[1]
        # Entradas sintéticas; el evaluador conserva arranque en puerto 0,
        # comprobación del host y recogida del hijo incluso ante una aserción.
        with tempfile.TemporaryDirectory(prefix="regresion-head-") as tmp:
            with evaluar.Server(project, Path(tmp)).running() as server:
                def check(method, target, status, *, head=False, allow=None):
                    raw = (f"{method} {target} HTTP/{version}\r\n"
                           "Host: 127.0.0.1\r\n\r\n").encode("ascii")
                    result = exchange(server, raw)
                    self.assertIn(server.record["peticiones"][-1]["cierre"], ("eof", "reset"))
                    expected = {"estado": "ok"} if status == 200 else None
                    evaluar.AcceptanceTests.assert_response(
                        self, result, status, expected, head=head, allow=allow)

                check("GET", "/health", 200)
                cases = [
                    ("HEAD", "/health", 405, True, "GET"),
                    ("HEAD", "/desconocida", 404, True, None),
                    ("HEAD", "/" + "a" * 69999, 414, True, None),
                    ("HEAD", "/" + "a" * 70000, 414, True, None),
                    ("GET", "/" + "a" * 70000, 414, False, None),
                    ("HEADX", "/" + "a" * 70000, 414, False, None),
                    ("head", "/" + "a" * 70000, 414, False, None),
                ]
                for method, target, status, head, allow in cases:
                    with self.subTest(version=version, method=method, longitud=len(target)):
                        check(method, target, status, head=head, allow=allow)
                        check("GET", "/health", 200)

    def test_head_largo_http_1_0_cierre_y_recuperacion(self):
        self.check_version("1.0")

    def test_head_largo_http_1_1_cierre_y_recuperacion(self):
        self.check_version("1.1")


class TestRawExchange(unittest.TestCase):
    """Controles del transporte sin sockets ni ejecución del producto."""

    def setUp(self):
        self.server = SimpleNamespace(port=12345, record={"peticiones": []})
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.request = b"HEAD /health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        self.headers = (b"HTTP/1.0 405 Method Not Allowed\r\n"
                        b"Content-Type: application/json\r\nContent-Length: 20\r\n")

    def receive(self, wire, *, reset=False, send_error=False):
        connection = self.connection
        connection.send.side_effect = BrokenPipeError("prefijado") if send_error else None
        connection.send.return_value = len(self.request)
        connection.recv.side_effect = [wire, ConnectionResetError("prefijado") if reset else b""]
        with patch.object(socket, "create_connection", return_value=connection) as connect, \
                patch.object(select, "select", side_effect=[
                    ([], [connection], []), ([connection], [], []), ([connection], [], [])]):
            result = exchange(self.server, self.request)
        connect.assert_called_once_with(("127.0.0.1", 12345), timeout=evaluar.IO_TIMEOUT)
        connection.__exit__.assert_called_once()
        return result

    def test_cierre_sin_connection_y_allow_equivalente(self):
        for name in (b"Allow", b"allow", b"aLlOw"):
            with self.subTest(name=name):
                self.connection.reset_mock()
                result = self.receive(self.headers + name + b": GET\r\n\r\n")
                evaluar.AcceptanceTests.assert_response(self, result, 405, head=True, allow="GET")
                self.assertEqual(self.server.record["peticiones"][-1]["cierre"], "eof")

    def test_allow_ausente_o_valor_distinto_se_rechazan(self):
        for extra in (b"", b"Allow: POST\r\n", b"Allow: get\r\n"):
            with self.subTest(extra=extra):
                result = evaluar.response(self.headers + extra + b"\r\n")
                with self.assertRaises(AssertionError):
                    evaluar.AcceptanceTests.assert_response(self, result, 405, head=True, allow="GET")

    def test_error_envio_y_reset_conservan_cuerpo_head_indebido(self):
        wire = self.headers + b"Allow: GET\r\n\r\n" + b'{"error":"indebido"}'
        result = self.receive(wire, reset=True, send_error=True)
        self.assertEqual(result["raw"], wire)
        self.assertEqual(result["body"], b'{"error":"indebido"}')
        with self.assertRaises(AssertionError):
            evaluar.AcceptanceTests.assert_response(self, result, 405, head=True, allow="GET")
        item = self.server.record["peticiones"][-1]
        self.assertEqual(item["cierre"], "reset")
        self.assertIn("BrokenPipeError", item["error_envio"])

    def test_cabecera_close_sin_cierre_agota_plazo_y_cierra_cliente(self):
        wire = self.headers + b"Connection: close\r\nAllow: GET\r\n\r\n"
        self.connection.recv.return_value = wire
        with patch.object(socket, "create_connection", return_value=self.connection), \
                patch.object(select, "select", return_value=([self.connection], [], [])), \
                patch.object(time, "monotonic", side_effect=[0, 0, 6, 6]):
            with self.assertRaises(TimeoutError):
                exchange(self.server, self.request)
        self.connection.__exit__.assert_called_once()
        item = self.server.record["peticiones"][-1]
        self.assertIsNone(item["cierre"])
        self.assertEqual(bytes.fromhex(item["respuesta_hex"]), wire)

    def test_reset_con_respuesta_incompleta_se_rechaza(self):
        with self.assertRaisesRegex(AssertionError, "incompleta"):
            self.receive(b"HTTP/1.0 414", reset=True)
        self.assertEqual(self.server.record["peticiones"][-1]["cierre"], "reset")

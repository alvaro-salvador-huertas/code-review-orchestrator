"""Adaptador HTTP local del nucleo protegido de reservas (contrato 007)."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import socket
from socketserver import TCPServer
import sys
import time

import booking_core


_HOST = "127.0.0.1"
_BODY_LIMIT = 65536
_BODY_SECONDS = 2.0
_CONTENT_TYPE = re.compile(
    r'[ \t]*application/json[ \t]*'
    r'(?:;[ \t]*charset[ \t]*=[ \t]*(?:utf-8|"utf-8")[ \t]*)?',
    re.IGNORECASE | re.ASCII,
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clave JSON duplicada")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Constante JSON no permitida: " + value)


class _LocalServer(HTTPServer):
    address_family = socket.AF_INET

    def server_bind(self):
        # Evita la resolucion de nombres que HTTPServer realiza por defecto.
        TCPServer.server_bind(self)
        self.server_name = _HOST
        self.server_port = self.server_address[1]


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 permite atender ambas versiones sin conexiones persistentes
    # ni respuestas 100 Continue anteriores a la validacion de cabeceras.
    protocol_version = "HTTP/1.0"
    timeout = 2.0

    def log_message(self, format, *args):
        # El unico mensaje de stdout es el anuncio inicial del servidor.
        pass

    def _reply(self, status, document, allow=None):
        # Los escapes ASCII tambien son UTF-8 valido y conservan incluso
        # cadenas JSON con sustitutos Unicode escapados.
        body = json.dumps(document, ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.close_connection = True
        self.connection.settimeout(self.timeout)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        if allow is not None:
            self.send_header("Allow", allow)
        self.end_headers()
        if self.command != "HEAD" and not self._head_request:
            self.wfile.write(body)
        self.wfile.flush()

    def send_error(self, code, message=None, explain=None):
        self._reply(code, {"error": message or "Peticion HTTP invalida"})

    def handle(self):
        """Una peticion por conexion, con despacho para cualquier metodo."""
        self.close_connection = True
        self.command = None
        self._head_request = False
        self.requestline = ""
        self.request_version = "HTTP/1.0"
        try:
            # Reconocer el metodo exacto antes de errores de lectura/analisis;
            # parse_request puede reiniciar command antes de responder un error.
            self.raw_requestline = self.rfile.readline(5)
            self._head_request = self.raw_requestline == b"HEAD "
            if self.raw_requestline and not self.raw_requestline.endswith(b"\n"):
                self.raw_requestline += self.rfile.readline(65537 - len(self.raw_requestline))
            if not self.raw_requestline:
                return
            if len(self.raw_requestline) > 65536:
                self.send_error(414, "Linea de peticion demasiado larga")
                return
            if not self.parse_request():
                return
            # BaseHTTPRequestHandler normaliza prefijos '//'. El contrato
            # exige comparar la ruta literal, sin esa normalizacion.
            self.path = self.requestline.split()[1]
            self.close_connection = True
            self._dispatch()
        except TimeoutError:
            try:
                self.send_error(408, "Plazo de lectura agotado")
            except OSError:
                pass
        except OSError:
            # Un cliente desconectado no impide atender al siguiente.
            pass
        finally:
            self.close_connection = True

    def _dispatch(self):
        if self.path not in ("/health", "/availability"):
            self.send_error(404, "Ruta desconocida")
            return
        allowed = "GET" if self.path == "/health" else "POST"
        if self.command != allowed:
            self._reply(405, {"error": "Metodo no permitido"}, allow=allowed)
            return
        if self.path == "/health":
            self._reply(200, {"estado": "ok"})
            return
        self._availability()

    def _read_body(self, length):
        deadline = time.monotonic() + _BODY_SECONDS
        body = bytearray()
        while len(body) < length:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self.connection.settimeout(remaining)
            # read1 hace como maximo una lectura de socket: read podria
            # reiniciar su espera interna con cada fragmento recibido.
            part = self.rfile.read1(length - len(body))
            if time.monotonic() >= deadline:
                raise TimeoutError
            if not part:
                raise ValueError("Cuerpo incompleto")
            body.extend(part)
        return bytes(body)

    def _availability(self):
        lengths = self.headers.get_all("Content-Length", [])
        encodings = self.headers.get_all("Transfer-Encoding", [])
        if encodings:
            self.send_error(
                400 if lengths else 501,
                "Transfer-Encoding incompatible con Content-Length"
                if lengths else "Transfer-Encoding no soportado",
            )
            return
        if not lengths:
            self.send_error(411, "Falta Content-Length")
            return
        if len(lengths) != 1:
            self.send_error(400, "Content-Length duplicado")
            return
        length_text = lengths[0].strip(" \t")
        if re.fullmatch(r"[0-9]+", length_text) is None:
            self.send_error(400, "Content-Length invalido")
            return
        # Comparar antes de int evita desbordamientos y limites del interprete
        # para numeros con miles de digitos; los ceros iniciales son validos.
        significant = length_text.lstrip("0") or "0"
        limit = str(_BODY_LIMIT)
        if (len(significant) > len(limit)
                or (len(significant) == len(limit) and significant > limit)):
            self.send_error(413, "Cuerpo demasiado grande")
            return
        length = int(significant)
        content_types = self.headers.get_all("Content-Type", [])
        if (len(content_types) != 1
                or _CONTENT_TYPE.fullmatch(content_types[0]) is None):
            self.send_error(415, "Content-Type no soportado")
            return
        try:
            body = self._read_body(length)
        except TimeoutError:
            self.send_error(408, "Plazo de lectura del cuerpo agotado")
            return
        except ValueError:
            self.send_error(400, "Cuerpo incompleto")
            return
        try:
            # Decodificar primero impide autodeteccion de UTF-16/32 y BOM.
            document = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (ValueError, RecursionError):
            self.send_error(400, "Documento JSON UTF-8 invalido")
            return
        try:
            result = booking_core.check_booking(document)
        except booking_core.InvalidInput:
            self.send_error(400, "Documento de reservas invalido")
            return
        self._reply(200, result)


def _port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("El puerto debe ser un entero") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("El puerto debe estar entre 0 y 65535")
    return port


def main(arguments=None):
    parser = argparse.ArgumentParser(
        description="HTTP local de disponibilidad en IPv4 127.0.0.1",
        allow_abbrev=False,
    )
    parser.add_argument("--port", type=_port, default=8000, help="puerto (0–65535)")
    args = parser.parse_args(arguments)
    try:
        with _LocalServer((_HOST, args.port), _Handler) as server:
            # El constructor ya ha enlazado y activado el socket de escucha.
            print(json.dumps({"host": _HOST, "port": server.server_port}), flush=True)
            server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"No se pudo iniciar o mantener el servidor: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Aceptación externa de check_booking.py con solicitudes sintéticas y CLI hija."""

import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
# Se conserva esta disposición al congelar autoridades. Nunca resolver la
# utilidad desde --project, ni importar el candidato en este proceso.
AUTHORITY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AUTHORITY_ROOT))
from process_environment import process_environment


TIMEOUT = 10
RESOURCE = "Sala Norte"
PRIVATE = {".git", "runs", ".codex", ".agents", ".aws", ".venv", ".env"}


def snapshot(directory, *, project=False):
    """Inventariar archivos y metadatos sin seguir enlaces ni leer datos privados."""
    result = {}

    def visit(path):
        info = path.lstat()
        hidden = project and path != directory and (path.name in PRIVATE or path.name.startswith(".env."))
        content = None
        if stat.S_ISREG(info.st_mode) and not hidden:
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            content = os.readlink(path)
        result[path.relative_to(directory).as_posix()] = (info.st_mode, info.st_mtime_ns, content)
        if stat.S_ISDIR(info.st_mode) and not hidden:
            for child in sorted(path.iterdir()):
                visit(child)

    visit(directory)
    return result


def instant(clock):
    return "2026-10-20T" + clock + "Z"


def booking(identifier, start="10:00:00", end="11:00:00", *, resource=RESOURCE):
    return {"id": identifier, "recurso": resource, "inicio": instant(start), "fin": instant(end)}


def document(bookings=(), *, resource=RESOURCE):
    return {"solicitud": {"recurso": resource, "inicio": instant("10:00:00"), "fin": instant("11:00:00")},
            "reservas": copy.deepcopy(list(bookings))}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clave duplicada en la respuesta")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Constante no JSON: " + value)


class AcceptanceTests(unittest.TestCase):
    project = None

    def setUp(self):
        self.script = self.project / "check_booking.py"
        self.assertTrue(self.script.is_file() and not self.script.is_symlink(),
                        "Funcionalidad pendiente: falta check_booking.py como archivo regular; CLI no invocada")
        temporary = tempfile.TemporaryDirectory(prefix="aceptacion-check-booking-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def save(self, data=None, *, raw=None, name="solicitud sintética.json"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else json.dumps(
            document() if data is None else data, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        return name

    @contextmanager
    def query(self, *arguments):
        before_inputs = snapshot(self.root)
        before_project = snapshot(self.project, project=True)
        try:
            with process_environment("evaluation") as environment:
                environment["PATH"] = ""
                try:
                    completed = subprocess.run(
                        [str(Path(sys.executable).resolve()), "-B", str(self.script), *arguments],
                        cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True,
                        timeout=TIMEOUT, shell=False, env=environment)
                except subprocess.TimeoutExpired:
                    self.fail(f"La CLI excedió {TIMEOUT} segundos")
            yield completed
        finally:
            with self.subTest(conservacion="entradas"):
                self.assertEqual(snapshot(self.root), before_inputs, "La CLI alteró las entradas o creó archivos")
            with self.subTest(conservacion="proyecto"):
                self.assertEqual(snapshot(self.project, project=True), before_project,
                                 "La CLI alteró el proyecto o creó cachés")

    def assert_answer(self, arguments, available, conflicts):
        with self.query(*arguments) as completed:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stderr, b"")
            try:
                answer = json.loads(completed.stdout.decode("utf-8"), object_pairs_hook=unique_object,
                                    parse_constant=invalid_constant)
            except (UnicodeError, ValueError, RecursionError) as exc:
                self.fail(f"stdout no contiene un único objeto JSON UTF-8 válido: {exc}")
            self.assertIs(type(answer), dict)
            self.assertEqual(set(answer), {"disponible", "conflictos"})
            self.assertIs(type(answer["disponible"]), bool)
            self.assertIs(type(answer["conflictos"]), list)
            self.assertTrue(all(type(value) is str for value in answer["conflictos"]))
            self.assertIs(answer["disponible"], available)
            self.assertEqual(answer["conflictos"], conflicts)

    def assert_invalid(self, arguments, affected):
        with self.query(*arguments) as completed:
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertEqual(completed.stdout, b"", "Salida parcial ante una entrada inválida")
            try:
                diagnostic = completed.stderr.decode("utf-8")
            except UnicodeError as exc:
                self.fail(f"Diagnóstico no UTF-8: {exc}")
            # Comparar representaciones del nombre conocido, sin decodificar el mensaje.
            names = sorted({affected, repr(affected), ascii(affected), json.dumps(affected)},
                           key=len, reverse=True)
            self.assertTrue(any(name in diagnostic for name in names), "El diagnóstico no localiza el archivo")
            for name in names:
                diagnostic = diagnostic.replace(name, "")
            self.assertTrue(diagnostic.strip(" \t\r\n:'\"[]().-"),
                            "Falta una causa además del nombre del archivo")

    def invalid_document(self, data):
        name = self.save(data)
        self.assert_invalid([name], name)

    def test_01_lista_vacia(self):
        raw = (" \n\t" + json.dumps(document()) + "\r\n").encode()
        name = self.save(raw=raw, name="carpeta con espacios/consulta sin extensión")
        self.assert_answer([name], True, [])

    def test_02_recursos_distintos_y_comparacion_literal(self):
        data = document([booking("otra", resource="Sala Sur"), booking("minusculas", resource="sala norte"),
                         booking("espacios", resource=" Sala Norte ")])
        self.assert_answer([self.save(data)], True, [])

    def test_03_solapamiento_igualdad_y_contencion(self):
        intervals = [("09:30:00", "10:30:00"), ("10:30:00", "11:30:00"),
                     ("10:00:00", "11:00:00"), ("10:15:00", "10:45:00"),
                     ("09:00:00", "12:00:00"), ("10:59:59", "11:00:01")]
        for start, end in intervals:
            with self.subTest(inicio=start, fin=end):
                self.assert_answer([self.save(document([booking("conflicto", start, end)]))], False, ["conflicto"])

    def test_04_adyacentes_ambos_extremos(self):
        data = document([booking("antes", "09:00:00", "10:00:00"), booking("despues", "11:00:00", "12:00:00")])
        self.assert_answer([self.save(data)], True, [])

    def test_05_intervalos_separados(self):
        data = document([booking("antes", "08:00:00", "09:59:59"), booking("despues", "11:00:01", "12:00:00")])
        self.assert_answer([self.save(data)], True, [])

    def test_06_varios_conflictos_conservan_orden(self):
        data = document([booking("z", "10:30:00", "11:30:00"), booking("otro", resource="Sala Sur"),
                         booking("a", "09:00:00", "10:15:00"), booking("adyacente", "11:00:00", "12:00:00"),
                         booking("medio", "10:40:00", "10:50:00")])
        self.assert_answer([self.save(data)], False, ["z", "a", "medio"])

    def test_07_reservas_pueden_solaparse_entre_si(self):
        data = document([booking("una"), booking("dos"), booking("tres", resource="Sala Sur"),
                         booking("cuatro", resource="Sala Sur")])
        self.assert_answer([self.save(data)], False, ["una", "dos"])

    def test_08_unicode_cadenas_literales_y_ids_distintos(self):
        resource = ' Sala É, "norte"\n🪑 '
        ids = [' id, "uno"\r\n🗓 ', "ID", "id"]
        data = document([booking(value, resource=resource) for value in ids] +
                        [booking("recortado", resource=resource.strip()),
                         booking("normalizado", resource=resource.replace("É", "E\u0301"))], resource=resource)
        self.assert_answer([self.save(data)], False, ids)

    def test_09_fechas_validas_bisiestos_y_extremos(self):
        intervals = [("2024-02-29T23:59:59Z", "2024-03-01T00:00:00Z"),
                     ("2000-02-29T00:00:00Z", "2000-03-01T00:00:00Z"),
                     ("1900-02-28T23:59:59Z", "1900-03-01T00:00:00Z"),
                     ("0001-01-01T00:00:00Z", "0001-01-01T00:00:01Z"),
                     ("9999-12-31T23:59:58Z", "9999-12-31T23:59:59Z")]
        for start, end in intervals:
            with self.subTest(inicio=start):
                data = document([booking("mismo")])
                for item in (data["solicitud"], data["reservas"][0]):
                    item.update(inicio=start, fin=end)
                self.assert_answer([self.save(data)], False, ["mismo"])

    def test_10_fechas_invalidas_en_solicitud_y_otro_recurso(self):
        dates = ["2023-02-29T10:00:00Z", "1900-02-29T10:00:00Z", "2026-04-31T10:00:00Z",
                 "0000-01-01T10:00:00Z", "2026-13-01T10:00:00Z", "2026-10-20T24:00:00Z",
                 "2026-10-20T10:60:00Z", "2026-10-20T10:00:60Z", "2026-1-20T10:00:00Z",
                 "2026-10-20T10:00:00+00:00", "2026-10-20T10:00:00.0Z", "2026-10-20T10:00:00",
                 "2026-10-20t10:00:00z", "2026-10-20 10:00:00Z", " 2026-10-20T10:00:00Z",
                 "2026-10-20T10:00:00Z\n", "２０２６-10-20T10:00:00Z"]
        for location in ("solicitud", "reserva"):
            for field in ("inicio", "fin"):
                for value in dates:
                    with self.subTest(objeto=location, campo=field, valor=value):
                        data = document([booking("otro", resource="Sala Sur")])
                        target = data["solicitud"] if location == "solicitud" else data["reservas"][0]
                        target[field] = value
                        self.invalid_document(data)

    def test_11_intervalos_vacios_e_invertidos(self):
        for location in ("solicitud", "reserva"):
            for end in ("10:00:00", "09:00:00"):
                with self.subTest(objeto=location, fin=end):
                    data = document([booking("otro", resource="Sala Sur")])
                    target = data["solicitud"] if location == "solicitud" else data["reservas"][0]
                    target["fin"] = instant(end)
                    self.invalid_document(data)

    def test_12_ids_duplicados_tambien_entre_recursos(self):
        for resource in (RESOURCE, "Sala Sur"):
            with self.subTest(recurso=resource):
                self.invalid_document(document([booking("repetido"), booking("repetido", resource=resource)]))

    def test_13_campos_ausentes_y_adicionales(self):
        for location, keys in (("raiz", ("solicitud", "reservas")),
                               ("solicitud", ("recurso", "inicio", "fin")),
                               ("reserva", ("id", "recurso", "inicio", "fin"))):
            for key in (*keys, "adicional"):
                with self.subTest(objeto=location, campo=key):
                    data = document([booking("otro", resource="Sala Sur")])
                    target = data if location == "raiz" else data["solicitud"] if location == "solicitud" else data["reservas"][0]
                    if key == "adicional":
                        target[key] = "no permitido"
                    else:
                        del target[key]
                    self.invalid_document(data)

    def test_14_tipos_de_contenedores(self):
        for value in (None, True, 0, "objeto", []):
            with self.subTest(raiz=value):
                name = self.save(raw=json.dumps(value).encode())
                self.assert_invalid([name], name)
            with self.subTest(solicitud=value):
                data = document()
                data["solicitud"] = value
                self.invalid_document(data)
            with self.subTest(reserva=value):
                self.invalid_document(document([value]))
        for value in (None, True, 0, "lista", {}):
            with self.subTest(reservas=value):
                data = document()
                data["reservas"] = value
                self.invalid_document(data)

    def test_15_tipos_de_campos_sin_coercion(self):
        for location, fields in (("solicitud", ("recurso", "inicio", "fin")),
                                 ("reserva", ("id", "recurso", "inicio", "fin"))):
            for field in fields:
                for value in (None, True, False, 1, 1.0, [], {}):
                    with self.subTest(objeto=location, campo=field, valor=value):
                        data = document([booking("otro", resource="Sala Sur")])
                        target = data["solicitud"] if location == "solicitud" else data["reservas"][0]
                        target[field] = value
                        self.invalid_document(data)

    def test_16_cadenas_blancas(self):
        for location, field in (("solicitud", "recurso"), ("reserva", "recurso"), ("reserva", "id")):
            for value in ("", " \t\r\n", "\u2003\u00a0"):
                with self.subTest(objeto=location, campo=field, valor=value):
                    data = document([booking("otro", resource="Sala Sur")])
                    target = data["solicitud"] if location == "solicitud" else data["reservas"][0]
                    target[field] = value
                    self.invalid_document(data)

    def test_17_json_invalido_y_codificacion(self):
        valid = json.dumps(document()).encode()
        variants = [b"", b"{", valid[:-1], valid + valid, b"\xff", b"\xef\xbb\xbf" + valid,
                    b"{'solicitud': None}", valid.replace(b'"Sala Norte"', b'"escape\\q"')]
        variants += [valid.replace(b'"Sala Norte"', token) for token in (b"NaN", b"Infinity", b"-Infinity")]
        for raw in variants:
            with self.subTest(entrada=raw):
                name = self.save(raw=raw)
                self.assert_invalid([name], name)

    def test_18_claves_duplicadas_a_toda_profundidad(self):
        for location in ("raiz", "solicitud", "reserva"):
            data = document([booking("id")])
            target = data if location == "raiz" else data["solicitud"] if location == "solicitud" else data["reservas"][0]
            for key in target:
                with self.subTest(objeto=location, clave=key):
                    text = json.dumps(data)
                    original = json.dumps(target)
                    duplicate = original[:-1] + ", " + json.dumps(key) + ": " + json.dumps(target[key]) + "}"
                    name = self.save(raw=text.replace(original, duplicate, 1).encode())
                    self.assert_invalid([name], name)
        raw = json.dumps(document([booking("id")])).replace('"id": "id"', '"id": "id", "\\u0069d": "id"').encode()
        name = self.save(raw=raw)
        self.assert_invalid([name], name)

    def test_19_archivos_ilegibles(self):
        (self.root / "directorio").mkdir()
        for name in ("ausente ñ.json", "directorio"):
            with self.subTest(archivo=name):
                self.assert_invalid([name], name)

    def test_20_argumentos_incorrectos(self):
        name = self.save()
        for arguments in ([], [name, name], ["--desconocida"], ["--he"], ["--hel"], ["--"], ["--project", name]):
            with self.subTest(argumentos=arguments):
                with self.query(*arguments) as completed:
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertEqual(completed.stdout, b"")
                    self.assertTrue(completed.stderr.strip())

    def test_21_ayuda_sin_archivos(self):
        for option in ("-h", "--help"):
            with self.subTest(opcion=option):
                with self.query(option) as completed:
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(completed.stderr, b"")
                    self.assertTrue(completed.stdout.strip())

    def test_22_rutas_con_guion_tras_fin_de_opciones(self):
        for name in ("-solicitud ñ.json", "--help"):
            with self.subTest(archivo=name):
                self.assert_answer(["--", self.save(name=name)], True, [])

    def test_23_contenido_tratado_como_datos(self):
        payload = "__import__('pathlib').Path('NO_EJECUTAR').write_text('centinela')"
        self.assert_answer([self.save(document([booking(payload)]))], False, [payload])
        self.assertFalse((self.root / "NO_EJECUTAR").exists())

    def test_24_validacion_total_sin_salida_parcial(self):
        data = document([booking("conflicto"), booking("otro", resource="Sala Sur")])
        data["reservas"][1]["inicio"] = "2026-02-30T10:00:00Z"
        self.invalid_document(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", type=Path, required=True, help="Directorio del proyecto candidato")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not project.is_dir():
        parser.error("--project debe ser un directorio existente")
    AcceptanceTests.project = project
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

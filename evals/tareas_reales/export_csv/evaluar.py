"""Aceptación externa de export_runs.py: CLI y documentos v1 sintéticos."""

import argparse
from contextlib import contextmanager
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
# Se resuelve desde la autoridad, nunca desde --project ni desde su cwd.
# Al congelar este evaluador se debe conservar esta disposición y su utilidad.
AUTHORITY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AUTHORITY_ROOT))
from process_environment import process_environment


TIMEOUT = 10
HEADER = ["origen", "consulta_estado", "consulta_codigo_salida", "caso",
          "ejecucion_estado", "ejecucion_codigo_salida", "intentos_registrados",
          "max_intentos", "invocaciones_total", "max_invocaciones", "duracion_segundos"]
# Decimal marca duraciones de entradas reales; enteros y null siguen siendo
# cadenas para exigir su representación literal, sin conversiones a float.
BASE_CELLS = ["completada", "0", "caso_sintético", "aprobada", "0", "2", "7", "11", "23", Decimal("12.3456789")]
CONTAINERS = [(), ("consulta",), ("ejecucion",),
              ("ejecucion", "presupuestos"), ("ejecucion", "invocaciones")]
COUNTERS = [("ejecucion", "intentos_registrados"),
            ("ejecucion", "presupuestos", "max_intentos"),
            ("ejecucion", "presupuestos", "max_invocaciones"),
            ("ejecucion", "invocaciones", "desarrollador"),
            ("ejecucion", "invocaciones", "revisor"),
            ("ejecucion", "invocaciones", "total")]
# No leer registros privados, credenciales ni metadatos Git al inventariar
# un checkout de trabajo. Sí inventariar cachés Python y todos los fuentes.
PRIVATE = {".git", "runs", ".codex", ".agents", ".aws", ".venv", ".env"}


def snapshot(directory, *, project=False):
    """Entradas, contenido y metadatos; sin seguir enlaces ni incluir atime."""
    result = {}

    def visit(path):
        name = path.relative_to(directory).as_posix()
        info = path.lstat()
        hidden = project and path != directory and (path.name in PRIVATE or path.name.startswith(".env."))
        content = None
        if stat.S_ISREG(info.st_mode) and not hidden:
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            content = os.readlink(path)
        result[name] = (info.st_mode, info.st_mtime_ns, content)
        if stat.S_ISDIR(info.st_mode) and not hidden:
            for child in sorted(path.iterdir()):
                visit(child)

    visit(directory)
    return result


def document():
    # Los contadores son independientes: el esquema no exige sumar ni inferir.
    return {
        "version_esquema": 1,
        "consulta": {"estado": "completada", "codigo_salida": 0, "incidencias": []},
        "ejecucion": {
            "caso": "caso_sintético", "estado": "aprobada", "codigo_salida": 0,
            "presupuestos": {"max_intentos": 7, "max_invocaciones": 23},
            "intentos_registrados": 2,
            "invocaciones": {"desarrollador": 3, "revisor": 5, "total": 11},
            "duracion_segundos": 12.3456789,
        },
    }


def at(data, path):
    for key in path:
        data = data[key]
    return data


class AcceptanceTests(unittest.TestCase):
    project = None

    def setUp(self):
        self.script = self.project / "export_runs.py"
        # Falta de funcionalidad = fallo de aceptación, no error de argparse
        # ni resultado inventado de un proceso Python que no puede arrancarla.
        self.assertTrue(self.script.is_file() and not self.script.is_symlink(),
                        "Funcionalidad pendiente: falta export_runs.py como archivo regular; CLI no invocada")
        temporary = tempfile.TemporaryDirectory(prefix="aceptacion-export-csv-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def save(self, name, data=None, *, raw=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else
                         json.dumps(document() if data is None else data,
                                    ensure_ascii=False, allow_nan=False).encode("utf-8"))
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
                        timeout=TIMEOUT, shell=False, env=environment,
                    )
                except subprocess.TimeoutExpired:
                    self.fail(f"La CLI excedió {TIMEOUT} segundos")
            # Bytes: text=True normalizaría CRLF y escondería defectos del CSV.
            yield completed
        finally:
            # Ambas comprobaciones se ejecutan incluso si falla una aserción,
            # expira la CLI o también se detecta una alteración del otro árbol.
            with self.subTest(conservacion="entradas"):
                self.assertEqual(snapshot(self.root), before_inputs, "La CLI alteró las entradas o su árbol")
            with self.subTest(conservacion="proyecto"):
                self.assertEqual(snapshot(self.project, project=True), before_project,
                                 "La CLI alteró el proyecto o creó archivos/cachés")

    def csv_rows(self, completed):
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertFalse(completed.stdout.startswith(b"\xef\xbb\xbf"), "CSV con BOM")
        try:
            text = completed.stdout.decode("utf-8")
            rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
        except (UnicodeError, csv.Error) as exc:
            self.fail(f"stdout no es CSV UTF-8 válido: {exc}")
        self.assertTrue(text.endswith("\n"), "Falta el LF final")
        quoted = False
        for char in text:
            if char == '"':
                quoted = not quoted
            if char == "\r" and not quoted:
                self.fail("Terminador de registro distinto de LF")
        self.assertTrue(rows, "Falta la cabecera")
        self.assertEqual(rows[0], HEADER)
        self.assertTrue(all(len(row) == len(HEADER) for row in rows), "Número de columnas incorrecto")
        return rows[1:]

    def assert_export(self, arguments, rows):
        with self.query(*arguments) as completed:
            actual = self.csv_rows(completed)
            self.assertEqual(len(actual), len(rows))
            for received, expected in zip(actual, rows):
                self.assertEqual(received[:-1], expected[:-1])
                if isinstance(expected[-1], Decimal):
                    # Decimal admite espacios/guiones bajos: no son notación CSV
                    # numérica del contrato. La celda vacía tampoco es cero.
                    self.assertIsNotNone(re.fullmatch(
                        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", received[-1]))
                    try:
                        duration = Decimal(received[-1])
                    except InvalidOperation:
                        self.fail("Duración CSV no numérica")
                    self.assertTrue(duration.is_finite())
                    self.assertEqual(duration, expected[-1])
                else:
                    self.assertEqual(received[-1], expected[-1])

    def assert_invalid(self, arguments, affected):
        with self.query(*arguments) as completed:
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertEqual(completed.stdout, b"", "CSV parcial ante una entrada inválida")
            diagnostic = completed.stderr.decode("utf-8")
            self.assertIn(affected, diagnostic, "El diagnóstico no localiza el archivo")
            self.assertNotIn("Traceback", diagnostic)

    def test_01_columnas_y_correspondencia(self):
        name = self.save("consulta.json")
        self.assert_export([name], [[name, *BASE_CELLS]])

    def test_02_orden_y_duplicados(self):
        first = self.save("primera.json")
        second_doc = document()
        second_doc["ejecucion"].update(caso="segundo", estado="en_curso", codigo_salida=None)
        second = self.save("datos/segunda consulta ñ.json", second_doc)
        other = [second, "completada", "0", "segundo", "en_curso", "", "2", "7", "11", "23", BASE_CELLS[-1]]
        self.assert_export([second, first, second], [other, [first, *BASE_CELLS], other])

    def test_03_null_frente_a_ceros(self):
        unknown = document()
        unknown["consulta"] = {"estado": "incompleta", "codigo_salida": 1, "incidencias": ["Sin evidencia sintética"]}
        unknown["ejecucion"] = {
            "caso": None, "estado": None, "codigo_salida": None,
            "presupuestos": {"max_intentos": None, "max_invocaciones": None},
            "intentos_registrados": None,
            "invocaciones": {"desarrollador": None, "revisor": None, "total": None},
            "duracion_segundos": None,
        }
        zero = document()
        for path in [*COUNTERS, ("ejecucion", "codigo_salida"), ("ejecucion", "duracion_segundos")]:
            at(zero, path[:-1])[path[-1]] = 0
        names = [self.save("desconocida.json", unknown), self.save("ceros.json", zero)]
        self.assert_export(names, [[names[0], "incompleta", "1", *([""] * 8)],
                                   [names[1], "completada", "0", "caso_sintético", "aprobada", "0", "0", "0", "0", "0", "0"]])

    def test_04_codigos_independientes_y_sin_inferencias(self):
        failed = document()
        failed["ejecucion"].update(estado="fallo_agente", codigo_salida=3)
        partial = document()
        partial["consulta"] = {"estado": "incompleta", "codigo_salida": 1, "incidencias": ["Informe ausente"]}
        partial["ejecucion"].update(estado="interrumpida", codigo_salida=-9)
        names = [self.save("fallida.json", failed), self.save("parcial.json", partial)]
        self.assert_export(names, [
            [names[0], "completada", "0", "caso_sintético", "fallo_agente", "3", "2", "7", "11", "23", BASE_CELLS[-1]],
            [names[1], "incompleta", "1", "caso_sintético", "interrumpida", "-9", "2", "7", "11", "23", BASE_CELLS[-1]],
        ])

    def test_05_enteros_sin_limites_ni_conversion_a_float(self):
        for token in ("9007199254740993", "1" + "0" * 309, "1" + "0" * 5000):
            with self.subTest(digitos=len(token)):
                data = document()
                for path in [*COUNTERS, ("ejecucion", "codigo_salida"), ("ejecucion", "duracion_segundos")]:
                    at(data, path[:-1])[path[-1]] = "NUMERO_SINTETICO"
                raw = json.dumps(data).replace('"NUMERO_SINTETICO"', token).encode()
                name = self.save("grande.json", raw=raw)
                self.assert_export([name], [[name, "completada", "0", "caso_sintético", "aprobada", *([token] * 6)]])

    def test_06_duracion_sin_redondeo_ni_limite_float(self):
        for token in ("0.12345678901234567890123456789", "1e-200", "1e400", "-0.0"):
            with self.subTest(numero=token):
                data = document()
                data["ejecucion"]["duracion_segundos"] = "NUMERO_SINTETICO"
                name = self.save("precision.json", raw=json.dumps(data).replace('"NUMERO_SINTETICO"', token).encode())
                self.assert_export([name], [[name, *BASE_CELLS[:-1], Decimal(token)]])

    def test_07_escape_csv_y_utf8(self):
        data = document()
        data["ejecucion"].update(caso='  caso, "ñ"\r\nsiguiente  ', estado='otro, "estado"\nlínea')
        name = self.save('./datos/área, "B"\nconsulta.json', data)
        self.assert_export([name], [[name, "completada", "0", data["ejecucion"]["caso"],
                                    data["ejecucion"]["estado"], "0", "2", "7", "11", "23", BASE_CELLS[-1]]])

    def test_08_origen_literal_y_sin_extension_obligatoria(self):
        self.save("consulta.datos")
        (self.root / "subdir").mkdir()
        names = ["./consulta.datos", "subdir/../consulta.datos", str(self.root / "consulta.datos")]
        self.assert_export(names, [[name, *BASE_CELLS] for name in names])

    def test_09_contenido_no_ejecutable(self):
        marker = self.root / "EJECUCION_NO_PERMITIDA"
        source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ejecutado')\n"
        data = document()
        data["ejecucion"]["caso"] = source
        name = self.save("texto.json", data)
        self.assert_export([name], [[name, "completada", "0", source, *BASE_CELLS[3:]]])
        executable = self.save("no_ejecutar.py", raw=source.encode())
        self.assert_invalid([executable], executable)
        self.assertFalse(marker.exists())

    def test_10_json_invalido_y_claves_duplicadas(self):
        valid = json.dumps(document()).encode()
        invalid = [b"", b"null", b"[]", b"true", b"1", b"{}{}", valid[:-1], b"\xff",
                   valid.replace(b'"version_esquema": 1', b'"version_esquema": 1, "version_esquema": 1'),
                   valid.replace(b'"total": 11', b'"total": 11, "total": 11'),
                   valid.replace(b'"desarrollador": 3', b'"desarrollador": 3, "desarrollador": 3')]
        invalid += [valid.replace(b"12.3456789", token) for token in (b"NaN", b"Infinity", b"-Infinity")]
        for index, raw in enumerate(invalid):
            with self.subTest(variante=index):
                name = self.save("invalida.json", raw=raw)
                self.assert_invalid([name], name)

    def test_11_estructura_completa_sin_claves_extra(self):
        for path in CONTAINERS:
            variants = [None, [], "objeto", 0]
            original = at(document(), path)
            variants.append({**original, "extra": None})
            variants.extend({key: value for key, value in original.items() if key != missing} for missing in original)
            for index, value in enumerate(variants):
                with self.subTest(objeto=".".join(path) or "raíz", variante=index):
                    data = document()
                    if path:
                        at(data, path[:-1])[path[-1]] = value
                    else:
                        data = value
                    # raw evita que save(data=None) cree el documento de control.
                    name = self.save("estructura.json", raw=json.dumps(data).encode())
                    self.assert_invalid([name], name)

    def test_12_tipos_y_valores_incluidos_campos_no_exportados(self):
        variants = [
            (("version_esquema",), [0, 2, -1, True, 1.0, "1", None]),
            (("consulta", "estado"), ["", "otra", None, True, 0, []]),
            (("consulta", "codigo_salida"), [True, False, 0.0, "0", None, -1, 2]),
            (("consulta", "incidencias"), [None, {}, "", [0], [None], [True], [""], [" \t"]]),
            (("ejecucion", "caso"), ["", " \t", True, 1, [], {}]),
            (("ejecucion", "estado"), ["", " \t", False, 1, [], {}]),
            (("ejecucion", "codigo_salida"), [True, False, 1.0, "0", [], {}]),
            (("ejecucion", "duracion_segundos"), [True, False, -1, -0.5, "1", [], {}]),
        ]
        variants += [(path, [True, False, -1, 1.0, "0", [], {}]) for path in COUNTERS]
        for path, values in variants:
            for value in values:
                with self.subTest(campo=".".join(path), valor=value):
                    data = document()
                    if path == ("consulta", "incidencias"):
                        data["consulta"].update(estado="incompleta", codigo_salida=1)
                    at(data, path[:-1])[path[-1]] = value
                    name = self.save("tipo.json", data)
                    self.assert_invalid([name], name)
        for path in [("version_esquema",), ("consulta", "codigo_salida"), *COUNTERS,
                     ("ejecucion", "codigo_salida")]:
            with self.subTest(campo=".".join(path), valor="1e0"):
                data = document()
                at(data, path[:-1])[path[-1]] = "NUMERO_SINTETICO"
                name = self.save("exponente.json", raw=json.dumps(data).replace('"NUMERO_SINTETICO"', "1e0").encode())
                self.assert_invalid([name], name)

    def test_13_coherencia_de_consulta(self):
        for state in ("completada", "incompleta"):
            for code in (0, 1):
                for issues in ([], ["Incidencia sintética"]):
                    if (state, code, bool(issues)) in (("completada", 0, False), ("incompleta", 1, True)):
                        continue
                    with self.subTest(estado=state, codigo=code, incidencias=issues):
                        data = document()
                        data["consulta"] = {"estado": state, "codigo_salida": code, "incidencias": issues}
                        name = self.save("coherencia.json", data)
                        self.assert_invalid([name], name)

    def test_14_entradas_ilegibles_y_ausencia_de_csv_parcial(self):
        good = self.save("valida.json")
        bad = self.save("rota.json", raw=b"{")
        wrong_version = self.save("version.json", {**document(), "version_esquema": 2})
        directory = "directorio"
        (self.root / directory).mkdir()
        for affected in ("ausente.json", directory, bad, wrong_version):
            for arguments in ([affected], [good, affected], [good, good, affected, good], [affected, good]):
                with self.subTest(argumentos=arguments):
                    self.assert_invalid(arguments, affected)

    def test_15_argumentos_incorrectos(self):
        name = self.save("valida.json")
        for arguments in ([], ["--desconocido"], [name, "--formato", "csv"],
                          ["--run", name], ["--format", "json"], ["--he"], ["--"]):
            with self.subTest(argumentos=arguments):
                with self.query(*arguments) as completed:
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, b"")
                    self.assertTrue(completed.stderr.strip())
                    self.assertNotIn(b"Traceback", completed.stderr)

    def test_16_archivo_con_guion_tras_fin_de_opciones(self):
        name = self.save("-consulta.json")
        self.assert_export(["--", name], [[name, *BASE_CELLS]])

    def test_17_ayuda_sin_archivos(self):
        for option in ("--help", "-h"):
            with self.subTest(opcion=option):
                with self.query(option) as completed:
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(completed.stderr, b"")
                    self.assertTrue(completed.stdout.strip())
                    self.assertNotEqual(completed.stdout.splitlines()[0], ",".join(HEADER).encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", type=Path, required=True, help="Directorio del proyecto candidato")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not project.is_dir():
        parser.error("--project debe ser un directorio existente")
    AcceptanceTests.project = project
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

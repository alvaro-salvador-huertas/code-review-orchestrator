"""Aceptación externa de inspect_run.py: solo CLI y registros sintéticos."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


def snapshot(directory):
    """Comparar contenido, entradas y metadatos; atime cambia al leer y se omite."""
    result = {}
    for path in [directory, *sorted(directory.rglob("*"))]:
        info = path.lstat()
        content = (hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode)
                   else os.readlink(path) if stat.S_ISLNK(info.st_mode) else None)
        result[path.relative_to(directory).as_posix()] = (info.st_mode, info.st_mtime_ns, content)
    return result


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Clave duplicada: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"Constante no JSON: {value}")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


def unknown_execution():
    return {
        "caso": None, "estado": None, "codigo_salida": None,
        "presupuestos": {"max_intentos": None, "max_invocaciones": None},
        "intentos_registrados": None,
        "invocaciones": {"desarrollador": None, "revisor": None, "total": None},
        "duracion_segundos": None,
    }


class AcceptanceTests(unittest.TestCase):
    project = None

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aceptacion-inspect-json-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.general = self.root / "registro sintético"
        self.general.mkdir()
        for name in ("home", "tmp"):
            (self.root / name).mkdir()
        self.repair_dir = self.general / "etapas/reparacion"
        self.review_dir = self.general / "etapas/revision"
        # Estos archivos son datos de prueba: el evaluador nunca los ejecuta.
        # Una ejecución accidental dejaría una marca detectable en el inventario.
        sentinel = ("from pathlib import Path\n"
                    f"Path({str(self.root / 'EJECUCION_NO_PERMITIDA')!r}).write_text('ejecutado')\n"
                    "raise RuntimeError('NO EJECUTAR MATERIALES DEL REGISTRO')\n")
        reference = sentinel + ("import unittest\nclass Historicas(unittest.TestCase):\n"
                                "    def test_a(self): pass\n    def test_b(self): pass\n")
        self.save(self.repair_dir / "referencia/test_solution.py", reference)
        for name in ("candidato.py", "workspace/solution.py", "agente/agente.py"):
            self.save(self.repair_dir / name, sentinel)
        self.save(self.repair_dir / "agente/entrada.txt", "PROMPT_SINTETICO_NO_EXPORTAR")
        self.save(self.repair_dir / "agente/eventos.jsonl", "EVENTOS_SINTETICOS_NO_EXPORTAR")
        self.repair = {
            "registro": "etapas/reparacion", "estado": "supera_las_pruebas_disponibles",
            "codigo_salida": 0,
            "agente": {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1},
            "pruebas_iniciales": {"estado": "finalizada", "codigo_salida": 0},
            "pruebas_posteriores": {"estado": "finalizada", "codigo_salida": 0},
        }
        report = ("test_a (test_solution.Historicas.test_a) ... ok\n"
                  "test_b (test_solution.Historicas.test_b) ... ok\n\n"
                  + "-" * 70 + "\nRan 2 tests in 0.001s\n\nOK\n")
        for phase, key in (("inicial", "pruebas_iniciales"), ("posterior", "pruebas_posteriores")):
            self.save(self.repair_dir / phase / "resultado.json", self.repair[key])
            self.save(self.repair_dir / phase / "stderr.txt", report)
        self.review = {
            "registro": "etapas/revision", "decision_controlador": "aprobada", "codigo_salida": 0,
            "revisor": {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1},
            "dictamen_modelo": {"decision": "aprobar", "hallazgos": []},
        }
        self.attempt = {"numero": 1, "reparacion": self.repair, "revision": self.review,
                        "transiciones": [{"etapa": "desarrollo", "accion": "revisar", "motivo": "pruebas_superadas"},
                                         {"etapa": "revision", "accion": "aprobar", "motivo": "aprobada"}]}
        self.record = {
            "caso": "case_01", "estado": "aprobada", "codigo_salida": 0,
            "max_intentos": 2, "max_invocaciones": 4, "intentos": [self.attempt],
            "invocaciones": {"desarrollador": 1, "revisor": 1, "total": 2},
            "duracion_segundos": 12.3456,
        }
        self.expected = {
            "caso": "case_01", "estado": "aprobada", "codigo_salida": 0,
            "presupuestos": {"max_intentos": 2, "max_invocaciones": 4},
            "intentos_registrados": 1,
            "invocaciones": {"desarrollador": 1, "revisor": 1, "total": 2},
            "duracion_segundos": 12.3456,
        }
        self.write_records()

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) + "\n"
        path.write_text(text, encoding="utf-8")

    def write_records(self):
        self.save(self.general / "resultado.json", self.record)
        self.save(self.repair_dir / "resultado.json", self.repair)
        self.save(self.review_dir / "resultado.json", self.review)

    def call(self, *arguments):
        before = snapshot(self.root)
        try:
            completed = subprocess.run(
                [sys.executable, "-B", str(self.project / "inspect_run.py"), *map(str, arguments)],
                cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, encoding="utf-8", timeout=10, shell=False,
                # No heredar credenciales, PYTHONPATH ni configuración de la CLI personal.
                env={"PATH": "", "HOME": str(self.root / "home"), "TMPDIR": str(self.root / "tmp"),
                     "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "LC_ALL": "C.UTF-8"},
            )
        finally:
            self.assertEqual(snapshot(self.root), before, "La consulta modificó los registros sintéticos")
        for marker in ("PROMPT_SINTETICO_NO_EXPORTAR", "EVENTOS_SINTETICOS_NO_EXPORTAR"):
            self.assertNotIn(marker, completed.stdout + completed.stderr)
        return completed

    def query(self, *options):
        # Ruta relativa, con espacios y Unicode, desde fuera del proyecto evaluado.
        return self.call("--run", self.general.name, *options)

    def assert_json(self, expected, code=0):
        completed = self.query("--format", "json")
        self.assertEqual(completed.returncode, code, completed.stderr)
        self.assertEqual(completed.stderr, "")
        try:
            data = strict_json(completed.stdout)
        except ValueError as exc:
            self.fail(f"stdout no es exclusivamente un objeto JSON válido: {exc}")
        self.assertIs(type(data), dict)
        self.assertEqual(set(data), {"version_esquema", "consulta", "ejecucion"})
        self.assertIs(type(data["version_esquema"]), int)
        self.assertEqual(data["version_esquema"], 1)
        query = data["consulta"]
        self.assertIs(type(query), dict)
        self.assertEqual(set(query), {"estado", "codigo_salida", "incidencias"})
        self.assertIs(type(query["codigo_salida"]), int)
        self.assertEqual(query["codigo_salida"], code)
        self.assertEqual(query["estado"], "incompleta" if code else "completada")
        self.assertIs(type(query["incidencias"]), list)
        self.assertEqual(bool(query["incidencias"]), bool(code))
        self.assertTrue(all(type(issue) is str and issue.strip() for issue in query["incidencias"]))
        execution = data["ejecucion"]
        self.assertIs(type(execution), dict)
        self.assertEqual(execution, expected)
        for name in ("caso", "estado"):
            value = execution[name]
            self.assertTrue(value is None or type(value) is str and bool(value.strip()))
        for name in ("presupuestos", "invocaciones"):
            self.assertIs(type(execution[name]), dict)
        numbers = [execution["intentos_registrados"], *execution["presupuestos"].values(),
                   *execution["invocaciones"].values()]
        self.assertTrue(all(value is None or type(value) is int and value >= 0 for value in numbers))
        self.assertTrue(execution["codigo_salida"] is None or type(execution["codigo_salida"]) is int)
        duration = execution["duracion_segundos"]
        self.assertTrue(duration is None or type(duration) in (int, float)
                        and math.isfinite(duration) and duration >= 0)
        return query["incidencias"]

    def test_01_texto_por_defecto(self):
        completed = self.query()
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        for text in ("Caso: case_01", "Estado del controlador: aprobada; código de la ejecución: 0",
                     "Intentos registrados: 1/2", "desarrollador 1, revisor 1, total 2/4",
                     "Duración: 12.346 s", "Dictamen registrado del modelo: aprobar",
                     "total 2, correctas 2, fallos 0, errores 0, omisiones 0",
                     "Consulta: completada (código 0)"):
            self.assertIn(text, completed.stdout)

    def test_02_texto_explicito_equivale_al_predeterminado(self):
        for incomplete in (False, True):
            with self.subTest(incompleta=incomplete):
                if incomplete:
                    (self.repair_dir / "posterior/stderr.txt").unlink()
                default = self.query()
                explicit = self.query("--format", "text")
                self.assertEqual(default.returncode, int(incomplete))
                self.assertEqual((explicit.returncode, explicit.stdout, explicit.stderr),
                                 (default.returncode, default.stdout, default.stderr))

    def test_03_json_consulta_completa_de_ambos_casos(self):
        for case in ("case_01", "case_02"):
            with self.subTest(caso=case):
                self.record["caso"] = self.expected["caso"] = case
                self.write_records()
                self.assert_json(self.expected)

    def test_04_ejecucion_fallida_pero_consulta_completa(self):
        self.record.update(estado="fallo_agente", codigo_salida=3)
        self.record["invocaciones"] = {"desarrollador": 1, "revisor": 0, "total": 1}
        self.repair.update(estado="fallo_agente", codigo_salida=3)
        self.repair["agente"].update(estado="error_inicio", codigo_salida=9, error="fallo sintético")
        self.repair["pruebas_posteriores"] = {"estado": "no_ejecutadas", "codigo_salida": None}
        self.attempt.update(revision=None, transiciones=[{"etapa": "desarrollo", "accion": "detener", "motivo": "fallo_agente"}])
        self.expected.update(estado="fallo_agente", codigo_salida=3, invocaciones=self.record["invocaciones"])
        self.write_records()
        self.assert_json(self.expected)

    def test_05_ausencias_opcionales_y_ceros_explicitos(self):
        self.record.update(estado="en_curso", codigo_salida=None, intentos=[],
                           invocaciones={"desarrollador": 0, "revisor": 0, "total": 0})
        self.expected.update(estado="en_curso", codigo_salida=None, intentos_registrados=0,
                             invocaciones=self.record["invocaciones"], duracion_segundos=None)
        for absent in (True, False):
            with self.subTest(duracion_ausente=absent):
                if absent:
                    del self.record["duracion_segundos"]
                else:
                    self.record["duracion_segundos"] = None
                self.write_records()
                self.assert_json(self.expected)

    def test_06_datos_necesarios_ausentes_conservan_los_conocidos(self):
        for name in ("caso", "codigo_salida", "intentos", "max_intentos", "duracion_segundos"):
            del self.record[name]
        del self.record["invocaciones"]["desarrollador"]
        self.expected.update(caso=None, codigo_salida=None, intentos_registrados=None, duracion_segundos=None)
        self.expected["presupuestos"]["max_intentos"] = None
        self.expected["invocaciones"]["desarrollador"] = None
        self.write_records()
        issues = self.assert_json(self.expected, 1)
        for field in ("caso", "codigo_salida", "intentos", "max_intentos", "desarrollador"):
            self.assertTrue(any(field in issue for issue in issues), field)

    def test_07_objeto_vacio_no_inventa_datos(self):
        self.save(self.general / "resultado.json", {})
        self.assert_json(unknown_execution(), 1)

    def test_08_registro_ausente(self):
        (self.general / "resultado.json").unlink()
        issues = self.assert_json(unknown_execution(), 1)
        self.assertTrue(any("resultado.json" in issue for issue in issues))

    def test_09_json_de_entrada_invalido(self):
        for raw in (b"{", b"[]", b"null", b'{"caso":1,"caso":2}',
                    b'{"duracion_segundos":NaN}', b"\xff"):
            with self.subTest(entrada=raw):
                (self.general / "resultado.json").write_bytes(raw)
                issues = self.assert_json(unknown_execution(), 1)
                self.assertTrue(any("resultado.json" in issue for issue in issues))

    def test_10_tipos_invalidos_no_se_convierten(self):
        mutations = (("max_intentos", True, "presupuestos", "max_intentos"),
                     ("max_invocaciones", -1, "presupuestos", "max_invocaciones"),
                     ("codigo_salida", "0", None, "codigo_salida"),
                     ("duracion_segundos", True, None, "duracion_segundos"),
                     ("duracion_segundos", -0.5, None, "duracion_segundos"),
                     ("intentos", {}, None, "intentos_registrados"))
        for source, value, group, target in mutations:
            with self.subTest(campo=source, valor=value):
                original = self.record[source]
                self.record[source] = value
                expected = json.loads(json.dumps(self.expected))
                (expected[group] if group else expected)[target] = None
                self.write_records()
                try:
                    issues = self.assert_json(expected, 1)
                    self.assertTrue(any(source in issue for issue in issues))
                finally:
                    self.record[source] = original

    def test_11_informe_ausente_no_se_ignora_en_json(self):
        (self.repair_dir / "posterior/stderr.txt").unlink()
        issues = self.assert_json(self.expected, 1)
        self.assertTrue(any("stderr.txt" in issue for issue in issues))

    def test_12_resumen_enlazado_invalido_o_discrepante(self):
        for raw in ("{", '{"decision_controlador":"fallo_revisor"}'):
            with self.subTest(resumen=raw):
                self.save(self.review_dir / "resultado.json", raw)
                issues = self.assert_json(self.expected, 1)
                self.assertTrue(any("resultado.json" in issue for issue in issues))

    def test_13_intento_interrumpido_conserva_datos(self):
        self.record.update(estado="en_curso", codigo_salida=None, duracion_segundos=None,
                           intentos=[{"numero": 1, "reparacion": None, "revision": None, "transiciones": []}])
        self.expected.update(estado="en_curso", codigo_salida=None, duracion_segundos=None)
        self.write_records()
        self.assert_json(self.expected, 1)

    def test_14_argumentos_invalidos(self):
        for args in ((), ("--run",), ("--format", "json"),
                     ("--run", self.general.name, "--format"),
                     ("--run", self.general.name, "--format", "yaml"),
                     ("--run", self.general.name, "--format", "JSON"),
                     ("--run", self.general.name, "--format", "json", "--desconocido")):
            with self.subTest(argumentos=args):
                completed = self.call(*args)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertTrue(completed.stderr.strip())
                self.assertNotIn("Traceback", completed.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="Raíz del proyecto candidato")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not (project / "inspect_run.py").is_file():
        parser.error("--project debe contener inspect_run.py")
    AcceptanceTests.project = project
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

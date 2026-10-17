"""Comprobaciones CLI de resúmenes profundos, separadas de aceptación y CI.

Uso: python3 -B evals/tareas_reales/inspect_json/comprobar_anidamiento.py
     --project <copia candidata> --output <directorio nuevo>

No importa el inspector ni cambia el límite de recursión. Reutiliza el fixture
sintético completo y el lanzador con política evaluation. Las copias y el
entorno reducido no proporcionan aislamiento de seguridad.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.tareas_reales.inspect_json import evaluar
from evals.tareas_reales.inspect_json.comprobar_hallazgos import sha256
from repair_case import run_process, write_json


def write_nested_records(fixture, general_leaf, linked_leaf, depth=600):
    """Insertar JSON por texto: sin deepcopy ni serializar estructuras profundas.

    El lector debe admitir cada entrada antes de invocar el candidato. La
    comprobación de profundidad también es iterativa; no compara árboles enteros.
    """
    marker = "MARCADOR_ANIDAMIENTO_SINTETICO"
    fixture.review["metadatos"] = marker
    fixture.write_records()
    inputs = ((fixture.general / "resultado.json", general_leaf, True),
              (fixture.review_dir / "resultado.json", linked_leaf, False))
    verified = []
    for path, leaf, general in inputs:
        text = path.read_text(encoding="utf-8")
        quoted = json.dumps(marker)
        if text.count(quoted) != 1:
            raise ValueError("Se requiere un único marcador por resumen")
        text = text.replace(quoted, "[" * depth + leaf + "]" * depth)
        parsed = evaluar.strict_json(text)
        value = (parsed["intentos"][0]["revision"] if general else parsed)["metadatos"]
        for _ in range(depth):
            if type(value) is not list or len(value) != 1:
                raise ValueError("Anidamiento sintético incorrecto")
            value = value[0]
        expected = evaluar.strict_json(leaf)
        if type(value) is not type(expected) or value != expected:
            raise ValueError("Hoja sintética incorrecta")
        path.write_text(text, encoding="utf-8")
        verified.append({"archivo": path.relative_to(fixture.general).as_posix(),
                         "profundidad": depth, "hoja_json": leaf,
                         "sha256": sha256(path), "lectura_json_verificada": True})
    return verified


class AnidamientoTests(unittest.TestCase):
    project = None
    output = None

    def setUp(self):
        self.fixture = evaluar.AcceptanceTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.logs = self.output / self._testMethodName
        self.logs.mkdir()
        self.program = self.fixture.root / "programa"
        self.program.mkdir()
        for name in ("inspect_run.py", "case_evidence.py"):
            shutil.copyfile(self.project / name, self.program / name)
            self.assertEqual(sha256(self.project / name), sha256(self.program / name))
        write_json(self.logs / "programa.json", {
            name: sha256(self.program / name) for name in ("inspect_run.py", "case_evidence.py")})

    def compare(self, left, right, code, name="consulta"):
        log = self.logs / name
        log.mkdir()
        verified = write_nested_records(self.fixture, left, right)
        write_json(log / "preparacion.json", verified)
        shutil.copytree(self.fixture.general, log / "entrada")
        for path in self.fixture.general.rglob("*"):
            if path.is_file():
                self.assertEqual(sha256(path), sha256(log / "entrada" / path.relative_to(self.fixture.general)))
        before = evaluar.snapshot(self.fixture.root)
        try:
            process = run_process(
                [sys.executable, "-B", str(self.program / "inspect_run.py"),
                 "--run", self.fixture.general.name, "--format", "json"],
                self.fixture.root, log, 10, env_policy="evaluation")
        finally:
            after = evaluar.snapshot(self.fixture.root)
            write_json(log / "integridad.json", {
                "antes": before, "despues": after, "intactos": before == after})
            self.assertEqual(after, before)
        stdout = (log / "stdout.txt").read_text(encoding="utf-8")
        stderr = (log / "stderr.txt").read_text(encoding="utf-8")
        self.assertEqual(process["estado"], "finalizada")
        self.assertEqual(process["codigo_salida"], code, stderr)
        self.assertEqual(stderr, "")
        data = evaluar.strict_json(stdout)
        self.assertEqual(set(data), {"version_esquema", "consulta", "ejecucion"})
        self.assertIs(type(data["version_esquema"]), int)
        self.assertEqual(data["version_esquema"], 1)
        self.assertEqual(data["ejecucion"], self.fixture.expected)
        query = data["consulta"]
        self.assertEqual(set(query), {"estado", "codigo_salida", "incidencias"})
        self.assertIs(type(query["codigo_salida"]), int)
        self.assertEqual(query["codigo_salida"], code)
        self.assertEqual(query["estado"], "incompleta" if code else "completada")
        self.assertIs(type(query["incidencias"]), list)
        self.assertEqual(bool(query["incidencias"]), bool(code))
        self.assertTrue(all(type(issue) is str and issue.strip() for issue in query["incidencias"]))
        if code:
            self.assertIn("etapas/revision/resultado.json", "\n".join(query["incidencias"]))

    def test_estructuras_profundas_iguales(self):
        self.compare("0", "0", 0)

    def test_booleano_profundo_distinto_de_numero(self):
        self.compare("0", "false", 1)

    def test_numeros_profundos_distintos(self):
        self.compare("1", "2", 1)

    def test_entero_y_float_profundos_equivalentes(self):
        self.compare("1", "1.0", 0)

    def test_diccionarios_sin_dependencia_del_orden(self):
        self.compare('{"a": [1, false], "b": {"c": 2}}',
                     '{"b": {"c": 2.0}, "a": [1.0, false]}', 0)

    def test_claves_de_diccionario_distintas(self):
        self.compare('{"a": 1}', '{"b": 1}', 1)

    def test_listas_respetan_orden_y_longitud(self):
        for name, right in (("orden", "[2, 1]"), ("longitud", "[1, 2, 3]")):
            with self.subTest(caso=name):
                self.compare("[1, 2]", right, 1, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("consultas"))
    args = parser.parse_args(argv)
    project, output = args.project.resolve(), args.output.resolve()
    if not all((project / name).is_file() for name in ("inspect_run.py", "case_evidence.py")):
        parser.error("--project debe contener inspect_run.py y case_evidence.py")
    if output.exists():
        parser.error("--output debe ser nuevo; no se sobrescriben registros")
    output.mkdir(parents=True)
    AnidamientoTests.project, AnidamientoTests.output = project, output
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AnidamientoTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

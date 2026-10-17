"""Contraste contractual de dos hallazgos; separado de aceptación y CI.

Uso: python3 -B evals/tareas_reales/inspect_json/comprobar_hallazgos.py
     --project <copia candidata> --output <directorio nuevo>

Devuelve 0 si cumple, 1 ante fallos y 2 ante argumentos inválidos. No importa
el inspector. Reutiliza solo la construcción de datos del evaluador existente;
sus 14 pruebas no se ejecutan. Las salidas se conservan incluso ante aserciones
fallidas. Las copias y el entorno mínimo no son aislamiento de seguridad.
"""

import argparse
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evals.tareas_reales.inspect_json import evaluar
from repair_case import run_process, write_json


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HallazgosTests(unittest.TestCase):
    project = None
    output = None

    def setUp(self):
        # Composición, no herencia: no descubrir ni ejecutar la aceptación.
        self.fixture = evaluar.AcceptanceTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.logs = self.output / self._testMethodName
        self.logs.mkdir()
        self.program = self.fixture.root / "programa"
        self.program.mkdir()
        for name in ("inspect_run.py", "case_evidence.py"):
            source = self.project / name
            shutil.copyfile(source, self.program / name)
            self.assertEqual(sha256(source), sha256(self.program / name))
        write_json(self.logs / "programa.json", {
            name: sha256(self.program / name) for name in ("inspect_run.py", "case_evidence.py")})

    def query(self, name):
        log = self.logs / name
        log.mkdir()
        # Conservar toda la entrada, sin pasar al inspector rutas de runs/.
        shutil.copytree(self.fixture.general, log / "entrada")
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
            self.assertEqual(after, before, "El inspector modificó el árbol temporal")
        stdout = (log / "stdout.txt").read_text(encoding="utf-8")
        stderr = (log / "stderr.txt").read_text(encoding="utf-8")
        self.assertEqual(process["estado"], "finalizada")
        self.assertEqual(stderr, "")
        for marker in ("PROMPT_SINTETICO_NO_EXPORTAR", "EVENTOS_SINTETICOS_NO_EXPORTAR"):
            self.assertNotIn(marker, stdout + stderr)
        data = evaluar.strict_json(stdout)
        self.assertIs(type(data), dict)
        self.assertEqual(set(data), {"version_esquema", "consulta", "ejecucion"})
        self.assertIs(type(data["version_esquema"]), int)
        self.assertEqual(data["version_esquema"], 1)
        query = data["consulta"]
        self.assertEqual(set(query), {"estado", "codigo_salida", "incidencias"})
        self.assertIs(type(query["codigo_salida"]), int)
        self.assertEqual(query["codigo_salida"], process["codigo_salida"])
        self.assertIs(type(query["incidencias"]), list)
        self.assertTrue(all(type(issue) is str and issue.strip() for issue in query["incidencias"]))
        return data

    def assert_response(self, data, expected, code=0, location=None):
        # Comparar la proyección completa conserva también los datos no dañados.
        self.assertEqual(data["ejecucion"], expected)
        query = data["consulta"]
        self.assertEqual(query["codigo_salida"], code)
        self.assertEqual(query["estado"], "incompleta" if code else "completada")
        self.assertEqual(bool(query["incidencias"]), bool(code))
        if location:
            self.assertRegex("\n".join(query["incidencias"]), location)

    def linked_boolean(self, code):
        fixture = self.fixture
        if code == 1:
            # Un intento consumido tras una solicitud de cambios coherente.
            fixture.review.update(decision_controlador="cambios_solicitados", codigo_salida=1,
                                  dictamen_modelo={"decision": "solicitar_cambios", "hallazgos": [
                                      {"archivo": "solution.py", "linea": 1,
                                       "explicacion": "Hallazgo sintético, no una revisión ejecutada."}]})
            fixture.attempt["transiciones"][-1] = {
                "etapa": "revision", "accion": "corregir", "motivo": "cambios_solicitados"}
            fixture.attempt["transiciones"].append({
                "etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"})
            fixture.record.update(estado="intentos_agotados", codigo_salida=1,
                                  max_intentos=1, max_invocaciones=2)
            fixture.expected.update(estado="intentos_agotados", codigo_salida=1,
                                    presupuestos={"max_intentos": 1, "max_invocaciones": 2})
        fixture.write_records()
        # La consulta del registro coherente debe pasar antes de introducir el defecto.
        self.assert_response(self.query("control"), fixture.expected)
        path = fixture.review_dir / "resultado.json"
        before = evaluar.snapshot(fixture.general)
        linked = copy.deepcopy(fixture.review)
        linked["codigo_salida"] = bool(code)
        fixture.save(path, linked)
        after = evaluar.snapshot(fixture.general)
        changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
        self.assertEqual(changed, ["etapas/revision/resultado.json"])
        saved = evaluar.strict_json(path.read_text(encoding="utf-8"))
        self.assertIs(type(saved.pop("codigo_salida")), bool)
        self.assertEqual(saved, {k: v for k, v in fixture.review.items() if k != "codigo_salida"})
        write_json(self.logs / "mutacion.json", {
            "archivo": "etapas/revision/resultado.json", "campo": "codigo_salida",
            "antes": code, "despues": bool(code), "archivos_cambiados": changed,
            "inventario_antes": before, "inventario_despues": after})
        self.assert_response(self.query("booleano"), fixture.expected, 1,
                             r"(?:etapas/revision/resultado\.json|revisi[oó]n|codigo_salida)")

    def test_resumen_cero_a_false(self):
        self.linked_boolean(0)

    def test_resumen_uno_a_true(self):
        self.linked_boolean(1)

    def duration(self, value, *, valid=True):
        self.fixture.record["duracion_segundos"] = value
        self.fixture.expected["duracion_segundos"] = value if valid else None
        self.fixture.write_records()
        data = self.query("duracion")
        self.assert_response(data, self.fixture.expected, 0 if valid else 1,
                             None if valid else r"\b(?:duración|duracion_segundos)\b")
        if valid:
            self.assertIn(type(data["ejecucion"]["duracion_segundos"]), (int, float))
        return data

    def test_duracion_cero(self):
        self.duration(0)

    def test_duracion_ordinaria(self):
        self.duration(12.3456)

    def test_duracion_entera_grande(self):
        # Entero decimal exacto, no 1e309 ni conversión a float en las aserciones.
        data = self.duration(10**309)
        self.assertIs(type(data["ejecucion"]["duracion_segundos"]), int)

    def test_duracion_invalida(self):
        self.duration(-0.5, valid=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("consultas"),
                        help="Directorio nuevo para entradas y salidas (predeterminado: ./consultas)")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not all((project / name).is_file() for name in ("inspect_run.py", "case_evidence.py")):
        parser.error("--project debe contener inspect_run.py y case_evidence.py")
    output = args.output.resolve()
    if output.exists():
        parser.error("--output debe ser nuevo; no se sobrescriben registros")
    output.mkdir(parents=True)
    HallazgosTests.project, HallazgosTests.output = project, output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HallazgosTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

"""Cobertura permanente de JSON por CLI, sin registros históricos ni agentes.

Reutiliza las aserciones existentes sin lanzar suites secundarias: cada método
forma parte del descubrimiento habitual. Solo los inspectores se ejecutan como
procesos hijos, sobre datos sintéticos y con los límites de los evaluadores.
"""

from pathlib import Path
import tempfile
import unittest

from evals.tareas_reales.inspect_json import comprobar_anidamiento, comprobar_hallazgos, evaluar


PROJECT = Path(__file__).resolve().parents[1]


class TestInspectJsonAcceptance(evaluar.AcceptanceTests):
    project = PROJECT

    def assert_text_formats(self, code):
        default = self.query()
        explicit = self.query("--format", "text")
        self.assertEqual(default.returncode, code)
        self.assertEqual((explicit.returncode, explicit.stdout, explicit.stderr),
                         (default.returncode, default.stdout, default.stderr))
        if code == 0:
            self.assertEqual(default.stderr, "")
            self.assertIn("Consulta: completada (código 0)", default.stdout)
        return default

    def test_texto_conserva_equivalencia_heredada_booleano_numero(self):
        for code in (0, 1):
            with self.subTest(codigo=code):
                if code == 1:
                    self.review.update(
                        decision_controlador="cambios_solicitados", codigo_salida=1,
                        dictamen_modelo={"decision": "solicitar_cambios", "hallazgos": [
                            {"archivo": "solution.py", "linea": 1,
                             "explicacion": "Hallazgo sintético, no una revisión ejecutada."}]})
                    self.attempt["transiciones"][-1] = {
                        "etapa": "revision", "accion": "corregir", "motivo": "cambios_solicitados"}
                    self.attempt["transiciones"].append({
                        "etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"})
                    self.record.update(estado="intentos_agotados", codigo_salida=1,
                                       max_intentos=1, max_invocaciones=2)
                self.write_records()
                self.save(self.review_dir / "resultado.json", {**self.review, "codigo_salida": bool(code)})
                self.assert_text_formats(0)

    def test_texto_conserva_tratamiento_heredado_de_duracion_grande(self):
        self.record["duracion_segundos"] = 10**309
        self.write_records()
        completed = self.assert_text_formats(1)
        self.assertIn("Duración: no consta", completed.stdout)
        self.assertIn("Consulta: incompleta (código 1)", completed.stdout)
        self.assertIn("general: duración inválida", completed.stderr)


class TestInspectJsonHallazgos(comprobar_hallazgos.HallazgosTests):
    project = PROJECT

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci-inspect-hallazgos-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        super().setUp()


class TestInspectJsonAnidamiento(comprobar_anidamiento.AnidamientoTests):
    project = PROJECT

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci-inspect-anidamiento-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        super().setUp()


if __name__ == "__main__":
    unittest.main(verbosity=2)

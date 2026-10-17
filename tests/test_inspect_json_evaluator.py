"""Comprobar el evaluador con respuestas controladas, sin ejecutar candidatos."""

import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from evals.tareas_reales.inspect_json import evaluar


class DurationDiagnosticTests(unittest.TestCase):
    def evaluate_responses(self, diagnostic, *, preserve_duration=False, other_field=False):
        case = evaluar.AcceptanceTests("test_10_tipos_invalidos_no_se_convierten")
        # Respuestas para las seis entradas inválidas del método de aceptación.
        fields = iter((
            ("max_intentos", "presupuestos", "max_intentos"),
            ("max_invocaciones", "presupuestos", "max_invocaciones"),
            ("codigo_salida", None, "codigo_salida"),
            ("duracion_segundos", None, "duracion_segundos"),
            ("duracion_segundos", None, "duracion_segundos"),
            ("intentos", None, "intentos_registrados"),
        ))

        def response(*options):
            self.assertEqual(options, ("--format", "json"))
            source, group, target = next(fields)
            execution = copy.deepcopy(case.expected)
            (execution[group] if group else execution)[target] = None
            issue = f"general: {source} inválido"
            if source == "duracion_segundos":
                issue = diagnostic
                if preserve_duration:
                    execution[target] = case.record[source]
            elif other_field and source == "max_intentos":
                issue = diagnostic
            data = {
                "version_esquema": 1,
                "consulta": {"estado": "incompleta", "codigo_salida": 1, "incidencias": [issue]},
                "ejecucion": execution,
            }
            return subprocess.CompletedProcess([], 1, json.dumps(data), "")

        result = unittest.TestResult()
        with patch.object(case, "query", side_effect=response) as query:
            case.run(result)
        self.assertEqual(query.call_count, 6)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])
        return result

    def assert_duration_failures(self, result):
        self.assertEqual(len(result.failures), 2)
        for subtest, _ in result.failures:
            self.assertEqual(subtest.params["campo"], "duracion_segundos")
        self.assertEqual([subtest.params["valor"] for subtest, _ in result.failures], [True, -0.5])

    def test_acepta_duracion(self):
        self.assertEqual(self.evaluate_responses("general: duración inválida").failures, [])

    def test_acepta_duracion_segundos(self):
        self.assertEqual(self.evaluate_responses("general: duracion_segundos inválida").failures, [])

    def test_rechaza_diagnosticos_sin_campo(self):
        for message in ("dato inválido", "general: valor inválido", "resultado.json: dato inválido"):
            with self.subTest(mensaje=message):
                self.assert_duration_failures(self.evaluate_responses(message))

    def test_rechaza_diagnosticos_de_otro_campo(self):
        for message in ("general: max_intentos inválido", "general: duracion_segundos_extra inválido",
                        "general: preduración inválida"):
            with self.subTest(mensaje=message):
                self.assert_duration_failures(self.evaluate_responses(message))

    def test_rechaza_duracion_invalida_aunque_el_diagnostico_sea_correcto(self):
        for name in ("duración", "duracion_segundos"):
            with self.subTest(nombre=name):
                result = self.evaluate_responses(f"general: {name} inválida", preserve_duration=True)
                self.assert_duration_failures(result)
                # El rechazo ocurre por el valor, antes de comprobar el diagnóstico.
                for _, traceback in result.failures:
                    self.assertIn("self.assertEqual(execution, expected)", traceback)

    def test_no_extiende_el_alias_a_otros_campos(self):
        result = self.evaluate_responses("general: duración inválida", other_field=True)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0][0].params["campo"], "max_intentos")


if __name__ == "__main__":
    unittest.main(verbosity=2)

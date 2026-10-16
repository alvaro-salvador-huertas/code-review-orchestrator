"""Material del evaluador: candidatos importados únicamente en procesos hijos."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from case_config import reference_paths
from case_evidence import reference_test_ids, snapshot_tree, validate_test_report


PROJECT = Path(__file__).resolve().parents[1]
CANDIDATES = PROJECT / "evals/revisor/candidatos"


class TestReviewerCandidates(unittest.TestCase):
    def execute(self, candidate_id, files, arguments, *, stdin=None):
        candidate = (CANDIDATES / f"{candidate_id}.py").read_bytes()
        with tempfile.TemporaryDirectory(prefix="test-reviewer-candidate-") as temporary:
            workspace = Path(temporary)
            (workspace / "solution.py").write_bytes(candidate)
            for name, content in files.items():
                (workspace / name).write_bytes(content)
            before = snapshot_tree(workspace)
            completed = subprocess.run(
                [sys.executable, "-B", *arguments], cwd=workspace, input=stdin,
                capture_output=True, text=True, timeout=30, shell=False,
            )
            self.assertEqual(snapshot_tree(workspace), before, candidate_id)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed

    def assert_reference_suite(self, candidate_id, case_id, count):
        reference = reference_paths(PROJECT, case_id)["test_solution.py"].read_bytes()
        self.assertEqual(len(reference_test_ids(reference)), count)
        completed = self.execute(
            candidate_id, {"test_solution.py": reference},
            ["-m", "unittest", "discover", "-s", ".", "-p", "test_solution.py", "-v"],
        )
        self.assertEqual(completed.stdout, "")
        validate_test_report(reference, completed.stderr)

    def probe(self, candidate_id, source, inputs):
        completed = self.execute(candidate_id, {}, ["-c", source], stdin=json.dumps(inputs))
        self.assertEqual(completed.stderr, "")
        return json.loads(completed.stdout)

    def test_candidato_01_pruebas_originales(self):
        self.assert_reference_suite("candidato_01", "case_01", 4)

    def test_candidato_02_pruebas_originales(self):
        self.assert_reference_suite("candidato_02", "case_01", 4)

    def test_candidato_03_pruebas_originales(self):
        self.assert_reference_suite("candidato_03", "case_02", 16)

    def test_candidato_04_pruebas_originales(self):
        self.assert_reference_suite("candidato_04", "case_02", 16)

    def test_comparacion_exacta_y_nombre_de_primera_aparicion(self):
        inputs = [
            [{"asignatura": "Python", "minutos": 20},
             {"asignatura": "python", "minutos": 15},
             {"asignatura": "Python", "minutos": 5},
             {"asignatura": "Redes", "minutos": 7}],
            [{"asignatura": "python", "minutos": 15},
             {"asignatura": "Python", "minutos": 20},
             {"asignatura": "python", "minutos": 5},
             {"asignatura": "Redes", "minutos": 7}],
        ]
        required = [{"Python": 25, "python": 15, "Redes": 7},
                    {"python": 20, "Python": 20, "Redes": 7}]
        source = """
import json
import sys
from solution import calcular_totales_por_asignatura

inputs = json.load(sys.stdin)
results = [calcular_totales_por_asignatura(sessions) for sessions in inputs]
print(json.dumps({"results": results, "inputs_after": inputs}))
"""
        for candidate_id, expected, mismatches in (
            ("candidato_01", required, []),
            ("candidato_02", [{"Python": 40, "Redes": 7}, {"python": 40, "Redes": 7}], [0, 1]),
        ):
            with self.subTest(candidate=candidate_id):
                observed = self.probe(candidate_id, source, inputs)
                self.assertEqual(observed["inputs_after"], inputs)
                self.assertEqual(observed["results"], expected)
                self.assertEqual(
                    [i for i, result in enumerate(observed["results"]) if result != required[i]],
                    mismatches,
                )

    def test_prioridad_timeout_y_ausencia_de_otras_discrepancias_en_la_tabla(self):
        responses = [None, "", "\t\u00a0", "texto"]
        rows = [
            (None, False, ["fallo_ejecucion"] * 4),
            (None, True, ["tiempo_agotado"] * 4),
            (0, False, ["respuesta_vacia"] * 3 + ["completada"]),
            (0, True, ["tiempo_agotado"] * 4),
            (1, False, ["fallo_ejecucion"] * 4),
            (1, True, ["tiempo_agotado"] * 4),
        ]
        inputs = [[code, response, timeout] for code, timeout, _ in rows for response in responses]
        required = [result for _, _, results in rows for result in results]
        source = """
import json
import sys
from solution import clasificar_ejecucion

inputs = json.load(sys.stdin)
results = [clasificar_ejecucion(code, response, tiempo_agotado=timeout)
           for code, response, timeout in inputs]
print(json.dumps(results))
"""
        for candidate_id, mismatches in (("candidato_03", []), ("candidato_04", [4, 5, 6, 7])):
            with self.subTest(candidate=candidate_id):
                expected = required.copy()
                for i in mismatches:
                    expected[i] = "fallo_ejecucion"
                observed = self.probe(candidate_id, source, inputs)
                self.assertEqual(observed, expected)
                self.assertEqual(
                    [i for i, result in enumerate(observed) if result != required[i]],
                    mismatches,
                )


if __name__ == "__main__":
    unittest.main()

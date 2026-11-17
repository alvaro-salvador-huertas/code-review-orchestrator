"""Corpus y puntuación con Git real y revisor simulado: cero llamadas a modelos."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import evaluate_review_diff as evaluation
from case_evidence import snapshot_tree
import review_diff


class EvaluateReviewDiffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="diff-eval-test-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.experiment = self.parent / "experiment"
        self.root = self.parent / "project"
        self.root.mkdir()
        for source in evaluation.SOURCES:
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((evaluation.PROJECT / source).read_bytes())
        # La suite también se ejecuta sobre copias de producto sin .git.
        # El fixture debe tener su propio repositorio, no depender del del lanzador.
        from process_environment import process_environment
        with process_environment() as env:
            for args in (["init", "-q", "--template="], ["add", "."],
                         ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                          "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture"]):
                subprocess.run(["git", "-C", str(self.root), *args], env=env,
                               check=True, capture_output=True, timeout=10)

    def synthetic(self):
        with patch("review_diff.invoke_reviewer", side_effect=AssertionError("No se permite un modelo")):
            result = evaluation.check(self.experiment, root=self.root)
        return result, evaluation.read_json(self.experiment / "juicios_sinteticos.json")

    def test_frozen_eight_commits_reproduce_and_previews_match_production_cli(self):
        with patch("review_diff.invoke_reviewer", side_effect=AssertionError("No modelo")):
            evaluation.prepare(self.experiment, root=self.root)
        manifest, cases = evaluation.validate_preparation(self.experiment)
        self.assertIn("fuentes/timeout_diagnostics.py", manifest["sha256"])
        another = evaluation.build_repository(self.parent / "other.git", cases)
        self.assertEqual([c["id"] for c in cases], evaluation.IDS)
        self.assertEqual(sum(bool(c["expectativa"]["defectos"]) for c in cases), 4)
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(another[case["id"]], case["commits"])
                cmd = [sys.executable, "-B", str(self.root / "review_diff.py"), "--repo",
                       str(self.experiment / "preparacion/repo.git"), "--base", case["commits"]["base"],
                       "--candidate", case["commits"]["candidato"], "--file", "module.py"]
                for criterion in case["criterios"]:
                    cmd += ["--criterion", criterion]
                proc = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
                preview = json.loads(proc.stdout)
                self.assertEqual(preview, evaluation.read_json(self.experiment / "preparacion" /
                                                              (case["id"] + ".json")))
                self.assertEqual(set(preview["materiales"]), {"version", "commit_base", "commit_candidato",
                                 "criterios", "archivos", "pruebas_ejecutadas"})
                self.assertEqual(len(preview["materiales"]["archivos"]), 1)
                self.assertFalse(preview["materiales"]["pruebas_ejecutadas"])
                self.assertNotIn(b'"expectativa"', proc.stdout)
                self.assertNotIn(b'"defectos"', proc.stdout)
                self.assertEqual(preview["materiales"]["archivos"][0]["candidato"]["texto"], case["candidato"])
        self.assertEqual(snapshot_tree(self.experiment / "preparacion"), manifest["sha256"])

    def test_synthetic_counts_duplicate_missed_false_additional_and_technical_denominators(self):
        result, judgments = self.synthetic()
        totals = result["totales"]
        self.assertEqual(result["modo"], "sintetico")
        self.assertEqual(result["estado"], "puntuacion_disponible")
        self.assertEqual((totals["casos_planificados"], totals["casos_puntuados"]), (8, 7))
        for name in ("deteccion", "omision"):
            self.assertEqual(totals[name], {"numerador": 2, "denominador": 4, "proporcion": .5})
        self.assertEqual(totals["correctos_con_falsos"]["numerador"], 1)
        self.assertEqual(totals["correctos_con_falsos"]["denominador"], 3)
        self.assertEqual(totals["adicionales_no_respaldados"]["numerador"], 1)
        self.assertEqual(totals["adicionales_no_respaldados"]["denominador"], 4)
        self.assertEqual(totals["menciones_duplicadas"], 1)
        self.assertEqual(totals["fallos_tecnicos"]["numerador"], 1)
        self.assertEqual(totals["correctos_no_evaluables"], 1)
        duplicate = result["casos"][1]
        self.assertEqual((duplicate["defectos_detectados"], duplicate["menciones_duplicadas"]), (1, 1))
        self.assertEqual(result["casos"][6]["estado"], "fallo_tecnico")
        self.assertIsNone(result["casos"][6]["defectos_omitidos"])
        self.assertEqual(evaluation.score(self.experiment, judgments), result)

    def test_pending_human_judgment_is_never_false_or_a_miss(self):
        _, judgments = self.synthetic()
        judgments["casos"][1]["revision_completa"] = False
        result = evaluation.score(self.experiment, judgments)
        self.assertEqual(result["estado"], "requiere_revision")
        self.assertEqual(result["casos"][1]["estado"], "pendiente_juicio")
        self.assertIsNone(result["casos"][1]["defectos_omitidos"])
        self.assertEqual(result["totales"]["deteccion"]["denominador"], 3)
        self.assertEqual(result["totales"]["defectos_no_evaluables"], 1)

    def test_each_finding_requires_bound_explicit_judgment_and_author(self):
        _, judgments = self.synthetic()
        mutations = [lambda j:j.update(autor=""),
                     lambda j:j.update(lanzamiento_sha256="0"*64),
                     lambda j:j.update(origen="humano"),
                     lambda j:j["casos"][1]["hallazgos"].pop(),
                     lambda j:j["casos"][1]["hallazgos"][0].update(respaldado=None),
                     lambda j:j["casos"][1]["hallazgos"][0].update(justificacion=""),
                     lambda j:j["casos"][1]["hallazgos"][0].update(sha256="0"*64),
                     lambda j:j["casos"][1]["hallazgos"][2].update(defecto="D1")]
        for mutate in mutations:
            changed = copy.deepcopy(judgments)
            mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                evaluation.score(self.experiment, changed)

    def test_supported_unexpected_finding_flags_expectation_for_human_revision(self):
        _, judgments = self.synthetic()
        judgments["casos"][3]["hallazgos"][0].update(respaldado=True, defecto=None,
                                                       justificacion="Supuesto hallazgo nuevo para probar el conflicto.")
        result = evaluation.score(self.experiment, judgments)
        self.assertEqual(result["estado"], "requiere_revision")
        self.assertEqual(result["totales"]["adicionales_respaldados"], 1)
        self.assertEqual(result["totales"]["correctos_con_falsos"]["numerador"], 0)

    def test_tampered_report_is_technical_not_a_reviewer_omission(self):
        _, judgments = self.synthetic()
        (self.experiment / "lanzamiento/caso_02/resultado.json").write_text("{}")
        result = evaluation.score(self.experiment, judgments)
        row = result["casos"][1]
        self.assertEqual(row["estado"], "fallo_tecnico")
        self.assertIn("alterado", row["error"])
        self.assertIsNone(row["defectos_omitidos"])
        self.assertEqual(result["totales"]["deteccion"]["denominador"], 3)
        self.assertEqual(result["totales"]["fallos_tecnicos"]["numerador"], 2)

    def test_preparation_tampering_is_rejected_before_any_reviewer(self):
        evaluation.prepare(self.experiment, root=self.root)
        path = self.experiment / "preparacion/fuentes" / evaluation.CORPUS
        path.write_text("{}")
        with patch("review_diff.run_review") as reviewer, self.assertRaisesRegex(ValueError, "alterada"):
            evaluation.run(self.experiment, root=self.root)
        reviewer.assert_not_called()
        self.assertFalse((self.experiment / "lanzamiento").exists())

    def fake_reviewer(self, work, final, prompt, log, *, on_invoke, timeout, timeout_diagnostics):
        self.assertEqual({p.name for p in work.iterdir()}, {"materiales.json", "respuesta.schema.json"})
        materials = evaluation.read_json(work / "materiales.json")
        self.assertNotIn("expectativa", materials)
        self.assertNotIn("casos", materials)
        self.assertEqual(timeout, 180)
        self.assertTrue(timeout_diagnostics)
        on_invoke()
        final.write_bytes(review_diff.json_bytes({"resumen": "Respuesta simulada, no es un modelo.", "hallazgos": []}))
        (log / "codex_version.txt").write_text("fixture-cli\n")
        return {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1,
                "comando": ["codex", "exec", "--cd", str(work), "--output-schema",
                            str(work / "respuesta.schema.json"), "--output-last-message", str(final)]}

    def test_production_path_uses_review_diff_once_per_case_and_refuses_relaunch(self):
        evaluation.prepare(self.experiment, root=self.root)
        with patch("review_diff.invoke_reviewer", side_effect=self.fake_reviewer) as reviewer:
            result = evaluation.run(self.experiment, root=self.root)
            self.assertEqual(result["estado"], "completada")
            self.assertEqual(reviewer.call_count, 8)
            before = snapshot_tree(self.experiment / "lanzamiento")
            with self.assertRaises(FileExistsError):
                evaluation.run(self.experiment, root=self.root)
            self.assertEqual(snapshot_tree(self.experiment / "lanzamiento"), before)
            self.assertEqual(reviewer.call_count, 8)
        judgments = evaluation.judgments_template(self.experiment)
        self.assertEqual(judgments["origen"], "humano")
        self.assertTrue(all(not j["revision_completa"] for j in judgments["casos"]))

    def test_initial_technical_failure_stops_and_remaining_cases_are_not_omissions(self):
        evaluation.prepare(self.experiment, root=self.root)
        with patch("review_diff.invoke_reviewer", return_value={"estado": "cli_no_disponible",
                "codigo_salida": None, "invocaciones": 0}) as reviewer:
            result = evaluation.run(self.experiment, root=self.root)
        self.assertEqual(result["estado"], "incompleta")
        self.assertEqual(reviewer.call_count, 1)
        self.assertEqual(result["casos"][0]["estado"], "fallo_tecnico")
        self.assertTrue(all(c["estado"] == "no_ejecutado" for c in result["casos"][1:]))
        judgments = evaluation.judgments_template(self.experiment)
        judgments["autor"] = "Revisión de la detención simulada"
        result = evaluation.score(self.experiment, judgments)
        self.assertEqual(result["totales"]["no_ejecutados"]["numerador"], 7)
        self.assertEqual(result["totales"]["deteccion"]["denominador"], 0)
        self.assertIsNone(result["totales"]["deteccion"]["proporcion"])

    def test_changed_cli_version_is_technical_and_stops_without_retry(self):
        evaluation.prepare(self.experiment, root=self.root)
        calls = []
        def reviewer(*args, **kwargs):
            calls.append(1)
            result = self.fake_reviewer(*args, **kwargs)
            if len(calls) == 2:
                (args[3] / "codex_version.txt").write_text("different-cli\n")
            return result
        with patch("review_diff.invoke_reviewer", side_effect=reviewer):
            result = evaluation.run(self.experiment, root=self.root)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["estado"], "incompleta")
        self.assertEqual(result["casos"][1]["estado"], "fallo_tecnico")
        self.assertIn("versión", result["casos"][1]["error"])
        self.assertTrue(all(c["estado"] == "no_ejecutado" for c in result["casos"][2:]))

    def test_tampering_previous_report_during_final_review_prevents_completion(self):
        evaluation.prepare(self.experiment, root=self.root)
        calls = []
        def reviewer(*args, **kwargs):
            calls.append(1)
            result = self.fake_reviewer(*args, **kwargs)
            if len(calls) == 8:
                (self.experiment / "lanzamiento/caso_01/instrucciones.txt").write_text("alterado")
            return result
        with patch("review_diff.invoke_reviewer", side_effect=reviewer):
            result = evaluation.run(self.experiment, root=self.root)
        self.assertEqual(len(calls), 8)
        self.assertEqual(result["estado"], "incompleta")
        self.assertEqual(result["casos"][-1]["estado"], "fallo_tecnico")
        self.assertIn("anterior alterado", result["casos"][-1]["error"])

    def test_cli_check_no_model_and_explicit_authorization_required(self):
        cli = [sys.executable, "-B", str(self.root / "evaluate_review_diff.py")]
        proc = subprocess.run(cli + ["check", "--output", str(self.experiment)], capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["modo"], "sintetico")
        proc = subprocess.run(cli + ["run", "--experiment", str(self.experiment)], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"--invoke-model", proc.stderr)


if __name__ == "__main__":
    unittest.main()

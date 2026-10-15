"""Recorridos con procesos reales y Codex simulado; nunca llama a un modelo."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import orchestrate_case
import repair_case
import review_case
from case_config import reviewer_prompt_path
from case_evidence import digest, snapshot_tree, unified_diff
import test_orchestrate_case as support


class TestMulticase(support.OrchestrationFixture, unittest.TestCase):
    def select_case(self, case_id):
        fixture = (support.TestOrchestrateCase01 if case_id == "case_01"
                   else support.TestOrchestrateCase)
        for name in ("case_id", "original", "good", "partial", "function"):
            setattr(self, name, getattr(fixture, name))

    def accepted_pair(self):
        records = {}
        for case_id in ("case_01", "case_02"):
            self.select_case(case_id)
            result = self.execute()
            self.assertEqual(result["codigo_salida"], 0)
            records[case_id] = result["intentos"][0]
        return records

    @contextmanager
    def replace_files(self, directory, changes):
        before = {name: (directory / name).read_bytes() for name in changes}
        try:
            for name, value in changes.items():
                if isinstance(value, bytes):
                    (directory / name).write_bytes(value)
                else:
                    repair_case.write_json(directory / name, value)
            yield
        finally:
            for name, value in before.items():
                (directory / name).write_bytes(value)

    def assert_rejected_without_cli(self, directory):
        before = snapshot_tree(self.project / "runs")
        with patch.object(review_case, "run_process") as process:
            result = review_case.run_review(directory, self.project)
        self.assertEqual(result["codigo_salida"], 7, result)
        self.assertEqual(result["revisor"]["invocaciones"], 0)
        self.assertIsNone(result["registro"])
        process.assert_not_called()
        self.assertEqual(snapshot_tree(self.project / "runs"), before)

    def test_cli_reparacion_y_revision_de_ambos_casos_desde_otro_directorio(self):
        for name in ("repair_case.py", "review_case.py", "run_case.py", "case_evidence.py", "case_config.py"):
            shutil.copy2(support.PROJECT / name, self.project / name)
        bin_dir = self.temporary / "bin"
        bin_dir.mkdir()
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        for case_id, total, failures in (("case_01", 4, 1), ("case_02", 16, 7)):
            with self.subTest(case_id=case_id):
                self.select_case(case_id)
                self.configure([{"candidate": self.good}], [{"response": json.dumps(support.APPROVAL)}])
                shutil.copy2(self.fake, bin_dir / "codex")
                before = set((self.project / "runs").iterdir())
                completed = subprocess.run(
                    [sys.executable, "-B", str(self.project / "repair_case.py"), case_id],
                    cwd=self.temporary, env=env, capture_output=True, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                source, = set((self.project / "runs").iterdir()) - before
                original = snapshot_tree(source)
                self.assertIn(f"Ran {total} tests", (source / "inicial/stderr.txt").read_text())
                self.assertIn(f"FAILED (failures={failures})", (source / "inicial/stderr.txt").read_text())
                self.assertIn(f"Ran {total} tests", (source / "posterior/stderr.txt").read_text())
                before.add(source)
                completed = subprocess.run(
                    [sys.executable, "-B", str(self.project / "review_case.py"), "--run",
                     str(source.relative_to(self.temporary))],
                    cwd=self.temporary, env=env, capture_output=True, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                review, = set((self.project / "runs").iterdir()) - before
                result, _ = review_case.validate_review_record(review, source, self.project)
                self.assertEqual(result["caso"], case_id)
                self.assertIn(f"_{case_id}_review_", review.name)
                self.assertEqual(snapshot_tree(source), original)
                developer, reviewer = self.observed_calls()
                self.assertEqual(developer["seen"]["solution.py"], self.original)
                self.assertEqual(reviewer["prompt"], reviewer_prompt_path(self.project, case_id).read_text())
                self.assertEqual(reviewer["seen"]["contrato.md"], (source / "referencia/contrato.md").read_text())
                if case_id == "case_01":
                    for requirement in ("acumulación", "comparación exacta", "entrada vacía", "diccionarios"):
                        self.assertIn(requirement, reviewer["prompt"])
                self.assertFalse((self.temporary / "runs").exists())
                self.assert_preserved()

    def test_identificador_contrato_pruebas_candidato_e_informe_cruzados_se_rechazan(self):
        records = self.accepted_pair()
        for case_id, other_id in (("case_01", "case_02"), ("case_02", "case_01")):
            directory = Path(records[case_id]["reparacion"]["registro"])
            other = Path(records[other_id]["reparacion"]["registro"])
            original_summary = (directory / "resultado.json").read_text()
            for field in ("caso", "contrato.md", "test_solution.py", "solution.py", "candidato.py",
                          "inicial/stderr.txt", "posterior/stderr.txt"):
                with self.subTest(case_id=case_id, field=field):
                    summary = json.loads(original_summary)
                    changes = {"resultado.json": summary}
                    if field == "caso":
                        summary["caso"] = other_id
                    elif field.endswith("stderr.txt"):
                        changes[field] = (other / field).read_bytes()
                    elif field == "candidato.py":
                        data = (other / field).read_bytes()
                        changes[field] = data
                        summary["sha256"]["candidato"] = digest(data)
                    else:
                        data = (other / "referencia" / field).read_bytes()
                        changes["referencia/" + field] = data
                        summary["sha256"]["referencia"][field] = digest(data)
                        if field == "test_solution.py":
                            for name in ("agente/test_solution_despues.py", "inicial/workspace/test_solution.py",
                                         "posterior/workspace/test_solution.py"):
                                changes[name] = data
                            summary["sha256"]["pruebas_agente"] = digest(data)
                    with self.replace_files(directory, changes):
                        self.assert_rejected_without_cli(directory)

    def test_caso_ausente_desconocido_o_invalido_no_se_infiere_de_la_carpeta(self):
        result = self.execute()
        directory = Path(result["intentos"][0]["reparacion"]["registro"])
        original = (directory / "resultado.json").read_text()
        for value in (None, "case_03", [], True):
            with self.subTest(value=value):
                summary = json.loads(original)
                summary["caso"] = value
                with self.replace_files(directory, {"resultado.json": summary}):
                    self.assert_rejected_without_cli(directory)
        summary = json.loads(original)
        del summary["caso"]
        with self.replace_files(directory, {"resultado.json": summary}):
            self.assert_rejected_without_cli(directory)

    def test_revision_no_puede_declarar_otro_caso_ni_usar_otro_origen(self):
        records = self.accepted_pair()
        source = Path(records["case_02"]["reparacion"]["registro"])
        review = Path(records["case_02"]["revision"]["registro"])
        other = Path(records["case_01"]["reparacion"]["registro"])
        summary = json.loads((review / "resultado.json").read_text())
        summary["caso"] = "case_01"
        with self.replace_files(review, {"resultado.json": summary}):
            with self.assertRaises(ValueError):
                review_case.validate_review_record(review, source, self.project)
        with self.assertRaises(ValueError):
            review_case.validate_review_record(review, other, self.project)

    def test_reparacion_rechaza_partida_y_feedback_de_otro_caso_antes_de_evaluar(self):
        result = self.execute([{"candidate": self.partial}], [], attempts=1)
        previous = Path(result["intentos"][0]["reparacion"]["registro"])
        candidate, feedback, provenance = review_case.correction_context(previous, None, self.project)
        with patch.object(repair_case, "evaluate") as evaluate, \
                patch.object(repair_case, "invoke_codex") as invoke:
            result = repair_case.run_repair("case_01", self.project, starting_candidate=candidate,
                                          feedback=feedback, provenance=provenance, strict=True)
        self.assertFalse(result["aceptada"])
        self.assertIn("otro caso", " ".join(result["errores_controlador"]))
        evaluate.assert_not_called()
        invoke.assert_not_called()

    def test_continuidad_cruzada_aunque_partida_hashes_y_feedback_coincidan(self):
        result = self.execute([{"candidate": self.partial}], [], attempts=1)
        previous = Path(result["intentos"][0]["reparacion"]["registro"])
        candidate, feedback, provenance = review_case.correction_context(previous, None, self.project)
        self.select_case("case_01")
        result = self.execute([{"candidate": self.partial}, {"candidate": self.good}])
        directory = Path(result["intentos"][1]["reparacion"]["registro"])
        summary = json.loads((directory / "resultado.json").read_text())
        feedback_bytes = (json.dumps(feedback, ensure_ascii=False, indent=2) + "\n").encode()
        summary["procedencia"] = provenance
        summary["sha256"].update(partida=digest(candidate), feedback=digest(feedback_bytes))
        changes = {
            "resultado.json": summary, "partida.py": candidate, "feedback.json": feedback_bytes,
            "partida.diff": unified_diff(self.original.encode(), candidate, "referencia/solution.py", "partida.py"),
            "correccion.diff": unified_diff(candidate, self.good.encode(), "partida.py", "candidato/solution.py"),
        }
        with self.replace_files(directory, changes):
            with self.assertRaisesRegex(ValueError, "otro caso"):
                review_case.validate_repair(directory, self.project)
            self.assert_rejected_without_cli(directory)

    def test_orquestador_rechaza_etapa_valida_de_otro_caso(self):
        result = self.execute()
        other_repair = result["intentos"][0]["reparacion"]
        self.select_case("case_01")
        with patch.object(orchestrate_case, "run_repair", return_value=other_repair), \
                patch.object(orchestrate_case, "run_review") as review:
            result = self.execute([], [])
        self.assertEqual(result["codigo_salida"], 7)
        self.assertFalse(result["aprobada"])
        review.assert_not_called()

    def test_case_02_sigue_exigiendo_contrato_version_2(self):
        contract = self.project / "tasks/002-classify-run.md"
        contract.write_text(contract.read_text().replace("**Versión 2", "**Versión 1"))
        result = self.execute([], [])
        self.assertEqual(result["codigo_salida"], 7)
        self.assertEqual(self.observed_calls(), [])
        self.assertIsNone(result["registro"])


if __name__ == "__main__":
    unittest.main()

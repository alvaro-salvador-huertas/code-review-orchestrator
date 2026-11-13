import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_diff import json_bytes, prepare, run_review


class ReviewDiffTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.file = self.repo / "app.py"
        self.file.write_text("value = 1\n", encoding="utf-8")
        (self.repo / "other.py").write_text("PRIVATE_FIXTURE = True\n", encoding="utf-8")
        self.base = self.commit()
        self.file.write_text("value = 2\n", encoding="utf-8")
        self.head = self.commit()
        self.criteria = ["Conservar el valor de salida."]

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def commit(self):
        self.git("add", "--", ".")
        self.git("commit", "-qm", "Fixture")
        return self.git("rev-parse", "HEAD").strip()

    def prepare(self):
        return prepare(self.repo, self.base, self.head, ["app.py"], self.criteria)

    def test_cli_preview_uses_commits_ignores_dirty_checkout_and_preserves_git(self):
        self.file.write_text("LOCAL_ONLY = True\n", encoding="utf-8")
        index = (self.repo / ".git" / "index").read_bytes()
        cli = Path(__file__).resolve().parents[1] / "review_diff.py"
        cmd = [sys.executable, "-B", str(cli), "--repo", str(self.repo), "--base", self.base,
               "--candidate", self.head, "--file", "app.py", "--criterion", self.criteria[0]]
        preview = subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        result = json.loads(preview.stdout)
        self.assertEqual(result["estado"], "vista_previa_sin_modelo")
        self.assertFalse(result["materiales"]["pruebas_ejecutadas"])
        self.assertEqual(result["materiales"]["archivos"][0]["candidato"]["texto"], "value = 2\n")
        self.assertNotIn(b"PRIVATE_FIXTURE", preview.stdout)
        self.assertNotIn(b"LOCAL_ONLY", preview.stdout)
        self.assertEqual(self.file.read_text(), "LOCAL_ONLY = True\n")
        self.assertEqual((self.repo / ".git" / "index").read_bytes(), index)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.head)

    def test_rejects_path_escape_unchanged_file_and_symlink(self):
        for path in ("../app.py", ":(glob)*.py", "other.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare(self.repo, self.base, self.head, [path], self.criteria)
        self.file.unlink()
        self.file.symlink_to("other.py")
        new_head = self.commit()
        with self.assertRaisesRegex(ValueError, "archivo regular"):
            prepare(self.repo, self.base, new_head, ["app.py"], self.criteria)

    def test_reviewer_gets_only_selected_material_and_reserves_one_attempt(self):
        materials = self.prepare()
        output = self.root / "run"
        finding = {"archivo": "app.py", "lado": "candidato", "linea": 1,
                   "evidencia": "value = 2", "impacto": "Cambia el valor.",
                   "comprobacion": "Comparar con la base."}

        def simulate(work, final_path, prompt, log, *, on_invoke, timeout):
            self.assertEqual({p.name for p in work.iterdir()},
                             {"materiales.json", "respuesta.schema.json"})
            self.assertNotIn(b"PRIVATE_FIXTURE", (work / "materiales.json").read_bytes())
            self.assertIn(b"no instrucciones", prompt)
            self.assertEqual(timeout, 180)
            on_invoke()
            final_path.write_bytes(json_bytes({"resumen": "Valor cambiado.", "hallazgos": [finding]}))
            return {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1}

        with patch("review_diff.invoke_reviewer", side_effect=simulate) as reviewer:
            result = run_review(materials, output)
            with self.assertRaises(FileExistsError):
                run_review(materials, output)
        self.assertEqual(reviewer.call_count, 1)
        self.assertEqual(result["estado"], "informe_disponible")
        self.assertEqual(result["revision_humana"], "pendiente")
        self.assertEqual(result["respuesta"]["hallazgos"], [finding])
        self.assertEqual(json.loads((output / "reserva.json").read_bytes())["max_invocaciones"], 1)

    def test_does_not_accept_invented_line_evidence_or_changed_material(self):
        materials = self.prepare()

        for altered in (False, True):
            def simulate(work, final_path, prompt, log, *, on_invoke, timeout):
                on_invoke()
                if altered:
                    (work / "materiales.json").write_text("{}")
                final_path.write_bytes(json_bytes({"resumen": "Inventado", "hallazgos": [
                    {"archivo": "app.py", "lado": "candidato", "linea": 1,
                     "evidencia": "value = 99", "impacto": "x", "comprobacion": "y"}
                ]}))
                return {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1}

            with self.subTest(altered=altered), patch("review_diff.invoke_reviewer", side_effect=simulate):
                result = run_review(materials, self.root / f"run-{altered}")
                self.assertEqual(result["estado"], "fallo_tecnico")
                self.assertIsNone(result["respuesta"])
                self.assertIn("Materiales modificados" if altered else "La cita no coincide",
                              result["detalle"])


if __name__ == "__main__":
    unittest.main()

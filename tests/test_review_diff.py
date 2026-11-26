import json
import os
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

    def pr_preview(self, base, head, *extra):
        gh = self.root / "gh"
        gh.write_text(
            "#!/bin/sh\n"
            'test "$*" = "api --hostname github.com --method GET repos/example/project/pulls/7 '
            '--jq .base.sha, .head.sha" || exit 1\n'
            f"echo {base}\necho {head}\n"
        )
        gh.chmod(0o700)
        cli = Path(__file__).resolve().parents[1] / "review_diff.py"
        return subprocess.run(
            [sys.executable, "-B", str(cli), "--repo", str(self.repo),
             "--pr-url", "https://github.com/example/project/pull/7",
             "--file", "app.py", "--criterion", self.criteria[0], *extra],
            env={**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"]},
            capture_output=True, timeout=15,
        )

    def test_pr_preview_reuses_selected_materials(self):
        result = self.pr_preview(self.base, self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["estado"], "vista_previa_sin_modelo")
        self.assertEqual(preview["materiales"], self.prepare())
        self.assertEqual(preview["pull_request"], {
            "url": "https://github.com/example/project/pull/7", "base_rama": self.base,
            "ancestro_comun": self.base, "candidato": self.head,
        })
        for flag in ("--model", "--provider", "--reasoning-effort"):
            self.assertNotIn(flag, preview["comando_vista_previa"])

    def test_pr_preview_command_replays_pinned_materials_without_gh(self):
        (self.repo / "other.py").write_text("candidate_only = True\n")
        candidate = self.commit()
        self.git("checkout", "-qb", "advanced", self.base)
        self.file.write_text("base_only = 99\n")
        advanced = self.commit()
        quoted = """Conservar "sin datos" y 'vacío'."""
        options = ["--model", "modelo-ejemplo", "--provider", "openai", "--reasoning-effort", "high"]
        result = self.pr_preview(advanced, candidate, "--file", "other.py", "--criterion", quoted,
                                 "--criterion=--help", *options)
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        command = preview["comando_vista_previa"]
        self.assertEqual(command[3:], [
            "--repo", str(self.repo.resolve()), "--base", self.base, "--candidate", candidate,
            "--file", "app.py", "--file", "other.py", "--criterion", self.criteria[0],
            "--criterion", quoted, "--criterion=--help", *options,
        ])
        gh_log = self.root / "gh.called"
        (self.root / "gh").write_text('#!/bin/sh\ntouch "$0.called"\nexit 1\n')
        replay = subprocess.run(command, cwd=self.root, capture_output=True, timeout=15,
                                env={**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"]})
        self.assertFalse(gh_log.exists())
        self.assertEqual(replay.returncode, 0, replay.stderr)
        repeated = json.loads(replay.stdout)
        for key in ("estado", "materiales", "instrucciones", "esquema", "seleccion_revisor"):
            self.assertEqual(repeated[key], preview[key])
        self.assertNotIn("comando_vista_previa", repeated)

    def test_pr_preview_excludes_changes_only_in_advanced_base(self):
        self.git("checkout", "-qb", "advanced", self.base)
        self.file.write_text("value = 99\n")
        (self.repo / "other.py").write_text("base_only = 3\n")
        advanced = self.commit()
        result = self.pr_preview(advanced, self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["materiales"], self.prepare())
        self.assertEqual(preview["pull_request"]["base_rama"], advanced)
        self.assertEqual(preview["pull_request"]["ancestro_comun"], self.base)
        rejected = self.pr_preview(advanced, self.head, "--file", "other.py")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn(b"Fuera del diff de la PR: other.py", rejected.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), advanced)

    def test_pr_preview_rejects_shallow_clone_with_misleading_merge_base(self):
        # La rama candidata incorpora el cambio de app.py por un camino largo.
        # Al truncarlo solo queda visible el camino corto a una base más antigua.
        self.git("checkout", "-qb", "topic", self.base)
        self.git("commit", "--allow-empty", "-qm", "Inicio de topic")
        self.git("checkout", "-qb", "long-side", self.head)
        for i in range(6):
            self.git("commit", "--allow-empty", "-qm", f"Paso {i}")
        self.git("checkout", "-q", "topic")
        self.git("merge", "-qm", "Incorporar long-side", "long-side")
        candidate = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(self.git("merge-base", self.head, candidate).strip(), self.head)
        self.assertEqual(self.git("diff", self.head, candidate, "--", "app.py"), "")

        shallow = self.root / "shallow"
        self.git("clone", "-q", "--depth", "4", "--no-single-branch", self.repo.as_uri(), str(shallow))
        self.repo = shallow
        ancestor = self.git("merge-base", self.head, candidate).strip()
        self.assertEqual(ancestor, self.base)
        self.assertEqual(self.git("diff", "--name-only", ancestor, candidate), "app.py\n")
        result = self.pr_preview(self.head, candidate)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"superficial", result.stderr)
        self.assertIn(b"fetch --unshallow", result.stderr)
        self.assertEqual(self.git("rev-parse", "--is-shallow-repository").strip(), "true")
        self.assertFalse((shallow / ".git" / "FETCH_HEAD").exists())

    def test_pr_preview_reports_unrelated_commits_without_fetch(self):
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        unrelated = self.git("commit-tree", tree, "-m", "Raíz independiente").strip()
        result = self.pr_preview(self.head, unrelated)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn("no tienen ancestro común", result.stderr.decode())
        self.assertNotIn(b"fetch", result.stderr)

    def test_pr_preview_missing_candidate_reports_manual_fetch(self):
        missing = "a" * 40
        result = self.pr_preview(self.base, missing)
        self.assertEqual(result.returncode, 2)
        self.assertIn(missing.encode(), result.stderr)
        self.assertIn(b"fetch https://github.com/example/project.git", result.stderr)
        self.assertIn(b"refs/pull/7/head", result.stderr)
        self.assertFalse((self.repo / ".git" / "FETCH_HEAD").exists())

    def test_pr_preview_rejects_model_invocation(self):
        output = self.root / "run"
        result = self.pr_preview(self.base, self.head, "--invoke-model", "--output", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"--pr-url solo genera la vista previa", result.stderr)
        self.assertFalse(output.exists())

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

        def simulate(work, final_path, prompt, log, *, on_invoke, timeout, timeout_diagnostics):
            self.assertEqual({p.name for p in work.iterdir()},
                             {"materiales.json", "respuesta.schema.json"})
            self.assertNotIn(b"PRIVATE_FIXTURE", (work / "materiales.json").read_bytes())
            self.assertIn(b"no instrucciones", prompt)
            self.assertEqual(timeout, 180)
            self.assertTrue(timeout_diagnostics)
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
            def simulate(work, final_path, prompt, log, *, on_invoke, timeout, timeout_diagnostics):
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

    def test_old_timeout_record_without_diagnostic_remains_usable(self):
        old = {"estado": "tiempo_agotado", "codigo_salida": -9, "invocaciones": 1,
               "inicio_utc": "2026-01-01T00:00:00Z", "fin_utc": "2026-01-01T00:03:00Z",
               "duracion_segundos": 180.1, "limite_segundos": 180, "error": None}
        output = self.root / "old-timeout"
        with patch("review_diff.invoke_reviewer", return_value=old):
            result = run_review(self.prepare(), output)
        self.assertEqual(result["estado"], "fallo_tecnico")
        self.assertIsNone(result["respuesta"])
        self.assertEqual(result["revisor"], old)
        self.assertNotIn("diagnostico_timeout", result["revisor"])
        self.assertEqual(json.loads((output / "resultado.json").read_bytes()), result)


if __name__ == "__main__":
    unittest.main()

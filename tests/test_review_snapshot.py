import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_diff import (
    MAX_FILE, SNAPSHOT_PROMPT, json_bytes, prepare_snapshot, response_schema,
    run_review, validate_response,
)


class ReviewSnapshotTests(unittest.TestCase):
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
        self.sources = {
            "src/app.cpp": 'int value() { return 2; }\n',
            "include/app.h": 'int value();\n',
            "include/types.hpp": 'using Count = unsigned;\n',
        }
        for name, content in self.sources.items():
            path = self.repo / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (self.repo / "private.cpp").write_text("PRIVATE_FIXTURE\n")
        (self.repo / "other.py").write_text("PRIVATE_PYTHON\n")
        self.commit = self.save()
        self.criteria = ["Comprobar el valor devuelto."]
        self.cli = Path(__file__).resolve().parents[1] / "review_diff.py"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def save(self):
        self.git("add", "--", ".")
        self.git("commit", "-qm", "Fixture")
        return self.git("rev-parse", "HEAD").strip()

    def prepare(self):
        return prepare_snapshot(self.repo, self.commit, list(self.sources), self.criteria)

    def command(self):
        return [sys.executable, "-B", str(self.cli), "--repo", str(self.repo),
                "--file", "src/app.cpp", "--criterion", self.criteria[0]]

    def test_cli_preview_single_commit_full_sources_and_preserved_checkout(self):
        dirty = self.repo / "src/app.cpp"
        dirty.write_text("LOCAL_ONLY\n")
        index = (self.repo / ".git/index").read_bytes()
        command = self.command() + ["--snapshot", self.commit]
        for name in list(self.sources)[1:]:
            command.extend(["--file", name])
        process = subprocess.run(command, capture_output=True, check=True, timeout=15)
        preview = json.loads(process.stdout)
        self.assertEqual(preview["estado"], "vista_previa_sin_modelo")
        materials = preview["materiales"]
        self.assertEqual(materials["modo"], "snapshot")
        self.assertEqual(materials["commit_snapshot"], self.commit)
        self.assertNotIn("commit_base", materials)
        self.assertNotIn("commit_candidato", materials)
        self.assertFalse(materials["pruebas_ejecutadas"])
        self.assertEqual(materials["criterios"], self.criteria)
        for entry in materials["archivos"]:
            self.assertEqual(set(entry), {"archivo", "snapshot"})
            self.assertEqual(entry["snapshot"]["texto"], self.sources[entry["archivo"]])
        self.assertEqual(preview["instrucciones"], SNAPSHOT_PROMPT)
        self.assertEqual(preview["esquema"], response_schema(materials))
        self.assertNotIn(b"PRIVATE_FIXTURE", process.stdout)
        self.assertNotIn(b"PRIVATE_PYTHON", process.stdout)
        self.assertNotIn(b"LOCAL_ONLY", process.stdout)
        self.assertEqual(dirty.read_text(), "LOCAL_ONLY\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.commit)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"project"})

    def test_cli_rejects_mixed_or_incomplete_modes(self):
        for options in (
            ["--snapshot", self.commit, "--candidate", self.commit],
            ["--snapshot", self.commit, "--base", self.commit],
            ["--base", self.commit],
            ["--candidate", self.commit],
        ):
            with self.subTest(options=options):
                process = subprocess.run(self.command() + options, capture_output=True, timeout=15)
                self.assertEqual(process.returncode, 2)
                self.assertEqual(process.stdout, b"")

    def test_rejects_unselected_types_unsafe_paths_and_symlinks(self):
        for files in ([], ["other.py"], ["../app.cpp"], ["/tmp/app.cpp"],
                      [":(glob)*.cpp"], ["src/app.cpp"] * 2, ["missing.h"],
                      list(self.sources) + ["private.cpp"]):
            with self.subTest(files=files), self.assertRaises(ValueError):
                prepare_snapshot(self.repo, self.commit, files, self.criteria)
        path = self.repo / "src/app.cpp"
        path.unlink()
        path.symlink_to("../private.cpp")
        linked = self.save()
        with self.assertRaisesRegex(ValueError, "archivo regular"):
            prepare_snapshot(self.repo, linked, ["src/app.cpp"], self.criteria)

    def test_rejects_noncommits_invalid_sha_and_oversized_or_invalid_text(self):
        blob = self.git("rev-parse", self.commit + ":src/app.cpp").strip()
        for commit in (self.commit[:8], "HEAD", "z" * 40, blob):
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                prepare_snapshot(self.repo, commit, ["src/app.cpp"], self.criteria)
        path = self.repo / "src/app.cpp"
        for content in (b"x" * (MAX_FILE + 1), b"a\0b", b"\xff"):
            path.write_bytes(content)
            commit = self.save()
            with self.subTest(content=content[:8]), self.assertRaises(ValueError):
                prepare_snapshot(self.repo, commit, ["src/app.cpp"], self.criteria)

    def test_citations_are_checked_against_snapshot_lines(self):
        materials = self.prepare()
        schema = response_schema(materials)
        self.assertEqual(schema["properties"]["hallazgos"]["items"]["properties"]["lado"]["enum"],
                         ["snapshot"])
        value = {"resumen": "Valor observado.", "hallazgos": [{
            "archivo": "src/app.cpp", "lado": "snapshot", "linea": 1,
            "evidencia": "return 2;", "impacto": "Valor observado.",
            "comprobacion": "Inspeccionar la función.",
        }]}
        self.assertEqual(validate_response(json_bytes(value), materials), value)
        for alteration in ({"lado": "base"}, {"lado": "candidato"}, {"linea": 2},
                           {"linea": True}, {"evidencia": "return 99;"},
                           {"archivo": "private.cpp"}):
            changed = copy.deepcopy(value)
            changed["hallazgos"][0].update(alteration)
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                validate_response(json_bytes(changed), materials)

    def test_snapshot_review_uses_single_version_prompt_and_one_mock_invocation(self):
        materials = self.prepare()
        output = self.root / "run"

        def simulate(work, final_path, prompt, log, *, on_invoke, timeout):
            self.assertEqual({p.name for p in work.iterdir()},
                             {"materiales.json", "respuesta.schema.json"})
            self.assertEqual(json.loads((work / "materiales.json").read_bytes()), materials)
            self.assertEqual(prompt, SNAPSHOT_PROMPT.encode("utf-8"))
            self.assertEqual(timeout, 180)
            on_invoke()
            final_path.write_bytes(json_bytes({"resumen": "Sin hallazgos.", "hallazgos": []}))
            return {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1}

        with patch("review_diff.invoke_reviewer", side_effect=simulate) as reviewer:
            result = run_review(materials, output)
        self.assertEqual(reviewer.call_count, 1)
        self.assertEqual(result["estado"], "informe_disponible")
        self.assertEqual((output / "instrucciones.txt").read_text(), SNAPSHOT_PROMPT)
        self.assertEqual(json.loads((output / "reserva.json").read_bytes())["max_invocaciones"], 1)


if __name__ == "__main__":
    unittest.main()

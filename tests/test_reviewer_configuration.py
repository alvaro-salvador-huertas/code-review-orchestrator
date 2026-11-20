"""CLI y campaña completas con ejecutable local; ninguna llamada a modelos."""

import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from case_evidence import digest, snapshot_tree
import evaluate_review_diff as evaluation
import review_case
import review_diff
import reviewer_configuration as configuration


PROJECT = Path(__file__).resolve().parents[1]
HELP = ("--model --config --sandbox read-only --cd --skip-git-repo-check "
        "--ephemeral --json --output-last-message --output-schema")
SELECTED = {"model": "fixture-model", "provider": "fixture_provider", "reasoning_effort": "high"}


class ReviewerConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="reviewer-config-fixture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in evaluation.SOURCES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((PROJECT / name).read_bytes())
        self.git(self.source, "init", "-q", "--template=")
        self.git(self.source, "add", ".")
        self.git(self.source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture")
        self.repo = self.root / "project"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "--template=")
        (self.repo / "app.py").write_text("value = 1\n")
        self.base = self.commit()
        (self.repo / "app.py").write_text("value = 2\n")
        self.head = self.commit()
        self.home = self.root / "codex-home"
        self.home.mkdir()
        (self.home / "config.toml").write_text(
            '[model_providers.fixture_provider]\n'
            'name = "Fixture"\nbase_url = "https://example.invalid/v1"\n'
            'api_key = "PRIVATE_CONFIG_VALUE"\n')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fake = self.bin / "codex"
        self.calls = self.root / "calls.jsonl"
        self.events = self.root / "events.json"
        self.events.write_text(json.dumps([
            {"type": "session_configured", "model": "declared-only", "model_provider": "declared",
             "reasoning_effort": "high"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "PRIVATE_EVENT_VALUE"}},
        ]))
        self.configure_fake()
        self.environment = patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "CODEX_HOME": str(self.home),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def git(self, repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True)

    def commit(self):
        self.git(self.repo, "add", ".")
        self.git(self.repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture")
        return self.git(self.repo, "rev-parse", "HEAD").strip()

    def configure_fake(self, help_text=HELP):
        self.fake.write_text(
            f"#!{sys.executable}\n"
            "import json,sys\nfrom pathlib import Path\n"
            "args = sys.argv[1:]\n"
            f"with Path({str(self.calls)!r}).open('a') as stream:\n"
            "    stream.write(json.dumps(args)+'\\n')\n"
            "if args == ['--version']:\n"
            "    print('fixture-codex 1.0'); sys.exit(0)\n"
            "if args == ['exec','--help']:\n"
            f"    print({help_text!r}); sys.exit(0)\n"
            "assert args[:3] == ['exec','--sandbox','read-only']\n"
            "for required in ('approval_policy=\"never\"','web_search=\"disabled\"','features.multi_agent=false'):\n"
            "    assert required in args\n"
            "assert '--ephemeral' in args and '--json' in args\n"
            "sys.stdin.buffer.read()\n"
            "final = Path(args[args.index('--output-last-message')+1])\n"
            "final.write_text(json.dumps({'resumen':'Fixture sin modelos.','hallazgos':[]}))\n"
            f"for event in json.loads(Path({str(self.events)!r}).read_text()):\n"
            "    print(json.dumps(event),flush=True)\n"
        )
        self.fake.chmod(0o700)

    def calls_read(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def review_command(self, output=None, options=None):
        command = [sys.executable, "-B", str(self.source / "review_diff.py"),
                   "--repo", str(self.repo), "--base", self.base, "--candidate", self.head,
                   "--file", "app.py", "--criterion", "Conservar el valor."]
        for key, value in (options or {}).items():
            command += ["--" + key.replace("_", "-"), value]
        if output is not None:
            command += ["--invoke-model", "--output", str(output)]
        return command

    def prepare(self, name="experiment", **options):
        path = self.root / name
        evaluation.prepare(path, root=self.source, **options)
        return path

    def run_campaign(self, experiment):
        with patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)):
            return evaluation.run(experiment, root=self.source)

    def test_review_cli_transmits_all_options_through_preflights_and_execution(self):
        output = self.root / "review"
        subprocess.run(self.review_command(output, SELECTED), check=True, capture_output=True, timeout=15)
        calls = self.calls_read()
        self.assertEqual(calls[:2], [["--version"], ["exec", "--help"]])
        self.assertEqual(len(calls), 3)
        self.assertEqual(configuration.sent_options(["codex", *calls[-1]]), review_case.codex_model_options(**SELECTED))
        result = evaluation.read_json(output / "resultado.json")
        trace = result["configuracion_revisor"]
        self.assertEqual(trace["solicitada"], {"modelo": "fixture-model", "proveedor": "fixture_provider", "esfuerzo": "high"})
        self.assertEqual(trace["argumentos_cli"], review_case.codex_model_options(**SELECTED))
        for field in ("modelo", "proveedor", "esfuerzo"):
            self.assertEqual(trace["efectiva"][field], "no consta")
        self.assertEqual(trace["efectiva"]["procedencia"], [])
        self.assertNotIn("PRIVATE", json.dumps(trace))
        raw = evaluation.read_json(output / "revisor/resultado.json")
        self.assertEqual(raw["comando"], result["revisor"]["comando"])
        self.assertEqual(raw["limite_segundos"], 180)

    def test_prepare_cli_freezes_and_run_sends_same_selection_to_eight_calls(self):
        experiment = self.root / "cli-campaign"
        command = [sys.executable, "-B", str(self.source / "evaluate_review_diff.py"), "prepare",
                   "--output", str(experiment), "--model", "fixture-model", "--provider", "fixture_provider",
                   "--reasoning-effort", "high"]
        subprocess.run(command, check=True, capture_output=True, timeout=15)
        self.assertEqual(self.calls_read(), [])
        manifest, _ = evaluation.validate_preparation(experiment)
        self.assertEqual(manifest["version"], 2)
        self.assertIn("configuracion-revisor.json", manifest["sha256"])
        self.assertEqual(evaluation.frozen_selection(experiment, manifest), SELECTED)
        command = [sys.executable, "-B", str(self.source / "evaluate_review_diff.py"), "run",
                   "--experiment", str(experiment), "--invoke-model"]
        subprocess.run(command, check=True, capture_output=True, timeout=30)
        calls = self.calls_read()
        self.assertEqual(len(calls), 24)
        for index in range(0, len(calls), 3):
            self.assertEqual(calls[index:index+2], [["--version"], ["exec", "--help"]])
            self.assertEqual(configuration.sent_options(["codex", *calls[index+2]]),
                             review_case.codex_model_options(**SELECTED))
        _, entries = evaluation.archives(experiment)
        self.assertTrue(all(state == "informe_disponible" for _, state, _, _ in entries))
        with self.assertRaises(FileExistsError):
            self.run_campaign(experiment)
        self.assertEqual(len(self.calls_read()), 24)

    def test_omitted_options_preserve_preview_and_command_without_reading_config(self):
        self.events.write_text("[]")
        with patch.object(review_case.Path, "open", side_effect=AssertionError("No leer configuración")):
            review_case.validate_codex_provider(None)
            review_case.validate_codex_provider("openai")
        preview = subprocess.run(self.review_command(), check=True, capture_output=True, timeout=15)
        self.assertNotIn("seleccion_revisor", json.loads(preview.stdout))
        output = self.root / "default-review"
        subprocess.run(self.review_command(output), check=True, capture_output=True, timeout=15)
        self.assertEqual(configuration.sent_options(["codex", *self.calls_read()[-1]]), [])
        result = evaluation.read_json(output / "resultado.json")
        self.assertEqual(result["configuracion_revisor"]["argumentos_cli"], [])
        self.assertEqual(result["configuracion_revisor"]["solicitada"]["modelo"], "no fijado por el lanzador")

    def test_invalid_api_selections_fail_before_outputs_preflights_or_reservations(self):
        invalid = ({"model": ""}, {"model": "--flag"}, {"model": "\ud800"},
                   {"reasoning_effort": []}, {"reasoning_effort": "High"},
                   {"provider": "https://example.invalid"}, {"provider": "model_providers.x"},
                   {"provider": 'x";approval_policy="always'}, {"provider": "missing_provider"})
        for index, options in enumerate(invalid):
            with self.subTest(options=repr(options)), patch.object(review_case, "run_process") as process:
                output = self.root / f"invalid-{index}"
                with self.assertRaises(ValueError):
                    review_diff.run_review({"archivos": [{"archivo": "app.py"}]}, output, **options)
                self.assertFalse(output.exists())
                with self.assertRaises(ValueError):
                    evaluation.prepare(output, root=self.root / "missing", **options)
                self.assertFalse(output.exists())
                with self.assertRaises(ValueError):
                    review_case.invoke_reviewer(self.root, self.root / "response", b"fixture", self.root, **options)
                process.assert_not_called()
        self.assertEqual(self.calls_read(), [])

    def test_invalid_cli_selections_fail_before_resolving_repo_or_writing_outputs(self):
        for option, value in (("--model", "--flag"), ("--model", ""),
                              ("--provider", "missing_provider"), ("--provider", "https://invalid"),
                              ("--reasoning-effort", "invented")):
            for script in ("review_diff.py", "evaluate_review_diff.py"):
                with self.subTest(script=script, option=option, value=value):
                    output = self.root / "invalid-cli"
                    command = (self.review_command(output) if script == "review_diff.py" else
                               [sys.executable, "-B", str(self.source/script), "prepare", "--output", str(output)])
                    result = subprocess.run(command + [option, value], capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(output.exists())
        self.assertEqual(self.calls_read(), [])

    def test_missing_model_flag_fails_preflight_without_model_reservation(self):
        self.configure_fake(HELP.replace("--model ", ""))
        output = self.root / "incompatible"
        subprocess.run(self.review_command(output, {"model": "fixture-model"}), capture_output=True, timeout=15)
        self.assertEqual(self.calls_read(), [["--version"], ["exec", "--help"]])
        result = evaluation.read_json(output / "resultado.json")
        self.assertEqual(result["revisor"]["estado"], "cli_incompatible")
        self.assertFalse((output / "reserva.json").exists())
        self.assertEqual(result["configuracion_revisor"]["argumentos_cli"], [])

    def test_response_evidence_is_separate_from_requested_and_has_minimal_provenance(self):
        self.events.write_text(json.dumps([{"type": "response.completed", "response": {
            "model": "served-model", "provider": "served-provider", "reasoning": {"effort": "low"},
            "id": "PRIVATE_RESPONSE", "output": [{"text": "PRIVATE_OUTPUT"}]}}]))
        output = self.root / "observed"
        subprocess.run(self.review_command(output, SELECTED), check=True, capture_output=True, timeout=15)
        trace = evaluation.read_json(output / "resultado.json")["configuracion_revisor"]
        self.assertEqual(trace["solicitada"]["modelo"], "fixture-model")
        self.assertEqual(trace["efectiva"]["modelo"], "served-model")
        self.assertEqual(trace["efectiva"]["proveedor"], "served-provider")
        self.assertEqual(trace["efectiva"]["esfuerzo"], "low")
        self.assertEqual(len(trace["efectiva"]["procedencia"]), 3)
        self.assertTrue(all(p["linea"] == 1 and p["archivo"] == "eventos.jsonl"
                            and p["evento"] == "response.completed" for p in trace["efectiva"]["procedencia"]))
        self.assertNotIn("PRIVATE", json.dumps(trace))

    def test_conflicting_effective_values_stay_unknown_and_provider_is_not_inferred(self):
        self.events.write_bytes(b'{"type":"response.completed","response":{"model":"one"}}\n'
                               b'{"type":"response.completed","response":{"model":"two"}}\n')
        effective = configuration.effective_from_events(self.events)
        self.assertEqual(effective["modelo"], "no consta")
        self.assertEqual(effective["proveedor"], "no consta")
        self.assertEqual(len(effective["procedencia"]), 2)

    def test_unencodable_or_oversized_metadata_does_not_break_utf8_recording(self):
        path = self.root / "eventos.jsonl"
        path.write_bytes(b"x" * (configuration.MAX_EVENT_LINE + 1) +
                         b'{"type":"response.completed","response":{"model":"false"}}\n' +
                         b'{"type":"response.completed","response":{"model":"\\ud800","provider":"safe"}}\n')
        effective = configuration.effective_from_events(path)
        self.assertEqual(effective["modelo"], "no consta")
        self.assertEqual(effective["proveedor"], "safe")
        review_diff.json_bytes(effective)

    def test_manifest_and_frozen_arguments_inconsistencies_stop_before_launch(self):
        experiment = self.prepare(**SELECTED)
        manifest_path = experiment / "preparacion.json"
        original = evaluation.read_json(manifest_path)
        changed = copy.deepcopy(original)
        changed["configuracion_solicitada"]["modelo"] = "other"
        evaluation.save_json(manifest_path, changed)
        with self.assertRaisesRegex(ValueError, "manifiesto"):
            self.run_campaign(experiment)
        self.assertFalse((experiment / "lanzamiento").exists())
        evaluation.save_json(manifest_path, original)
        path = experiment / "preparacion/configuracion-revisor.json"
        frozen = evaluation.read_json(path)
        frozen["argumentos_cli"] = []
        evaluation.save_json(path, frozen)
        original["sha256"] = snapshot_tree(experiment / "preparacion")
        evaluation.save_json(manifest_path, original)
        with self.assertRaisesRegex(ValueError, "argumentos inconsistentes"):
            self.run_campaign(experiment)
        self.assertFalse((experiment / "lanzamiento").exists())
        self.assertEqual(self.calls_read(), [])

    def test_changed_selection_or_raw_command_cannot_be_hidden_by_rehashing_records(self):
        experiment = self.prepare(**SELECTED)
        self.assertEqual(self.run_campaign(experiment)["estado"], "completada")
        launch_path = experiment / "lanzamiento/resultado.json"
        launch = evaluation.read_json(launch_path)
        first = experiment / "lanzamiento/caso_01"
        result = evaluation.read_json(first / "resultado.json")
        result["revisor"]["comando"] += ["--model", "other"]
        result["configuracion_revisor"] = configuration.trace(SELECTED, result["revisor"], first/"revisor/eventos.jsonl")
        evaluation.save_json(first / "resultado.json", result)
        launch["casos"][0]["sha256"] = snapshot_tree(first)
        evaluation.save_json(launch_path, launch)
        _, entries = evaluation.archives(experiment)
        self.assertEqual(entries[0][1], "fallo_tecnico")
        self.assertIn("comando original", entries[0][3])
        raw = evaluation.read_json(first / "revisor/resultado.json")
        raw["comando"] = result["revisor"]["comando"]
        evaluation.save_json(first / "revisor/resultado.json", raw)
        launch["casos"][0]["sha256"] = snapshot_tree(first)
        evaluation.save_json(launch_path, launch)
        _, entries = evaluation.archives(experiment)
        self.assertEqual(entries[0][1], "fallo_tecnico")
        self.assertIn("selección congelada", entries[0][3])

    def test_historical_preparation_and_records_without_new_fields_still_score(self):
        experiment = self.root / "legacy"
        expected = evaluation.check(experiment, root=self.source)
        manifest = evaluation.read_json(experiment / "preparacion.json")
        (experiment / "preparacion/configuracion-revisor.json").unlink()
        manifest["version"] = 1
        manifest["sha256"] = snapshot_tree(experiment / "preparacion")
        evaluation.save_json(experiment / "preparacion.json", manifest)
        launch = evaluation.read_json(experiment / "lanzamiento/resultado.json")
        launch["preparacion_sha256"] = digest((experiment / "preparacion.json").read_bytes())
        for item in launch["casos"]:
            folder = experiment / "lanzamiento" / item["id"]
            result_file = folder / "resultado.json"
            if result_file.exists():
                result = evaluation.read_json(result_file)
                result.pop("version_registro")
                result.pop("configuracion_revisor")
                evaluation.save_json(result_file, result)
                item["sha256"] = snapshot_tree(folder)
        evaluation.save_json(experiment / "lanzamiento/resultado.json", launch)
        judgments = evaluation.read_json(experiment / "juicios_sinteticos.json")
        judgments["lanzamiento_sha256"] = digest((experiment / "lanzamiento/resultado.json").read_bytes())
        with patch.object(review_case, "validate_codex_provider", side_effect=AssertionError("No consultar proveedores históricos")), \
                patch.object(evaluation, "validate_codex_provider", side_effect=AssertionError("No consultar proveedores históricos")):
            actual = evaluation.score(experiment, judgments)
        self.assertEqual(actual["totales"], expected["totales"])

    def test_removed_provider_is_rejected_before_reservation_but_does_not_block_reading(self):
        experiment = self.prepare(**SELECTED)
        (self.home / "config.toml").unlink()
        evaluation.validate_preparation(experiment)
        with self.assertRaisesRegex(ValueError, "Proveedor no configurado"):
            self.run_campaign(experiment)
        self.assertFalse((experiment / "lanzamiento").exists())
        self.assertEqual(self.calls_read(), [])

    def test_provider_headers_inside_private_multiline_values_are_not_configuration(self):
        config = self.home / "config.toml"
        for quote in ('"""', "'''"):
            with self.subTest(quote=quote):
                config.write_text(f'note = {quote}\n[model_providers.fixture_provider]\n{quote}\n')
                with self.assertRaises(ValueError):
                    review_case.validate_codex_provider("fixture_provider")
                with config.open("a") as stream:
                    stream.write('[model_providers."fixture_provider"] # Proveedor válido; comentario privado\n')
                review_case.validate_codex_provider("fixture_provider")
        config.write_text('#' + 'x' * (256 * 1024) + '\n[model_providers.fixture_provider]\n')
        with self.assertRaises(ValueError):
            review_case.validate_codex_provider("fixture_provider")
        self.assertEqual(self.calls_read(), [])

    def test_changed_frozen_selection_is_detected_without_rehashing(self):
        experiment = self.prepare(**SELECTED)
        path = experiment / "preparacion/configuracion-revisor.json"
        frozen = evaluation.read_json(path)
        frozen["seleccion"]["model"] = "changed"
        evaluation.save_json(path, frozen)
        with self.assertRaisesRegex(ValueError, "Preparación alterada"):
            self.run_campaign(experiment)
        self.assertFalse((experiment / "lanzamiento").exists())
        self.assertEqual(self.calls_read(), [])

    def test_requested_value_cannot_be_used_to_fabricate_effective_evidence(self):
        output = self.root / "unproven"
        subprocess.run(self.review_command(output, SELECTED), check=True, capture_output=True, timeout=15)
        record = evaluation.read_json(output / "resultado.json")
        record["configuracion_revisor"]["efectiva"]["modelo"] = SELECTED["model"]
        with self.assertRaisesRegex(ValueError, "configuración ausente o inconsistente"):
            configuration.validate_trace(record, SELECTED, output / "revisor/eventos.jsonl")


if __name__ == "__main__":
    unittest.main()

from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import repair_case
import review_case
import review_diff
import timeout_diagnostics
from timeout_diagnostics import JSONL_TAIL_BYTES, boottime_seconds, jsonl_tail_summary


class TimeoutDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.log = self.root / "log"

    def simulated_timeout(self, *, enabled=True, boot=(100, 500)):
        popen = MagicMock()
        process = popen.return_value.__enter__.return_value
        process.communicate.side_effect = subprocess.TimeoutExpired("fixture", 180)
        process.returncode = -9
        with patch("repair_case.subprocess.Popen", popen), \
                patch("repair_case.stop_process") as stop, \
                patch("repair_case.timestamp", side_effect=[
                    "2026-01-01T00:00:00Z", "2026-01-01T00:06:40Z", "2026-01-01T00:06:41Z"]), \
                patch("repair_case.time.monotonic", side_effect=[10, 190, 191]), \
                patch("timeout_diagnostics.boottime_seconds", side_effect=boot) as clock:
            result = repair_case.run_process(
                ["fixture"], self.root, self.log, 180,
                stdout_name="eventos.jsonl", timeout_diagnostics=enabled,
            )
        stop.assert_called_once_with(process)
        process.communicate.assert_called_once_with(input=None, timeout=180)
        if not enabled:
            clock.assert_not_called()
        self.assertEqual(result, json.loads((self.log / "resultado.json").read_bytes()))
        self.assertEqual(result["estado"], "tiempo_agotado")
        self.assertEqual(result["codigo_salida"], -9)
        self.assertIsNone(result["error"])
        return result

    def test_simulated_clocks_record_observations_before_cleanup(self):
        result = self.simulated_timeout()
        self.assertEqual(result["limite_segundos"], 180)
        self.assertEqual(result["duracion_segundos"], 181)
        self.assertEqual(result["fin_utc"], "2026-01-01T00:06:41Z")
        self.assertEqual(result["diagnostico_timeout"], {
            "inicio_utc": "2026-01-01T00:00:00Z",
            "timeout_utc": "2026-01-01T00:06:40Z",
            "duracion_monotonica_segundos": 180,
            "duracion_boottime_segundos": 400,
            "eventos_jsonl": {"estado": "vacio", "cola_limitada": False},
        })

    def test_boottime_absent_or_unavailable_at_either_sample_is_omitted(self):
        for samples in ((None, None), (100, None), (None, 500)):
            with self.subTest(samples=samples):
                result = self.simulated_timeout(boot=samples)
                self.assertNotIn("duracion_boottime_segundos", result["diagnostico_timeout"])

    def test_platform_without_boottime_constant_or_clock_support(self):
        with patch.object(timeout_diagnostics.time, "CLOCK_BOOTTIME", 123, create=True):
            del timeout_diagnostics.time.CLOCK_BOOTTIME
            with patch.object(timeout_diagnostics.time, "clock_gettime") as clock:
                self.assertIsNone(boottime_seconds())
                clock.assert_not_called()
        with patch.object(timeout_diagnostics.time, "CLOCK_BOOTTIME", 123, create=True), \
                patch.object(timeout_diagnostics.time, "clock_gettime", side_effect=OSError):
            self.assertIsNone(boottime_seconds())

    def test_default_keeps_old_process_record_without_diagnostic_or_tail_read(self):
        with patch("timeout_diagnostics.jsonl_tail_summary") as read:
            result = self.simulated_timeout(enabled=False)
        self.assertNotIn("diagnostico_timeout", result)
        read.assert_not_called()
        self.assertEqual(set(result), {
            "comando", "directorio_trabajo", "inicio_utc", "limite_segundos", "estado",
            "codigo_salida", "error", "politica_entorno", "fin_utc", "duracion_segundos",
        })

    def test_tail_read_failure_preserves_original_timeout_and_timing(self):
        with patch("timeout_diagnostics.jsonl_tail_summary", side_effect=OSError("fixture")):
            result = self.simulated_timeout()
        diagnostic = result["diagnostico_timeout"]
        self.assertEqual(diagnostic["duracion_monotonica_segundos"], 180)
        self.assertEqual(diagnostic["duracion_boottime_segundos"], 400)
        self.assertEqual(diagnostic["eventos_jsonl"], {"estado": "error_lectura"})

    def test_reviewer_enables_diagnostics_only_for_main_execution(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.log.mkdir(exist_ok=True)

                def preflight(command, work, log, timeout, **kwargs):
                    log.mkdir(exist_ok=True)
                    (log / "stdout.txt").write_text(
                        "--config --sandbox read-only --cd --skip-git-repo-check "
                        "--ephemeral --json --output-last-message --output-schema")
                    return {"estado": "finalizada", "codigo_salida": 0}

                with patch.object(review_case, "run_process", side_effect=preflight) as run:
                    review_case.invoke_reviewer(self.root, self.root / "response", b"fixture",
                                                self.log, timeout_diagnostics=enabled)
                self.assertEqual(run.call_count, 3)
                for call in run.call_args_list[:2]:
                    self.assertNotIn("timeout_diagnostics", call.kwargs)
                execution = run.call_args_list[-1]
                self.assertEqual(execution.args[3], 180)
                self.assertEqual(execution.kwargs.get("timeout_diagnostics", False), enabled)

    def test_preflight_timeout_does_not_enable_diagnostics_or_invoke_reviewer(self):
        self.log.mkdir()

        def preflight(command, work, log, timeout, **kwargs):
            log.mkdir()
            (log / "stdout.txt").write_bytes(b"")
            return {"estado": "tiempo_agotado", "codigo_salida": -9}

        with patch.object(review_case, "run_process", side_effect=preflight) as run:
            result = review_case.invoke_reviewer(self.root, self.root / "response", b"fixture",
                                                 self.log, timeout_diagnostics=True)
        run.assert_called_once()
        self.assertNotIn("timeout_diagnostics", run.call_args.kwargs)
        self.assertNotIn("diagnostico_timeout", result)
        self.assertEqual(result["invocaciones"], 0)
        self.assertEqual(result["estado"], "tiempo_agotado")

    def test_success_does_not_add_timeout_diagnostic(self):
        result = repair_case.run_process([sys.executable, "-B", "-c", "pass"],
                                         self.root, self.log, 5, timeout_diagnostics=True)
        self.assertEqual(result["estado"], "finalizada")
        self.assertNotIn("diagnostico_timeout", result)

    def local_review_timeout(self, events, output):
        fake = self.root / "fake-reviewer"
        help_text = ("--config --sandbox read-only --cd --skip-git-repo-check --ephemeral "
                     "--json --output-last-message --output-schema")
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys, time\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('local fixture'); sys.exit(0)\n"
            "if sys.argv[1:] == ['exec', '--help']:\n"
            f"    print({help_text!r}); sys.exit(0)\n"
            "sys.stdin.buffer.read()\n"
            f"for event in {events!r}:\n"
            "    event['fixture_pid'] = os.getpid()\n"
            "    print(json.dumps(event), flush=True)\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        fake.chmod(0o700)
        # Solo este ejecutable local sustituye al revisor; nunca se lanza Codex.
        with patch.object(review_case, "CODEX_EXECUTABLE", str(fake)), \
                patch.object(review_diff, "TIMEOUT", 0.5):
            return review_diff.run_review({"archivos": [{"archivo": "app.py"}]}, output)

    def test_local_event_emitter_times_out_through_full_review_diff_flow(self):
        result = self.local_review_timeout([{
            "type": "item.started",
            "item": {"type": "command_execution", "command": "PRIVATE_PAYLOAD"},
        }], self.log)
        agent = result["revisor"]
        self.assertEqual(result["estado"], "fallo_tecnico")
        self.assertIsNone(result["respuesta"])
        self.assertEqual(agent["estado"], "tiempo_agotado")
        self.assertEqual(agent["invocaciones"], 1)
        self.assertEqual(agent["limite_segundos"], 0.5)
        diagnostic = agent["diagnostico_timeout"]
        self.assertEqual(diagnostic["eventos_jsonl"], {
            "estado": "leido", "cola_limitada": False,
            "ultimo_evento": {"tipo": "item.started", "tipo_item": "command_execution"},
        })
        self.assertNotIn("PRIVATE_PAYLOAD", json.dumps(diagnostic))
        self.assertGreaterEqual(diagnostic["duracion_monotonica_segundos"], 0.5)
        self.assertLess(diagnostic["duracion_monotonica_segundos"], 5)
        for name in ("version", "ayuda"):
            self.assertEqual(agent[name]["estado"], "finalizada")
            self.assertNotIn("diagnostico_timeout", agent[name])
        for path, expected in ((self.log / "resultado.json", result),
                               (self.log / "revisor/resultado.json", {
                                   k: v for k, v in agent.items() if k not in
                                   ("version", "ayuda", "invocaciones")})):
            self.assertEqual(json.loads(path.read_bytes()), expected)
        if os.name == "posix":
            self.assertEqual(agent["codigo_salida"], -signal.SIGKILL)
            event = json.loads((self.log / "revisor/eventos.jsonl").read_bytes())
            with self.assertRaises(ProcessLookupError):
                os.kill(event["fixture_pid"], 0)

    def test_local_surrogate_events_preserve_both_timeout_records(self):
        for field in ("type", "item.type"):
            for codepoint in (0xd800, 0xdfff):
                with self.subTest(field=field, codepoint=hex(codepoint)):
                    event = {"type": "item.completed", "item": {"type": "agent_message"}}
                    if field == "type":
                        event["type"] = chr(codepoint)
                        expected = {"tipo": "thread.started"}
                    else:
                        event["item"]["type"] = chr(codepoint)
                        expected = {"tipo": "item.completed"}
                    output = self.root / f"{field}-{codepoint:x}"
                    result = self.local_review_timeout([{"type": "thread.started"}, event], output)
                    self.assertEqual(result["estado"], "fallo_tecnico")
                    self.assertIsNone(result["respuesta"])
                    # Ambos documentos deben poder leerse como UTF-8 estricto y JSON.
                    process = json.loads((output / "revisor/resultado.json").read_text(encoding="utf-8"))
                    saved = json.loads((output / "resultado.json").read_text(encoding="utf-8"))
                    self.assertEqual(saved, result)
                    agent = saved["revisor"]
                    self.assertEqual(process, {k: v for k, v in agent.items()
                                              if k not in ("version", "ayuda", "invocaciones")})
                    self.assertEqual(agent["invocaciones"], 1)
                    for record in (process, agent):
                        self.assertEqual(record["estado"], "tiempo_agotado")
                        self.assertEqual(record["limite_segundos"], 0.5)
                        self.assertIsNone(record["error"])
                        if os.name == "posix":
                            self.assertEqual(record["codigo_salida"], -signal.SIGKILL)
                        else:
                            self.assertNotEqual(record["codigo_salida"], 0)
                        diagnostic = record["diagnostico_timeout"]
                        self.assertEqual(diagnostic["inicio_utc"], record["inicio_utc"])
                        for key in ("inicio_utc", "timeout_utc"):
                            self.assertTrue(diagnostic[key].endswith("Z"))
                        self.assertLessEqual(datetime.fromisoformat(record["inicio_utc"]),
                                             datetime.fromisoformat(diagnostic["timeout_utc"]))
                        self.assertLessEqual(datetime.fromisoformat(diagnostic["timeout_utc"]),
                                             datetime.fromisoformat(record["fin_utc"]))
                        self.assertGreaterEqual(diagnostic["duracion_monotonica_segundos"], 0.5)
                        self.assertGreaterEqual(record["duracion_segundos"],
                                                diagnostic["duracion_monotonica_segundos"])
                        if boottime_seconds() is not None:
                            self.assertGreaterEqual(diagnostic["duracion_boottime_segundos"], 0.5)
                        self.assertEqual(diagnostic["eventos_jsonl"], {
                            "estado": "leido", "cola_limitada": False, "ultimo_evento": expected,
                        })
                    events = (output / "revisor/eventos.jsonl").read_bytes()
                    self.assertIn(f"\\u{codepoint:04x}".encode("ascii"), events)
                    if os.name == "posix":
                        pid = json.loads(events.splitlines()[-1])["fixture_pid"]
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
        self.assertEqual(review_diff.TIMEOUT, 180)


class JsonlTailTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "eventos.jsonl"

    def summary(self, content):
        self.path.write_bytes(content)
        return jsonl_tail_summary(self.path)

    def test_empty_and_truncated_only_logs_are_distinct(self):
        self.assertEqual(self.summary(b""), {"estado": "vacio", "cola_limitada": False})
        self.assertEqual(self.summary(b'{"type":"item.'),
                         {"estado": "linea_incompleta", "cola_limitada": False})

    def test_incomplete_final_line_keeps_only_previous_complete_event_types(self):
        content = (b'{"type":"thread.started","thread_id":"PRIVATE"}\n'
                   b'{"type":"item.completed","item":{"type":"agent_message",'
                   b'"text":"PRIVATE"}}\n'
                   b'{"type":"turn.compl')
        self.assertEqual(self.summary(content), {
            "estado": "linea_incompleta", "cola_limitada": False,
            "ultimo_evento": {"tipo": "item.completed", "tipo_item": "agent_message"},
        })

    def test_complete_final_event_without_newline_and_event_without_item(self):
        for ending in (b"", b"\n", b"\r\n"):
            with self.subTest(ending=ending):
                self.assertEqual(self.summary(b'{"type":"turn.completed","usage":{}}' + ending), {
                    "estado": "leido", "cola_limitada": False,
                    "ultimo_evento": {"tipo": "turn.completed"},
                })

    def test_invalid_lines_and_non_event_json_do_not_replace_last_event(self):
        self.assertEqual(self.summary(b'{"type":"turn.started"}\ninvalid\n[]\n'), {
            "estado": "leido", "cola_limitada": False,
            "ultimo_evento": {"tipo": "turn.started"},
        })
        self.assertEqual(self.summary(b'[]\n'),
                         {"estado": "sin_evento_completo", "cola_limitada": False})

    def test_unencodable_event_type_is_skipped_in_favor_of_previous_event(self):
        for invalid in (chr(0xd800), chr(0xdfff), "prefix" + chr(0xd800) + "suffix"):
            with self.subTest(invalid=repr(invalid)):
                event = json.dumps({"type": invalid, "item": {"type": "agent_message"}}).encode("ascii")
                self.assertEqual(self.summary(b'{"type":"thread.started"}\n' + event + b"\n"), {
                    "estado": "leido", "cola_limitada": False,
                    "ultimo_evento": {"tipo": "thread.started"},
                })
                self.assertEqual(self.summary(event + b"\n"), {
                    "estado": "sin_evento_completo", "cola_limitada": False,
                })

    def test_unencodable_item_type_is_omitted_without_losing_event_type(self):
        for invalid in (chr(0xd800), chr(0xdfff), "prefix" + chr(0xdfff) + "suffix"):
            with self.subTest(invalid=repr(invalid)):
                event = json.dumps({"type": "item.completed", "item": {"type": invalid}}).encode("ascii")
                self.assertEqual(self.summary(b'{"type":"thread.started"}\n' + event + b"\n"), {
                    "estado": "leido", "cola_limitada": False,
                    "ultimo_evento": {"tipo": "item.completed"},
                })

    def test_valid_unicode_types_and_surrogate_pairs_keep_original_format(self):
        event = {"type": "événement.\U0001f680", "item": {"type": "mensaje.\U0001f4a1"}}
        # ensure_ascii=True produce un par válido de sustitutos para cada emoji.
        summary = self.summary((json.dumps(event) + "\n").encode("ascii"))
        self.assertEqual(summary, {
            "estado": "leido", "cola_limitada": False,
            "ultimo_evento": {"tipo": event["type"], "tipo_item": event["item"]["type"]},
        })
        self.assertEqual(json.loads(review_diff.json_bytes(summary)), summary)

    def test_bounded_read_never_parses_cut_first_line_as_an_event(self):
        # El sufijo parece un evento, pero su línea empieza antes de la cola.
        fragment = b'{"type":"false_event"}\n'
        suffix = fragment + b" " * (JSONL_TAIL_BYTES - len(fragment))
        self.path.write_bytes(b"x" * JSONL_TAIL_BYTES + suffix)
        self.assertNotIn("ultimo_evento", jsonl_tail_summary(self.path))
        self.path.write_bytes(b"x" * (2 * JSONL_TAIL_BYTES) + b'\n{"type":"turn.started"}\n')
        real_fdopen = os.fdopen
        readers = []

        def tracked_open(descriptor, mode):
            stream = real_fdopen(descriptor, mode)
            reader = MagicMock(wraps=stream)
            reader.__enter__.return_value = reader
            reader.__exit__.side_effect = lambda *args: stream.close()
            readers.append(reader)
            return reader

        with patch("timeout_diagnostics.os.fdopen", side_effect=tracked_open):
            summary = jsonl_tail_summary(self.path)
        self.assertTrue(summary["cola_limitada"])
        self.assertEqual(summary["ultimo_evento"], {"tipo": "turn.started"})
        readers[0].read.assert_called_once_with(JSONL_TAIL_BYTES)


if __name__ == "__main__":
    unittest.main()

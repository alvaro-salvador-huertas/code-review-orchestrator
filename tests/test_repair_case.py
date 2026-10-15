from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import repair_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELP = "--config --sandbox --cd --skip-git-repo-check --json --output-last-message --ephemeral"


class TestRepairCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-repair-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.project = self.temporary / "proyecto con espacios"
        self.project.mkdir()
        for folder in ("benchmark", "tasks"):
            shutil.copytree(PROJECT_ROOT / folder, self.project / folder)
        self.source = self.project / "benchmark" / "case_02"
        (self.source / "solution.py").write_text("VALOR = 0\n", encoding="utf-8")
        (self.source / "test_solution.py").write_text(
            "import unittest\nfrom solution import VALOR\n"
            "class TestValor(unittest.TestCase):\n"
            "    def test_valor(self):\n"
            "        print('salida de pruebas')\n"
            "        self.assertEqual(VALOR, 7)\n", encoding="utf-8",
        )
        self.contract = self.project / "tasks" / repair_case.CASES["case_02"]
        self.contract.write_text("Contrato: VALOR debe valer 7.\n", encoding="utf-8")
        (self.project / "README.md").write_text("PISTA QUE NO DEBE RECIBIR EL AGENTE\n")
        self.originals = {
            path: path.read_bytes()
            for folder in ("benchmark", "tasks")
            for path in (self.project / folder).rglob("*") if path.is_file()
        }
        self.fake = self.temporary / "codex simulado"
        self.calls = self.temporary / "llamadas.jsonl"
        self.received = self.temporary / "entrada_recibida.txt"
        self.configure_fake()

    def configure_fake(self, mode="success"):
        self.fake.write_text(
            f"#!{sys.executable}\n"
            "import json, sys, time\nfrom pathlib import Path\n"
            f"mode = {mode!r}\n"
            f"with Path({str(self.calls)!r}).open('a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('codex-cli 0.162.1')\n    sys.exit(0)\n"
            "if sys.argv[1:] == ['exec', '--help']:\n"
            f"    print('incompatible' if mode == 'incompatible' else {HELP!r})\n"
            "    sys.exit(0)\n"
            f"Path({str(self.received)!r}).write_bytes(sys.stdin.buffer.read())\n"
            "print('{\"type\":\"thread.started\"}', flush=True)\n"
            "print('diagnóstico del agente', file=sys.stderr, flush=True)\n"
            "final = Path(sys.argv[sys.argv.index('--output-last-message') + 1])\n"
            "final.write_text('El agente afirma que todo pasa.\\n')\n"
            "if mode != 'failing':\n"
            "    Path('solution.py').write_text('VALOR = 7\\n')\n"
            "if mode == 'modified':\n"
            "    Path('test_solution.py').write_text('# pruebas eliminadas\\n')\n"
            "if mode == 'deleted_tests':\n"
            "    Path('test_solution.py').unlink()\n"
            "if mode == 'linked_tests':\n"
            "    data = Path('test_solution.py').read_bytes()\n"
            "    Path('copy.py').write_bytes(data)\n"
            "    Path('test_solution.py').unlink()\n"
            "    Path('test_solution.py').symlink_to('copy.py')\n"
            "if mode == 'missing_candidate':\n"
            "    Path('solution.py').unlink()\n"
            "if mode == 'test_timeout':\n"
            "    Path('solution.py').write_text('import time\\ntime.sleep(60)\\nVALOR = 7\\n')\n"
            "if mode == 'test_mutation':\n"
            "    Path('solution.py').write_text(\n"
            "        'from pathlib import Path\\n'\n"
            "        'Path(\"test_solution.py\").write_text(\"# cambiado\")\\nVALOR = 7\\n')\n"
            "if mode == 'timeout':\n    time.sleep(60)\n"
            "sys.exit(9 if mode == 'nonzero' else 0)\n",
            encoding="utf-8",
        )
        self.fake.chmod(0o700)

    def execute(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(repair_case, "CODEX_EXECUTABLE", str(self.fake)):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = repair_case.repair_case("case_02", self.project)
        return code, stdout.getvalue(), stderr.getvalue()

    def record(self):
        directories = list((self.project / "runs").iterdir())
        self.assertEqual(len(directories), 1)
        directory = directories[0]
        return directory, json.loads((directory / "resultado.json").read_text())

    def assert_originals(self):
        for path, content in self.originals.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def agent_calls(self):
        return [args for args in map(json.loads, self.calls.read_text().splitlines())
                if args[0] == "exec" and "--help" not in args]

    def test_candidato_supera_pruebas_con_registro_completo_y_originales_intactos(self):
        code, output, errors = self.execute()
        directory, result = self.record()
        self.assertEqual((code, errors), (0, ""))
        self.assertTrue(result["aceptada"])
        self.assertEqual(result["estado"], "supera_las_pruebas_disponibles")
        self.assertIn("supera las pruebas disponibles", output)
        self.assertEqual(result["pruebas_iniciales"]["codigo_salida"], 1)
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 0)
        self.assertTrue(all(result["integridad"].values()))
        self.assertEqual(result["agente"]["invocaciones"], 1)
        self.assertGreater(result["duracion_segundos"], 0)
        self.assertTrue(result["inicio_utc"].endswith("Z"))
        self.assertTrue(result["fin_utc"].endswith("Z"))
        self.assert_originals()
        for filename in ("solution.py", "test_solution.py"):
            self.assertEqual((directory / "referencia" / filename).read_bytes(),
                             (self.source / filename).read_bytes())
        self.assertEqual((directory / "referencia" / "contrato.md").read_bytes(), self.contract.read_bytes())
        self.assertEqual((directory / "candidato.py").read_text(), "VALOR = 7\n")
        self.assertIn("-VALOR = 0\n+VALOR = 7", (directory / "candidato.diff").read_text())
        agent = directory / "agente"
        self.assertEqual((agent / "entrada.txt").read_bytes(), self.received.read_bytes())
        prompt = self.received.read_text()
        for text in ("Contrato: VALOR debe valer 7", "FAILED (failures=1)", "No instales",
                     "no uses Git", "ni delegues", "no modificarlas"):
            self.assertIn(text, prompt)
        self.assertNotIn("PISTA QUE NO", prompt)
        self.assertEqual((agent / "codex_version.txt").read_text(), "codex-cli 0.162.1\n")
        self.assertIn("thread.started", (agent / "eventos.jsonl").read_text())
        self.assertIn("diagnóstico del agente", (agent / "errores.txt").read_text())
        self.assertIn("afirma", (agent / "respuesta_final.txt").read_text())
        self.assertEqual(json.loads((agent / "resultado.json").read_text())["codigo_salida"], 0)
        for phase in ("inicial", "posterior"):
            self.assertIn("salida de pruebas", (directory / phase / "stdout.txt").read_text())
            self.assertIn("Ran 1 test", (directory / phase / "stderr.txt").read_text())
            self.assertTrue((directory / phase / "resultado.json").is_file())
        workspace = Path(result["agente"]["directorio_trabajo"])
        self.assertNotIn(self.project, workspace.parents)
        self.assertFalse(workspace.exists())
        self.assertNotEqual(result["pruebas_iniciales"]["directorio_trabajo"],
                            result["pruebas_posteriores"]["directorio_trabajo"])
        args, = self.agent_calls()
        for value in ('approval_policy="never"', 'web_search="disabled"',
                      'sandbox_workspace_write.writable_roots=[]', 'features.multi_agent=false',
                      'sandbox_workspace_write.network_access=false',
                      'sandbox_workspace_write.exclude_slash_tmp=true',
                      'sandbox_workspace_write.exclude_tmpdir_env_var=true'):
            self.assertIn(value, args)
        self.assertEqual(args[args.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(args[-1], "-")
        self.assertNotIn("--add-dir", args)
        self.assertNotIn(str(self.project), " ".join(args))
        self.assertEqual(result["agente"]["limite_segundos"], 180)

    def test_codigo_cero_del_agente_no_acepta_candidato_fallido(self):
        self.configure_fake("failing")
        code, _, _ = self.execute()
        directory, result = self.record()
        self.assertEqual(code, 1)
        self.assertFalse(result["aceptada"])
        self.assertEqual(result["agente"]["codigo_salida"], 0)
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 1)
        self.assertEqual((directory / "candidato.diff").read_bytes(), b"")
        self.assertEqual(len(self.agent_calls()), 1)
        self.assert_originals()

    def test_pruebas_modificadas_se_rechazan_y_se_evalua_con_referencia(self):
        self.configure_fake("modified")
        code, _, _ = self.execute()
        directory, result = self.record()
        self.assertEqual(code, 5)
        self.assertEqual(result["estado"], "modificacion_no_permitida")
        self.assertFalse(result["integridad"]["pruebas_agente_intactas"])
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 0)
        self.assertEqual((directory / "posterior" / "workspace" / "test_solution.py").read_bytes(),
                         (self.source / "test_solution.py").read_bytes())
        self.assertIn("eliminadas", (directory / "agente" / "test_solution_despues.py").read_text())
        self.assert_originals()

    def test_pruebas_borradas_no_se_aceptan(self):
        self.configure_fake("deleted_tests")
        self.assertEqual(self.execute()[0], 5)
        self.assertFalse(self.record()[1]["integridad"]["pruebas_agente_intactas"])

    def test_enlace_a_pruebas_identicas_no_se_acepta(self):
        self.configure_fake("linked_tests")
        self.assertEqual(self.execute()[0], 5)

    def test_codex_ausente_conserva_diagnostico_y_evalua_copia_intacta(self):
        self.fake.unlink()
        code, _, _ = self.execute()
        directory, result = self.record()
        self.assertEqual(code, 3)
        self.assertEqual(result["agente"]["estado"], "cli_no_disponible")
        self.assertEqual(result["agente"]["invocaciones"], 0)
        self.assertEqual(result["agente"]["version"]["estado"], "ausente")
        self.assertTrue((directory / "agente" / "version" / "stderr.txt").read_bytes())
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 1)
        self.assert_originals()

    def test_cli_incompatible_no_invoca_agente(self):
        self.configure_fake("incompatible")
        self.assertEqual(self.execute()[0], 3)
        self.assertEqual(self.record()[1]["agente"]["estado"], "cli_incompatible")
        self.assertEqual(self.agent_calls(), [])

    def test_agente_no_cero_no_acepta_aunque_candidato_pase(self):
        self.configure_fake("nonzero")
        self.assertEqual(self.execute()[0], 3)
        directory, result = self.record()
        self.assertEqual(result["agente"]["codigo_salida"], 9)
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 0)
        self.assertTrue((directory / "agente" / "errores.txt").read_bytes())
        self.assertEqual(len(self.agent_calls()), 1)

    def test_tiempo_agotado_conserva_candidato_y_salidas_parciales_sin_reintentar(self):
        self.configure_fake("timeout")
        with patch.object(repair_case, "AGENT_TIMEOUT_SECONDS", 0.3):
            code, _, _ = self.execute()
        directory, result = self.record()
        self.assertEqual(code, 4)
        self.assertEqual(result["agente"]["estado"], "tiempo_agotado")
        self.assertNotEqual(result["agente"]["codigo_salida"], 0)
        self.assertEqual(result["pruebas_posteriores"]["codigo_salida"], 0)
        self.assertEqual((directory / "candidato.py").read_text(), "VALOR = 7\n")
        self.assertIn("thread.started", (directory / "agente" / "eventos.jsonl").read_text())
        self.assertIn("diagnóstico", (directory / "agente" / "errores.txt").read_text())
        self.assertEqual(len(self.agent_calls()), 1)
        self.assert_originals()

    def test_pruebas_posteriores_tienen_limite_de_tiempo(self):
        self.configure_fake("test_timeout")
        with patch.object(repair_case, "TIMEOUT_SECONDS", 0.3):
            self.assertEqual(self.execute()[0], 1)
        self.assertEqual(self.record()[1]["pruebas_posteriores"]["estado"], "tiempo_agotado")

    def test_candidato_que_altera_pruebas_durante_evaluacion_no_se_acepta(self):
        self.configure_fake("test_mutation")
        self.assertEqual(self.execute()[0], 5)
        _, result = self.record()
        self.assertTrue(result["integridad"]["pruebas_agente_intactas"])
        self.assertFalse(result["integridad"]["pruebas_posteriores_pruebas_intactas"])
        self.assert_originals()

    def test_candidato_ausente_no_se_acepta(self):
        self.configure_fake("missing_candidate")
        self.assertEqual(self.execute()[0], 3)
        self.assertFalse(self.record()[1]["candidato_disponible"])

    def test_archivo_requerido_ausente_es_fallo_controlador_con_registro(self):
        self.contract.unlink()
        self.assertEqual(self.execute()[0], 6)
        _, result = self.record()
        self.assertTrue(result["errores_controlador"])
        self.assertFalse(self.calls.exists())

    def test_error_de_registro_conserva_canales_y_no_acepta(self):
        write_json = repair_case.write_json

        def fail_summary(path, value):
            if path.parent.parent.name == "runs":
                raise OSError("fallo de registro simulado")
            write_json(path, value)

        with patch.object(repair_case, "write_json", side_effect=fail_summary):
            code, output, errors = self.execute()
        self.assertEqual(code, 6)
        self.assertIn("fallo controlador", output)
        self.assertIn("fallo de registro simulado", errors)
        directory, = (self.project / "runs").iterdir()
        self.assertTrue((directory / "agente" / "eventos.jsonl").read_bytes())
        self.assertTrue((directory / "agente" / "errores.txt").read_bytes())
        self.assertIn("OK", (directory / "posterior" / "stderr.txt").read_text())
        self.assert_originals()

    def test_registros_unicos(self):
        self.assertEqual(self.execute()[0], 0)
        self.assertEqual(self.execute()[0], 0)
        self.assertEqual(len(list((self.project / "runs").iterdir())), 2)
        self.assertEqual(len(self.agent_calls()), 2)
        self.assert_originals()

    def test_cli_desde_otro_directorio_y_argumentos_invalidos(self):
        for name in ("repair_case.py", "run_case.py", "case_evidence.py", "case_config.py"):
            shutil.copy2(PROJECT_ROOT / name, self.project / name)
        tool_dir = self.temporary / "bin"
        tool_dir.mkdir()
        shutil.copy2(self.fake, tool_dir / "codex")
        environment = dict(os.environ, PATH=str(tool_dir) + os.pathsep + os.environ.get("PATH", ""))
        completed = subprocess.run(
            [sys.executable, "-B", str(self.project / "repair_case.py"), "case_02"],
            cwd=self.temporary, env=environment, capture_output=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.record()[1]["caso"], "case_02")
        self.assertFalse((self.temporary / "runs").exists())
        rejected = subprocess.run(
            [sys.executable, "-B", str(self.project / "repair_case.py"), "case_03"],
            cwd=self.temporary, env=environment, capture_output=True, timeout=10,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(len(self.agent_calls()), 1)


if __name__ == "__main__":
    unittest.main()

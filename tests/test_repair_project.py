"""Flujo de proyecto con Git, CLI y tareas mínimas temporales; nunca Codex real."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import repair_project as controller


PROJECT = Path(__file__).resolve().parents[1]
BASE = 'import argparse\np = argparse.ArgumentParser()\np.add_argument("--run")\np.parse_args()\nprint("BASE")\n'
DELIVERY = 'print("ENTREGA")\n'
HELP = "--config --sandbox --cd --skip-git-repo-check --json --output-last-message --ephemeral"
ACCEPTANCE = '''import argparse
from pathlib import Path
import subprocess
import sys
import unittest
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
args = p.parse_args()
class Acceptance(unittest.TestCase):
    def call(self, *options):
        return subprocess.run([sys.executable, '-B', str(args.project/'inspect_run.py'), '--run', 'sintetico', *options], capture_output=True, text=True, timeout=3)
    def test_basico(self):
        self.assertEqual(self.call().returncode, 0)
    def test_entrega(self):
        for variant in (1, 2):
            with self.subTest(variante=variant):
                completed = self.call('--format', 'json')
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout.strip(), 'ENTREGA')
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
sys.exit(0 if result.wasSuccessful() else 1)
'''
REGRESSION = '''from pathlib import Path
import subprocess
import sys
import unittest
class Regression(unittest.TestCase):
    def test_compatible(self):
        script = Path(__file__).resolve().parents[1]/'inspect_run.py'
        result = subprocess.run([sys.executable, '-B', str(script), '--run', 'sintetico'], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertIn(result.stdout.strip(), ('BASE', 'ENTREGA'))
'''


class TestRepairProject(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-repair-project-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.root = self.temporary / "proyecto con espacios"
        self.root.mkdir()
        self.write("inspect_run.py", BASE)
        self.write("tests/test_fixture.py", REGRESSION)
        self.write("support.txt", "Referencia inmutable\n")
        for name in (".env", ".codex/config.toml", "runs/historico/privado.txt", "__pycache__/archivo.pyc"):
            self.write(name, "NO_COPIAR")
        self.git("init", "-q")
        self.git("add", "--force", ".")
        self.commit_base()
        self.write(controller.ACCEPTANCE, ACCEPTANCE)
        # Copia del controlador para sus pruebas de CLI; no entra en el commit base fixture.
        for name in ("repair_project.py", "project_test_runner.py", "repair_case.py", "run_case.py",
                     "case_config.py", "case_evidence.py", "process_environment.py"):
            self.write(name, (PROJECT / name).read_text())
        self.fake = self.temporary / "codex"
        self.settings = self.temporary / "opciones.json"
        self.calls = self.temporary / "llamadas.jsonl"
        self.configure()
        self.addCleanup(patch.stopall)
        patch.object(controller, "CODEX_EXECUTABLE", str(self.fake)).start()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, timeout=10).stdout

    def commit_base(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Base sintética")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        self.write(controller.CONTRACT, f"# Tarea sintética, sin exportación JSON real\nBase: `{self.base}`\n"
                   "Solo inspect_run.py es editable. No se aporta una implementación.\n")

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import json
import os
from pathlib import Path
import sys
import time
options = json.loads(Path({str(self.settings)!r}).read_text())
args = sys.argv[1:]
if args == ['--version']:
    print('codex-simulado 1.0')
    sys.exit(0)
if args == ['exec', '--help']:
    print('incompatible' if options.get('incompatible') else {HELP!r})
    sys.exit(0)
assert args[0] == 'exec' and args[-1] == '-'
workspace = Path.cwd()
prompt = sys.stdin.read()
with Path({str(self.calls)!r}).open('a') as out:
    out.write(json.dumps({{'args': args, 'workspace': str(workspace), 'prompt': prompt, 'pid': os.getpid(),
                          'files': sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob('*'))}}) + '\\n')
print('{{"type":"evento_simulado"}}', flush=True)
candidate = workspace/'inspect_run.py'
candidate.write_text(options.get('candidate', {DELIVERY!r}))
mutation = options.get('mutation')
if mutation == 'add': (workspace/'extra.txt').write_text('extra')
if mutation == 'empty_dir': (workspace/'nuevo').mkdir()
if mutation == 'delete': (workspace/'support.txt').unlink()
if mutation == 'tests': (workspace/'tests/test_fixture.py').write_text('')
if mutation == 'mode': candidate.chmod(0o777)
if mutation == 'link':
    candidate.unlink()
    candidate.symlink_to(workspace/'support.txt')
if mutation == 'reference':
    final = Path(args[args.index('--output-last-message')+1])
    (final.parent.parent/'referencia/evaluar.py').write_text('alterado')
if mutation == 'record':
    final = Path(args[args.index('--output-last-message')+1])
    (final.parent.parent/'inicial/aceptacion/stderr.txt').write_text('alterado')
if options.get('mutate_original'): Path(options['mutate_original']).write_text('alterado')
if options.get('block'): time.sleep(30)
Path(args[args.index('--output-last-message')+1]).write_text('Respuesta simulada')
sys.exit(options.get('exit_code', 0))
''')
        self.fake.chmod(0o755)

    def run_project(self):
        return controller.run_project(self.root)

    def calls_read(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def cli_command(self):
        return [sys.executable, "-B", str(self.root / "repair_project.py"), "inspect-json"]

    def cli_env(self):
        return {**os.environ, "PATH": str(self.temporary) + os.pathsep + os.environ.get("PATH", "")}

    def test_exito_procedencia_copias_distintas_y_subtests(self):
        self.write("inspect_run.py", "CAMBIO PENDIENTE DEL USUARIO\n")
        before = controller.tree_state(self.root, filter_local=True)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = self.run_project()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["estado"], "supera_las_comprobaciones_disponibles")
        self.assertEqual(out.getvalue() + err.getvalue(), "")
        self.assertEqual(controller.tree_state(self.root, filter_local=True), before)
        self.assertEqual(result["procedencia"]["commit_base"], self.base)
        initial = result["inicial"]["aceptacion"]
        self.assertEqual((initial["metodos"], initial["aserciones_fallidas"], initial["metodos_con_fallos"], initial["fallos_subtest"]), (2, 2, 1, 2))
        self.assertTrue(all(entry["clasificacion"] == "superadas" for entry in result["posterior"].values()))
        log = Path(result["registro"])
        self.assertEqual((log / "referencia/proyecto/inspect_run.py").read_text(), BASE)
        self.assertEqual((log / "entrega/inspect_run.py").read_text(), DELIVERY)
        self.assertIn("+++ b/inspect_run.py", (log / "entrega/candidato.diff").read_text())
        calls = self.calls_read()
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["agente"]["invocaciones"], 1)
        self.assertEqual(result["agente"]["proceso"]["limite_segundos"], 300)
        self.assertTrue(result["reserva_invocacion"])
        self.assertEqual(result["revision"], "pendiente_no_conectada")
        self.assertTrue(all(result["integridad"].values()))
        self.assertIn("CONTRATO", calls[0]["prompt"])
        self.assertIn("unrecognized arguments: --format json", calls[0]["prompt"])
        self.assertNotIn("NO_COPIAR", calls[0]["prompt"])
        self.assertNotIn(self.root, Path(calls[0]["workspace"]).parents)
        for name in calls[0]["files"]:
            self.assertFalse(controller.excluded(name), name)
        workspaces = {calls[0]["workspace"]}
        for phase in ("inicial", "posterior"):
            for kind, timeout in (("aceptacion", 60), ("regresion", 180)):
                process = result[phase][kind]["proceso"]
                self.assertEqual(process["limite_segundos"], timeout)
                workspaces.add(process["directorio_trabajo"])
                self.assertIn(str(log / "referencia/project_test_runner.py"), process["comando"])
                self.assertTrue((log / phase / kind / "pruebas.json").is_file())
        self.assertEqual(len(workspaces), 3)

    def test_aceptacion_posterior_fallida_no_reintenta(self):
        self.configure(candidate=BASE)
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["posterior"]["aceptacion"]["clasificacion"], "fallos_asercion")
        self.assertEqual(result["posterior"]["regresion"]["clasificacion"], "superadas")
        self.assertEqual(len(self.calls_read()), 1)

    def test_regresion_posterior_fallida(self):
        self.configure(candidate="import sys\nprint('ENTREGA' if '--format' in sys.argv else 'MAL')\n")
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["posterior"]["aceptacion"]["clasificacion"], "superadas")
        self.assertEqual(result["posterior"]["regresion"]["clasificacion"], "fallos_asercion")

    def test_regresion_inicial_no_autoriza_desarrollo(self):
        self.write("tests/test_fixture.py", REGRESSION.replace("('BASE', 'ENTREGA')", "('OTRO',)"))
        self.git("add", "tests/test_fixture.py")
        self.commit_base()
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(result["estado"], "preparacion_no_autoriza")
        self.assertEqual(self.calls_read(), [])

    def test_aceptacion_inicial_verde_no_autoriza_desarrollo(self):
        self.write("inspect_run.py", DELIVERY)
        self.git("add", "inspect_run.py")
        self.commit_base()
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(self.calls_read(), [])

    def test_fallo_tecnico_del_agente_conserva_entrega(self):
        self.configure(exit_code=9)
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 3, result)
        self.assertEqual(result["agente"]["proceso"]["codigo_salida"], 9)
        self.assertEqual(result["posterior"], {})
        self.assertTrue((Path(result["registro"]) / "entrega/inspect_run.py").is_file())

    def test_cli_incompatible_no_reserva_ni_anuncia_invocacion(self):
        self.configure(incompatible=True)
        messages = []
        result = controller.run_project(self.root, progress=messages.append)
        self.assertEqual(result["codigo_salida"], 3, result)
        self.assertFalse(result["reserva_invocacion"])
        self.assertEqual(self.calls_read(), [])
        self.assertFalse(any("iniciando Codex" in message for message in messages))

    def test_timeout_del_agente_conserva_eventos_y_no_evalua(self):
        self.configure(block=True)
        with patch.object(controller, "AGENT_TIMEOUT", 0.2):
            result = self.run_project()
        self.assertEqual(result["codigo_salida"], 4, result)
        self.assertEqual(result["posterior"], {})
        self.assertEqual(len(self.calls_read()), 1)
        self.assertIn("evento_simulado", (Path(result["registro"]) / "agente/eventos.jsonl").read_text())

    def test_timeout_de_aceptacion_no_invoca_agente(self):
        with patch.object(controller, "ACCEPTANCE_TIMEOUT", 0.001):
            result = self.run_project()
        self.assertEqual(result["codigo_salida"], 4, result)
        self.assertEqual(self.calls_read(), [])

    def test_interrupcion_cli_conserva_proceso_y_candidato(self):
        self.configure(block=True)
        with subprocess.Popen(self.cli_command(), env=self.cli_env(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            try:
                deadline = time.monotonic() + 10
                while not self.calls.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(self.calls.exists())
                process.send_signal(signal.SIGINT)
                out, err = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 7, (out, err))
                self.assertIn(b"Detenido:", err)
                self.assertNotIn(b"posterior:", err)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
        log = next(path for path in (self.root / "runs").iterdir() if path.name != "historico")
        result = json.loads((log / "resultado.json").read_text())
        self.assertEqual(result["agente"]["proceso"]["estado"], "interrumpida")
        self.assertEqual(result["agente"]["invocaciones"], 1)
        self.assertTrue((log / "entrega/inspect_run.py").is_file())
        with self.assertRaises(ProcessLookupError):
            os.kill(self.calls_read()[0]["pid"], 0)

    def test_cambios_no_permitidos_incluyen_altas_bajas_modos_y_enlaces(self):
        for mutation in ("add", "empty_dir", "delete", "tests", "mode", "link"):
            with self.subTest(cambio=mutation):
                self.configure(mutation=mutation)
                result = self.run_project()
                self.assertEqual(result["codigo_salida"], 5, result)
                self.assertFalse(result["integridad"]["alcance_respetado"])
                self.assertEqual(result["posterior"], {})
                self.assertTrue((Path(result["registro"]) / "entrega/cambios.json").is_file())

    def test_referencia_y_original_fuera_del_workspace_protegidos(self):
        self.configure(mutation="reference")
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 5, result)
        self.assertFalse(result["integridad"]["referencia_intacta"])
        self.configure(mutate_original=str(self.root / "inspect_run.py"))
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 5, result)
        self.assertFalse(result["integridad"]["original_intacto"])

    def test_informes_iniciales_no_pueden_ser_alterados_por_el_agente(self):
        self.configure(mutation="record")
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 5, result)
        self.assertFalse(result["integridad"]["registros_intactos"])
        self.assertEqual(result["posterior"], {})

    def test_codigo_uno_sin_informe_no_es_asercion(self):
        self.write(controller.ACCEPTANCE, ACCEPTANCE.replace("result = unittest.TextTestRunner", "sys.exit(1)\nresult = unittest.TextTestRunner"))
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(result["inicial"]["aceptacion"]["clasificacion"], "no_acreditada")
        self.assertEqual(self.calls_read(), [])

    def test_error_en_pruebas_no_es_asercion(self):
        self.write(controller.ACCEPTANCE, ACCEPTANCE.replace("self.assertEqual(self.call().returncode, 0)", "raise RuntimeError('error sintético')"))
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 3, result)
        self.assertEqual(result["inicial"]["aceptacion"]["clasificacion"], "error_pruebas")
        self.assertEqual(self.calls_read(), [])

    def test_omision_no_acredita_suite_completa(self):
        self.write(controller.ACCEPTANCE, ACCEPTANCE.replace("    def test_basico", "    @unittest.skip('omisión sintética')\n    def test_basico"))
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(self.calls_read(), [])

    def test_alteracion_durante_evaluacion_no_se_acepta(self):
        self.configure(candidate="from pathlib import Path\nPath('support.txt').write_text('alterado')\nprint('ENTREGA')\n")
        result = self.run_project()
        self.assertEqual(result["codigo_salida"], 5, result)
        self.assertFalse(result["posterior"]["aceptacion"]["workspace_intacto"])

    def test_cli_progreso_canales_y_argumentos(self):
        completed = subprocess.run(self.cli_command(), env=self.cli_env(), capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stderr.splitlines()
        self.assertEqual(lines[0], "Preparando proyecto base y congelando contrato y pruebas.")
        self.assertEqual(lines[1:3], ["Evaluación inicial: aceptacion.", "Evaluación inicial: regresion."])
        self.assertIn("Desarrollo 1/1: iniciando Codex", lines[3])
        self.assertEqual(lines[-2:], ["Evaluación posterior: aceptacion.", "Evaluación posterior: regresion."])
        self.assertIn("supera las comprobaciones disponibles", completed.stdout)
        self.assertIn("Registro:", completed.stdout)
        self.assertNotIn("evento_simulado", completed.stdout + completed.stderr)
        for args in ([], ["otra-tarea"]):
            invalid = subprocess.run(self.cli_command()[:-1] + args, env=self.cli_env(), capture_output=True, text=True, timeout=5)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, "")


if __name__ == "__main__":
    unittest.main()

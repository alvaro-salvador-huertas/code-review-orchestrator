"""Repositorios y marcadores sintéticos; CLI de agentes simulada, sin modelos."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import orchestrate_project as controller
import project_flow
import project_task_config
import repair_project
import review_case
from process_environment import process_environment


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ("orchestrate_project.py", "project_flow.py", "repair_project.py", "review_project.py",
          "project_task_config.py", "project_flow_runner.py", "project_test_inventory.py", "review_case.py",
          "inspect_project.py", "export_runs.py", *project_flow.SUPPORT)
ACCEPTANCE = '''import argparse
from pathlib import Path
import sys, unittest
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
args = p.parse_args()
class Acceptance(unittest.TestCase):
    def test_marker(self):
        target = args.project / EDITABLE
        self.assertTrue(target.is_file() and not target.is_symlink(), 'Falta marcador sintético')
        self.assertEqual(target.read_text(), EXPECTED)
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
sys.exit(0 if result.wasSuccessful() else 1)
'''


class ConfigurableProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tareas-sinteticas-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.root = self.temporary / "proyecto con espacios"
        self.root.mkdir()
        self.write("alpha.py", "# PENDIENTE alfa: solo un marcador\n")
        self.write("referencia.txt", "Base sintética inmutable\n")
        self.write("tests/test_base.py", "import unittest\nfrom pathlib import Path\n"
            "class Base(unittest.TestCase):\n    def test_reference(self):\n"
            "        self.assertEqual((Path(__file__).parents[1]/'referencia.txt').read_text(), 'Base sintética inmutable\\n')\n")
        self.write("parent.py", "import unittest\nclass Parent(unittest.TestCase):\n    def test_inherited(self): self.assertTrue(True)\n")
        self.write("tests/test_child.py", "import parent\nclass Child(parent.Parent):\n    def test_own(self): self.assertTrue(True)\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Base sintética")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        for name in ENGINE:
            self.write(name, (ROOT / name).read_text())
        self.configs = {}
        for task, editable, initial in (("marcador-alfa", "alpha.py", "existente"),
                                        ("marcador-beta", "beta.py", "ausente")):
            config = {"version": 1, "identificador": task, "commit_base": self.base,
                "contrato": f"tasks/{task}.md", "archivo_editable": editable, "estado_inicial": initial,
                "evaluador_aceptacion": f"evals/{task}/evaluar.py",
                "prompts": {"desarrollador": f"prompts/{task}-d.md", "revisor": f"prompts/{task}-r.md"},
                "referencias": [f"docs/{task}.md"],
                "limites_segundos": {"desarrollador": 5, "revisor": 5, "aceptacion": 5,
                                     "regresion": 5, "inventario": 5, "consulta_cli": 10}}
            self.write(config["contrato"], f"# Contrato sintético {task}\nBase: `{self.base}`\nSolo {editable}.\n")
            self.write(config["evaluador_aceptacion"], ACCEPTANCE.replace("EDITABLE", repr(editable)).replace("EXPECTED", repr(self.good(task))))
            for role, name in config["prompts"].items():
                self.write(name, f"Instrucciones sintéticas {task} para {role}; no funcionalidad real.\n")
            self.write(config["referencias"][0], f"Referencia exclusiva de {task}\n")
            self.configs[task] = config
            self.save_config(task)
        self.settings = self.temporary / "opciones.json"
        self.calls = self.temporary / "llamadas.jsonl"
        self.fake = self.temporary / "codex"
        self.configure()
        self.addCleanup(patch.stopall)
        patch.object(repair_project, "CODEX_EXECUTABLE", str(self.fake)).start()
        patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)).start()

    def write(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def git(self, *args):
        with process_environment("evaluation") as environment:
            return subprocess.run(["git", "-C", str(self.root), *args], env=environment,
                                  capture_output=True, check=True, timeout=10).stdout

    @staticmethod
    def good(task):
        return f"# ACEPTADO {task}: solo un marcador sintético\n"

    def config_path(self, task):
        return f"tasks/config/{task}.json"

    def save_config(self, task):
        self.write(self.config_path(task), json.dumps(self.configs[task]))

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import hashlib, json
from pathlib import Path
import sys, time
args = sys.argv[1:]
if args == ['--version']: print('CLI simulada'); sys.exit(0)
if args == ['exec', '--help']:
    print('--config --sandbox --cd --skip-git-repo-check --json --output-last-message --ephemeral read-only --output-schema')
    sys.exit(0)
options = json.loads(Path({str(self.settings)!r}).read_text())
role = 'revisor' if args[args.index('--sandbox')+1] == 'read-only' else 'desarrollador'
workspace = Path.cwd()
prompt = sys.stdin.read()
if role == 'desarrollador':
    config = json.JSONDecoder().raw_decode(prompt.split('CONFIGURACION CONGELADA\\n')[1])[0]
else:
    config = json.loads((workspace/'configuracion_tarea.json').read_text())
task = config['identificador']
candidate = workspace/config['archivo_editable']
starting = candidate.read_bytes() if candidate.is_file() else None
calls_path = Path({str(self.calls)!r})
calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
number = sum(c['rol'] == role and c['tarea'] == task for c in calls)
settings = options.get(role, [{{}}])
setting = settings[min(number, len(settings)-1)]
final = Path(args[args.index('--output-last-message')+1])
if role == 'desarrollador':
    run = final.parents[4]
    summary = json.loads((run/'resultado.json').read_text())
    assert summary['invocaciones'][role] == number+1
    assert (run/'reservas'/f'{{number+1}}-{{role}}'/'reserva.json').is_file()
with calls_path.open('a') as output:
    output.write(json.dumps({{'rol': role, 'tarea': task, 'partida': starting.decode() if starting is not None else None,
        'workspace': str(workspace), 'prompt': prompt,
        'archivos': sorted(str(p.relative_to(workspace)) for p in workspace.rglob('*') if p.is_file())}})+'\\n')
if role == 'desarrollador':
    if not setting.get('absent'):
        candidate.write_text(setting.get('candidate', f'# ACEPTADO {{task}}: solo un marcador sintético\\n'))
        candidate.chmod(0o644)
    final.write_text('Explicación del desarrollador simulado')
else:
    final.write_text(setting.get('raw', json.dumps(setting.get('verdict',
        {{'decision':'aprobar','resumen':'Aprobación sintética','hallazgos':[]}}))))
mutation = setting.get('mutation')
if mutation == 'extra': (workspace/'intruso.txt').write_text('fuera de alcance')
if mutation == 'reference': (run/'referencia/tarea.json').write_text('{{}}')
if mutation == 'authority': (run/'referencia/autoridades'/config['evaluador_aceptacion']).write_text('alterado')
if mutation == 'original': (Path({str(self.root)!r})/'tasks/config'/f'{{task}}.json').write_text('{{}}')
if setting.get('block'): time.sleep(20)
sys.exit(setting.get('exit_code', 0))
''')
        self.fake.chmod(0o755)

    def calls_read(self):
        return [json.loads(row) for row in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def run_flow(self, task="marcador-beta", attempts=2):
        before = repair_project.tree_state(self.root, filter_local=True)
        result = controller.run_orchestration(root=self.root, max_attempts=attempts, task_config_path=self.config_path(task))
        self.assertEqual(result, json.loads((Path(result["registro"])/"resultado.json").read_text()))
        self.assertEqual(result["incorporacion"], "no_realizada")
        if result["integridad"].get("original_intacto") is not False:
            self.assertEqual(repair_project.tree_state(self.root, filter_local=True), before)
        self.assertEqual((self.root/"alpha.py").read_text(), "# PENDIENTE alfa: solo un marcador\n")
        self.assertFalse((self.root/"beta.py").exists())
        return result

    def cli(self, script, *args):
        with process_environment("evaluation") as environment:
            environment["PATH"] = str(self.temporary) + os.pathsep + environment["PATH"]
            return subprocess.run([str(Path(sys.executable).resolve()), "-B", str(self.root/script), *map(str, args)],
                cwd=self.root, env=environment, capture_output=True, timeout=30)

    def test_two_tasks_same_engine_existing_and_absent(self):
        before = {name: hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in ENGINE}
        for task, config in self.configs.items():
            with self.subTest(task=task):
                result = self.run_flow(task)
                self.assertEqual(result["codigo_salida"], 0, result)
                self.assertEqual(result["tipo"], "orquestacion_configurable_v1")
                self.assertEqual(result["invocaciones"], {"desarrollador": 1, "revisor": 1, "total": 2})
                frozen = Path(result["registro"])/"referencia"
                self.assertEqual(json.loads((frozen/"tarea.json").read_text()), config)
                self.assertEqual(result["procedencia"]["pruebas_esperadas"]["regresion"],
                    ["test_base.Base.test_reference", "test_child.Child.test_inherited", "test_child.Child.test_own"])
                entry = result["intentos"][0]
                self.assertEqual(set(entry["evaluaciones"]), {"aceptacion", "regresion"})
                self.assertEqual(entry["revision"]["dictamen_modelo"]["decision"], "aprobar")
                delivery = Path(entry["registro"])
                name = config["archivo_editable"]
                expected = json.loads((delivery / "entrega/workspace_despues.json").read_text())[name]
                self.assertEqual(entry["revision"]["materiales_sha256"][name], expected)
                self.assertEqual(entry["revision"]["evidencia_sha256"]["evidencia/entrega/" + name], expected)
                self.assertEqual((delivery/"entrega"/config["archivo_editable"]).read_text(), self.good(task))
                self.assertEqual((delivery/"entrega/partida.py").exists(), config["estado_inicial"] == "existente")
                calls = [c for c in self.calls_read() if c["tarea"] == task]
                self.assertNotEqual(calls[0]["workspace"], entry["evaluaciones"]["aceptacion"]["proceso"]["directorio_trabajo"])
                self.assertIn("referencias/"+config["referencias"][0], calls[1]["archivos"])
                other = "marcador-beta" if task == "marcador-alfa" else "marcador-alfa"
                self.assertNotIn(other, calls[0]["prompt"])
                self.assertFalse(any(other in name for name in calls[1]["archivos"]))
                self.assertEqual(before, {name: hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in ENGINE})

    def test_correction_after_acceptance_failure_continuity(self):
        for task in self.configs:
            with self.subTest(task=task):
                bad = "# Corrección aún insuficiente\n"
                self.configure(desarrollador=[{"candidate": bad}, {}])
                result = self.run_flow(task)
                self.assertEqual(result["codigo_salida"], 0, result)
                self.assertEqual(result["invocaciones"], {"desarrollador": 2, "revisor": 1, "total": 3})
                calls = [c for c in self.calls_read() if c["tarea"] == task]
                self.assertEqual([c["rol"] for c in calls], ["desarrollador", "desarrollador", "revisor"])
                self.assertEqual(calls[1]["partida"], bad)
                self.assertEqual(result["intentos"][0]["evaluaciones"]["aceptacion"]["clasificacion"], "fallos_asercion")
                self.assertIn("corregir", [t["accion"] for t in result["intentos"][0]["transiciones"]])

    def test_budget_stops_without_extra_invocation(self):
        self.configure(desarrollador=[{"candidate": "# Sigue pendiente\n"}])
        result = self.run_flow(attempts=2)
        self.assertEqual((result["estado"], result["codigo_salida"]), ("intentos_agotados", 1))
        self.assertEqual(len(self.calls_read()), 2)
        self.assertEqual(result["invocaciones"]["revisor"], 0)

    def test_frozen_selection_does_not_reread_original_config(self):
        selections = []
        original = project_task_config.load_task
        def capture(*args):
            selection = original(*args)
            selections.append(selection)
            return selection
        with patch.object(project_task_config, "load_task", side_effect=capture):
            result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(len(selections), 1)
        (self.root/self.config_path("marcador-beta")).unlink()
        record, _ = project_flow.validate_delivery(result["intentos"][0]["registro"], self.root, task=selections[0])
        self.assertEqual(record["tarea"], "marcador-beta")
        with self.assertRaises(ValueError):
            project_flow.validate_delivery(result["intentos"][0]["registro"], self.root)

    def test_invalid_configs_before_agent(self):
        original = copy.deepcopy(self.configs["marcador-beta"])
        variants = [dict(original, version=True), dict(original, shell="echo peligro"),
                    dict(original, identificador="../escape"), dict(original, identificador="export-csv"),
                    dict(original, commit_base="main"), dict(original, archivo_editable="../beta.py"),
                    dict(original, archivo_editable="src/beta.py"), dict(original, estado_inicial="existente"),
                    dict(original, contrato="/tmp/contrato.md"), dict(original, referencias=[".env"]),
                    dict(original, referencias=["docs/../referencia.txt"]),
                    dict(original, prompts={**original["prompts"], "opciones": {"permisos": "all"}}),
                    dict(original, limites_segundos={**original["limites_segundos"], "desarrollador": True}),
                    dict(original, limites_segundos={**original["limites_segundos"], "regresion": 601})]
        for data in variants:
            with self.subTest(data=data):
                self.write(self.config_path("marcador-beta"), json.dumps(data))
                with self.assertRaises((ValueError, OSError, subprocess.SubprocessError)):
                    controller.run_orchestration(root=self.root, task_config_path=self.config_path("marcador-beta"))
        self.write(self.config_path("marcador-beta"), '{"version":1,"version":1}')
        with self.assertRaises(ValueError):
            project_task_config.load_task(self.root, self.config_path("marcador-beta"))
        self.assertEqual(self.calls_read(), [])
        self.assertFalse((self.root/"runs").exists())

    def test_links_and_contract_base_mismatch_rejected(self):
        config = self.configs["marcador-beta"]
        target = self.root/config["referencias"][0]
        data = target.read_bytes()
        target.unlink()
        target.symlink_to(self.root/"referencia.txt")
        with self.assertRaises(ValueError):
            project_task_config.load_task(self.root, self.config_path("marcador-beta"))
        target.unlink()
        target.write_bytes(data)
        source = self.root/config["contrato"]
        source.write_text(source.read_text().replace(self.base, "0"*40))
        with self.assertRaises(ValueError):
            project_task_config.load_task(self.root, self.config_path("marcador-beta"))
        self.assertEqual(self.calls_read(), [])

    def test_material_tampering_and_out_of_scope_stop(self):
        for mutation in ("reference", "authority", "extra"):
            with self.subTest(mutation=mutation):
                self.calls.unlink(missing_ok=True)
                self.configure(desarrollador=[{"mutation": mutation}])
                result = self.run_flow()
                self.assertEqual(result["codigo_salida"], 6, result)
                self.assertEqual([c["rol"] for c in self.calls_read()], ["desarrollador"])

    def test_original_config_mutation_does_not_select_other_task(self):
        self.configure(desarrollador=[{"mutation": "original"}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(result["configuracion"]["identificador"], "marcador-beta")
        self.assertEqual([c["rol"] for c in self.calls_read()], ["desarrollador"])

    def test_technical_failure_and_timeout_do_not_retry(self):
        config = self.configs["marcador-beta"]
        config["limites_segundos"]["desarrollador"] = 1
        self.save_config("marcador-beta")
        for options, expected in (({"exit_code": 1}, 3), ({"block": True}, 4)):
            with self.subTest(options=options):
                self.calls.unlink(missing_ok=True)
                self.configure(desarrollador=[options])
                result = self.run_flow()
                self.assertEqual(result["codigo_salida"], expected, result)
                self.assertEqual(len(result["intentos"]), 1)
                self.assertEqual([c["rol"] for c in self.calls_read()], ["desarrollador"])

    def test_invalid_reviewer_never_approves(self):
        self.configure(revisor=[{"raw": '{"decision":"aprobar"}'}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 5, result)
        self.assertFalse(result["lista_para_revision_humana"])
        self.assertEqual(len(self.calls_read()), 2)

    def test_initial_acceptance_success_error_or_incomplete_does_not_authorize(self):
        config = self.configs["marcador-beta"]
        for body, expected in ((ACCEPTANCE.replace("self.assertTrue(target.is_file() and not target.is_symlink(), 'Falta marcador sintético')", "pass")
                               .replace("self.assertEqual(target.read_text(), EXPECTED)", "self.assertTrue(True)"), 7),
                              (ACCEPTANCE.replace("self.assertTrue(target.is_file()", "raise RuntimeError('error sintético')\n        self.assertTrue(target.is_file()"), 3),
                              ("# No ejecuta unittest\n", 7)):
            with self.subTest(expected=expected):
                self.write(config["evaluador_aceptacion"], body.replace("EDITABLE", repr(config["archivo_editable"])).replace("EXPECTED", repr(self.good("marcador-beta"))))
                result = self.run_flow()
                self.assertEqual(result["codigo_salida"], expected, result)
                self.assertEqual(result["intentos"], [])
        self.assertEqual(self.calls_read(), [])

    def test_cli_selection_and_new_summary_export(self):
        for args in ((), ("export-csv", "--task-config", self.config_path("marcador-beta")),
                     ("--task-config", self.config_path("marcador-alfa"), "--task-config", self.config_path("marcador-beta")),
                     ("--task-config", "../escape.json"), ("--task-config", self.config_path("marcador-beta"), "--max-attempts", "3")):
            completed = self.cli("orchestrate_project.py", *args)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(completed.stdout, b"")
        self.assertEqual(self.calls_read(), [])
        completed = self.cli("orchestrate_project.py", "--task-config", self.config_path("marcador-beta"), "--max-attempts", "1")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        run = next(p for p in (self.root/"runs").iterdir() if "_orchestrate_" in p.name)
        query = self.cli("inspect_project.py", "--run", run, "--format", "json")
        self.assertEqual((query.returncode, query.stderr), (0, b""))
        result = json.loads(query.stdout)
        self.assertEqual(result["ejecucion"]["caso"], "marcador-beta")
        query_file = self.temporary/"consulta.json"
        query_file.write_bytes(query.stdout)
        exported = self.cli("export_runs.py", query_file)
        self.assertEqual((exported.returncode, exported.stderr), (0, b""))
        self.assertIn(b'"marcador-beta"', exported.stdout)

    def test_symlink_directory_and_nonexistent_commit_rejected(self):
        config = self.configs["marcador-beta"]
        source = self.root / "docs"
        source.rename(self.root / "docs-original")
        source.symlink_to(self.root / "docs-original", target_is_directory=True)
        with self.assertRaises(ValueError):
            project_task_config.load_task(self.root, self.config_path("marcador-beta"))
        source.unlink()
        (self.root / "docs-original").rename(source)
        config["commit_base"] = "f" * 40
        self.save_config("marcador-beta")
        self.write(config["contrato"], "# Sintético\nBase: `" + "f" * 40 + "`\n")
        with self.assertRaises(subprocess.SubprocessError):
            project_task_config.load_task(self.root, self.config_path("marcador-beta"))
        self.assertEqual(self.calls_read(), [])

    def test_initial_regression_failure_does_not_authorize(self):
        self.write("tests/test_base.py", "import unittest\nclass Base(unittest.TestCase):\n"
                   "    def test_reference(self): self.assertTrue(False, 'Fallo de regresión sintético')\n")
        self.git("add", "tests/test_base.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Regresión sintética fallida")
        base = self.git("rev-parse", "HEAD").decode().strip()
        config = self.configs["marcador-beta"]
        config["commit_base"] = base
        self.save_config("marcador-beta")
        self.write(config["contrato"], f"# Sintético\nBase: `{base}`\n")
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 7, result)
        self.assertEqual(result["inicial"]["regresion"]["clasificacion"], "fallos_asercion")
        self.assertEqual(self.calls_read(), [])

    def test_reviewer_changes_can_use_second_attempt(self):
        change = {"decision": "solicitar_cambios", "resumen": "Cambio sintético", "hallazgos": [
            {"archivo": "beta.py", "linea": 1, "requisito": "Contrato sintético",
             "explicacion": "Comprobar el marcador", "ejemplo": "Observación simulada"}]}
        self.configure(revisor=[{"verdict": change}, {}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["invocaciones"], {"desarrollador": 2, "revisor": 2, "total": 4})
        self.assertEqual(self.calls_read()[2]["partida"], self.good("marcador-beta"))

    def test_reviewer_timeout_does_not_retry(self):
        self.configs["marcador-beta"]["limites_segundos"]["revisor"] = 1
        self.save_config("marcador-beta")
        self.configure(revisor=[{"block": True}])
        result = self.run_flow()
        self.assertEqual((result["codigo_salida"], result["estado"]), (4, "tiempo_agotado_revisor"), result)
        self.assertEqual(len(self.calls_read()), 2)

    def test_invalid_acceptance_syntax_is_recorded_without_agents(self):
        self.write(self.configs["marcador-beta"]["evaluador_aceptacion"], "def incompleta(\n")
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 7, result)
        self.assertEqual(self.calls_read(), [])

    def test_invalid_candidate_syntax_cannot_escape_review(self):
        invalid = "def incompleta(\n"
        self.configure(desarrollador=[{"candidate": invalid}])
        config = self.configs["marcador-beta"]
        self.write(config["evaluador_aceptacion"], ACCEPTANCE.replace("EDITABLE", repr("beta.py")).replace("EXPECTED", repr(invalid)))
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 7, result)
        self.assertFalse(result["lista_para_revision_humana"])
        self.assertEqual([c["rol"] for c in self.calls_read()], ["desarrollador"])

    def test_excessively_nested_configuration_is_argument_error(self):
        self.write(self.config_path("marcador-beta"), '[' * 2000 + '0' + ']' * 2000)
        result = self.cli("orchestrate_project.py", "--task-config", self.config_path("marcador-beta"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(self.calls_read(), [])


if __name__ == "__main__":
    unittest.main()

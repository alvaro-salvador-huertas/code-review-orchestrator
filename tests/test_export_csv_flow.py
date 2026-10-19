"""Mecanismo CSV con agentes simulados y marcadores; no implementa el exportador."""

import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from case_evidence import digest
import orchestrate_project as controller
import project_flow
import repair_project
import review_case
import review_project
from repair_case import write_json
import test_repair_project as fixture


ROOT = Path(__file__).resolve().parents[1]
GOOD = "# fixture correcto: no exporta CSV\n"
BAD = "# fixture incorrecto: no exporta CSV\n"
APPROVE = {"decision": "aprobar", "resumen": "Aprobación simulada del mecanismo", "hallazgos": []}
CHANGE = {"decision": "solicitar_cambios", "resumen": "Cambio simulado", "hallazgos": [
    {"archivo": "export_runs.py", "linea": 1, "requisito": "Contrato sintético",
     "explicacion": "OBSERVACION_SIMULADA_NO_CONFIRMADA", "ejemplo": "Contrastar el marcador"}]}
ACCEPTANCE = '''import argparse
from pathlib import Path
import sys, unittest
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
args = p.parse_args()
class Acceptance(unittest.TestCase):
    def setUp(self):
        self.script = args.project / 'export_runs.py'
        self.assertTrue(self.script.is_file() and not self.script.is_symlink(),
                        'Funcionalidad pendiente: falta export_runs.py como archivo regular; CLI no invocada')
    def test_marker(self):
        self.assertTrue(self.script.read_text().startswith('# fixture correcto'))
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
sys.exit(0 if result.wasSuccessful() else 1)
'''


class ExportCsvFlowTests(unittest.TestCase):
    write = fixture.TestRepairProject.write
    git = fixture.TestRepairProject.git
    commit_base = fixture.TestRepairProject.commit_base
    calls_read = fixture.TestRepairProject.calls_read
    cli_env = fixture.TestRepairProject.cli_env

    def setUp(self):
        fixture.TestRepairProject.setUp(self)
        self.write("inventory_parent.py", "import unittest\nclass Parent(unittest.TestCase):\n"
                   "    def test_inherited(self): self.assertTrue(True)\n")
        self.write("tests/test_inherited.py", "import inventory_parent\n"
                   "class Child(inventory_parent.Parent):\n    def test_own(self): self.assertTrue(True)\n")
        self.git("add", "inventory_parent.py", "tests/test_inherited.py")
        self.commit_base()
        self.config = project_flow.task_config("export-csv")
        for name in (*project_flow.SUPPORT, "orchestrate_project.py", "project_flow.py", "project_flow_runner.py",
                     "project_test_inventory.py", "review_case.py", "review_project.py",
                     self.config["desarrollo"], self.config["revision"]):
            self.write(name, (ROOT / name).read_text())
        self.write(self.config["suites"]["aceptacion"], ACCEPTANCE)
        self.select_base()
        patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)).start()

    def select_base(self):
        self.write(self.config["contrato"], f"# Contrato de marcador simulado, no CSV real\nBase: `{self.base}`\n")
        # Solo la copia del controlador del fixture admite su commit sintético.
        self.write("project_flow.py", (ROOT / "project_flow.py").read_text().replace(project_flow.CSV_BASE, self.base))

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import hashlib, json, os
from pathlib import Path
import sys, time
args = sys.argv[1:]
options = json.loads(Path({str(self.settings)!r}).read_text())
if args == ['--version']: print('CLI simulada'); sys.exit(0)
if args == ['exec', '--help']: print({(fixture.HELP + ' read-only --output-schema')!r}); sys.exit(0)
role = 'revisor' if args[args.index('--sandbox')+1] == 'read-only' else 'desarrollador'
calls_path = Path({str(self.calls)!r})
calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
number = sum(c['rol'] == role for c in calls)
settings = options.get(role, [{{}}])
setting = settings[min(number, len(settings)-1)]
workspace = Path.cwd()
candidate = workspace/'export_runs.py'
starting = candidate.read_bytes() if candidate.is_file() else None
prompt = sys.stdin.read()
final = Path(args[args.index('--output-last-message')+1])
if role == 'desarrollador':
    run = final.parents[4]
    summary = json.loads((run/'resultado.json').read_text())
    assert summary['invocaciones'][role] == number+1
    assert (run/'reservas'/f'{{number+1}}-{{role}}'/'reserva.json').is_file()
with calls_path.open('a') as output:
    output.write(json.dumps({{'rol': role, 'workspace': str(workspace), 'prompt': prompt,
        'partida_sha256': hashlib.sha256(starting).hexdigest() if starting is not None else None,
        'archivos': sorted(str(p.relative_to(workspace)) for p in workspace.rglob('*') if p.is_file())}})+'\\n')
print('PARCIAL_SIMULADO', flush=True)
if role == 'desarrollador':
    if not setting.get('absent'):
        candidate.write_text(setting.get('candidate', {GOOD!r}))
        candidate.chmod(0o644)
    final.write_text('EXPLICACION_DESARROLLADOR_NO_REVISAR')
else:
    final.write_text(setting.get('raw', json.dumps(setting.get('verdict', {APPROVE!r}))))
mutation = setting.get('mutation')
if mutation == 'extra': (workspace/'intruso.txt').write_text('extra')
if mutation == 'tests': (workspace/'tests/test_fixture.py').write_text('alterado')
if mutation == 'mode': candidate.chmod(0o755)
if mutation == 'link':
    candidate.unlink(); candidate.symlink_to(workspace/'support.txt')
if mutation == 'fifo':
    candidate.unlink(); os.mkfifo(candidate)
if mutation == 'reference': (run/'referencia/inventario/informe.json').write_text('{{}}')
if setting.get('block'): time.sleep(30)
sys.exit(setting.get('exit_code', 0))
''')
        self.fake.chmod(0o755)

    def run_flow(self, attempts=2):
        with patch.object(project_flow, "CSV_BASE", self.base):
            result = controller.run_orchestration("export-csv", self.root, attempts)
        self.assertEqual(result, json.loads((Path(result["registro"]) / "resultado.json").read_text()))
        self.assertEqual(result["incorporacion"], "no_realizada")
        self.assertFalse((self.root / "export_runs.py").exists())
        return result

    def validate(self, path, **kwargs):
        with patch.object(project_flow, "CSV_BASE", self.base):
            return project_flow.validate_delivery(path, self.root, **kwargs)

    def test_configuracion_dos_tareas_y_presupuestos(self):
        cfg = project_flow.task_config("export-csv")
        self.assertEqual(cfg["base"], "4cda45e2ccda3f7091f8ab15e55087516c09bec0")
        self.assertEqual(cfg["limites"], {"desarrollador": 300, "revisor": 300, "consulta_cli": 10,
                                        "aceptacion": 60, "regresion": 300, "inventario": 30})
        self.assertEqual(set(cfg["suites"]), {"aceptacion", "regresion"})
        old = project_flow.task_config("inspect-json")
        self.assertEqual(old["suites"], project_flow.SUITES)
        self.assertEqual(old["limites"], project_flow.LIMITS)
        self.assertEqual((old["limites"]["revisor"], old["limites"]["regresion"]), (180, 180))
        with self.assertRaises(ValueError):
            project_flow.task_config("inventada")

    def test_creacion_aprobacion_inventario_y_original_intacto(self):
        before = repair_project.tree_state(self.root, filter_local=True)
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["tipo"], "orquestacion_export_csv_v1")
        self.assertEqual(result["invocaciones"], {"desarrollador": 1, "revisor": 1, "total": 2})
        self.assertEqual(repair_project.tree_state(self.root, filter_local=True), before)
        entry = result["intentos"][0]
        self.assertEqual(entry["partida"], project_flow.file_identity(None))
        path = Path(entry["registro"])
        self.assertFalse((path / "entrega/partida.py").exists())
        self.assertTrue((path / "entrega/candidato.diff").read_text().startswith("--- /dev/null\n+++ b/export_runs.py\n"))
        self.assertEqual(set(entry["evaluaciones"]), {"aceptacion", "regresion"})
        self.assertEqual(entry["revision"]["revisor"]["limite_segundos"], 300)
        self.assertEqual(entry["desarrollo"]["agente"]["proceso"]["limite_segundos"], 300)
        self.assertEqual(entry["evaluaciones"]["regresion"]["proceso"]["limite_segundos"], 300)
        expected = result["procedencia"]["pruebas_esperadas"]["regresion"]
        self.assertEqual(expected, ["test_fixture.Regression.test_compatible", "test_inherited.Child.test_inherited",
                                    "test_inherited.Child.test_own"])
        self.validate(path)
        calls = self.calls_read()
        self.assertIsNone(calls[0]["partida_sha256"])
        self.assertNotIn("export_runs.py", calls[0]["archivos"])
        self.assertNotEqual(calls[0]["workspace"], entry["evaluaciones"]["aceptacion"]["proceso"]["directorio_trabajo"])
        review_files = calls[1]["archivos"]
        self.assertIn("esquema_003.md", review_files)
        self.assertIn("ausencia_original.json", review_files)
        self.assertFalse(any("stderr" in name or "eventos" in name for name in review_files))
        material = Path(entry["revision"]["registro"]) / "materiales"
        schema = json.loads((material / "respuesta.schema.json").read_text())
        self.assertEqual(schema["properties"]["hallazgos"]["items"]["properties"]["archivo"]["enum"], ["export_runs.py"])

    def test_fallos_correccion_y_continuidad_exacta(self):
        self.configure(desarrollador=[{"candidate": BAD}, {}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        first, second = result["intentos"]
        self.assertIsNone(first["revision"])
        self.assertEqual(result["invocaciones"], {"desarrollador": 2, "revisor": 1, "total": 3})
        self.assertEqual(first["candidato_sha256"], second["partida_sha256"])
        self.assertEqual(first["candidato_sha256"], self.calls_read()[1]["partida_sha256"])
        path = Path(second["registro"])
        self.assertEqual((path / "entrega/partida.py").read_text(), BAD)
        self.assertTrue((path / "entrega/anterior.diff").read_text().startswith("--- a/export_runs.py"))
        self.validate(path)

    def test_cambios_revisor_y_segunda_revision_dentro_del_presupuesto(self):
        self.configure(desarrollador=[{}, {"candidate": GOOD + "# ajuste simulado\n"}],
                       revisor=[{"verdict": CHANGE}, {}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["invocaciones"], {"desarrollador": 2, "revisor": 2, "total": 4})
        self.assertIn("OBSERVACION_SIMULADA", self.calls_read()[2]["prompt"])
        self.assertEqual(result["intentos"][0]["candidato_sha256"], result["intentos"][1]["partida_sha256"])

    def test_agotamiento_sin_tercer_intento(self):
        for attempts in (1, 2):
            with self.subTest(intentos=attempts):
                self.calls.unlink(missing_ok=True)
                self.configure(revisor=[{"verdict": CHANGE}])
                result = self.run_flow(attempts)
                self.assertEqual(result["estado"], "intentos_agotados", result)
                self.assertEqual(result["invocaciones"]["total"], attempts * 2)

    def test_entrega_invalida_no_alcanza_evaluacion_ni_revision(self):
        for settings in ({"absent": True}, *({"mutation": name} for name in ("extra", "tests", "mode", "link", "fifo"))):
            with self.subTest(variante=settings):
                self.calls.unlink(missing_ok=True)
                self.configure(desarrollador=[settings])
                result = self.run_flow()
                self.assertEqual(result["estado"], "entrega_invalida", result)
                self.assertEqual(result["invocaciones"], {"desarrollador": 1, "revisor": 0, "total": 1})
                self.assertFalse((Path(result["intentos"][0]["registro"]) / "evaluaciones").exists())

    def test_preparacion_no_acepta_diagnostico_json_historico(self):
        self.write(self.config["suites"]["aceptacion"], ACCEPTANCE.replace(project_flow.CSV_MISSING, "unrecognized arguments: --format json"))
        result = self.run_flow()
        self.assertEqual(result["estado"], "preparacion_no_autoriza", result)
        self.assertEqual(self.calls_read(), [])

    def test_regresion_inicial_fallida_no_reserva_desarrollador(self):
        self.write("tests/test_failing.py", "import unittest\nclass Failing(unittest.TestCase):\n"
                   "    def test_fail(self): self.fail('Regresión inicial sintética')\n")
        self.git("add", "tests/test_failing.py")
        self.commit_base()
        self.select_base()
        result = self.run_flow()
        self.assertEqual(result["estado"], "preparacion_no_autoriza", result)
        self.assertEqual(result["reservas"], [])
        self.assertEqual(self.calls_read(), [])

    def test_error_importacion_inventario_detiene_antes_de_evaluar(self):
        self.write("tests/test_broken.py", "import modulo_inexistente_fixture\n")
        self.git("add", "tests/test_broken.py")
        self.commit_base()
        self.select_base()
        result = self.run_flow()
        self.assertEqual(result["estado"], "evidencia_invalida", result)
        self.assertEqual(result["inicial"], {})
        self.assertEqual(self.calls_read(), [])
        self.assertTrue((Path(result["registro"]) / "referencia/inventario/stdout.txt").exists())

    def test_inventario_incompleto_o_alterado_no_autoriza(self):
        original = project_flow.run_process
        for variant in ("incompleto", "alterado", "identidades", "base"):
            def tamper(command, workspace, log, timeout, **kwargs):
                result = original(command, workspace, log, timeout, **kwargs)
                if log.name == "inventario":
                    report = json.loads((log / "stdout.txt").read_text())
                    if variant == "incompleto":
                        report["total"] += 1
                    elif variant == "alterado":
                        report["arbol_despues_sha256"] = "0" * 64
                    elif variant == "identidades":
                        report["identidades"] = sorted(["test_inventado.Clase.test_otro", *report["identidades"][1:]])
                    else:
                        (workspace / "support.txt").write_text("Base alterada durante el inventario")
                    write_json(log / "stdout.txt", report)
                return result
            with self.subTest(variante=variant), patch.object(project_flow, "run_process", side_effect=tamper):
                result = self.run_flow()
                self.assertEqual(result["codigo_salida"], 7, result)
                self.assertEqual(result["reservas"], [])
                self.assertEqual(self.calls_read(), [])

    def test_base_con_archivo_vacio_no_equivale_a_ausencia(self):
        self.write("export_runs.py", "")
        self.git("add", "export_runs.py")
        self.commit_base()
        (self.root / "export_runs.py").unlink()
        self.select_base()
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 7, result)
        self.assertIn("carecer del exportador", result["error"])
        self.assertEqual(result["reservas"], [])

    def test_timeout_preparacion_conserva_parciales_sin_agentes(self):
        original = project_flow.run_process
        for stage in ("inventario", "aceptacion"):
            def slow(command, workspace, log, timeout, **kwargs):
                if log.name == stage:
                    command = [str(Path(sys.executable).resolve()), "-B", "-c",
                               "import time; print('PREPARACION_PARCIAL', flush=True); time.sleep(20)"]
                return original(command, workspace, log, timeout, **kwargs)
            with self.subTest(etapa=stage), patch.dict(project_flow.CSV_LIMITS, {stage: 0.2}), \
                    patch.object(project_flow, "run_process", side_effect=slow):
                result = self.run_flow()
            self.assertEqual(result["codigo_salida"], 4, result)
            self.assertEqual(result["reservas"], [])
            prefix = "referencia/inventario" if stage == "inventario" else "inicial/aceptacion"
            self.assertIn("PREPARACION_PARCIAL", (Path(result["registro"]) / prefix / "stdout.txt").read_text())

    def test_reserva_no_persistida_no_se_disfraza_de_entrega_ausente(self):
        original = controller.atomic_json
        def fail(path, data):
            if path.name == "reserva.json":
                raise OSError("Reserva no persistida")
            return original(path, data)
        with patch.object(controller, "atomic_json", side_effect=fail):
            result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 8, result)
        self.assertEqual(result["invocaciones"]["total"], 0)
        self.assertEqual(self.calls_read(), [])

    def test_error_tecnico_posterior_detiene_y_conserva_evidencia(self):
        self.write(self.config["suites"]["aceptacion"], ACCEPTANCE.replace(
            "self.assertTrue(self.script.read_text().startswith('# fixture correcto'))", "raise RuntimeError('Fallo técnico simulado')"))
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 3, result)
        self.assertEqual(result["invocaciones"]["total"], 1)
        self.assertIn("Fallo técnico", (Path(result["intentos"][0]["registro"]) / "evaluaciones/aceptacion/stderr.txt").read_text())

    def test_fallo_tecnico_y_timeout_de_agentes_sin_reintento(self):
        for role in ("desarrollador", "revisor"):
            for settings, code in (({"exit_code": 17}, 3), ({"block": True}, 4)):
                with self.subTest(rol=role, variante=settings):
                    self.calls.unlink(missing_ok=True)
                    self.configure(**{role: [settings]})
                    with patch.dict(project_flow.CSV_LIMITS, {role: 0.2 if settings.get("block") else 300}):
                        result = self.run_flow()
                    self.assertEqual(result["codigo_salida"], code, result)
                    self.assertEqual(len(result["intentos"]), 1)
                    self.assertFalse(result["lista_para_revision_humana"])

    def test_dictamen_archivo_lineas_y_formato_invalidos(self):
        for bad in ({}, {**CHANGE, "hallazgos": [{**CHANGE["hallazgos"][0], "archivo": "inspect_run.py"}]},
                    {**CHANGE, "hallazgos": [{**CHANGE["hallazgos"][0], "linea": 2}]}):
            with self.subTest(dictamen=bad):
                self.calls.unlink(missing_ok=True)
                self.configure(revisor=[{"verdict": bad}])
                result = self.run_flow()
                self.assertEqual(result["codigo_salida"], 5, result)
                self.assertEqual(result["invocaciones"]["total"], 2)

    def test_referencia_inventario_alterada_durante_agente_detiene(self):
        self.configure(desarrollador=[{"mutation": "reference"}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 6, result)
        self.assertEqual(result["invocaciones"]["revisor"], 0)

    def test_continuidad_alterada_se_rechaza(self):
        self.configure(desarrollador=[{"candidate": BAD}, {}])
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        path = Path(result["intentos"][1]["registro"])
        record = json.loads((path / "resultado.json").read_text())
        other = b"# partida falsa\n"
        (path / "entrega/partida.py").write_bytes(other)
        record["partida_sha256"] = digest(other)
        record["partida"] = project_flow.file_identity(other)
        write_json(path / "entrega/partida.json", record["partida"])
        record["etapas_sha256"]["entrega"] = repair_project.tree_state(path / "entrega")
        write_json(path / "resultado.json", record)
        with self.assertRaisesRegex(ValueError, "Continuidad"):
            self.validate(path)

    def test_revision_aislada_csv_rechazada_antes_de_cli(self):
        result = self.run_flow()
        self.assertEqual(result["codigo_salida"], 0, result)
        count = len(self.calls_read())
        review = review_project.run_isolated_review(result["registro"], 1, "csv-no-admitido", self.root)
        self.assertEqual(review["codigo_salida"], 7, review)
        self.assertIn("export-csv no está admitida", review["error"])
        self.assertEqual(len(self.calls_read()), count)

    def test_cli_csv_seleccion_y_argumentos(self):
        command = [str(Path(sys.executable).resolve()), "-B", str(self.root / "orchestrate_project.py"), "export-csv"]
        result = subprocess.run(command + ["--max-attempts", "1"], capture_output=True, text=True,
                                env=self.cli_env(), timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("total 2/2", result.stdout)
        count = len(self.calls_read())
        for args in (["--max-attempts", "3"], ["--max-attempts", "0"]):
            rejected = subprocess.run(command + args, capture_output=True, env=self.cli_env(), timeout=5)
            self.assertEqual(rejected.returncode, 2)
        self.assertEqual(len(self.calls_read()), count)

    def test_interrupcion_cli_conserva_reserva_candidato_y_parciales(self):
        self.configure(desarrollador=[{"block": True}])
        with subprocess.Popen([str(Path(sys.executable).resolve()), "-B", str(self.root / "orchestrate_project.py"), "export-csv"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.cli_env()) as process:
            deadline = time.monotonic() + 15
            while not self.calls.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(0.02)
            self.assertTrue(self.calls.exists())
            process.send_signal(signal.SIGTERM)
            out, err = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 9, out + err)
        log = next((self.root / "runs").glob("*_orchestrate_*"))
        result = json.loads((log / "resultado.json").read_text())
        self.assertEqual(result["invocaciones"]["total"], 1)
        self.assertTrue((log / "reservas/1-desarrollador/reserva.json").exists())
        self.assertIn("PARCIAL_SIMULADO", (log / "intentos/1/evidencia/desarrollo/eventos.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()

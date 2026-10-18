"""Agentes ejecutables simulados y evaluaciones reales sobre fixtures temporales pequeños."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import orchestrate_project as controller
import project_flow
import repair_project
import review_case
import review_project
from case_evidence import digest
from repair_case import write_json
import test_repair_project as fixture


ROOT = Path(__file__).resolve().parents[1]
APPROVE = {"decision": "aprobar", "resumen": "Aprobación del fixture simulado", "hallazgos": []}
CHANGE = {"decision": "solicitar_cambios", "resumen": "Observación simulada", "hallazgos": [
    {"archivo": "inspect_run.py", "linea": 1, "requisito": "Contrato sintético",
     "explicacion": "OBSERVACION_MODELO_NO_CONFIRMADA", "ejemplo": "Contrastar antes de corregir"}]}
PUBLIC = '''import argparse
from pathlib import Path
import subprocess, sys, unittest
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path)
p.add_argument('--output', type=Path)
args = p.parse_args()
args.output.mkdir()
class Public(unittest.TestCase):
    def test_public(self):
        completed = subprocess.run([sys.executable, '-B', str(args.project/'inspect_run.py'), '--format', 'json'],
                                   text=True, capture_output=True, timeout=3)
        (args.output/'stdout.txt').write_text(completed.stdout)
        for variant in (1, 2):
            with self.subTest(variante=variant):
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout.strip(), 'ENTREGA')
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Public))
sys.exit(0 if result.wasSuccessful() else 1)
'''


class ProjectFlowTests(unittest.TestCase):
    write = fixture.TestRepairProject.write
    git = fixture.TestRepairProject.git
    commit_base = fixture.TestRepairProject.commit_base
    calls_read = fixture.TestRepairProject.calls_read
    cli_env = fixture.TestRepairProject.cli_env

    def setUp(self):
        fixture.TestRepairProject.setUp(self)
        self.write("tests/test_inspect_run.py", fixture.REGRESSION.replace("class Regression", "class Inspector"))
        self.git("add", "tests/test_inspect_run.py")
        self.commit_base()
        for name in (*project_flow.SUPPORT, "orchestrate_project.py", "project_flow.py", "project_flow_runner.py",
                     "review_case.py", "review_project.py", project_flow.DEVELOPER_PROMPT, project_flow.REVIEW_PROMPT):
            self.write(name, (ROOT / name).read_text())
        for kind in ("hallazgos", "anidamiento"):
            self.write(project_flow.SUITES[kind], PUBLIC)
        patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)).start()

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import hashlib, json, os
from pathlib import Path
import sys, time
args = sys.argv[1:]
options = json.loads(Path({str(self.settings)!r}).read_text())
if args == ['--version']:
    print('simulado'); sys.exit(0)
if args == ['exec', '--help']:
    print({(fixture.HELP + ' read-only --output-schema')!r}); sys.exit(0)
role = 'revisor' if args[args.index('--sandbox')+1] == 'read-only' else 'desarrollador'
calls_path = Path({str(self.calls)!r})
calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
number = sum(c['rol'] == role for c in calls)
settings = options.get(role, [{{}}])
setting = settings[min(number, len(settings)-1)]
workspace = Path.cwd()
prompt = sys.stdin.read()
final = Path(args[args.index('--output-last-message')+1])
if role == 'desarrollador':
    run = final.parents[4]
    summary = json.loads((run/'resultado.json').read_text())
    assert summary['invocaciones'][role] == number+1
    assert (run/'reservas'/f'{{number+1}}-{{role}}'/'reserva.json').is_file()
    assert summary['intentos'][number]['invocaciones'][role] == 1
with calls_path.open('a') as output:
    output.write(json.dumps({{'rol': role, 'args': args, 'workspace': str(workspace), 'prompt': prompt,
        'partida_sha256': hashlib.sha256((workspace/'inspect_run.py').read_bytes()).hexdigest(),
        'archivos': sorted(str(p.relative_to(workspace)) for p in workspace.rglob('*') if p.is_file()),
        'pid': os.getpid()}})+'\\n')
print('EVENTO_PARCIAL_SIMULADO', flush=True)
if role == 'desarrollador':
    (workspace/'inspect_run.py').write_text(setting.get('candidate', {fixture.DELIVERY!r}))
    final.write_text('EXPLICACION_DESARROLLADOR_NO_REVISAR')
else:
    final.write_text(setting.get('raw', json.dumps(setting.get('verdict', {APPROVE!r}))))
if setting.get('mutation') == 'workspace':
    (workspace/'archivo_extra').write_text('alterado')
if setting.get('mutation') == 'reference':
    (run/'referencia/contrato.md').write_text('alterado')
if setting.get('mutation') == 'evaluation':
    (run/'intentos/1/evidencia/evaluaciones/aceptacion/stderr.txt').write_text('alterado')
if setting.get('block'): time.sleep(30)
sys.exit(setting.get('exit_code', 0))
''')
        self.fake.chmod(0o755)

    def run_flow(self, attempts=2):
        result = controller.run_orchestration(root=self.root, max_attempts=attempts)
        self.assertEqual(result, json.loads((Path(result['registro'])/'resultado.json').read_text()))
        self.assertEqual(result['incorporacion'], 'no_realizada')
        return result

    def test_aprobacion_primera_entrega_y_original_intacto(self):
        self.write('inspect_run.py', 'TRABAJO PREVIO DEL USUARIO\n')
        before = repair_project.tree_state(self.root, filter_local=True)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(out.getvalue() + err.getvalue(), '')
        self.assertEqual(result['invocaciones'], {'desarrollador': 1, 'revisor': 1, 'total': 2})
        self.assertEqual(repair_project.tree_state(self.root, filter_local=True), before)
        entry = result['intentos'][0]
        self.assertEqual(set(entry['evaluaciones']), set(project_flow.SUITES))
        self.assertEqual(entry['evaluaciones']['hallazgos']['subtests_ejecutados'], 2)
        self.assertTrue(result['lista_para_revision_humana'])
        self.assertTrue(all(result['integridad'].values()))
        self.assertEqual(entry['desarrollo']['agente']['proceso']['limite_segundos'], 300)
        self.assertEqual(entry['revision']['revisor']['limite_segundos'], 180)
        for call in self.calls_read():
            self.assertIn('--ephemeral', call['args'])
            self.assertNotIn('resume', call['args'])
            self.assertNotIn(str(self.root), call['workspace'])
        review = entry['revision']
        context = Path(review['registro'])/'materiales'
        self.assertFalse(any('EXPLICACION_DESARROLLADOR' in p.read_text() for p in context.rglob('*') if p.is_file()))
        self.assertFalse(any('eventos' in name or 'stderr' in name for name in self.calls_read()[1]['archivos']))
        for path, state in result['etapas_cerradas'].items():
            self.assertEqual(repair_project.tree_state(Path(path)), state)

    def test_fallo_aceptacion_correccion_aprobacion_y_continuidad(self):
        self.configure(desarrollador=[{'candidate': fixture.BASE}, {'candidate': fixture.DELIVERY}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(result['invocaciones'], {'desarrollador': 2, 'revisor': 1, 'total': 3})
        first, second = result['intentos']
        self.assertIsNone(first['revision'])
        self.assertEqual(first['candidato_sha256'], second['partida_sha256'])
        self.assertNotEqual(first['candidato_sha256'], second['candidato_sha256'])
        calls = self.calls_read()
        self.assertEqual(calls[1]['partida_sha256'], first['candidato_sha256'])
        self.assertIn('AssertionError', calls[1]['prompt'])
        self.assertIn('sha256', calls[1]['prompt'])
        path = Path(second['registro'])/'entrega'
        self.assertEqual((path/'partida.py').read_text(), fixture.BASE)
        self.assertTrue((path/'anterior.diff').read_text())
        project_flow.validate_delivery(second['registro'], self.root)

    def test_solicitud_cambios_correccion_y_nueva_revision_sin_dictamen_anterior(self):
        self.configure(desarrollador=[{}, {'candidate': fixture.DELIVERY+'# corrección verificable\n'}],
                       revisor=[{'verdict': CHANGE}, {'verdict': APPROVE}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(result['invocaciones'], {'desarrollador': 2, 'revisor': 2, 'total': 4})
        calls = self.calls_read()
        self.assertIn('OBSERVACION_MODELO_NO_CONFIRMADA', calls[2]['prompt'])
        self.assertIn('pendientes_de_contraste_semantico', calls[2]['prompt'])
        self.assertNotEqual(calls[0]['workspace'], calls[2]['workspace'])
        self.assertNotEqual(calls[1]['workspace'], calls[3]['workspace'])
        for entry in result['intentos']:
            context = Path(entry['revision']['registro'])/'materiales'
            self.assertFalse(any('OBSERVACION_MODELO_NO_CONFIRMADA' in p.read_text() for p in context.rglob('*') if p.is_file()))
        first, second = result['intentos']
        self.assertNotEqual(first['candidato_sha256'], second['candidato_sha256'])
        self.assertEqual(first['candidato_sha256'], calls[2]['partida_sha256'])

    def test_agotamiento_uno_y_dos_intentos(self):
        for attempts in (1, 2):
            with self.subTest(intentos=attempts):
                if self.calls.exists(): self.calls.unlink()
                self.configure(desarrollador=[{'candidate': fixture.BASE}])
                result = self.run_flow(attempts)
                self.assertEqual(result['codigo_salida'], 1, result)
                self.assertEqual(result['estado'], 'intentos_agotados')
                self.assertEqual(result['invocaciones'], {'desarrollador': attempts, 'revisor': 0, 'total': attempts})

    def test_agotamiento_cambios_no_produce_tercer_intento(self):
        self.configure(revisor=[{'verdict': CHANGE}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 1, result)
        self.assertEqual(result['invocaciones']['total'], 4)
        self.assertEqual(len(self.calls_read()), 4)

    def test_fallo_tecnico_desarrollador_no_reintenta_y_conserva_candidato(self):
        self.configure(desarrollador=[{'exit_code': 17}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertEqual(len(self.calls_read()), 1)
        self.assertEqual((Path(result['intentos'][0]['registro'])/'entrega/inspect_run.py').read_text(), fixture.DELIVERY)

    def test_timeout_desarrollador_conserva_salida_parcial(self):
        self.configure(desarrollador=[{'block': True}])
        with patch.object(repair_project, 'AGENT_TIMEOUT', 0.2):
            result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 4, result)
        self.assertEqual(len(self.calls_read()), 1)
        self.assertIn('EVENTO_PARCIAL', (Path(result['intentos'][0]['registro'])/'desarrollo/eventos.jsonl').read_text())

    def test_revisor_invalido_fallido_y_timeout_no_aprueban(self):
        for setting, code in (({'raw': '{}'}, 5), ({'exit_code': 17}, 3), ({'block': True}, 4)):
            with self.subTest(setting=setting):
                if self.calls.exists(): self.calls.unlink()
                self.configure(revisor=[setting])
                with patch.object(review_case, 'AGENT_TIMEOUT_SECONDS', 0.2 if setting.get('block') else 180):
                    result = self.run_flow()
                self.assertEqual(result['codigo_salida'], code, result)
                self.assertFalse(result['lista_para_revision_humana'])
                self.assertEqual(result['invocaciones']['total'], 2)

    def test_integridad_workspace_referencia_y_evaluacion_previa(self):
        for mutation in ('workspace', 'reference', 'evaluation'):
            with self.subTest(mutation=mutation):
                if self.calls.exists(): self.calls.unlink()
                settings = [{'mutation': mutation}] if mutation != 'evaluation' else [
                    {'candidate': fixture.BASE}, {'mutation': mutation}]
                self.configure(desarrollador=settings)
                result = self.run_flow()
                self.assertEqual(result['codigo_salida'], 6, result)
                self.assertEqual(result['invocaciones']['revisor'], 0)

    def test_error_tecnico_evaluador_detiene_sin_agentes(self):
        self.write(repair_project.ACCEPTANCE, fixture.ACCEPTANCE.replace("self.assertEqual(self.call().returncode, 0)", "raise RuntimeError('error técnico')"))
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertEqual(self.calls_read(), [])

    def test_error_tecnico_posterior_no_permite_correccion(self):
        self.write(repair_project.ACCEPTANCE, fixture.ACCEPTANCE.replace(
            'self.assertEqual(self.call().returncode, 0)',
            "self.assertEqual(self.call().returncode, 0)\n        if 'ENTREGA' in self.call().stdout: raise RuntimeError('error posterior')"))
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertEqual(result['invocaciones']['total'], 1)
        evaluation = Path(result['intentos'][0]['registro'])/'evaluaciones/aceptacion'
        self.assertIn('error posterior', (evaluation/'stderr.txt').read_text())
        self.assertIn(str(evaluation), result['etapas_cerradas'])

    def test_timeout_evaluacion_inicial_conserva_parciales_sin_agentes(self):
        self.write(repair_project.ACCEPTANCE,
                   "import time\nprint('PARCIAL_EVALUACION', flush=True)\ntime.sleep(20)\n" + fixture.ACCEPTANCE)
        with patch.dict(project_flow.LIMITS, aceptacion=0.2):
            result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 4, result)
        self.assertEqual(result['invocaciones']['total'], 0)
        evaluation = Path(result['registro'])/'inicial/aceptacion'
        self.assertIn('PARCIAL_EVALUACION', (evaluation/'stdout.txt').read_text())
        self.assertIn(str(evaluation), result['etapas_cerradas'])

    def test_reserva_no_persistida_impide_invocacion(self):
        original = controller.atomic_json
        def failing_reservation(path, data):
            if path.name == 'reserva.json':
                raise OSError('fallo de disco simulado')
            return original(path, data)
        with patch.object(controller, 'atomic_json', failing_reservation):
            result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 8, result)
        self.assertEqual(result['invocaciones']['total'], 0)
        self.assertEqual(self.calls_read(), [])

    def test_revisor_altera_workspace_no_se_acepta_dictamen(self):
        self.configure(revisor=[{'mutation': 'workspace'}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 6, result)
        self.assertFalse(result['lista_para_revision_humana'])
        self.assertEqual(result['invocaciones']['total'], 2)

    def test_sin_reserva_global_no_se_reanuda_revision(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        count = len(self.calls_read())
        review = review_project.run_delivery_review(result['intentos'][0]['registro'], self.root)
        self.assertNotEqual(review['codigo_salida'], 0)
        self.assertIn('reserva del orquestador', review['error'])
        self.assertEqual(len(self.calls_read()), count)

    def test_informe_incompleto_impide_revision_aun_resellado(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        path = Path(result['intentos'][0]['registro'])
        summary = json.loads((path/'resultado.json').read_text())
        report = path/'evaluaciones/hallazgos/pruebas.json'
        data = json.loads(report.read_text())
        data['terminados'].clear()
        write_json(report, data)
        summary['etapas_sha256']['evaluaciones'] = repair_project.tree_state(path/'evaluaciones')
        write_json(path/'resultado.json', summary)
        count = len(self.calls_read())
        rejected = review_project.run_delivery_review(path, self.root)
        self.assertEqual(rejected['codigo_salida'], 7, rejected)
        self.assertEqual(len(self.calls_read()), count)

    def test_continuidad_alterada_se_rechaza_aun_resellada(self):
        self.configure(desarrollador=[{'candidate': fixture.BASE}, {}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        path = Path(result['intentos'][1]['registro'])
        summary = json.loads((path/'resultado.json').read_text())
        (path/'entrega/partida.py').write_text('# otra partida\n')
        summary['partida_sha256'] = digest((path/'entrega/partida.py').read_bytes())
        summary['etapas_sha256']['entrega'] = repair_project.tree_state(path/'entrega')
        write_json(path/'resultado.json', summary)
        with self.assertRaisesRegex(ValueError, 'Continuidad'):
            project_flow.validate_delivery(path, self.root)

    def test_recuentos_booleanos_no_acreditan_evidencia(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        path = Path(result['intentos'][0]['registro'])
        summary = json.loads((path/'resultado.json').read_text())
        item = summary['evaluaciones']['hallazgos']
        self.assertEqual(item['metodos'], 1)
        item['metodos'] = True
        write_json(path/'evaluaciones/hallazgos/evaluacion.json', item)
        summary['etapas_sha256']['evaluaciones'] = repair_project.tree_state(path/'evaluaciones')
        write_json(path/'resultado.json', summary)
        with self.assertRaisesRegex(ValueError, 'Recuentos de evaluación inválidos'):
            project_flow.validate_delivery(path, self.root)

    def test_cli_canales_y_limites_argumentos(self):
        command = [sys.executable, '-B', str(self.root/'orchestrate_project.py'), 'inspect-json']
        completed = subprocess.run(command + ['--max-attempts', '1'], capture_output=True, text=True,
                                   env=self.cli_env(), timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('Congelando', completed.stderr)
        self.assertIn('Estado: lista_para_revision_humana', completed.stdout)
        self.assertIn('desarrollador 1, revisor 1, total 2/2', completed.stdout)
        count = len(self.calls_read())
        for args in (['--max-attempts', '0'], ['--max-attempts', '3']):
            bad = subprocess.run(command + args, capture_output=True, text=True, env=self.cli_env(), timeout=5)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, '')
        self.assertEqual(len(self.calls_read()), count)

    def test_interrupcion_cli_conserva_reserva_y_salida(self):
        self.configure(desarrollador=[{'block': True}])
        with subprocess.Popen([sys.executable, '-B', str(self.root/'orchestrate_project.py'), 'inspect-json'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.cli_env()) as process:
            deadline = time.monotonic() + 10
            while not self.calls.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(0.02)
            self.assertTrue(self.calls.exists())
            process.send_signal(signal.SIGTERM)
            out, err = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 9, out + err)
        log = next((self.root/'runs').glob('*_orchestrate_*'))
        result = json.loads((log/'resultado.json').read_text())
        self.assertEqual(result['invocaciones']['total'], 1)
        self.assertEqual(result['estado'], 'interrumpida')
        self.assertIn('EVENTO_PARCIAL', (log/'intentos/1/evidencia/desarrollo/eventos.jsonl').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)

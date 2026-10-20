"""Conjuntos v2 sintéticos con CLI simulada; nunca se invocan modelos."""

import copy
import hashlib
import json
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

import test_configurable_projects as fixtures
import orchestrate_project as controller
import project_delivery as bundles
import project_flow
import project_task_config
import repair_project
import review_project


ORIGINAL = "from util import cero\n\ndef calcular():\n    return cero()\n"
RULES = "from consulta import valor\n\ndef calcular():\n    return valor()\n"
QUERY = "from util import siete\n\ndef valor():\n    return siete()\n"
BAD_QUERY = "def valor():\n    return 6\n"
ACCEPTANCE = '''import argparse, subprocess, sys, unittest
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
args = p.parse_args()
class Acceptance(unittest.TestCase):
    def test_behavior(self):
        for name in ('reglas.py', 'consulta.py'):
            self.assertTrue((args.project/name).is_file(), 'Falta módulo sintético: '+name)
        result = subprocess.run([sys.executable, '-B', '-c', 'from reglas import calcular; print(calcular())'],
                                cwd=args.project, capture_output=True, timeout=5)
        self.assertEqual((result.returncode, result.stderr), (0, b''))
        self.assertEqual(result.stdout, b'7\\n')
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
sys.exit(0 if result.wasSuccessful() else 1)
'''


class MultipleProjectTests(unittest.TestCase):
    write = fixtures.ConfigurableProjectTests.write
    git = fixtures.ConfigurableProjectTests.git
    good = staticmethod(fixtures.ConfigurableProjectTests.good)
    config_path = fixtures.ConfigurableProjectTests.config_path
    save_config = fixtures.ConfigurableProjectTests.save_config
    cli = fixtures.ConfigurableProjectTests.cli
    calls_read = fixtures.ConfigurableProjectTests.calls_read

    def setUp(self):
        fixtures.ConfigurableProjectTests.setUp(self)
        self.write('project_delivery.py', (fixtures.ROOT/'project_delivery.py').read_text())
        self.write('reglas.py', ORIGINAL)
        (self.root/'reglas.py').chmod(0o755)
        self.write('util.py', 'def cero(): return 0\ndef siete(): return 7\n')
        self.git('add', 'reglas.py', 'util.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Base de módulos sintéticos')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()
        self.task = 'modulos-sinteticos'
        self.config = copy.deepcopy(self.configs['marcador-beta'])
        self.config.update(version=2, identificador=self.task, commit_base=self.base,
            archivos_editables=[{'ruta': 'reglas.py', 'estado_inicial': 'existente'},
                               {'ruta': 'consulta.py', 'estado_inicial': 'ausente'}])
        del self.config['archivo_editable'], self.config['estado_inicial']
        self.configs[self.task] = self.config
        self.write(self.config['contrato'], f'# Contrato sintético\nBase: `{self.base}`\n'
                   'reglas.calcular devuelve 7 utilizando consulta.valor; biblioteca estándar.\n')
        self.write(self.config['evaluador_aceptacion'], ACCEPTANCE)
        self.save_config(self.task)

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import json, os, signal, sys, time
from pathlib import Path
args = sys.argv[1:]
if args == ['--version']: print('CLI simulada'); sys.exit(0)
if args == ['exec', '--help']:
    print('--config --sandbox --cd --skip-git-repo-check --json --output-last-message --ephemeral read-only --output-schema')
    sys.exit(0)
role = 'revisor' if args[args.index('--sandbox')+1] == 'read-only' else 'desarrollador'
workspace = Path.cwd()
prompt = sys.stdin.read()
config = (json.JSONDecoder().raw_decode(prompt.split('CONFIGURACION CONGELADA\\n')[1])[0]
          if role == 'desarrollador' else json.loads((workspace/'configuracion_tarea.json').read_text()))
paths = [x['ruta'] for x in config['archivos_editables']]
starting = {{name: (workspace/name).read_text() if (workspace/name).is_file() else None for name in paths}}
calls_file = Path({str(self.calls)!r})
calls = [json.loads(x) for x in calls_file.read_text().splitlines()] if calls_file.exists() else []
number = sum(c['rol'] == role for c in calls)
settings = json.loads(Path({str(self.settings)!r}).read_text()).get(role, [{{}}])
setting = settings[min(number, len(settings)-1)]
final = Path(args[args.index('--output-last-message')+1])
if role == 'desarrollador':
    run = final.parents[4]
    summary = json.loads((run/'resultado.json').read_text())
    assert summary['invocaciones'][role] == number+1
    assert (run/'reservas'/f'{{number+1}}-{{role}}'/'reserva.json').is_file()
with calls_file.open('a') as output:
    output.write(json.dumps({{'rol':role, 'partida':starting, 'workspace':str(workspace), 'prompt':prompt,
        'archivos':{{str(p.relative_to(workspace)):p.read_text() for p in workspace.rglob('*') if p.is_file()}}}})+'\\n')
if role == 'desarrollador':
    for name, text in setting.get('files', {{'reglas.py':{RULES!r}, 'consulta.py':{QUERY!r}}}).items():
        if text is None:
            (workspace/name).unlink(missing_ok=True)
        else:
            new = not (workspace/name).exists()
            (workspace/name).write_text(text)
            if new: (workspace/name).chmod(0o644)
    final.write_text('Desarrollo de módulos simulado')
else:
    final.write_text(setting.get('raw', json.dumps(setting.get('verdict',
        {{'decision':'aprobar','resumen':'Revisión simulada','hallazgos':[]}}))))
mutation = setting.get('mutation')
if mutation == 'extra': (workspace/'intruso.py').write_text('intrusión')
if mutation == 'directory': (workspace/'extra').mkdir()
if mutation == 'mode': (workspace/'reglas.py').chmod(0o644)
if mutation == 'newmode': (workspace/'consulta.py').chmod(0o755)
if mutation == 'link':
    (workspace/'consulta.py').unlink()
    (workspace/'consulta.py').symlink_to(workspace/'reglas.py')
if mutation == 'config': (run/'referencia/tarea.json').write_text('{{}}')
if setting.get('interrupt'): os.kill(os.getppid(), signal.SIGINT)
if setting.get('block'): time.sleep(20)
sys.exit(setting.get('exit_code', 0))
''')
        self.fake.chmod(0o755)

    def run_flow(self, attempts=2):
        before = repair_project.tree_state(self.root, filter_local=True)
        self.selection = project_task_config.load_task(self.root, self.config_path(self.task))
        with patch.object(project_task_config, 'load_task', return_value=self.selection):
            result = controller.run_orchestration(root=self.root, task_config_path=self.config_path(self.task),
                                                  max_attempts=attempts)
        self.assertEqual(result, json.loads((Path(result['registro'])/'resultado.json').read_text()))
        self.assertEqual(repair_project.tree_state(self.root, filter_local=True), before)
        self.assertEqual(result['incorporacion'], 'no_realizada')
        self.assertFalse((self.root/'consulta.py').exists())
        return result

    def test_behavior_correction_exact_set_and_review_materials(self):
        self.configure(desarrollador=[{'files': {'reglas.py': RULES, 'consulta.py': BAD_QUERY}},
                                       {'files': {'consulta.py': QUERY}}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(result['tipo'], 'orquestacion_configurable_v2')
        self.assertEqual(result['invocaciones'], {'desarrollador': 2, 'revisor': 1, 'total': 3})
        first, second = result['intentos']
        self.assertEqual(first['conjunto'], second['partida_conjunto'])
        self.assertNotEqual(first['conjunto_sha256'], second['conjunto_sha256'])
        calls = self.calls_read()
        self.assertEqual(calls[0]['partida'], {'reglas.py': ORIGINAL, 'consulta.py': None})
        self.assertEqual(calls[1]['partida'], {'reglas.py': RULES, 'consulta.py': BAD_QUERY})
        self.assertEqual(calls[2]['partida'], {'reglas.py': RULES, 'consulta.py': QUERY})
        self.assertEqual(first['evaluaciones']['aceptacion']['clasificacion'], 'fallos_asercion')
        self.assertEqual(second['revision']['dictamen_modelo']['decision'], 'aprobar')
        for entry in result['intentos']:
            self.assertNotIn('candidato_sha256', entry)
            self.assertNotEqual(entry['evaluaciones']['aceptacion']['proceso']['directorio_trabajo'],
                                entry['evaluaciones']['regresion']['proceso']['directorio_trabajo'])
            for item in entry['evaluaciones'].values():
                self.assertEqual(item['conjunto_evaluado'], entry['conjunto'])
                self.assertNotEqual(item['proceso']['directorio_trabajo'], calls[entry['numero']-1]['workspace'])
            project_flow.validate_delivery(entry['registro'], self.root, task=self.selection, allow_failures=True)
        path = Path(second['registro'])/'entrega'
        self.assertEqual((path/'diff_anterior/reglas.py.diff').read_bytes(), b'')
        self.assertIn(b'--- /dev/null', (path/'diff_base/consulta.py.diff').read_bytes())
        self.assertFalse((path/'original/consulta.py').exists())
        self.assertEqual(stat.S_IMODE((path/'archivos/reglas.py').stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((path/'archivos/consulta.py').stat().st_mode), 0o644)
        materials = calls[2]['archivos']
        self.assertEqual(materials['reglas.py'], RULES)
        self.assertEqual(materials['consulta.py'], QUERY)
        self.assertEqual(materials['original/reglas.py'], ORIGINAL)
        self.assertNotIn('original/consulta.py', materials)
        self.assertEqual(materials['dependencias/util.py'], materials['original/dependencias/util.py'])
        self.assertEqual(json.loads(materials['resumen_evidencia.json'])['conjunto'], second['conjunto'])
        for folder in ('materiales_sha256', 'evidencia_sha256'):
            state = second['revision'][folder]
            self.assertEqual(bundles.identity(state, self.selection.config), second['conjunto'])
        for item in second['conjunto']['archivos']:
            copied = second['revision']['evidencia_sha256']['evidencia/entrega/archivos/' + item['ruta']]
            self.assertEqual(copied, {k: v for k, v in item.items() if k != 'ruta'})
        self.trace = {'naturaleza': 'simulación CLI; sin modelos', 'inicial': result['procedencia']['conjunto_inicial'],
            'intentos': [{k: e[k] for k in ('numero', 'partida_conjunto', 'conjunto', 'evaluaciones', 'transiciones')}
                         for e in result['intentos']], 'revision': second['revision'],
            'invocaciones': result['invocaciones'], 'registro_temporal': result['registro']}

    def test_invalid_configurations_rejected_before_agents(self):
        original = copy.deepcopy(self.config)
        variants = [dict(original, version=1), dict(original, version=True), dict(original, version=3),
                    dict(original, archivo_editable='consulta.py'), dict(original, estado_inicial='ausente'),
                    dict(original, archivos_editables=[]), dict(original, archivos_editables={})]
        for entry in ({'ruta':'consulta.py','estado_inicial':'existente'},
                      {'ruta':'reglas.py','estado_inicial':'ausente'},
                      {'ruta':'../consulta.py','estado_inicial':'ausente'},
                      {'ruta':'src/consulta.py','estado_inicial':'ausente'},
                      {'ruta':'consulta.py','estado_inicial':True},
                      {'ruta':'consulta.py','estado_inicial':'ausente','modo':420},
                      {'ruta':'project_flow.py','estado_inicial':'ausente'},
                      {'ruta':'process_environment.py','estado_inicial':'ausente'}):
            variants.append(dict(original, archivos_editables=[entry]))
        variants.append(dict(original, archivos_editables=original['archivos_editables']*2))
        variants.append(dict(original, referencias=['reglas.py']))
        for data in variants:
            with self.subTest(data=data):
                self.write(self.config_path(self.task), json.dumps(data))
                with self.assertRaises(ValueError):
                    project_task_config.load_task(self.root, self.config_path(self.task))
        self.write(self.config_path(self.task), '{"version":2,"version":2}')
        with self.assertRaises(ValueError):
            project_task_config.load_task(self.root, self.config_path(self.task))
        self.assertEqual(self.calls_read(), [])
        self.assertFalse((self.root/'runs').exists())

    def test_git_links_and_directories_cannot_be_editable(self):
        (self.root/'enlace.py').symlink_to('reglas.py')
        self.write('directorio.py/dato', 'dato')
        self.git('add', 'enlace.py', 'directorio.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Entradas no regulares')
        base = self.git('rev-parse', 'HEAD').decode().strip()
        self.config['commit_base'] = base
        self.write(self.config['contrato'], f'# Sintético\nBase: `{base}`\n')
        for name in ('enlace.py', 'directorio.py'):
            self.config['archivos_editables'] = [{'ruta': name, 'estado_inicial':'existente'}]
            self.save_config(self.task)
            with self.assertRaises(ValueError):
                project_task_config.load_task(self.root, self.config_path(self.task))
        self.assertEqual(self.calls_read(), [])

    def test_incomplete_scope_modes_links_and_directories_stop(self):
        settings = [{'files': {'reglas.py': RULES}}, {'files': {'reglas.py': None, 'consulta.py': QUERY}}]
        settings += [{'mutation': name} for name in ('extra', 'directory', 'mode', 'newmode', 'link', 'config')]
        for setting in settings:
            with self.subTest(setting=setting):
                self.calls.unlink(missing_ok=True)
                self.configure(desarrollador=[setting])
                result = self.run_flow()
                self.assertEqual(result['codigo_salida'], 6, result)
                self.assertFalse(result['lista_para_revision_humana'])
                self.assertEqual(len(self.calls_read()), 1)
                entry = result['intentos'][0]
                self.assertNotIn('evaluaciones', entry)
                self.assertTrue((Path(entry['registro'])/'entrega/conjunto.json').is_file())

    def test_partial_technical_failure_timeout_and_interrupt_preserved(self):
        self.config['limites_segundos']['desarrollador'] = 1
        self.save_config(self.task)
        for options, expected in (({'exit_code': 1}, 3), ({'block': True}, 4), ({'interrupt': True, 'block': True}, 9)):
            with self.subTest(options=options):
                self.calls.unlink(missing_ok=True)
                self.configure(desarrollador=[{'files': {'reglas.py': RULES}, **options}])
                result = self.run_flow()
                self.assertEqual(result['codigo_salida'], expected, result)
                self.assertEqual(len(self.calls_read()), 1)
                entry = result['intentos'][0]
                self.assertNotIn('evaluaciones', entry)
                self.assertEqual(next(x for x in entry['conjunto']['archivos'] if x['ruta']=='consulta.py')['tipo'], 'ausente')
                self.assertEqual((Path(entry['registro'])/'entrega/archivos/reglas.py').read_text(), RULES)
                self.assertFalse((Path(entry['registro'])/'entrega/archivos/consulta.py').exists())

    @staticmethod
    def changes(file='consulta.py', line=4):
        return {'decision': 'solicitar_cambios', 'resumen': 'Hallazgo simulado', 'hallazgos': [{
            'archivo': file, 'linea': line, 'requisito': 'Contrato sintético',
            'explicacion': 'Observación simulada pendiente de contraste', 'ejemplo': 'calcular()'}]}

    def test_review_changes_second_file_continuity_and_budget(self):
        self.configure(revisor=[{'verdict': self.changes()}, {}],
                       desarrollador=[{}, {'files': {}}])
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        first, second = result['intentos']
        self.assertEqual(first['conjunto'], second['partida_conjunto'])
        self.assertEqual(first['conjunto'], second['conjunto'])
        self.assertEqual(result['invocaciones'], {'desarrollador': 2, 'revisor': 2, 'total': 4})
        feedback = json.loads((Path(second['registro'])/'feedback.json').read_text())
        self.assertEqual(feedback['conjunto_sha256'], first['conjunto_sha256'])
        self.assertEqual(feedback['revision']['dictamen']['hallazgos'][0]['archivo'], 'consulta.py')
        self.calls.unlink()
        self.configure(revisor=[{'verdict': self.changes()}])
        exhausted = self.run_flow(attempts=1)
        self.assertEqual((exhausted['codigo_salida'], exhausted['estado']), (1, 'intentos_agotados'))
        self.assertEqual(len(self.calls_read()), 2)

    def test_invalid_verdict_paths_lines_and_reviewer_failures(self):
        self.config['limites_segundos']['revisor'] = 1
        self.save_config(self.task)
        settings = [({'verdict': self.changes('intruso.py')}, 5),
                    ({'verdict': self.changes(line=5)}, 5), ({'verdict': self.changes(line=True)}, 5),
                    ({'raw': '{"decision":"aprobar"}'}, 5), ({'exit_code':1}, 3), ({'block':True},4)]
        for setting, code in settings:
            with self.subTest(setting=setting):
                self.calls.unlink(missing_ok=True)
                self.configure(revisor=[setting])
                result = self.run_flow()
                self.assertEqual(result['codigo_salida'], code, result)
                self.assertEqual(len(result['intentos']), 1)
                self.assertEqual(len(self.calls_read()), 2)
                self.assertFalse(result['lista_para_revision_humana'])

    def test_other_set_evaluation_and_feedback_rejected(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        entry = result['intentos'][0]
        delivery = Path(entry['registro'])
        record = json.loads((delivery/'resultado.json').read_text())
        evaluation = delivery/'evaluaciones/aceptacion/evaluacion.json'
        item = json.loads(evaluation.read_text())
        original = evaluation.read_bytes()
        fake = copy.deepcopy(item['conjunto_evaluado'])
        fake['archivos'][0]['sha256'] = '0'*64
        fake['sha256'] = hashlib.sha256(json.dumps({k: fake[k] for k in ('version', 'archivos')},
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        item['conjunto_evaluado'] = fake
        item['conjunto_sha256'] = fake['sha256']
        evaluation.write_text(json.dumps(item))
        record['evaluaciones']['aceptacion'] = item
        record['etapas_sha256']['evaluaciones'] = repair_project.tree_state(delivery/'evaluaciones')
        (delivery/'resultado.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'otro conjunto'):
            project_flow.validate_delivery(delivery, self.root, task=self.selection)
        evaluation.write_bytes(original)
        record['evaluaciones']['aceptacion'] = json.loads(original)
        record['etapas_sha256']['evaluaciones'] = repair_project.tree_state(delivery/'evaluaciones')
        (delivery/'resultado.json').write_text(json.dumps(record))
        feedback_path = delivery/'feedback.json'
        feedback = json.loads(feedback_path.read_text())
        feedback['conjunto_sha256'] = entry['conjunto_sha256']
        feedback_path.write_text(json.dumps(feedback))
        with self.assertRaisesRegex(ValueError, 'Feedback de otro conjunto'):
            project_flow.validate_delivery(delivery, self.root, task=self.selection)
        with self.assertRaisesRegex(ValueError, 'referencia de confianza'):
            project_flow.validate_delivery(delivery, self.root)

    def test_identity_is_order_independent_and_distinguishes_mode_absence_and_content(self):
        selection = project_task_config.load_task(self.root, self.config_path(self.task))
        config = selection.config
        tree = config['editables_iniciales']
        stamp = bundles.identity(tree, config)
        self.assertEqual(stamp, bundles.identity(dict(reversed(list(tree.items()))),
                                                {**config, 'editables': list(reversed(config['editables']))}))
        for alteration in ({'tipo':'archivo', 'modo':0o644, 'sha256':hashlib.sha256(b'').hexdigest()},
                           {**tree['reglas.py'], 'modo':0o644}, {**tree['reglas.py'], 'sha256':'0'*64}):
            self.assertNotEqual(stamp['sha256'], bundles.identity({**tree, 'consulta.py':alteration}, config)['sha256'])

    def test_verdict_limits_each_file_and_dependencies_reject_packages(self):
        counts = {'reglas.py': 50, 'consulta.py': 4}
        good = json.dumps(self.changes()).encode()
        self.assertEqual(review_project.validate_verdict(good, counts)['hallazgos'][0]['archivo'], 'consulta.py')
        for file, line in (('consulta.py', 5), ('reglas.py', 51), ('ajeno.py', 1), ('consulta.py', 0), ('consulta.py', True)):
            with self.subTest(file=file, line=line), self.assertRaises(ValueError):
                review_project.validate_verdict(json.dumps(self.changes(file, line)).encode(), counts)
        schema = review_project.response_schema(counts)
        choices = schema['properties']['hallazgos']['items']['anyOf']
        self.assertEqual({x['properties']['archivo']['enum'][0]: x['properties']['linea']['maximum'] for x in choices}, counts)
        for files in ({'json': {}, 'json/__init__.py': {}}, {'util.py': {}, 'tests/util.py': {}}):
            with self.assertRaises(ValueError):
                review_project.review_dependencies([b'import json\nimport util\n'], files,
                                                   lambda name: b'', editables=counts)

    def test_static_context_never_executes_and_rejects_unresolved_dependencies(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        delivery = Path(result['intentos'][0]['registro'])
        reference = review_project.Evidence(Path(result['registro'])/'referencia')
        sentinel = self.temporary/'NO-EJECUTAR'
        (delivery/'entrega/archivos/consulta.py').write_text(
            f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("ejecutado")\n' + QUERY)
        materials = bundles.review_context(review_project.Evidence(delivery), reference, self.selection.config)
        self.assertIn('NO-EJECUTAR', materials['consulta.py'].decode())
        self.assertFalse(sentinel.exists())
        for source in ('import ausente\n', 'from .util import siete\n', '__import__("util")\n', 'def rota(\n'):
            (delivery/'entrega/archivos/consulta.py').write_text(source)
            with self.assertRaises(ValueError):
                bundles.review_context(review_project.Evidence(delivery), reference, self.selection.config)
        with self.assertRaises(ValueError):
            review_project.orchestration_review_evidence(result['registro'], 1, self.root)
        self.assertEqual(len(self.calls_read()), 2)

    def test_cli_text_json_export_and_no_referenced_reads(self):
        result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        run = Path(result['registro'])
        # El inspector solo necesita el resumen: las referencias quedan inaccesibles.
        detached = self.temporary/'solo-resumen'
        detached.mkdir()
        (detached/'resultado.json').write_bytes((run/'resultado.json').read_bytes())
        text = self.cli('inspect_project.py', '--run', detached)
        self.assertEqual((text.returncode, text.stderr), (0, b''))
        self.assertIn(b'modulos-sinteticos', text.stdout)
        query = self.cli('inspect_project.py', '--run', detached, '--format', 'json')
        self.assertEqual((query.returncode, query.stderr), (0, b''))
        document = json.loads(query.stdout)
        self.assertEqual(document['ejecucion']['caso'], self.task)
        self.assertEqual(document['consulta']['estado'], 'completada')
        filename = self.temporary/'consulta.json'
        filename.write_bytes(query.stdout)
        exported = self.cli('export_runs.py', filename)
        self.assertEqual((exported.returncode, exported.stderr), (0, b''))
        self.assertIn(b'"modulos-sinteticos"', exported.stdout)


if __name__ == '__main__':
    unittest.main()

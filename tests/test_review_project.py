"""Revisión de proyectos con registros sintéticos y CLI simulada; sin modelos."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import review_case
import review_project as controller
from case_evidence import digest, unified_diff
from repair_case import ProcessInterrupted, write_json
from repair_project import static_test_ids, tree_state


PROJECT = Path(__file__).resolve().parents[1]
ORIGINAL = b'import case_evidence\nraise RuntimeError("NO EJECUTAR ORIGINAL")\n'
CANDIDATE = b'import case_evidence\nraise RuntimeError("NO EJECUTAR CANDIDATO")\n# entrega\n'
OLD = b'import unittest\nclass Acceptance(unittest.TestCase):\n    def test_json(self): pass\n'
NEW = OLD + b'# Ajuste sintetico del diagnostico; no implementa inspect-json.\n'
REGRESSION = b'import inspect_run\nimport case_evidence\nimport unittest\nclass Regression(unittest.TestCase):\n    def test_text(self): pass\n'
GENERAL = b'import unittest\nclass General(unittest.TestCase):\n    def test_controller(self): pass\n'
SPECIFIC = b'import unittest\nclass Specific(unittest.TestCase):\n    def test_alias(self): pass\n'
APPROVE = {"decision": "aprobar", "resumen": "Sin incumplimientos en el fixture.", "hallazgos": []}
CHANGE = {"decision": "solicitar_cambios", "resumen": "Incumplimiento sintético.", "hallazgos": [
    {"archivo": "inspect_run.py", "linea": 2, "requisito": "Interfaz de consulta",
     "explicacion": "El fixture termina con una excepción.",
     "ejemplo": "Con --run registro, se exige una consulta; el raise termina el proceso."}]}
HELP = '--config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema'


class ProjectReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-review-project-")
        self.addCleanup(temporary.cleanup)
        self.temp = Path(temporary.name)
        self.root = self.temp / "proyecto con espacios"
        self.root.mkdir()
        self.dev = self.root / "runs/desarrollo"
        self.ree = self.root / "runs/reevaluacion"
        for name, data in {"inspect_run.py": ORIGINAL, "case_evidence.py": b'# dependencia sintetica\n',
                           "tests/test_inspect_run.py": REGRESSION,
                           "tests/test_general.py": GENERAL}.items():
            self.write(self.root / name, data)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Base temporal")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        contract = f'# Contrato sintético\nBase: `{self.base}`\nSolo inspect_run.py.\n'.encode()
        runner = (PROJECT / "project_test_runner.py").read_bytes()
        for name, data in {controller.CONTRACT: contract, controller.ACCEPTANCE: NEW,
                           controller.SPECIFIC: SPECIFIC, "project_test_runner.py": runner,
                           controller.PROMPT: (PROJECT / controller.PROMPT).read_bytes()}.items():
            self.write(self.root / name, data)
        reference = self.dev / "referencia"
        files = {}
        for entry in self.git("ls-tree", "-rz", self.base).split(b'\0'):
            if entry:
                metadata, name = entry.split(b'\t', 1)
                mode, _, oid = metadata.decode().split()
                name = name.decode()
                data = self.git("cat-file", "blob", oid)
                self.write(reference / "proyecto" / name, data)
                (reference / "proyecto" / name).chmod(int(mode[-3:], 8))
                files[name] = {"objeto_git": oid, "modo_git": mode, "sha256": digest(data)}
        for name, data in {"contrato.md": contract, "evaluar.py": OLD, "project_test_runner.py": runner}.items():
            self.write(reference / name, data)
        expected = {"aceptacion": static_test_ids(OLD, "__main__"),
                    "regresion": sorted(static_test_ids(REGRESSION, "test_inspect_run")
                                        + static_test_ids(GENERAL, "test_general"))}
        base = {"tipo": "proyecto_existente", "tarea": "inspect-json", "commit_base": self.base,
                "head_origen": self.base, "archivos_base": files, "excluidos": [],
                "materiales_del_arbol_actual": {controller.CONTRACT: digest(contract), controller.ACCEPTANCE: digest(OLD)},
                "pruebas_esperadas": expected}
        write_json(reference / "procedencia.json", base)
        agent = {"estado": "finalizada", "codigo_salida": 0, "error": None, "duracion_segundos": 0.1}
        self.write(self.dev / "agente/respuesta_final.txt", b'NO_MOSTRAR_EXPLICACION_DESARROLLADOR')
        write_json(self.dev / "agente/resultado.json", agent)
        self.write(self.dev / "entrega/inspect_run.py", CANDIDATE)
        self.write(self.dev / "entrega/archivos_modificados/inspect_run.py", CANDIDATE)
        self.write(self.dev / "entrega/candidato.diff", unified_diff(ORIGINAL, CANDIDATE, "a/inspect_run.py", "b/inspect_run.py"))
        workspace = tree_state(reference / "proyecto")
        before = workspace['inspect_run.py']
        after = {**before, 'sha256': digest(CANDIDATE)}
        workspace['inspect_run.py'] = after
        write_json(self.dev / "entrega/cambios.json", {'inspect_run.py': {'antes': before, 'despues': after}})
        write_json(self.dev / "entrega/workspace_despues.json", workspace)
        d = {"tarea": "inspect-json", "registro": str(self.dev), "estado": "no_supera_comprobaciones", "codigo_salida": 1,
             "error": None, "reserva_invocacion": True, "agente": {"invocaciones": 1, "proceso": agent},
             "integridad": dict.fromkeys(("original_intacto", "referencia_intacta", "registros_intactos", "alcance_respetado"), True),
             "procedencia": base, "referencia_sha256": tree_state(reference), "candidato_sha256": digest(CANDIDATE)}
        for phase in ("inicial", "posterior"):
            d[phase] = {}
            for kind in ("aceptacion", "regresion"):
                d[phase][kind] = self.report(self.dev, f'{phase}/{kind}', expected[kind],
                                             self.temp / phase, kind == 'aceptacion',
                                             reference / 'evaluar.py' if kind == 'aceptacion' else None)
        d['evidencia_sha256'] = {name: tree_state(self.dev / name) for name in ('inicial', 'agente', 'entrega')}
        write_json(self.dev / "resultado.json", d)
        ref = self.ree / 'referencia'
        shutil.copytree(reference / 'proyecto', ref / 'proyecto_base')
        for name, data in {'contrato.md': contract, 'evaluador_anterior.py': OLD, 'evaluar.py': NEW,
                           'project_test_runner.py': runner,
                           'evaluador.diff': unified_diff(OLD, NEW, 'a/evaluar.py', 'b/evaluar.py'),
                           'comprobaciones/' + controller.SPECIFIC: SPECIFIC,
                           'comprobaciones/' + controller.ACCEPTANCE: NEW}.items():
            self.write(ref / name, data)
        write_json(ref / 'procedencia_original.json', base)
        self.write(self.ree / 'entrega/inspect_run.py', CANDIDATE)
        write_json(self.ree / 'proyecto_evaluado_sha256.json', workspace)
        shutil.copytree(self.dev / 'posterior/regresion', self.ree / 'regresion_historica')
        fresh = {'aceptacion': static_test_ids(NEW, '__main__'),
                 'comprobaciones': static_test_ids(SPECIFIC, 'test_inspect_json_evaluator')}
        reuse = {'ejecutada_ahora': False, 'registro': 'runs/desarrollo/posterior/regresion',
                 'evaluacion_historica': d['posterior']['regresion']}
        hashes = {'candidato': digest(CANDIDATE), 'contrato': digest(contract), 'evaluador_anterior': digest(OLD),
                  'evaluador_revisado': digest(NEW), 'adaptador_pruebas': digest(runner), 'comprobaciones': digest(SPECIFIC),
                  'diff_evaluador': digest((ref / 'evaluador.diff').read_bytes()),
                  'resultado_origen': digest((self.dev / 'resultado.json').read_bytes())}
        p = {'tipo': controller.REEVALUATION, 'registro_origen': 'runs/desarrollo',
             'resultado_origen': {'estado': d['estado'], 'codigo_salida': 1}, 'commit_base': self.base,
             'head_origen': self.base, 'sha256': hashes, 'pruebas_esperadas': fresh, 'regresion_reutilizada': reuse}
        write_json(self.ree / 'procedencia.json', p)
        r = {'tipo': controller.REEVALUATION, 'registro': str(self.ree), 'registro_origen': 'runs/desarrollo',
             'estado': 'supera_aceptacion_revisada_y_comprobaciones', 'codigo_salida': 0,
             'invocaciones_nuevas': {'desarrollador': 0, 'revisor': 0}, 'regresion_reutilizada': reuse,
             'integridad': dict.fromkeys(('mismo_workspace_entregado', 'copia_evaluada_intacta', 'registros_previos_intactos',
                                         'referencia_intacta', 'original_intacto', 'mismo_candidato'), True),
             'evaluaciones_nuevas': {}}
        for kind in fresh:
            r['evaluaciones_nuevas'][kind] = self.report(self.ree, kind, fresh[kind],
                self.temp / 'reevaluada' if kind == 'aceptacion' else ref / 'comprobaciones',
                False, ref / 'evaluar.py' if kind == 'aceptacion' else None)
        write_json(self.ree / 'resultado.json', r)
        self.seal()
        self.settings = self.temp / 'opciones.json'
        self.calls = self.temp / 'llamadas.jsonl'
        self.fake = self.temp / 'codex'
        self.configure()
        self.addCleanup(patch.stopall)
        patch.object(review_case, 'CODEX_EXECUTABLE', str(self.fake)).start()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True, timeout=10).stdout

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, path):
        return json.loads(path.read_text())

    def report(self, record, name, expected, project, failed, acceptance):
        directory = record / name
        directory.mkdir(parents=True)
        cmd = [sys.executable, '-B', str(record / 'referencia/project_test_runner.py'),
               '--project', str(project), '--report', str(directory / 'pruebas.json')]
        if acceptance:
            cmd += ['--acceptance', str(acceptance)]
        process = {'comando': cmd, 'directorio_trabajo': str(project), 'estado': 'finalizada',
                   'codigo_salida': int(failed), 'error': None, 'duracion_segundos': 0.1}
        report = {'version': 1, 'completo': True, 'sesiones': 1, 'metodos': expected, 'terminados': expected,
                  'total': len(expected), 'fallos': [{'metodo': expected[0], 'subtest': '(valor=True)'}] if failed else [],
                  'errores': [], 'omitidos': [], 'esperados': [], 'inesperados': []}
        evaluation = {'proceso': process, 'workspace_intacto': True, 'metodos': len(expected),
                      'clasificacion': 'fallos_asercion' if failed else 'superadas', 'aserciones_fallidas': int(failed),
                      'metodos_con_fallos': int(failed), 'fallos_subtest': int(failed), 'errores': 0}
        write_json(directory / 'resultado.json', process)
        write_json(directory / 'pruebas.json', report)
        write_json(directory / 'evaluacion.json', evaluation)
        self.write(directory / 'stdout.txt', b'')
        # Informes sintéticos declarados como datos; no representan ejecuciones reales.
        self.write(directory / 'stderr.txt', (f'Ran {len(expected)} tests in 0.001s\n\n'
                                            + ('FAILED (failures=1)' if failed else 'OK') + '\n').encode())
        return evaluation

    def seal(self):
        write_json(self.ree / 'referencia_sha256.json', tree_state(self.ree / 'referencia'))
        write_json(self.ree / 'evidencia_sha256.json', {name: tree_state(self.ree / name)
                   for name in ('aceptacion', 'comprobaciones', 'entrega', 'regresion_historica')})

    def configure(self, **options):
        self.settings.write_text(json.dumps(options))
        self.fake.write_text(f'''#!{sys.executable}
import json
from pathlib import Path
import sys
import time
options = json.loads(Path({str(self.settings)!r}).read_text())
args = sys.argv[1:]
if args == ['--version']:
    print('codex-simulado 1.0'); sys.exit(0)
if args == ['exec', '--help']:
    print('incompatible' if options.get('incompatible') else {HELP!r}); sys.exit(0)
assert args[0] == 'exec' and args[-1] == '-'
prompt = sys.stdin.read()
workspace = Path.cwd()
with Path({str(self.calls)!r}).open('a') as out:
    out.write(json.dumps({{'args': args, 'workspace': str(workspace), 'prompt': prompt,
                          'files': sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob('*'))}}) + '\\n')
print('{{"type":"evento_simulado"}}', flush=True)
if options.get('mutation') == 'file': (workspace/'inspect_run.py').write_text('alterado')
if options.get('mutation') == 'directory': (workspace/'directorio_nuevo').mkdir()
if options.get('mutation') == 'mode': (workspace/'inspect_run.py').chmod(0o777)
if options.get('external'): Path(options['external']).write_text('alterado')
if options.get('block'): time.sleep(30)
if not options.get('missing'):
    Path(args[args.index('--output-last-message')+1]).write_text(options.get('raw', json.dumps({APPROVE!r})))
sys.exit(options.get('code', 0))
''')
        self.fake.chmod(0o755)

    def run_review(self, **kwargs):
        return controller.run_review(self.dev, self.ree, self.root, **kwargs)

    def test_aprobacion_sesion_nueva_materiales_silencio_e_integridad(self):
        before = tree_state(self.root, filter_local=True)
        self.write(self.dev / 'agente/explicacion_extra.txt', b'PRIVADO')
        d = self.read(self.dev / 'resultado.json')
        d['evidencia_sha256']['agente'] = tree_state(self.dev / 'agente')
        write_json(self.dev / 'resultado.json', d)
        p = self.read(self.ree / 'procedencia.json')
        p['sha256']['resultado_origen'] = digest((self.dev / 'resultado.json').read_bytes())
        write_json(self.ree / 'procedencia.json', p)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = self.run_review()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(out.getvalue() + err.getvalue(), '')
        self.assertEqual(tree_state(self.root, filter_local=True), before)
        self.assertTrue(all(result['integridad'].values()))
        self.assertEqual(result['contraste_semantico'], 'pendiente')
        self.assertEqual(result['revisor']['invocaciones'], 1)
        self.assertEqual(result['revisor']['limite_segundos'], 180)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertIn('read-only', calls[0]['args'])
        self.assertIn('--ephemeral', calls[0]['args'])
        self.assertNotIn('resume', calls[0]['args'])
        self.assertNotIn(self.root, Path(calls[0]['workspace']).parents)
        self.assertIn('dependencias/case_evidence.py', calls[0]['files'])
        log = Path(result['registro'])
        contents = b''.join(p.read_bytes() for p in (log/'materiales').rglob('*') if p.is_file())
        self.assertNotIn(b'NO_MOSTRAR_EXPLICACION_DESARROLLADOR', contents)
        self.assertNotIn(b'PRIVADO', contents)
        self.assertEqual(self.read(log/'origen.json')['autorizacion']['resultado_original']['codigo_salida'], 1)
        self.assertEqual((log/'materiales/inspect_run.py').read_bytes(), CANDIDATE)

    def test_solicitud_de_cambios_no_es_error_tecnico(self):
        self.configure(raw=json.dumps(CHANGE))
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 1, result)
        self.assertEqual(result['dictamen_modelo'], CHANGE)
        self.assertEqual(result['decision_controlador'], 'cambios_solicitados')

    def test_workspace_contiene_solo_seleccion_y_archivo_conserva_fuentes(self):
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 0, result)
        log = Path(result['registro'])
        context, full = log/'materiales', log/'evidencia_validada'
        expected = {'contrato.md', 'inspect_run.py', 'original/inspect_run.py', 'candidato.diff',
                    'dependencias/case_evidence.py', 'pruebas/test_inspect_run.py',
                    'evaluacion/evaluador_revisado.py', 'resumen_evidencia.json', 'respuesta.schema.json'}
        snapshot = tree_state(context)
        self.assertEqual({name for name, item in snapshot.items() if item['tipo'] == 'archivo'}, expected)
        self.assertTrue(all(item['tipo'] in ('archivo', 'directorio') for item in snapshot.values()))
        call, = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(set(call['files']), set(snapshot))
        self.assertEqual(result['contexto']['archivos'], len(expected))
        self.assertEqual(result['contexto']['bytes'], sum((context/name).stat().st_size for name in expected))
        self.assertEqual((context/'pruebas/test_inspect_run.py').read_bytes(), REGRESSION)
        self.assertEqual((context/'evaluacion/evaluador_revisado.py').read_bytes(), NEW)
        self.assertEqual((full/'regresion/tests/test_general.py').read_bytes(), GENERAL)
        self.assertEqual((full/'evaluacion/evaluador_anterior.py').read_bytes(), OLD)
        for label, record in (('desarrollo', self.dev), ('reevaluacion', self.ree)):
            self.assertEqual((full/'registros'/label/'resultado.json').read_bytes(), (record/'resultado.json').read_bytes())
        mapping = self.read(log/'seleccion.json')
        self.assertEqual(set(mapping['materiales']), expected)
        for name, item in mapping['materiales'].items():
            self.assertEqual(item['sha256'], digest((context/name).read_bytes()))
            if item['fuente']:
                self.assertEqual((context/name).read_bytes(), (full/item['fuente']).read_bytes())
        for source, checksum in mapping['resumen']['fuentes_sha256'].items():
            self.assertEqual(digest((full/source).read_bytes()), checksum)
        self.assertEqual(tree_state(full), result['evidencia_sha256'])
        self.assertEqual(digest((log/'seleccion.json').read_bytes()), result['contexto']['seleccion_sha256'])
        summary = (context/'resumen_evidencia.json').read_bytes()
        for path in (self.root, self.dev, self.ree):
            self.assertNotIn(str(path).encode(), summary)
        self.assertNotIn(b'../', summary)
        self.assertNotIn(b'file://', summary)

    def test_resumen_determinista_distingue_metodos_subtests_y_reutilizacion(self):
        # Dos aserciones de subtests en el mismo método; nunca contarlas como dos métodos.
        folder = self.dev/'posterior/aceptacion'
        report = self.read(folder/'pruebas.json')
        report['fallos'].append({'metodo': report['metodos'][0], 'subtest': '(valor=-1)'})
        write_json(folder/'pruebas.json', report)
        evaluation = self.read(folder/'evaluacion.json')
        evaluation.update(aserciones_fallidas=2, fallos_subtest=2)
        write_json(folder/'evaluacion.json', evaluation)
        (folder/'stderr.txt').write_text('Ran 1 test in 0.001s\n\nFAILED (failures=2)\n')
        d = self.read(self.dev/'resultado.json')
        d['posterior']['aceptacion'] = evaluation
        write_json(self.dev/'resultado.json', d)
        p = self.read(self.ree/'procedencia.json')
        p['sha256']['resultado_origen'] = digest((self.dev/'resultado.json').read_bytes())
        write_json(self.ree/'procedencia.json', p)
        evidence, authorization, _ = controller.validate_evidence(self.dev, self.ree, self.root)
        first, mapping = controller.review_materials(evidence, authorization)
        second, _ = controller.review_materials(dict(reversed(list(evidence.items()))), authorization)
        self.assertEqual(first, second)
        summary = json.loads(first['resumen_evidencia.json'])
        self.assertEqual(summary['procedencia']['resultado_desarrollo']['codigo_salida'], 1)
        self.assertEqual(summary['procedencia']['resultado_reevaluacion']['codigo_salida'], 0)
        self.assertEqual(summary['sha256'], authorization['sha256'])
        for key, sources in mapping['resumen']['evaluaciones'].items():
            original = json.loads(evidence[sources[0]])
            saved = summary['evaluaciones'][key]
            for field in ('metodos', 'metodos_con_fallos', 'aserciones_fallidas', 'fallos_subtest', 'errores', 'clasificacion'):
                self.assertEqual(saved[field], original[field])
            self.assertEqual(saved['codigo_salida'], original['proceso']['codigo_salida'])
            self.assertEqual(saved['metodos_correctos'], original['metodos'] - original['metodos_con_fallos'])
        after = summary['evaluaciones']['aceptacion_original_entrega']
        self.assertEqual((after['metodos'], after['metodos_con_fallos'], after['aserciones_fallidas'], after['fallos_subtest']),
                         (1, 1, 2, 2))
        self.assertEqual(summary['evaluaciones']['aceptacion_revisada']['metodos_correctos'], 1)
        self.assertEqual(summary['evaluaciones']['regresion_entrega_reutilizada']['metodos_correctos'], 2)
        self.assertIs(summary['regresion_reutilizada']['ejecutada_en_reevaluacion'], False)
        self.assertNotIn('dictamen_modelo', summary)
        self.assertFalse(self.calls.exists())

    def test_dependencias_de_pruebas_y_transitivas_se_conservan_sin_ejecutar(self):
        files = {'helper.py': b'import nested\nraise RuntimeError("NO EJECUTAR")\n',
                 'nested.py': b'raise RuntimeError("NO EJECUTAR")\n', 'ajeno.py': b'NO LEER'}
        read = []
        def source(name):
            read.append(name)
            return files[name]
        selected = controller.review_dependencies([b'import helper\n'], files, source)
        self.assertEqual(set(selected), {'dependencias/helper.py', 'dependencias/nested.py'})
        self.assertEqual(set(read), {'helper.py', 'nested.py'})
        with patch.object(controller, 'review_dependencies', wraps=controller.review_dependencies) as gather:
            controller.validate_evidence(self.dev, self.ree, self.root)
        roots = gather.call_args.args[0]
        self.assertTrue(all(data in roots for data in (ORIGINAL, CANDIDATE, REGRESSION, NEW)))
        for data in (b'import desconocido\n', b'from . import helper\n', b'__import__("helper")\n'):
            with self.subTest(importacion=data), self.assertRaises(ValueError):
                controller.review_dependencies([data], files, source)

    def test_informe_excluido_del_modelo_sigue_validandose(self):
        # Actualizar inventarios y resúmenes no debe hacer admisible una regresión omitida.
        report = self.read(self.dev/'posterior/regresion/pruebas.json')
        report['omitidos'] = [report['metodos'][0]]
        for path in (self.dev/'posterior/regresion/pruebas.json', self.ree/'regresion_historica/pruebas.json'):
            write_json(path, report)
        self.seal()
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIsNone(result['registro'])
        self.assertFalse(self.calls.exists())

    def test_alterar_archivo_completo_o_correspondencia_impide_aprobar(self):
        for name, flag in (('evidencia_validada/evidencia/desarrollo/posterior/regresion/stderr.txt', 'evidencia_completa_intacta'),
                           ('seleccion.json', 'seleccion_intacta')):
            def mutate(workspace, final, prompt, log, *, on_invoke):
                on_invoke()
                (log.parent/name).write_text('alterado')
                final.write_text(json.dumps(APPROVE))
                return {'estado': 'finalizada', 'codigo_salida': 0, 'invocaciones': 1}
            with self.subTest(archivo=name), patch.object(controller, 'invoke_reviewer', side_effect=mutate):
                result = self.run_review()
                self.assertEqual(result['codigo_salida'], 6, result)
                self.assertFalse(result['integridad'][flag])
                self.assertIsNone(result['dictamen_modelo'])

    def test_evidencia_ausente_alterada_o_mezclada_no_invoca(self):
        paths = [self.dev/'entrega/inspect_run.py', self.dev/'entrega/candidato.diff',
                 self.dev/'referencia/contrato.md', self.dev/'referencia/proyecto/tests/test_general.py',
                 self.ree/'referencia/evaluador.diff', self.ree/'regresion_historica/stderr.txt',
                 self.ree/'aceptacion/pruebas.json', self.root/controller.ACCEPTANCE]
        for path in paths:
            with self.subTest(archivo=str(path)):
                data = path.read_bytes()
                try:
                    path.write_bytes(b'alterado')
                    result = self.run_review()
                    self.assertEqual(result['codigo_salida'], 7, result)
                    self.assertIsNone(result['registro'])
                finally:
                    path.write_bytes(data)
        path = self.ree/'aceptacion/stdout.txt'
        path.unlink()
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_origen_distinto_no_invoca(self):
        p = self.read(self.ree/'procedencia.json')
        p['registro_origen'] = 'runs/otro'
        write_json(self.ree/'procedencia.json', p)
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_enlaces_en_evidencia_no_se_siguen(self):
        (self.ree/'enlace').symlink_to(self.temp)
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_resultado_original_no_puede_reescribirse_como_aceptado(self):
        d = self.read(self.dev/'resultado.json')
        d.update(estado='supera_las_comprobaciones_disponibles', codigo_salida=0)
        write_json(self.dev/'resultado.json', d)
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_manifest_coherente_no_oculta_omision_de_prueba(self):
        path = self.ree/'aceptacion/pruebas.json'
        report = self.read(path)
        report['omitidos'] = [report['metodos'][0]]
        write_json(path, report)
        self.seal()
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_comando_mezclado_aunque_coincidan_los_resumenes(self):
        path = self.ree/'aceptacion/resultado.json'
        process = self.read(path)
        process['comando'][4] = '/tmp/otro-candidato'
        write_json(path, process)
        evaluation = self.read(self.ree/'aceptacion/evaluacion.json')
        evaluation['proceso'] = process
        write_json(self.ree/'aceptacion/evaluacion.json', evaluation)
        r = self.read(self.ree/'resultado.json')
        r['evaluaciones_nuevas']['aceptacion'] = evaluation
        write_json(self.ree/'resultado.json', r)
        self.seal()
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_workspace_evaluado_de_otro_candidato(self):
        path = self.ree/'proyecto_evaluado_sha256.json'
        data = self.read(path)
        data['inspect_run.py']['sha256'] = digest(b'otro')
        write_json(path, data)
        self.assertEqual(self.run_review()['codigo_salida'], 7)
        self.assertFalse(self.calls.exists())

    def test_respuesta_invalida_o_ausente_no_aprueba(self):
        for options in ({'raw': '{}'}, {'raw': '```json\n{}\n```'}, {'missing': True}):
            with self.subTest(opciones=options):
                self.configure(**options)
                result = self.run_review()
                self.assertEqual(result['codigo_salida'], 5, result)
                self.assertIsNone(result['dictamen_modelo'])
                self.assertEqual(result['revisor']['invocaciones'], 1)

    def test_fallo_tecnico_no_aprueba_aunque_haya_json_de_aprobacion(self):
        self.configure(code=9)
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertIsNone(result['dictamen_modelo'])
        self.assertEqual(result['revisor']['codigo_salida'], 9)
        self.assertTrue((Path(result['registro'])/'revisor/respuesta_original.txt').exists())

    def test_cli_incompatible_no_reserva_invocacion(self):
        self.configure(incompatible=True)
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertFalse(result['reserva_invocacion'])
        self.assertFalse(self.calls.exists())

    def test_timeout_conserva_eventos_y_no_reintenta(self):
        self.configure(block=True)
        with patch.object(review_case, 'AGENT_TIMEOUT_SECONDS', 0.2):
            result = self.run_review()
        self.assertEqual(result['codigo_salida'], 4, result)
        self.assertEqual(result['revisor']['invocaciones'], 1)
        self.assertIn('evento_simulado', (Path(result['registro'])/'revisor/eventos.jsonl').read_text())
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_cambios_de_contenido_modos_y_directorios_impiden_aprobar(self):
        for mutation in ('file', 'directory', 'mode'):
            with self.subTest(cambio=mutation):
                self.configure(mutation=mutation)
                result = self.run_review()
                self.assertEqual(result['codigo_salida'], 6, result)
                self.assertFalse(result['integridad']['workspace_intacto'])

    def test_alteracion_de_origen_se_detecta(self):
        self.configure(external=str(self.dev/'entrega/inspect_run.py'))
        result = self.run_review()
        self.assertEqual(result['codigo_salida'], 6, result)
        self.assertFalse(result['integridad']['origenes_intactos'])

    def test_interrupcion_conserva_proceso_y_reserva(self):
        def interrupted(workspace, final, prompt, log, *, on_invoke):
            on_invoke()
            raise ProcessInterrupted({'estado': 'interrumpida', 'codigo_salida': -2})
        with patch.object(controller, 'invoke_reviewer', side_effect=interrupted):
            result = self.run_review()
        self.assertEqual(result['codigo_salida'], 9, result)
        self.assertEqual(result['revisor']['estado'], 'interrumpida')
        self.assertEqual(result['revisor']['invocaciones'], 1)
        self.assertEqual(self.read(Path(result['registro'])/'resultado.json')['codigo_salida'], 9)

    def test_cli_canales_progreso_y_argumentos(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(controller, 'PROJECT', self.root), redirect_stdout(out), redirect_stderr(err):
            code = controller.main(['--development-run', str(self.dev), '--reevaluation-run', str(self.ree)])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn('Validando desarrollo', err.getvalue())
        self.assertIn('Revisión 1/1:', err.getvalue())
        self.assertIn('Registro:', out.getvalue())
        self.assertNotIn('evento_simulado', out.getvalue() + err.getvalue())
        for args in ([], ['--development-run', str(self.dev)], ['--ignore-failures']):
            with self.subTest(argumentos=args), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    controller.main(args)
                self.assertEqual(exc.exception.code, 2)

    def test_dictamen_exige_campos_lineas_y_coherencia_sin_certificar_semantica(self):
        self.assertEqual(controller.validate_verdict(json.dumps(CHANGE).encode(), 3), CHANGE)
        invalid = [dict(APPROVE, hallazgos=CHANGE['hallazgos']), dict(CHANGE, hallazgos=[]), dict(APPROVE, extra=1)]
        for key, value in (('linea', True), ('linea', 0), ('linea', 4), ('archivo', 'candidato.py'),
                           ('requisito', ''), ('ejemplo', ' '), ('explicacion', None)):
            verdict = copy.deepcopy(CHANGE)
            verdict['hallazgos'][0][key] = value
            invalid.append(verdict)
        for verdict in invalid:
            with self.subTest(dictamen=verdict), self.assertRaises(ValueError):
                controller.validate_verdict(json.dumps(verdict).encode(), 3)
        for raw in (b'{"decision":"aprobar","decision":"aprobar"}', b'NaN', b'{}\n{}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                controller.validate_verdict(raw, 3)


if __name__ == '__main__':
    unittest.main()

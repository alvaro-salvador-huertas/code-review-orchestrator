"""Credenciales ficticias, hijos reales y Codex simulado; nunca autenticación real."""

from contextlib import contextmanager, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import process_environment as policy
import repair_case
import repair_project
import review_case
import run_case
from evals.tareas_reales.inspect_json import evaluar


ROOT = Path(__file__).resolve().parents[1]
BLOCKED = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "GITHUB_TOKEN",
    "DATABASE_PASSWORD", "UNRELATED_API_KEY", "SSH_AUTH_SOCK", "GOOGLE_APPLICATION_CREDENTIALS",
    "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "LD_PRELOAD", "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "NODE_OPTIONS", "BASH_ENV", "ENV",
    "SSLKEYLOGFILE", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS",
)
AUTH = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID")
HELP = "--config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema"


def probe_source(*, use_temporary=True):
    # Solo nombres de variables y comprobaciones booleanas, nunca sus valores.
    return f'''import json, os, pathlib, subprocess, sys, tempfile
forbidden = {BLOCKED + AUTH + ('CODEX_HOME', 'DBUS_SESSION_BUS_ADDRESS')!r}
safe = all(name not in os.environ for name in forbidden)
necessary = all(name in os.environ for name in ('PATH', 'HOME', 'TMPDIR', 'LC_ALL', 'PYTHONIOENCODING'))
directories = all(pathlib.Path(os.environ[name]).is_dir() for name in ('HOME', 'TMPDIR'))
if {use_temporary!r}:
    with tempfile.TemporaryFile() as temporary:
        temporary.write('texto con ñ'.encode('utf-8'))
usable = os.environ.get('PYTHONIOENCODING') == 'utf-8'
result = {{'sin_credenciales': safe, 'variables_necesarias': necessary,
          'directorios_disponibles': directories, 'unicode_y_temporales': usable}}
if len(sys.argv) == 1:
    child = subprocess.run([sys.executable, '-B', __file__, 'hijo'], capture_output=True, text=True, timeout=5)
    result['hijo_limpio'] = child.returncode == 0 and all(json.loads(child.stdout).values())
print(json.dumps(result))
sys.exit(0 if all(result.values()) else 1)
'''


class TestProcessEnvironment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-entornos-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.probe = self.workspace / "probe.py"
        self.probe.write_text(probe_source())
        self.secrets = {name: "FICTICIO_" + uuid4().hex for name in BLOCKED + AUTH}
        self.home = self.root / "home_simulado"
        self.home.mkdir()
        self.codex_home = self.root / "codex_simulado"
        self.codex_home.mkdir()
        self.host = {
            **self.secrets,
            **{name: os.environ[name] for name in policy.SYSTEM_VARIABLES if name in os.environ},
            'PATH': str(self.root / 'bin_ajeno') + os.pathsep + policy.base_environment()['PATH'],
            'HOME': str(self.home), 'CODEX_HOME': str(self.codex_home),
            'XDG_CONFIG_HOME': str(self.home), 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=ficticio',
        }

    def assert_clean_logs(self, directory):
        for path in directory.rglob('*'):
            if path.is_file():
                content = path.read_bytes()
                self.assertTrue(all(value.encode() not in content for value in self.secrets.values()),
                                'Un registro contiene un valor ficticio que debía excluirse')

    def test_lista_cerrada_temporales_distintos_y_entorno_padre_intacto(self):
        with patch.dict(os.environ, self.host, clear=True):
            before = dict(os.environ)
            with policy.process_environment() as first:
                first_home = Path(first['HOME'])
                self.assertTrue(first_home.is_dir())
                self.assertTrue(all(name not in first for name in BLOCKED + AUTH + ('CODEX_HOME',)))
                self.assertNotEqual(first['PATH'], self.host['PATH'])
                self.assertEqual(first['PYTHONNOUSERSITE'], '1')
                self.assertEqual(first['GIT_CONFIG_GLOBAL'], os.devnull)
                with policy.process_environment() as second:
                    self.assertNotEqual(first['HOME'], second['HOME'])
                    self.assertEqual(Path(second['TMPDIR']).parent, Path(second['HOME']).parent)
                self.assertFalse(Path(second['HOME']).exists())
            self.assertFalse(first_home.exists())
            self.assertTrue(dict(os.environ) == before, 'No modificar el entorno del padre')
        with self.assertRaises(ValueError):
            with policy.process_environment('heredar_todo'):
                self.fail('No admitir políticas implícitas')

    def test_run_process_filtra_hijo_y_nieto_sin_valores_en_registros(self):
        log = self.root / 'proceso'
        with patch.dict(os.environ, self.host, clear=True):
            result = repair_case.run_process([sys.executable, '-B', str(self.probe)], self.workspace, log, 10)
        self.assertEqual(result['codigo_salida'], 0)
        self.assertEqual(result['politica_entorno'], 'evaluation')
        self.assertEqual((log / 'stderr.txt').read_bytes(), b'')
        self.assertTrue(all(json.loads((log / 'stdout.txt').read_text()).values()))
        self.assert_clean_logs(log)

    def test_no_carga_pythonpath_ni_site_del_usuario(self):
        trap = self.root / 'site_ajeno'
        trap.mkdir()
        marker = self.root / 'carga_no_permitida'
        source = f'from pathlib import Path\nPath({str(marker)!r}).touch()\n'
        (trap / 'sitecustomize.py').write_text(source)
        site = self.home / '.local/lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
        site.mkdir(parents=True)
        (site / 'usercustomize.py').write_text(source)
        with patch.dict(os.environ, {**self.host, 'PYTHONPATH': str(trap)}, clear=True):
            result = repair_case.run_process([sys.executable, '-B', str(self.probe)], self.workspace,
                                             self.root / 'carga', 10)
        self.assertEqual(result['codigo_salida'], 0)
        self.assertFalse(marker.exists())

    def benchmark_sources(self):
        return ("import runpy\nrunpy.run_path('probe.py', run_name='__main__')\n".encode(),
                b'import unittest\nclass TestProbe(unittest.TestCase):\n'
                b'    def test_probe(self):\n'
                b'        import subprocess, sys\n'
                b'        self.assertEqual(subprocess.call([sys.executable, "-B", "solution.py"]), 0)\n')

    def test_evaluacion_benchmark_tambien_filtra_descendientes(self):
        # El candidato lleva su propia sonda; no importa nada del proceso controlador.
        solution, tests = probe_source().encode(), self.benchmark_sources()[1]
        log = self.root / 'benchmark'
        with patch.dict(os.environ, self.host, clear=True):
            result = repair_case.evaluate(solution, tests, log)
        self.assertEqual(result['codigo_salida'], 0)
        self.assert_clean_logs(log)

    def test_run_case_directo_tiene_la_misma_politica(self):
        project = self.root / 'proyecto'
        benchmark = project / 'benchmark/case_01'
        benchmark.mkdir(parents=True)
        (project / 'tasks').mkdir()
        (project / 'tasks' / run_case.CASES['case_01']).write_text('Contrato sintético')
        (benchmark / 'solution.py').write_text(probe_source())
        (benchmark / 'test_solution.py').write_bytes(self.benchmark_sources()[1])
        with patch.dict(os.environ, self.host, clear=True), redirect_stdout(io.StringIO()):
            code = run_case.run_case('case_01', project)
        directory, = (project / 'runs').iterdir()
        result = json.loads((directory / 'resultado.json').read_text())
        self.assertEqual(code, 0)
        self.assertEqual(result['codigo_salida_pruebas'], 0)
        self.assertEqual(result['politica_entorno'], 'evaluation')
        self.assert_clean_logs(directory)

    def test_proyecto_aceptacion_y_regresion_reciben_entorno_minimo(self):
        frozen = self.root / 'referencia'
        frozen.mkdir()
        shutil.copy2(ROOT / 'project_test_runner.py', frozen / 'project_test_runner.py')
        source = '''import subprocess, sys, unittest
from pathlib import Path
class TestProbe(unittest.TestCase):
    def test_probe(self):
        self.assertEqual(subprocess.call([sys.executable, '-B', str(Path.cwd()/'probe.py')]), 0)
'''
        (self.workspace / 'tests').mkdir()
        (self.workspace / 'tests/test_probe.py').write_text(source)
        (frozen / 'evaluar.py').write_text(source + '''
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestProbe))
sys.exit(0 if result.wasSuccessful() else 1)
''')
        expected = {'aceptacion': ['__main__.TestProbe.test_probe'],
                    'regresion': ['test_probe.TestProbe.test_probe']}
        results = {}
        log = self.root / 'proyecto'
        with patch.dict(os.environ, self.host, clear=True):
            repair_project.evaluate(self.workspace, frozen, log, expected, results, None, lambda: None)
        self.assertEqual(set(results), {'aceptacion', 'regresion'})
        for result in results.values():
            self.assertEqual(result['clasificacion'], 'superadas')
            self.assertEqual(result['proceso']['politica_entorno'], 'evaluation')
            self.assertTrue(result['workspace_intacto'])
        self.assert_clean_logs(log)

    def test_evaluador_externo_conservado_ya_filtra_hijo_y_nieto(self):
        # No ejecutar la entrega real ni cambiar el evaluador congelado.
        # El inspector solo consulta: crear temporales aquí alteraría el mtime
        # de tmp y el evaluador lo rechazaría correctamente por integridad.
        (self.workspace / 'inspect_run.py').write_text(probe_source(use_temporary=False))
        case = evaluar.AcceptanceTests('test_10_tipos_invalidos_no_se_convierten')
        case.project = self.workspace
        case.setUp()
        self.addCleanup(case.doCleanups)
        with patch.dict(os.environ, self.host, clear=True):
            completed = case.call()
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(all(json.loads(completed.stdout).values()))
        self.assertEqual(completed.stderr, '')

    def fake_codex(self):
        path = self.root / 'codex_simulado.py'
        expected = {name: hashlib.sha256(self.host[name].encode()).hexdigest() for name in AUTH}
        path.write_text(f'''#!{sys.executable}
import hashlib, json, os, pathlib, sys
expected = {expected!r}
authenticated = all(hashlib.sha256(os.environ.get(name, '').encode()).hexdigest() == value for name, value in expected.items())
clean = all(name not in os.environ for name in {BLOCKED!r})
located = os.environ.get('HOME') == {str(self.home)!r} and os.environ.get('CODEX_HOME') == {str(self.codex_home)!r}
if not (authenticated and clean and located):
    print('Política incorrecta; valores omitidos', file=sys.stderr)
    sys.exit(19)
args = sys.argv[1:]
if args == ['--version']: print('codex simulado')
elif args == ['exec', '--help']: print({HELP!r})
else:
    sys.stdin.read()
    pathlib.Path(args[args.index('--output-last-message')+1]).write_text('Respuesta simulada')
    print(json.dumps({{'autenticacion_ficticia_disponible': True, 'credenciales_ajenas_ausentes': True}}))
''')
        path.chmod(0o755)
        return path

    def test_tres_lanzadores_codex_conservan_solo_autenticacion_prevista(self):
        fake = self.fake_codex()
        for name in ('benchmark', 'revision', 'proyecto'):
            with self.subTest(lanzador=name):
                log = self.root / ('codex_' + name)
                with patch.dict(os.environ, self.host, clear=True):
                    if name == 'proyecto':
                        result = {'agente': {}}
                        with patch.object(repair_project, 'CODEX_EXECUTABLE', str(fake)):
                            repair_project.develop(self.workspace, log, b'Encargo simulado', result, None, lambda: None)
                        agent = result['agente']['proceso']
                    else:
                        log.mkdir()
                        module = repair_case if name == 'benchmark' else review_case
                        invoke = module.invoke_codex if name == 'benchmark' else module.invoke_reviewer
                        with patch.object(module, 'CODEX_EXECUTABLE', str(fake)):
                            agent = invoke(self.workspace, log / 'respuesta.txt', b'Encargo simulado', log)
                    # La evaluación posterior vuelve a filtrar la autenticación del mismo padre.
                    evaluated = repair_case.run_process([sys.executable, '-B', str(self.probe)],
                                                        self.workspace, log / 'evaluacion', 10)
                self.assertEqual(agent['codigo_salida'], 0)
                self.assertEqual(agent['politica_entorno'], 'codex')
                self.assertEqual(evaluated['codigo_salida'], 0)
                for stage in ('version', 'ayuda'):
                    self.assertEqual(json.loads((log / stage / 'resultado.json').read_text())['politica_entorno'], 'codex')
                self.assert_clean_logs(log)

    def test_timeout_y_error_inicio_limpian_directorios_y_conservan_resultado(self):
        homes = []
        @contextmanager
        def traced(policy_name):
            with policy.process_environment(policy_name) as environment:
                homes.append(Path(environment['HOME']))
                yield environment
        with patch.dict(os.environ, self.host, clear=True), patch.object(repair_case, 'process_environment', traced):
            timeout = repair_case.run_process([sys.executable, '-B', '-c',
                "import time; print('salida parcial', flush=True); time.sleep(20)"],
                self.workspace, self.root / 'timeout', 0.3)
            absent = repair_case.run_process([str(self.root / 'inexistente')], self.workspace,
                                             self.root / 'ausente', 1)
        self.assertEqual(timeout['estado'], 'tiempo_agotado')
        self.assertEqual(absent['estado'], 'ausente')
        self.assertEqual((self.root / 'timeout/stdout.txt').read_text(), 'salida parcial\n')
        self.assertTrue(all(not path.exists() for path in homes))
        self.assert_clean_logs(self.root / 'timeout')
        self.assert_clean_logs(self.root / 'ausente')


if __name__ == '__main__':
    unittest.main(verbosity=2)

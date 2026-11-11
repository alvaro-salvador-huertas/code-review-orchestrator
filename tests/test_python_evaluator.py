"""Pruebas unitarias con runtime simulado; no demuestran aislamiento real."""

import json
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import orchestrate_project
import project_flow
import python_evaluator as sandbox
from process_environment import process_environment
from repair_case import run_process, write_json


class PythonEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.log = self.root / 'log'
        self.marker = self.root / 'HOST_EXECUTED'
        self.command = [sys.executable, '-B', '-c',
                        f'from pathlib import Path; Path({str(self.marker)!r}).touch()']

    def test_runtime_ausente_no_ejecuta_candidato(self):
        with patch.object(sandbox, 'runtime_call', side_effect=FileNotFoundError('podman ausente')), \
             patch.object(sandbox, 'os') as system:
            system.geteuid.return_value = 1000
            result = sandbox.run_isolated(self.command, self.project, self.log, 1,
                                           materials=(), runner=run_process)
        self.assertEqual(result['estado'], 'error_inicio')
        self.assertIn('podman ausente', result['error'])
        self.assertFalse(self.marker.exists())
        self.assertEqual(json.loads((self.log/'resultado.json').read_text()), result)

    def test_arranque_fallido_no_ejecuta_candidato(self):
        calls = []
        def failing_runner(command, workspace, log, timeout, **kwargs):
            calls.append(command)
            self.assertEqual(command[0], 'podman')
            (log/'stderr.txt').write_text('newuidmap: Operation not permitted\n')
            return {'estado': 'finalizada', 'codigo_salida': 125, 'error': None}
        with patch.object(sandbox, 'require_runtime'), patch.object(sandbox, 'cleanup') as cleanup:
            result = sandbox.run_isolated(self.command, self.project, self.log, 1,
                                           materials=(), runner=failing_runner)
        self.assertEqual(result['estado'], 'error_inicio')
        self.assertIn('aislamiento exigido', result['error'])
        cleanup.assert_called_once_with(result['aislamiento']['contenedor'])
        self.assertFalse(self.marker.exists())
        self.assertEqual(len(calls), 1)

    def test_limites_red_montajes_y_entorno_runtime(self):
        command = sandbox.container_command('cro-eval-unit', self.command, self.project,
                         [(self.project, self.project, False), (self.root/'out', self.log, True)])
        for flag in ('--pull=never', '--network=none', '--cap-drop=ALL', '--read-only',
                     '--security-opt=no-new-privileges', '--memory=512m', '--pids-limit=128',
                     '--memory-swap=512m', '--http-proxy=false', '--cgroupns=private'):
            self.assertIn(flag, command)
        self.assertIn(sandbox.IMAGE, command)
        self.assertIn('ro=true', command[command.index('--mount')+1])
        with patch.dict(os.environ, {'OPENAI_API_KEY':'SYNTHETIC', 'CONTAINER_HOST':'unix:///bad',
                                     'CONTAINERS_CONF':'/bad', 'HTTP_PROXY':'SYNTHETIC'}):
            with process_environment('podman') as env:
                self.assertNotIn('OPENAI_API_KEY', env)
                self.assertNotIn('CONTAINER_HOST', env)
                self.assertNotIn('HTTP_PROXY', env)
                self.assertNotEqual(env['CONTAINERS_CONF'], '/bad')
                self.assertEqual((Path(env['XDG_CONFIG_HOME'])/'containers/mounts.conf').read_text(), '')

    def test_timeout_limpia_contenedor_y_conserva_diagnostico(self):
        def timed_out(*args, **kwargs):
            return {'estado':'tiempo_agotado', 'codigo_salida':-9, 'error':None}
        with patch.object(sandbox, 'require_runtime'), patch.object(sandbox, 'cleanup') as cleanup:
            result = sandbox.run_isolated(self.command, self.project, self.log, .1,
                                           materials=(), runner=timed_out)
        self.assertEqual(result['estado'], 'tiempo_agotado')
        self.assertTrue(result['aislamiento']['limpieza_confirmada'])
        cleanup.assert_called_once()
        self.assertFalse(self.marker.exists())

    def test_limpieza_no_confirmada_detiene(self):
        with patch.object(sandbox, 'require_runtime'), \
             patch.object(sandbox, 'cleanup', side_effect=RuntimeError('proceso vivo')):
            result = sandbox.run_isolated(self.command, self.project, self.log, 1, materials=(),
                runner=lambda *a, **k: {'estado':'finalizada', 'codigo_salida':0})
        self.assertEqual(result['estado'], 'error_inicio')
        self.assertFalse(result['aislamiento']['limpieza_confirmada'])
        self.assertIn('proceso vivo', result['error'])

    def test_salida_hostil_no_sigue_enlaces(self):
        source = self.root/'output'
        source.mkdir()
        (source/'pruebas.json').symlink_to(self.marker)
        with self.assertRaisesRegex(ValueError, 'no regular'):
            sandbox.collect_output(source, self.root)
        self.assertFalse(self.marker.exists())

    def test_validacion_rechaza_montajes_o_controles_alterados(self):
        output = self.root/'output'
        stamp = {'version':1, 'runtime':'podman-rootless', 'imagen':sandbox.IMAGE,
                 'contenedor':'cro-eval-unit', 'limpieza_confirmada':True,
                 'salida_temporal':str(output)}
        mounts = [(self.project, self.project, False), (output, self.log, True)]
        stamp['comando_runtime'] = sandbox.container_command('cro-eval-unit', self.command,
                                                             self.project, mounts)
        result = {'comando':self.command, 'directorio_trabajo':str(self.project), 'aislamiento':stamp}
        sandbox.validate_isolation(result, materials=(), log=self.log)
        stamp['comando_runtime'][stamp['comando_runtime'].index('--network=none')] = '--network=host'
        with self.assertRaisesRegex(ValueError, 'Controles o montajes'):
            sandbox.validate_isolation(result, materials=(), log=self.log)

    def test_runtime_rootful_o_sin_cgroups_no_se_admite(self):
        for rootless, version in ((False, 'v2'), (True, 'v1')):
            info = subprocess.CompletedProcess([], 0, json.dumps(
                {'host':{'security':{'rootless':rootless}, 'cgroupVersion':version}}), '')
            with self.subTest(rootless=rootless, version=version), \
                 patch.object(sandbox.os, 'geteuid', return_value=1000), \
                 patch.object(sandbox, 'runtime_call', return_value=info):
                with self.assertRaisesRegex(RuntimeError, 'cgroups v2'):
                    sandbox.require_runtime()

    def test_sonda_rechaza_controles_inefectivos_antes_de_exec(self):
        status = 'NoNewPrivs: 1\nCapEff: 00000000\nSeccomp: 2\n'
        valid = {'/proc/self/status': status, '/proc/self/cgroup': '0::/\n',
                 '/sys/fs/cgroup/memory.max': str(sandbox.MEMORY),
                 '/sys/fs/cgroup/pids.max': str(sandbox.PIDS),
                 '/sys/fs/cgroup/memory.swap.max': '0'}
        failures = ({'/sys/fs/cgroup/memory.max':'max'}, {'/sys/fs/cgroup/pids.max':'max'},
                    {'/sys/fs/cgroup/memory.swap.max':'max'},
                    {'/proc/self/status':status.replace('NoNewPrivs: 1', 'NoNewPrivs: 0')},
                    {'/proc/self/status':status.replace('00000000', '00000001')},
                    {'/proc/self/status':status.replace('Seccomp: 2', 'Seccomp: 0')})
        for changed in failures:
            files = {**valid, **changed}
            with self.subTest(changed=changed), patch.object(os, 'getuid', return_value=1000), \
                 patch.object(os, 'listdir', return_value=['lo']), \
                 patch.object(Path, 'read_text', lambda p: files[str(p)]), \
                 patch.object(os, 'execve') as execute, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    exec(sandbox.BOOTSTRAP, {})
                self.assertEqual(stopped.exception.code, 125)
                execute.assert_not_called()

    def test_controlador_se_detiene_antes_del_descubrimiento_y_candidato(self):
        # Base Git y autoridades reales del fixture; solo el runtime está simulado.
        from test_orchestrate_project import ProjectFlowTests
        fixture = ProjectFlowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        candidate = fixture.root/'inspect_run.py'
        candidate.write_text(f'from pathlib import Path; Path({str(self.marker)!r}).touch()')
        fixture.git('add', 'inspect_run.py')
        fixture.commit_base()
        # Retirar la sustitución del evaluador que ese fixture instala.
        with patch.object(project_flow, 'run_isolated', sandbox.run_isolated), \
             patch.object(sandbox, 'runtime_call', side_effect=FileNotFoundError('podman ausente')):
            result = orchestrate_project.run_orchestration(root=fixture.root)
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertIn('podman ausente', result['error'])
        self.assertEqual(result['invocaciones']['total'], 0)
        self.assertFalse(self.marker.exists())

    def test_controlador_arranque_rechazado_no_ejecuta_candidato(self):
        from test_orchestrate_project import ProjectFlowTests
        fixture = ProjectFlowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write('inspect_run.py', f'from pathlib import Path; Path({str(self.marker)!r}).touch()')
        fixture.git('add', 'inspect_run.py')
        fixture.commit_base()
        def refused(command, workspace, log, timeout, **kwargs):
            self.assertEqual(command[0], 'podman')
            (log/'stderr.txt').write_text('Fallo sintético al aplicar los controles\n')
            return {'estado':'finalizada', 'codigo_salida':125, 'error':None}
        with patch.object(project_flow, 'run_isolated', sandbox.run_isolated), \
             patch.object(sandbox, 'require_runtime'), patch.object(sandbox, 'cleanup'), \
             patch.object(project_flow, 'run_process', side_effect=refused):
            result = orchestrate_project.run_orchestration(root=fixture.root)
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertEqual(result['invocaciones']['total'], 0)
        self.assertFalse(self.marker.exists())

    def test_controlador_detiene_inventario_antes_de_importar_base(self):
        from test_export_csv_flow import ExportCsvFlowTests
        fixture = ExportCsvFlowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write('tests/test_hostile.py',
                      f'from pathlib import Path\nPath({str(self.marker)!r}).touch()\n')
        fixture.git('add', 'tests/test_hostile.py')
        fixture.commit_base()
        fixture.select_base()
        with patch.object(project_flow, 'CSV_BASE', fixture.base), \
             patch.object(project_flow, 'run_isolated', sandbox.run_isolated), \
             patch.object(sandbox, 'runtime_call', side_effect=FileNotFoundError('podman ausente')):
            result = orchestrate_project.run_orchestration('export-csv', fixture.root)
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertEqual(result['inicial'], {})
        self.assertEqual(result['invocaciones']['total'], 0)
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()

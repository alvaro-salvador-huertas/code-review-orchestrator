"""Integración opt-in: CRO_REAL_PODMAN=1. Nunca sustituye el contenedor.

Con la opción activa, un runtime ausente o roto produce un fallo, no un skip.
Los agentes son fixtures sintéticos; el inventario/evaluador usa Podman real.
"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import project_flow
import python_evaluator as sandbox
from repair_case import run_process


@unittest.skipUnless(os.environ.get('CRO_REAL_PODMAN') == '1', 'integración real opt-in: CRO_REAL_PODMAN=1')
class RealPythonIsolationTests(unittest.TestCase):
    def test_1_candidato_valido_completa_orquestacion(self):
        from test_orchestrate_project import ProjectFlowTests
        fixture = ProjectFlowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        (fixture.root/'python_evaluator.py').write_text(Path(sandbox.__file__).read_text())
        with patch.object(project_flow, 'run_isolated', sandbox.run_isolated):
            result = fixture.run_flow()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertTrue(result['lista_para_revision_humana'])
        self.assertEqual(result['incorporacion'], 'no_realizada')
        for stage in result['inicial'].values():
            self.assertTrue(stage['proceso']['aislamiento']['limpieza_confirmada'])

    def test_2_senuelo_y_destino_controlado_inaccesibles(self):
        with tempfile.TemporaryDirectory() as temporary, socket.socket() as server:
            root = Path(temporary)
            workspace = root/'project'
            workspace.mkdir()
            decoy = root/'senuelo-sintetico.txt'
            decoy.write_text('DATO_SINTETICO_SIN_SECRETOS')
            server.bind(('127.0.0.1', 0))
            server.listen()
            server.settimeout(.2)
            port = server.getsockname()[1]
            code = f'''import socket
from pathlib import Path
try:
    Path({str(decoy)!r}).read_text()
except (FileNotFoundError, PermissionError):
    pass
else:
    raise AssertionError('Se leyó el señuelo del anfitrión')
try:
    socket.create_connection(('127.0.0.1', {port}), timeout=1)
except OSError:
    pass
else:
    raise AssertionError('Se alcanzó el destino controlado del anfitrión')
print('SENUELO_INACCESIBLE RED_BLOQUEADA', flush=True)
'''
            result = sandbox.run_isolated([sandbox.PYTHON, '-B', '-c', code], workspace,
                                           root/'log', 20, materials=(), runner=run_process)
            self.assertEqual((result['estado'], result['codigo_salida']), ('finalizada', 0), result)
            self.assertIn('RED_BLOQUEADA', (root/'log/stdout.txt').read_text())
            with self.assertRaises(socket.timeout):
                server.accept()

    def test_3_timeout_sin_contenedor_ni_descendientes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/'project'
            project.mkdir()
            token = 'cro-timeout-' + uuid4().hex
            code = f'''import subprocess, sys, time
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)', {token!r}])
print('TIMEOUT_PARCIAL', flush=True)
time.sleep(300)
'''
            result = sandbox.run_isolated([sandbox.PYTHON, '-B', '-c', code], project,
                                           root/'log', 5, materials=(), runner=run_process)
            self.assertEqual(result['estado'], 'tiempo_agotado', result)
            self.assertIn('TIMEOUT_PARCIAL', (root/'log/stdout.txt').read_text())
            self.assertTrue(result['aislamiento']['limpieza_confirmada'])
            exists = sandbox.runtime_call(['container', 'exists', result['aislamiento']['contenedor']])
            self.assertEqual(exists.returncode, 1, exists.stderr)
            processes = subprocess.run(['ps', '-eo', 'args'], capture_output=True, text=True, check=True)
            self.assertNotIn(token, processes.stdout)

    def test_4_inventario_no_ejecuta_importaciones_en_host(self):
        # El descubrimiento sucede antes de evaluate_flow en tareas configurables.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/'project'
            (project/'tests').mkdir(parents=True)
            marker = root/'HOST_IMPORTADO'
            (project/'tests/test_candidate.py').write_text(
                'from pathlib import Path\nimport unittest\n'
                f'p = Path({str(marker)!r})\n'
                'try:\n    p.touch()\nexcept OSError:\n    pass\n'
                'class Candidate(unittest.TestCase):\n    def test_ok(self): pass\n')
            authority = root/'authority'
            authority.mkdir()
            for name in ('project_test_inventory.py', 'process_environment.py'):
                (authority/name).write_bytes((Path(sandbox.__file__).parent/name).read_bytes())
            result = sandbox.run_isolated([sandbox.PYTHON, '-B', str(authority/'project_test_inventory.py'),
                                           '--reference', str(project)], project, root/'log', 20,
                                           materials=(authority,), runner=run_process)
            self.assertEqual((result['estado'], result['codigo_salida']), ('finalizada', 0), result)
            self.assertFalse(marker.exists())

    def test_5_montaje_automatico_del_home_no_es_visible(self):
        # Conservar el almacén de la imagen sin usar el HOME personal ni tocarlo.
        data_home = os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root/'home'
            config = home/'.config/containers'
            config.mkdir(parents=True)
            project = root/'project'
            project.mkdir()
            payload = 'SENUELO_SINTETICO_DE_MONTAJE_AUTOMATICO'
            decoy = root/'senuelo.txt'
            decoy.write_text(payload)
            target = '/run/senuelo-automatico-' + uuid4().hex + '.txt'
            mounts = config/'mounts.conf'
            contents = f'{decoy}:{target}\n'
            mounts.write_text(contents)
            with patch.dict(os.environ, {'HOME':str(home), 'XDG_DATA_HOME':data_home}):
                # Control positivo: solo un lector sintético, con los mismos
                # límites y namespaces; retirar únicamente la opción corregida.
                name = 'cro-eval-' + uuid4().hex
                control = [sandbox.PYTHON, '-B', '-c',
                           f'from pathlib import Path; assert Path({target!r}).read_text() == {payload!r}; '
                           'print("MONTAJE_CONTROL_PRESENTE", flush=True)']
                command = sandbox.container_command(name, control, project, [(project, project, False)])
                command.remove('--default-mounts-file=/dev/null')
                try:
                    result = run_process(command, project, root/'control', 20, env_policy='podman')
                finally:
                    sandbox.cleanup(name)
                self.assertEqual((result['estado'], result['codigo_salida']), ('finalizada', 0), result)
                self.assertIn('MONTAJE_CONTROL_PRESENTE', (root/'control/stdout.txt').read_text())

                # Esta invocación usa el evaluador de producción, sin sustituir
                # el runtime ni sus controles. El montaje automático debe faltar.
                code = f'''from pathlib import Path
assert not Path({target!r}).exists(), 'El montaje automático del HOME es visible'
print('MONTAJE_AUTOMATICO_BLOQUEADO', flush=True)
'''
                result = sandbox.run_isolated([sandbox.PYTHON, '-B', '-c', code], project,
                                               root/'log', 20, materials=(), runner=run_process)
                self.assertEqual((result['estado'], result['codigo_salida']), ('finalizada', 0), result)
                self.assertTrue(result['aislamiento']['limpieza_confirmada'])
                sandbox.validate_isolation(result, materials=(), log=root/'log')
                self.assertIn('MONTAJE_AUTOMATICO_BLOQUEADO', (root/'log/stdout.txt').read_text())
            self.assertEqual(mounts.read_text(), contents)
            self.assertEqual(decoy.read_text(), payload)


if __name__ == '__main__':
    unittest.main()

"""Regresiones con fallos inyectados; no sustituyen la integración Podman real."""

from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import python_evaluator as sandbox
from repair_project import StopProject


class VolumeRuntime:
    def __init__(self, *, created=False, create_error=None, unmount_error=None, remove_error=None):
        self.created = created
        self.create_error = create_error
        self.unmount_error = unmount_error
        self.remove_error = remove_error
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        code, error = 0, ''
        if args[:2] == ['volume','exists']:
            code = 0 if self.created else 1
        elif args[:2] == ['volume','create']:
            if self.create_error:
                code, error = 125, self.create_error
            else:
                self.created = True
        elif args[:4] == ['unshare','podman','volume','mount']:
            code, error = 125, 'MONTAJE_ORIGINAL_FALLIDO'
        elif args[:4] == ['unshare','podman','volume','unmount']:
            if isinstance(self.unmount_error, Exception):
                raise self.unmount_error
            if self.unmount_error:
                code, error = 125, self.unmount_error
        elif args[:2] == ['volume','rm']:
            if self.remove_error:
                code, error = 125, self.remove_error
            else:
                self.created = False
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, '', error)


class PartialPreparationTests(unittest.TestCase):
    def test_desmontaje_fallido_no_impide_retirar_por_nombre(self):
        for error in ('DESMONTAJE_FALLIDO', OSError('DESMONTAJE_FALLIDO')):
            with self.subTest(error=type(error).__name__):
                runtime = VolumeRuntime(created=True, unmount_error=error)
                with patch.object(sandbox, 'runtime_call', runtime):
                    report = sandbox.cleanup_result_volume('cro-eval-regresion-results')
                self.assertEqual(report['estado_inicial'], 'presente')
                self.assertEqual(report['estado_final'], 'ausente')
                self.assertTrue(report['ausente_confirmado'])
                self.assertIn('DESMONTAJE_FALLIDO', report['errores'][0]['error'])
                self.assertEqual(runtime.calls[-2:], [['volume','rm','cro-eval-regresion-results'],
                                                      ['volume','exists','cro-eval-regresion-results']])
                self.assertTrue(all('--force' not in command for command in runtime.calls))

    def test_volumen_no_creado_se_distingue_de_volumen_presente(self):
        runtime = VolumeRuntime()
        with patch.object(sandbox, 'runtime_call', runtime):
            report = sandbox.cleanup_result_volume('ausente')
        self.assertEqual(report, {'estado_inicial':'ausente', 'estado_final':'ausente',
                                 'ausente_confirmado':True, 'errores':[]})
        self.assertEqual(runtime.calls, [['volume','exists','ausente']])
        runtime = VolumeRuntime(created=True, unmount_error='DESMONTAJE', remove_error='EN_USO')
        with patch.object(sandbox, 'runtime_call', runtime):
            report = sandbox.cleanup_result_volume('presente')
        self.assertEqual(report['estado_final'], 'presente')
        self.assertFalse(report['ausente_confirmado'])
        self.assertEqual([e['operacion'] for e in report['errores']],
                         ['desmontar','retirar','comprobar_despues'])
        self.assertNotIn('--force', runtime.calls[-2])

    def run_partial_preparation(self, runtime):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/'project'; project.mkdir()
            runner = Mock()
            with patch.object(sandbox, 'require_runtime'), patch.object(sandbox, 'runtime_call', runtime):
                result = sandbox.run_isolated([sandbox.PYTHON, '-B', '-c', 'raise AssertionError()'],
                    project, root/'log', 1, materials=(), runner=runner)
            runner.assert_not_called()
            self.assertEqual(json.loads((root/'log/resultado.json').read_text()), result)
            self.assertEqual(result['estado'], 'error_inicio')
            self.assertFalse((root/'log/pruebas.json').exists())
            return result

    def test_montaje_y_desmontaje_fallidos_conservan_error_original(self):
        runtime = VolumeRuntime(unmount_error='DESMONTAJE_SECUNDARIO')
        result = self.run_partial_preparation(runtime)
        self.assertIn('MONTAJE_ORIGINAL_FALLIDO', result['error'])
        self.assertNotIn('DESMONTAJE_SECUNDARIO', result['error'])
        self.assertIn('DESMONTAJE_SECUNDARIO', result['errores_limpieza'][0]['error'])
        self.assertTrue(result['aislamiento']['limpieza_confirmada'])
        self.assertFalse(runtime.created)

    def test_retencion_del_volumen_no_oculta_el_error_del_montaje(self):
        runtime = VolumeRuntime(unmount_error='DESMONTAJE', remove_error='RETIRADA_FALLIDA')
        result = self.run_partial_preparation(runtime)
        self.assertIn('MONTAJE_ORIGINAL_FALLIDO', result['error'])
        self.assertEqual(result['aislamiento']['limpieza_volumen']['estado_final'], 'presente')
        self.assertFalse(result['aislamiento']['limpieza_confirmada'])
        self.assertIn('RETIRADA_FALLIDA', str(result['errores_limpieza']))

    def test_creacion_fallida_no_se_etiqueta_como_recurso_abandonado(self):
        result = self.run_partial_preparation(VolumeRuntime(create_error='NO_CREADO'))
        self.assertIn('NO_CREADO', result['error'])
        self.assertEqual(result['aislamiento']['limpieza_volumen']['estado_inicial'], 'ausente')
        self.assertTrue(result['aislamiento']['limpieza_confirmada'])
        self.assertNotIn('errores_limpieza', result)


class FinalizationFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root/'project'; self.project.mkdir()
        self.log = self.root/'log'
        self.limits = {'resultados':16384, 'stdout':128, 'stderr':128, 'inodos':64}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(sandbox, 'require_runtime'))
        self.stack.enter_context(patch.object(sandbox, 'prepare_result_volume', return_value='/tmp/simulado'))
        self.stack.enter_context(patch.object(sandbox, 'result_volume_usage', return_value={'excedido':False}))
        self.stack.enter_context(patch.object(sandbox, 'cleanup'))
        self.stack.enter_context(patch.object(sandbox, 'cleanup_result_volume', return_value={
            'estado_inicial':'presente', 'estado_final':'ausente', 'ausente_confirmado':True, 'errores':[]}))

    def execute(self, collect, runner=None):
        with patch.object(sandbox, 'collect_result_volume', side_effect=collect):
            result = sandbox.run_isolated([sys.executable, '-B', '-c', 'raise AssertionError()'],
                self.project, self.log, 1, materials=(), output_limits=self.limits,
                runner=runner or (lambda *a, **k: {'estado':'finalizada','codigo_salida':0,'error':None}))
        self.assertEqual(json.loads((self.log/'resultado.json').read_text()), result)
        self.assertNotEqual(result['estado'], 'finalizada')
        self.assertLessEqual((self.log/'stderr.txt').stat().st_size, self.limits['stderr'])
        self.assertEqual(result['aislamiento']['limites_salida'], self.limits)
        with self.assertRaises(StopProject):
            sandbox.check_isolated_process(result)
        return result

    def test_directorio_con_nombre_de_informe_no_impide_guardar_resultado(self):
        def malformed(*args):
            (self.log/'pruebas.json').mkdir()
            raise ValueError('ESTRUCTURA_ORIGINAL_INVALIDA')
        result = self.execute(malformed)
        self.assertEqual(result['estado'], 'error_inicio')
        self.assertIn('ESTRUCTURA_ORIGINAL_INVALIDA', result['error'])
        self.assertEqual(result['errores_limpieza'][0]['recurso'], 'pruebas.json')
        self.assertEqual(result['errores_limpieza'][0]['operacion'], 'retirar_parcial')
        self.assertTrue(result['aislamiento']['limpieza_confirmada'])

    def test_error_al_retirar_parcial_preserva_diagnostico_de_recogida(self):
        def partial(*args):
            (self.log/'pruebas.json').write_text('{"completo":true}')
            raise OSError('EIO_RECOGIDA_ORIGINAL')
        original = Path.unlink
        def refuse(path, *args, **kwargs):
            if path == self.log/'pruebas.json':
                raise PermissionError('EACCES_RETIRADA_SECUNDARIO')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', refuse):
            result = self.execute(partial)
        self.assertIn('EIO_RECOGIDA_ORIGINAL', result['error'])
        self.assertNotIn('EACCES', result['error'])
        self.assertIn('EACCES_RETIRADA_SECUNDARIO', str(result['errores_limpieza']))
        self.assertEqual(result['estado'], 'error_inicio')

    def test_timeout_no_es_sustituido_por_error_de_limpieza(self):
        with patch.object(sandbox, 'cleanup_result_volume', return_value={
                'estado_inicial':'presente', 'estado_final':'ausente', 'ausente_confirmado':True,
                'errores':[{'operacion':'desmontar','error':'DESMONTAJE_SECUNDARIO'}]}):
            result = self.execute(None, runner=lambda *a, **k: {
                'estado':'tiempo_agotado','codigo_salida':-9,'error':None})
        self.assertEqual(result['estado'], 'tiempo_agotado')
        self.assertIn('agotó', result['error'])
        self.assertIn('DESMONTAJE_SECUNDARIO', str(result['errores_limpieza']))


if __name__ == '__main__':
    unittest.main()

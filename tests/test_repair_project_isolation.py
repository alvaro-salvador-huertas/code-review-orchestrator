"""Frontera de repair_project con fallos inyectados y proyectos sintéticos."""

import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

import python_evaluator as sandbox
import repair_project as controller
import review_project
from repair_case import write_json
from evaluator_stub import simulated
import test_repair_project as fixture


class RepairProjectIsolationTests(unittest.TestCase):
    write = fixture.TestRepairProject.write
    git = fixture.TestRepairProject.git
    commit_base = fixture.TestRepairProject.commit_base
    configure = fixture.TestRepairProject.configure
    calls_read = fixture.TestRepairProject.calls_read
    run_project = fixture.TestRepairProject.run_project

    def setUp(self):
        fixture.TestRepairProject.setUp(self)

    def test_cuatro_evaluaciones_y_lector_aceptan_la_procedencia_nueva(self):
        substitute = simulated()
        with patch.object(controller, 'run_isolated', wraps=substitute) as isolated:
            result = self.run_project()
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(isolated.call_count, 4)
        log = Path(result['registro'])
        self.assertEqual(result['version_evaluacion'], 2)
        self.assertEqual(result['procedencia']['version_evaluacion'], 2)
        record = review_project.Evidence(log)
        for phase in ('inicial', 'posterior'):
            for kind in ('aceptacion', 'regresion'):
                item = result[phase][kind]
                counts = review_project.evaluation(record, f'{phase}/{kind}', item,
                    result['procedencia']['pruebas_esperadas'][kind],
                    log/'referencia/project_test_runner.py',
                    log/'referencia/evaluar.py' if kind == 'aceptacion' else None, version=2)
                self.assertEqual(counts['clasificacion'], item['clasificacion'])
        for call in isolated.call_args_list:
            command, workspace, output, timeout = call.args
            self.assertEqual(command[0], sandbox.PYTHON)
            self.assertEqual(timeout, 60 if output.name == 'aceptacion' else 180)
            wanted = (log/'referencia/project_test_runner.py',)
            if output.name == 'aceptacion': wanted += (log/'referencia/evaluar.py',)
            self.assertEqual(call.kwargs['materials'], wanted)
            sandbox.validate_isolation(result[output.parent.name][output.name]['proceso'],
                                       materials=wanted, log=output)
        self.assertTrue(all(result['integridad'].values()))
        self.assertEqual(result['revision'], 'pendiente_no_conectada')

    def test_runtime_ausente_no_invoca_agente_ni_aceptacion_en_host(self):
        marker = self.temporary/'HOST_NO_EJECUTADO'
        self.write(controller.ACCEPTANCE,
            f'from pathlib import Path\nPath({str(marker)!r}).touch()\n' + fixture.ACCEPTANCE)
        with patch.object(controller, 'run_isolated', sandbox.run_isolated), \
             patch.object(sandbox, 'require_runtime', side_effect=RuntimeError('RUNTIME_AUSENTE')):
            result = self.run_project()
        self.assertEqual((result['codigo_salida'], result['estado']), (3, 'fallo_tecnico'), result)
        self.assertIn('RUNTIME_AUSENTE', result['error'])
        self.assertEqual(self.calls_read(), [])
        self.assertFalse(marker.exists())
        self.assertEqual(result['posterior'], {})

    def test_cli_runtime_ausente_conserva_codigo_diagnostico_y_resumen(self):
        # Fallo inyectado solo en la copia privada de la CLI del fixture.
        (self.root/'python_evaluator.py').write_text(Path(sandbox.__file__).read_text() +
            "\ndef require_runtime():\n    raise RuntimeError('RUNTIME_CLI_AUSENTE')\n")
        completed = subprocess.run(fixture.TestRepairProject.cli_command(self),
            env=fixture.TestRepairProject.cli_env(self), capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertNotIn('Traceback', completed.stderr)
        self.assertIn('RUNTIME_CLI_AUSENTE', completed.stderr)
        paths = list((self.root/'runs').glob('*/resultado.json'))
        self.assertEqual(len(paths), 1)
        result = json.loads(paths[0].read_text())
        self.assertEqual((result['codigo_salida'], result['estado']), (3, 'fallo_tecnico'))
        self.assertIn('RUNTIME_CLI_AUSENTE', result['error'])
        self.assertEqual(result['agente']['invocaciones'], 0)
        self.assertEqual(self.calls_read(), [])

    def test_arranque_inicial_rechazado_no_autoriza_agente(self):
        clean = {'estado_inicial':'presente', 'estado_final':'ausente',
                 'ausente_confirmado':True, 'errores':[]}
        runner = Mock(return_value={'estado':'finalizada','codigo_salida':125,'error':None})
        with patch.object(controller, 'run_isolated', sandbox.run_isolated), \
             patch.object(sandbox, 'require_runtime'), \
             patch.object(sandbox, 'prepare_result_volume', return_value='/tmp/volumen-simulado'), \
             patch.object(sandbox, 'cleanup'), \
             patch.object(sandbox, 'cleanup_result_volume', return_value=clean), \
             patch.object(sandbox, 'result_volume_usage', return_value={'excedido':False}), \
             patch.object(controller, 'run_process', runner):
            result = self.run_project()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertIn('no pudo iniciar', result['error'])
        self.assertEqual(self.calls_read(), [])
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.args[0][0], 'podman')
        self.assertEqual(result['inicial']['aceptacion']['clasificacion'], 'no_acreditada')

    def test_fallo_posterior_cuota_timeout_o_evidencia_impiden_acreditar(self):
        substitute = simulated()
        for fault, code in (('cuota',3), ('timeout',4), ('aislamiento',6), ('informe',6)):
            def fail_after(command, workspace, log, timeout, **kwargs):
                process = substitute(command, workspace, log, timeout, **kwargs)
                if log.parent.name == 'posterior':
                    if fault == 'cuota':
                        process.update(estado='limite_salida', error='Límite sintético de stdout', salida_excedida='stdout')
                    elif fault == 'timeout':
                        process.update(estado='tiempo_agotado', error='Timeout sintético')
                    elif fault == 'aislamiento':
                        process.pop('aislamiento')
                    else:
                        report = json.loads((log/'pruebas.json').read_text())
                        report['completo'] = False
                        write_json(log/'pruebas.json', report)
                    write_json(log/'resultado.json', process)
                return process
            with self.subTest(fallo=fault), patch.object(controller, 'run_isolated', fail_after):
                before = len(self.calls_read())
                result = self.run_project()
                self.assertEqual(result['codigo_salida'], code, result)
                self.assertEqual(result['posterior']['aceptacion']['clasificacion'], 'no_acreditada')
                self.assertEqual(result['agente']['invocaciones'], 1)
                self.assertEqual(len(self.calls_read()), before + 1)
                self.assertTrue(result['error'])


if __name__ == '__main__':
    unittest.main()

"""Regresiones sintéticas del evaluador compartido, transiciones y lectura."""

import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import orchestrate_case
import python_evaluator as sandbox
import repair_case
import review_case
from case_evidence import snapshot_tree
from evaluator_stub import simulated
from test_orchestrate_case import OrchestrationFixture

REAL_ISOLATED = sandbox.run_isolated


class CaseIsolationTests(OrchestrationFixture, unittest.TestCase):
    def test_runtime_inicial_ausente_no_invoca_desarrollador_ni_descubrimiento(self):
        marker = self.temporary/'NO_EJECUTADO_EN_HOST'
        tests = self.project/'benchmark'/self.case_id/'test_solution.py'
        tests.write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n'+tests.read_text())
        with patch.object(sandbox, 'run_isolated', REAL_ISOLATED), \
             patch.object(sandbox, 'require_runtime', side_effect=RuntimeError('RUNTIME_AUSENTE')):
            result = self.execute([], [])
        self.assertEqual((result['codigo_salida'], result['estado']), (8,'error_pruebas'), result)
        self.assertEqual(result['invocaciones']['total'], 0)
        self.assertEqual(self.observed_calls(), [])
        self.assertFalse(marker.exists())
        repair = result['intentos'][0]['reparacion']
        self.assertIn('RUNTIME_AUSENTE', str(repair['errores_controlador']))
        self.assertEqual(repair['pruebas_posteriores']['estado'], 'no_ejecutadas')

    def test_fallo_posterior_no_autoriza_correccion_ni_revision(self):
        substitute = simulated()
        for fault in ('runtime','cuota','evidencia','limpieza','timeout'):
            def failed(command, workspace, log, timeout, **kwargs):
                process = substitute(command, workspace, log, timeout, **kwargs)
                if log.parent.name == 'posterior':
                    if fault in ('runtime','cuota'):
                        process.update(estado='error_inicio' if fault=='runtime' else 'limite_salida',
                                       error='FALLO_POSTERIOR_'+fault)
                    elif fault == 'timeout':
                        process.update(estado='tiempo_agotado', error='TIMEOUT_POSTERIOR')
                    elif fault == 'evidencia':
                        process.pop('aislamiento')
                    else:
                        process['aislamiento']['limpieza_confirmada'] = False
                    repair_case.write_json(log/'resultado.json', process)
                return process
            with self.subTest(fault=fault), patch.object(sandbox, 'run_isolated', failed):
                result = self.execute([{'candidate':self.good}], [])
                self.assertEqual(result['codigo_salida'], 4 if fault=='timeout' else 8, result)
                self.assertEqual(len(result['intentos']), 1)
                self.assertEqual(result['invocaciones'], {'desarrollador':1,'revisor':0,'total':1})
                self.assertIsNone(result['intentos'][0]['revision'])
                self.assertEqual(result['intentos'][0]['transiciones'][0]['accion'], 'detener')

    def test_aserciones_ordinarias_conservan_partida_feedback_y_presupuesto(self):
        result = self.execute([{'candidate':self.partial}, {'candidate':self.good}])
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(result['invocaciones'], {'desarrollador':2,'revisor':1,'total':3})
        first, second = [entry['reparacion'] for entry in result['intentos']]
        self.assertEqual(first['pruebas_posteriores_clasificacion'], 'fallos_asercion')
        self.assertEqual(result['intentos'][0]['transiciones'][0]['accion'], 'corregir')
        self.assertEqual((Path(second['registro'])/'partida.py').read_text(), self.partial)
        self.assertEqual(json.loads((Path(second['registro'])/'feedback.json').read_text())['tipo'], 'fallos_pruebas')
        review_case.validate_repair(Path(second['registro']), self.project)
        previous = Path(first['registro'])
        (previous/'agente/respuesta_final.txt').write_text('ALTERADO')
        with self.assertRaises(ValueError):
            review_case.validate_repair(Path(second['registro']), self.project)

    def accepted_repair(self):
        result = self.execute()
        self.assertEqual(result['codigo_salida'], 0, result)
        repair = result['intentos'][0]['reparacion']
        return Path(repair['registro']), repair

    def save_altered_phase(self, path, result, phase, mutation):
        key = 'pruebas_iniciales' if phase=='inicial' else 'pruebas_posteriores'
        root = json.loads(json.dumps(result))
        item = root[key]
        mutation(item)
        raw = {k:v for k,v in item.items() if k not in
               ('version_evaluacion','pruebas_intactas','implementacion_intacta')}
        repair_case.write_json(path/phase/'evaluacion/resultado.json', raw)
        repair_case.write_json(path/phase/'resultado.json', item)
        repair_case.write_json(path/'resultado.json', root)
        # El lector inventaría de nuevo este registro: no depende de hashes viejos.
        return snapshot_tree(path)

    def test_lector_rechaza_aislamiento_ausente_con_resumen_y_proceso_actualizados(self):
        path, result = self.accepted_repair()
        for phase in ('inicial','posterior'):
            for fault in ('ausente','limpieza','montajes'):
                def mutation(item):
                    if fault=='ausente': item.pop('aislamiento')
                    elif fault=='limpieza': item['aislamiento']['limpieza_confirmada'] = False
                    else: item['aislamiento']['comando_runtime'].remove('--network=none')
                current = self.save_altered_phase(path,result,phase,mutation)
                with self.subTest(phase=phase,fault=fault), self.assertRaises(ValueError):
                    review_case.validate_repair(path,self.project)
                self.assertEqual(snapshot_tree(path),current)
                self.save_altered_phase(path,result,phase,lambda item: None)

    def test_registro_historico_v2_sigue_legible_sin_runtime(self):
        path, result = self.accepted_repair()
        result.pop('version_evaluacion')
        for phase, key in (('inicial','pruebas_iniciales'),('posterior','pruebas_posteriores')):
            item = result[key]
            item.pop('version_evaluacion'); item.pop('aislamiento')
            shutil.rmtree(path/phase/'evaluacion')
            repair_case.write_json(path/phase/'resultado.json',item)
        repair_case.write_json(path/'resultado.json',result)
        before = snapshot_tree(path)
        with patch.object(sandbox,'runtime_call',side_effect=AssertionError('No ejecutar Podman al leer')):
            materials, hashes = review_case.validate_repair(path,self.project)
        self.assertEqual(materials['candidato.py'].decode(),self.good)
        self.assertEqual(hashes,before)
        self.assertEqual(snapshot_tree(path),before)
        self.assertNotIn('version_evaluacion',json.loads((path/'resultado.json').read_text()))

    def test_version_nueva_no_admite_descenso_parcial_ni_candidato_mezclado(self):
        path, result = self.accepted_repair()
        for fault in ('version','desconocida','candidato'):
            altered = json.loads(json.dumps(result))
            if fault=='version': altered.pop('version_evaluacion')
            elif fault=='desconocida': altered['version_evaluacion'] = 3
            else: (path/'posterior/workspace/solution.py').write_text(self.partial)
            repair_case.write_json(path/'resultado.json',altered)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review_case.validate_repair(path,self.project)


if __name__ == '__main__':
    unittest.main()

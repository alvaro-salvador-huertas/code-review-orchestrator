"""Revisión adicional con agentes simulados; jamás utiliza registros ni modelos reales."""

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

import project_flow
import repair_project
import review_case
import review_project as controller
from repair_case import write_json
import test_orchestrate_project as flow_fixture


class IsolatedReviewTests(unittest.TestCase):
    setUp = flow_fixture.ProjectFlowTests.setUp
    write = flow_fixture.ProjectFlowTests.write
    git = flow_fixture.ProjectFlowTests.git
    commit_base = flow_fixture.ProjectFlowTests.commit_base
    calls_read = flow_fixture.ProjectFlowTests.calls_read
    cli_env = flow_fixture.ProjectFlowTests.cli_env
    configure = flow_fixture.ProjectFlowTests.configure
    run_flow = flow_fixture.ProjectFlowTests.run_flow

    def origin(self, *, second=True):
        self.configure(desarrollador=[{'candidate': flow_fixture.fixture.BASE}, {}] if second else [{}],
                       revisor=[{'block': True, 'raw': 'OBSERVACION_TIMEOUT_NO_REVISAR'}])
        with patch.object(review_case, 'AGENT_TIMEOUT_SECONDS', 0.2):
            result = self.run_flow()
        self.assertEqual(result['codigo_salida'], 4, result)
        self.source = Path(result['registro'])
        self.attempt = 2 if second else 1
        self.delivery = self.source / 'intentos' / str(self.attempt) / 'evidencia'
        self.source_state = repair_project.tree_state(self.source)
        self.linked = Path(result['intentos'][-1]['revision']['registro'])
        self.linked_state = repair_project.tree_state(self.linked)
        self.original = repair_project.tree_state(self.root, filter_local=True)
        self.count = len(self.calls_read())
        self.configure()
        return result

    def run_isolated(self, operation='revision', **kwargs):
        result = controller.run_isolated_review(self.source, self.attempt, operation, self.root, **kwargs)
        if result['registro']:
            self.assertEqual(result, json.loads((Path(result['registro']) / 'resultado.json').read_text()))
        self.assertEqual(result['incorporacion'], 'no_realizada')
        self.assertEqual(result['contraste_semantico'], 'pendiente')
        return result

    def assert_unchanged(self):
        self.assertEqual(repair_project.tree_state(self.source), self.source_state)
        self.assertEqual(repair_project.tree_state(self.linked), self.linked_state)
        self.assertEqual(repair_project.tree_state(self.root, filter_local=True), self.original)

    def reseal(self):
        """Actualizar sellos del fixture no debe ocultar contradicciones de contenido."""
        record = json.loads((self.delivery / 'resultado.json').read_text())
        record['etapas_sha256'] = {n: repair_project.tree_state(self.delivery / n)
                                  for n in ('desarrollo', 'entrega', 'evaluaciones')}
        write_json(self.delivery / 'resultado.json', record)
        summary = json.loads((self.source / 'resultado.json').read_text())
        entry = summary['intentos'][self.attempt - 1]
        for key in ('candidato_sha256', 'partida_sha256', 'desarrollo', 'evaluaciones'):
            entry[key] = record[key]
        summary['etapas_cerradas'] = {p: repair_project.tree_state(Path(p))
                                     for p in summary['etapas_cerradas']}
        write_json(self.source / 'resultado.json', summary)

    def test_aprobacion_tras_timeout_identidad_contexto_y_presupuesto_propio(self):
        origin = self.origin()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = self.run_isolated(review_timeout=300)
        self.assertEqual(out.getvalue() + err.getvalue(), '')
        self.assertEqual(result['codigo_salida'], 0, result)
        self.assertEqual(result['dictamen_modelo'], flow_fixture.APPROVE)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assertEqual(result['revisor']['invocaciones'], 1)
        self.assertEqual(result['revisor']['limite_segundos'], 300)
        self.assertEqual(origin['invocaciones'], {'desarrollador': 2, 'revisor': 1, 'total': 3})
        log = Path(result['registro'])
        operation = json.loads((log / 'operacion.json').read_text())
        reservation = json.loads((log / 'reserva.json').read_text())
        for value in (operation, reservation):
            self.assertEqual(value['limite_solicitado_segundos'], 300)
            self.assertEqual(value['limite_efectivo_segundos'], 300)
            self.assertEqual(value['candidato_sha256'], origin['intentos'][1]['candidato_sha256'])
        self.assertLessEqual(reservation['fecha_utc'], result['revisor']['inicio_utc'])
        self.assertEqual(result['revisor_sha256'], repair_project.tree_state(log / 'revisor'))
        self.assertEqual((log / 'materiales/inspect_run.py').read_bytes(),
                         (self.delivery / 'entrega/inspect_run.py').read_bytes())
        self.assertEqual((log / 'revisor/entrada.txt').read_bytes(),
                         (self.source / 'referencia' / project_flow.REVIEW_PROMPT).read_bytes())
        context = '\n'.join(p.read_text() for p in (log / 'materiales').rglob('*') if p.is_file())
        summary = json.loads((log / 'materiales/resumen_evidencia.json').read_text())
        self.assertTrue(summary['regresion_reutilizada'])
        self.assertFalse(summary['evaluaciones_nuevas'])
        for unwanted in ('EXPLICACION_DESARROLLADOR_NO_REVISAR', 'OBSERVACION_TIMEOUT_NO_REVISAR',
                         'tiempo_agotado_revisor', 'simulado'):
            self.assertNotIn(unwanted, context)
        call = self.calls_read()[-1]
        self.assertEqual(call['rol'], 'revisor')
        self.assertIn('--ephemeral', call['args'])
        self.assertEqual(call['args'][call['args'].index('--sandbox') + 1], 'read-only')
        self.assertNotIn(call['workspace'], [c['workspace'] for c in self.calls_read()[:-1]])
        self.assert_unchanged()

    def test_solicitud_cambios_y_limite_predeterminado(self):
        self.origin()
        self.configure(revisor=[{'verdict': flow_fixture.CHANGE}])
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 1, result)
        self.assertEqual(result['dictamen_modelo'], flow_fixture.CHANGE)
        self.assertEqual(result['limites_segundos']['revisor'], 180)
        self.assertEqual(result['revisor']['limite_segundos'], 180)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assert_unchanged()

    def test_intento_inexistente_no_invoca(self):
        self.origin(second=False)
        self.attempt = 2
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIn('no existe', result['error'])
        self.assertEqual(len(self.calls_read()), self.count)
        self.assert_unchanged()

    def test_candidato_alterado_o_evidencia_ausente_no_invoca(self):
        self.origin()
        for name in ('entrega/inspect_run.py', 'evaluaciones/aceptacion/pruebas.json'):
            with self.subTest(name=name):
                path = self.delivery / name
                before = path.read_bytes()
                if name.endswith('.py'):
                    path.write_bytes(before + b'# alterado\n')
                else:
                    path.unlink()
                result = self.run_isolated()
                self.assertEqual(result['codigo_salida'], 7, result)
                self.assertEqual(len(self.calls_read()), self.count)
                path.write_bytes(before)
        self.assert_unchanged()

    def test_evaluacion_de_otro_candidato_no_vale_aun_resellada(self):
        self.origin()
        path = self.delivery / 'evaluaciones/aceptacion/proyecto_evaluado.json'
        state = json.loads(path.read_text())
        state['inspect_run.py']['sha256'] = '0' * 64
        write_json(path, state)
        self.reseal()
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIn('otra entrega', result['error'])
        self.assertEqual(len(self.calls_read()), self.count)

    def test_informe_incompleto_no_vale_aun_resellado(self):
        self.origin()
        path = self.delivery / 'evaluaciones/hallazgos/pruebas.json'
        report = json.loads(path.read_text())
        report['terminados'].clear()
        write_json(path, report)
        self.reseal()
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertEqual(len(self.calls_read()), self.count)

    def test_evaluaciones_fallidas_no_autorizan(self):
        self.origin()
        self.attempt = 1
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIn('no supera', result['error'])
        self.assertEqual(len(self.calls_read()), self.count)
        self.assert_unchanged()

    def test_desarrollo_no_satisfactorio_no_autoriza_aun_resellado(self):
        self.origin()
        path = self.delivery / 'desarrollo/resultado.json'
        process = json.loads(path.read_text())
        process['codigo_salida'] = 17
        write_json(path, process)
        record = json.loads((self.delivery / 'resultado.json').read_text())
        record['desarrollo']['agente']['proceso'] = process
        write_json(self.delivery / 'resultado.json', record)
        self.reseal()
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIn('desarrollo inválido', result['error'])
        self.assertEqual(len(self.calls_read()), self.count)

    def test_autoridad_distinta_no_se_ignora_por_haber_pasado_pruebas(self):
        self.origin()
        path = self.root / project_flow.SUITES['hallazgos']
        before = path.read_bytes()
        path.write_bytes(before + b'# autoridad distinta\n')
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 7, result)
        self.assertIn('Autoridad distinta', result['error'])
        self.assertEqual(len(self.calls_read()), self.count)
        path.write_bytes(before)
        self.assert_unchanged()

    def test_resumen_mezclado_o_manifiesto_omitido_no_autoriza(self):
        self.origin()
        path = self.source / 'resultado.json'
        before = path.read_bytes()
        for change in ('resumen', 'manifiesto', 'consumos', 'estado'):
            with self.subTest(change=change):
                summary = json.loads(before)
                if change == 'resumen':
                    summary['intentos'][1]['candidato_sha256'] = summary['intentos'][0]['candidato_sha256']
                elif change == 'manifiesto':
                    del summary['etapas_cerradas'][str(self.delivery)]
                elif change == 'consumos':
                    summary['invocaciones']['revisor'] = 0
                else:
                    summary['estado'] = 'aprobacion_inventada'
                write_json(path, summary)
                result = self.run_isolated()
                self.assertEqual(result['codigo_salida'], 7, result)
                self.assertEqual(len(self.calls_read()), self.count)
        path.write_bytes(before)
        self.assert_unchanged()

    def test_repeticion_no_reescribe_ni_invoca(self):
        self.origin()
        first = self.run_isolated()
        self.assertEqual(first['codigo_salida'], 0, first)
        state = repair_project.tree_state(Path(first['registro']))
        second = self.run_isolated(review_timeout=300)
        self.assertEqual(second['codigo_salida'], 10, second)
        self.assertEqual(second['revisor']['invocaciones'], 0)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assertEqual(state, repair_project.tree_state(Path(first['registro'])))
        self.assert_unchanged()

    def test_reserva_persistida_antes_de_lanzar_y_callback_duplicado(self):
        self.origin()
        def duplicate(workspace, final, prompt, log, *, on_invoke, timeout):
            on_invoke()
            saved = json.loads((log.parent / 'resultado.json').read_text())
            self.assertTrue(saved['reserva_invocacion'])
            self.assertEqual(saved['revisor']['invocaciones'], 1)
            self.assertEqual(json.loads((log.parent / 'reserva.json').read_text())['max_invocaciones'], 1)
            on_invoke()
            self.fail('Una segunda reserva no debe autorizar una segunda llamada')
        with patch.object(controller, 'invoke_reviewer', side_effect=duplicate) as invoke:
            result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 8, result)
        self.assertIn('ya reservada', result['error'])
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(len(self.calls_read()), self.count)

    def test_fallo_persistencia_reserva_impide_lanzamiento(self):
        self.origin()
        persist = controller.persist_review_json
        def broken(path, data, **kwargs):
            if path.name == 'reserva.json':
                raise OSError('disco simulado')
            return persist(path, data, **kwargs)
        with patch.object(controller, 'persist_review_json', side_effect=broken):
            result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 8, result)
        self.assertEqual(len(self.calls_read()), self.count)
        self.assertEqual(self.run_isolated()['codigo_salida'], 10)

    def test_cli_ausente_no_reserva_ni_permite_reanudar_operacion(self):
        self.origin()
        with patch.object(review_case, 'CODEX_EXECUTABLE', str(self.temporary / 'inexistente')):
            result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 3, result)
        self.assertFalse(result['reserva_invocacion'])
        self.assertEqual(result['revisor']['invocaciones'], 0)
        self.assertFalse((Path(result['registro']) / 'reserva.json').exists())
        self.assertEqual(self.run_isolated()['codigo_salida'], 10)
        self.assertEqual(len(self.calls_read()), self.count)
        self.assert_unchanged()

    def test_timeout_conserva_parcial_sin_aprobar_ni_reintentar(self):
        self.origin()
        self.configure(revisor=[{'block': True}])
        run_process = review_case.run_process
        def shortened(command, workspace, log, timeout, **kwargs):
            if '--output-schema' in command:
                self.assertEqual(timeout, 300)
                # Acortar solo el proceso simulado; conservar su límite realmente usado.
                timeout = 0.2
            return run_process(command, workspace, log, timeout, **kwargs)
        with patch.object(review_case, 'run_process', side_effect=shortened):
            result = self.run_isolated(review_timeout=300)
        self.assertEqual(result['codigo_salida'], 4, result)
        self.assertIsNone(result['dictamen_modelo'])
        self.assertEqual(result['revisor']['codigo_salida'], -signal.SIGKILL)
        log = Path(result['registro'])
        self.assertIn('EVENTO_PARCIAL', (log / 'revisor/eventos.jsonl').read_text())
        self.assertTrue((log / 'revisor/respuesta_original.txt').is_file())
        self.assertEqual(self.run_isolated()['codigo_salida'], 10)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assert_unchanged()

    def test_respuesta_invalida_y_fallo_tecnico_no_aprueban(self):
        self.origin()
        for setting, code in (({'raw': '{}'}, 5), ({'exit_code': 17}, 3)):
            with self.subTest(setting=setting):
                self.configure(revisor=[setting])
                result = self.run_isolated(operation='fallo-' + str(code))
                self.assertEqual(result['codigo_salida'], code, result)
                self.assertIsNone(result['dictamen_modelo'])
                self.assertTrue((Path(result['registro']) / 'revisor/respuesta_original.txt').is_file())
        self.assertEqual(len(self.calls_read()), self.count + 2)
        self.assert_unchanged()

    def test_integridad_del_contexto_impide_aprobacion(self):
        self.origin()
        self.configure(revisor=[{'mutation': 'workspace'}])
        result = self.run_isolated()
        self.assertEqual(result['codigo_salida'], 6, result)
        self.assertIsNone(result['dictamen_modelo'])
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assert_unchanged()

    def command(self):
        return [sys.executable, '-B', str(self.root / 'review_project.py'),
                '--orchestration-run', str(self.source), '--attempt', str(self.attempt),
                '--operation-id', 'cli']

    def test_lanzamientos_simultaneos_interrupcion_y_repeticion_cli(self):
        self.origin()
        self.configure(revisor=[{'block': True}])
        with subprocess.Popen(self.command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=self.cli_env()) as first:
            try:
                deadline = time.monotonic() + 10
                while len(self.calls_read()) == self.count and time.monotonic() < deadline and first.poll() is None:
                    time.sleep(0.02)
                self.assertEqual(len(self.calls_read()), self.count + 1)
                second = subprocess.run(self.command(), capture_output=True, text=True,
                                        env=self.cli_env(), timeout=10)
                self.assertEqual(second.returncode, 10, second.stderr)
            finally:
                first.send_signal(signal.SIGTERM)
                out, err = first.communicate(timeout=10)
        self.assertEqual(first.returncode, 9, out + err)
        log = self.root / 'runs/inspect-json_isolated-review_cli'
        result = json.loads((log / 'resultado.json').read_text())
        self.assertEqual(result['revisor']['estado'], 'interrumpida')
        self.assertEqual(result['revisor']['invocaciones'], 1)
        self.assertTrue(result['reserva_invocacion'])
        self.assertIsNone(result['dictamen_modelo'])
        self.assertIn('EVENTO_PARCIAL', (log / 'revisor/eventos.jsonl').read_text())
        self.assertTrue((log / 'revisor/respuesta_original.txt').is_file())
        again = subprocess.run(self.command(), capture_output=True, text=True, env=self.cli_env(), timeout=10)
        self.assertEqual(again.returncode, 10, again.stderr)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assert_unchanged()

    def test_cli_limite_canales_y_combinaciones_ambiguas(self):
        self.origin()
        result = subprocess.run(self.command() + ['--review-timeout', '300'], capture_output=True,
                                text=True, env=self.cli_env(), timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('límite 300 s', result.stderr)
        self.assertIn('dictamen_aprobar_validado', result.stdout)
        log = self.root / 'runs/inspect-json_isolated-review_cli'
        self.assertEqual(json.loads((log / 'resultado.json').read_text())['revisor']['limite_segundos'], 300)
        self.assertNotIn('EVENTO_PARCIAL', result.stderr + result.stdout)
        options = self.command()[3:]
        bad = [[], options[:2], options[:-2], options + ['--development-run', 'x'],
               options + ['--reevaluation-run', 'x'], ['--development-run', 'x', '--reevaluation-run', 'y', '--attempt', '2'],
               *[options + ['--review-timeout', value] for value in ('59', '601', '1.5')],
               options[:-1] + ['../escape']]
        for arguments in bad:
            with self.subTest(arguments=arguments), patch.object(controller, 'PROJECT', self.root), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    controller.main(arguments)
                self.assertEqual(exc.exception.code, 2)
        self.assertEqual(len(self.calls_read()), self.count + 1)
        self.assert_unchanged()


if __name__ == '__main__':
    unittest.main(verbosity=2)

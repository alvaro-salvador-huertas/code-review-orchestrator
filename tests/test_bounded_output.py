"""Captura real de pipes sintéticos; el filesystem rootless se prueba en integración."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import bounded_output as quota
from repair_case import run_process


class BoundedOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.limits = {'resultados':16384, 'stdout':1024, 'stderr':1024, 'inodos':64}

    def execute(self, code, timeout=5):
        return run_process([sys.executable, '-B', '-c', code], self.root, self.root/'log', timeout,
                           output_limits=self.limits)

    def test_cada_pipe_corta_antes_del_primer_byte_excesivo_en_disco(self):
        for channel, fd in (('stdout',1), ('stderr',2)):
            with self.subTest(channel=channel):
                result = self.execute(f'import os\nwhile True: os.write({fd}, b"X"*65536)')
                self.assertEqual(result['estado'], 'limite_salida')
                self.assertEqual(result['salida_excedida'], channel)
                self.assertEqual((self.root/'log'/f'{channel}.txt').stat().st_size, 1024)

    def test_limite_exacto_es_valido_y_no_se_trunca(self):
        result = self.execute('import os; os.write(1, b"A"*1024); os.write(2, b"B"*1024)')
        self.assertEqual(result['estado'], 'finalizada')
        self.assertEqual(result['codigo_salida'], 0)
        self.assertEqual((self.root/'log/stdout.txt').read_bytes(), b'A'*1024)
        self.assertEqual((self.root/'log/stderr.txt').read_bytes(), b'B'*1024)

    def test_timeout_conserva_parciales_y_limite(self):
        result = self.execute('import time; print("PARCIAL", flush=True); time.sleep(20)', .2)
        self.assertEqual(result['estado'], 'tiempo_agotado')
        self.assertIn('PARCIAL', (self.root/'log/stdout.txt').read_text())

    def test_diagnostico_no_rebasa_stderr_lleno(self):
        self.execute('import os; os.write(2,b"X"*1024)')
        quota.append_diagnostic(self.root/'log', 'TIMEOUT', self.limits)
        self.assertEqual((self.root/'log/stderr.txt').stat().st_size, 1024)

    def test_recogida_preserva_json_valido_y_presupuesto_agregado(self):
        source, target = self.root/'source', self.root/'target'
        source.mkdir(); target.mkdir()
        report = b'{"version":1,"completo":true}\n'
        (source/'pruebas.json').write_bytes(report)
        self.assertEqual(quota.collect_output(source, target, self.limits), len(report))
        self.assertEqual((target/'pruebas.json').read_bytes(), report)
        (source/'consultas').mkdir()
        (source/'consultas/big').write_bytes(b'B'*16384)
        other = self.root/'other'; other.mkdir()
        with self.assertRaisesRegex(ValueError, 'agregado'):
            quota.collect_output(source, other, self.limits)
        self.assertLessEqual(sum(p.stat().st_size for p in other.rglob('*') if p.is_file()), 16384)

    def test_no_acepta_un_directorio_ordinario_en_lugar_de_tmpfs(self):
        with self.assertRaises(RuntimeError):
            quota.filesystem_usage(self.root, self.limits)

    def test_monitor_caido_detiene_la_ejecucion_cerradamente(self):
        result = run_process([sys.executable, '-B', '-c', 'import time; time.sleep(20)'],
            self.root, self.root/'log', 5, output_limits=self.limits,
            monitor_command=[sys.executable, '-B', '-c', 'print("ERROR", flush=True)'])
        self.assertEqual(result['estado'], 'error_inicio')
        self.assertIn('Monitor', result['error'])


if __name__ == '__main__':
    unittest.main()

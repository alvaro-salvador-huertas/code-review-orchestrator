"""Fixtures mínimos de protocolo e instrumentación, no un producto de referencia.

Cada fixture solo satisface un aspecto seleccionado. No se acredita aceptación
positiva de un booking_batch completo. No requiere runs/, red ni modelos.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import evaluar


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="control-booking-batch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "proyecto"
        self.project.mkdir()
        core = self.project / "booking_core.py"
        core.write_bytes((evaluar.AUTHORITY_ROOT / "booking_core.py").read_bytes())
        core.chmod(0o644)
        self.script = self.project / "booking_batch.py"

    def fixture(self, source):
        self.script.write_text(source, encoding="utf-8")
        self.script.chmod(0o644)

    def fixed(self, stdout=b"[]\n", stderr=b"", code=0):
        self.fixture(f"import os\nos.write(1, {stdout!r})\nos.write(2, {stderr!r})\nraise SystemExit({code})\n")

    def run_case(self, method):
        case = evaluar.AcceptanceTests(method)
        case.project = self.project
        result = unittest.TestResult()
        case.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])
        if hasattr(case, "root"):
            self.assertFalse(case.root.exists(), "Temporal de entradas no recogido")
            self.assertFalse(case.logs.exists(), "Temporal de canales no recogido")
        return result

    def passed(self, method):
        result = self.run_case(method)
        self.assertEqual(result.failures, [])

    def rejected(self, method):
        result = self.run_case(method)
        self.assertTrue(result.failures)
        return result

    def test_01_fixture_lote_vacio_y_traza(self):
        self.fixed()
        before = len(evaluar.QUERIES)
        self.passed("test_01_lote_vacio_y_espacio_exterior")
        traces = evaluar.QUERIES[before:]
        self.assertEqual(len(traces), 2)
        for trace in traces:
            self.assertEqual(trace["comando"][:3], [str(Path(sys.executable).resolve()), "-B", str(self.script)])
            self.assertEqual(trace["politica_entorno"], "evaluation")
            self.assertEqual(trace["limite_segundos"], 10)
            self.assertEqual(trace["codigo_salida"], 0)
            self.assertEqual(bytes.fromhex(trace["stdout_hex"]), b"[]\n")
            self.assertEqual(trace["stderr_hex"], "")
            self.assertFalse(Path(trace["directorio_trabajo"]).exists())

    def test_02_respuesta_fija_no_resuelve_consultas(self):
        self.fixed()
        self.rejected("test_02_consulta_disponible")

    def test_03_mixtas_resultado_explicito_y_orden(self):
        expected = [evaluar.AVAILABLE, {"disponible": False, "conflictos": ["r2", "r1"]}, evaluar.AVAILABLE]
        self.fixed(evaluar.encode(expected) + b"\n")
        self.passed("test_03_mixtas_orden_y_conflictos")
        expected[1]["conflictos"].reverse()
        self.fixed(evaluar.encode(expected) + b"\n")
        self.rejected("test_03_mixtas_orden_y_conflictos")

    def test_04_repeticiones_no_deduplicadas(self):
        expected = [{"disponible": False, "conflictos": ["mismo"]}, evaluar.AVAILABLE,
                    {"disponible": False, "conflictos": ["mismo"]}]
        self.fixed(evaluar.encode(expected) + b"\n")
        self.passed("test_04_repeticiones_e_independencia")
        self.fixed(evaluar.encode(expected[:2]) + b"\n")
        self.rejected("test_04_repeticiones_e_independencia")

    def test_05_extremos_y_unicode_con_esperados_independientes(self):
        cases = [("test_05_extremos_de_intervalo", [evaluar.AVAILABLE, {"disponible": False, "conflictos": ["igual", "contiene"]}]),
                 ("test_06_unicode_y_escapes_literales", [{"disponible": False, "conflictos": [' id "uno"\r\nñ ']}])]
        for method, value in cases:
            with self.subTest(metodo=method):
                self.fixed(evaluar.encode(value) + b"\n")
                self.passed(method)

    def test_06_json_tipos_canales_y_salto_final(self):
        for raw in (b"", b"[]", b"{}\n", b"null\n", b"\xff\n", b"\xef\xbb\xbf[]\n", b"[] []\n",
                    b"aviso\n[]\n", b'[{"disponible":1,"conflictos":[]}]\n',
                    b'[{"disponible":true,"conflictos":[],"extra":0}]\n',
                    b'[{"disponible":true,"disponible":true,"conflictos":[]}]\n',
                    b'[{"disponible":NaN,"conflictos":[]}]\n'):
            with self.subTest(salida=raw):
                self.fixed(raw)
                self.rejected("test_02_consulta_disponible")
        for code, stderr in ((1, b""), (2, b""), (0, b"aviso")):
            with self.subTest(codigo=code, stderr=stderr):
                self.fixed(evaluar.encode([evaluar.AVAILABLE]) + b"\n", stderr, code)
                self.rejected("test_02_consulta_disponible")

    def test_07_json_equivalente(self):
        self.fixed(b' \n[ {"conflictos": [], "disponible": true} ]\r\n')
        self.passed("test_02_consulta_disponible")

    def test_08_error_tardio_posicion_y_causa(self):
        for diagnostic in (b"Consulta 3: falta fin", b"Third query: missing end"):
            self.fixed(b"", diagnostic, 1)
            self.passed("test_09_error_ultima_consulta_sin_salida_parcial")
        for diagnostic in (b"", b"Consulta 2: falta fin", b"Error consulta 3"):
            self.fixed(b"", diagnostic, 1)
            self.rejected("test_09_error_ultima_consulta_sin_salida_parcial")

    def test_09_salida_parcial_se_rechaza(self):
        self.fixed(b"[", b"Consulta 3: falta fin", 1)
        self.rejected("test_09_error_ultima_consulta_sin_salida_parcial")

    def test_10_clasificacion_de_errores(self):
        for method in ("test_11_json_invalido_y_concatenado", "test_12_constantes_no_json",
                       "test_13_utf8_invalido_y_bom", "test_14_raiz_no_lista",
                       "test_15_claves_duplicadas_en_varios_niveles", "test_16_archivo_inexistente_y_directorio"):
            with self.subTest(metodo=method):
                self.fixed(b"", "Entrada sintética inválida".encode(), 1)
                self.passed(method)
                self.fixed(b"", "Entrada sintética inválida".encode(), 2)
                self.rejected(method)

    def test_11_ayuda_y_argumentos(self):
        self.fixed("Uso sintético\n".encode())
        self.passed("test_17_ayuda_unicamente_argumento_unico")
        self.rejected("test_18_argumentos_invalidos")
        self.fixed(b"", "Argumentos inválidos".encode(), 2)
        self.passed("test_18_argumentos_invalidos")
        self.rejected("test_17_ayuda_unicamente_argumento_unico")

    def test_12_fixture_lectura_literal_no_ayuda(self):
        # Solo eco de la lista vacía; no implementa consultas ni validación.
        self.fixture("import pathlib,sys\nsys.stdout.buffer.write(pathlib.Path(sys.argv[-1]).read_bytes()+b'\\n')\n")
        self.passed("test_19_rutas_literales_con_guiones")
        self.fixed("Ayuda sintética\n".encode())
        self.rejected("test_19_rutas_literales_con_guiones")

    def test_13_ausencia_tipo_y_modo_no_lanzan_hijo(self):
        for kind in ("ausente", "directorio", "enlace", "fifo", "modo"):
            with self.subTest(tipo=kind):
                if kind == "directorio": self.script.mkdir()
                elif kind == "enlace": self.script.symlink_to(self.project / "booking_core.py")
                elif kind == "fifo": os.mkfifo(self.script)
                elif kind == "modo":
                    self.fixed()
                    self.script.chmod(0o664)
                try:
                    with patch.object(evaluar, "run_process") as launch:
                        self.rejected("test_02_consulta_disponible")
                        launch.assert_not_called()
                finally:
                    if self.script.is_dir(): self.script.rmdir()
                    elif self.script.exists() or self.script.is_symlink(): self.script.unlink()

    def delegator(self, *, alias=False, mutation="", partial=False):
        # Fixture solo para el centinela: no interpreta argumentos, no rechaza
        # duplicados/constantes/BOM/raíces ni implementa el contrato completo.
        imports = "from booking_core import check_booking as call, InvalidInput" if alias else "import booking_core"
        call = "call" if alias else "booking_core.check_booking"
        error = "InvalidInput" if alias else "booking_core.InvalidInput"
        source = f'''import json,sys
from pathlib import Path
{imports}
if __name__ == "__main__":
    data = json.loads(Path(sys.argv[1]).read_text())
    values = []
    try:
        for position, item in enumerate(data, 1):
            {mutation if mutation.startswith('antes:') else 'pass'}
            values.append({call}(item))
            {mutation if mutation.startswith('despues:') else 'pass'}
            {"print('[')" if partial else 'pass'}
    except {error} as exc:
        print(f"Consulta {{position}}: {{exc}}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(values))
'''
        source = source.replace("antes:", "").replace("despues:", "")
        self.fixture(source)

    def test_14_delegacion_admite_modulo_y_alias(self):
        for alias in (False, True):
            with self.subTest(alias=alias):
                self.delegator(alias=alias)
                self.passed("test_24_delegacion_completa_resultados_y_conservacion")
                self.passed("test_25_invalidinput_delegado_sin_resultado_parcial")

    def test_15_falta_de_delegacion(self):
        self.fixed(evaluar.encode([evaluar.AVAILABLE] * 3) + b"\n")
        self.rejected("test_24_delegacion_completa_resultados_y_conservacion")

    def test_16_mutaciones_antes_y_despues_de_delegar(self):
        for mutation in ("antes:item.clear()", "despues:item.clear()",
                         "despues:values[-1]['conflictos'] = ['alterado']"):
            with self.subTest(mutacion=mutation):
                self.delegator(mutation=mutation)
                self.rejected("test_24_delegacion_completa_resultados_y_conservacion")

    def test_17_invalidinput_y_salida_parcial(self):
        self.delegator(partial=True)
        self.rejected("test_25_invalidinput_delegado_sin_resultado_parcial")

    def test_18_importador_normal_y_dependencias_estandar(self):
        self.fixture("import booking_core\nimport fractions\nimport decimal\nVALUE = 1\n")
        self.passed("test_23_importacion_sin_efectos")

    def test_19_importacion_detecta_efectos_propios(self):
        fixtures = ["print('aviso')", "import os; os.write(2,b'aviso')",
                    "open('entrada', 'w')", "from pathlib import Path; Path(__file__).read_text()",
                    "import sys; sys.stdin.buffer.read()", "import os; os.read(0,1)",
                    "raise SystemExit(0)", "import socket; socket.socket()",
                    "import subprocess; subprocess.Popen(['PROHIBIDO'])"]
        for source in fixtures:
            with self.subTest(fixture=source):
                self.fixture(source + "\n")
                self.rejected("test_23_importacion_sin_efectos")

    def test_20_timeout_recoge_hijo_y_conserva_canales(self):
        self.fixture("import os,time\nprint(os.getpid(),flush=True)\ntime.sleep(60)\n")
        with patch.object(evaluar, "TIMEOUT", 0.3):
            self.rejected("test_02_consulta_disponible")
        trace = evaluar.QUERIES[-1]
        self.assertEqual(trace["estado"], "tiempo_agotado")
        pid = int(bytes.fromhex(trace["stdout_hex"]))
        with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_21_conservacion_detecta_cambios(self):
        self.fixture("import pathlib,sys\npathlib.Path(sys.argv[1]).write_text('alterado')\nprint('[]')\n")
        result = self.rejected("test_01_lote_vacio_y_espacio_exterior")
        self.assertIn("alteró entradas", str(result.failures))

    def test_22_utilidades_de_autoridad_y_entorno_reducido(self):
        self.assertEqual(Path(evaluar.run_process.__code__.co_filename).resolve(), evaluar.AUTHORITY_ROOT / "repair_case.py")
        (self.project / "repair_case.py").write_text("raise RuntimeError('NO IMPORTAR')\n")
        self.fixture("import os\nassert 'OPENAI_API_KEY' not in os.environ\nassert 'PYTHONPATH' not in os.environ\nprint('[]')\n")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SINTETICA", "PYTHONPATH": "NO_HEREDAR"}):
            self.passed("test_01_lote_vacio_y_espacio_exterior")

    def test_23_recomprueba_modo_antes_de_cada_hijo(self):
        self.fixed()
        case = evaluar.AcceptanceTests("test_02_consulta_disponible")
        case.project = self.project
        def change_after_setup():
            self.script.chmod(0o664)
            with case.query([case.save([])]):
                self.fail("No debía llegar al hijo")
        result = unittest.TestResult()
        with patch.object(case, "test_02_consulta_disponible", side_effect=change_after_setup), \
                patch.object(evaluar, "run_process") as launch:
            case.run(result)
        launch.assert_not_called()
        self.assertTrue(result.failures)
        self.assertEqual(result.errors, [])
        self.assertFalse(case.root.exists())

    def test_24_mutacion_booleano_a_entero_no_es_conservacion(self):
        for phase in ("antes:", "despues:"):
            with self.subTest(fase=phase):
                self.delegator(mutation=phase + "if 'anidado' in item: item['anidado'][1]['x'] = 1")
                self.rejected("test_24_delegacion_completa_resultados_y_conservacion")


def main():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvaluatorTests))
    print(json.dumps({"tipo": "fixtures_parciales_no_producto", "procesos": len(evaluar.QUERIES),
                      "consultas": evaluar.QUERIES}, ensure_ascii=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

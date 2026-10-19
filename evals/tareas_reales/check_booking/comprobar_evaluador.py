"""Controles acotados con respuestas prefijadas; no crea ni implementa el candidato."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import evaluar


AVAILABLE = b'{"disponible": true, "conflictos": []}\n'


def fixed_answer(available, conflicts):
    return json.dumps({"disponible": available, "conflictos": conflicts}, ensure_ascii=False).encode()


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="comprobar-check-booking-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "proyecto"
        self.project.mkdir()
        (self.project / "protegido.txt").write_text("Contenido sintético conservado\n", encoding="utf-8")

    def run_case(self, method="test_01_lista_vacia", *, stdout=AVAILABLE, stderr=b"", code=0, response=None):
        temporary = tempfile.TemporaryDirectory(prefix="entrada-", dir=self.root)
        self.addCleanup(temporary.cleanup)
        self.inputs = Path(temporary.name)
        case = evaluar.AcceptanceTests(method)
        case.project = self.project

        def prepare():
            # Se sustituye el lanzador: este archivo nunca se crea ni se ejecuta.
            case.script = self.project / "check_booking.py"
            case.root = self.inputs

        def fixed(command, **kwargs):
            return subprocess.CompletedProcess(command, code, stdout, stderr)

        result = unittest.TestResult()
        with patch.object(case, "setUp", side_effect=prepare), \
                patch.object(evaluar.subprocess, "run", side_effect=response or fixed) as run:
            case.run(result)
        self.assertGreater(run.call_count, 0)
        self.assertFalse((self.project / "check_booking.py").exists())
        return result, run.call_args_list

    def assert_passed(self, result):
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])

    def assert_rejected(self, result):
        self.assertTrue(result.failures)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])

    def test_control_y_lanzador_sin_credenciales(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SINTETICA_NO_HEREDAR",
                                     "AWS_SECRET_ACCESS_KEY": "SINTETICA_NO_HEREDAR",
                                     "PYTHONPATH": "SINTETICA_NO_HEREDAR"}):
            result, calls = self.run_case()
        self.assert_passed(result)
        command, options = calls[0].args[0], calls[0].kwargs
        self.assertEqual(command[:3], [str(Path(sys.executable).resolve()), "-B", str(self.project / "check_booking.py")])
        self.assertEqual(options["cwd"], self.inputs)
        self.assertEqual(options["timeout"], 10)
        self.assertFalse(options["shell"])
        self.assertEqual(options["stdin"], subprocess.DEVNULL)
        self.assertTrue(options["capture_output"])
        self.assertNotIn("text", options)
        self.assertEqual(options["env"]["PATH"], "")
        self.assertNotEqual(options["env"]["HOME"], os.environ.get("HOME"))
        for name in ("OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "PYTHONPATH"):
            self.assertNotIn(name, options["env"])

    def test_ejemplos_validos_con_respuestas_explicitas(self):
        cases = [("test_02_recursos_distintos_y_comparacion_literal", True, []),
                 ("test_03_solapamiento_igualdad_y_contencion", False, ["conflicto"]),
                 ("test_04_adyacentes_ambos_extremos", True, []),
                 ("test_05_intervalos_separados", True, []),
                 ("test_06_varios_conflictos_conservan_orden", False, ["z", "a", "medio"]),
                 ("test_07_reservas_pueden_solaparse_entre_si", False, ["una", "dos"]),
                 ("test_08_unicode_cadenas_literales_y_ids_distintos", False, [' id, "uno"\r\n🗓 ', "ID", "id"]),
                 ("test_09_fechas_validas_bisiestos_y_extremos", False, ["mismo"]),
                 ("test_22_rutas_con_guion_tras_fin_de_opciones", True, []),
                 ("test_23_contenido_tratado_como_datos", False,
                  ["__import__('pathlib').Path('NO_EJECUTAR').write_text('centinela')"])]
        for method, available, conflicts in cases:
            with self.subTest(metodo=method):
                result, _ = self.run_case(method, stdout=fixed_answer(available, conflicts))
                self.assert_passed(result)

    def test_rechaza_falsos_positivos_negativos_y_orden(self):
        cases = [("test_03_solapamiento_igualdad_y_contencion", True, []),
                 ("test_04_adyacentes_ambos_extremos", False, ["antes", "despues"]),
                 ("test_02_recursos_distintos_y_comparacion_literal", False, ["otra"]),
                 ("test_06_varios_conflictos_conservan_orden", False, ["a", "medio", "z"]),
                 ("test_06_varios_conflictos_conservan_orden", False, ["z", "a"]),
                 ("test_08_unicode_cadenas_literales_y_ids_distintos", False, ['id, "uno"\r\n🗓', "ID", "id"])]
        for method, available, conflicts in cases:
            with self.subTest(metodo=method, conflictos=conflicts):
                result, _ = self.run_case(method, stdout=fixed_answer(available, conflicts))
                self.assert_rejected(result)

    def test_rechaza_json_y_tipos_de_salida_incorrectos(self):
        variants = [b"", b"\xff", b"\xef\xbb\xbf" + AVAILABLE, b"[]", b"null", b"true", b"{}",
                    b'{"disponible": 1, "conflictos": []}', b'{"disponible": true, "conflictos": null}',
                    b'{"disponible": true, "conflictos": [1]}', b'{"disponible": true, "conflictos": [], "extra": 0}',
                    b'{"disponible": true, "disponible": true, "conflictos": []}',
                    b'{"disponible": NaN, "conflictos": []}', AVAILABLE + AVAILABLE, b"aviso\n" + AVAILABLE]
        for raw in variants:
            with self.subTest(salida=raw):
                result, _ = self.run_case(stdout=raw)
                self.assert_rejected(result)

    def test_admite_representaciones_json_equivalentes(self):
        for raw in (b'  {"conflictos": [], "disponible": true}\r\n',
                    b'{"disponible":true,"conflictos":[]}'):
            with self.subTest(salida=raw):
                result, _ = self.run_case(stdout=raw)
                self.assert_passed(result)
        result, _ = self.run_case("test_08_unicode_cadenas_literales_y_ids_distintos", stdout=json.dumps(
            {"disponible": False, "conflictos": [' id, "uno"\r\n🗓 ', "ID", "id"]}, ensure_ascii=True).encode())
        self.assert_passed(result)

    def test_rechaza_codigos_y_stderr_incorrectos(self):
        for options in ({"stderr": b"aviso"}, {"code": 1}, {"code": 2}):
            with self.subTest(opciones=options):
                result, _ = self.run_case(**options)
                self.assert_rejected(result)

    def test_entradas_invalidas_requieren_error_localizado(self):
        methods = [name for name in unittest.TestLoader().getTestCaseNames(evaluar.AcceptanceTests)
                   if name.startswith(tuple(f"test_{number:02d}_" for number in (*range(10, 20), 24)))]

        def fixed_error(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, b"", (command[-1] + ": entrada inválida sintética").encode())

        for method in methods:
            with self.subTest(metodo=method):
                result, _ = self.run_case(method, response=fixed_error)
                self.assert_passed(result)
                result, _ = self.run_case(method)
                self.assert_rejected(result)

    def test_error_sin_causa_sin_archivo_o_con_salida_parcial(self):
        for stderr in (b"", b"entrada inv\xc3\xa1lida", "solicitud sintética.json".encode()):
            with self.subTest(diagnostico=stderr):
                result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1, stdout=b"", stderr=stderr)
                self.assert_rejected(result)
        result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1,
                                 stderr="solicitud sintética.json: fecha imposible".encode())
        self.assert_rejected(result)

    def test_diagnostico_nombre_unicode_literal(self):
        result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1, stdout=b"",
                                 stderr="solicitud sintética.json: fecha imposible".encode())
        self.assert_passed(result)

    def test_diagnostico_ascii_del_nombre(self):
        # Respuesta prefijada con la representación que rechazó el experimento.
        result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1, stdout=b"",
                                 stderr=b"Archivo 'solicitud sint\\xe9tica.json': fecha imposible\n")
        self.assert_passed(result)

    def test_diagnostico_representacion_json_del_nombre(self):
        result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1, stdout=b"",
                                 stderr=b'Archivo "solicitud sint\\u00e9tica.json": fecha imposible\n')
        self.assert_passed(result)

    def test_diagnostico_rechaza_otro_archivo_o_identificacion_ausente(self):
        diagnostics = [b"", b"\xff", b"fecha imposible", b"otro.json: fecha imposible",
                       "otra solicitud.json: fecha imposible".encode(),
                       b"'solicitud sint\\xe8tica.json': fecha imposible",
                       b"'solicitud sint\\\\xe9tica.json': fecha imposible"]
        for diagnostic in diagnostics:
            with self.subTest(diagnostico=diagnostic):
                result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1,
                                         stdout=b"", stderr=diagnostic)
                self.assert_rejected(result)

    def test_diagnostico_rechaza_nombre_sin_causa(self):
        name = "solicitud sintética.json"
        names = (name, repr(name), ascii(name), json.dumps(name))
        for diagnostic in (*names, " : ".join(names)):
            with self.subTest(diagnostico=diagnostic):
                result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1,
                                         stdout=b"", stderr=(diagnostic + ": \n").encode())
                self.assert_rejected(result)

    def test_diagnostico_valido_no_admite_codigo_incorrecto_o_salida_parcial(self):
        name = "solicitud sintética.json"
        for representation in (name, ascii(name)):
            for code, stdout in ((0, b""), (2, b""), (1, AVAILABLE), (1, b" ")):
                with self.subTest(nombre=representation, codigo=code, salida=stdout):
                    result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=code,
                                             stdout=stdout, stderr=(representation + ": fecha imposible").encode())
                    self.assert_rejected(result)

    def test_ayuda_y_argumentos_tienen_canales_propios(self):
        result, _ = self.run_case("test_20_argumentos_incorrectos", code=2, stdout=b"", stderr=b"Argumentos invalidos")
        self.assert_passed(result)
        result, _ = self.run_case("test_20_argumentos_incorrectos")
        self.assert_rejected(result)
        result, _ = self.run_case("test_21_ayuda_sin_archivos", stdout=b"Uso sintetico: check_booking.py archivo")
        self.assert_passed(result)
        result, _ = self.run_case("test_21_ayuda_sin_archivos", stdout=b"", stderr=b"error", code=2)
        self.assert_rejected(result)

    def test_ausencia_es_asercion_sin_invocar_cli(self):
        case = evaluar.AcceptanceTests("test_01_lista_vacia")
        case.project = self.project
        result = unittest.TestResult()
        with patch.object(evaluar.subprocess, "run") as run:
            case.run(result)
        self.assert_rejected(result)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("CLI no invocada", result.failures[0][1])
        run.assert_not_called()

    def test_conservacion_incluso_ante_respuesta_incorrecta(self):
        def altered(command, **kwargs):
            (self.inputs / command[-1]).write_bytes(b"alterada")
            (self.project / "protegido.txt").write_bytes(b"alterado")
            return subprocess.CompletedProcess(command, 0, b"{}", b"")

        result, _ = self.run_case(response=altered)
        self.assert_rejected(result)
        text = "\n".join(message for _, message in result.failures)
        self.assertIn("La CLI alteró las entradas", text)
        self.assertIn("La CLI alteró el proyecto", text)
        self.assertGreaterEqual(len(result.failures), 3)

    def test_timeout_y_excepcion_conservan_comprobaciones(self):
        for error in (subprocess.TimeoutExpired("python", 10), OSError("Fallo sintético del lanzador")):
            def broken(command, **kwargs):
                (self.project / "protegido.txt").write_bytes(b"alterado")
                raise error

            with self.subTest(error=type(error).__name__):
                (self.project / "protegido.txt").write_bytes(b"original")
                result, _ = self.run_case(response=broken)
                self.assertTrue(any("La CLI alteró el proyecto" in message for _, message in result.failures))
                if isinstance(error, subprocess.TimeoutExpired):
                    self.assert_rejected(result)
                    self.assertTrue(any("excedió 10 segundos" in message for _, message in result.failures))
                else:
                    self.assertEqual(len(result.errors), 1)

    def test_identidades_compatibles_con_inventario_actual(self):
        from repair_project import static_test_ids
        expected = static_test_ids(Path(evaluar.__file__).read_bytes(), evaluar.__name__)
        suite = unittest.TestLoader().loadTestsFromTestCase(evaluar.AcceptanceTests)
        self.assertEqual(sorted(case.id() for case in suite), expected)
        self.assertEqual(len(expected), len(set(expected)))
        self.assertTrue(expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)

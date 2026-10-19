"""Comprobaciones del evaluador con respuestas prefijadas; no implementa CSV."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import evaluar


GOOD = (
    'origen,consulta_estado,consulta_codigo_salida,caso,ejecucion_estado,ejecucion_codigo_salida,'
    'intentos_registrados,max_intentos,invocaciones_total,max_invocaciones,duracion_segundos\n'
    'consulta.json,completada,0,caso_sintético,aprobada,0,2,7,11,23,12.3456789\n'
).encode("utf-8")


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="comprobar-export-csv-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "proyecto"
        self.inputs = self.root / "entradas"
        self.project.mkdir()
        self.inputs.mkdir()
        (self.project / "protegido.py").write_text("# No se importa ni ejecuta.\n", encoding="utf-8")

    def run_case(self, method="test_01_columnas_y_correspondencia", *, stdout=GOOD,
                 stderr=b"", code=0, response=None):
        temporary = tempfile.TemporaryDirectory(prefix="respuesta-", dir=self.root)
        self.addCleanup(temporary.cleanup)
        self.inputs = Path(temporary.name)
        case = evaluar.AcceptanceTests(method)
        case.project = self.project

        def prepare():
            # No se crea export_runs.py. Solo se ejercitan el lanzador y las
            # aserciones con subprocess sustituido por una respuesta fija.
            case.script = self.project / "export_runs.py"
            case.root = self.inputs

        def fixed(command, **kwargs):
            return subprocess.CompletedProcess(command, code, stdout, stderr)

        result = unittest.TestResult()
        with patch.object(case, "setUp", side_effect=prepare), \
                patch.object(evaluar.subprocess, "run", side_effect=response or fixed) as run:
            case.run(result)
        self.assertGreater(run.call_count, 0)
        return result, run.call_args_list

    def assert_passed(self, result):
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])

    def test_control_y_lanzamiento_sin_credenciales(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SINTETICA_NO_HEREDAR",
                                     "AWS_SECRET_ACCESS_KEY": "SINTETICA_NO_HEREDAR",
                                     "PYTHONPATH": "SINTETICA_NO_HEREDAR"}):
            result, calls = self.run_case()
        self.assert_passed(result)
        command = calls[0].args[0]
        options = calls[0].kwargs
        self.assertEqual(command, [str(Path(sys.executable).resolve()), "-B",
                                   str(self.project / "export_runs.py"), "consulta.json"])
        self.assertEqual(options["cwd"], self.inputs)
        self.assertEqual(options["timeout"], 10)
        self.assertFalse(options["shell"])
        self.assertEqual(options["stdin"], subprocess.DEVNULL)
        self.assertTrue(options["capture_output"])
        self.assertNotIn("text", options)
        self.assertEqual(options["env"]["PATH"], "")
        for name in ("OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "PYTHONPATH"):
            self.assertNotIn(name, options["env"])
        self.assertNotEqual(options["env"]["HOME"], os.environ.get("HOME"))
        self.assertFalse((self.project / "export_runs.py").exists())

    def test_rechaza_salida_incorrecta(self):
        variants = [GOOD.replace(b"origen,consulta_estado", b"consulta_estado,origen"),
                    b"\xef\xbb\xbf" + GOOD, GOOD.replace(b"\n", b"\r\n"), b"\xff",
                    GOOD.replace(b"12.3456789", b"12.346"), GOOD + b"\n", GOOD[:-1]]
        for output in variants:
            with self.subTest(salida=output[:60]):
                result, _ = self.run_case(stdout=output)
                self.assertTrue(result.failures)
                self.assertEqual(result.errors, [])
        for kwargs in ({"stderr": b"aviso\n"}, {"code": 1}):
            with self.subTest(variante=kwargs):
                result, _ = self.run_case(**kwargs)
                self.assertTrue(result.failures)
                self.assertEqual(result.errors, [])

    def test_acepta_comillas_opcionales(self):
        # Otra codificación válida del mismo fixture fijo; no fija QUOTE_MINIMAL.
        output = "\n".join(
            ",".join('"' + cell + '"' for cell in line.split(","))
            for line in GOOD.decode("utf-8").splitlines()) + "\n"
        result, _ = self.run_case(stdout=output.encode("utf-8"))
        self.assert_passed(result)

    def test_acepta_duracion_cientifica_equivalente(self):
        for token in (b"1.23456789e1", b"123456789E-7", b"12.3456789000"):
            with self.subTest(duracion=token):
                result, _ = self.run_case(stdout=GOOD.replace(b"12.3456789", token))
                self.assert_passed(result)

    def test_rechaza_duracion_alterada_no_finita_vacia_o_no_decimal(self):
        for token in (b"1.23456788e1", b"12.345678900000000000000000001", b"NaN",
                      b"sNaN", b"Infinity", b"-Infinity", b"", b"0", b"1_2.3456789", b" 12.3456789"):
            with self.subTest(duracion=token):
                result, _ = self.run_case(stdout=GOOD.replace(b"12.3456789", token))
                self.assertTrue(result.failures)
                self.assertEqual(result.errors, [])

    def test_otros_campos_siguen_siendo_literales(self):
        for before, after in ((b"consulta.json", b"./consulta.json"),
                              (b"caso_sint", b" caso_sint"), (b",2,7,", b",2e0,7,")):
            with self.subTest(campo=before):
                result, _ = self.run_case(stdout=GOOD.replace(before, after))
                self.assertTrue(result.failures)
                self.assertEqual(result.errors, [])

    def test_enteros_grandes_exigen_representacion_entera_exacta(self):
        for variant in ("literal", "cientifica", "decimal", "alterada"):
            tokens = iter(("9007199254740993", "1" + "0" * 309, "1" + "0" * 5000))

            def fixed(command, **kwargs):
                token = next(tokens)
                duration = {"literal": token, "cientifica": token + "e0",
                            "decimal": token + ".0", "alterada": token[:-1] + "2"}[variant]
                row = ["grande.json", "completada", "0", "caso_sintético", "aprobada",
                       *([token] * 5), duration]
                raw = GOOD.split(b"\n")[0] + b"\n" + (",".join(row) + "\n").encode()
                return subprocess.CompletedProcess(command, 0, raw, b"")

            with self.subTest(variante=variant):
                result, calls = self.run_case("test_05_enteros_sin_limites_ni_conversion_a_float", response=fixed)
                self.assertEqual(len(calls), 3)
                self.assertEqual(result.errors, [])
                self.assertEqual(bool(result.failures), variant != "literal")

    def test_null_y_cero_entero_no_se_confunden(self):
        unknown = b"desconocida.json,incompleta,1,,,,,,,,\n"
        zero = "ceros.json,completada,0,caso_sintético,aprobada,0,0,0,0,0,0\n".encode()
        for missing, number, valid in ((unknown, zero, True),
                                       (unknown[:-1] + b"0\n", zero, False),
                                       (unknown, zero[:-2] + b"\n", False),
                                       (unknown, zero[:-2] + b"0e0\n", False),
                                       (unknown, zero[:-2] + b"0.0\n", False)):
            with self.subTest(desconocida=missing, cero=number):
                raw = GOOD.split(b"\n")[0] + b"\n" + missing + number
                result, _ = self.run_case("test_03_null_frente_a_ceros", stdout=raw)
                self.assertEqual(result.errors, [])
                self.assertEqual(bool(result.failures), not valid)

    def test_conservacion_de_ambos_arboles_si_falla_la_asercion(self):
        def changed(command, **kwargs):
            (self.inputs / "consulta.json").write_bytes(b"ALTERADA")
            cache = self.project / "__pycache__"
            cache.mkdir()
            (cache / "intruso.pyc").write_bytes(b"CACHE")
            return subprocess.CompletedProcess(command, 0, "cabecera errónea\n".encode(), b"")

        result, _ = self.run_case(response=changed)
        self.assertEqual(result.errors, [])
        diagnostics = "\n".join(text for _, text in result.failures)
        self.assertIn("La CLI alteró las entradas", diagnostics)
        self.assertIn("La CLI alteró el proyecto", diagnostics)
        self.assertGreaterEqual(len(result.failures), 3)  # salida y ambos inventarios

    def test_timeout_tambien_comprueba_conservacion(self):
        def timeout(command, **kwargs):
            (self.project / "intruso.txt").write_bytes(b"alterado")
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        result, _ = self.run_case(response=timeout)
        self.assertEqual(result.errors, [])
        diagnostics = "\n".join(text for _, text in result.failures)
        self.assertIn("excedió 10 segundos", diagnostics)
        self.assertIn("La CLI alteró el proyecto", diagnostics)

    def test_error_tecnico_no_se_convierte_en_exito(self):
        def broken(command, **kwargs):
            (self.project / "intruso.txt").write_bytes(b"alterado")
            raise RuntimeError("Fallo sintético del lanzador")

        result, _ = self.run_case(response=broken)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Fallo sintético", result.errors[0][1])
        self.assertTrue(any("La CLI alteró el proyecto" in text for _, text in result.failures))

    def test_inventario_no_lee_configuracion_y_detecta_caches(self):
        private = self.project / ".env"
        private.write_bytes(b"SINTETICO")
        original = Path.read_bytes

        def protected(path):
            if path == private:
                raise AssertionError("No leer configuración personal")
            return original(path)

        with patch.object(Path, "read_bytes", protected):
            before = evaluar.snapshot(self.project, project=True)
            cache = self.project / "__pycache__"
            cache.mkdir()
            (cache / "nuevo.pyc").write_bytes("sintético".encode())
            after = evaluar.snapshot(self.project, project=True)
        self.assertNotEqual(before, after)
        self.assertIn("__pycache__/nuevo.pyc", after)

    def test_precision_admite_valores_finitos_y_rechaza_redondeo(self):
        tokens = ("0.12345678901234567890123456789", "1e-200", "1e400", "-0.0")
        equivalent = ("1.2345678901234567890123456789e-1", "0.1e-199", "10e399", "0")
        for variant in ("literal", "equivalente", "redondeo", "cero_vacio", "cero_alterado"):
            outputs = iter(equivalent if variant == "equivalente" else tokens)

            def fixed(command, **kwargs):
                token = next(outputs)
                if variant == "redondeo" and token == tokens[0]:
                    token = "0.12345678901234568"
                if token == "-0.0" and variant in ("cero_vacio", "cero_alterado"):
                    token = "" if variant == "cero_vacio" else "0.00000000000000000001"
                raw = GOOD.replace(b"consulta.json", b"precision.json").replace(b"12.3456789", token.encode())
                return subprocess.CompletedProcess(command, 0, raw, b"")

            with self.subTest(variante=variant):
                result, _ = self.run_case("test_06_duracion_sin_redondeo_ni_limite_float", response=fixed)
                self.assertEqual(result.errors, [])
                self.assertEqual(bool(result.failures), variant not in ("literal", "equivalente"))

    def test_entradas_invalidas_no_se_dan_por_buenas(self):
        result, _ = self.run_case("test_10_json_invalido_y_claves_duplicadas",
                                  code=1, stdout=b"", stderr="invalida.json: JSON inválido\n".encode())
        self.assert_passed(result)
        result, _ = self.run_case("test_10_json_invalido_y_claves_duplicadas")
        self.assertTrue(result.failures)
        self.assertEqual(result.errors, [])

    def test_rechaza_csv_parcial_y_diagnostico_no_localizado(self):
        method = "test_14_entradas_ilegibles_y_ausencia_de_csv_parcial"
        diagnostic = b"ausente.json directorio rota.json version.json: entrada incorrecta\n"
        good, _ = self.run_case(method, code=1, stdout=b"", stderr=diagnostic)
        self.assert_passed(good)
        partial, _ = self.run_case(method, code=1, stdout=GOOD, stderr=diagnostic)
        self.assertTrue(partial.failures)
        self.assertEqual(partial.errors, [])
        unlocated, _ = self.run_case(method, code=1, stdout=b"", stderr=b"error\n")
        self.assertTrue(unlocated.failures)
        self.assertEqual(unlocated.errors, [])

    def test_ausencia_es_fallo_explicito_sin_invocar_cli(self):
        case = evaluar.AcceptanceTests("test_01_columnas_y_correspondencia")
        case.project = self.project
        result = unittest.TestResult()
        with patch.object(evaluar.subprocess, "run") as run:
            case.run(result)
        run.assert_not_called()
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])
        self.assertIn("Funcionalidad pendiente: falta export_runs.py", result.failures[0][1])

    def test_identidades_compatibles_con_runner_y_sin_descubrimiento_en_ci(self):
        from repair_project import static_test_ids
        actual = unittest.defaultTestLoader.getTestCaseNames(evaluar.AcceptanceTests)
        expected = static_test_ids(Path(evaluar.__file__).read_bytes(), "__main__")
        self.assertEqual(expected, [f"__main__.AcceptanceTests.{name}" for name in actual])
        self.assertEqual(len(actual), 17)
        self.assertNotIn("tests", Path(evaluar.__file__).relative_to(evaluar.AUTHORITY_ROOT).parts)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Controles acotados con respuestas prefijadas; no crea ni implementa el candidato."""

import json
import copy
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

    def api_answer(self, **changes):
        call = {"error": None, "es_invalid_input": False, "resultado": {"disponible": True, "conflictos": []},
                "tipo_correcto": True, "conservada": True, "stdout": "", "stderr": ""}
        call.update(changes)
        return {"import_stdout": "", "import_stderr": "", "invalid_input": True, "llamadas": [call]}

    def run_api_case(self, report, method="test_25_api_disponibilidad", **options):
        original = Path.is_file
        def regular(path):
            return True if path == self.project / "booking_core.py" else original(path)
        # Simula solo la precondición de presencia; no crea ningún candidato.
        with patch.object(Path, "is_file", regular):
            return self.run_case(method, stdout=json.dumps(report).encode(), **options)

    def test_api_control_y_lanzador(self):
        result, calls = self.run_api_case(self.api_answer())
        self.assert_passed(result)
        command, options = calls[0].args[0], calls[0].kwargs
        self.assertEqual(command[:3], [str(Path(sys.executable).resolve()), "-B", "-c"])
        self.assertEqual(command[3], evaluar.API_CHILD)
        self.assertEqual(command[4], str(self.project))
        self.assertEqual(options["cwd"], self.inputs)
        self.assertEqual(options["timeout"], 10)
        self.assertEqual(options["stdin"], subprocess.DEVNULL)
        self.assertFalse(options["shell"])
        self.assertEqual(options["env"]["PATH"], "")
        self.assertFalse((self.project / "booking_core.py").exists())

    def test_api_rechaza_resultado_mutacion_salida_y_tipos(self):
        for changes in ({"resultado": {"disponible": False, "conflictos": ["inventado"]}},
                        {"tipo_correcto": False}, {"conservada": False},
                        {"stdout": "aviso"}, {"stderr": "aviso"}, {"error": "fallo"}):
            with self.subTest(cambio=changes):
                result, _ = self.run_api_case(self.api_answer(**changes))
                self.assert_rejected(result)

    def test_api_rechaza_importacion_con_salida_y_excepcion_base_erronea(self):
        for field, value in (("import_stdout", "aviso"), ("import_stderr", "aviso"), ("invalid_input", False)):
            report = self.api_answer()
            report[field] = value
            result, _ = self.run_api_case(report)
            self.assert_rejected(result)

    def test_api_invalidinput_no_cualquier_excepcion_ni_explicacion_vacia(self):
        report = self.api_answer(error="fecha imposible", es_invalid_input=True, resultado=None, tipo_correcto=False)
        result, _ = self.run_api_case(report, "test_35_api_validacion_completa")
        self.assert_passed(result)
        for changes in ({"es_invalid_input": False}, {"error": ""}, {"error": "  "},
                        {"conservada": False}, {"stdout": "aviso"}):
            invalid = copy.deepcopy(report)
            invalid["llamadas"][0].update(changes)
            result, _ = self.run_api_case(invalid, "test_35_api_validacion_completa")
            self.assert_rejected(result)

    def test_api_ausente_es_asercion_sin_importar(self):
        case = evaluar.AcceptanceTests("test_25_api_disponibilidad")
        case.project, case.root = self.project, self.root
        result = unittest.TestResult()
        with patch.object(case, "setUp"), patch.object(evaluar.subprocess, "run") as run:
            case.run(result)
        self.assert_rejected(result)
        self.assertIn("API no importada", result.failures[0][1])
        run.assert_not_called()
        self.assertFalse((self.project / "booking_core.py").exists())

    def test_api_rechaza_canales_codigos_e_informe_incompleto(self):
        for options in ({"code": 1}, {"stderr": b"aviso"}):
            result, _ = self.run_api_case(self.api_answer(), **options)
            self.assert_rejected(result)
        for report in ({}, dict(self.api_answer(), llamadas=[])):
            result, _ = self.run_api_case(report)
            self.assert_rejected(result)

    def probe_stub(self, behavior, *, mode="llamadas"):
        """Ejecutar la sonda contra un módulo prefijado solo en sys.modules del hijo."""
        payload = self.root / "sonda.json"
        documents = [evaluar.document()] if mode == "llamadas" else [evaluar.document(), evaluar.document([evaluar.booking("r")])]
        payload.write_text(json.dumps({"modo": mode, "documentos": documents}))
        bootstrap = ('import sys, types\n'
                     'stub = types.ModuleType("booking_core")\n'
                     'class InvalidInput(ValueError): pass\n'
                     'stub.InvalidInput = InvalidInput\n' + behavior + '\n'
                     'stub.check_booking = fixed\n'
                     'sys.modules["booking_core"] = stub\n')
        with evaluar.process_environment("evaluation") as environment:
            completed = subprocess.run([str(Path(sys.executable).resolve()), "-B", "-c",
                                        bootstrap + evaluar.API_CHILD, str(self.project), str(payload)],
                                       cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True,
                                       timeout=10, shell=False, env=environment)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertFalse((self.project / "booking_core.py").exists())
        return json.loads(completed.stdout)

    def test_sonda_real_detecta_mutacion_salida_y_excepcion_equivocada(self):
        snippets = [
            ('def fixed(data):\n    return {"disponible": True, "conflictos": []}', "conservada", True),
            ('def fixed(data):\n    data["solicitud"]["recurso"] = "cambio"\n    return {"disponible": True, "conflictos": []}', "conservada", False),
            ('def fixed(data):\n    print("salida indebida")\n    return {"disponible": True, "conflictos": []}', "stdout", "salida indebida\n"),
            ('def fixed(data):\n    import os\n    os.write(2, b"salida binaria")\n    return {"disponible": True, "conflictos": []}', "stderr", "salida binaria"),
            ('def fixed(data):\n    raise TypeError("equivocada")', "es_invalid_input", False),
            ('def fixed(data):\n    raise InvalidInput("dominio inválido")', "es_invalid_input", True),
            ('def fixed(data):\n    return {"disponible": 1, "conflictos": ()}', "tipo_correcto", False),
            ('def fixed(data):\n    data.clear()\n    raise InvalidInput("tras mutar")', "conservada", False),
        ]
        for snippet, field, expected in snippets:
            with self.subTest(comportamiento=snippet):
                report = self.probe_stub(snippet)
                self.assertEqual(report["llamadas"][0][field], expected)

    def test_sonda_real_detecta_resultados_compartidos(self):
        report = self.probe_stub('shared = {"disponible": True, "conflictos": []}\n'
                                 'def fixed(data): return shared', mode="independencia")
        self.assertEqual(report["segundo_tras_mutacion"],
                         {"disponible": False, "conflictos": ["CENTINELA_NO_COMPARTIDA"]})
        result, _ = self.run_api_case(report, "test_37_api_independencia_de_resultados")
        self.assert_rejected(result)

    def test_delegacion_rechaza_cli_independiente(self):
        sentinel = {"centinela": "delegación; no documento de dominio"}
        report = {"import_stdout": "", "import_stderr": "", "invalid_input": True,
                  "alias_error": True, "llamadas_delegadas": [sentinel], "codigo": 1,
                  "stdout": "", "stderr": "solicitud sintética.json: claves inválidas"}
        result, _ = self.run_api_case(report, "test_38_delegacion_cli_y_nombres_importables")
        self.assert_rejected(result)

    def test_sonda_delegacion_admite_alias_y_acceso_al_modulo(self):
        # Sustituciones acotadas del import y arranque CLI en un hijo; no archivos
        # candidatos ni algoritmo de reservas. La sonda real aplica el centinela.
        sentinel = {"centinela": "delegación; no documento de dominio"}
        for alias in (True, False):
            for error in (True, False):
                with self.subTest(alias=alias, error=error):
                    payload = self.root / "sonda.json"
                    payload.write_text(json.dumps({"modo": "delegacion", "error": error, "documento": sentinel}))
                    (self.root / "solicitud sintética.json").write_text(json.dumps(sentinel))
                    bootstrap = r'''import sys, types, importlib, runpy, json
from pathlib import Path
core = types.ModuleType("booking_core")
class InvalidInput(ValueError): pass
core.InvalidInput = InvalidInput
core.check_booking = lambda data: None
sys.modules["booking_core"] = core
original_import = importlib.import_module
def importing(name):
    if name != "check_booking": return original_import(name)
    cli = types.ModuleType(name)
    cli.InvalidInput = core.InvalidInput
    cli.check_booking = core.check_booking if ALIAS else lambda data: core.check_booking(data)
    return cli
importlib.import_module = importing
def running(path, run_name):
    try:
        answer = core.check_booking(json.loads(Path(sys.argv[1]).read_text()))
    except core.InvalidInput:
        sys.stderr.buffer.write((ascii(sys.argv[1]) + ": entrada inválida\n").encode("utf-8"))
        raise SystemExit(1)
    sys.stdout.buffer.write(json.dumps(answer).encode("utf-8"))
    raise SystemExit(0)
runpy.run_path = running
'''.replace("ALIAS", repr(alias))
                    with evaluar.process_environment("evaluation") as environment:
                        completed = subprocess.run([str(Path(sys.executable).resolve()), "-B", "-c",
                                                    bootstrap + evaluar.API_CHILD, str(self.project), str(payload)],
                                                   cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True,
                                                   timeout=10, shell=False, env=environment)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    report = json.loads(completed.stdout)
                    self.assertEqual(report["llamadas_delegadas"], [sentinel, sentinel])
                    self.assertIs(report["alias_error"], True)
                    self.assertEqual(report["codigo"], 1 if error else 0)
                    if error:
                        self.assertIs(report["alias_excepcion"], True)
                        self.assertEqual(report["stdout"], "")
                    else:
                        self.assertEqual(json.loads(report["stdout"]),
                                         {"disponible": False, "conflictos": ["centinela del núcleo"]})
                    self.assertFalse((self.project / "booking_core.py").exists())

    def test_diagnostico_etiqueta_sin_causa_no_basta(self):
        for representation in ("solicitud sintética.json", ascii("solicitud sintética.json")):
            result, _ = self.run_case("test_24_validacion_total_sin_salida_parcial", code=1, stdout=b"",
                                     stderr=("Archivo " + representation + ":\n").encode())
            self.assert_rejected(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)

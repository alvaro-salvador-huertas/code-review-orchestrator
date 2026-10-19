"""Cobertura permanente de JSON por CLI, sin registros históricos ni agentes.

Reutiliza las aserciones existentes sin lanzar suites secundarias: cada método
forma parte del descubrimiento habitual. Solo los inspectores se ejecutan como
procesos hijos, sobre datos sintéticos y con los límites de los evaluadores.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings

import inspect_run
from evals.tareas_reales.inspect_json import comprobar_anidamiento, comprobar_hallazgos, evaluar


PROJECT = Path(__file__).resolve().parents[1]


class TestInspectJsonAcceptance(evaluar.AcceptanceTests):
    project = PROJECT

    def test_json_escape_no_reconocido_conserva_consulta_y_stderr_vacio(self):
        control = self.query("--format", "json")
        data = evaluar.strict_json(control.stdout)
        self.assertEqual(data, {
            "version_esquema": 1,
            "consulta": {"estado": "completada", "codigo_salida": 0, "incidencias": []},
            "ejecucion": self.expected,
        })
        self.assertEqual((control.returncode, control.stderr), (0, ""))

        reference = self.repair_dir / "referencia/test_solution.py"
        # Bytes crudos: el escape llega al AST del inspector, no al compilador
        # de este fixture. Se conservan los identificadores y el centinela.
        reference.write_bytes(reference.read_bytes() + br'patron = "\d"' + b"\n")
        completed = self.query("--format", "json")
        self.assertEqual(evaluar.strict_json(completed.stdout), data)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # query() inventaría contenido y metadatos, incluido el centinela de
        # ejecución: ni referencias ni registros pueden modificarse al consultar.
        self.assertEqual(completed.stderr, "")

    def test_json_sintaxis_invalida_localiza_incidencias_sin_stderr(self):
        reference = self.repair_dir / "referencia/test_solution.py"
        reference.write_bytes(reference.read_bytes() + b"def sin_cierre(\n")
        issues = self.assert_json(self.expected, code=1)
        for phase in ("inicial", "posterior"):
            self.assertTrue(any(str(reference) in issue
                                and str(self.repair_dir / phase / "stderr.txt") in issue
                                and "sintaxis" in issue for issue in issues), issues)

    def test_texto_conserva_advertencias_ast_y_contenido(self):
        control = self.assert_text_formats(0)
        reference = self.repair_dir / "referencia/test_solution.py"
        reference.write_bytes(reference.read_bytes() + br'patron = "\d"' + b"\n")
        default = self.query()
        explicit = self.query("--format", "text")
        self.assertEqual((default.returncode, default.stdout), (0, control.stdout))
        self.assertEqual((explicit.returncode, explicit.stdout, explicit.stderr),
                         (default.returncode, default.stdout, default.stderr))
        # Python 3.12 (la versión de CI) avisa sin forzar filtros en el hijo.
        self.assertIn("SyntaxWarning", default.stderr)

        before = evaluar.snapshot(self.root)
        out = io.StringIO()
        with warnings.catch_warnings(record=True) as emitted, redirect_stdout(out):
            warnings.simplefilter("always", SyntaxWarning)
            self.assertEqual(inspect_run.inspect_run(self.general), 0)
        self.assertEqual(out.getvalue(), control.stdout)
        self.assertTrue(any(issubclass(item.category, SyntaxWarning) for item in emitted))
        self.assertEqual(evaluar.snapshot(self.root), before)

    def test_json_restaura_politica_de_avisos_tras_lectura_y_sintaxis_invalida(self):
        reference = self.repair_dir / "referencia/test_solution.py"
        original = reference.read_bytes()
        for suffix, code in ((br'patron = "\d"' + b"\n", 0), (b"def sin_cierre(\n", 1)):
            reference.write_bytes(original + suffix)
            for action in ("always", "error", "ignore"):
                with self.subTest(codigo=code, filtro=action):
                    before = evaluar.snapshot(self.root)
                    out, err = io.StringIO(), io.StringIO()
                    with warnings.catch_warnings(record=True) as emitted:
                        for category in (SyntaxWarning, DeprecationWarning):
                            warnings.simplefilter(action, category)
                        filters = warnings.filters[:]
                        with redirect_stdout(out), redirect_stderr(err):
                            result = inspect_run.main(["--run", str(self.general), "--format", "json"])
                        self.assertEqual(result, code)
                        self.assertEqual(err.getvalue(), "")
                        self.assertEqual(evaluar.strict_json(out.getvalue())["consulta"]["estado"],
                                         "incompleta" if code else "completada")
                        self.assertEqual(emitted, [])
                        self.assertEqual(warnings.filters, filters)
                        for category in (SyntaxWarning, DeprecationWarning):
                            if action == "error":
                                with self.assertRaises(category):
                                    warnings.warn("Aviso posterior a la consulta", category)
                            else:
                                emitted.clear()
                                warnings.warn("Aviso posterior a la consulta", category)
                                self.assertEqual(bool(emitted), action == "always")
                    self.assertEqual(evaluar.snapshot(self.root), before)

    def test_json_no_oculta_excepcion_ast_y_restaura_filtros(self):
        before = evaluar.snapshot(self.root)
        out, err = io.StringIO(), io.StringIO()
        failure = RuntimeError("Fallo inesperado del analizador")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            filters = warnings.filters[:]
            # Inyección de un fallo inesperado en el analizador, atravesando la
            # interfaz pública: debe propagarse, sin fabricar una consulta válida.
            with patch("case_evidence.ast.parse", side_effect=failure), \
                    redirect_stdout(out), redirect_stderr(err):
                with self.assertRaises(RuntimeError) as raised:
                    inspect_run.main(["--run", str(self.general), "--format", "json"])
            self.assertIs(raised.exception, failure)
            self.assertEqual(warnings.filters, filters)
            with self.assertRaises(SyntaxWarning):
                warnings.warn("Aviso posterior al fallo", SyntaxWarning)
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))
        self.assertEqual(evaluar.snapshot(self.root), before)

    def assert_text_formats(self, code):
        default = self.query()
        explicit = self.query("--format", "text")
        self.assertEqual(default.returncode, code)
        self.assertEqual((explicit.returncode, explicit.stdout, explicit.stderr),
                         (default.returncode, default.stdout, default.stderr))
        if code == 0:
            self.assertEqual(default.stderr, "")
            self.assertIn("Consulta: completada (código 0)", default.stdout)
        return default

    def test_texto_conserva_equivalencia_heredada_booleano_numero(self):
        for code in (0, 1):
            with self.subTest(codigo=code):
                if code == 1:
                    self.review.update(
                        decision_controlador="cambios_solicitados", codigo_salida=1,
                        dictamen_modelo={"decision": "solicitar_cambios", "hallazgos": [
                            {"archivo": "solution.py", "linea": 1,
                             "explicacion": "Hallazgo sintético, no una revisión ejecutada."}]})
                    self.attempt["transiciones"][-1] = {
                        "etapa": "revision", "accion": "corregir", "motivo": "cambios_solicitados"}
                    self.attempt["transiciones"].append({
                        "etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"})
                    self.record.update(estado="intentos_agotados", codigo_salida=1,
                                       max_intentos=1, max_invocaciones=2)
                self.write_records()
                self.save(self.review_dir / "resultado.json", {**self.review, "codigo_salida": bool(code)})
                self.assert_text_formats(0)

    def test_texto_conserva_tratamiento_heredado_de_duracion_grande(self):
        self.record["duracion_segundos"] = 10**309
        self.write_records()
        completed = self.assert_text_formats(1)
        self.assertIn("Duración: no consta", completed.stdout)
        self.assertIn("Consulta: incompleta (código 1)", completed.stdout)
        self.assertIn("general: duración inválida", completed.stderr)


class TestInspectJsonHallazgos(comprobar_hallazgos.HallazgosTests):
    project = PROJECT

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci-inspect-hallazgos-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        super().setUp()


class TestInspectJsonAnidamiento(comprobar_anidamiento.AnidamientoTests):
    project = PROJECT

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci-inspect-anidamiento-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        super().setUp()


if __name__ == "__main__":
    unittest.main(verbosity=2)

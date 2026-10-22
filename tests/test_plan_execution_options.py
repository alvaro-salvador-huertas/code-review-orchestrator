"""Selección por ejecución: transmisión comprobada por una CLI sintética."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import plan_project as planner
import project_plan_continuation as continuity
import review_case
from repair_project import tree_state
import test_plan_project as initial
import test_plan_continuation as previous
import test_plan_decisions as decisions_tests


class ExecutionOptionsTests(unittest.TestCase):
    setUp = initial.PlanningTests.setUp
    configure = initial.PlanningTests.configure
    git = initial.PlanningTests.git
    calls_read = initial.PlanningTests.calls_read
    assert_failure = initial.PlanningTests.assert_failure
    answers = previous.ContinuationTests.answers
    decisions = decisions_tests.DecisionTests.decisions

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = planner.main(args, project_root=self.root)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def recorded(self):
        logs = list((self.root / "runs").glob("*_plan_project_*"))
        log = max(logs, key=lambda p: p.stat().st_mtime_ns)
        return log, json.loads((log / "resultado.json").read_bytes())

    def test_cli_transmite_modelo_esfuerzo_y_registra_solicitud_no_modelo_servido(self):
        self.configure(model="gpt-6-astra", reasoning_effort="medium")
        code, _, err = self.cli(["Petición sintética", "--model", "gpt-6-astra", "--reasoning-effort", "medium"])
        self.assertEqual(code, 0, err)
        log, result = self.recorded()
        self.assertEqual(result["opciones_solicitadas"], {"model": "gpt-6-astra", "reasoning_effort": "medium"})
        self.assertEqual(json.loads((log / "procedencia.json").read_bytes())["opciones_solicitadas"],
                         result["opciones_solicitadas"])
        args = self.calls_read()[-1]
        self.assertEqual(args[-5:], ["--model", "gpt-6-astra", "--config", 'model_reasoning_effort="medium"', "-"])
        process = json.loads((log / "planificador/resultado.json").read_bytes())
        self.assertEqual(process["comando"], [str(self.fake), *args])
        self.assertEqual(result["planificador"]["comando"], process["comando"])
        self.assertEqual(result["invocaciones"], {"planificador": 1})
        self.assertEqual(process["limite_segundos"], 300)
        self.assertTrue(all(result["integridad"].values()))
        self.assertFalse(result["aprobada"])
        self.assertNotIn("modelo_servido", result)
        self.assertEqual(len(self.calls_read()), 3)
        continuity.load_parent(log)

    def test_opciones_independientes_y_sin_opciones_conserva_argv(self):
        for options in ({}, {"model": "proveedor/modelo:version-1"}, {"reasoning_effort": "high"}):
            with self.subTest(options=options):
                self.configure(**options)
                result = planner.run_plan("Petición sintética", self.root, **options)
                self.assertEqual(result["codigo_salida"], 0, result)
                log = Path(result["registro"])
                args = self.calls_read()[-1]
                expected = ["exec", "--sandbox", "read-only", "--config", 'approval_policy="never"',
                            "--config", 'web_search="disabled"', "--config", "features.multi_agent=false",
                            "--cd", args[args.index("--cd") + 1], "--skip-git-repo-check", "--ephemeral", "--json",
                            "--output-schema", args[args.index("--output-schema") + 1],
                            "--output-last-message", args[args.index("--output-last-message") + 1]]
                if "model" in options:
                    expected += ["--model", options["model"]]
                if "reasoning_effort" in options:
                    expected += ["--config", 'model_reasoning_effort="high"']
                self.assertEqual(args, expected + ["-"])
                if not options:
                    self.assertNotIn("opciones_solicitadas", result)
                    self.assertNotIn("opciones_solicitadas", json.loads((log / "procedencia.json").read_bytes()))
                continuity.load_parent(log)

    def test_argumentos_invalidos_y_plantillas_rechazados_sin_consultar_cli(self):
        invalid = [["Petición", "--model", v] for v in ("", " ", "gpt\n6", "gpt\0six", "--flag", "gpt;echo", "a" * 201, "\ud800")]
        invalid += [["Petición", "--reasoning-effort", v] for v in ("", "Medium", "inventado", 'medium"', "high\n")]
        invalid += [["Petición", "--model"], ["Petición", "--reasoning-effort"]]
        invalid += [["--model", "gpt-6-astra"], ["--from-plan", "ausente", "--model", "gpt-6-astra"]]
        for template in ("--answers-template", "--decisions-template"):
            for option, value in (("--model", "gpt-6-astra"), ("--reasoning-effort", "medium")):
                invalid.append(["--from-plan", "ausente", template, str(self.tmp / "plantilla"), option, value])
        before = tree_state(self.root)
        with patch.object(planner, "invoke_read_only") as invoke, patch.object(planner, "load_parent") as load:
            for args in invalid:
                with self.subTest(args=repr(args)):
                    self.assertEqual(self.cli(args)[0], 2)
            invoke.assert_not_called()
            load.assert_not_called()
        self.assertEqual(self.calls_read(), [])
        self.assertEqual(tree_state(self.root), before)
        self.assertFalse((self.tmp / "plantilla").exists())

    def test_api_invalida_rechaza_antes_de_cli_y_reserva(self):
        for options in ({"model": True}, {"model": ""}, {"model": "--flag"},
                        {"reasoning_effort": []}, {"reasoning_effort": "inventado"}):
            with self.subTest(options=options), patch.object(planner, "invoke_read_only") as invoke:
                result = planner.run_plan("Petición sintética", self.root, **options)
                self.assert_failure(result, "error_controlador", 0)
                self.assertIsNone(result["registro"])
                invoke.assert_not_called()
            with patch.object(review_case, "run_process") as run:
                with self.assertRaises(ValueError):
                    review_case.invoke_reviewer(self.tmp, self.tmp / "out", b"{}", self.tmp, **options)
                run.assert_not_called()
        self.assertEqual(self.calls_read(), [])

    def test_plantilla_con_ruta_vacia_no_se_convierte_en_planificacion(self):
        before = tree_state(self.root)
        result = {"codigo_salida": 0, "estado": "borrador", "registro": None, "fallo": None}
        with patch.object(planner, "run_plan", return_value=result) as run, \
                patch.object(planner, "export_template") as export:
            for flag in ("--answers-template", "--decisions-template"):
                for options in ([], ["--model", "gpt-6-astra"], ["--reasoning-effort", "medium"]):
                    with self.subTest(flag=flag, options=options):
                        self.assertEqual(self.cli(["Petición", flag, "", *options])[0], 2)
            run.assert_not_called()
            export.assert_not_called()
        self.assertEqual(self.calls_read(), [])
        self.assertEqual(tree_state(self.root), before)

    def test_cli_sin_model_no_reserva_con_model_y_sigue_compatible_sin_el(self):
        help_without_model = initial.HELP.replace("--model ", "")
        self.configure(cli_help=help_without_model, model="gpt-6-astra")
        result = planner.run_plan("Petición", self.root, model="gpt-6-astra")
        self.assert_failure(result, "cli_incompatible", 0)
        self.assertEqual(self.calls_read(), [["--version"], ["exec", "--help"]])
        self.configure(cli_help=help_without_model)
        self.assertEqual(planner.run_plan("Petición", self.root)["codigo_salida"], 0)

    def test_continuacion_combinada_y_opciones_no_se_heredan(self):
        self.configure(plan=initial.ambiguous())
        origin = Path(planner.run_plan("Petición", self.root)["registro"])
        answers = self.answers(origin, "Respuesta sintética")
        decisions = self.decisions(origin, ("aceptar", "", ""))
        before = tree_state(origin)
        calls = len(self.calls_read())
        self.configure(model="gpt-6-astra", reasoning_effort="medium")
        args = ["--from-plan", str(origin), "--answers", str(answers), "--decisions", str(decisions),
                "--model", "gpt-6-astra", "--reasoning-effort", "medium"]
        self.assertEqual(self.cli(args)[0], 0)
        child, result = self.recorded()
        self.assertEqual(len(self.calls_read()) - calls, 3)
        loaded = continuity.load_parent(child)
        self.assertEqual(len(loaded.answers), 1)
        self.assertEqual(len(loaded.decisions), 1)
        self.assertEqual(tree_state(origin), before)
        next_answers = self.answers(child, "Otra respuesta sintética")
        self.configure()
        next_result = planner.run_plan(None, self.root, from_plan=child, answers=next_answers)
        self.assertEqual(next_result["codigo_salida"], 0, next_result)
        self.assertNotIn("opciones_solicitadas", next_result)
        self.assertNotIn("--model", self.calls_read()[-1])
        continuity.load_parent(next_result["registro"])

    def test_solo_decisiones_y_exportaciones_siguen_sin_invocacion(self):
        self.configure(plan=decisions_tests.assumed())
        origin = Path(planner.run_plan("Petición", self.root)["registro"])
        calls = self.calls_read()
        before = tree_state(origin)
        for flag in ("--answers-template", "--decisions-template"):
            with patch.object(planner, "invoke_read_only") as invoke:
                self.assertEqual(self.cli(["--from-plan", str(origin), flag, str(self.tmp / flag[2:])])[0], 0)
                invoke.assert_not_called()
        self.assertEqual(self.calls_read(), calls)
        self.assertEqual(tree_state(origin), before)
        decisions = self.decisions(origin, ("aceptar", "", ""))
        self.configure(model="gpt-6-astra", reasoning_effort="medium")
        self.assertEqual(self.cli(["--from-plan", str(origin), "--decisions", str(decisions),
                                  "--model", "gpt-6-astra", "--reasoning-effort", "medium"])[0], 0)
        self.assertEqual(tree_state(origin), before)

    def test_fixture_detecta_opciones_incorrectas_antes_de_responder(self):
        self.configure(model="otro-modelo")
        result = planner.run_plan("Petición", self.root, model="gpt-6-astra")
        self.assert_failure(result, "fallo_proceso", 1)
        log = Path(result["registro"])
        self.assertEqual((log / "planificador/respuesta_original.txt").read_bytes(), b"")
        self.assertEqual((log / "planificador/eventos.jsonl").read_bytes(), b"")
        self.assertEqual(len(self.calls_read()), 3)


if __name__ == "__main__":
    unittest.main()

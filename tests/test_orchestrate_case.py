from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import orchestrate_case
import repair_case
import review_case
from case_evidence import classify_test_report, digest, snapshot_tree


PROJECT = Path(__file__).resolve().parents[1]
ORIGINAL = (PROJECT / "benchmark/case_02/solution.py").read_text()
GOOD = ORIGINAL.replace('    return "completada"',
                        '    if respuesta is None or respuesta == "" or respuesta.isspace():\n'
                        '        return "respuesta_vacia"\n    return "completada"')
PARTIAL = ORIGINAL + "# candidato del primer intento\n"
APPROVAL = {"decision": "aprobar", "resumen": "Aprobación simulada.", "hallazgos": []}
CHANGES = {"decision": "solicitar_cambios", "resumen": "Observación simulada.", "hallazgos": [
    {"archivo": "candidato.py", "linea": 6, "explicacion": "Defecto simulado, contrastar con el contrato.",
     "ejemplo": "Ejemplo simulado para probar el envío de feedback."}]}


class TestOrchestrateCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-orchestration-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.project = self.temporary / "proyecto con espacios"
        self.project.mkdir()
        for folder in ("benchmark", "tasks", "prompts"):
            shutil.copytree(PROJECT / folder, self.project / folder)
        self.originals = repair_case.inventory(self.project)
        self.historical = self.project / "runs/zz_registro_ajeno"
        self.historical.mkdir(parents=True)
        (self.historical / "candidato.py").write_text("NO USAR EL REGISTRO MÁS RECIENTE\n")
        self.history = snapshot_tree(self.historical)
        self.fake = self.temporary / "codex simulado"
        self.calls = self.temporary / "calls.jsonl"

    def configure(self, developers, reviewers):
        self.calls.unlink(missing_ok=True)
        self.fake.write_text(
            f"#!{sys.executable}\n"
            "import json, sys, time\nfrom pathlib import Path\n"
            f"developers={developers!r}\nreviewers={reviewers!r}\n"
            f"calls=Path({str(self.calls)!r})\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('codex-cli simulado'); sys.exit(0)\n"
            "if sys.argv[1:] == ['exec', '--help']:\n"
            "    print('--config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema'); sys.exit(0)\n"
            "role='reviewer' if sys.argv[sys.argv.index('--sandbox')+1]=='read-only' else 'developer'\n"
            "previous=[json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []\n"
            "index=sum(item['role']==role for item in previous)\n"
            "action=(reviewers if role=='reviewer' else developers)[index]\n"
            "prompt=sys.stdin.read()\n"
            "seen={p.name:p.read_text() for p in Path.cwd().iterdir()}\n"
            "with calls.open('a') as log:\n"
            "    log.write(json.dumps({'role':role, 'prompt':prompt, 'seen':seen, 'args':sys.argv[1:]})+'\\n')\n"
            "print('{\"type\":\"turn.completed\"}', flush=True)\n"
            "print('diagnóstico simulado',file=sys.stderr,flush=True)\n"
            "mode=action.get('mode','ok')\n"
            "final=Path(sys.argv[sys.argv.index('--output-last-message')+1])\n"
            "if role=='developer':\n"
            "    Path('solution.py').write_text(action.get('candidate',seen['solution.py']))\n"
            "    final.write_text('EXPLICACION PRIVADA: todo está arreglado')\n"
            "    if mode=='tests_tamper': Path('test_solution.py').write_text('# alterado')\n"
            "else:\n"
            "    final.write_text(action['response'])\n"
            "    if mode=='material_tamper': Path('candidato.py').write_text('# alterado')\n"
            f"if mode=='original_tamper': Path({str(self.project / 'benchmark/case_02/solution.py')!r}).write_text('# alterado')\n"
            "if mode=='timeout': time.sleep(60)\n"
            "sys.exit(9 if mode=='nonzero' else 0)\n", encoding="utf-8")
        self.fake.chmod(0o700)

    def execute(self, developers=None, reviewers=None, attempts=2):
        self.configure(developers if developers is not None else [{"candidate": GOOD}],
                       reviewers if reviewers is not None else [{"response": json.dumps(APPROVAL)}])
        output = io.StringIO()
        with patch.object(repair_case, "CODEX_EXECUTABLE", str(self.fake)), \
                patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)), \
                redirect_stdout(output), redirect_stderr(output):
            result = orchestrate_case.run_orchestration("case_02", self.project, attempts)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(snapshot_tree(self.historical), self.history)
        if result["registro"] and (Path(result["registro"]) / "resultado.json").exists():
            saved = json.loads((Path(result["registro"]) / "resultado.json").read_text())
            if result["estado"] != "fallo_controlador":
                self.assertEqual(saved, result)
        return result

    def observed_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def assert_preserved(self):
        self.assertEqual(repair_case.inventory(self.project), self.originals)

    def test_aprobacion_inicial_no_consume_segundo_intento(self):
        result = self.execute()
        self.assertEqual((result["codigo_salida"], result["estado"]), (0, "aprobada"))
        self.assertEqual(len(result["intentos"]), 1)
        self.assertEqual(result["invocaciones"], {"desarrollador": 1, "revisor": 1, "total": 2})
        self.assertTrue(all(result["integridad"].values()))
        developer, reviewer = self.observed_calls()
        self.assertEqual(developer["seen"]["solution.py"], ORIGINAL)
        self.assertNotIn("EXPLICACION PRIVADA", str(reviewer))
        for call in (developer, reviewer):
            args = call["args"]
            for flag in ('approval_policy="never"', 'web_search="disabled"', 'features.multi_agent=false',
                         '--ephemeral', '--json'):
                self.assertIn(flag, args)
            self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)
            self.assertNotIn('--add-dir', args)
        entry = result["intentos"][0]
        self.assertEqual(entry["reparacion"]["agente"]["limite_segundos"], 180)
        self.assertEqual(entry["revision"]["revisor"]["limite_segundos"], 180)
        self.assertEqual(entry["reparacion"]["pruebas_posteriores"]["limite_segundos"], 30)
        self.assert_preserved()

    def test_fallos_de_asercion_y_correccion_con_partida_y_feedback_exactos(self):
        result = self.execute([{"candidate": PARTIAL}, {"candidate": GOOD}])
        self.assertEqual(result["codigo_salida"], 0)
        self.assertEqual(result["invocaciones"]["total"], 3)
        first, second = result["intentos"]
        self.assertIsNone(first["revision"])
        self.assertEqual(first["transiciones"][0]["motivo"], "fallos_asercion")
        self.check_continuity(result, PARTIAL)
        first_run = Path(first["reparacion"]["registro"])
        feedback = json.loads((Path(second["reparacion"]["registro"]) / "feedback.json").read_text())
        self.assertEqual(feedback, {"tipo": "fallos_pruebas",
                                   "resultado": first["reparacion"]["pruebas_posteriores"],
                                   "stdout": (first_run / "posterior/stdout.txt").read_text(),
                                   "stderr": (first_run / "posterior/stderr.txt").read_text()})
        self.assertIn(json.dumps(feedback, ensure_ascii=False, indent=2), self.observed_calls()[1]["prompt"])

    def test_solicitud_de_cambios_y_correccion_con_hallazgos_exactos(self):
        first_candidate = GOOD + "# primera propuesta\n"
        result = self.execute([{"candidate": first_candidate}, {"candidate": GOOD}],
                              [{"response": json.dumps(CHANGES)}, {"response": json.dumps(APPROVAL)}])
        self.assertEqual(result["codigo_salida"], 0)
        self.assertEqual(result["invocaciones"]["total"], 4)
        self.check_continuity(result, first_candidate)
        feedback = json.loads((Path(result["intentos"][1]["reparacion"]["registro"]) / "feedback.json").read_text())
        self.assertEqual(feedback, {"tipo": "solicitar_cambios", "dictamen": CHANGES})
        prompt = self.observed_calls()[2]["prompt"]
        self.assertIn(json.dumps(feedback, ensure_ascii=False, indent=2), prompt)
        self.assertIn("no autorizan a cambiar sus requisitos", prompt)

    def check_continuity(self, result, candidate):
        first, second = (Path(e["reparacion"]["registro"]) for e in result["intentos"])
        self.assertEqual((second / "partida.py").read_bytes(), (first / "candidato.py").read_bytes())
        self.assertEqual((second / "inicial/workspace/solution.py").read_text(), candidate)
        developers = [call for call in self.observed_calls() if call["role"] == "developer"]
        self.assertEqual(developers[1]["seen"]["solution.py"], candidate)
        self.assertEqual((second / "referencia/solution.py").read_text(), ORIGINAL)
        self.assertEqual((second / "referencia/contrato.md").read_bytes(), (first / "referencia/contrato.md").read_bytes())
        self.assertEqual((second / "referencia/test_solution.py").read_bytes(), (first / "referencia/test_solution.py").read_bytes())
        for path in (first, second):
            for name in ("partida.diff", "correccion.diff", "candidato.diff"):
                self.assertTrue((path / name).exists())
        self.assertEqual(result["intentos"][1]["partida_sha256"], digest(candidate.encode()))
        review_case.validate_repair(second, self.project)
        self.assert_preserved()

    def test_agotamiento_por_pruebas_con_uno_o_dos_intentos(self):
        for limit in (1, 2):
            with self.subTest(limit=limit):
                result = self.execute([{"candidate": PARTIAL}] * limit, [], limit)
                self.assertEqual((result["codigo_salida"], result["estado"]), (1, "intentos_agotados"))
                self.assertFalse(result["aprobada"])
                self.assertEqual(len(result["intentos"]), limit)
                self.assertEqual(result["invocaciones"]["total"], limit)

    def test_agotamiento_por_dictamenes_no_excede_cuatro_invocaciones(self):
        for limit in (1, 2):
            with self.subTest(limit=limit):
                result = self.execute([{"candidate": GOOD}] * limit,
                                      [{"response": json.dumps(CHANGES)}] * limit, limit)
                self.assertEqual(result["codigo_salida"], 1)
                self.assertEqual(result["invocaciones"]["total"], limit * 2)
                self.assertEqual(len(self.observed_calls()), limit * 2)

    def test_error_tecnico_del_desarrollador_detiene_sin_evaluar_ni_revisar(self):
        result = self.execute([{"candidate": GOOD, "mode": "nonzero"}], [])
        self.assertEqual(result["codigo_salida"], 3)
        repair = result["intentos"][0]["reparacion"]
        self.assertEqual(repair["pruebas_posteriores"]["estado"], "no_ejecutadas")
        self.assertEqual(result["invocaciones"]["total"], 1)
        self.assertTrue((Path(repair["registro"]) / "agente/errores.txt").read_bytes())

    def test_timeout_del_desarrollador_no_reintenta(self):
        with patch.object(repair_case, "AGENT_TIMEOUT_SECONDS", 0.3):
            result = self.execute([{"candidate": GOOD, "mode": "timeout"}], [])
        self.assertEqual(result["codigo_salida"], 4)
        self.assertEqual(len(self.observed_calls()), 1)

    def test_timeout_de_evaluacion_inicial_no_invoca_desarrollador(self):
        (self.project / "benchmark/case_02/solution.py").write_text("import time\ntime.sleep(60)\n")
        with patch.object(repair_case, "TIMEOUT_SECONDS", 0.3):
            result = self.execute([], [])
        self.assertEqual(result["codigo_salida"], 4)
        self.assertEqual(self.observed_calls(), [])

    def test_timeout_de_evaluacion_posterior_no_reintenta(self):
        with patch.object(repair_case, "TIMEOUT_SECONDS", 0.3):
            result = self.execute([{"candidate": "import time\ntime.sleep(60)\n"}], [])
        self.assertEqual(result["codigo_salida"], 4)
        self.assertEqual(len(self.observed_calls()), 1)

    def test_salida_uno_sin_aserciones_y_cero_sin_pruebas_no_permiten_corregir(self):
        for candidate in ("raise RuntimeError('fallo al importar')\n", "import sys\nsys.exit(1)\n",
                          "import sys\nsys.exit(0)\n", "sintaxis inválida ???\n"):
            with self.subTest(candidate=candidate):
                result = self.execute([{"candidate": candidate}], [])
                self.assertIn(result["codigo_salida"], (7, 8))
                self.assertEqual(len(self.observed_calls()), 1)
                self.assertFalse(result["aprobada"])

    def test_error_en_prueba_no_es_fallo_de_asercion(self):
        candidate = "def clasificar_ejecucion(*args, **kwargs):\n    raise RuntimeError('error')\n"
        result = self.execute([{"candidate": candidate}], [])
        self.assertEqual((result["codigo_salida"], result["estado"]), (8, "error_pruebas"))
        self.assertEqual(len(self.observed_calls()), 1)

    def test_fallos_del_revisor_detienen_aunque_quede_presupuesto(self):
        for mode, raw, code in (("ok", "no JSON", 5), ("nonzero", json.dumps(APPROVAL), 3),
                                ("timeout", json.dumps(APPROVAL), 4),
                                ("material_tamper", json.dumps(APPROVAL), 6)):
            with self.subTest(mode=mode):
                with patch.object(review_case, "AGENT_TIMEOUT_SECONDS", 0.3):
                    result = self.execute(reviewers=[{"mode": mode, "response": raw}])
                self.assertEqual(result["codigo_salida"], code)
                self.assertFalse(result["aprobada"])
                self.assertEqual(len(self.observed_calls()), 2)

    def test_alteracion_de_pruebas_del_agente_no_lanza_evaluacion(self):
        result = self.execute([{"candidate": GOOD, "mode": "tests_tamper"}], [])
        self.assertEqual(result["codigo_salida"], 6)
        self.assertEqual(result["intentos"][0]["reparacion"]["pruebas_posteriores"]["estado"], "no_ejecutadas")
        self.assertEqual(len(self.observed_calls()), 1)
        self.assert_preserved()

    def test_alteracion_de_originales_no_continua(self):
        result = self.execute([{"candidate": GOOD, "mode": "original_tamper"}], [])
        self.assertEqual(result["codigo_salida"], 6)
        self.assertFalse(result["integridad"]["originales_intactos"])
        self.assertEqual(len(self.observed_calls()), 1)

    def test_evidencia_incompleta_no_invoca_revisor(self):
        original = orchestrate_case.run_repair

        def remove_evidence(*args, **kwargs):
            result = original(*args, **kwargs)
            (Path(result["registro"]) / "posterior/workspace/solution.py").unlink()
            return result

        with patch.object(orchestrate_case, "run_repair", side_effect=remove_evidence):
            result = self.execute()
        self.assertEqual(result["codigo_salida"], 7)
        self.assertEqual(len(self.observed_calls()), 1)

    def test_continuidad_alterada_no_es_aceptable_para_revisar(self):
        result = self.execute([{"candidate": PARTIAL}, {"candidate": GOOD}])
        second = Path(result["intentos"][1]["reparacion"]["registro"])
        for name in ("partida.py", "partida.diff", "correccion.diff", "feedback.json"):
            with self.subTest(name=name):
                data = (second / name).read_bytes()
                (second / name).write_bytes(data + b"alterado")
                try:
                    with self.assertRaises(ValueError):
                        review_case.validate_repair(second, self.project)
                finally:
                    (second / name).write_bytes(data)
        previous = Path(result["intentos"][0]["reparacion"]["registro"])
        (previous / "agente/respuesta_final.txt").write_text("alterado")
        with self.assertRaises(ValueError):
            review_case.validate_repair(second, self.project)

    def test_fallo_al_guardar_registro_general_detiene_la_siguiente_etapa(self):
        original = orchestrate_case.write_json

        def fail(path, value):
            if value.get("intentos") and value["intentos"][0]["reparacion"] is not None:
                raise OSError("fallo al guardar resumen general")
            original(path, value)

        with patch.object(orchestrate_case, "write_json", side_effect=fail):
            result = self.execute()
        self.assertEqual(result["codigo_salida"], 8)
        self.assertEqual(len(self.observed_calls()), 1)
        self.assertFalse(result["aprobada"])

    def test_fallo_de_registro_del_proceso_conserva_invocaciones_realizadas(self):
        original = repair_case.write_json
        for role, calls in (("agente", 1), ("revisor", 2)):
            with self.subTest(role=role):
                def fail(path, value):
                    if path.parent.name == role and path.name == "resultado.json":
                        raise OSError("fallo al guardar proceso")
                    original(path, value)

                with patch.object(repair_case, "write_json", side_effect=fail):
                    result = self.execute()
                self.assertEqual(result["codigo_salida"], 8)
                self.assertEqual(result["invocaciones"]["total"], calls)
                self.assertEqual(len(self.observed_calls()), calls)
                self.assertFalse(result["aprobada"])

    def test_codex_ausente_no_consume_invocaciones_ni_reintenta(self):
        configure = self.configure

        def absent(*args):
            configure(*args)
            self.fake.unlink()

        with patch.object(self, "configure", side_effect=absent):
            result = self.execute([], [])
        self.assertEqual(result["codigo_salida"], 3)
        self.assertEqual(result["invocaciones"]["total"], 0)
        self.assertEqual(len(result["intentos"]), 1)
        self.assertEqual(self.observed_calls(), [])

    def test_cli_presupuesto_predeterminado_y_argumentos_invalidos(self):
        for name in ("orchestrate_case.py", "repair_case.py", "review_case.py", "run_case.py", "case_evidence.py"):
            shutil.copy2(PROJECT / name, self.project / name)
        self.configure([{"candidate": GOOD}], [{"response": json.dumps(APPROVAL)}])
        bin_dir = self.temporary / "bin"
        bin_dir.mkdir()
        shutil.copy2(self.fake, bin_dir / "codex")
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        command = [sys.executable, "-B", str(self.project / "orchestrate_case.py")]
        completed = subprocess.run(command + ["case_02"], cwd=self.temporary, env=env,
                                   capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(b"Intentos: 1/2", completed.stdout)
        self.assertIn(b"Invocaciones: 2/4", completed.stdout)
        self.assertFalse((self.temporary / "runs").exists())
        for args in ([], ["case_01"], ["case_02", "--max-attempts", "0"],
                     ["case_02", "--max-attempts", "3"], ["case_02", "--max-attempts", "x"]):
            rejected = subprocess.run(command + args, cwd=self.temporary, env=env,
                                      capture_output=True, timeout=10)
            self.assertEqual(rejected.returncode, 2)
        self.assertEqual(len(self.observed_calls()), 2)

    def test_informe_failed_sin_diagnostico_no_acredita_aserciones(self):
        reference = b"import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
        report = "test_a (test_solution.T.test_a) ... FAIL\n\nRan 1 test in 0.001s\n\nFAILED (failures=1)\n"
        with self.assertRaises(ValueError):
            classify_test_report(reference, report, 1)


if __name__ == "__main__":
    unittest.main()

from contextlib import redirect_stderr, redirect_stdout
import difflib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import review_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPROVAL = {"decision": "aprobar", "resumen": "Sin defectos en esta simulación.", "hallazgos": []}
FINDING = {"archivo": "candidato.py", "linea": 6,
           "explicacion": "Incumplimiento simulado para probar el controlador.",
           "ejemplo": "Entrada (0, None): se espera respuesta_vacia; se deduce completada."}
HELP = "--config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema"


class TestReviewCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-review-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.project = self.temporary / "proyecto con espacios"
        self.project.mkdir()
        for folder in ("benchmark", "tasks", "prompts"):
            shutil.copytree(PROJECT_ROOT / folder, self.project / folder)
        self.source = self.project / "runs" / "reparacion aceptada"
        self.source.mkdir(parents=True)
        self.build_record()
        self.original_source = review_case.snapshot_tree(self.source)
        self.originals = review_case.inventory(self.project)
        self.fake = self.temporary / "codex simulado"
        self.calls = self.temporary / "llamadas.jsonl"
        self.received = self.temporary / "entrada_recibida.txt"
        self.seen = self.temporary / "materiales_recibidos.json"
        self.configure_fake()

    def save(self, name, value):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            review_case.write_json(path, value)

    def build_record(self, reference_tests=None):
        """Fixture explícita: no llama al desarrollador ni ejecuta el caso."""
        if reference_tests is not None:
            (self.project / "benchmark/case_02/test_solution.py").write_bytes(reference_tests)
        initial = (self.project / "benchmark/case_02/solution.py").read_bytes()
        self.candidate = initial.replace(
            b'    return "completada"',
            b'    if respuesta is None or not respuesta.strip():\n'
            b'        return "respuesta_vacia"\n    return "completada"',
        )
        tests = (self.project / "benchmark/case_02/test_solution.py").read_bytes()
        contract = (self.project / "tasks/002-classify-run.md").read_bytes()
        references = {"solution.py": initial, "test_solution.py": tests, "contrato.md": contract}
        for name, content in references.items():
            self.save("referencia/" + name, content)
        self.save("agente/respuesta_final.txt", b"EXPLICACION PRIVADA DEL DESARROLLADOR")
        self.save("agente/test_solution_despues.py", tests)
        self.update_candidate(self.candidate)
        agent = {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1}
        self.save("agente/resultado.json", agent)
        test_names = sorted(re.findall(r"    def (test_\w+)\(self\):", tests.decode()))
        results = {}
        for phase, code, implementation in (("inicial", 1, initial), ("posterior", 0, self.candidate)):
            workspace = self.source / phase / "workspace"
            phase_result = {
                "estado": "finalizada", "codigo_salida": code, "pruebas_intactas": True,
                "implementacion_intacta": True, "limite_segundos": 30,
                "comando": [sys.executable, "-B", "-m", "unittest", "discover", "-s",
                            str(workspace), "-p", "test_solution.py", "-v"],
                "directorio_trabajo": str(workspace),
            }
            results[phase] = phase_result
            self.save(phase + "/resultado.json", phase_result)
            self.save(phase + "/workspace/solution.py", implementation)
            self.save(phase + "/workspace/test_solution.py", tests)
            self.save(phase + "/stdout.txt", b"")
            rows = [f"{name} (test_solution.TestClasificarEjecucion.{name}) ... "
                    + ("FAIL" if code and i < 3 else "ok") for i, name in enumerate(test_names)]
            noun = "test" if len(test_names) == 1 else "tests"
            report = "\n".join(rows) + f"\n\nRan {len(test_names)} {noun} in 0.001s\n\n"
            report += f"FAILED (failures={min(3, len(test_names))})\n" if code else "OK\n"
            self.save(phase + "/stderr.txt", report.encode())
        self.summary = {
            "caso": "case_02", "aceptada": True, "estado": "supera_las_pruebas_disponibles",
            "codigo_salida": 0, "candidato_disponible": True, "errores_controlador": [],
            "integridad": dict.fromkeys(review_case.INTEGRITY_KEYS, True), "agente": agent,
            "pruebas_iniciales": results["inicial"], "pruebas_posteriores": results["posterior"],
            "sha256": {
                "originales": review_case.inventory(self.project),
                "referencia": {key: review_case.digest(value) for key, value in references.items()},
                "candidato": review_case.digest(self.candidate), "pruebas_agente": review_case.digest(tests),
            },
        }
        self.save("resultado.json", self.summary)

    def update_candidate(self, candidate):
        initial = (self.source / "referencia/solution.py").read_bytes()
        self.save("candidato.py", candidate)
        self.save("posterior/workspace/solution.py", candidate)
        self.save("candidato.diff", b"".join(difflib.diff_bytes(
            difflib.unified_diff, initial.splitlines(keepends=True), candidate.splitlines(keepends=True),
            fromfile=b"inicial/solution.py", tofile=b"candidato/solution.py")))

    def configure_fake(self, mode="approval", response=None):
        response = json.dumps(APPROVAL) if response is None else response
        self.fake.write_text(
            f"#!{sys.executable}\n"
            "import json, sys, time\nfrom pathlib import Path\n"
            f"mode = {mode!r}\n"
            f"with Path({str(self.calls)!r}).open('a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('codex-cli 0.162.1', flush=True)\n"
            "    if mode == 'version_timeout': time.sleep(60)\n"
            "    sys.exit(0)\n"
            "if sys.argv[1:] == ['exec', '--help']:\n"
            f"    print('incompatible' if mode == 'incompatible' else {HELP!r})\n"
            "    if mode == 'vanish': Path(sys.argv[0]).unlink()\n"
            "    sys.exit(0)\n"
            "assert sys.argv[1] == 'exec' and sys.argv[-1] == '-'\n"
            "assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'\n"
            "assert '--output-schema' in sys.argv\n"
            f"Path({str(self.received)!r}).write_bytes(sys.stdin.buffer.read())\n"
            f"Path({str(self.seen)!r}).write_text(json.dumps(\n"
            "    {p.name: p.read_text() for p in Path.cwd().iterdir()}))\n"
            "print('{\"type\":\"turn.completed\"}', flush=True)\n"
            "print('diagnóstico simulado', file=sys.stderr, flush=True)\n"
            "final = Path(sys.argv[sys.argv.index('--output-last-message') + 1])\n"
            f"if mode != 'missing_response': final.write_text({response!r}, encoding='utf-8')\n"
            "if mode == 'material_tamper': Path('candidato.py').write_text('# alterado')\n"
            "if mode == 'material_deleted': Path('contrato.md').unlink()\n"
            "if mode == 'material_added': Path('extra.txt').write_text('extra')\n"
            "if mode == 'material_linked':\n"
            "    Path('candidato.py').unlink()\n"
            "    Path('candidato.py').symlink_to('original.py')\n"
            f"if mode == 'source_tamper': Path({str(self.source / 'candidato.py')!r}).write_text('# alterado')\n"
            "if mode == 'timeout': time.sleep(60)\n"
            "sys.exit(9 if mode == 'nonzero' else 0)\n", encoding="utf-8",
        )
        self.fake.chmod(0o700)

    def execute(self):
        before = set((self.project / "runs").iterdir())
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = review_case.review_case(self.source, self.project)
        added = set((self.project / "runs").iterdir()) - before
        self.assertLessEqual(len(added), 1)
        directory = next(iter(added)) if added else None
        result_path = directory / "resultado.json" if directory else None
        result = json.loads(result_path.read_text()) if result_path and result_path.exists() else None
        return code, directory, result, stdout.getvalue(), stderr.getvalue()

    def agent_calls(self):
        if not self.calls.exists():
            return []
        return [args for args in map(json.loads, self.calls.read_text().splitlines())
                if args[0] == "exec" and "--help" not in args]

    def test_aprobacion_con_evidencia_registros_y_sesion_nueva(self):
        code, directory, result, output, errors = self.execute()
        self.assertEqual((code, errors), (0, ""))
        self.assertTrue(result["aprobada"])
        self.assertEqual(result["decision_controlador"], "aprobada")
        self.assertEqual(result["dictamen_modelo"], APPROVAL)
        self.assertTrue(result["evidencia_previa_valida"])
        self.assertTrue(all(result["integridad"].values()))
        self.assertEqual(result["revisor"]["invocaciones"], 1)
        self.assertEqual(result["revisor"]["limite_segundos"], 180)
        self.assertGreater(result["duracion_segundos"], 0)
        self.assertIn("aprobada", output)
        self.assertEqual(review_case.snapshot_tree(self.source), self.original_source)
        self.assertEqual(review_case.inventory(self.project), self.originals)
        self.assertEqual(json.loads((directory / "dictamen_validado.json").read_text()), APPROVAL)
        origin = json.loads((directory / "origen.json").read_text())
        self.assertEqual(origin["registro_reparacion"], str(self.source))
        self.assertEqual(origin["registro_sha256"], self.original_source)
        self.assertEqual(origin["materiales_sha256"], result["materiales_sha256"])
        log = directory / "revisor"
        self.assertEqual((log / "entrada.txt").read_bytes(), self.received.read_bytes())
        self.assertEqual((log / "entrada.txt").read_bytes(), (self.project / "prompts/reviewer.md").read_bytes())
        self.assertIn("turn.completed", (log / "eventos.jsonl").read_text())
        self.assertIn("diagnóstico", (log / "stderr.txt").read_text())
        self.assertEqual((log / "codex_version.txt").read_text().strip(), "codex-cli 0.162.1")
        self.assertEqual(json.loads((log / "resultado.json").read_text()), result["revisor"])
        self.assertEqual(json.loads((log / "respuesta_original.txt").read_text()), APPROVAL)
        seen = json.loads(self.seen.read_text())
        self.assertEqual(set(seen), set(review_case.MATERIALS) | {"respuesta.schema.json"})
        self.assertNotIn("EXPLICACION PRIVADA", " ".join(seen.values()) + self.received.read_text())
        self.assertFalse(Path(result["revisor"]["directorio_trabajo"]).exists())
        self.assertNotIn(self.project, Path(result["revisor"]["directorio_trabajo"]).parents)
        args, = self.agent_calls()
        for option in ('approval_policy="never"', 'web_search="disabled"', 'features.multi_agent=false',
                       "--ephemeral", "--json", "--output-schema"):
            self.assertIn(option, args)
        for option in ("resume", "fork", "--add-dir", "--dangerously-bypass-approvals-and-sandbox"):
            self.assertNotIn(option, args)

    def test_cambios_solicitados_con_hallazgo_estructurado(self):
        verdict = {"decision": "solicitar_cambios", "resumen": "Defecto simulado.", "hallazgos": [FINDING]}
        self.configure_fake(response=json.dumps(verdict))
        code, _, result, _, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertFalse(result["aprobada"])
        self.assertEqual(result["decision_controlador"], "cambios_solicitados")
        self.assertEqual(result["dictamen_modelo"], verdict)

    def test_respuestas_invalidas_no_se_aceptan(self):
        invalid = ["", "no es JSON", "```json\n" + json.dumps(APPROVAL) + "\n```", "null", "[]",
                   '{"decision":"aprobar","decision":"aprobar","resumen":"bien","hallazgos":[]}',
                   '{"decision":"aprobar","resumen":NaN,"hallazgos":[]}']
        invalid += [json.dumps(value) for value in (
            {**APPROVAL, "resumen": "  "}, {**APPROVAL, "decision": "quizás"},
            {**APPROVAL, "hallazgos": {}}, {**APPROVAL, "extra": True},
            {**APPROVAL, "decision": "solicitar_cambios"}, {**APPROVAL, "hallazgos": [FINDING]},
            {"decision": "aprobar", "resumen": "sin hallazgos"},
        )]
        for bad_finding in ({**FINDING, "linea": True}, {**FINDING, "linea": 0},
                            {**FINDING, "linea": 999}, {**FINDING, "linea": "6"},
                            {**FINDING, "archivo": "../solution.py"}, {**FINDING, "ejemplo": " "},
                            {**FINDING, "explicacion": None}, {"archivo": "candidato.py"}):
            invalid.append(json.dumps({"decision": "solicitar_cambios", "resumen": "defecto",
                                       "hallazgos": [bad_finding]}))
        for raw in invalid:
            with self.subTest(raw=raw):
                self.configure_fake(response=raw)
                code, directory, result, _, _ = self.execute()
                self.assertEqual(code, 5)
                self.assertFalse(result["aprobada"])
                self.assertIsNone(result["dictamen_modelo"])
                self.assertTrue(result["error_respuesta"])
                self.assertEqual((directory / "revisor/respuesta_original.txt").read_text(), raw)
                self.assertFalse((directory / "dictamen_validado.json").exists())

    def test_respuesta_ausente_es_invalida(self):
        self.configure_fake("missing_response")
        code, _, result, _, _ = self.execute()
        self.assertEqual(code, 5)
        self.assertFalse(result["revisor"]["respuesta_disponible"])

    def test_salida_no_cero_preserva_dictamen_sin_aprobar(self):
        self.configure_fake("nonzero")
        code, directory, result, _, _ = self.execute()
        self.assertEqual(code, 3)
        self.assertEqual(result["revisor"]["codigo_salida"], 9)
        self.assertEqual(result["dictamen_modelo"], APPROVAL)
        self.assertFalse(result["aprobada"])
        self.assertTrue((directory / "dictamen_validado.json").exists())
        self.assertEqual(len(self.agent_calls()), 1)

    def test_timeout_preserva_respuesta_parcial_sin_aprobar_ni_reintentar(self):
        self.configure_fake("timeout")
        with patch.object(review_case, "AGENT_TIMEOUT_SECONDS", 0.3):
            code, directory, result, _, _ = self.execute()
        self.assertEqual(code, 4)
        self.assertEqual(result["dictamen_modelo"], APPROVAL)
        self.assertEqual(result["revisor"]["estado"], "tiempo_agotado")
        self.assertFalse(result["aprobada"])
        self.assertTrue((directory / "revisor/eventos.jsonl").read_bytes())
        self.assertTrue((directory / "revisor/stderr.txt").read_bytes())
        self.assertEqual(len(self.agent_calls()), 1)

    def test_codex_ausente_o_incompatible_o_fallo_de_arranque(self):
        for mode in ("absent", "incompatible", "vanish"):
            with self.subTest(mode=mode):
                self.configure_fake(mode)
                if mode == "absent":
                    self.fake.unlink()
                code, directory, result, _, _ = self.execute()
                self.assertEqual(code, 3)
                self.assertEqual(result["decision_controlador"], "fallo_revisor")
                self.assertFalse(result["aprobada"])
                self.assertTrue((directory / "revisor/resultado.json").exists())
        self.assertEqual(self.agent_calls(), [])

    def test_timeout_en_comprobacion_previa_no_invoca_revisor(self):
        self.configure_fake("version_timeout")
        with patch.object(review_case, "PREFLIGHT_TIMEOUT_SECONDS", 0.3):
            code, _, result, _, _ = self.execute()
        self.assertEqual(code, 4)
        self.assertEqual(result["revisor"]["invocaciones"], 0)
        self.assertEqual(self.agent_calls(), [])

    def assert_rejected(self):
        code, directory, result, output, errors = self.execute()
        self.assertEqual(code, 7)
        self.assertIsNone(directory)
        self.assertIsNone(result)
        self.assertIn("evidencia_invalida", output)
        self.assertTrue(errors)
        self.assertFalse(self.calls.exists())

    def test_evidencia_incompleta_no_invoca_ni_crea_revision(self):
        for name in ("resultado.json", "referencia/contrato.md", "referencia/solution.py",
                     "referencia/test_solution.py", "candidato.py", "candidato.diff",
                     "posterior/workspace/solution.py", "posterior/workspace/test_solution.py",
                     "posterior/resultado.json", "posterior/stdout.txt", "posterior/stderr.txt",
                     "agente/resultado.json", "agente/test_solution_despues.py", "inicial/stderr.txt"):
            with self.subTest(name=name):
                path = self.source / name
                content = path.read_bytes()
                path.unlink()
                try:
                    self.assert_rejected()
                finally:
                    path.write_bytes(content)

    def test_candidato_pruebas_diff_o_informe_alterados_se_rechazan(self):
        for name in ("candidato.py", "posterior/workspace/solution.py", "referencia/test_solution.py",
                     "posterior/workspace/test_solution.py", "candidato.diff", "posterior/stderr.txt"):
            with self.subTest(name=name):
                path = self.source / name
                content = path.read_bytes()
                path.write_bytes(b"alterado\n")
                try:
                    self.assert_rejected()
                finally:
                    path.write_bytes(content)

    def test_hash_candidato_actualizado_no_oculta_copia_evaluada_distinta(self):
        self.save("candidato.py", self.candidate + b"# alterado\n")
        self.summary["sha256"]["candidato"] = review_case.digest((self.source / "candidato.py").read_bytes())
        self.save("resultado.json", self.summary)
        self.assert_rejected()

    def test_informe_con_pruebas_duplicadas_no_acredita_la_referencia(self):
        path = self.source / "posterior/stderr.txt"
        lines = path.read_text().splitlines(keepends=True)
        lines[1] = lines[0]
        path.write_text("".join(lines))
        self.assert_rejected()

    def test_numero_de_pruebas_se_deriva_de_la_referencia_guardada(self):
        for count in (1, 3, 8, 12):
            with self.subTest(count=count):
                reference = "import unittest\nclass TestClasificarEjecucion(unittest.TestCase):\n"
                reference += "".join(f"    def test_{i}(self):\n        pass\n" for i in range(count))
                self.build_record(reference.encode())
                code, _, result, _, _ = self.execute()
                self.assertEqual(code, 0)
                self.assertTrue(result["evidencia_previa_valida"])

    def test_omite_pruebas_o_informe_inconsistente_aunque_diga_ok(self):
        path = self.source / "posterior/stderr.txt"
        original = path.read_text()
        count = len(re.findall(r"^test_", original, re.M))
        rows = original.splitlines(keepends=True)
        first_name = rows[0].split()[0]
        invalid = [
            "OK\n",
            original.replace(f"Ran {count} tests", "Ran 8 tests"),
            original.replace(rows[0], ""),
            original.replace(rows[0], "").replace(f"Ran {count} tests", f"Ran {count - 1} tests"),
            original.replace(rows[0], rows[0].replace(" ... ok", " ... skipped 'omitida'")),
            original.replace(rows[0], rows[0].replace(" ... ok", " ... expected failure")),
            original.replace(first_name, "test_desconocido"),
            original.replace("test_solution.TestClasificarEjecucion.", "test_solution.OtraClase.", 1),
            original.replace("\n\nOK\n", "\n\nOK (skipped=1)\n"),
            original.replace("\n\nOK\n", "\n"),
            f"Ran {count} tests in 0.001s\n\n" + original,
        ]
        for report in invalid:
            with self.subTest(report=report):
                path.write_text(report)
                self.assert_rejected()
        path.write_text(original)

    def test_referencias_sin_pruebas_no_acreditan_evaluacion(self):
        self.build_record(b"import unittest\n")
        self.assert_rejected()

    def test_cambio_de_contrato_no_reescribe_ni_revalida_registro_anterior(self):
        contract = self.project / "tasks/002-classify-run.md"
        contract.write_bytes(contract.read_bytes() + b"\nNueva decision funcional.\n")
        self.assert_rejected()
        self.assertEqual(review_case.snapshot_tree(self.source), self.original_source)

    def test_lectura_estatica_identifica_clase_y_no_ejecuta_referencia(self):
        marker = self.temporary / "referencia_no_debe_ejecutarse"
        reference = (
            f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
            "import unittest\n"
            "class Primera(unittest.TestCase):\n"
            "    def test_igual(self): pass\n"
            "class Segunda(unittest.TestCase):\n"
            "    def test_igual(self): pass\n"
            "def test_ayudante(): pass\n"
        ).encode()
        report = (
            "test_igual (test_solution.Primera.test_igual) ... ok\n"
            "test_igual (test_solution.Segunda.test_igual) ... ok\n"
            "\nRan 2 tests in 0.001s\n\nOK\n"
        )
        review_case.validate_test_report(reference, report)
        self.assertFalse(marker.exists())
        with self.assertRaises(ValueError):
            review_case.validate_test_report(reference, report.replace("Segunda", "Primera"))

    def test_referencia_invalida_duplicada_o_dinamica_se_rechaza(self):
        references = [
            b"no es sintaxis Python!", b"import unittest\n",
            b"class Ejemplo(unittest.TestCase):\n    def test_a(self): pass\n    def test_a(self): pass\n",
            b"class Ejemplo(BaseDinamica):\n    def test_a(self): pass\n",
            b"def load_tests(loader, tests, pattern): return tests\n",
        ]
        for reference in references:
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    review_case.reference_test_ids(reference)

    def test_comando_de_evaluacion_incompleto_no_se_acepta(self):
        del self.summary["pruebas_posteriores"]["comando"]
        self.save("posterior/resultado.json", self.summary["pruebas_posteriores"])
        self.save("resultado.json", self.summary)
        self.assert_rejected()

    def test_caso_rechazado_o_resumen_inconsistente_no_invoca(self):
        original = (self.source / "resultado.json").read_bytes()
        invalid = [[], {}, {**self.summary, "caso": "case_01"},
                   {**self.summary, "aceptada": False}, {**self.summary, "aceptada": 1},
                   {**self.summary, "codigo_salida": False}, {**self.summary, "codigo_salida": 1},
                   {**self.summary, "integridad": {}}, {**self.summary, "sha256": {}},
                   {**self.summary, "pruebas_posteriores": {**self.summary["pruebas_posteriores"], "codigo_salida": 1}}]
        for summary in invalid:
            with self.subTest(summary=summary):
                self.save("resultado.json", summary)
                self.assert_rejected()
        (self.source / "resultado.json").write_bytes(original)

    def test_enlace_en_evidencia_no_se_acepta(self):
        path = self.source / "candidato.py"
        path.unlink()
        path.symlink_to("posterior/workspace/solution.py")
        self.assert_rejected()

    def test_modificacion_de_materiales_impide_aprobacion(self):
        for mode in ("material_tamper", "material_deleted", "material_added", "material_linked"):
            with self.subTest(mode=mode):
                self.configure_fake(mode)
                code, _, result, _, _ = self.execute()
                self.assertEqual(code, 6)
                self.assertFalse(result["integridad"]["workspace_intacto"])
                self.assertEqual(result["dictamen_modelo"], APPROVAL)
                self.assertEqual(review_case.snapshot_tree(self.source), self.original_source)

    def test_modificacion_del_registro_origen_impide_aprobacion(self):
        self.configure_fake("source_tamper")
        code, _, result, _, _ = self.execute()
        self.assertEqual(code, 6)
        self.assertFalse(result["integridad"]["registro_reparacion_intacto"])
        self.assertEqual(result["dictamen_modelo"], APPROVAL)

    def test_no_ejecuta_el_candidato(self):
        marker = self.temporary / "no_debe_crearse"
        candidate = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode()
        self.update_candidate(candidate)
        self.summary["sha256"]["candidato"] = review_case.digest(candidate)
        self.save("resultado.json", self.summary)
        code, _, _, _, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertFalse(marker.exists())
        self.assertEqual(len(self.agent_calls()), 1)

    def test_registros_nuevos_conservan_reparacion(self):
        first = self.execute()
        second = self.execute()
        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertNotEqual(first[1], second[1])
        self.assertEqual(len(self.agent_calls()), 2)
        self.assertEqual(review_case.snapshot_tree(self.source), self.original_source)

    def test_fallo_al_guardar_resumen_no_aprueba_y_conserva_diagnosticos(self):
        original = review_case.write_json

        def fail(path, value):
            if path.name == "resultado.json" and path.parent.parent.name == "runs":
                raise OSError("fallo de escritura simulado")
            return original(path, value)

        with patch.object(review_case, "write_json", side_effect=fail):
            code, directory, _, output, errors = self.execute()
        self.assertEqual(code, 8)
        self.assertIn("fallo_controlador", output)
        self.assertIn("fallo de escritura", errors)
        self.assertTrue((directory / "revisor/eventos.jsonl").read_bytes())
        self.assertTrue((directory / "revisor/respuesta_original.txt").read_bytes())

    def test_cli_con_ruta_relativa_desde_otro_directorio(self):
        for name in ("review_case.py", "repair_case.py", "run_case.py"):
            shutil.copy2(PROJECT_ROOT / name, self.project / name)
        tools_dir = self.temporary / "bin"
        tools_dir.mkdir()
        shutil.copy2(self.fake, tools_dir / "codex")
        env = dict(os.environ, PATH=str(tools_dir) + os.pathsep + os.environ.get("PATH", ""))
        completed = subprocess.run(
            [sys.executable, "-B", str(self.project / "review_case.py"), "--run",
             str(self.source.relative_to(self.temporary))], cwd=self.temporary, env=env,
            capture_output=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.agent_calls()), 1)
        self.assertEqual(review_case.snapshot_tree(self.source), self.original_source)
        rejected = subprocess.run([sys.executable, "-B", str(self.project / "review_case.py")],
                                  cwd=self.temporary, env=env, capture_output=True, timeout=10)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(len(self.agent_calls()), 1)


if __name__ == "__main__":
    unittest.main()

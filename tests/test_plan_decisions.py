"""Decisiones sobre supuestos con registros temporales y CLI simulada."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import plan_project as planner
import project_plan
import project_plan_continuation as continuity
from case_evidence import digest
from repair_project import tree_state
import test_plan_continuation as previous
import test_plan_project as initial


def assumed():
    plan = initial.concrete()
    plan["supuestos"] = [f"Supuesto sintético {i}." for i in range(1, 6)]
    return plan


class DecisionTests(unittest.TestCase):
    setUp = previous.ContinuationTests.setUp
    git = previous.ContinuationTests.git
    configure = previous.ContinuationTests.configure
    calls_read = previous.ContinuationTests.calls_read
    assert_failure = previous.ContinuationTests.assert_failure
    answers = previous.ContinuationTests.answers
    rehash = previous.ContinuationTests.rehash

    def origin(self):
        plan = initial.ambiguous()
        plan["supuestos"] = []
        plan["preguntas_pendientes"] = [f"¿Pregunta sintética {i}?" for i in range(1, 7)]
        self.configure(plan=plan)
        first = planner.run_plan("Caso sintético: seis respuestas y cinco supuestos.", self.root)
        self.assertEqual(first["codigo_salida"], 0, first)
        parent = Path(first["registro"])
        answers = self.answers(parent, *[f"Respuesta sintética {i}." for i in range(1, 7)])
        self.configure(plan=assumed())
        second = planner.run_plan(None, self.root, from_plan=parent, answers=answers)
        self.assertEqual(second["codigo_salida"], 0, second)
        return Path(second["registro"])

    def call(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = planner.main(args, project_root=self.root)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def simple_origin(self, plan=None):
        self.configure(plan=assumed() if plan is None else plan)
        result = planner.run_plan("Petición sintética, nunca respuestas reales.", self.root)
        self.assertEqual(result["codigo_salida"], 0, result)
        return Path(result["registro"])

    def decisions(self, parent, *choices):
        target = self.tmp / f"decisiones-{len(list(self.tmp.glob('decisiones-*.json')))}.json"
        continuity.export_template(parent, target, decisions=True)
        data = json.loads(target.read_bytes())
        for item, (action, explanation, alternative) in zip(data["decisiones"], choices):
            item.update(decision=action, explicacion=explanation, alternativa=alternative)
        target.write_bytes(continuity.encoded(data))
        return target

    def continue_plan(self, parent, decisions=None, answers=None):
        return planner.run_plan(None, self.root, from_plan=parent, decisions=decisions, answers=answers)

    def assert_success(self, result):
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertFalse(result["aprobada"])
        self.assertTrue(all(result["integridad"].values()))
        self.assertEqual(result["invocaciones"], {"planificador": 1})
        return continuity.load_parent(result["registro"])

    def legacy_v2(self, child):
        """Construir formato histórico sintético; nunca leer ni reescribir runs privados."""
        proposal = json.loads((child / "propuesta.json").read_bytes())
        meta = {k: proposal["continuacion"][k] for k in (
            "profundidad", "padre", "respuestas_confirmadas", "pendientes_anteriores", "preguntas_pendientes")}
        meta["version"] = 1
        proposal.update(version=2, continuacion=meta, estado=project_plan.plan_state(proposal["propuesta"]))
        (child / "propuesta.json").write_bytes(continuity.encoded(proposal))
        (child / "propuesta.md").write_text(project_plan.render_proposal(proposal))
        path = child / "materiales/continuacion.json"
        value = json.loads(path.read_bytes())
        value = {k: value[k] for k in ("propuesta_anterior_del_modelo", "preguntas_identificadas",
                                     "respuestas_explicitas_del_usuario", "preguntas_sin_responder")}
        value["version"] = 1
        path.write_bytes(continuity.encoded(value))
        path = child / "planificador/entrada.txt"
        prompt = json.loads(path.read_bytes())
        prompt["materiales"]["continuacion.json"] = (child / "materiales/continuacion.json").read_text()
        path.write_bytes(continuity.encoded(prompt))
        path = child / "procedencia.json"
        provenance = json.loads(path.read_bytes())
        provenance["continuacion"] = {k: v for k, v in meta.items() if k != "preguntas_pendientes"}
        provenance["materiales"] = tree_state(child / "materiales")
        provenance["prompt_sha256"] = digest((child / "planificador/entrada.txt").read_bytes())
        path.write_bytes(continuity.encoded(provenance))
        path = child / "resultado.json"
        result = json.loads(path.read_bytes())
        result["estado"] = proposal["estado"]
        path.write_bytes(continuity.encoded(result))
        self.rehash(child)

    def test_cero_preguntas_cinco_supuestos_solo_decisiones(self):
        parent = self.origin()
        proposal = json.loads((parent / "propuesta.json").read_bytes())
        self.assertEqual(proposal["estado"], "necesita_aclaraciones")
        self.assertEqual(len(proposal["continuacion"]["respuestas_confirmadas"]), 6)
        empty = self.answers(parent)
        self.assertEqual(json.loads(empty.read_bytes())["respuestas"], [])
        with patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(parent, answers=empty), "error_controlador", 0)
            invoke.assert_not_called()
        target = self.tmp / "decisiones.json"
        before = self.calls_read()
        code, out, err = self.call(["--from-plan", str(parent), "--decisions-template", str(target)])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.calls_read(), before)
        data = json.loads(target.read_bytes())
        self.assertEqual(len(data["decisiones"]), 5)
        for item in data["decisiones"]:
            self.assertEqual(item["decision"], "sin_decidir")
            item["decision"] = "aceptar"
        target.write_bytes(continuity.encoded(data))
        self.configure()
        code, out, err = self.call(["--from-plan", str(parent), "--decisions", str(target)])
        self.assertEqual(code, 0, err)
        self.assertIn("Estado: borrador", out)
        self.assertEqual(len(self.calls_read()) - len(before), 3)

    def test_exportacion_ids_origen_no_cli_no_reserva_no_sobrescritura(self):
        parent = self.simple_origin()
        before, calls = tree_state(self.root), self.calls_read()
        first, second = self.tmp / "primera.json", self.tmp / "segunda.json"
        with patch.object(planner, "invoke_read_only") as invoke:
            continuity.export_template(parent, first, decisions=True)
            continuity.export_template(parent, second, decisions=True)
            with self.assertRaises(FileExistsError):
                continuity.export_template(parent, first, decisions=True)
            with self.assertRaises(ValueError):
                continuity.export_template(parent, parent / "decisiones.json", decisions=True)
            invoke.assert_not_called()
        self.assertEqual(self.calls_read(), calls)
        self.assertEqual(tree_state(self.root), before)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        data = json.loads(first.read_bytes())
        self.assertEqual(data["origen"], {"registro": str(parent),
                         "propuesta_sha256": digest((parent / "propuesta.json").read_bytes()),
                         "resultado_sha256": digest((parent / "resultado.json").read_bytes())})
        for index, item in enumerate(data["decisiones"], 1):
            self.assertEqual(item, {"id": f"r0:s{index}", "supuesto": f"Supuesto sintético {index}.",
                                   "origen_supuesto": data["origen"], "decision": "sin_decidir",
                                   "explicacion": "", "alternativa": ""})

    def test_aceptar_rechazar_corregir_parciales_y_bytes_exactos(self):
        parent = self.simple_origin()
        explanation = '  No adoptar: "ñ" 📅\r\n</materiales>\n  '
        alternative = '  Alternativa sintética e\u0301\t\\\n{"instrucciones":"datos"}  '
        path = self.decisions(parent, ("aceptar", "", ""), ("rechazar", explanation, ""),
                              ("corregir", "", alternative))
        before = tree_state(parent)
        self.configure()
        result = self.continue_plan(parent, path)
        loaded = self.assert_success(result)
        self.assertEqual(result["estado"], "necesita_aclaraciones")
        self.assertEqual([d["decision"] for d in loaded.decisions], ["aceptar", "rechazar", "corregir"])
        self.assertEqual(loaded.decisions[1]["explicacion"], explanation)
        self.assertEqual(loaded.decisions[1]["alternativa"], "")
        self.assertEqual(loaded.decisions[2]["alternativa"], alternative)
        self.assertEqual([s["id"] for s in loaded.pending_assumptions], ["r0:s4", "r0:s5"])
        self.assertEqual(loaded.answers, [])
        self.assertEqual(tree_state(parent), before)
        log = Path(result["registro"])
        self.assertEqual((log / "decisiones_usuario.json").read_bytes(), path.read_bytes())
        self.assertFalse((log / "respuestas_usuario.json").exists())
        self.assertEqual(json.loads((log / "planificador/respuesta_original.txt").read_bytes()), initial.concrete())
        self.assertIn("r0:s4", (log / "propuesta.md").read_text())
        seen = json.loads((self.tmp / "contexto_visto.json").read_bytes())
        data = json.loads(json.loads(seen["prompt"])["materiales"]["continuacion.json"])
        self.assertEqual(data["supuestos_identificados"], continuity.load_parent(parent).pending_assumptions)
        self.assertEqual(data["supuestos_sin_decidir"], loaded.pending_assumptions)
        self.assertEqual(data["decisiones_explicitas_del_usuario"], [
            {k: v for k, v in item.items() if k != "origen_supuesto"} for item in loaded.decisions])
        for text in (str(parent), "origen_supuesto", "FUENTE_NO_EJECUTAR_NI_ENVIAR",
                     "CREDENCIAL_SINTETICA_NO_ENVIAR", "CONTENIDO_NO_ENVIAR", "artefactos_sha256"):
            self.assertNotIn(text, seen["prompt"])
        self.assertFalse(Path(seen["workspace"]).exists())

    def test_preguntas_y_supuestos_juntos_una_revision_y_una_invocacion(self):
        plan = assumed()
        plan["preguntas_pendientes"] = ["¿Pregunta sintética?"]
        parent = self.simple_origin(plan)
        answers = self.answers(parent, "Respuesta explícita sintética")
        decisions = self.decisions(parent, *[("aceptar", "", "")] * 5)
        before = len(list((self.root / "runs").glob("*_plan_project_*")))
        calls = len(self.calls_read())
        self.configure()
        code, out, err = self.call(["--from-plan", str(parent), "--answers", str(answers), "--decisions", str(decisions)])
        self.assertEqual(code, 0, err)
        self.assertIn("Estado: borrador", out)
        self.assertEqual(len(self.calls_read()) - calls, 3)  # versión, ayuda y un único exec
        logs = list((self.root / "runs").glob("*_plan_project_*"))
        self.assertEqual(len(logs), before + 1)
        child = max(logs, key=lambda p: p.stat().st_mtime_ns)
        loaded = continuity.load_parent(child)
        self.assertEqual(len(loaded.answers), 1)
        self.assertEqual(len(loaded.decisions), 5)
        self.assertEqual(loaded.pending, [])
        self.assertEqual(loaded.pending_assumptions, [])
        self.assertFalse(json.loads((child / "resultado.json").read_bytes())["aprobada"])

    def test_pendientes_preguntas_y_supuestos_omitidos_no_se_resuelven(self):
        plan = assumed()
        plan["preguntas_pendientes"] = ["¿Pregunta que sigue sin responder?"]
        parent = self.simple_origin(plan)
        decisions = self.decisions(parent, ("aceptar", "", ""))
        answers = self.answers(parent, " \t\r\n")
        self.configure()
        result = self.continue_plan(parent, decisions, answers)
        child = self.assert_success(result)
        self.assertEqual(result["estado"], "necesita_aclaraciones")
        self.assertEqual(child.pending, [{"id": "r0:p1", "pregunta": plan["preguntas_pendientes"][0]}])
        self.assertEqual(len(child.pending_assumptions), 4)
        self.assertEqual(child.answers, [])

    def test_acumulacion_origen_y_textos_repetidos_reciben_nuevos_ids(self):
        parent = self.simple_origin()
        decisions = self.decisions(parent, ("aceptar", "", ""))
        self.configure(plan=assumed())  # mismo texto, nuevas identidades
        first = self.continue_plan(parent, decisions)
        child = self.assert_success(first)
        self.assertEqual([s["id"] for s in child.pending_assumptions],
                         [f"r0:s{i}" for i in range(2, 6)] + [f"r1:s{i}" for i in range(1, 6)])
        before = tree_state(parent), tree_state(child.path)
        decisions2 = self.decisions(child.path, ("corregir", "", "Alternativa sintética"))
        data = json.loads(decisions2.read_bytes())
        self.assertEqual(data["decisiones"][0]["origen_supuesto"]["registro"], str(parent))
        self.assertEqual(data["decisiones"][4]["origen_supuesto"]["registro"], str(child.path))
        self.configure()
        second = self.continue_plan(child.path, decisions2)
        grandchild = self.assert_success(second)
        self.assertEqual(grandchild.decisions[0], child.decisions[0])
        self.assertEqual([d["id"] for d in grandchild.decisions], ["r0:s1", "r0:s2"])
        self.assertEqual(len(grandchild.pending_assumptions), 8)
        self.assertEqual((tree_state(parent), tree_state(child.path)), before)
        self.assertEqual((grandchild.path / "materiales/contexto.json").read_bytes(),
                         (parent / "materiales/contexto.json").read_bytes())

    def test_compatibilidad_v2_sin_reescribir_ni_resolver_por_omision(self):
        plan = assumed()
        plan["preguntas_pendientes"] = ["¿Pregunta sintética?"]
        parent = self.simple_origin(plan)
        answers = self.answers(parent, "Respuesta v1 sintética")
        self.assertEqual(json.loads(answers.read_bytes())["version"], 1)
        self.configure()
        result = self.continue_plan(parent, answers=answers)
        child = Path(result["registro"])
        self.legacy_v2(child)
        before = tree_state(child)
        self.assertEqual(json.loads((child / "resultado.json").read_bytes())["estado"], "borrador")
        loaded = continuity.load_parent(child)
        self.assertEqual(len(loaded.pending_assumptions), 5)  # derivados, sin reclasificar el histórico
        decisions = self.decisions(child, *[("aceptar", "", "")] * 5)
        revised = self.continue_plan(child, decisions)
        final = self.assert_success(revised)
        self.assertEqual(revised["estado"], "borrador")
        self.assertEqual(final.answers, loaded.answers)
        self.assertEqual(tree_state(child), before)

    def test_v2_caso_cinco_supuestos_deriva_identidad_de_su_revision(self):
        parent = self.origin()
        self.legacy_v2(parent)
        loaded = continuity.load_parent(parent)
        self.assertEqual([s["id"] for s in loaded.pending_assumptions], [f"r1:s{i}" for i in range(1, 6)])
        for origin in loaded.assumption_origins.values():
            self.assertEqual(origin, continuity.reference(loaded))
        target = self.decisions(parent, *[("aceptar", "", "")] * 5)
        self.configure()
        self.assertEqual(self.assert_success(self.continue_plan(parent, target)).pending_assumptions, [])

    def test_no_degradar_v3_a_v2_perdiendo_decisiones(self):
        parent = self.simple_origin()
        decisions = self.decisions(parent, ("aceptar", "", ""))
        plan = initial.concrete()
        plan["preguntas_pendientes"] = ["¿Nueva pregunta sintética?"]
        self.configure(plan=plan)
        child = self.assert_success(self.continue_plan(parent, decisions))
        answers = self.answers(child.path, "Respuesta sintética")
        self.configure()
        grandchild = Path(self.continue_plan(child.path, answers=answers)["registro"])
        self.legacy_v2(grandchild)  # intenta borrar el historial de decisiones usando el formato anterior
        with self.assertRaises(ValueError):
            continuity.load_parent(grandchild)

    def test_sin_decisiones_efectivas_no_llama_ni_reserva(self):
        parent = self.simple_origin()
        target = self.decisions(parent)
        with patch.object(planner, "invoke_read_only") as invoke:
            result = self.continue_plan(parent, target)
        invoke.assert_not_called()
        self.assert_failure(result, "error_controlador", 0)
        self.assertIsNone(result["registro"])

    def test_decisiones_incoherentes_origen_unicode_y_duplicados_rechazados(self):
        parent = self.simple_origin()
        target = self.decisions(parent, ("aceptar", "", ""))
        valid = json.loads(target.read_bytes())
        cases = []
        for key, value in (("id", "r0:s99"), ("supuesto", "Otro texto"), ("decision", "Aceptar"),
                           ("decision", True), ("explicacion", "No corresponde"), ("alternativa", " "),
                           ("explicacion", None), ("explicacion", "\ud800"), ("alternativa", "x" * 8001)):
            data = copy.deepcopy(valid)
            data["decisiones"][0][key] = value
            cases.append(json.dumps(data).encode())
        for action, explanation, alternative in (("rechazar", " \n", ""), ("rechazar", "Motivo", "Alternativa"),
                                                  ("corregir", "", " \t"), ("corregir", "Motivo", "Alternativa"),
                                                  ("sin_decidir", "Motivo", ""), ("sin_decidir", "", "Alternativa")):
            data = copy.deepcopy(valid)
            data["decisiones"][0].update(decision=action, explicacion=explanation, alternativa=alternative)
            cases.append(continuity.encoded(data))
        for area in ("origen", "origen_supuesto"):
            for key in ("registro", "propuesta_sha256", "resultado_sha256"):
                data = copy.deepcopy(valid)
                origin = data["origen"] if area == "origen" else data["decisiones"][0]["origen_supuesto"]
                origin[key] = "incorrecto"
                cases.append(continuity.encoded(data))
        data = copy.deepcopy(valid)
        data["decisiones"][1] = data["decisiones"][0]
        cases.append(continuity.encoded(data))
        data = copy.deepcopy(valid)
        data["decisiones"][0]["extra"] = "no permitido"
        cases.extend([continuity.encoded(data), b'', b'{}', b'\xff', b'{"version":1,"version":1}',
                      target.read_bytes().replace(b'"decision":', b'"decision":"aceptar","decision":', 1)])
        before = tree_state(self.root)
        for raw in cases:
            target.write_bytes(raw)
            with self.subTest(raw=repr(raw)[:100]), patch.object(planner, "invoke_read_only") as invoke:
                result = self.continue_plan(parent, target)
                self.assert_failure(result, "error_controlador", 0)
                self.assertIsNone(result["registro"])
                invoke.assert_not_called()
        self.assertEqual(tree_state(self.root), before)

    def test_supuesto_resuelto_no_se_puede_decidir_de_nuevo(self):
        parent = self.simple_origin()
        first = self.decisions(parent, ("aceptar", "", ""))
        resolved = json.loads(first.read_bytes())["decisiones"][0]
        self.configure()
        child = self.assert_success(self.continue_plan(parent, first))
        second = self.decisions(child.path, ("aceptar", "", ""))
        data = json.loads(second.read_bytes())
        data["decisiones"][0] = resolved
        second.write_bytes(continuity.encoded(data))
        with patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(child.path, second), "error_controlador", 0)
            invoke.assert_not_called()

    def test_limites_archivos_no_regulares_y_entradas_combinadas(self):
        parent = self.simple_origin()
        target = self.decisions(parent, ("aceptar", "", ""))
        answers = self.answers(parent)
        for owner, constant in ((planner, "MAX_ANSWERS"), (planner, "MAX_MESSAGE"),
                                (continuity, "MAX_CHAIN_BYTES"), (continuity, "MAX_DEPTH")):
            with self.subTest(constant=constant), patch.object(owner, constant, 1 if constant != "MAX_DEPTH" else 0), \
                    patch.object(planner, "invoke_read_only") as invoke:
                self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
                invoke.assert_not_called()
        limit = len(target.read_bytes()) + len(answers.read_bytes()) - 1
        with patch.object(continuity, "MAX_ANSWERS", limit), patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(parent, target, answers), "error_controlador", 0)
            invoke.assert_not_called()
        target.unlink()
        os.mkfifo(target)
        with patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
            target.unlink()
            target.symlink_to(answers)
            self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
            invoke.assert_not_called()

    def test_stdin_decisiones_omitidas_o_alteradas_no_emite_respuesta(self):
        parent = self.simple_origin()
        target = self.decisions(parent, ("aceptar", "", ""))
        self.configure()
        original = planner.invoke_read_only
        for name in ("decisiones_explicitas_del_usuario", "supuestos_sin_decidir"):
            def damaged(workspace, final, prompt, log, **kwargs):
                message = json.loads(prompt)
                data = json.loads(message["materiales"]["continuacion.json"])
                data[name] = []
                message["materiales"]["continuacion.json"] = continuity.encoded(data).decode()
                return original(workspace, final, continuity.encoded(message), log, **kwargs)
            with self.subTest(name=name), patch.object(planner, "invoke_read_only", side_effect=damaged):
                result = self.continue_plan(parent, target)
            self.assert_failure(result, "fallo_proceso", 1)
            log = Path(result["registro"])
            self.assertEqual((log / "planificador/eventos.jsonl").read_bytes(), b"")
            self.assertEqual((log / "planificador/respuesta_original.txt").read_bytes(), b"")

    def test_estado_viabilidad_y_preguntas_nuevas_sin_aprobacion(self):
        parent = self.simple_origin()
        target = self.decisions(parent, *[("aceptar", "", "")] * 5)
        for plan in (initial.concrete(), initial.blocked(), initial.ambiguous()):
            self.configure(plan=plan)
            result = self.continue_plan(parent, target)
            self.assert_success(result)
            self.assertEqual(result["estado"], project_plan.plan_state(plan))

    def test_errores_cli_e_integridad_conservan_presupuesto_y_originales(self):
        parent = self.simple_origin()
        target = self.decisions(parent, ("aceptar", "", ""))
        before = tree_state(parent)
        for options, kind, count in (({"code": 7}, "fallo_proceso", 1),
                                      ({"raw": "{"}, "respuesta_invalida", 1),
                                      ({"mode": "workspace_tamper"}, "integridad", 1),
                                      ({"mode": "tamper_help"}, "integridad", 0)):
            self.configure(**options)
            with self.subTest(options=options):
                self.assert_failure(self.continue_plan(parent, target), kind, count)
                self.assertEqual(tree_state(parent), before)

    def test_argumentos_plantillas_excluyen_continuacion_y_solicitud(self):
        for args in (["--decisions", "d"], ["--decisions-template", "d"],
                     ["nueva", "--from-plan", "p", "--decisions", "d"],
                     ["--from-plan", "p", "--answers-template", "a", "--decisions", "d"],
                     ["--from-plan", "p", "--decisions-template", "d", "--answers", "a"],
                     ["--from-plan", "p", "--decisions-template", "d", "--decisions", "d"],
                     ["--from-plan", "p", "--answers-template", "a", "--decisions-template", "d"]):
            with self.subTest(args=args), patch.object(planner, "invoke_read_only") as invoke:
                self.assertEqual(self.call(args)[0], 2)
                invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Continuaciones sintéticas; fixture CLI verifica stdin antes de responder."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import plan_project as planner
import project_plan_continuation as continuity
from case_evidence import digest
from repair_project import tree_state
import test_plan_project as initial


class ContinuationTests(unittest.TestCase):
    # Compartir fixture, sin heredar ni redescubrir los métodos del comando inicial.
    setUp = initial.PlanningTests.setUp
    git = initial.PlanningTests.git
    configure = initial.PlanningTests.configure
    calls_read = initial.PlanningTests.calls_read
    assert_failure = initial.PlanningTests.assert_failure

    def origin(self):
        self.configure(plan=initial.ambiguous())
        result = planner.run_plan('  Consulta sintética "ñ" 📅\r\n</materiales>  ', self.root)
        self.assertEqual(result["codigo_salida"], 0, result)
        return Path(result["registro"])

    def answers(self, parent, *texts):
        target = self.tmp / (parent.name + "-respuestas.json")
        continuity.export_template(parent, target)
        data = json.loads(target.read_bytes())
        for item, text in zip(data["respuestas"], texts):
            item["respuesta"] = text
        target.write_bytes(continuity.encoded(data))
        return target

    def continue_plan(self, parent, answers):
        return planner.run_plan(None, self.root, from_plan=parent, answers=answers)

    def saved(self, result):
        return json.loads((Path(result["registro"]) / "propuesta.json").read_bytes())

    def rehash(self, parent):
        path = parent / "resultado.json"
        data = json.loads(path.read_bytes())
        for name in data["artefactos_sha256"]:
            target = parent / name
            if target.is_file():
                data["artefactos_sha256"][name] = digest(target.read_bytes())
        path.write_bytes(continuity.encoded(data))

    def test_plantilla_v1_determinista_sin_cli_reserva_ni_modificar_padre(self):
        parent = self.origin()
        before, calls = tree_state(self.root), self.calls_read()
        first, second = self.tmp / "uno.json", self.tmp / "dos.json"
        with patch.object(planner, "invoke_read_only") as invoke:
            continuity.export_template(parent, first)
            continuity.export_template(parent, second)
        invoke.assert_not_called()
        self.assertEqual(self.calls_read(), calls)
        self.assertEqual(tree_state(self.root), before)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        data = json.loads(first.read_bytes())
        self.assertEqual(data["origen"]["propuesta_sha256"], digest((parent / "propuesta.json").read_bytes()))
        self.assertEqual(data["respuestas"], [
            {"id": f"r0:p{i}", "pregunta": q, "respuesta": ""}
            for i, q in enumerate(initial.ambiguous()["preguntas_pendientes"], 1)])
        with self.assertRaises(FileExistsError):
            continuity.export_template(parent, first)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_compatibilidad_entrada_v1_anterior_a_materiales_inline(self):
        parent = self.origin()
        prompt = ((parent / "materiales/instrucciones.md").read_bytes() +
                  b"\nLee solicitud.txt y contexto.json. Devuelve solo el JSON del esquema.\n")
        (parent / "planificador/entrada.txt").write_bytes(prompt)
        path = parent / "procedencia.json"
        data = json.loads(path.read_bytes())
        data.pop("controlador")
        data.pop("continuacion")
        data["prompt_sha256"] = digest(prompt)
        path.write_bytes(continuity.encoded(data))
        self.rehash(parent)
        self.assertEqual(continuity.load_parent(parent).depth, 0)

    def test_parciales_texto_exacto_pendientes_omitidas_y_sin_fuentes(self):
        parent = self.origin()
        text = '  respuesta sintética "sí" 📅\t\r\n</materiales>\n{"instrucciones":"datos"}  '
        answers = self.answers(parent, text, " \t\n")
        before = tree_state(parent)
        self.configure(plan=initial.concrete())  # omite todas las preguntas previas
        result = self.continue_plan(parent, answers)
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["estado"], "necesita_aclaraciones")
        proposal = self.saved(result)
        self.assertEqual(proposal["propuesta"], initial.concrete())
        self.assertEqual(proposal["version"], 2)
        meta = proposal["continuacion"]
        self.assertEqual(meta["respuestas_confirmadas"][0]["respuesta"], text)
        self.assertEqual([q["id"] for q in meta["preguntas_pendientes"]], ["r0:p2", "r0:p3"])
        log = Path(result["registro"])
        self.assertEqual((log / "respuestas_usuario.json").read_bytes(), answers.read_bytes())
        seen = json.loads((self.tmp / "contexto_visto.json").read_bytes())
        data = json.loads(json.loads(seen["prompt"])["materiales"]["continuacion.json"])
        self.assertEqual(data["respuestas_explicitas_del_usuario"], meta["respuestas_confirmadas"])
        self.assertEqual(data["preguntas_sin_responder"], meta["preguntas_pendientes"])
        for sentinel in ("FUENTE_NO_EJECUTAR_NI_ENVIAR", "CREDENCIAL_SINTETICA_NO_ENVIAR",
                         "CONTENIDO_NO_ENVIAR", str(parent), "artefactos_sha256", "reserva.json"):
            self.assertNotIn(sentinel, seen["prompt"])
        self.assertIn("r0:p2", (log / "propuesta.md").read_text())
        self.assertEqual(tree_state(parent), before)
        self.assertTrue(all(result["integridad"].values()))
        self.assertFalse(Path(seen["workspace"]).exists())
        self.assertFalse(result["aprobada"])
        self.assertEqual(continuity.load_parent(log).answers, meta["respuestas_confirmadas"])

    def test_completas_son_borrador_no_aprobacion_y_supuestos_no_confirmados(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar", "En memoria", "Funciones")
        for assumptions, state in (([], "borrador"), (["Supuesto del modelo"], "necesita_aclaraciones")):
            plan = initial.concrete()
            plan["supuestos"] = assumptions
            self.configure(plan=plan)
            result = self.continue_plan(parent, answers)
            self.assertEqual(result["estado"], state, result)
            self.assertFalse(result["aprobada"])
            meta = self.saved(result)["continuacion"]
            self.assertEqual(meta["preguntas_pendientes"], [])
            self.assertEqual(len(meta["respuestas_confirmadas"]), 3)

    def test_dos_continuaciones_acumulan_sin_sustituir_ni_refrescar_contexto(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        original = tree_state(parent)
        self.configure()
        first = self.continue_plan(parent, answers)
        self.assertEqual(first["codigo_salida"], 0, first)
        child = Path(first["registro"])
        child_before = tree_state(child)
        second_answers = self.answers(child, "Memoria", "Funciones")
        (self.root / "nuevo.py").write_text("# nombre nuevo, no parte de base histórica\n")
        self.git("add", "nuevo.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Otro HEAD")
        second = self.continue_plan(child, second_answers)
        self.assertEqual(second["codigo_salida"], 0, second)
        self.assertNotEqual(second["commit_controlador"], self.base)
        self.assertEqual(second["commit_base"], self.base)
        log = Path(second["registro"])
        self.assertEqual((log / "materiales/contexto.json").read_bytes(), (parent / "materiales/contexto.json").read_bytes())
        self.assertEqual([a["respuesta"] for a in continuity.load_parent(log).answers], ["Consultar", "Memoria", "Funciones"])
        self.assertEqual(tree_state(parent), original)
        self.assertEqual(tree_state(child), child_before)
        self.assertTrue(all(second["integridad"].values()))

    def test_preguntas_modelo_tienen_ids_nuevos_sin_emparejar_textos(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure(plan=initial.ambiguous())
        result = self.continue_plan(parent, answers)
        self.assertEqual(result["codigo_salida"], 0, result)
        ids = [q["id"] for q in continuity.load_parent(result["registro"]).pending]
        self.assertEqual(ids, ["r0:p2", "r0:p3", "r1:p1", "r1:p2", "r1:p3"])

    def test_respuestas_invalidas_no_consultan_cli_ni_reservan(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        valid = json.loads(answers.read_bytes())
        invalid = []
        for field, value in (("registro", str(self.tmp)), ("propuesta_sha256", "0" * 64), ("resultado_sha256", "0" * 64)):
            data = copy.deepcopy(valid)
            data["origen"][field] = value
            invalid.append(continuity.encoded(data))
        for field, value in (("id", "r0:p9"), ("pregunta", "otra"), ("respuesta", 1), ("respuesta", "x" * 8001)):
            data = copy.deepcopy(valid)
            data["respuestas"][0][field] = value
            invalid.append(continuity.encoded(data))
        data = copy.deepcopy(valid)
        data["respuestas"][1] = data["respuestas"][0]
        invalid.append(continuity.encoded(data))
        data = copy.deepcopy(valid)
        data["extra"] = True
        invalid.extend([continuity.encoded(data), b'{"version":1,"version":1}', b'"\\ud800"', b'\xff', b'{}'])
        data = copy.deepcopy(valid)
        data["respuestas"][0]["respuesta"] = "\ud800"
        invalid.append(json.dumps(data).encode())
        data = copy.deepcopy(valid)
        data["respuestas"][0]["respuesta"] = " \t\n"
        invalid.append(continuity.encoded(data))
        calls = self.calls_read()
        for raw in invalid:
            answers.write_bytes(raw)
            with self.subTest(raw=repr(raw)[:100]), patch.object(planner, "invoke_read_only") as invoke:
                result = self.continue_plan(parent, answers)
                self.assert_failure(result, "error_controlador", 0)
                self.assertIsNone(result["registro"])
                invoke.assert_not_called()
        self.assertEqual(self.calls_read(), calls)

    def test_no_sustituir_respuestas_anteriores(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure()
        first = self.continue_plan(parent, answers)
        child = Path(first["registro"])
        second = self.answers(child, "Memoria")
        data = json.loads(second.read_bytes())
        data["respuestas"].insert(0, {"id": "r0:p1", "pregunta": "¿Qué operaciones incluye?", "respuesta": "Modificar"})
        second.write_bytes(continuity.encoded(data))
        with patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(child, second), "error_controlador", 0)
            invoke.assert_not_called()

    def test_origen_tecnico_ausente_hash_y_no_regular_rechazados(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        proposal = parent / "propuesta.json"
        original = proposal.read_bytes()
        for mode in ("ausente", "hash", "enlace", "directorio"):
            proposal.unlink(missing_ok=True)
            if mode == "hash":
                proposal.write_bytes(original + b" ")
            elif mode == "enlace":
                proposal.symlink_to(answers)
            elif mode == "directorio":
                proposal.mkdir()
            with self.subTest(mode=mode), patch.object(planner, "invoke_read_only") as invoke:
                self.assert_failure(self.continue_plan(parent, answers), "error_controlador", 0)
                invoke.assert_not_called()
            if proposal.is_dir():
                proposal.rmdir()
        proposal.write_bytes(original)
        result_path = parent / "resultado.json"
        data = json.loads(result_path.read_bytes())
        data.update(codigo_salida=1, estado="fallo_tecnico")
        result_path.write_bytes(continuity.encoded(data))
        with self.assertRaises(ValueError):
            continuity.load_parent(parent)

    def test_coherencia_no_basta_recalcular_hash(self):
        parent = self.origin()
        cases = [("propuesta.json", "solicitud_original", "otra"),
                 ("propuesta.json", "propuesta", initial.concrete()),
                 ("procedencia.json", "prompt_sha256", "0" * 64),
                 ("reserva.json", "numero", 2)]
        for name, key, value in cases:
            path = parent / name
            original = path.read_bytes()
            data = json.loads(original)
            data[key] = value
            path.write_bytes(continuity.encoded(data))
            self.rehash(parent)
            with self.subTest(name=name, key=key), self.assertRaises(ValueError):
                continuity.load_parent(parent)
            path.write_bytes(original)
            self.rehash(parent)

    def test_modo_material_y_directorio_enlace_rechazados(self):
        parent = self.origin()
        material = parent / "materiales/contexto.json"
        mode = material.stat().st_mode & 0o777
        material.chmod(mode ^ 0o020)
        with self.assertRaises(ValueError):
            continuity.load_parent(parent)
        material.chmod(mode)
        actual = self.tmp / "materiales"
        (parent / "materiales").rename(actual)
        (parent / "materiales").symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            continuity.load_parent(parent)

    def test_limites_entrada_mensaje_cadena_y_archivo_antes_cli(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        for constant in ("MAX_ANSWERS", "MAX_MESSAGE"):
            with self.subTest(limit=constant), patch.object(planner, constant, 1), \
                    patch.object(planner, "invoke_read_only") as invoke:
                self.assert_failure(self.continue_plan(parent, answers), "error_controlador", 0)
                invoke.assert_not_called()
        for constant in ("MAX_CHAIN_BYTES", "MAX_ARTIFACTS"):
            with self.subTest(limit=constant), patch.object(continuity, constant, 1), self.assertRaises(ValueError):
                continuity.load_parent(parent)
        with self.assertRaises(ValueError):
            continuity.regular_bytes(answers, 1)
        self.configure()
        first = self.continue_plan(parent, answers)
        child = Path(first["registro"])
        next_answers = self.answers(child, "Memoria")
        with patch.object(continuity, "MAX_DEPTH", 1), patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(child, next_answers), "error_controlador", 0)
            invoke.assert_not_called()
        with patch.object(continuity, "MAX_DEPTH", 0), self.assertRaises(ValueError):
            continuity.load_parent(child)

    def test_stdin_omitido_no_emite_respuesta_aunque_workspace_completo(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure()
        original = planner.invoke_read_only
        def damaged(workspace, final, prompt, log, **kwargs):
            message = json.loads(prompt)
            del message["materiales"]["continuacion.json"]
            return original(workspace, final, continuity.encoded(message), log, **kwargs)
        with patch.object(planner, "invoke_read_only", side_effect=damaged):
            result = self.continue_plan(parent, answers)
        self.assert_failure(result, "fallo_proceso", 1)
        log = Path(result["registro"])
        self.assertEqual((log / "planificador/eventos.jsonl").read_bytes(), b"")
        self.assertEqual((log / "planificador/respuesta_original.txt").read_bytes(), b"")

    def test_fallo_cli_respuesta_invalida_e_integridad_preservan_reserva(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        before = tree_state(parent)
        cases = [({"code": 7}, "fallo_proceso"), ({"raw": "{"}, "respuesta_invalida"),
                 ({"mode": "workspace_tamper"}, "integridad")]
        for options, failure in cases:
            self.configure(**options)
            with self.subTest(options=options):
                result = self.continue_plan(parent, answers)
                self.assert_failure(result, failure, 1)
                self.assertEqual(tree_state(parent), before)

    def test_padre_alterado_antes_reserva_no_invoca_exec(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure()
        original = planner.invoke_read_only
        def damaged(*args, **kwargs):
            (parent / "propuesta.md").write_text("alterada")
            return original(*args, **kwargs)
        before = len(self.calls_read())
        with patch.object(planner, "invoke_read_only", side_effect=damaged):
            result = self.continue_plan(parent, answers)
        self.assert_failure(result, "integridad", 0)
        self.assertEqual(self.calls_read()[before:], [["--version"], ["exec", "--help"]])

    def test_argumentos_exclusivos_y_exportacion_cli(self):
        for args in (["--from-plan", "origen"], ["--answers", "a"], ["--answers-template", "a"],
                     ["nuevo", "--from-plan", "o", "--answers", "a"],
                     ["--from-plan", "o", "--answers", "a", "--answers-template", "b"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                planner.main(args, project_root=self.root)
            self.assertEqual(exc.exception.code, 2)
        parent = self.origin()
        target = self.tmp / "exportada.json"
        out, err = io.StringIO(), io.StringIO()
        args = ["--from-plan", str(parent), "--answers-template", str(target)]
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(planner.main(args, project_root=self.root), 0)
            self.assertEqual(planner.main(args, project_root=self.root), 1)
        self.assertIn("Sin invocación ni reserva", out.getvalue())
        self.assertIn("Fallo de plantilla", err.getvalue())

    def test_plantilla_no_escribe_dentro_de_ningun_registro_ni_sigue_destino(self):
        parent = self.origin()
        before = tree_state(parent)
        with self.assertRaises(ValueError):
            continuity.export_template(parent, parent / "nueva.json")
        external = self.tmp / "existente.json"
        external.write_text("no sobrescribir")
        link = self.tmp / "enlace.json"
        link.symlink_to(external)
        with self.assertRaises(FileExistsError):
            continuity.export_template(parent, link)
        self.assertEqual(external.read_text(), "no sobrescribir")
        self.assertEqual(tree_state(parent), before)

    def test_entradas_no_regulares_y_limite_real_respuestas(self):
        parent = self.origin()
        target = self.tmp / "respuestas"
        with target.open("wb") as stream:
            stream.truncate(continuity.MAX_ANSWERS + 1)
        with patch.object(planner, "invoke_read_only") as invoke:
            self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
            target.unlink()
            os.mkfifo(target)
            self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
            target.unlink()
            target.symlink_to(parent / "propuesta.json")
            self.assert_failure(self.continue_plan(parent, target), "error_controlador", 0)
            invoke.assert_not_called()

    def test_estructuras_corruptas_se_rechazan_sin_excepcion_no_controlada(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        path = parent / "resultado.json"
        original = path.read_bytes()
        for key, value in (("planificador", None), ("artefactos_sha256", []),
                           ("integridad", []), ("version", True)):
            data = json.loads(original)
            data[key] = value
            path.write_bytes(continuity.encoded(data))
            with self.subTest(key=key), patch.object(planner, "invoke_read_only") as invoke:
                self.assert_failure(self.continue_plan(parent, answers), "error_controlador", 0)
                invoke.assert_not_called()
        path.write_bytes(original)

    def test_ciclo_y_pendientes_alteradas_en_revision_no_se_admiten(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure()
        child = Path(self.continue_plan(parent, answers)["registro"])
        path = child / "propuesta.json"
        original = path.read_bytes()
        for alteration in ("ciclo", "pendientes", "profundidad"):
            data = json.loads(original)
            if alteration == "ciclo":
                data["continuacion"]["padre"]["registro"] = str(child)
            elif alteration == "profundidad":
                data["continuacion"]["profundidad"] = 9
            else:
                data["continuacion"]["preguntas_pendientes"] = []
            path.write_bytes(continuity.encoded(data))
            self.rehash(child)
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                continuity.load_parent(child)

    def test_continuacion_cli_y_timeout_no_reintenta(self):
        parent = self.origin()
        answers = self.answers(parent, "Consultar")
        self.configure()
        args = ["--from-plan", str(parent), "--answers", str(answers)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(planner.main(args, project_root=self.root), 0)
        self.configure(mode="timeout")
        original = initial.review_case.run_process
        limits = []
        def shortened(command, cwd, logs, timeout, *args, **kwargs):
            limits.append(timeout)
            return original(command, cwd, logs, 0.3 if "--output-last-message" in command else timeout,
                            *args, **kwargs)
        before = len(self.calls_read())
        with patch.object(initial.review_case, "run_process", side_effect=shortened):
            result = self.continue_plan(parent, answers)
        self.assert_failure(result, "tiempo_agotado", 1)
        self.assertEqual(limits, [10, 10, 300])
        self.assertEqual(len(self.calls_read()) - before, 3)
        self.assertFalse(Path(json.loads((self.tmp / "contexto_visto.json").read_bytes())["workspace"]).exists())


if __name__ == "__main__":
    unittest.main()

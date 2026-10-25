"""Cadenas sintéticas escritas localmente; ni fixtures privadas ni procesos de agentes."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unittest
from unittest.mock import patch

from case_evidence import digest
import prepare_project as prepare
import project_plan as plan_data
import project_plan_continuation as continuity
import project_task_config as task_config


ROOT = Path(__file__).resolve().parents[1]
BASE = "53f88b39ee0ac47644708ee1538546eec29382a9"


def documented_json(name):
    text = (ROOT / "docs/ejemplos-v1.1" / name).read_text(encoding="utf-8")
    return [json.loads(raw) for raw in re.findall(r"```json\n(.*?)\n```", text, re.S)]


def concrete():
    return copy.deepcopy(documented_json("01-completo.md")[0])


def synthetic_record(path, plan=None, *, parent=None, answers=None, decisions=None,
                     version=1, references=None, legacy=False, request=None):
    """Construir evidencia ficticia completa, sin ejecutar planificador, Git o modelos.

    Las reservas/resultados son datos sintéticos para el lector, nunca invocaciones.
    answers/decisions contienen solo aportaciones explícitas de cada escenario.
    """
    path = Path(path).absolute()
    path.mkdir()
    plan = concrete() if plan is None else copy.deepcopy(plan)
    if parent is not None:
        parent = continuity.load_parent(parent)
        materials = {key: raw for key, raw in parent.materials.items() if key != "continuacion.json"}
    else:
        restrictions = copy.deepcopy(plan_data.RESTRICTIONS)
        # Simular un contexto anterior a v1.1, sin reescribirlo al exportar.
        restrictions["infraestructura_protegida"].remove("prepare_project.py")
        context = {"commit_base": BASE, "inventario_python": [
            {"ruta": "booking_batch.py", "tipo": "archivo", "protegido": False}],
            "restricciones": restrictions}
        materials = {"solicitud.txt": (request or "Solicitud sintetica explicita; no ejecucion real.").encode("utf-8"),
                     "instrucciones.md": b"Instrucciones sinteticas archivadas; no ejecutar.",
                     "respuesta.schema.json": continuity.encoded(plan_data.response_schema())}
        if references is not None:
            context["restricciones"]["contexto"] = (
                "Inventario y referencias explícitas del commit base; sin cambios pendientes del workspace.")
            documents = []
            for name, content in references:
                raw = content.encode("utf-8")
                documents.append({"ruta": name, "commit": BASE, "modo": 420,
                                  "bytes": len(raw), "sha256": digest(raw), "contenido": content})
            materials["referencias.json"] = continuity.encoded({"version": 1, "archivos": documents})
            context["referencias"] = [{key: item[key] for key in plan_data.REFERENCE_FIELDS} for item in documents]
        materials["contexto.json"] = continuity.encoded(context)
    raw = continuity.encoded(plan)
    request = materials["solicitud.txt"].decode("utf-8")
    proposal = {"version": version, "tipo": "propuesta_planificacion", "estado": plan_data.plan_state(plan),
                "solicitud_original": request, "commit_base": BASE, "propuesta": plan,
                "procedencia": {"rol": "planificador", "registro": path.name,
                                "respuesta_sha256": digest(raw), "requiere_revision_humana": True}}
    blobs = {"planificador/respuesta_original.txt": raw}
    provenance = {"rol": "planificador", "commit_base": BASE,
                  "solicitud_sha256": digest(materials["solicitud.txt"])}
    if parent is not None:
        answer_raw = decision_raw = None
        if answers is not None:
            value = continuity.template(parent)
            for item in value["respuestas"]:
                item["respuesta"] = answers.get(item["id"], "")
            answer_raw = blobs["respuestas_usuario.json"] = continuity.encoded(value)
        if decisions is not None:
            value = continuity.decisions_template(parent)
            for item in value["decisiones"]:
                if item["id"] in decisions:
                    item["decision"], item["explicacion"], item["alternativa"] = decisions[item["id"]]
            decision_raw = blobs["decisiones_usuario.json"] = continuity.encoded(value)
        meta = continuity.continuation_data(parent, answer_raw, decision_raw, version=version - 1)
        materials["continuacion.json"] = continuity.encoded(continuity.model_data(parent, meta))
        pending = continuity.questions(plan, meta["profundidad"], meta["pendientes_anteriores"])
        proposal["continuacion"] = dict(meta, preguntas_pendientes=pending)
        if version == 3:
            pending_assumptions = continuity.assumptions(plan, meta["profundidad"], meta["supuestos_anteriores"])
            proposal["continuacion"]["supuestos_pendientes"] = pending_assumptions
            if pending_assumptions:
                proposal["estado"] = "necesita_aclaraciones"
        if pending:
            proposal["estado"] = "necesita_aclaraciones"
        provenance.update(continuacion=meta, controlador={
            "commit": "1" * 40, "fuentes_sha256": {
                name: digest(("fuente ficticia: " + name).encode()) for name in continuity.CONTROLLER_SOURCES}})
    if legacy:
        prompt = materials["instrucciones.md"] + b"\nLee solicitud.txt y contexto.json. Devuelve solo el JSON del esquema.\n"
    else:
        prompt = continuity.encoded({"instrucciones": materials["instrucciones.md"].decode(),
            "materiales": {key: raw.decode("utf-8") for key, raw in materials.items() if key != "instrucciones.md"}})
    provenance.update(prompt_sha256=digest(prompt), materiales={
        name: {"tipo": "archivo", "sha256": digest(raw), "modo": 420} for name, raw in materials.items()})
    blobs.update({"propuesta.json": continuity.encoded(proposal),
                  "propuesta.md": plan_data.render_proposal(proposal).encode(),
                  "procedencia.json": continuity.encoded(provenance), "planificador/entrada.txt": prompt,
                  "reserva.json": continuity.encoded({"rol": "planificador", "numero": 1, "limite_segundos": 300})})
    blobs.update({"materiales/" + name: raw for name, raw in materials.items()})
    result = {"version": 1, "tipo": "planificacion_proyecto", "rol": "planificador", "codigo_salida": 0,
              "fallo": None, "aprobada": False, "registro": str(path), "commit_base": BASE,
              "commit_controlador": "1" * 40, "solicitud_original": request, "estado": proposal["estado"],
              "invocaciones": {"planificador": 1}, "limite_segundos": 300, "respuesta_tipo": "regular",
              "planificador": {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1},
              "integridad": dict.fromkeys(("proyecto_intacto", "base_intacta", "materiales_intactos", "workspace_intacto"), True),
              "artefactos_sha256": {name: digest(raw) for name, raw in blobs.items()}}
    blobs["resultado.json"] = continuity.encoded(result)
    for name, raw in blobs.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o644)
    continuity.load_parent(path)  # Las fixtures pasan por el lector real, sin procesos.
    return path


def documented_records(directory):
    """Los dos escenarios de la guía, reutilizables para una demo local sintética."""
    directory = Path(directory)
    def request(name):
        text = (ROOT / "docs/ejemplos-v1.1" / name).read_text(encoding="utf-8")
        return re.search(r"Solicitud original: «(.*?)»", text, re.S).group(1).replace("\n", " ")
    complete = synthetic_record(directory / "completo", request=request("01-completo.md"))
    values = documented_json("02-pendientes.md")
    current = next(value for value in values if "objetivo" in value)
    original = copy.deepcopy(current)
    original.update(preguntas_pendientes=["¿Qué nombre tendrá la función privada?"], supuestos=[
        "Se puede admitir BOM al leer UTF-8.",
        "La función privada devolverá la lista y propagará las excepciones."])
    references = [(name, (ROOT / name).read_text(encoding="utf-8")) for name in
                  ("booking_batch.py", "tasks/008-booking-batch.md")]
    origin = synthetic_record(directory / "pendiente-r0", original, references=references,
                              request=request("02-pendientes.md"))
    child = synthetic_record(directory / "pendiente-r1", current, parent=origin, version=3,
        decisions={"r0:s1": ("rechazar", "Conservar el rechazo de BOM del contrato 008.", "")})
    return complete, child


def snapshot(path):
    return {str(p.relative_to(path)): (stat.S_IMODE(p.lstat().st_mode), p.read_bytes())
            for p in path.rglob("*") if p.is_file()}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="preparacion-sintetica-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "proyecto"
        self.root.mkdir()
        self.source = synthetic_record(self.root / "original")
        self.output = self.tmp / "paquete"

    def call(self, source=None, destination=None, *, args=None, project_root=None):
        out, err = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            for name in ("subprocess.Popen", "subprocess.run", "os.system", "os.fork",
                         "os.posix_spawn", "os.posix_spawnp", "socket.socket"):
                stack.enter_context(patch(name, side_effect=AssertionError("Proceso no permitido")))
            stack.enter_context(redirect_stdout(out))
            stack.enter_context(redirect_stderr(err))
            try:
                code = prepare.main(args if args is not None else ["--from-plan", str(source or self.source),
                    "--output", str(destination or self.output)], project_root=project_root or self.root)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_completo_sin_procesos_reservas_y_no_ejecutable(self):
        (self.root / ".git").mkdir()
        (self.root / ".git/HEAD").write_text("NO CONSULTAR\n")
        (self.root / "contar_etiquetas.py").write_text("raise AssertionError('NO IMPORTAR')\n")
        before = snapshot(self.root)
        code, out, err = self.call()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("no ejecutable", out)
        self.assertEqual(set(p.name for p in self.output.iterdir()),
                         {"contrato.borrador.md", "configuracion.borrador.json", "revision.md"})
        self.assertEqual(snapshot(self.root), before)
        draft = json.loads((self.output / "configuracion.borrador.json").read_bytes())
        self.assertEqual(draft["derivado"]["archivos_propuestos"][0]["estado_inicial_segun_inventario"], "ausente")
        with self.assertRaises(ValueError):
            task_config.validate_document(draft)
        self.assertFalse(draft["ejecutable"])
        review = (self.output / "revision.md").read_text()
        for path, (mode, size, sha) in continuity.load_parent(self.source).identities.items():
            self.assertIn(sha, review)
            self.assertIn(str(size), review)
        self.assertIn("No se ha ejecutado ninguna evaluación", review)
        self.assertIn("refactorización", review)

    def test_ejemplos_documentados_contrato_configuracion_y_diagnostico(self):
        complete, pending = documented_records(self.tmp)
        self.assertEqual(self.call(complete)[0], 0)
        documentation = (ROOT / "docs/ejemplos-v1.1/01-completo.md").read_text()
        contract = re.search(r"```markdown\n(.*?)\n```", documentation, re.S).group(1) + "\n"
        self.assertEqual((self.output / "contrato.borrador.md").read_text(), contract)
        self.assertEqual(json.loads((self.output / "configuracion.borrador.json").read_bytes()),
                         documented_json("01-completo.md")[1])
        target = self.tmp / "diagnostico"
        self.assertEqual(self.call(pending, target)[0], 3)
        self.assertEqual([p.name for p in target.iterdir()], ["revision.md"])
        review = (target / "revision.md").read_text()
        for value in ("r0:p1", "r0:s2", "r0:s1", "rechazar", "booking_batch.py", "coincidente con un editable"):
            self.assertIn(value, review)
        self.assertEqual(continuity.load_parent(pending).answers, [])
        for document, destination in (("01-completo.md", self.output), ("02-pendientes.md", target)):
            text = (ROOT / "docs/ejemplos-v1.1" / document).read_text()
            prefix = re.search(r"<!-- revision:inicio -->\n```markdown\n(.*?)\n```", text, re.S).group(1)
            self.assertTrue((destination / "revision.md").read_text().startswith(prefix + "\n"))

    def test_v1_legacy_y_moderno_v2_v3_completos(self):
        for index, version in enumerate((1, 1, 2, 3)):
            with self.subTest(version=version, legacy=index == 0):
                if version == 1:
                    source = synthetic_record(self.tmp / f"r-{index}", legacy=index == 0)
                else:
                    plan = concrete()
                    plan["preguntas_pendientes"] = ["¿Confirmar dominio?"]
                    origin = synthetic_record(self.tmp / f"padre-{index}", plan)
                    source = synthetic_record(self.tmp / f"r-{index}", parent=origin, version=version,
                                              answers={"r0:p1": "Solo listas de cadenas."})
                before = snapshot(source)
                self.assertEqual(self.call(source, self.tmp / f"salida-{index}")[0], 0)
                self.assertEqual(snapshot(source), before)

    def test_v2_borrador_con_supuesto_heredado_no_reclasifica_origen(self):
        plan = concrete()
        plan.update(preguntas_pendientes=["¿Pregunta?"], supuestos=["Supuesto sin decidir."])
        origin = synthetic_record(self.tmp / "r0", plan)
        source = synthetic_record(self.tmp / "r1", parent=origin, version=2, answers={"r0:p1": "Respuesta."})
        before = snapshot(self.tmp)
        self.assertEqual(continuity.load_parent(source).proposal["estado"], "borrador")
        self.assertEqual(self.call(source)[0], 3)
        self.assertEqual(continuity.load_parent(source).proposal["estado"], "borrador")
        for name, value in before.items():
            self.assertEqual(snapshot(self.tmp)[name], value)

    def test_decisiones_respuestas_y_texto_literal_acumulados(self):
        plan = concrete()
        plan.update(preguntas_pendientes=["¿Una?", "¿Otra?"], supuestos=["Primero", "Segundo", "Tercero", "Cuarto"])
        origin = synthetic_record(self.tmp / "r0", plan)
        text = '  texto "ñ" 📅\r\n# NO ACTIVAR\n[x](https://example.invalid)\n```\n'
        source = synthetic_record(self.tmp / "r1", parent=origin, version=3, answers={"r0:p1": text},
            decisions={"r0:s1": ("aceptar", "", ""), "r0:s2": ("rechazar", text, ""),
                       "r0:s3": ("corregir", "", text)})
        plan = concrete()
        plan["objetivo"] = text
        plan["criterios_aceptacion"][0]["ejemplos"][0]["entrada"] = ""
        final = synthetic_record(self.tmp / "r2", plan, parent=source, version=3,
            answers={"r0:p2": "Respuesta posterior"}, decisions={"r0:s4": ("aceptar", "", "")})
        self.assertEqual(self.call(final)[0], 0)
        parent = continuity.load_parent(final)
        review = (self.output / "revision.md").read_text()
        self.assertIn(prepare.literal(parent.decisions), review)
        self.assertEqual(len(parent.answers), 2)
        self.assertEqual(len(parent.decisions), 4)
        self.assertNotIn("\n# NO ACTIVAR", review)
        contract = (self.output / "contrato.borrador.md").read_text()
        self.assertIn(prepare.literal(text), contract)
        self.assertIn('    ""\n', contract)
        goal = contract.split("## Objetivo\n\n", 1)[1].split("## Requisitos", 1)[0].strip()
        self.assertEqual(json.loads(goal), text)
        self.assertNotRegex(contract, r"(?m)^\[x\]\(")

    def test_referencias_orden_base_ausencias_y_colisiones(self):
        refs = [("booking_batch.py", "# Fuente histórica\r\n"), ("docs/vacia.md", ""),
                ("repair_case.py", "# Referencia a utilidad, nunca editable"),
                ("tasks/antigua.md", "Base: `" + "2" * 40 + "`\n")]
        plan = concrete()
        plan["archivos"] = [{"ruta": "booking_batch.py", "accion": "modificar", "proposito": "Refactorizar."}]
        plan["exclusiones"] = []
        source = synthetic_record(self.tmp / "ref", plan, references=refs)
        parent = continuity.load_parent(source)
        self.assertEqual(self.call(source)[0], 0)
        draft = json.loads((self.output / "configuracion.borrador.json").read_bytes())
        self.assertEqual(draft["derivado"]["referencias_planificacion"], json.loads(parent.materials["contexto.json"])["referencias"])
        self.assertEqual(draft["derivado"]["commit_base"], BASE)
        self.assertIsNone(draft["por_decidir"]["referencias"])
        review = (self.output / "revision.md").read_text()
        for value in ("coincidente con un editable", "Nombre reservado", "Referencia vac", "No se ha ejecutado"):
            self.assertIn(value, review)
        self.assertIn("No consta en el plan", (self.output / "contrato.borrador.md").read_text())
        self.assertTrue(parent.intact())

    def test_profundidad_ocho_sin_crear_novena_revision(self):
        plan = concrete()
        plan["preguntas_pendientes"] = [f"¿Pregunta {i}?" for i in range(8)]
        source = synthetic_record(self.tmp / "r0", plan)
        for index in range(1, 9):
            source = synthetic_record(self.tmp / f"r{index}", parent=source, version=3,
                                      answers={f"r0:p{index}": f"Respuesta {index}"})
        self.assertEqual(continuity.load_parent(source).depth, 8)
        self.assertEqual(self.call(source)[0], 0)
        self.assertEqual(len(list(self.tmp.glob("r[0-9]"))), 9)

    def test_viabilidad_insuficiente_y_pendientes_solo_diagnostico(self):
        for index, viability in enumerate(("pendiente_de_aclaracion", "fuera_del_alcance", "dentro_del_alcance")):
            plan = concrete()
            plan["viabilidad"] = viability
            if viability == "fuera_del_alcance":
                plan["archivos"] = []
            elif viability == "pendiente_de_aclaracion":
                plan["preguntas_pendientes"] = ["¿Qué interfaz?"]
            else:
                plan["supuestos"] = ["Por decidir."]
            source = synthetic_record(self.tmp / f"r{index}", plan)
            target = self.tmp / f"salida{index}"
            self.assertEqual(self.call(source, target)[0], 3)
            self.assertEqual([p.name for p in target.iterdir()], ["revision.md"])

    def test_argumentos_vacios_repetidos_desconocidos_y_ayuda_sin_lecturas(self):
        invalid = [[], ["--from-plan", "", "--output", "y"],
                   ["--from-plan", "  ", "--output", "y"], ["--from-plan", "x", "--output", ""],
                   ["--from-plan", "x", "--output", "  "],
                   ["--from-plan", "x", "--output", "\0"], ["--from", "x", "--output", "y"],
                   ["--from-plan", "x", "--output", "y", "--force"],
                   ["--from-plan", "x", "--from-plan", "z", "--output", "y"],
                   ["--from-plan", "x", "--output", "y", "--output", "z"]]
        with patch.object(prepare, "load_parent", side_effect=AssertionError("No leer")):
            for args in invalid:
                with self.subTest(args=args):
                    self.assertEqual(self.call(args=args)[0], 2)
            self.assertEqual(self.call(args=["--help"])[0], 0)

    def test_origen_invalido_sin_destino(self):
        for index, mutation in enumerate(("missing", "hash", "markdown", "symlink", "fifo", "json")):
            with self.subTest(mutation=mutation):
                source = synthetic_record(self.tmp / f"r{index}")
                path = source / "propuesta.md"
                if mutation == "missing":
                    path.unlink()
                elif mutation in ("hash", "markdown"):
                    path.write_text("alterado")
                    if mutation == "markdown":
                        result = json.loads((source / "resultado.json").read_bytes())
                        result["artefactos_sha256"]["propuesta.md"] = digest(path.read_bytes())
                        (source / "resultado.json").write_bytes(continuity.encoded(result))
                elif mutation == "symlink":
                    path.unlink()
                    path.symlink_to(self.source / "propuesta.md")
                elif mutation == "fifo":
                    path.unlink()
                    os.mkfifo(path)
                else:
                    (source / "resultado.json").write_text('{"version": 1, "version": 1}')
                self.assertEqual(self.call(source)[0], 1)
                self.assertFalse(self.output.exists())

    def test_limites_del_lector_se_mantienen(self):
        for name, value in (("MAX_FILE", 1), ("MAX_CHAIN_BYTES", 1), ("MAX_ARTIFACTS", 1)):
            with self.subTest(name=name), patch.object(continuity, name, value):
                self.assertEqual(self.call()[0], 1)
                self.assertFalse(self.output.exists())

    def test_destinos_existentes_se_conservan_incluidos_enlaces_rotos(self):
        for index, kind in enumerate(("archivo", "directorio", "enlace", "roto")):
            target = self.tmp / f"destino{index}"
            if kind == "archivo":
                target.write_bytes(b"conservar")
            elif kind == "directorio":
                target.mkdir()
            else:
                target.symlink_to(self.source if kind == "enlace" else self.tmp / "inexistente")
            before = target.lstat()
            self.assertEqual(self.call(destination=target)[0], 1)
            self.assertEqual(target.lstat(), before)

    def test_padres_ausentes_no_directorios_enlaces_y_rutas_excluidas(self):
        (self.tmp / "enlace").symlink_to(self.root, target_is_directory=True)
        (self.tmp / "archivo").write_text("conservar")
        for name in ("tasks", "evals", "prompts", "runs", ".git", ".oculto"):
            (self.root / name).mkdir()
        destinations = [self.tmp / "ausente/nuevo", self.tmp / "archivo/nuevo", self.tmp / "enlace/nuevo",
                        self.tmp / "enlace/../nuevo", self.source / "nuevo", self.root]
        destinations += [self.root / name / "nuevo" for name in ("tasks", "evals", "prompts", "runs", ".git", ".oculto")]
        before = snapshot(self.root)
        for target in destinations:
            with self.subTest(target=target):
                self.assertEqual(self.call(destination=target)[0], 1)
        self.assertEqual(snapshot(self.root), before)

    def test_solapamiento_con_ancestro_y_directorio_superior(self):
        plan = concrete()
        plan["preguntas_pendientes"] = ["¿Pregunta?"]
        origin = synthetic_record(self.tmp / "padre", plan)
        child = synthetic_record(self.tmp / "hijo", parent=origin, version=3, answers={"r0:p1": "Sí"})
        for target in (origin / "salida", origin, self.tmp):
            self.assertEqual(self.call(child, target)[0], 1)

    def test_doble_barra_inicial_no_elude_autoridades_ni_solapamientos(self):
        (self.root / "tasks").mkdir()
        for target in (self.root / "tasks/salida", self.source / "salida"):
            with self.subTest(target=target):
                self.assertEqual(self.call(destination="/" + str(target))[0], 1)
                self.assertFalse(target.exists())

    def test_raiz_explicita_no_depende_del_cwd_y_permite_destino_externo(self):
        external = self.tmp / "tasks"
        external.mkdir()
        self.assertEqual(self.call(destination=external / "salida")[0], 0)
        previous = Path.cwd()
        try:
            os.chdir(self.tmp)
            (self.root / "docs").mkdir()
            self.assertEqual(self.call(args=["--from-plan", "proyecto/original", "--output", "proyecto/docs/salida"])[0], 0)
        finally:
            os.chdir(previous)

    def test_origen_alterado_antes_y_despues_de_escribir(self):
        for index, stage in enumerate(("antes", "despues")):
            source = synthetic_record(self.tmp / f"r{index}")
            original = prepare.revision if stage == "antes" else prepare.write_exclusive
            def change(*args):
                result = original(*args)
                (source / "materiales/solicitud.txt").write_text("alteración externa")
                return result
            with patch.object(prepare, "revision" if stage == "antes" else "write_exclusive", side_effect=change):
                self.assertEqual(self.call(source)[0], 1)
            self.assertFalse(self.output.exists())

    def test_fallos_de_escritura_parcial_y_por_archivo_limpian_solo_lo_propio(self):
        original = prepare.write_exclusive
        before = snapshot(self.root)
        for fail in ("contrato.borrador.md", "configuracion.borrador.json", "revision.md"):
            def failing(fd, name, raw, created):
                if name == fail:
                    real_write = os.write
                    calls = 0
                    def partial(output, data):
                        nonlocal calls
                        calls += 1
                        if calls == 1:
                            return real_write(output, data[:7])
                        raise OSError("Disco lleno simulado")
                    with patch.object(os, "write", side_effect=partial):
                        original(fd, name, raw, created)
                else:
                    original(fd, name, raw, created)
            with patch.object(prepare, "write_exclusive", side_effect=failing):
                code, out, err = self.call()
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn("No hay cierre válido", err)
            self.assertFalse(self.output.exists())
        self.assertEqual(snapshot(self.root), before)

    def test_colision_exclusiva_interrupcion_y_contenido_ajeno_no_se_borran(self):
        original = prepare.write_exclusive
        def collision(fd, name, raw, created):
            if name == "configuracion.borrador.json":
                (self.output / name).write_bytes(b"AJENO")
            original(fd, name, raw, created)
        with patch.object(prepare, "write_exclusive", side_effect=collision):
            self.assertEqual(self.call()[0], 1)
        self.assertEqual([p.name for p in self.output.iterdir()], ["configuracion.borrador.json"])
        self.assertEqual((self.output / "configuracion.borrador.json").read_bytes(), b"AJENO")
        self.assertEqual(self.call()[0], 1)  # Un resto incompleto nunca se reutiliza.
        second = self.tmp / "interrumpido"
        def interrupt(fd, name, raw, created):
            original(fd, name, raw, created)
            (second / name).write_bytes(b"EDITADO POR OTRO")
            raise KeyboardInterrupt()
        with patch.object(prepare, "write_exclusive", side_effect=interrupt):
            self.assertEqual(self.call(destination=second)[0], 1)
        self.assertEqual((second / "contrato.borrador.md").read_bytes(), b"EDITADO POR OTRO")

    def test_interrupcion_sin_cambios_ajenos_limpia(self):
        original = prepare.write_exclusive
        def interrupt(*args):
            original(*args)
            raise KeyboardInterrupt()
        with patch.object(prepare, "write_exclusive", side_effect=interrupt):
            self.assertEqual(self.call()[0], 1)
        self.assertFalse(self.output.exists())

    def test_sustitucion_de_destino_y_edicion_externa_no_se_publican(self):
        original = prepare.write_exclusive
        def replace(fd, name, raw, created):
            original(fd, name, raw, created)
            if name == "revision.md":
                target = self.output / "contrato.borrador.md"
                target.unlink()
                target.symlink_to(self.source / "propuesta.md")
        before = snapshot(self.root)
        with patch.object(prepare, "write_exclusive", side_effect=replace):
            self.assertEqual(self.call()[0], 1)
        self.assertTrue((self.output / "contrato.borrador.md").is_symlink())
        self.assertFalse((self.output / "revision.md").exists())
        self.assertEqual(snapshot(self.root), before)

    def test_sustitucion_del_padre_por_enlace_no_escribe_fuera(self):
        enclosing = self.tmp / "contenedor"
        enclosing.mkdir()
        foreign = self.tmp / "ajeno"
        foreign.mkdir()
        moved = self.tmp / "movido"
        original = prepare.write_exclusive
        def move(fd, name, raw, created):
            original(fd, name, raw, created)
            if name == "contrato.borrador.md":
                enclosing.rename(moved)
                enclosing.symlink_to(foreign, target_is_directory=True)
        with patch.object(prepare, "write_exclusive", side_effect=move):
            self.assertEqual(self.call(destination=enclosing / "salida")[0], 1)
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertFalse((moved / "salida").exists())

    def test_proteccion_de_infraestructura_y_reservas_coincide_con_motor(self):
        import project_flow
        self.assertEqual(prepare.RESERVED_MATERIALS, set(project_flow.SUPPORT) | {"project_test_inventory.py"})
        self.assertIn("prepare_project.py", task_config.PROTECTED)
        plan = concrete()
        plan["archivos"][0]["ruta"] = "prepare_project.py"
        context = json.loads(continuity.load_parent(self.source).materials["contexto.json"])
        with self.assertRaisesRegex(ValueError, "Infraestructura protegida"):
            plan_data.validate_response(continuity.encoded(plan), context)


if __name__ == "__main__":
    unittest.main()

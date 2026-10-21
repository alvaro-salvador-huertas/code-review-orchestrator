"""Una planificación de solo lectura; nunca encadena el motor de proyectos."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from case_evidence import digest, read_regular, require
from project_plan import (MAX_REQUEST, base_context, plan_state, render_proposal,
                          response_schema, validate_response)
from project_plan_continuation import (CONTROLLER_SOURCES, MAX_ANSWERS, MAX_MESSAGE, continuation_data,
                                      assumptions, encoded, export_template, load_parent, model_data,
                                      questions, regular_bytes)
from project_task_config import git
from repair_case import ProcessInterrupted, timestamp, write_json
from repair_project import tree_state
from review_case import invoke_reviewer as invoke_read_only


PROJECT = Path(__file__).resolve().parent
PROMPT = PROJECT / "prompts/planner_project.md"
PLANNING_SECONDS = 300


class PlanningFailure(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def request_text(value):
    if not value.strip() or len(value) > MAX_REQUEST or "\0" in value:
        raise argparse.ArgumentTypeError("La solicitud debe contener entre 1 y 16000 caracteres, sin NUL.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise argparse.ArgumentTypeError("La solicitud debe ser texto representable en UTF-8.") from exc
    return value


def error_text(error):
    """Los diagnósticos también pueden contener datos JSON rechazados."""
    return str(error).encode("utf-8", errors="backslashreplace").decode("utf-8")


def process_failure(agent):
    if agent.get("error_registro"):
        return "error_registro"
    if agent["estado"] == "tiempo_agotado":
        return "tiempo_agotado"
    if agent["estado"] == "cli_incompatible":
        return "cli_incompatible"
    if agent["estado"] in ("ausente", "error_inicio"):
        return "cli_no_disponible"
    if agent["estado"] == "cli_no_disponible":
        checks = [agent[key] for key in ("version", "ayuda") if key in agent]
        return ("cli_no_disponible" if any(c["estado"] in ("ausente", "error_inicio") for c in checks)
                else "fallo_proceso")
    if agent["estado"] != "finalizada" or agent["codigo_salida"] != 0:
        return "fallo_proceso"
    return None


def run_plan(request, project_root=PROJECT, *, from_plan=None, answers=None, decisions=None):
    started = time.monotonic()
    root = Path(project_root).resolve()
    log = None
    result = {"version": 1, "tipo": "planificacion_proyecto", "rol": "planificador",
              "estado": "preparando", "codigo_salida": 1, "inicio_utc": timestamp(),
              "registro": None, "commit_base": None, "solicitud_original": request,
              "invocaciones": {"planificador": 0}, "limite_segundos": PLANNING_SECONDS,
              "planificador": {"estado": "no_ejecutado", "codigo_salida": None, "invocaciones": 0},
              "integridad": {}, "fallo": None, "aprobada": False}

    def save():
        write_json(log / "resultado.json", result)

    def discard_proposal():
        if log is not None:
            for name in ("propuesta.json", "propuesta.md"):
                (log / name).unlink(missing_ok=True)

    try:
        parent = None
        if from_plan is not None:
            require(request is None and (answers is not None or decisions is not None),
                    "Continuación exige origen y respuestas o decisiones, sin solicitud nueva")
            parent = load_parent(from_plan)
            answers_raw = regular_bytes(answers, MAX_ANSWERS) if answers is not None else None
            decisions_raw = regular_bytes(decisions, MAX_ANSWERS) if decisions is not None else None
            continuation = continuation_data(parent, answers_raw, decisions_raw)
            request = parent.proposal["solicitud_original"]
            result["solicitud_original"] = request
        else:
            require(answers is None and decisions is None, "Respuestas y decisiones requieren --from-plan")
        request_text(request)
        runs = root / "runs"
        require(not runs.is_symlink(), "runs no puede ser un enlace")
        runs.mkdir(exist_ok=True)
        candidate_log = runs / (result["inicio_utc"].replace(":", "") + "_plan_project_" + uuid4().hex)
        candidate_log.mkdir()  # exclusivo; nunca reutilizar ni sobrescribir un registro
        log = candidate_log
        result["registro"] = str(log)
        archive = log / "materiales"
        archive.mkdir()
        agent_log = log / "planificador"
        agent_log.mkdir()
        for name in ("eventos.jsonl", "stderr.txt", "respuesta_original.txt", "codex_version.txt"):
            (agent_log / name).write_bytes(b"")
        (archive / "solicitud.txt").write_text(request, encoding="utf-8")
        save()
        before = tree_state(root, filter_local=True)
        controller_commit = git(root, "rev-parse", "HEAD^{commit}").decode().strip()
        context = json.loads(parent.materials["contexto.json"]) if parent else base_context(root)
        result["commit_base"] = context["commit_base"]
        result["commit_controlador"] = controller_commit
        instructions = read_regular(PROMPT)
        require(instructions is not None and instructions.strip(), "Faltan instrucciones de planificación")
        materials = {
            "solicitud.txt": request.encode("utf-8"),
            "contexto.json": (json.dumps(context, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "respuesta.schema.json": (json.dumps(response_schema(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "instrucciones.md": instructions,
        }
        if parent:
            # Mantener incluso la representación exacta del contexto histórico.
            for name in ("solicitud.txt", "contexto.json"):
                materials[name] = parent.materials[name]
            materials["continuacion.json"] = encoded(model_data(parent, continuation))
            for name, raw_input in (("respuestas_usuario.json", answers_raw), ("decisiones_usuario.json", decisions_raw)):
                if raw_input is not None:
                    (log / name).write_bytes(raw_input)
        for name, raw in materials.items():
            (archive / name).write_bytes(raw)
        expected = tree_state(archive)
        # Los textos archivados viajan completos: no requieren herramientas de lectura.
        prompt = (json.dumps({
            "instrucciones": materials["instrucciones.md"].decode("utf-8"),
            "materiales": {name: raw.decode("utf-8") for name, raw in materials.items()
                           if name != "instrucciones.md"},
        }, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        require(len(prompt) <= MAX_MESSAGE, "Mensaje de planificación supera 4 MiB")
        (agent_log / "entrada.txt").write_bytes(prompt)
        write_json(log / "proyecto_antes.json", before)
        write_json(log / "procedencia.json", {
            "rol": "planificador", "commit_base": context["commit_base"],
            "solicitud_sha256": digest(request.encode("utf-8")),
            "materiales": expected, "prompt_sha256": digest(prompt),
            "python": sys.version, "politica_entorno": "codex",
            "controlador": {"commit": controller_commit, "fuentes_sha256": {
                name: digest(read_regular(PROJECT / name)) for name in CONTROLLER_SOURCES}},
            "continuacion": continuation if parent else None,
            "nota": "Inventario mínimo de Git, sin fuentes. Directorios y hashes no son un sandbox.",
        })
        temp_root = Path(tempfile.gettempdir()).resolve()
        require(temp_root != root and root not in temp_root.parents,
                "El workspace temporal debe estar fuera del proyecto")
        with tempfile.TemporaryDirectory(prefix="plan-project-", dir=temp_root) as temporary:
            workspace = Path(temporary) / "workspace"
            shutil.copytree(archive, workspace)
            final = Path(temporary) / "respuesta.txt"

            def check_integrity():
                result["integridad"] = {
                    "proyecto_intacto": tree_state(root, filter_local=True) == before,
                    "base_intacta": git(root, "rev-parse", "HEAD^{commit}").decode().strip() == controller_commit,
                    "materiales_intactos": tree_state(archive) == expected,
                    "workspace_intacto": tree_state(workspace) == expected,
                }
                if parent:
                    result["integridad"]["origen_intacto"] = parent.intact()
                if not all(result["integridad"].values()):
                    raise PlanningFailure("integridad", "Cambió el proyecto, la base o los materiales")

            def reserve():
                check_integrity()
                require(result["invocaciones"]["planificador"] == 0, "Presupuesto de planificación agotado")
                reservation = {"rol": "planificador", "numero": 1, "inicio_utc": timestamp(),
                               "limite_segundos": PLANNING_SECONDS}
                with (log / "reserva.json").open("x", encoding="utf-8") as stream:
                    json.dump(reservation, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                result["invocaciones"]["planificador"] = 1
                result["estado"] = "planificando"
                save()  # persistir la reserva antes de entrar en run_process

            raw = None
            try:
                check_integrity()  # también antes de consultar versión/ayuda de la CLI
                result["planificador"] = invoke_read_only(
                    workspace, final, prompt, agent_log, on_invoke=reserve, timeout=PLANNING_SECONDS)
            except ProcessInterrupted as exc:
                result["planificador"] = dict(exc.result, invocaciones=result["invocaciones"]["planificador"])
                raise
            finally:
                raw = read_regular(final)
                result["respuesta_tipo"] = ("regular" if raw is not None else
                                             "no_regular" if final.exists() or final.is_symlink() else "ausente")
                if raw is not None:
                    (agent_log / "respuesta_original.txt").write_bytes(raw)
                check_integrity()
            failure = process_failure(result["planificador"])
            if failure:
                raise PlanningFailure(failure, "No se completó una planificación válida; consultar los canales")
            require(result["invocaciones"]["planificador"] == result["planificador"]["invocaciones"] == 1,
                    "Contabilidad incoherente de planificación")
            try:
                plan = validate_response(raw, context)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise PlanningFailure("respuesta_invalida", str(exc)) from exc
        proposal = {"version": 1, "tipo": "propuesta_planificacion", "estado": plan_state(plan),
                    "solicitud_original": request, "commit_base": context["commit_base"],
                    "procedencia": {"rol": "planificador", "registro": log.name,
                                    "respuesta_sha256": digest(raw), "requiere_revision_humana": True},
                    "propuesta": plan}
        if parent:
            pending = questions(plan, continuation["profundidad"], continuation["pendientes_anteriores"])
            pending_assumptions = assumptions(plan, continuation["profundidad"], continuation["supuestos_anteriores"])
            proposal.update(version=3, continuacion=dict(continuation, preguntas_pendientes=pending,
                                                        supuestos_pendientes=pending_assumptions))
            if pending or pending_assumptions:
                proposal["estado"] = "necesita_aclaraciones"
        # Preparar ambas representaciones en memoria. Ante cualquier fallo de
        # escritura o de registro se eliminan los dos entregables de este run.
        document = json.dumps(proposal, ensure_ascii=False, indent=2) + "\n"
        markdown = render_proposal(proposal)
        with (log / "propuesta.json").open("x", encoding="utf-8") as stream:
            stream.write(document)
        with (log / "propuesta.md").open("x", encoding="utf-8") as stream:
            stream.write(markdown)
        result.update(estado=proposal["estado"], codigo_salida=0)
    except KeyboardInterrupt:
        result.update(estado="fallo_tecnico", codigo_salida=1,
                      fallo={"tipo": "interrumpida", "mensaje": "Planificación interrumpida; sin reintento"})
    except (PlanningFailure, OSError, ValueError, RecursionError, subprocess.SubprocessError) as exc:
        result.update(estado="fallo_tecnico", codigo_salida=1,
                      fallo={"tipo": exc.kind if isinstance(exc, PlanningFailure) else "error_controlador",
                             "mensaje": error_text(exc)})
    finally:
        result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
        result["fase"] = "planificacion" if result["invocaciones"]["planificador"] else "preparacion_o_consulta_cli"
        if result["codigo_salida"]:
            discard_proposal()
        if log is not None:
            try:
                result["artefactos_sha256"] = {
                    str(path.relative_to(log)): digest(read_regular(path))
                    for path in sorted(log.rglob("*")) if path.is_file() and path != log / "resultado.json"}
                save()
            except OSError as exc:
                discard_proposal()
                result.update(estado="fallo_tecnico", codigo_salida=1,
                              fallo={"tipo": "error_registro", "mensaje": error_text(exc)})
    return result


def main(arguments=None, *, project_root=PROJECT):
    parser = argparse.ArgumentParser(
        description="Una planificación con modelo: borrador revisable, sin desarrollo ni ejecución.",
        allow_abbrev=False)
    parser.add_argument("solicitud", nargs="?", type=request_text, help="Descripción del trabajo; una única sesión de planificación")
    parser.add_argument("--from-plan", metavar="REGISTRO", help="Registro validado que se continuará")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--answers-template", metavar="ARCHIVO", help="Exportar plantilla sin invocar modelos ni sobrescribir")
    mode.add_argument("--decisions-template", metavar="ARCHIVO", help="Exportar plantilla de decisiones sobre supuestos")
    parser.add_argument("--answers", metavar="ARCHIVO", help="Respuestas explícitas para una nueva planificación")
    parser.add_argument("--decisions", metavar="ARCHIVO", help="Decisiones explícitas; se puede combinar con --answers")
    args = parser.parse_args(arguments)
    exporting = args.answers_template or args.decisions_template
    continuing = args.answers or args.decisions
    if exporting and continuing:
        parser.error("Exportar una plantilla excluye --answers y --decisions")
    if args.from_plan:
        if args.solicitud is not None or not (exporting or continuing):
            parser.error("--from-plan exige una plantilla, --answers o --decisions y excluye una solicitud nueva")
    elif args.solicitud is None or exporting or continuing:
        parser.error("Indica una solicitud, o --from-plan con una operación de continuidad")
    if exporting:
        try:
            export_template(args.from_plan, exporting, decisions=bool(args.decisions_template))
        except (OSError, ValueError, RecursionError) as exc:
            print("Fallo de plantilla:", error_text(exc), file=sys.stderr)
            return 1
        print("Plantilla:", exporting)
        print("Sin invocación ni reserva; pendiente de completar por el usuario.")
        return 0
    result = run_plan(args.solicitud, project_root, from_plan=args.from_plan, answers=args.answers, decisions=args.decisions)
    stream = sys.stderr if result["codigo_salida"] else sys.stdout
    print("Estado:", result["estado"], file=stream)
    if result["registro"]:
        print("Registro:", result["registro"], file=stream)
    if result["fallo"]:
        print("Fallo:", result["fallo"]["tipo"], "-", result["fallo"]["mensaje"], file=stream)
    else:
        print("Borrador pendiente de revisión humana; no se ha autorizado ni ejecutado desarrollo.", file=stream)
    return result["codigo_salida"]


if __name__ == "__main__":
    sys.exit(main())

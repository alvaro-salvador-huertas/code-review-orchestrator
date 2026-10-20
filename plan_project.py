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


def run_plan(request, project_root=PROJECT):
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
        context = base_context(root)
        result["commit_base"] = context["commit_base"]
        instructions = read_regular(PROMPT)
        require(instructions is not None and instructions.strip(), "Faltan instrucciones de planificación")
        materials = {
            "solicitud.txt": request.encode("utf-8"),
            "contexto.json": (json.dumps(context, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "respuesta.schema.json": (json.dumps(response_schema(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "instrucciones.md": instructions,
        }
        for name, raw in materials.items():
            (archive / name).write_bytes(raw)
        expected = tree_state(archive)
        prompt = instructions + b"\nLee solicitud.txt y contexto.json. Devuelve solo el JSON del esquema.\n"
        (agent_log / "entrada.txt").write_bytes(prompt)
        write_json(log / "proyecto_antes.json", before)
        write_json(log / "procedencia.json", {
            "rol": "planificador", "commit_base": context["commit_base"],
            "solicitud_sha256": digest(request.encode("utf-8")),
            "materiales": expected, "prompt_sha256": digest(prompt),
            "python": sys.version, "politica_entorno": "codex",
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
                    "base_intacta": git(root, "rev-parse", "HEAD^{commit}").decode().strip() == context["commit_base"],
                    "materiales_intactos": tree_state(archive) == expected,
                    "workspace_intacto": tree_state(workspace) == expected,
                }
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
    except (PlanningFailure, OSError, ValueError, subprocess.SubprocessError) as exc:
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
    parser.add_argument("solicitud", type=request_text, help="Descripción del trabajo; una única sesión de planificación")
    args = parser.parse_args(arguments)
    result = run_plan(args.solicitud, project_root)
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

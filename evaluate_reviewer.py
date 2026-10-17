"""Preparar y ejecutar una sola vez cuatro revisiones de candidatos preparados."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from case_config import reference_paths
from case_evidence import (
    digest, parse_json, read_regular, reference_test_ids, require,
    snapshot_matches, snapshot_tree, validate_test_report,
)
import repair_case
import review_case
from process_environment import process_environment


PROJECT = Path(__file__).resolve().parent
CANDIDATES = (
    ("candidato_01", "case_01"), ("candidato_02", "case_01"),
    ("candidato_03", "case_02"), ("candidato_04", "case_02"),
)
RUNTIME_FILES = (
    "evaluate_reviewer.py", "review_case.py", "repair_case.py",
    "run_case.py", "case_config.py", "case_evidence.py", "process_environment.py",
)
ORIGIN = "candidatos_preparados_para_evaluacion"


class AlreadyReserved(ValueError):
    """La reserva existente pertenece a otro lanzamiento y no debe modificarse."""


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def save_json(path, value):
    """Sustituir un resumen completo sin dejar visible un JSON a medio escribir."""
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".resumen-", delete=False) as out:
        temporary = Path(out.name)
        try:
            out.write(json_bytes(value))
            out.flush()
            os.fsync(out.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def required_bytes(path):
    content = read_regular(path)
    require(content is not None, f"Falta un archivo regular: {path}")
    return content


def inputs_for(root, candidate_id, case_id):
    references = reference_paths(root, case_id)
    return {
        "candidato.py": f"evals/revisor/candidatos/{candidate_id}.py",
        "contrato.md": references["contrato.md"].relative_to(root).as_posix(),
        "test_solution.py": references["test_solution.py"].relative_to(root).as_posix(),
        "instrucciones.md": f"evals/revisor/instrucciones_{case_id}.md",
    }


def source_paths(root):
    paths = set(RUNTIME_FILES)
    for candidate_id, case_id in CANDIDATES:
        paths.update(inputs_for(root, candidate_id, case_id).values())
    return sorted(paths)


def requested_configuration():
    return {
        "sandbox": "read-only", "approval_policy": "never", "web_search": "disabled",
        "features.multi_agent": False, "sesion": "nueva; --ephemeral; sin resume ni fork",
        "limite_agente_segundos": review_case.AGENT_TIMEOUT_SECONDS,
        "limite_consulta_cli_segundos": review_case.PREFLIGHT_TIMEOUT_SECONDS,
        "limite_pruebas_segundos": repair_case.TIMEOUT_SECONDS,
        "modelo": "no fijado por el lanzador", "proveedor": "no fijado por el lanzador",
        "esfuerzo": "no fijado por el lanzador",
    }


def effective_configuration():
    return {
        "modelo": "no consta", "proveedor": "no consta", "esfuerzo": "no consta",
        "observacion": "La CLI puede heredar configuración personal y del entorno. "
        "No se lee ni copia esa configuración; los argumentos iguales no acreditan "
        "igualdad de parámetros efectivos. No se infieren de la versión de CLI. "
        "Los eventos se conservan para su contraste posterior.",
    }


def temporary_workspace(root, prefix):
    parent = Path(tempfile.gettempdir()).resolve()
    require(parent != root and root not in parent.parents,
            "El directorio temporal debe estar fuera del repositorio")
    return tempfile.TemporaryDirectory(prefix=prefix, dir=parent)


def record_git(root, destination, paths):
    def git(*args):
        with process_environment() as environment:
            return subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True,
                check=True, timeout=10, env=environment,
            ).stdout
    revision = git("rev-parse", "HEAD").decode().strip()
    branch = git("branch", "--show-current").decode().strip()
    status = git("status", "--porcelain=v1", "--untracked-files=all", "--", *paths).decode()
    changes = git("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--", *paths)
    (destination / "cambios.patch").write_bytes(changes)
    save_json(destination / "git.json", {
        "revision": revision, "rama": branch, "estado_relevante": status,
        "rutas_incluidas": paths,
        "nota": "El diff incluye cambios versionados; fuentes/ conserva también los no versionados. "
        "Solo se incluyen las rutas explícitas; no se copia configuración privada.",
    })


def verify_evaluation(directory, candidate, tests, case_id):
    result = parse_json(required_bytes(directory / "resultado.json"))
    require(result["estado"] == "finalizada" and type(result["codigo_salida"]) is int
            and result["codigo_salida"] == 0, "Las pruebas originales no terminaron correctamente")
    require(result["pruebas_intactas"] is True and result["implementacion_intacta"] is True,
            "La evaluación alteró sus materiales")
    require(required_bytes(directory / "workspace/solution.py") == candidate
            and required_bytes(directory / "workspace/test_solution.py") == tests,
            "La copia evaluada no coincide con las fuentes congeladas")
    require(len(reference_test_ids(tests)) == {"case_01": 4, "case_02": 16}[case_id],
            "Número de pruebas originales inesperado")
    require(required_bytes(directory / "stdout.txt") == b"", "Salida inesperada de las pruebas")
    validate_test_report(tests, required_bytes(directory / "stderr.txt").decode("utf-8"))


def prepare(root=PROJECT, *, progress=None):
    root = Path(root).resolve()
    started = time.monotonic()
    result = {"version": 1, "procedencia": ORIGIN, "experimento": None,
              "estado": "en_preparacion", "codigo_salida": 1, "error": None,
              "inicio_utc": repair_case.timestamp(), "orden": list(map(list, CANDIDATES)),
              "configuracion_solicitada": requested_configuration(), "sha256": {}}
    experiment = None
    try:
        runs = root / "runs"
        runs.mkdir(exist_ok=True)
        experiment = runs / f"{repair_case.utc_timestamp().strftime('%Y%m%dT%H%M%S%fZ')}_revisor_{uuid4().hex}"
        experiment.mkdir()
        result["experimento"] = str(experiment)
        frozen = experiment / "preparacion"
        frozen.mkdir()
        if progress is not None:
            progress("Preparando materiales y comprobando candidatos.")
        paths = source_paths(root)
        for name in paths:
            target = frozen / "fuentes" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(required_bytes(root / name))
        record_git(root, frozen, paths)
        for candidate_id, case_id in CANDIDATES:
            inputs = {key: required_bytes(frozen / "fuentes" / name)
                      for key, name in inputs_for(root, candidate_id, case_id).items()}
            require(inputs["instrucciones.md"].strip(), "Instrucciones vacías")
            require(inputs["candidato.py"].strip(), "Candidato vacío")
            if case_id == "case_02":
                require(b"**Versi\xc3\xb3n 2" in inputs["contrato.md"], "Se requiere contrato v2")
            saved = frozen / "evaluaciones" / candidate_id
            saved.parent.mkdir(exist_ok=True)
            with temporary_workspace(root, "evaluacion-revisor-") as temporary:
                evaluation = Path(temporary) / "evaluacion"
                try:
                    repair_case.evaluate(inputs["candidato.py"], inputs["test_solution.py"], evaluation)
                finally:
                    if evaluation.exists():
                        shutil.copytree(evaluation, saved, symlinks=True)
            verify_evaluation(saved, inputs["candidato.py"], inputs["test_solution.py"], case_id)
        result["sha256"] = snapshot_tree(frozen)
        result.update(estado="preparada", codigo_salida=0)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        result.update(estado="interrumpida" if isinstance(exc, KeyboardInterrupt) else "fallida",
                      error=str(exc) or type(exc).__name__)
    result.update(fin_utc=repair_case.timestamp(), duracion_segundos=time.monotonic() - started)
    if experiment is not None:
        try:
            save_json(experiment / "preparacion.json", result)
        except OSError as exc:
            result.update(estado="fallida", codigo_salida=1, error=str(exc))
    return result


def validate_preparation(experiment, root):
    raw = required_bytes(experiment / "preparacion.json")
    result = parse_json(raw)
    require(result["version"] == 1 and result["procedencia"] == ORIGIN,
            "Procedencia o versión no admitida")
    require(result["estado"] == "preparada" and type(result["codigo_salida"]) is int
            and result["codigo_salida"] == 0, "La preparación no autoriza el lanzamiento")
    require(result["orden"] == list(map(list, CANDIDATES)), "Orden de candidatos alterado")
    require(result["configuracion_solicitada"] == requested_configuration(),
            "La configuración solicitada cambió desde la preparación")
    frozen = experiment / "preparacion"
    require(snapshot_tree(frozen) == result["sha256"], "Hashes de la preparación alterados")
    require(snapshot_tree(frozen / "fuentes").keys() == set(source_paths(root)),
            "Fuentes incompletas o materiales no permitidos")
    for name in RUNTIME_FILES:
        require(required_bytes(root / name) == required_bytes(frozen / "fuentes" / name),
                f"El código del lanzador cambió desde la preparación: {name}")
    for candidate_id, case_id in CANDIDATES:
        sources = inputs_for(root, candidate_id, case_id)
        verify_evaluation(frozen / "evaluaciones" / candidate_id,
                          required_bytes(frozen / "fuentes" / sources["candidato.py"]),
                          required_bytes(frozen / "fuentes" / sources["test_solution.py"]), case_id)
    return result, digest(raw)


def review_materials(experiment, root, candidate_id, case_id):
    frozen = experiment / "preparacion"
    inputs = {key: required_bytes(frozen / "fuentes" / name)
              for key, name in inputs_for(root, candidate_id, case_id).items()}
    prompt = inputs.pop("instrucciones.md")
    evaluation = frozen / "evaluaciones" / candidate_id
    for target, source in (("posterior.json", "resultado.json"),
                           ("posterior.stdout.txt", "stdout.txt"),
                           ("posterior.stderr.txt", "stderr.txt")):
        inputs[target] = required_bytes(evaluation / source)
    inputs["respuesta.schema.json"] = json_bytes(
        review_case.response_schema(len(inputs["candidato.py"].splitlines())))
    return inputs, prompt


def review_one(experiment, root, entry, *, on_invoke=None):
    materials, prompt = review_materials(experiment, root, entry["id"], entry["caso"])
    directory = experiment / "lanzamiento" / entry["id"]
    directory.mkdir()
    entry["registro"] = str(directory)
    archive = directory / "materiales"
    archive.mkdir()
    for name, data in materials.items():
        (archive / name).write_bytes(data)
    hashes = snapshot_tree(archive)
    log = directory / "revisor"
    log.mkdir()
    (log / "entrada.txt").write_bytes(prompt)
    started = time.monotonic()
    entry.update(estado="en_curso", invocaciones=None, instrucciones_sha256=digest(prompt),
                 configuracion_efectiva=effective_configuration(), inicio_utc=repair_case.timestamp())
    save_json(directory / "resultado.json", entry)
    with temporary_workspace(root, "revision-preparada-") as temporary:
        workspace = Path(temporary) / "workspace"
        workspace.mkdir()
        for name, data in materials.items():
            (workspace / name).write_bytes(data)
        final = Path(temporary) / "respuesta.txt"
        try:
            agent = review_case.invoke_reviewer(workspace, final, prompt, log, on_invoke=on_invoke)
            entry.update(revisor=agent, invocaciones=agent["invocaciones"])
            require(agent["invocaciones"] in (0, 1), "Más de una invocación para un candidato")
            entry["estado"] = ("completada" if agent["estado"] == "finalizada"
                               and agent["codigo_salida"] == 0 and not agent.get("error_registro")
                               else "fallo_tecnico")
        except repair_case.ProcessInterrupted as exc:
            command = exc.result["comando"]
            calls = int(len(command) > 1 and command[1] == "exec" and "--help" not in command)
            entry.update(estado="interrumpida", revisor=exc.result, invocaciones=calls, error=str(exc))
        except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as exc:
            entry.update(estado="interrumpida" if isinstance(exc, KeyboardInterrupt) else "fallo_tecnico",
                         error=str(exc) or type(exc).__name__)
        finally:
            raw = read_regular(final)
            if raw is not None:
                (log / "respuesta_original.txt").write_bytes(raw)
            try:
                require(raw is not None, "No hay respuesta del revisor")
                entry["dictamen"] = review_case.validate_verdict(raw, len(materials["candidato.py"].splitlines()))
                save_json(directory / "dictamen_validado.json", entry["dictamen"])
            except (ValueError, TypeError) as exc:
                entry["error_respuesta"] = str(exc)
                if entry["estado"] == "completada":
                    entry["estado"] = "respuesta_invalida"
            entry["integridad"] = {
                "workspace_intacto": snapshot_matches(workspace, hashes),
                "materiales_intactos": snapshot_matches(archive, hashes),
                "instrucciones_intactas": read_regular(log / "entrada.txt") == prompt,
            }
            try:
                save_json(directory / "workspace_despues.sha256.json", snapshot_tree(workspace))
            except (OSError, ValueError) as exc:
                entry["error_integridad"] = str(exc)
            if not all(entry["integridad"].values()):
                entry["estado"] = "integridad_alterada"
            entry.update(fin_utc=repair_case.timestamp(), duracion_segundos=time.monotonic() - started)
            save_json(directory / "resultado.json", entry)
    return entry


def normalized_command(command):
    command = command.copy()
    for flag in ("--cd", "--output-schema", "--output-last-message"):
        command[command.index(flag) + 1] = f"<{flag[2:]}>"
    return command


def report_review(progress, entry):
    if progress is not None:
        decision = f"; dictamen: {entry['dictamen']['decision']}" if entry["dictamen"] else ""
        progress(f"{entry['id']}: {entry['estado']}{decision}.")


def run_experiment(experiment, root=PROJECT, *, progress=None):
    experiment, root = Path(experiment).resolve(), Path(root).resolve()
    result = {"experimento": str(experiment), "estado": "no_iniciado", "codigo_salida": 1,
              "error": None, "inicio_utc": repair_case.timestamp(), "max_invocaciones": 4,
              "revisiones_reservadas": 0, "evidencia_completa_verificada": False,
              "configuracion_solicitada": requested_configuration(),
              "configuracion_efectiva": effective_configuration(),
              "candidatos": [{"id": candidate_id, "caso": case_id, "estado": "pendiente",
                              "invocaciones": 0, "dictamen": None, "registro": None,
                              "validez_hallazgos": "pendiente_de_contraste"}
                             for candidate_id, case_id in CANDIDATES]}
    started = time.monotonic()
    reserved = False
    active = None
    records = {}
    launch = experiment / "lanzamiento"
    try:
        prepared, manifest_hash = validate_preparation(experiment, root)
        # mkdir es la reserva atómica y permanente: también sobrevive a una interrupción.
        try:
            launch.mkdir()
        except FileExistsError as exc:
            raise AlreadyReserved("Experimento ya reservado: no se permite repetir ni reanudar") from exc
        reserved = True
        result.update(estado="en_curso", preparacion_sha256=manifest_hash)
        save_json(launch / "reserva.json", {"preparacion_sha256": manifest_hash,
                  "inicio_utc": result["inicio_utc"], "pid": os.getpid(), "reanudacion": False})
        save_json(launch / "resultado.json", result)
        executable = shutil.which(review_case.CODEX_EXECUTABLE)
        executable = Path(executable).resolve() if executable else None
        binary_hash = digest(read_regular(executable)) if executable else None
        result["cli"] = {"ruta": str(executable) if executable else None, "sha256": binary_hash}
        baseline_command = baseline_version = None

        def check_integrity():
            require(digest(required_bytes(experiment / "preparacion.json")) == manifest_hash,
                    "El manifiesto cambió durante el lanzamiento")
            require(snapshot_matches(experiment / "preparacion", prepared["sha256"]),
                    "La preparación cambió durante el lanzamiento")
            for name in RUNTIME_FILES:
                require(required_bytes(root / name) == required_bytes(experiment / "preparacion/fuentes" / name),
                        f"Código del lanzador alterado: {name}")
            require(all(snapshot_matches(launch / name, hashes) for name, hashes in records.items()),
                    "Se alteró la evidencia de una revisión anterior")
            require(executable is None or digest(read_regular(executable)) == binary_hash,
                    "El ejecutable de la CLI cambió durante el lanzamiento")

        for number, entry in enumerate(result["candidatos"], 1):
            active = None
            check_integrity()
            active = entry
            result["revisiones_reservadas"] += 1
            entry.update(estado="en_curso", invocaciones=None)
            save_json(launch / "resultado.json", result)
            on_invoke = None
            if progress is not None:
                def on_invoke():
                    progress(f"Revisión {number}/{len(CANDIDATES)}: iniciando {entry['id']}…")
            review_one(experiment, root, entry, on_invoke=on_invoke)
            check_integrity()
            if entry["estado"] == "completada":
                require(entry["invocaciones"] == 1, "Revisión sin invocación acreditada")
                command = normalized_command(entry["revisor"]["comando"])
                version = required_bytes(Path(entry["registro"]) / "revisor/codex_version.txt")
                if baseline_command is None:
                    baseline_command, baseline_version = command, version
                require(command == baseline_command and version == baseline_version,
                        "Los argumentos o la versión de CLI difieren entre revisiones")
            records[entry["id"]] = snapshot_tree(Path(entry["registro"]))
            save_json(launch / "resultado.json", result)
            report_review(progress, entry)
            if entry["estado"] != "completada":
                result.update(estado="incompleto", error=f"Detención en {entry['id']}: {entry['estado']}")
                break
        else:
            check_integrity()
            result.update(estado="completado", codigo_salida=0, evidencia_completa_verificada=True)
    except AlreadyReserved as exc:
        result.update(estado="rechazado", error=str(exc))
    except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as exc:
        result.update(estado="interrumpido" if isinstance(exc, KeyboardInterrupt) else "incompleto",
                      error=str(exc) or type(exc).__name__)
        if active is not None:
            active["estado"] = "interrumpida" if isinstance(exc, KeyboardInterrupt) else "fallo_evidencia"
            active["error"] = result["error"]
            if active["registro"] is not None:
                try:
                    save_json(Path(active["registro"]) / "resultado.json", active)
                    records[active["id"]] = snapshot_tree(Path(active["registro"]))
                except (OSError, ValueError) as record_error:
                    result["error_registro"] = str(record_error)
            report_review(progress, active)
    result.update(fin_utc=repair_case.timestamp(), duracion_segundos=time.monotonic() - started,
                  revisiones_sha256=records)
    if reserved:
        try:
            save_json(launch / "resultado.json", result)
        except OSError as exc:
            result.update(estado="incompleto", codigo_salida=1, error=f"No se pudo guardar el resumen: {exc}")
    return result


def cli_progress(message):
    try:
        print(message, file=sys.stderr, flush=True)
    except OSError:
        # Un canal informativo cerrado no debe alterar la ejecución ni sus decisiones.
        pass


def stop_message(result):
    details = [result["error"] or result["estado"]]
    entries = [entry for entry in result.get("candidatos", []) if entry["estado"] != "pendiente"]
    entry = entries[-1] if entries else {}
    for key in ("error", "error_respuesta", "error_integridad"):
        if entry.get(key) and entry[key] not in details:
            details.append(entry[key])
    agent = entry.get("revisor", {})
    for label, process in (("revisor", agent), ("versión", agent.get("version", {})),
                           ("ayuda", agent.get("ayuda", {}))):
        if process and (process.get("estado") != "finalizada" or process.get("codigo_salida") != 0):
            details.append(f"{label}: {process.get('estado')}, código {process.get('codigo_salida')}")
            if process.get("error"):
                details.append(process["error"])
    if agent.get("error_registro"):
        details.append(agent["error_registro"])
    failed = [name for name, intact in entry.get("integridad", {}).items() if not intact]
    if failed:
        details.append("integridad: " + ", ".join(failed))
    location = entry.get("registro") or result["experimento"] or "no creado"
    return f"Detenido: {'; '.join(details)}; registro: {location}."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)
    operations.add_parser("prepare", help="Congelar fuentes y evaluar sin invocar modelos")
    run = operations.add_parser("run", help="Invocar al revisor una vez por candidato, sin reanudación")
    run.add_argument("--experiment", type=Path, required=True, help="Ruta exacta impresa por prepare")
    args = parser.parse_args(argv)
    result = (prepare(progress=cli_progress) if args.operation == "prepare"
              else run_experiment(args.experiment, progress=cli_progress))
    if result["codigo_salida"] != 0:
        cli_progress(stop_message(result))
    print(f"Estado: {result['estado']}; código: {result['codigo_salida']}")
    print(f"Experimento: {result['experimento'] or 'no creado'}")
    for entry in result.get("candidatos", []):
        decision = entry["dictamen"]["decision"] if entry["dictamen"] else "no consta"
        print(f"{entry['id']}: {entry['estado']}; invocaciones: {entry['invocaciones']}; "
              f"dictamen: {decision}; evidencia: {entry['registro'] or 'no creada'}; "
              "hallazgos: pendientes de contraste")
    return result["codigo_salida"]


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"Señal {signum}")
    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())

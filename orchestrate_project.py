"""Flujo acotado de proyectos: una entrega y una revisión por intento; sin incorporación."""

import argparse
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from case_evidence import digest, parse_json, read_regular, require
from repair_case import timestamp, write_json
from repair_project import PROJECT, StopProject, cli_progress, develop, required, tree_state
from project_flow import (TASKS, delivery_diff, file_identity, preparation_authorized, task_config,
                          evaluate_flow, freeze_flow, validate_delivery, validate_inventory)
from review_project import run_delivery_review, validate_verdict


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    write_json(temporary, data)
    temporary.replace(path)


def feedback_from(delivery, record, review=None, *, task=None):
    """Datos trazables; los hallazgos del modelo no son hechos acreditados."""
    config = task_config(task if task is not None else record["tarea"])
    multiple = config.get("multiples", False)
    key = "conjunto_sha256" if multiple else "candidato_sha256"
    feedback = {key: record[key], "pruebas": {}, "revision": None}
    if multiple:
        feedback["version"] = 2
    for kind, item in record["evaluaciones"].items():
        if item["clasificacion"] == "fallos_asercion":
            stage = delivery / "evaluaciones" / kind
            diagnostics = {name: required(stage / name) for name in ("pruebas.json", "stderr.txt")}
            feedback["pruebas"][kind] = {
                "fuente": str(stage), "sha256": {n: digest(raw) for n, raw in diagnostics.items()},
                "informe": parse_json(diagnostics["pruebas.json"]),
                "diagnosticos": diagnostics["stderr.txt"].decode(errors="replace")}
    if review:
        editable = config.get("editable")
        path = Path(review["registro"])
        lines = ({name: len(required(delivery / "entrega/archivos" / name).splitlines())
                  for name in config["editables"]} if multiple else
                 len(required(delivery / "entrega" / editable).splitlines()))
        verdict = validate_verdict(required(path / "revisor/respuesta_original.txt"), lines, editable=editable)
        require(verdict == review["dictamen_modelo"] == parse_json(required(path / "dictamen_validado.json"))
                and verdict["decision"] == "solicitar_cambios", "Feedback de revisión inválido")
        feedback["revision"] = {
            "naturaleza": "observaciones_del_modelo_pendientes_de_contraste_semantico",
            "instruccion": "Contrastar con contrato y código antes de corregir; validar JSON no confirma hallazgos.",
            "fuente": str(path / "dictamen_validado.json"),
            "sha256": digest(required(path / "dictamen_validado.json")), "dictamen": verdict}
    return feedback


def run_orchestration(task=None, root=PROJECT, max_attempts=2, *, progress=None, task_config_path=None):
    root = Path(root).resolve()
    if task_config_path is not None:
        from project_task_config import load_task
        require(task is None, "No combinar tarea posicional con --task-config")
        selection = load_task(root, task_config_path)
        config = task_config(selection)
        task = config["tarea"]
    else:
        task = "inspect-json" if task is None else task
        selection = task
        config = task_config(task if task in TASKS else "inspect-json")
    generic = config.get("configurable", False)
    multiple = config.get("multiples", False)
    if multiple:
        import project_delivery as bundle
    editable, limits = config.get("editable"), config["limites"]
    started = time.monotonic()
    result = {"tipo": config["tipo"], "tarea": task, "registro": None, "inicio_utc": timestamp(),
              "estado": "en_preparacion", "motivo": None, "codigo_salida": 8,
              "max_intentos": max_attempts, "max_invocaciones": max_attempts * 2,
              "invocaciones": {"desarrollador": 0, "revisor": 0, "total": 0},
              "reservas": [], "intentos": [], "inicial": {}, "integridad": {},
              "limites_segundos": dict(limits), "etapas_cerradas": {},
              "lista_para_revision_humana": False, "incorporacion": "no_realizada", "error": None}
    if generic:
        result["configuracion"] = {"version": selection.document["version"], "identificador": task,
            "origen": config["origen_configuracion"], "sha256": config["configuracion_sha256"],
            "commit_base": config["base"]}
    log = frozen = None
    original_state = reference_state = None

    def save():
        if log is not None:
            atomic_json(log / "resultado.json", result)

    def notify(message):
        if progress:
            progress(message)

    def seal(path):
        key = str(path)
        require(key not in result["etapas_cerradas"], "No se permite volver a sellar una etapa")
        result["etapas_cerradas"][key] = tree_state(path)
        save()

    def check():
        result["integridad"].update(
            original_intacto=tree_state(root, filter_local=True) == original_state,
            referencia_intacta=tree_state(frozen) == reference_state,
            registros_intactos=all(tree_state(Path(p)) == s for p, s in result["etapas_cerradas"].items()))
        if not all(v for k, v in result["integridad"].items() if k != "alcance_respetado"):
            raise StopProject(6, "modificacion_no_permitida", "Original, referencia, alcance o evidencia alterados")
        if result["integridad"].get("alcance_respetado") is False:
            raise StopProject(6, "entrega_invalida" if multiple or config["ausente"] else "modificacion_no_permitida",
                              "Entrega ausente, no regular, con permisos incorrectos o fuera de alcance")

    def reserve(role, entry):
        check()
        require(role in ("desarrollador", "revisor") and entry["invocaciones"][role] == 0
                and result["invocaciones"][role] < max_attempts
                and result["invocaciones"]["total"] < result["max_invocaciones"], "Presupuesto excedido")
        reservation = {"rol": role, "intento": entry["numero"], "fecha_utc": timestamp(),
                       "limite_segundos": limits[role], "estado": "reservada_antes_de_invocar"}
        directory = log / "reservas" / f"{entry['numero']}-{role}"
        directory.mkdir()
        atomic_json(directory / "reserva.json", reservation)
        result["reservas"].append(reservation)
        entry["invocaciones"][role] += 1
        result["invocaciones"][role] += 1
        result["invocaciones"]["total"] += 1
        seal(directory)  # También persiste los contadores antes del proceso.

    try:
        require(generic or task in TASKS, "Tarea de proyecto desconocida")
        require(type(max_attempts) is int and max_attempts in (1, 2), "Solo uno o dos intentos")
        original_state = tree_state(root, filter_local=True)
        parent = Path(tempfile.gettempdir()).resolve()
        require(parent != root and root not in parent.parents, "Los temporales deben estar fuera del proyecto")
        (root / "runs").mkdir(exist_ok=True)
        log = root / "runs" / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{task}_orchestrate_{uuid4().hex}"
        log.mkdir()
        (log / "intentos").mkdir()
        (log / "reservas").mkdir()
        result["registro"] = str(log)
        save()
        notify(f"Congelando base de {config['contrato']}, autoridades, prompts y configuración del flujo.")
        frozen = log / "referencia"
        result["procedencia"] = freeze_flow(root, frozen, max_attempts, selection)
        reference_state = tree_state(frozen)
        if generic:
            selection.reference_state = reference_state
        result.update(referencia_sha256=reference_state, original_sha256=original_state)
        expected = result["procedencia"]["pruebas_esperadas"]
        with tempfile.TemporaryDirectory(prefix="orchestrate-project-", dir=parent) as temporary:
            temporary = Path(temporary)
            initial = temporary / "inicial"
            shutil.copytree(frozen / "proyecto", initial)
            evaluate_flow(initial, frozen, log / "inicial", expected, result["inicial"], progress, check, seal,
                          kinds=("aceptacion", "regresion"), task=selection)
            seal(log / "inicial")
            if not preparation_authorized(result["inicial"], required(log / "inicial/aceptacion/stderr.txt"), config):
                raise StopProject(7, "preparacion_no_autoriza", "Regresión o precondición inicial no acreditadas")
            if generic or config["ausente"]:
                require(validate_inventory(frozen, config, result["procedencia"]) == expected["regresion"],
                        "Inventario esperado alterado")
            if multiple:
                starting = bundle.contents(frozen / "proyecto", config)
            else:
                if config["ausente"]:
                    require(editable not in tree_state(frozen / "proyecto"), "El editable inicial debe estar ausente")
                starting = None if config["ausente"] else required(frozen / "proyecto" / editable)
            feedback, previous = None, None
            for number in range(1, max_attempts + 1):
                check()
                attempt = log / "intentos" / str(number)
                delivery = attempt / "evidencia"
                delivery.mkdir(parents=True)
                entry = {"numero": number, "registro": str(delivery),
                         "invocaciones": {"desarrollador": 0, "revisor": 0}, "transiciones": [], "revision": None}
                result["intentos"].append(entry)
                record = {"tipo": config["tipo"], "tarea": task, "numero": number, "registro": str(delivery),
                          "referencia_sha256": reference_state, "inicial_sha256": tree_state(log / "inicial"),
                          "anterior_sha256": tree_state(previous) if previous else None,
                          "desarrollo": {"agente": {"invocaciones": 0, "proceso": None}, "reserva_invocacion": False},
                          "evaluaciones": {}, "etapas_sha256": {}}
                workspace = temporary / f"desarrollo-{number}"
                shutil.copytree(frozen / "proyecto", workspace)
                if multiple:
                    bundle.overlay(workspace, starting, config)
                    part = bundle.identity(tree_state(workspace), config)
                    entry.update(partida_conjunto=part, partida_conjunto_sha256=part["sha256"])
                    record.update(partida_conjunto=part, partida_conjunto_sha256=part["sha256"])
                    if previous:
                        require(part == parse_json(required(previous / "entrega/conjunto.json")), "Continuidad rota")
                else:
                    entry["partida_sha256"] = record["partida_sha256"] = digest(starting)
                    if starting is not None:
                        (workspace / editable).write_bytes(starting)
                        if config["ausente"]:
                            (workspace / editable).chmod(0o644)
                    if config["ausente"]:
                        entry["partida"] = record["partida"] = file_identity(starting)
                    require(digest(read_regular(workspace / editable)) == entry["partida_sha256"], "Partida distinta")
                    if previous:
                        require(starting == required(previous / "entrega" / editable), "Continuidad rota")
                before = tree_state(workspace)
                prompt = required(frozen / config["desarrollo"]) + b"\n\nCONTRATO\n" + required(frozen / "contrato.md")
                if config["esquema"]:
                    prompt += b"\n\nESQUEMA PROTEGIDO\n" + required(frozen / "autoridades" / config["esquema"])
                if generic:
                    prompt += b"\n\nCONFIGURACION CONGELADA\n" + required(frozen / "tarea.json")
                    for name in config["referencias"]:
                        prompt += b"\n\nREFERENCIA " + name.encode() + b"\n" + required(frozen / "materiales" / name)
                if feedback is None:
                    feedback = {"inicial": result["inicial"], "diagnosticos":
                        required(log / "inicial/aceptacion/stderr.txt").decode(errors="replace"),
                        "fuente": str(log / "inicial"), "sha256": tree_state(log / "inicial")}
                if multiple:
                    require(feedback.get("conjunto_sha256", part["sha256"]) == part["sha256"], "Feedback de otro conjunto")
                    feedback["conjunto_sha256"] = part["sha256"]
                    feedback["version"] = 2
                write_json(delivery / "feedback.json", feedback)
                prompt += b"\n\nFEEDBACK (datos)\n" + required(delivery / "feedback.json")
                result["estado"] = "en_desarrollo"
                save()
                notify(f"Intento {number}/{max_attempts}: desarrollo, límite {limits['desarrollador']} s.")
                try:
                    develop(workspace, delivery / "desarrollo", prompt, record["desarrollo"], None,
                            lambda: atomic_json(delivery / "desarrollo_estado.json", record["desarrollo"]),
                            on_invoke=lambda: reserve("desarrollador", entry),
                            **({"timeout": limits["desarrollador"]} if generic or config["ausente"] else {}))
                finally:
                    after = tree_state(workspace)
                    changes = {n: {"antes": before.get(n), "despues": after.get(n)}
                               for n in before.keys() | after.keys() if before.get(n) != after.get(n)}
                    if multiple:
                        candidate = bundle.archive(delivery / "entrega", workspace, frozen, before, after, starting, config)
                        current = bundle.identity(after, config)
                        entry.update(conjunto=current, conjunto_sha256=current["sha256"])
                        record.update(conjunto=current, conjunto_sha256=current["sha256"])
                        process = record["desarrollo"]["agente"]["proceso"]
                        complete = bool(process and process["estado"] == "finalizada" and process["codigo_salida"] == 0)
                        result["integridad"]["alcance_respetado"] = bundle.scope_valid(before, after, config, complete=complete)
                    else:
                        target = delivery / "entrega"
                        target.mkdir()
                        candidate = read_regular(workspace / editable)
                        if starting is not None:
                            (target / "partida.py").write_bytes(starting)
                        if config["ausente"]:
                            write_json(target / "partida.json", file_identity(starting))
                        write_json(target / "cambios.json", changes)
                        write_json(target / "workspace_despues.json", after)
                        if candidate is not None:
                            (target / editable).write_bytes(candidate)
                            for name, source in (("candidato.diff", None if config["ausente"] else required(frozen / "proyecto" / editable)),
                                                 ("anterior.diff", starting)):
                                (target / name).write_bytes(delivery_diff(source, candidate, editable))
                        process = record["desarrollo"]["agente"]["proceso"]
                        # Una consulta CLI fallida o una reserva no persistida no es
                        # una entrega: conservar la ausencia y el fallo técnico.
                        absent_after_failure = (config["ausente"] and starting is None and editable not in after
                            and not (process and process["estado"] == "finalizada" and process["codigo_salida"] == 0))
                        result["integridad"]["alcance_respetado"] = (set(changes) <= {editable} and (absent_after_failure
                            or candidate is not None and after[editable]["modo"] ==
                            (0o644 if config["ausente"] else before[editable]["modo"])))
                        entry["candidato_sha256"] = record["candidato_sha256"] = digest(candidate)
                    entry["desarrollo"] = record["desarrollo"]
                    for name in ("desarrollo", "entrega"):
                        seal(delivery / name)
                    atomic_json(delivery / "resultado.json", record)
                    check()
                posterior = temporary / f"evaluacion-{number}"
                shutil.copytree(frozen / "proyecto", posterior)
                if multiple:
                    bundle.overlay(posterior, candidate, config)
                    require(bundle.identity(tree_state(posterior), config) == current, "Copia de evaluación de otro conjunto")
                else:
                    (posterior / editable).write_bytes(candidate)
                    if config["ausente"]:
                        (posterior / editable).chmod(0o644)
                result["estado"] = "en_evaluacion"
                save()
                try:
                    evaluate_flow(posterior, frozen, delivery / "evaluaciones", expected, record["evaluaciones"],
                                  progress, check, seal, task=selection)
                finally:
                    record["integridad"] = dict(result["integridad"])
                    record["etapas_sha256"] = {n: tree_state(delivery / n) for n in ("desarrollo", "entrega", "evaluaciones")}
                    entry["evaluaciones"] = record["evaluaciones"]
                    atomic_json(delivery / "resultado.json", record)
                    seal(delivery)
                check()
                validated, _ = validate_delivery(delivery, root, allow_failures=True,
                                                  **({"task": selection} if generic else {}))
                passed = all(item["clasificacion"] == "superadas" for item in validated["evaluaciones"].values())
                reason = "fallos_asercion"
                entry["transiciones"].append({"etapa": "evaluacion", "accion": "revisar" if passed else "corregir", "motivo": "superadas" if passed else reason})
                save()
                review = None
                if passed:
                    result["estado"] = "en_revision"
                    save()
                    review = run_delivery_review(delivery, root, progress=progress,
                                                 on_invoke=lambda: reserve("revisor", entry), task=selection)
                    entry["revision"] = review
                    if review["registro"]:
                        seal(Path(review["registro"]))
                        require(parse_json(required(Path(review["registro"]) / "resultado.json")) == review,
                                "Resumen de revisión incoherente")
                    check()
                    code = review["codigo_salida"]
                    if code not in (0, 1):
                        raise StopProject(code, review["decision_controlador"], review["error"] or "Revisión detenida")
                    raw = required(Path(review["registro"]) / "revisor/respuesta_original.txt")
                    lines = ({name: len(data.splitlines()) for name, data in candidate.items()} if multiple
                             else len(candidate.splitlines()))
                    verdict = validate_verdict(raw, lines, editable=editable)
                    require(verdict == review["dictamen_modelo"] and code == (0 if verdict["decision"] == "aprobar" else 1)
                            and entry["invocaciones"]["revisor"] == 1, "Dictamen no acreditado")
                    reason = "revision_aprobada" if code == 0 else "cambios_solicitados"
                    entry["transiciones"].append({"etapa": "revision", "accion": "aprobar" if code == 0 else "corregir", "motivo": reason})
                    if code == 0:
                        result.update(estado="lista_para_revision_humana", motivo=reason, codigo_salida=0,
                                      lista_para_revision_humana=True)
                        break
                if number == max_attempts:
                    entry["transiciones"].append({"etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"})
                    result.update(estado="intentos_agotados", motivo=reason, codigo_salida=1)
                    break
                feedback = feedback_from(delivery, validated, review, task=selection)
                previous, starting = delivery, candidate
                check()
            check()
    except StopProject as exc:
        result.update(estado=exc.state, motivo=exc.state, codigo_salida=exc.code, error=str(exc))
    except KeyboardInterrupt as exc:
        result.update(estado="interrumpida", motivo="interrupcion", codigo_salida=9, error=str(exc) or "Interrupción")
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        result.update(estado="evidencia_invalida", motivo="evidencia_invalida", codigo_salida=7, error=str(exc))
    except (OSError, subprocess.SubprocessError) as exc:
        result.update(estado="fallo_controlador", motivo="fallo_controlador", codigo_salida=8, error=str(exc))
    finally:
        if reference_state is not None:
            try:
                check()
            except (StopProject, OSError) as exc:
                state = "entrega_invalida" if isinstance(exc, StopProject) and exc.state == "entrega_invalida" else "modificacion_no_permitida"
                result.update(estado=state, motivo="integridad_alterada", codigo_salida=6, error=str(exc))
        if result["codigo_salida"] != 0:
            result["lista_para_revision_humana"] = False
        # Conservar también etapas parciales tras fallos técnicos o interrupciones.
        # Nunca sobrescribir un sello anterior con el estado alterado.
        try:
            for entry in result["intentos"]:
                path = Path(entry["registro"])
                if str(path) not in result["etapas_cerradas"]:
                    seal(path)
        except (OSError, ValueError) as exc:
            result.update(estado="fallo_controlador", codigo_salida=8, lista_para_revision_humana=False, error=str(exc))
        result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
        try:
            save()
        except OSError as exc:
            result.update(estado="fallo_controlador", codigo_salida=8, lista_para_revision_humana=False, error=str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tarea", choices=TASKS, nargs="?")
    parser.add_argument("--task-config", action="append", help="Una configuración relativa bajo tasks/config/")
    parser.add_argument("--max-attempts", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    if (args.tarea is None) == (args.task_config is None):
        parser.error("Seleccione una tarea posicional o --task-config, sin combinarlas")
    if args.task_config is not None and len(args.task_config) != 1:
        parser.error("Seleccione exactamente una configuración")
    try:
        result = run_orchestration(args.tarea, PROJECT, args.max_attempts, progress=cli_progress,
                                   task_config_path=args.task_config[0] if args.task_config else None)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.error(f"Configuración inválida: {exc}")
    print(f"Estado: {result['estado']}; código: {result['codigo_salida']}")
    calls = result["invocaciones"]
    print(f"Intentos: {len(result['intentos'])}/{result['max_intentos']}; invocaciones: "
          f"desarrollador {calls['desarrollador']}, revisor {calls['revisor']}, total {calls['total']}/{result['max_invocaciones']}")
    print(f"Registro: {result['registro'] or 'no creado'}; incorporación: no realizada")
    if result["error"]:
        cli_progress("Detenido: " + result["error"])
    return result["codigo_salida"]


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"Señal {signum}")
    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())

"""Referencias, evaluación y procedencia del flujo de tareas de proyectos."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from case_evidence import digest, parse_json, read_regular, require, unified_diff
from process_environment import process_environment
from repair_case import ProcessInterrupted, ProcessRecordError, run_process, write_json
from repair_project import (PROJECT, ACCEPTANCE, EDITABLE, StopProject, check_process,
                            classify_report, excluded, freeze, required, static_test_ids, tree_state)


TYPE = "orquestacion_inspect_json_v1"
DEVELOPER_PROMPT = "prompts/developer_inspect_json_flow.md"
REVIEW_PROMPT = "prompts/reviewer_inspect_json_flow.md"
PUBLIC = "evals/tareas_reales/inspect_json/"
SUITES = {"aceptacion": ACCEPTANCE, "regresion": None,
          "hallazgos": PUBLIC + "comprobar_hallazgos.py",
          "anidamiento": PUBLIC + "comprobar_anidamiento.py"}
LIMITS = {"desarrollador": 300, "revisor": 180, "consulta_cli": 10,
          "aceptacion": 60, "regresion": 180, "hallazgos": 60, "anidamiento": 60}
SUPPORT = ("repair_case.py", "run_case.py", "case_config.py", "case_evidence.py", "process_environment.py")
CSV_BASE = "4cda45e2ccda3f7091f8ab15e55087516c09bec0"
CSV_LIMITS = {"desarrollador": 300, "revisor": 300, "consulta_cli": 10,
              "aceptacion": 60, "regresion": 300, "inventario": 30}
CSV_MISSING = "Funcionalidad pendiente: falta export_runs.py como archivo regular; CLI no invocada"
TASKS = ("inspect-json", "export-csv")


def task_config(task="inspect-json"):
    if not isinstance(task, str):
        from project_task_config import ConfiguredTask
        require(isinstance(task, ConfiguredTask), "Selección de tarea inválida")
        return task.config
    require(task in TASKS, "Tarea de proyecto desconocida")
    if task == "inspect-json":
        return {"tipo": TYPE, "tarea": task, "contrato": "tasks/003-inspect-run-json.md",
                "base": None, "editable": EDITABLE, "ausente": False, "esquema": None,
                "desarrollo": DEVELOPER_PROMPT, "revision": REVIEW_PROMPT, "suites": SUITES, "limites": LIMITS}
    return {"tipo": "orquestacion_export_csv_v1", "tarea": task,
            "contrato": "tasks/004-export-runs-csv.md", "base": CSV_BASE,
            "editable": "export_runs.py", "ausente": True, "esquema": "tasks/003-inspect-run-json.md",
            "desarrollo": "prompts/developer_export_csv_flow.md", "revision": "prompts/reviewer_export_csv_flow.md",
            "suites": {"aceptacion": "evals/tareas_reales/export_csv/evaluar.py", "regresion": None},
            "limites": CSV_LIMITS}


def file_identity(content, mode=0o644):
    return {"tipo": "ausente" if content is None else "archivo", "sha256": digest(content),
            "modo": None if content is None else mode}


def delivery_diff(before, after, editable):
    return unified_diff(b"" if before is None else before, after,
                        "/dev/null" if before is None else "a/" + editable, "b/" + editable)


def flow_configuration(config, max_attempts):
    saved = {"tipo": config["tipo"], "max_intentos": max_attempts, "limites_segundos": config["limites"],
             "archivo_editable": config["editable"], "suites": config["suites"],
             "politicas_entorno": ["evaluation", "codex"], "incorporacion_automatica": False, "reanudacion": False}
    if config.get("configurable"):
        saved.update(tarea=config["tarea"], commit_base=config["base"], contrato=config["contrato"],
                     prompts={"desarrollador": config["desarrollo"], "revisor": config["revision"]},
                     referencias=config["referencias"], editable_inicial=config["editable_inicial"],
                     configuracion_sha256=config["configuracion_sha256"],
                     origen_configuracion=config["origen_configuracion"], max_invocaciones=max_attempts * 2,
                     modo_creacion=0o644)
    elif config["ausente"]:
        saved.update(tarea=config["tarea"], commit_base=config["base"], contrato=config["contrato"],
                     esquema=config["esquema"], prompts={"desarrollador": config["desarrollo"], "revisor": config["revision"]},
                     editable_inicial=file_identity(None), modo_creacion=0o644, max_invocaciones=max_attempts * 2)
    return saved


def preparation_authorized(results, stderr, config):
    acceptance = results["aceptacion"]
    valid = (results["regresion"]["clasificacion"] == "superadas"
             and acceptance["clasificacion"] == "fallos_asercion")
    if config.get("configurable"):
        return (valid and acceptance["metodos"] > 0 and acceptance["aserciones_fallidas"] > 0
                and acceptance["errores"] == 0)
    if not config["ausente"]:
        return valid and b"unrecognized arguments: --format json" in stderr
    return (valid and acceptance["metodos"] > 0
            and acceptance["metodos"] == acceptance["metodos_con_fallos"] == acceptance["aserciones_fallidas"]
            and acceptance["errores"] == acceptance["fallos_subtest"] == 0
            and len(re.findall(rb"(?m)^AssertionError: [^\n]*" + re.escape(CSV_MISSING.encode()) + rb"$", stderr))
            == acceptance["metodos"])


def freeze_declared_base(root, destination, config, *, contract=None):
    """Reconstruir solo blobs Git; inventariar después, antes de cualquier agente."""
    contract = required(root / config["contrato"]) if contract is None else contract
    match = re.search(rb"Base: `([0-9a-f]{40})`", contract)
    require(match and match[1].decode() == config["base"],
            "Base declarada distinta de la configuración" if config.get("configurable") else "Base CSV distinta de la configuración")
    def git(*args):
        with process_environment("evaluation") as environment:
            return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                                  timeout=config["limites"]["consulta_cli"], env=environment).stdout
    base = config["base"]
    require(git("rev-parse", base + "^{commit}").decode().strip() == base, "Base no disponible")
    source = destination / "proyecto"
    source.mkdir(parents=True)
    files, omissions = {}, []
    for entry in git("ls-tree", "-rz", "--full-tree", base).split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = raw_name.decode("utf-8")
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "Ruta Git inválida")
        if excluded(name):
            omissions.append(name)
            continue
        require(kind == "blob" and mode in ("100644", "100755"), "Base no regular")
        content = git("cat-file", "blob", oid)
        require(hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() == oid,
                "Blob distinto de Git")
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(int(mode[-3:], 8))
        files[name] = {"objeto_git": oid, "sha256": digest(content), "modo_git": mode}
    initial = file_identity(None)
    if config.get("configurable"):
        initial = tree_state(source).get(config["editable"], initial)
        require(initial == config["editable_inicial"], "Estado inicial distinto de la configuración")
    else:
        require(config["editable"] not in tree_state(source), "La base CSV debe carecer del exportador")
    (destination / "contrato.md").write_bytes(contract)
    provenance = {"tipo": "proyecto_existente_archivo_ausente", "tarea": config["tarea"], "commit_base": base,
                  "head_origen": git("rev-parse", "HEAD").decode().strip(),
                  "archivos_base": files, "excluidos": omissions, "editable_inicial": initial,
                  "materiales_del_arbol_actual": {config["contrato"]: digest(contract)}, "pruebas_esperadas": {}}
    write_json(destination / "procedencia.json", provenance)
    return provenance


def freeze_csv_base(root, destination, config):
    return freeze_declared_base(root, destination, config)


def inventory_base(destination, config, provenance):
    from project_test_inventory import snapshot, state_hash
    source, authority = destination / "proyecto", destination / "autoridades"
    log = destination / "inventario"
    before = snapshot(source)
    log.mkdir()
    write_json(log / "base_antes.json", before)
    command = [str(Path(sys.executable).resolve()), "-B", str(authority / "project_test_inventory.py"),
               "--reference", str(source), "--timeout", str(config["limites"]["inventario"])]
    process = run_process(command, source, log, config["limites"]["inventario"], env_policy="evaluation")
    check_process(process)
    require(snapshot(source) == before, "El inventario alteró la base de confianza")
    raw = required(log / "stdout.txt")
    (log / "informe.json").write_bytes(raw)
    provenance["inventario"] = {"commit_base": config["base"], "informe_sha256": digest(raw),
                                "base_antes_sha256": state_hash(before)}
    write_json(destination / "procedencia.json", provenance)
    return validate_inventory(destination, config, provenance)


def validate_inventory(destination, config, provenance):
    """Leer el inventario sellado; nunca redescubrir desde un candidato."""
    raw = required(destination / "inventario/informe.json")
    report = parse_json(raw)
    process = parse_json(required(destination / "inventario/resultado.json"))
    ids = report["identidades"]
    stamp = provenance["inventario"]
    require(raw == required(destination / "inventario/stdout.txt") and digest(raw) == stamp["informe_sha256"]
            and stamp["commit_base"] == config["base"], "Informe de inventario alterado")
    require(report["version"] == 1 and type(report["version"]) is int and report["estado"] == "completado"
            and report["conservada"] is True and report["errores"] == []
            and type(report["codigo_hijo"]) is int and report["codigo_hijo"] == 0
            and isinstance(ids, list) and ids and all(isinstance(n, str) and n.strip() for n in ids)
            and ids == sorted(set(ids)) and type(report["total"]) is int and report["total"] == len(ids),
            "Inventario incompleto o inválido")
    require(report["referencia"] == str(destination / "proyecto")
            and report["arbol_antes_sha256"] == report["arbol_despues_sha256"] == stamp["base_antes_sha256"]
            and report["politica_entorno"] == "evaluation" and Path(report["interprete"]).is_absolute()
            and report["timeout_segundos"] == config["limites"]["inventario"]
            and report["utilidad_sha256"] == digest(required(destination / "autoridades/project_test_inventory.py"))
            and report["entorno_sha256"] == digest(required(destination / "autoridades/process_environment.py")),
            "Procedencia del inventario inválida")
    require(process["estado"] == "finalizada" and process["codigo_salida"] == 0
            and process["politica_entorno"] == "evaluation"
            and process["limite_segundos"] == config["limites"]["inventario"], "Proceso de inventario inválido")
    require(process["directorio_trabajo"] == str(destination / "proyecto") and process["comando"] == [
        report["interprete"], "-B", str(destination / "autoridades/project_test_inventory.py"),
        "--reference", str(destination / "proyecto"), "--timeout", str(config["limites"]["inventario"])],
        "Comando del inventario incoherente")
    from project_test_inventory import state_hash
    before = parse_json(required(destination / "inventario/base_antes.json"))
    require(state_hash(before) == stamp["base_antes_sha256"],
            "Inventario de archivos alterado")
    require({name: {"sha256": item[2], "modo": item[0] & 0o7777} for name, item in before.items() if item[2] is not None}
            == {name: {"sha256": item["sha256"], "modo": int(item["modo_git"][-3:], 8)}
                for name, item in provenance["archivos_base"].items()}, "El inventario no procede de la base Git")
    return ids


def freeze_flow(root, destination, max_attempts, task="inspect-json"):
    config = task_config(task)
    suites = config["suites"]
    generic = config.get("configurable", False)
    if generic:
        provenance = freeze_declared_base(root, destination, config, contract=task.materials[config["contrato"]])
        provenance.update(tipo="proyecto_configurable_v1", configuracion_sha256=digest(task.raw),
                          origen_configuracion=config["origen_configuracion"])
        (destination / "tarea.json").write_bytes(task.raw)
    else:
        provenance = freeze_csv_base(root, destination, config) if config["ausente"] else freeze(root, destination)
    authority = destination / "autoridades"
    extra = (("project_test_inventory.py",) if generic else
             ("project_test_inventory.py", config["esquema"]) if config["ausente"] else ())
    for name in (*filter(None, suites.values()), *SUPPORT, *extra):
        target = authority / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if generic:
            require(name not in SUPPORT and name != "project_test_inventory.py" or name not in task.materials,
                    "Un material no puede sustituir una utilidad del controlador")
            target.write_bytes(task.materials[name] if name in task.materials else required(PROJECT / name))
        else:
            target.write_bytes(required(root / name))
    for name in (config["desarrollo"], config["revision"]):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(task.materials[name] if generic else required(root / name))
    if generic:
        for name in config["referencias"]:
            target = destination / "materiales" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(task.materials[name])
    for name in ("orchestrate_project.py", "project_flow.py", "project_flow_runner.py",
                 "repair_project.py", "review_project.py", "review_case.py",
                 *(("project_task_config.py",) if generic else ())):
        (destination / name).write_bytes(required(PROJECT / name))
    expected = provenance["pruebas_esperadas"]
    if config["ausente"] or generic:
        expected["regresion"] = inventory_base(destination, config, provenance)
    for kind, name in suites.items():
        if name:
            try:
                expected[kind] = static_test_ids(required(authority / name), "__main__")
            except SyntaxError as exc:
                if not generic:
                    raise
                raise ValueError(f"Sintaxis inválida en el evaluador {name}: {exc}") from exc
    require(all(ids and len(ids) == len(set(ids)) for ids in expected.values()), "Identidades de pruebas inválidas")
    provenance.update(tipo_flujo=config["tipo"], tarea_conocida=True)
    if generic:
        provenance["materiales_del_arbol_actual"] = {config["origen_configuracion"]: digest(task.raw),
            **{name: digest(data) for name, data in task.materials.items()}}
        provenance["utilidades_sha256"] = {name: digest(required(authority / name))
                                          for name in (*SUPPORT, "project_test_inventory.py")}
    elif config["ausente"]:
        provenance["materiales_del_arbol_actual"].update({
            name: digest(required(root / name)) for name in (
                *filter(None, suites.values()), *SUPPORT, *extra, config["desarrollo"], config["revision"])})
    write_json(destination / "procedencia.json", provenance)
    write_json(destination / "configuracion.json", flow_configuration(config, max_attempts))
    return provenance


def evaluation_command(frozen, workspace, log, kind, task="inspect-json"):
    suites = task_config(task)["suites"]
    command = [sys.executable, "-B", str(frozen / "project_flow_runner.py"),
               "--project", str(workspace), "--report", str(log / "pruebas.json")]
    if suites[kind]:
        command += ["--acceptance", str(frozen / "autoridades" / suites[kind])]
    if kind in ("hallazgos", "anidamiento"):
        command += ["--checks-output", str(log / "consultas")]
    return command


def flow_counts(raw, expected, process, stderr):
    counts = classify_report(raw, expected, process, stderr)
    report = parse_json(raw)
    require(type(report["version"]) is int and type(report["sesiones"]) is int,
            "Versión o sesiones inválidas")
    subtests = report["subtests"]
    require(isinstance(subtests, list), "Faltan subtests registrados")
    for item in subtests:
        require(set(item) == {"metodo", "subtest", "resultado"} and item["metodo"] in expected
                and isinstance(item["subtest"], str) and item["resultado"] in ("superado", "fallo", "error"),
                "Subtest inválido")
    for key, state in (("fallos", "fallo"), ("errores", "error")):
        require([{k: x[k] for k in ("metodo", "subtest")} for x in subtests if x["resultado"] == state]
                == [x for x in report[key] if x["subtest"] is not None], "Subtests incoherentes")
    return {**counts, "subtests_ejecutados": len(subtests)}


def evaluate_flow(workspace, frozen, directory, expected, results, progress, check, seal,
                  kinds=None, task="inspect-json"):
    config = task_config(task)
    kinds = tuple(config["suites"]) if kinds is None else kinds
    directory.mkdir()
    for kind in kinds:
        check()
        if progress:
            progress(f"Evaluación {directory.parent.name}: {kind}.")
        log = directory / kind
        log.mkdir()
        before = tree_state(workspace)
        candidate = (read_regular if config["ausente"] else required)(workspace / config["editable"])
        item = results[kind] = {"proceso": None, "clasificacion": "no_acreditada",
                                "candidato_sha256": digest(candidate)}
        if config["ausente"]:
            item["archivo_evaluado"] = file_identity(candidate)
        write_json(log / "proyecto_evaluado.json", before)
        try:
            try:
                item["proceso"] = run_process(evaluation_command(frozen, workspace, log, kind, task),
                                               workspace, log, config["limites"][kind], env_policy="evaluation")
            except (ProcessInterrupted, ProcessRecordError) as exc:
                item["proceso"] = exc.result
                raise
            check_process(item["proceso"])
            try:
                item.update(flow_counts(required(log / "pruebas.json"), expected[kind], item["proceso"],
                                        required(log / "stderr.txt").decode()))
            except (ValueError, KeyError, TypeError) as exc:
                raise StopProject(7, "evidencia_invalida", str(exc)) from exc
            if item["clasificacion"] == "error_pruebas":
                raise StopProject(3, "fallo_tecnico", f"Error técnico en {kind}")
        finally:
            item["workspace_intacto"] = tree_state(workspace) == before
            write_json(log / "evaluacion.json", item)
            seal(log)
            check()
            if not item["workspace_intacto"]:
                raise StopProject(6, "modificacion_no_permitida", "La evaluación alteró su copia")


def validate_delivery(delivery_run, project_root=PROJECT, *, allow_failures=False, task=None):
    """Vía explícita nueva: no relaja ni fabrica la procedencia histórica."""
    from review_project import Evidence, completed, integrity_flags

    delivery = Evidence(delivery_run)
    # Estructura fija del controlador; no seguir rutas que proponga un candidato.
    require(delivery.path.name == "evidencia" and delivery.path.parent.parent.name == "intentos",
            "Ubicación de entrega inválida")
    run = delivery.path.parents[2]
    reference, initial = Evidence(run / "referencia"), Evidence(run / "inicial")
    try:
        record = delivery.json("resultado.json")
        if record["tipo"] == "orquestacion_configurable_v1":
            from project_task_config import ConfiguredTask
            require(isinstance(task, ConfiguredTask) and task.reference_state is not None,
                    "La vía configurable requiere la referencia de confianza anterior al agente")
            require(reference.state == task.reference_state and reference.read("tarea.json") == task.raw,
                    "Configuración o autoridades congeladas alteradas")
            cfg = task_config(task)
        else:
            cfg = task_config(record["tarea"])
        generic = cfg.get("configurable", False)
        editable, suites, limits = cfg["editable"], cfg["suites"], cfg["limites"]
        base = reference.json("procedencia.json")
        config = reference.json("configuracion.json")
        require(record["tipo"] == base["tipo_flujo"] == config["tipo"] == cfg["tipo"]
                and record["tarea"] == base["tarea"] == cfg["tarea"]
                and record["registro"] == str(delivery.path), "Procedencia de entrega inválida")
        require(reference.state == record["referencia_sha256"]
                and initial.state == record["inicial_sha256"], "Referencias o evaluación inicial alteradas")
        require(config["suites"] == suites and config["limites_segundos"] == limits
                and type(config["max_intentos"]) is int and config["max_intentos"] in (1, 2)
                and config["archivo_editable"] == editable and config["incorporacion_automatica"] is False,
                "Configuración del flujo incoherente")
        if cfg["ausente"] or generic:
            require(config == flow_configuration(cfg, config["max_intentos"]),
                    "Configuración congelada alterada" if generic else "Configuración CSV alterada")
        integrity_flags(record["integridad"], ("alcance_respetado", "original_intacto", "referencia_intacta", "registros_intactos"))
        require(set(record["etapas_sha256"]) == {"desarrollo", "entrega", "evaluaciones"}, "Faltan etapas cerradas")
        for name, state in record["etapas_sha256"].items():
            require(delivery.subtree(name) == state, f"Etapa alterada: {name}")
        contract = reference.read("contrato.md")
        if generic:
            require(contract == task.materials[cfg["contrato"]]
                    and base["configuracion_sha256"] == digest(task.raw)
                    and base["editable_inicial"] == cfg["editable_inicial"]
                    and base["commit_base"] == cfg["base"], "Procedencia configurable alterada")
        else:
            require(contract == required(Path(project_root) / cfg["contrato"]),
                    "Contrato distinto de la autoridad")
            for name in (*filter(None, suites.values()), *SUPPORT,
                         *(("project_test_inventory.py", cfg["esquema"]) if cfg["ausente"] else ())):
                require(reference.read("autoridades/" + name) == required(Path(project_root) / name),
                        f"Autoridad distinta: {name}")
            for name in (cfg["desarrollo"], cfg["revision"]):
                require(reference.read(name) == required(Path(project_root) / name), "Prompt distinto")
            require(reference.read("project_flow_runner.py") == required(PROJECT / "project_flow_runner.py"),
                    "Adaptador de evaluación distinto")
        match = re.search(rb"Base: `([0-9a-f]{40})`", contract)
        require(match and match[1].decode() == base["commit_base"], "Base distinta del contrato")
        if cfg["ausente"] and not generic:
            require(base["commit_base"] == cfg["base"] and base["editable_inicial"] == file_identity(None),
                    "Base o ausencia original CSV no acreditadas")
        with process_environment() as environment:
            git_tree = subprocess.run(["git", "-C", str(project_root), "ls-tree", "-rz", base["commit_base"]],
                                      check=True, capture_output=True, timeout=10, env=environment).stdout
        files = {}
        for entry in git_tree.split(b"\0"):
            if not entry:
                continue
            metadata, raw_name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            name = raw_name.decode()
            if excluded(name):
                continue
            require(kind == "blob" and mode in ("100644", "100755"), "Base no regular")
            data = reference.read("proyecto/" + name)
            require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == oid,
                    "Base distinta de Git")
            require(reference.state["proyecto/" + name]["modo"] == int(mode[-3:], 8), "Modo de base alterado")
            files[name] = {"objeto_git": oid, "sha256": digest(data), "modo_git": mode}
        require(files == base["archivos_base"] and set(files) == {
            n for n, item in reference.subtree("proyecto").items() if item["tipo"] == "archivo"}, "Base incompleta")
        expected = {kind: static_test_ids(reference.read("autoridades/" + name), "__main__")
                    for kind, name in suites.items() if name}
        expected["regresion"] = (validate_inventory(reference.path, cfg, base) if cfg["ausente"] or generic else
            sorted(identity for name in files
                   if Path(name).parent == Path("tests") and Path(name).match("test*.py")
                   for identity in static_test_ids(reference.read("proyecto/" + name), Path(name).stem)))
        require(expected == base["pruebas_esperadas"], "Evaluaciones esperadas incompletas")
        original = None if cfg["ausente"] else reference.read("proyecto/" + editable)
        candidate = delivery.read("entrega/" + editable)
        if cfg["ausente"]:
            require(editable not in reference.subtree("proyecto"), "Editable presente en la base")
            require(delivery.json("entrega/partida.json") == record["partida"], "Estado de partida incoherente")
            if record["partida"] == file_identity(None):
                require("entrega/partida.py" not in delivery.state, "Partida ausente fabricada como archivo")
                starting = None
            else:
                starting = delivery.read("entrega/partida.py")
                require(record["partida"] == file_identity(starting), "Partida mezclada")
        else:
            starting = delivery.read("entrega/partida.py")
        require((cfg["ausente"] or generic or candidate) and digest(candidate) == record["candidato_sha256"]
                and digest(starting) == record["partida_sha256"], "Candidato mezclado")
        number = record["numero"]
        require(type(number) is int and 1 <= number <= config["max_intentos"]
                and delivery.path.parent.name == str(number), "Intento inválido")
        if number == 1:
            require(starting == original and record["anterior_sha256"] is None, "Partida inicial distinta")
        else:
            previous = Evidence(run / "intentos" / str(number - 1) / "evidencia")
            require(previous.state == record["anterior_sha256"]
                    and starting == previous.read("entrega/" + editable), "Continuidad de candidato rota")
        for name, source in (("candidato.diff", original), ("anterior.diff", starting)):
            require(delivery.read("entrega/" + name) == delivery_diff(source, candidate, editable),
                    "Diff incoherente")
        workspace = reference.subtree("proyecto")
        workspace[editable] = {"tipo": "archivo", "modo": 0o644 if cfg["ausente"] else workspace[editable]["modo"],
                               "sha256": digest(candidate)}
        require(delivery.json("entrega/workspace_despues.json") == workspace, "Alcance de entrega inválido")
        before = reference.subtree("proyecto")
        if starting is not None:
            before[editable] = {**workspace[editable], "sha256": digest(starting)}
        changes = {name: {"antes": before.get(name), "despues": workspace.get(name)}
                   for name in before.keys() | workspace.keys() if before.get(name) != workspace.get(name)}
        require(delivery.json("entrega/cambios.json") == changes, "Cambios de entrega incoherentes")
        agent = record["desarrollo"]
        require(agent["reserva_invocacion"] is True and type(agent["agente"]["invocaciones"]) is int
                and agent["agente"]["invocaciones"] == 1, "Desarrollo no acreditado")
        process = delivery.json("desarrollo/resultado.json")
        completed(process)
        require(process == agent["agente"]["proceso"] and process["codigo_salida"] == 0
                and process["limite_segundos"] == limits["desarrollador"]
                and process["politica_entorno"] == "codex", "Proceso de desarrollo inválido")
        reservation = Evidence(run / "reservas" / f"{number}-desarrollador")
        saved_reservation = reservation.json("reserva.json")
        require(saved_reservation["rol"] == "desarrollador" and saved_reservation["intento"] == number
                and saved_reservation["estado"] == "reservada_antes_de_invocar"
                and saved_reservation["fecha_utc"] <= process["inicio_utc"], "Falta reserva previa al desarrollo")
        require(set(record["evaluaciones"]) == set(suites), "Evaluaciones incompletas")

        def validate_evaluation(source, prefix, kind, wanted, saved=None):
            item = source.json(prefix + "/evaluacion.json")
            process = source.json(prefix + "/resultado.json")
            completed(process)
            require(item["proceso"] == process and (saved is None or item == saved)
                    and item["workspace_intacto"] is True and source.json(prefix + "/proyecto_evaluado.json") == wanted
                    and item["candidato_sha256"] == wanted.get(editable, {}).get("sha256"), "Evaluación de otra entrega")
            if cfg["ausente"]:
                require(item["archivo_evaluado"] == wanted.get(editable, file_identity(None)),
                        "Estado de archivo evaluado incoherente")
            command = evaluation_command(reference.path, Path(process["directorio_trabajo"]), source.path / prefix, kind,
                                         task if generic else cfg["tarea"])
            # El intérprete absoluto queda registrado; no exigir la misma instalación al consultar.
            require(Path(process["comando"][0]).is_absolute(), "Intérprete inválido")
            command[0] = process["comando"][0]
            require(process["comando"] == command and process["limite_segundos"] == limits[kind]
                    and process["politica_entorno"] == "evaluation", "Comando o límites distintos")
            counts = flow_counts(source.read(prefix + "/pruebas.json"), expected[kind], process,
                                 source.read(prefix + "/stderr.txt").decode())
            source.read(prefix + "/stdout.txt")
            require(all(item.get(k) == v for k, v in counts.items()), "Recuentos incoherentes")
            require(all(type(item[k]) is int for k in counts if k != "clasificacion"),
                    "Recuentos de evaluación inválidos")
            return counts

        for kind in ("aceptacion", "regresion"):
            counts = validate_evaluation(initial, kind, kind, reference.subtree("proyecto"))
            require(counts["clasificacion"] == ("superadas" if kind == "regresion" else "fallos_asercion"),
                    "Preparación no acreditada")
        if cfg["ausente"] or generic:
            require(preparation_authorized({kind: initial.json(kind + "/evaluacion.json")
                                            for kind in ("aceptacion", "regresion")},
                                           initial.read("aceptacion/stderr.txt"), cfg),
                    "Precondición inicial no acreditada" if generic else "La preparación no acredita funcionalidad ausente")
        for kind in suites:
            counts = validate_evaluation(delivery, "evaluaciones/" + kind, kind, workspace, record["evaluaciones"][kind])
            require(counts["clasificacion"] in (("superadas", "fallos_asercion") if allow_failures else ("superadas",)),
                    "La entrega no supera todas las evaluaciones")
        sources = (delivery, reference, initial, reservation)
        if number > 1:
            sources += (previous,)
        require(all(source.unchanged() for source in sources), "Evidencia alterada durante la validación")
        return record, sources
    except (KeyError, TypeError, AttributeError, SyntaxError, IndexError, OverflowError) as exc:
        raise ValueError(f"Evidencia incompleta o inválida: {exc}") from exc


def delivery_review_evidence(delivery_run, project_root, *, task=None):
    from review_project import review_dependencies
    record, sources = validate_delivery(delivery_run, project_root, task=task)
    delivery, reference = sources[:2]
    cfg = task_config(task if task is not None else record["tarea"])
    editable = cfg["editable"]
    candidate = delivery.read("entrega/" + editable)
    materials = {"contrato.md": reference.read("contrato.md"), editable: candidate,
                 "candidato.diff": delivery.read("entrega/candidato.diff"),
                 "evaluacion/evaluador_revisado.py": reference.read("autoridades/" + cfg["suites"]["aceptacion"])}
    if cfg.get("configurable"):
        materials.update({"configuracion_tarea.json": reference.read("tarea.json"),
                          "estado_inicial.json": (json.dumps(cfg["editable_inicial"]) + "\n").encode()})
        materials.update({"referencias/" + name: reference.read("materiales/" + name) for name in cfg["referencias"]})
        dependency_sources = [candidate]
        if not cfg["ausente"]:
            original = reference.read("proyecto/" + editable)
            materials["original/" + editable] = original
            dependency_sources.append(original)
    elif cfg["ausente"]:
        materials.update({"esquema_003.md": reference.read("autoridades/" + cfg["esquema"]),
                          "ausencia_original.json": (json.dumps(file_identity(None)) + "\n").encode(),
                          "partida.json": delivery.read("entrega/partida.json"),
                          "anterior.diff": delivery.read("entrega/anterior.diff")})
        dependency_sources = [candidate]
    else:
        original = reference.read("proyecto/" + editable)
        materials.update({"original/inspect_run.py": original,
                          "pruebas/test_inspect_run.py": reference.read("proyecto/tests/test_inspect_run.py")})
        dependency_sources = [candidate, original, materials["pruebas/test_inspect_run.py"]]
    try:
        materials.update(review_dependencies(dependency_sources,
            reference.json("procedencia.json")["archivos_base"], lambda n: reference.read("proyecto/" + n),
            **({"editable": editable} if cfg.get("configurable") else {})))
    except SyntaxError as exc:
        if not cfg.get("configurable"):
            raise
        raise ValueError(f"Sintaxis inválida en los materiales de revisión: {exc}") from exc
    evidence = dict(materials)
    for name, item in delivery.state.items():
        if item["tipo"] == "archivo":
            evidence["evidencia/" + name] = delivery.read(name)
    authorization = {"tipo": cfg["tipo"], "entrega": str(delivery.path),
                     "commit_base": reference.json("procedencia.json")["commit_base"],
                     "candidato_sha256": record["candidato_sha256"], "referencia_sha256": reference.state,
                     "evaluaciones": record["evaluaciones"]}
    if cfg["ausente"] or cfg.get("configurable"):
        authorization["tarea"] = cfg["tarea"]
    return evidence, authorization, sources


def delivery_review_materials(evidence, authorization, *, task=None):
    from review_project import response_schema
    cfg = task_config(task if task is not None else authorization.get("tarea", "inspect-json"))
    materials = {n: data for n, data in evidence.items() if not n.startswith("evidencia/")}
    stages = {}
    mapping = {}
    for kind in cfg["suites"]:
        prefix = "evidencia/evaluaciones/" + kind + "/"
        item = authorization["evaluaciones"][kind]
        stages[kind] = {k: v for k, v in item.items() if k != "proceso"}
        identities = parse_json(evidence[prefix + "pruebas.json"])["metodos"]
        stages[kind]["identidades_sha256"] = digest(json.dumps(identities, ensure_ascii=False).encode())
        mapping[kind] = {n: digest(evidence[prefix + n]) for n in ("evaluacion.json", "resultado.json", "pruebas.json", "stdout.txt", "stderr.txt")}
    summary = {"tipo": "resumen_evidencia_validada_no_dictamen", "procedencia": cfg["tipo"],
               "commit_base": authorization["commit_base"], "candidato_sha256": authorization["candidato_sha256"],
               "evaluaciones": stages, "fuentes_sha256": mapping, "regresion_reutilizada": False}
    if "orquestacion" in authorization:
        summary.update(regresion_reutilizada=True, evaluaciones_nuevas=False,
                       intento_origen=authorization["intento"],
                       alcance="Evaluaciones conservadas de este candidato exacto, verificadas por lectura. "
                               "No sustituyen la revisión ni demuestran corrección general.")
    materials["resumen_evidencia.json"] = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode()
    materials["respuesta.schema.json"] = json.dumps(response_schema(
        len(materials[cfg["editable"]].splitlines()), editable=cfg["editable"])).encode()
    return materials, {"version": 1, "fuentes_sha256": mapping,
                       "materiales": {n: digest(data) for n, data in materials.items()}}

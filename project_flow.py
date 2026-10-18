"""Referencias, evaluación y procedencia exclusiva del flujo acotado inspect-json."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from case_evidence import digest, parse_json, require, unified_diff
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


def freeze_flow(root, destination, max_attempts):
    provenance = freeze(root, destination)
    authority = destination / "autoridades"
    for name in (*filter(None, SUITES.values()), *SUPPORT):
        target = authority / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(required(root / name))
    for name in (DEVELOPER_PROMPT, REVIEW_PROMPT):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(required(root / name))
    for name in ("orchestrate_project.py", "project_flow.py", "project_flow_runner.py",
                 "repair_project.py", "review_project.py", "review_case.py"):
        (destination / name).write_bytes(required(PROJECT / name))
    expected = provenance["pruebas_esperadas"]
    for kind, name in SUITES.items():
        if name:
            expected[kind] = static_test_ids(required(authority / name), "__main__")
    require(all(ids and len(ids) == len(set(ids)) for ids in expected.values()), "Identidades de pruebas inválidas")
    provenance.update(tipo_flujo=TYPE, tarea_conocida=True)
    write_json(destination / "procedencia.json", provenance)
    write_json(destination / "configuracion.json", {
        "tipo": TYPE, "max_intentos": max_attempts, "limites_segundos": LIMITS,
        "archivo_editable": EDITABLE, "suites": SUITES, "politicas_entorno": ["evaluation", "codex"],
        "incorporacion_automatica": False, "reanudacion": False})
    return provenance


def evaluation_command(frozen, workspace, log, kind):
    command = [sys.executable, "-B", str(frozen / "project_flow_runner.py"),
               "--project", str(workspace), "--report", str(log / "pruebas.json")]
    if SUITES[kind]:
        command += ["--acceptance", str(frozen / "autoridades" / SUITES[kind])]
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
                  kinds=tuple(SUITES)):
    directory.mkdir()
    for kind in kinds:
        check()
        if progress:
            progress(f"Evaluación {directory.parent.name}: {kind}.")
        log = directory / kind
        log.mkdir()
        before = tree_state(workspace)
        item = results[kind] = {"proceso": None, "clasificacion": "no_acreditada",
                                "candidato_sha256": digest(required(workspace / EDITABLE))}
        write_json(log / "proyecto_evaluado.json", before)
        try:
            try:
                item["proceso"] = run_process(evaluation_command(frozen, workspace, log, kind),
                                               workspace, log, LIMITS[kind], env_policy="evaluation")
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


def validate_delivery(delivery_run, project_root=PROJECT, *, allow_failures=False):
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
        base = reference.json("procedencia.json")
        config = reference.json("configuracion.json")
        require(record["tipo"] == base["tipo_flujo"] == config["tipo"] == TYPE
                and record["tarea"] == base["tarea"] == "inspect-json"
                and record["registro"] == str(delivery.path), "Procedencia de entrega inválida")
        require(reference.state == record["referencia_sha256"]
                and initial.state == record["inicial_sha256"], "Referencias o evaluación inicial alteradas")
        require(config["suites"] == SUITES and config["limites_segundos"] == LIMITS
                and type(config["max_intentos"]) is int and config["max_intentos"] in (1, 2)
                and config["archivo_editable"] == EDITABLE and config["incorporacion_automatica"] is False,
                "Configuración del flujo incoherente")
        integrity_flags(record["integridad"], ("alcance_respetado", "original_intacto", "referencia_intacta", "registros_intactos"))
        require(set(record["etapas_sha256"]) == {"desarrollo", "entrega", "evaluaciones"}, "Faltan etapas cerradas")
        for name, state in record["etapas_sha256"].items():
            require(delivery.subtree(name) == state, f"Etapa alterada: {name}")
        contract = reference.read("contrato.md")
        require(contract == required(Path(project_root) / "tasks/003-inspect-run-json.md"),
                "Contrato distinto de la autoridad")
        for name in (*filter(None, SUITES.values()), *SUPPORT):
            require(reference.read("autoridades/" + name) == required(Path(project_root) / name),
                    f"Autoridad distinta: {name}")
        for name in (DEVELOPER_PROMPT, REVIEW_PROMPT):
            require(reference.read(name) == required(Path(project_root) / name), "Prompt distinto")
        require(reference.read("project_flow_runner.py") == required(PROJECT / "project_flow_runner.py"),
                "Adaptador de evaluación distinto")
        match = re.search(rb"Base: `([0-9a-f]{40})`", contract)
        require(match and match[1].decode() == base["commit_base"], "Base distinta del contrato")
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
                    for kind, name in SUITES.items() if name}
        expected["regresion"] = sorted(identity for name in files
            if Path(name).parent == Path("tests") and Path(name).match("test*.py")
            for identity in static_test_ids(reference.read("proyecto/" + name), Path(name).stem))
        require(expected == base["pruebas_esperadas"], "Evaluaciones esperadas incompletas")
        original, candidate = reference.read("proyecto/" + EDITABLE), delivery.read("entrega/" + EDITABLE)
        starting = delivery.read("entrega/partida.py")
        require(candidate and digest(candidate) == record["candidato_sha256"]
                and digest(starting) == record["partida_sha256"], "Candidato mezclado")
        number = record["numero"]
        require(type(number) is int and 1 <= number <= config["max_intentos"]
                and delivery.path.parent.name == str(number), "Intento inválido")
        if number == 1:
            require(starting == original and record["anterior_sha256"] is None, "Partida inicial distinta")
        else:
            previous = Evidence(run / "intentos" / str(number - 1) / "evidencia")
            require(previous.state == record["anterior_sha256"]
                    and starting == previous.read("entrega/" + EDITABLE), "Continuidad de candidato rota")
        for name, source in (("candidato.diff", original), ("anterior.diff", starting)):
            require(delivery.read("entrega/" + name) == unified_diff(source, candidate, "a/inspect_run.py", "b/inspect_run.py"),
                    "Diff incoherente")
        workspace = reference.subtree("proyecto")
        workspace[EDITABLE] = {**workspace[EDITABLE], "sha256": digest(candidate)}
        require(delivery.json("entrega/workspace_despues.json") == workspace, "Alcance de entrega inválido")
        before = reference.subtree("proyecto")
        before[EDITABLE] = {**before[EDITABLE], "sha256": digest(starting)}
        changes = {name: {"antes": before[name], "despues": workspace[name]}
                   for name in before if before[name] != workspace[name]}
        require(delivery.json("entrega/cambios.json") == changes, "Cambios de entrega incoherentes")
        agent = record["desarrollo"]
        require(agent["reserva_invocacion"] is True and type(agent["agente"]["invocaciones"]) is int
                and agent["agente"]["invocaciones"] == 1, "Desarrollo no acreditado")
        process = delivery.json("desarrollo/resultado.json")
        completed(process)
        require(process == agent["agente"]["proceso"] and process["codigo_salida"] == 0
                and process["limite_segundos"] == LIMITS["desarrollador"]
                and process["politica_entorno"] == "codex", "Proceso de desarrollo inválido")
        reservation = Evidence(run / "reservas" / f"{number}-desarrollador")
        saved_reservation = reservation.json("reserva.json")
        require(saved_reservation["rol"] == "desarrollador" and saved_reservation["intento"] == number
                and saved_reservation["estado"] == "reservada_antes_de_invocar"
                and saved_reservation["fecha_utc"] <= process["inicio_utc"], "Falta reserva previa al desarrollo")
        require(set(record["evaluaciones"]) == set(SUITES), "Evaluaciones incompletas")

        def validate_evaluation(source, prefix, kind, wanted, saved=None):
            item = source.json(prefix + "/evaluacion.json")
            process = source.json(prefix + "/resultado.json")
            completed(process)
            require(item["proceso"] == process and (saved is None or item == saved)
                    and item["workspace_intacto"] is True and source.json(prefix + "/proyecto_evaluado.json") == wanted
                    and item["candidato_sha256"] == wanted[EDITABLE]["sha256"], "Evaluación de otra entrega")
            command = evaluation_command(reference.path, Path(process["directorio_trabajo"]), source.path / prefix, kind)
            # El intérprete absoluto queda registrado; no exigir la misma instalación al consultar.
            require(Path(process["comando"][0]).is_absolute(), "Intérprete inválido")
            command[0] = process["comando"][0]
            require(process["comando"] == command and process["limite_segundos"] == LIMITS[kind]
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
        for kind in SUITES:
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


def delivery_review_evidence(delivery_run, project_root):
    from review_project import review_dependencies
    record, sources = validate_delivery(delivery_run, project_root)
    delivery, reference = sources[:2]
    original = reference.read("proyecto/" + EDITABLE)
    candidate = delivery.read("entrega/" + EDITABLE)
    materials = {"contrato.md": reference.read("contrato.md"), EDITABLE: candidate,
                 "original/inspect_run.py": original, "candidato.diff": delivery.read("entrega/candidato.diff"),
                 "pruebas/test_inspect_run.py": reference.read("proyecto/tests/test_inspect_run.py"),
                 "evaluacion/evaluador_revisado.py": reference.read("autoridades/" + ACCEPTANCE)}
    materials.update(review_dependencies([candidate, original, materials["pruebas/test_inspect_run.py"]],
        reference.json("procedencia.json")["archivos_base"], lambda n: reference.read("proyecto/" + n)))
    evidence = dict(materials)
    for name, item in delivery.state.items():
        if item["tipo"] == "archivo":
            evidence["evidencia/" + name] = delivery.read(name)
    authorization = {"tipo": TYPE, "entrega": str(delivery.path),
                     "commit_base": reference.json("procedencia.json")["commit_base"],
                     "candidato_sha256": record["candidato_sha256"], "referencia_sha256": reference.state,
                     "evaluaciones": record["evaluaciones"]}
    return evidence, authorization, sources


def delivery_review_materials(evidence, authorization):
    from review_project import response_schema
    materials = {n: data for n, data in evidence.items() if not n.startswith("evidencia/")}
    stages = {}
    mapping = {}
    for kind in SUITES:
        prefix = "evidencia/evaluaciones/" + kind + "/"
        item = authorization["evaluaciones"][kind]
        stages[kind] = {k: v for k, v in item.items() if k != "proceso"}
        identities = parse_json(evidence[prefix + "pruebas.json"])["metodos"]
        stages[kind]["identidades_sha256"] = digest(json.dumps(identities, ensure_ascii=False).encode())
        mapping[kind] = {n: digest(evidence[prefix + n]) for n in ("evaluacion.json", "resultado.json", "pruebas.json", "stdout.txt", "stderr.txt")}
    summary = {"tipo": "resumen_evidencia_validada_no_dictamen", "procedencia": TYPE,
               "commit_base": authorization["commit_base"], "candidato_sha256": authorization["candidato_sha256"],
               "evaluaciones": stages, "fuentes_sha256": mapping, "regresion_reutilizada": False}
    if "orquestacion" in authorization:
        summary.update(regresion_reutilizada=True, evaluaciones_nuevas=False,
                       intento_origen=authorization["intento"],
                       alcance="Evaluaciones conservadas de este candidato exacto, verificadas por lectura. "
                               "No sustituyen la revisión ni demuestran corrección general.")
    materials["resumen_evidencia.json"] = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode()
    materials["respuesta.schema.json"] = json.dumps(response_schema(len(materials[EDITABLE].splitlines()))).encode()
    return materials, {"version": 1, "fuentes_sha256": mapping,
                       "materiales": {n: digest(data) for n, data in materials.items()}}

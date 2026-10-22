"""Revisa una reparación aceptada sin ejecutar el candidato ni al desarrollador."""

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from uuid import uuid4

from repair_case import (
    AGENT_TIMEOUT_SECONDS, PREFLIGHT_TIMEOUT_SECONDS, digest, inventory,
    read_regular, run_process, timestamp, write_json,
    ProcessRecordError,
)
from run_case import utc_timestamp
from case_config import get_case, reference_paths, reviewer_prompt_path
from case_evidence import (
    require, parse_json, snapshot_tree, reference_test_ids, validate_test_report,
    classify_test_report, test_report_rows, unified_diff,
)


CODEX_EXECUTABLE = "codex"
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
INTEGRITY_KEYS = (
    "pruebas_agente_intactas", "originales_intactos", "referencia_intacta",
    "pruebas_iniciales_pruebas_intactas", "pruebas_iniciales_implementacion_intacta",
    "pruebas_posteriores_pruebas_intactas", "pruebas_posteriores_implementacion_intacta",
)
MATERIALS = {
    "contrato.md": "referencia/contrato.md",
    "original.py": "referencia/solution.py",
    "candidato.py": "candidato.py",
    "candidato.diff": "candidato.diff",
    "test_solution.py": "referencia/test_solution.py",
    "posterior.json": "posterior/resultado.json",
    "posterior.stdout.txt": "posterior/stdout.txt",
    "posterior.stderr.txt": "posterior/stderr.txt",
}


def recorded_case(run_dir, snapshot):
    """Leer el caso del resumen ya inventariado, sin inferirlo del nombre de carpeta."""
    content = read_regular(run_dir / "resultado.json")
    require(content is not None and digest(content) == snapshot["resultado.json"],
            "El resumen cambió durante la lectura del caso")
    result = parse_json(content)
    require(isinstance(result, dict), "Resumen inválido")
    case_id = result.get("caso")
    get_case(case_id)
    return case_id


def validate_repair(run_dir, project_root, *, allow_test_failure=False, expected_case=None, _seen=()):
    """Contrastar evidencia conservada; nunca importar ni ejecutar sus archivos."""
    run_dir = Path(run_dir).absolute()
    require(run_dir not in _seen and len(_seen) < 2, "Continuidad cíclica o más de dos intentos")
    snapshot = snapshot_tree(run_dir)

    def read(name):
        require(name in snapshot, f"Falta evidencia requerida: {name}")
        content = read_regular(run_dir / name)
        require(content is not None and digest(content) == snapshot[name],
                f"Evidencia alterada durante la lectura: {name}")
        return content

    try:
        result = parse_json(read("resultado.json"))
        case_id = result["caso"]
        sources = reference_paths(project_root, case_id)
        require(expected_case is None or case_id == expected_case,
                "La reparación pertenece a otro caso")
        accepted = (result["aceptada"] is True
                    and result["estado"] == "supera_las_pruebas_disponibles"
                    and type(result["codigo_salida"]) is int and result["codigo_salida"] == 0)
        failed = (allow_test_failure and result["aceptada"] is False
                  and result["estado"] == "no_supera_pruebas"
                  and type(result["codigo_salida"]) is int and result["codigo_salida"] == 1)
        require((accepted or failed)
                and result["candidato_disponible"] is True
                and result["errores_controlador"] == [], "La reparación no está aceptada")
        require(all(result["integridad"][key] is True for key in INTEGRITY_KEYS),
                "La reparación no acredita toda la integridad exigida")
        require(all(value is True for value in result["integridad"].values()),
                "El registro contiene una comprobación de integridad fallida")
        hashes = result["sha256"]
        require(hashes["originales"] == inventory(project_root),
                "Los originales actuales no coinciden con los hashes de la reparación")
        for filename, path in sources.items():
            source = path.relative_to(project_root).as_posix()
            reference = read("referencia/" + filename)
            require(digest(reference) == hashes["referencia"][filename] == hashes["originales"][source],
                    f"Referencia o hash inconsistente: {filename}")
        candidate = read("candidato.py")
        require(digest(candidate) == hashes["candidato"], "Hash del candidato inconsistente")
        tests = read("referencia/test_solution.py")
        agent_tests = read("agente/test_solution_despues.py")
        require(agent_tests == tests and digest(agent_tests) == hashes["pruebas_agente"],
                "Las pruebas entregadas al desarrollador no coinciden con la referencia")
        agent = parse_json(read("agente/resultado.json"))
        require(agent == result["agente"] and agent["estado"] == "finalizada"
                and type(agent["codigo_salida"]) is int and agent["codigo_salida"] == 0
                and type(agent["invocaciones"]) is int and agent["invocaciones"] == 1,
                "Resultado del desarrollador inconsistente")
        original = read("referencia/solution.py")
        starting = original
        new_format = result.get("version_registro") == 2
        require(result.get("version_registro", 1) in (1, 2), "Versión de registro desconocida")
        if new_format:
            starting = read("partida.py")
            require(digest(starting) == hashes["partida"], "Hash de partida inconsistente")
            require(digest(read("feedback.json")) == hashes["feedback"], "Feedback alterado")
            feedback = parse_json(read("feedback.json"))
            provenance = result["procedencia"]
            if provenance == {"tipo": "benchmark"}:
                require(starting == original and feedback is None, "Partida original inconsistente")
            else:
                expected_start, expected_feedback, expected_origin = correction_context(
                    Path(provenance["reparacion_previa"]),
                    Path(provenance["revision_previa"]) if provenance.get("revision_previa") else None,
                    project_root, expected_case=case_id, _seen=_seen + (run_dir,),
                )
                require(starting == expected_start and feedback == expected_feedback
                        and provenance == expected_origin, "Continuidad o feedback inconsistente")
            require(read("partida.diff") == unified_diff(
                original, starting, "referencia/solution.py", "partida.py"), "Diff de partida inconsistente")
            require(read("correccion.diff") == unified_diff(
                starting, candidate, "partida.py", "candidato/solution.py"), "Diff de corrección inconsistente")
        for phase, key, implementation in (
            ("inicial", "pruebas_iniciales", starting),
            ("posterior", "pruebas_posteriores", candidate),
        ):
            phase_result = parse_json(read(phase + "/resultado.json"))
            require(phase_result == result[key], f"Resumen de pruebas inconsistente: {phase}")
            require(phase_result["estado"] in ("finalizada", "tiempo_agotado")
                    and type(phase_result["codigo_salida"]) is int
                    and phase_result["pruebas_intactas"] is True
                    and phase_result["implementacion_intacta"] is True,
                    f"Evaluación incompleta: {phase}")
            command = phase_result["comando"]
            cwd = phase_result["directorio_trabajo"]
            require(isinstance(cwd, str) and Path(cwd).is_absolute()
                    and isinstance(command, list) and len(command) == 10
                    and isinstance(command[0], str)
                    and command[1:] == ["-B", "-m", "unittest", "discover", "-s", cwd,
                                        "-p", "test_solution.py", "-v"],
                    f"Comando de evaluación ausente o inconsistente: {phase}")
            require(read(phase + "/workspace/solution.py") == implementation,
                    f"La implementación evaluada no coincide: {phase}")
            require(read(phase + "/workspace/test_solution.py") == tests,
                    f"Las pruebas evaluadas no coinciden: {phase}")
            read(phase + "/stdout.txt")
            read(phase + "/stderr.txt")
        test_report_rows(tests, read("inicial/stderr.txt").decode("utf-8"))
        after = result["pruebas_posteriores"]
        require(after["estado"] == "finalizada" and type(after["codigo_salida"]) is int
                and after["codigo_salida"] == (0 if accepted else 1),
                "La evaluación posterior no coincide con el resultado")
        report = read("posterior/stderr.txt").decode("utf-8")
        classification = classify_test_report(tests, report, after["codigo_salida"])
        require(classification == ("superadas" if accepted else "fallos_asercion"),
                "El resultado de las pruebas no permite esta transición")
        expected_diff = unified_diff(original, candidate,
                                     "referencia/solution.py" if new_format else "inicial/solution.py",
                                     "candidato/solution.py")
        require(read("candidato.diff") == expected_diff, "El diff no corresponde al candidato")
        materials = {name: read(source) for name, source in MATERIALS.items()}
        require(snapshot_tree(run_dir) == snapshot, "El registro cambió durante la validación")
        return materials, snapshot
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Estructura de evidencia incompleta o inválida: {exc}") from exc


def validate_review_record(run_dir, source_run, project_root):
    """Comprobar un dictamen ya registrado, sin volver a invocar al revisor."""
    try:
        source_materials, source_snapshot = validate_repair(source_run, project_root)
        case_id = recorded_case(source_run, source_snapshot)
        snapshot = snapshot_tree(run_dir)
        result = parse_json((run_dir / "resultado.json").read_bytes())
        origin = parse_json((run_dir / "origen.json").read_bytes())
        require(result["reparacion_origen"] == origin["registro_reparacion"] == str(source_run),
                "Origen de revisión inconsistente")
        require(origin["registro_sha256"] == source_snapshot, "Reparación de origen alterada")
        require(result["caso"] == case_id and result["evidencia_previa_valida"] is True
                and result["error_respuesta"] is None and result["errores_controlador"] == [],
                "Evidencia de revisión inválida")
        keys = {"workspace_intacto", "registro_reparacion_intacto", "materiales_conservados_intactos",
                "originales_intactos", "instrucciones_intactas", "entrada_intacta"}
        require(keys <= result["integridad"].keys()
                and all(value is True for value in result["integridad"].values()),
                "Integridad de revisión inválida")
        hashes = snapshot_tree(run_dir / "materiales")
        require(hashes == origin["materiales_sha256"] == result["materiales_sha256"]
                == result["materiales_sha256_despues"], "Materiales de revisión alterados")
        for name, content in source_materials.items():
            require(read_regular(run_dir / "materiales" / name) == content,
                    f"Material de revisión distinto: {name}")
        prompt = read_regular(reviewer_prompt_path(project_root, case_id))
        require(digest(prompt) == origin["instrucciones_sha256"]
                and prompt == read_regular(run_dir / "revisor/entrada.txt"), "Instrucciones alteradas")
        agent = result["revisor"]
        require(agent == parse_json((run_dir / "revisor/resultado.json").read_bytes())
                and agent["estado"] == "finalizada" and type(agent["codigo_salida"]) is int
                and agent["codigo_salida"] == 0 and type(agent["invocaciones"]) is int
                and agent["invocaciones"] == 1, "Proceso de revisión inconsistente")
        verdict = validate_verdict((run_dir / "revisor/respuesta_original.txt").read_bytes(),
                                  len((source_run / "candidato.py").read_bytes().splitlines()))
        require(verdict == result["dictamen_modelo"]
                == parse_json((run_dir / "dictamen_validado.json").read_bytes()), "Dictamen alterado")
        code, decision = decide(result)
        require(type(result["codigo_salida"]) is int and result["codigo_salida"] == code
                and result["decision_controlador"] == decision and result["aprobada"] is (code == 0),
                "Decisión de revisión inconsistente")
        require(snapshot_tree(run_dir) == snapshot, "La revisión cambió durante la lectura")
        return result, snapshot
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Revisión incompleta: {exc}") from exc


def correction_context(previous_run, previous_review, project_root, *, expected_case=None, _seen=()):
    """Solo evidencia validada puede motivar la única corrección permitida."""
    materials, hashes = validate_repair(previous_run, project_root, allow_test_failure=True,
                                       expected_case=expected_case, _seen=_seen)
    previous = parse_json((previous_run / "resultado.json").read_bytes())
    review_hashes = None
    if previous_review is None:
        require(previous["estado"] == "no_supera_pruebas", "Faltan fallos que justifiquen corregir")
        feedback = {"tipo": "fallos_pruebas", "resultado": previous["pruebas_posteriores"],
                    "stdout": materials["posterior.stdout.txt"].decode("utf-8"),
                    "stderr": materials["posterior.stderr.txt"].decode("utf-8")}
    else:
        require(previous["aceptada"] is True, "La reparación revisada no estaba aceptada")
        review, review_hashes = validate_review_record(previous_review, previous_run, project_root)
        require(review["decision_controlador"] == "cambios_solicitados", "La revisión no solicita cambios")
        feedback = {"tipo": "solicitar_cambios", "dictamen": review["dictamen_modelo"]}
    provenance = {
        "tipo": "candidato_previo", "reparacion_previa": str(previous_run),
        "reparacion_previa_sha256": hashes,
        "revision_previa": str(previous_review) if previous_review else None,
        "revision_previa_sha256": review_hashes,
    }
    return materials["candidato.py"], feedback, provenance


def response_schema(line_count):
    return {
        "type": "object", "additionalProperties": False,
        "required": ["decision", "resumen", "hallazgos"],
        "properties": {
            "decision": {"type": "string", "enum": ["aprobar", "solicitar_cambios"]},
            "resumen": {"type": "string", "minLength": 1},
            "hallazgos": {
                "type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["archivo", "linea", "explicacion", "ejemplo"],
                    "properties": {
                        "archivo": {"type": "string", "enum": ["candidato.py"]},
                        "linea": {"type": "integer", "minimum": 1, "maximum": line_count},
                        "explicacion": {"type": "string", "minLength": 1},
                        "ejemplo": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def validate_verdict(raw, line_count):
    verdict = parse_json(raw)
    require(isinstance(verdict, dict) and set(verdict) == {"decision", "resumen", "hallazgos"},
            "Se requiere un objeto con decision, resumen y hallazgos, sin campos adicionales")
    require(verdict["decision"] in ("aprobar", "solicitar_cambios"), "Decisión desconocida")
    require(isinstance(verdict["resumen"], str) and verdict["resumen"].strip(), "Resumen vacío o inválido")
    findings = verdict["hallazgos"]
    require(isinstance(findings, list), "hallazgos debe ser una lista")
    require((verdict["decision"] == "aprobar" and not findings)
            or (verdict["decision"] == "solicitar_cambios" and bool(findings)),
            "Decisión incompatible con los hallazgos pendientes")
    for finding in findings:
        require(isinstance(finding, dict)
                and set(finding) == {"archivo", "linea", "explicacion", "ejemplo"},
                "Hallazgo con estructura inválida")
        require(finding["archivo"] == "candidato.py", "El hallazgo debe referirse a candidato.py")
        require(type(finding["linea"]) is int and 1 <= finding["linea"] <= line_count,
                "La línea debe existir en el candidato y ser un entero positivo")
        for key in ("explicacion", "ejemplo"):
            require(isinstance(finding[key], str) and finding[key].strip(), f"{key} vacío o inválido")
    return verdict


def codex_model_options(*, model=None, reasoning_effort=None):
    """Validar selecciones explícitas sin consultar modelos ni configuración personal."""
    require(model is None or (type(model) is str and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model)),
            "Modelo inválido: usa un identificador de hasta 200 caracteres ASCII, sin espacios ni opciones")
    require(reasoning_effort is None or (type(reasoning_effort) is str and reasoning_effort in REASONING_EFFORTS),
            "Esfuerzo no admitido: " + ", ".join(REASONING_EFFORTS))
    options = []
    if model is not None:
        options += ["--model", model]
    if reasoning_effort is not None:
        options += ["--config", "model_reasoning_effort=" + json.dumps(reasoning_effort)]
    return options


def invoke_reviewer(workspace, final_path, prompt, log_dir, *, on_invoke=None, timeout=None,
                    model=None, reasoning_effort=None):
    """Una sesión nueva de Codex: sin resume, fork ni llamada al desarrollador."""
    options = codex_model_options(model=model, reasoning_effort=reasoning_effort)
    result = {"estado": "cli_no_disponible", "codigo_salida": None, "invocaciones": 0}
    for name, args in (("version", ["--version"]), ("ayuda", ["exec", "--help"])):
        check = run_process([CODEX_EXECUTABLE] + args, workspace, log_dir / name,
                            PREFLIGHT_TIMEOUT_SECONDS, env_policy="codex")
        result[name] = check
        output = (log_dir / name / "stdout.txt").read_bytes()
        if name == "version":
            (log_dir / "codex_version.txt").write_bytes(output)
        if check["estado"] != "finalizada" or check["codigo_salida"] != 0:
            if check["estado"] == "tiempo_agotado":
                result["estado"] = "tiempo_agotado"
            return result
    help_text = output.decode("utf-8", errors="replace")
    required = ("--config", "--sandbox", "read-only", "--cd", "--skip-git-repo-check",
                "--ephemeral", "--json", "--output-last-message", "--output-schema")
    if model is not None:
        required += ("--model",)
    if any(option not in help_text for option in required):
        result["estado"] = "cli_incompatible"
        return result
    command = [
        CODEX_EXECUTABLE, "exec", "--sandbox", "read-only",
        "--config", 'approval_policy="never"', "--config", 'web_search="disabled"',
        "--config", "features.multi_agent=false",
        "--cd", str(workspace), "--skip-git-repo-check", "--ephemeral", "--json",
        "--output-schema", str(workspace / "respuesta.schema.json"),
        "--output-last-message", str(final_path), *options, "-",
    ]
    if on_invoke is not None:
        on_invoke()
    try:
        execution = run_process(command, workspace, log_dir,
                                AGENT_TIMEOUT_SECONDS if timeout is None else timeout, prompt=prompt,
                                stdout_name="eventos.jsonl", stderr_name="stderr.txt", env_policy="codex")
    except ProcessRecordError as exc:
        execution = exc.result
        execution["error_registro"] = str(exc)
    result.update(execution, invocaciones=1)
    return result


def decide(result):
    if result["errores_controlador"]:
        return 8, "fallo_controlador"
    if not result["evidencia_previa_valida"]:
        return 7, "evidencia_invalida"
    if not result["integridad"] or not all(result["integridad"].values()):
        return 6, "modificacion_no_permitida"
    agent = result["revisor"]
    if agent["estado"] == "tiempo_agotado":
        return 4, "tiempo_agotado_revisor"
    if agent["estado"] != "finalizada" or agent["codigo_salida"] != 0:
        return 3, "fallo_revisor"
    if result["dictamen_modelo"] is None:
        return 5, "respuesta_invalida"
    if result["dictamen_modelo"]["decision"] == "solicitar_cambios":
        return 1, "cambios_solicitados"
    return 0, "aprobada"


def run_review(source_run, project_root):
    started = time.monotonic()
    started_at = utc_timestamp()
    project_root = Path(project_root).resolve()
    source_run = Path(source_run).absolute()
    # Ninguna comprobación de la CLI ni registro nuevo antes de validar la evidencia.
    try:
        materials, source_hashes = validate_repair(source_run, project_root)
        case_id = recorded_case(source_run, source_hashes)
        runs_dir = project_root / "runs"
        require(source_run.resolve() != runs_dir.resolve()
                and source_run.resolve() not in runs_dir.resolve().parents,
                "El registro de revisión no puede crearse dentro del registro original")
    except (OSError, ValueError) as exc:
        return {"registro": None, "codigo_salida": 7, "decision_controlador": "evidencia_invalida",
                "aprobada": False, "evidencia_previa_valida": False, "dictamen_modelo": None,
                "error_evidencia": str(exc), "errores_controlador": [],
                "revisor": {"estado": "no_ejecutado", "codigo_salida": None, "invocaciones": 0}}

    run_dir = None
    result = {
        "caso": case_id, "inicio_utc": started_at.isoformat().replace("+00:00", "Z"), "registro": None,
        "reparacion_origen": str(source_run),
        "evidencia_previa_valida": True, "dictamen_modelo": None,
        "error_respuesta": None, "integridad": {}, "errores_controlador": [],
        "revisor": {"estado": "no_ejecutado", "codigo_salida": None, "invocaciones": 0},
    }
    try:
        runs_dir.mkdir(exist_ok=True)
        run_dir = runs_dir / f"{started_at.strftime('%Y%m%dT%H%M%S%fZ')}_{case_id}_review_{uuid4().hex}"
        run_dir.mkdir()
        result["registro"] = str(run_dir)
        agent_log = run_dir / "revisor"
        agent_log.mkdir()
        for name in ("eventos.jsonl", "stderr.txt", "respuesta_original.txt", "codex_version.txt"):
            (agent_log / name).write_bytes(b"")
        prompt_path = reviewer_prompt_path(project_root, case_id)
        prompt = read_regular(prompt_path)
        require(prompt is not None and prompt.strip(), "Faltan las instrucciones del revisor")
        (agent_log / "entrada.txt").write_bytes(prompt)
        line_count = len(materials["candidato.py"].splitlines())
        require(line_count > 0, "Candidato vacío")
        materials["respuesta.schema.json"] = (
            json.dumps(response_schema(line_count), ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        material_hashes = {name: digest(data) for name, data in materials.items()}
        result["materiales_sha256"] = material_hashes
        original_hashes = inventory(project_root)
        write_json(run_dir / "origen.json", {
            "registro_reparacion": str(source_run), "registro_sha256": source_hashes,
            "materiales_sha256": material_hashes, "instrucciones_sha256": digest(prompt),
        })
        archive = run_dir / "materiales"
        archive.mkdir()
        for name, content in materials.items():
            (archive / name).write_bytes(content)
        temporary_root = Path(tempfile.gettempdir()).resolve()
        require(temporary_root != project_root and project_root not in temporary_root.parents,
                "El directorio temporal debe estar fuera del repositorio")
        with tempfile.TemporaryDirectory(prefix="review-case-", dir=temporary_root) as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            for name, content in materials.items():
                (workspace / name).write_bytes(content)
            final_path = Path(temporary) / "respuesta.txt"
            result["revisor"] = invoke_reviewer(workspace, final_path, prompt, agent_log)
            if result["revisor"].get("error_registro"):
                result["errores_controlador"].append(result["revisor"]["error_registro"])
            raw = read_regular(final_path)
            result["revisor"]["respuesta_disponible"] = raw is not None
            if raw is not None:
                (agent_log / "respuesta_original.txt").write_bytes(raw)
                try:
                    result["dictamen_modelo"] = validate_verdict(raw, line_count)
                except ValueError as exc:
                    result["error_respuesta"] = str(exc)
                else:
                    write_json(run_dir / "dictamen_validado.json", result["dictamen_modelo"])
            else:
                result["error_respuesta"] = "El revisor no produjo un archivo de respuesta"
            try:
                after_hashes = snapshot_tree(workspace)
                result["integridad"]["workspace_intacto"] = after_hashes == material_hashes
                result["materiales_sha256_despues"] = after_hashes
            except (ValueError, OSError):
                result["integridad"]["workspace_intacto"] = False
        for key, directory, expected in (
            ("registro_reparacion_intacto", source_run, source_hashes),
            ("materiales_conservados_intactos", archive, material_hashes),
        ):
            try:
                result["integridad"][key] = snapshot_tree(directory) == expected
            except (ValueError, OSError):
                result["integridad"][key] = False
        result["integridad"]["originales_intactos"] = inventory(project_root) == original_hashes
        result["integridad"]["instrucciones_intactas"] = read_regular(prompt_path) == prompt
        result["integridad"]["entrada_intacta"] = read_regular(agent_log / "entrada.txt") == prompt
    except (OSError, ValueError) as exc:
        result["errores_controlador"].append(str(exc))

    if run_dir is not None and (run_dir / "revisor").is_dir():
        try:
            write_json(run_dir / "revisor" / "resultado.json", result["revisor"])
        except OSError as exc:
            result["errores_controlador"].append(str(exc))
    code, decision = decide(result)
    result.update(decision_controlador=decision, codigo_salida=code, aprobada=(code == 0),
                  fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
    if run_dir is not None:
        try:
            write_json(run_dir / "resultado.json", result)
        except OSError as exc:
            code = 8
            result.update(decision_controlador="fallo_controlador", codigo_salida=code, aprobada=False)
            result["errores_controlador"].append(f"No se pudo guardar resultado.json: {exc}")
    return result


def review_case(source_run, project_root):
    result = run_review(source_run, project_root)
    if not result["evidencia_previa_valida"]:
        print(f"Evidencia inválida: {result['error_evidencia']}", file=sys.stderr)
        print("Decisión del controlador: evidencia_invalida; revisor no invocado")
        return 7
    print(f"Decisión del controlador: {result['decision_controlador']}")
    print(f"Dictamen del modelo: {result['dictamen_modelo']['decision'] if result['dictamen_modelo'] else 'no válido/disponible'}")
    print(f"Registro: {result['registro'] or 'no creado'}")
    for error in result["errores_controlador"]:
        print(f"Error del controlador: {error}", file=sys.stderr)
    return result["codigo_salida"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Registro de reparación aceptada de case_01 o case_02")
    args = parser.parse_args(argv)
    return review_case(args.run, Path(__file__).resolve().parent)


if __name__ == "__main__":
    sys.exit(main())

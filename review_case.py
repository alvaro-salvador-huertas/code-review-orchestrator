"""Revisa una reparación aceptada sin ejecutar el candidato ni al desarrollador."""

import argparse
import ast
import difflib
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
)
from run_case import CASES, utc_timestamp


CODEX_EXECUTABLE = "codex"
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_json(content):
    """Rechazar JSON ambiguo: claves duplicadas, NaN e infinitos."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Clave JSON duplicada: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Constante JSON no admitida: {value}")

    return json.loads(content.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def snapshot_tree(directory):
    """Inventariar archivos sin aceptar enlaces ni archivos especiales."""
    require(directory.is_dir() and not directory.is_symlink(), f"Directorio inválido: {directory}")
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"Enlace no permitido: {path}")
        if path.is_dir():
            continue
        content = read_regular(path)
        require(content is not None, f"No es un archivo regular: {path}")
        result[path.relative_to(directory).as_posix()] = digest(content)
    return result


def reference_test_ids(reference):
    """Leer las pruebas explícitas de unittest mediante AST, sin importarlas."""
    try:
        tree = ast.parse(reference, filename="test_solution.py")
    except SyntaxError as exc:
        raise ValueError(f"Pruebas de referencia con sintaxis inválida: {exc}") from exc
    identifiers = []
    for node in tree.body:
        require(not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == "load_tests"),
                "No se admite descubrimiento dinámico mediante load_tests")
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [method.name for method in node.body
                   if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and method.name.startswith("test")]
        if not methods:
            continue
        require(any(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                    and base.value.id == "unittest" and base.attr == "TestCase"
                    or isinstance(base, ast.Name) and base.id == "TestCase"
                    for base in node.bases),
                f"Clase de pruebas no admitida para lectura estática: {node.name}")
        identifiers.extend(f"test_solution.{node.name}.{method}" for method in methods)
    require(identifiers and len(set(identifiers)) == len(identifiers),
            "Las referencias deben declarar pruebas explícitas sin identificadores duplicados")
    return sorted(identifiers)


def validate_test_report(reference, report):
    expected = reference_test_ids(reference)
    summaries = list(re.finditer(r"(?m)^Ran (\d+) tests? in [0-9.]+s$", report))
    require(len(summaries) == 1 and int(summaries[0].group(1)) == len(expected)
            and re.fullmatch(r"\n\nOK\s*", report[summaries[0].end():]) is not None,
            "El total o el cierre del informe no acredita las pruebas de referencia completas")
    rows = [line for line in report.splitlines() if line.startswith("test")]
    actual = []
    for row in rows:
        match = re.fullmatch(r"(test\w*) \((test_solution\.\w+\.(test\w*))\) \.\.\. ok", row)
        require(match is not None and match.group(1) == match.group(3),
                "Prueba omitida, fallida o fila de informe inválida")
        actual.append(match.group(2))
    require(sorted(actual) == expected,
            "El número y los nombres del informe no coinciden con las pruebas conservadas")


def validate_repair(run_dir, project_root):
    """Contrastar evidencia conservada; nunca importar ni ejecutar sus archivos."""
    snapshot = snapshot_tree(run_dir)

    def read(name):
        require(name in snapshot, f"Falta evidencia requerida: {name}")
        content = read_regular(run_dir / name)
        require(content is not None and digest(content) == snapshot[name],
                f"Evidencia alterada durante la lectura: {name}")
        return content

    try:
        result = parse_json(read("resultado.json"))
        require(result["caso"] == "case_02", "El registro no corresponde a case_02")
        require(result["aceptada"] is True
                and result["estado"] == "supera_las_pruebas_disponibles"
                and type(result["codigo_salida"]) is int and result["codigo_salida"] == 0
                and result["candidato_disponible"] is True
                and result["errores_controlador"] == [], "La reparación no está aceptada")
        require(all(result["integridad"][key] is True for key in INTEGRITY_KEYS),
                "La reparación no acredita toda la integridad exigida")
        require(all(value is True for value in result["integridad"].values()),
                "El registro contiene una comprobación de integridad fallida")
        hashes = result["sha256"]
        require(hashes["originales"] == inventory(project_root),
                "Los originales actuales no coinciden con los hashes de la reparación")
        for filename, source in (
            ("solution.py", "benchmark/case_02/solution.py"),
            ("test_solution.py", "benchmark/case_02/test_solution.py"),
            ("contrato.md", "tasks/" + CASES["case_02"]),
        ):
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
        for phase, key, implementation in (
            ("inicial", "pruebas_iniciales", read("referencia/solution.py")),
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
        after = result["pruebas_posteriores"]
        require(after["estado"] == "finalizada" and type(after["codigo_salida"]) is int
                and after["codigo_salida"] == 0,
                "La evaluación posterior no terminó con código cero")
        report = read("posterior/stderr.txt").decode("utf-8")
        validate_test_report(tests, report)
        expected_diff = b"".join(difflib.diff_bytes(
            difflib.unified_diff, read("referencia/solution.py").splitlines(keepends=True),
            candidate.splitlines(keepends=True), fromfile=b"inicial/solution.py",
            tofile=b"candidato/solution.py",
        ))
        require(read("candidato.diff") == expected_diff, "El diff no corresponde al candidato")
        materials = {name: read(source) for name, source in MATERIALS.items()}
        require(snapshot_tree(run_dir) == snapshot, "El registro cambió durante la validación")
        return materials, snapshot
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Estructura de evidencia incompleta o inválida: {exc}") from exc


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


def invoke_reviewer(workspace, final_path, prompt, log_dir):
    """Una sesión nueva de Codex: sin resume, fork ni llamada al desarrollador."""
    result = {"estado": "cli_no_disponible", "codigo_salida": None, "invocaciones": 0}
    for name, args in (("version", ["--version"]), ("ayuda", ["exec", "--help"])):
        check = run_process([CODEX_EXECUTABLE] + args, workspace, log_dir / name,
                            PREFLIGHT_TIMEOUT_SECONDS)
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
    if any(option not in help_text for option in required):
        result["estado"] = "cli_incompatible"
        return result
    command = [
        CODEX_EXECUTABLE, "exec", "--sandbox", "read-only",
        "--config", 'approval_policy="never"', "--config", 'web_search="disabled"',
        "--config", "features.multi_agent=false",
        "--cd", str(workspace), "--skip-git-repo-check", "--ephemeral", "--json",
        "--output-schema", str(workspace / "respuesta.schema.json"),
        "--output-last-message", str(final_path), "-",
    ]
    execution = run_process(command, workspace, log_dir, AGENT_TIMEOUT_SECONDS, prompt=prompt,
                            stdout_name="eventos.jsonl", stderr_name="stderr.txt")
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


def review_case(source_run, project_root):
    started = time.monotonic()
    started_at = utc_timestamp()
    project_root = Path(project_root).resolve()
    source_run = Path(source_run).absolute()
    # Ninguna comprobación de la CLI ni registro nuevo antes de validar la evidencia.
    try:
        materials, source_hashes = validate_repair(source_run, project_root)
        runs_dir = project_root / "runs"
        require(source_run.resolve() != runs_dir.resolve()
                and source_run.resolve() not in runs_dir.resolve().parents,
                "El registro de revisión no puede crearse dentro del registro original")
    except (OSError, ValueError) as exc:
        print(f"Evidencia inválida: {exc}", file=sys.stderr)
        print("Decisión del controlador: evidencia_invalida; revisor no invocado")
        return 7

    run_dir = None
    result = {
        "caso": "case_02", "inicio_utc": started_at.isoformat().replace("+00:00", "Z"),
        "reparacion_origen": str(source_run),
        "evidencia_previa_valida": True, "dictamen_modelo": None,
        "error_respuesta": None, "integridad": {}, "errores_controlador": [],
        "revisor": {"estado": "no_ejecutado", "codigo_salida": None, "invocaciones": 0},
    }
    try:
        runs_dir.mkdir(exist_ok=True)
        run_dir = runs_dir / f"{started_at.strftime('%Y%m%dT%H%M%S%fZ')}_case_02_review_{uuid4().hex}"
        run_dir.mkdir()
        agent_log = run_dir / "revisor"
        agent_log.mkdir()
        for name in ("eventos.jsonl", "stderr.txt", "respuesta_original.txt", "codex_version.txt"):
            (agent_log / name).write_bytes(b"")
        prompt_path = project_root / "prompts" / "reviewer.md"
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
    print(f"Decisión del controlador: {result['decision_controlador']}")
    print(f"Dictamen del modelo: {result['dictamen_modelo']['decision'] if result['dictamen_modelo'] else 'no válido/disponible'}")
    print(f"Registro: {run_dir if run_dir else 'no creado'}")
    for error in result["errores_controlador"]:
        print(f"Error del controlador: {error}", file=sys.stderr)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Registro de reparación aceptada del caso 02")
    args = parser.parse_args(argv)
    return review_case(args.run, Path(__file__).resolve().parent)


if __name__ == "__main__":
    sys.exit(main())

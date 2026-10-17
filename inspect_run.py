"""Consulta un registro general del orquestador sin ejecutar sus materiales."""

import argparse
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from case_evidence import classify_test_report, parse_json, read_regular, test_report_rows


UNKNOWN = "no consta"


def brief(value):
    """No volcar estructuras, textos extensos ni controles de terminal."""
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return str(value).lower()
    if not isinstance(value, (str, int, float, Path, BaseException)):
        return "dato no escalar (consultar JSON)"
    text = "".join(c if c.isprintable() else " " for c in str(value))
    return text if len(text) <= 240 else text[:237] + "..."


def field(record, key, kind, issues, context, *, optional=False, nullable=False):
    if key not in record:
        if not optional:
            issues.append(f"{context}: falta {key}")
        return None
    value = record[key]
    if value is None and (nullable or optional):
        return None
    if type(value) is not kind or (kind is str and not value.strip()):
        issues.append(f"{context}: {key} tiene un tipo o valor inválido")
        return None
    return value


def count(record, key, issues, context):
    value = field(record, key, int, issues, context)
    if value is not None and value < 0:
        issues.append(f"{context}: {key} es negativo")
        return None
    return value


def read_bytes(path, issues):
    try:
        content = read_regular(path)
        if content is None:
            raise ValueError("falta el archivo regular")
        return content
    except (OSError, ValueError) as exc:
        issues.append(f"{path}: {brief(exc)}")
        return None


def read_summary(path, issues):
    content = read_bytes(path, issues)
    if content is not None:
        try:
            result = parse_json(content)
            if not isinstance(result, dict):
                raise ValueError("se requiere un objeto JSON")
            return result
        except (ValueError, RecursionError) as exc:
            issues.append(f"{path}: JSON inválido ({brief(exc)})")
    return None


def same_json_values(left, right):
    """Distinguir booleanos de números, sin separar enteros y floats iguales."""
    pending = [(left, right)]
    while pending:
        left, right = pending.pop()
        if type(left) is bool or type(right) is bool:
            if type(left) is not type(right) or left != right:
                return False
        elif isinstance(left, dict) and isinstance(right, dict):
            if left.keys() != right.keys():
                return False
            pending.extend((left[key], right[key]) for key in left)
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                return False
            pending.extend(zip(left, right))
        elif left != right:
            return False
    return True


def match_summary(record, path, issues, *, json_mode=False):
    saved = read_summary(path, issues)
    if saved is not None and not (same_json_values(saved, record) if json_mode else saved == record):
        issues.append(f"{path}: difiere del resumen general; se muestra el general")


def registered_details(record, label, issues, *, emit=print):
    checks = field(record, "integridad", dict, issues, label, optional=True)
    if checks:
        if emit is not None:
            emit(f"  Integridad registrada ({label}): " + "; ".join(
                f"{brief(key)}={brief(value)}" for key, value in checks.items()))
        if any(value is not None and type(value) is not bool for value in checks.values()):
            issues.append(f"{label}: integridad contiene valores no booleanos")
    else:
        if emit is not None:
            emit(f"  Integridad registrada ({label}): {UNKNOWN}")
    errors = field(record, "errores_controlador", list, issues, label, optional=True)
    if emit is not None:
        emit(f"  Errores del controlador ({label}): " +
              (UNKNOWN if errors is None else "ninguno registrado" if not errors else str(len(errors))))
    for error in (errors or [])[:5]:
        if emit is not None:
            emit(f"    {brief(error)}")
    if errors and len(errors) > 5:
        if emit is not None:
            emit("    Resto de errores: consultar resultado.json de la etapa.")
    for key in ("detencion", "error_informe", "error_respuesta", "error_evidencia"):
        if record.get(key) is not None:
            if emit is not None:
                emit(f"  {key}: {brief(record[key])}")


def agent_summary(record, key, label, issues, *, emit=print):
    agent = field(record, key, dict, issues, label)
    if agent is None:
        if emit is not None:
            emit(f"  {label}: {UNKNOWN}")
        return
    state = field(agent, "estado", str, issues, label)
    calls = count(agent, "invocaciones", issues, label)
    code = field(agent, "codigo_salida", int, issues, label, nullable=True)
    if emit is not None:
        emit(f"  {label}: {brief(state)}; invocaciones registradas: {brief(calls)}; "
              f"código: {brief(code)}")
        emit(f"  Modelo / proveedor / esfuerzo ({label}): no consta en este formato de resumen")
    for name, process in ((label, agent), (label + "/version", agent.get("version")),
                          (label + "/ayuda", agent.get("ayuda"))):
        if isinstance(process, dict):
            for key in ("error", "error_registro"):
                if process.get(key) is not None:
                    if emit is not None:
                        emit(f"  Error registrado ({name}): {brief(process[key])}")


def test_summary(repair, phase, directory, issues, *, json_mode=False):
    label, key = ("iniciales", "pruebas_iniciales") if phase == "inicial" else (
        "posteriores", "pruebas_posteriores")
    result = field(repair, key, dict, issues, "reparación")
    if result is None:
        return f"Pruebas {label}: incompleto; recuentos: {UNKNOWN}" if not json_mode else None
    state = field(result, "estado", str, issues, key)
    code = field(result, "codigo_salida", int, issues, key, nullable=True)
    prefix = (f"Pruebas {label}: estado registrado {brief(state)}; código {brief(code)}"
              if not json_mode else None)
    if state == "no_ejecutadas":
        return prefix + f"; recuentos: {UNKNOWN} (no ejecutadas)" if not json_mode else None
    if directory is None:
        issues.append(f"{key}: no consta la ruta para consultar el informe")
        return prefix + f"; incompleto; recuentos: {UNKNOWN}" if not json_mode else None
    phase_dir = directory / phase
    match_summary(result, phase_dir / "resultado.json", issues, json_mode=json_mode)
    report = read_bytes(phase_dir / "stderr.txt", issues)
    if state != "finalizada":
        # Un timeout o un fallo de arranque puede tener un informe parcial válido.
        return prefix + f"; evaluación incompleta; recuentos: {UNKNOWN}" if not json_mode else None
    reference = read_bytes(directory / "referencia/test_solution.py", issues)
    if report is None or reference is None:
        return prefix + f"; incompleto; recuentos: {UNKNOWN}" if not json_mode else None
    try:
        text = report.decode("utf-8")
        classification = classify_test_report(reference, text, code)
        summary, failed, errors = test_report_rows(reference, text)
        total = int(summary.group(1))
        if errors:
            # El lector compartido comprueba las filas; aquí exigimos también
            # que el cierre de errores concuerde con sus recuentos.
            parts = ([f"failures={len(failed)}"] if failed else []) + [f"errors={len(errors)}"]
            ending = "\n\nFAILED (" + ", ".join(parts) + ")"
            if text[summary.end():].rstrip() != ending:
                raise ValueError("El cierre de errores no coincide con las filas")
        if json_mode:
            return None
        status = {"superadas": "pruebas superadas", "fallos_asercion": "fallos de aserción",
                  "error_pruebas": "errores de pruebas"}[classification]
        return (prefix + f"; {status}; total {total}, correctas {total-len(failed)-len(errors)}, "
                f"fallos {len(failed)}, errores {len(errors)}, omisiones 0")
    except (ValueError, RecursionError) as exc:
        issues.append(f"{phase_dir / 'stderr.txt'} y {directory / 'referencia/test_solution.py'}: {brief(exc)}")
        return prefix + f"; informe incompleto o no acreditado; recuentos: {UNKNOWN}" if not json_mode else None


def stage_directory(stage, run_dir, label, issues, *, emit=print):
    location = field(stage, "registro", str, issues, label, nullable=True)
    if location is None:
        if emit is not None:
            emit(f"  Evidencia de {label}: {UNKNOWN} (registro no disponible)")
        return None
    directory = Path(location)
    if not directory.is_absolute():
        directory = run_dir / directory
    if emit is not None:
        emit(f"  Evidencia de {label}: {directory}")
    match_summary(stage, directory / "resultado.json", issues, json_mode=emit is None)
    return directory


def attempt_summary(attempt, run_dir, issues, *, emit=print):
    number = count(attempt, "numero", issues, "intento")
    if emit is not None:
        emit(f"\nIntento {brief(number)}:")
    repair = field(attempt, "reparacion", dict, issues, "intento", nullable=True)
    if repair is None:
        if emit is not None:
            emit("  Reparación: no consta; intento incompleto")
        issues.append(f"Intento {brief(number)}: falta el resultado de reparación")
    else:
        directory = stage_directory(repair, run_dir, "reparación", issues, emit=emit)
        state = field(repair, "estado", str, issues, "reparación")
        code = field(repair, "codigo_salida", int, issues, "reparación", nullable=True)
        if emit is not None:
            emit(f"  Decisión de reparación: {brief(state)}; código {brief(code)}")
        agent_summary(repair, "agente", "Desarrollador", issues, emit=emit)
        for phase in ("inicial", "posterior"):
            summary = test_summary(repair, phase, directory, issues, json_mode=emit is None)
            if emit is not None:
                emit("  " + summary)
        registered_details(repair, "reparación", issues, emit=emit)
        if directory is not None:
            if emit is not None:
                emit("  Informes: inicial/ y posterior/; referencias: referencia/; "
                      "candidato y diff: candidato.py, candidato.diff; sesión: agente/.")

    review = field(attempt, "revision", dict, issues, "intento", nullable=True)
    transitions = field(attempt, "transiciones", list, issues, "intento")
    if review is None:
        pending = ("revision" not in attempt or not transitions or
                   any(isinstance(t, dict) and t.get("accion") == "revisar" for t in transitions))
        if emit is not None:
            emit("  Revisión: " + ("incompleta; sin resultado registrado" if pending else
                                      "no ejecutada según las etapas registradas"))
            emit("  Dictamen del modelo / decisión de revisión: no consta")
        if pending:
            issues.append(f"Intento {brief(number)}: revisión prevista sin resultado")
    else:
        stage_directory(review, run_dir, "revisión", issues, emit=emit)
        agent_summary(review, "revisor", "Revisor", issues, emit=emit)
        verdict = field(review, "dictamen_modelo", dict, issues, "revisión", nullable=True)
        if verdict is None:
            if emit is not None:
                emit("  Dictamen registrado del modelo: no consta (no disponible o inválido)")
        else:
            decision = field(verdict, "decision", str, issues, "dictamen")
            findings = field(verdict, "hallazgos", list, issues, "dictamen")
            if emit is not None:
                emit(f"  Dictamen registrado del modelo: {brief(decision)}; "
                      f"hallazgos: {len(findings) if findings is not None else UNKNOWN}")
        decision = field(review, "decision_controlador", str, issues, "revisión")
        code = field(review, "codigo_salida", int, issues, "revisión", nullable=True)
        if emit is not None:
            emit(f"  Decisión del controlador de revisión: {brief(decision)}; código {brief(code)}")
        registered_details(review, "revisión", issues, emit=emit)
        if emit is not None:
            emit("  Dictamen y respuesta: dictamen_validado.json (si existe), revisor/; materiales: materiales/.")

    if not transitions:
        if emit is not None:
            emit("  Transiciones: no consta")
    for transition in transitions or []:
        if not isinstance(transition, dict):
            issues.append("Transición inválida: se requiere un objeto")
            continue
        parts = [field(transition, key, str, issues, "transición") for key in ("etapa", "accion", "motivo")]
        if emit is not None:
            emit(f"  Transición: {brief(parts[0])} -> {brief(parts[1])} ({brief(parts[2])})")


def read_inspection(run_dir, *, emit=None):
    """Validar una sola vez y proyectar los datos; el texto es una salida opcional."""
    # Sin emisor: JSON, sin preparar la presentación textual. Texto conserva
    # sus comprobaciones históricas, incluidos los casos límite heredados.
    execution = {
        "caso": None,
        "estado": None,
        "codigo_salida": None,
        "presupuestos": {"max_intentos": None, "max_invocaciones": None},
        "intentos_registrados": None,
        "invocaciones": {"desarrollador": None, "revisor": None, "total": None},
        "duracion_segundos": None,
    }
    run_dir = Path(run_dir).absolute()
    issues = []
    if emit is not None:
        emit(f"Registro general: {run_dir / 'resultado.json'}")
        emit("Consulta de evidencia registrada; no es una auditoría independiente ni certifica corrección general.")
    result = read_summary(run_dir / "resultado.json", issues)
    if result is not None:
        case = field(result, "caso", str, issues, "general")
        state = field(result, "estado", str, issues, "general")
        code = field(result, "codigo_salida", int, issues, "general", nullable=True)
        attempts = field(result, "intentos", list, issues, "general")
        limit = count(result, "max_intentos", issues, "general")
        calls = field(result, "invocaciones", dict, issues, "general")
        call_limit = count(result, "max_invocaciones", issues, "general")
        totals = [count(calls, key, issues, "invocaciones") if calls is not None else None
                  for key in ("desarrollador", "revisor", "total")]
        if emit is not None:
            emit(f"Caso: {brief(case)}")
            emit(f"Estado del controlador: {brief(state)}; código de la ejecución: {brief(code)}")
            emit(f"Intentos registrados: {len(attempts) if attempts is not None else UNKNOWN}/{brief(limit)}")
            emit(f"Invocaciones registradas: desarrollador {brief(totals[0])}, revisor {brief(totals[1])}, "
                  f"total {brief(totals[2])}/{brief(call_limit)}")
        duration = result.get("duracion_segundos")
        if duration is not None:
            try:
                if emit is None and type(duration) is int:
                    valid = duration >= 0
                else:
                    valid = type(duration) in (int, float) and math.isfinite(duration) and duration >= 0
                if not valid:
                    raise ValueError("duración inválida")
            except (ValueError, OverflowError):
                issues.append("general: duración inválida")
                duration = None
        execution.update({
            "caso": case,
            "estado": state,
            "codigo_salida": code,
            "presupuestos": {"max_intentos": limit, "max_invocaciones": call_limit},
            "intentos_registrados": len(attempts) if attempts is not None else None,
            "invocaciones": dict(zip(("desarrollador", "revisor", "total"), totals)),
            "duracion_segundos": duration,
        })
        if emit is not None:
            emit("Duración: " + (f"{duration:.3f} s" if duration is not None else UNKNOWN))
            emit("Segundo intento: " + (UNKNOWN if attempts is None else
                  "registrado; no se verifica su continuidad ni una corrección satisfactoria" if len(attempts) > 1 else
                  "no registrado (no acredita corrección automática)"))
        registered_details(result, "general", issues, emit=emit)
        for attempt in attempts or []:
            if isinstance(attempt, dict):
                attempt_summary(attempt, run_dir, issues, emit=emit)
            else:
                issues.append("Intento inválido: se requiere un objeto")
    if emit is not None:
        emit("\nVerificación de consulta: lectura de JSON y coherencia de resúmenes enlazados; "
              "recuentos e identificadores de informes frente a pruebas conservadas (AST).")
        emit("Integridad registrada: no se recalculan hashes ni se verifica el candidato. "
              "No se leen eventos, prompts ni configuración del entorno.")
    return {
        "version_esquema": 1,
        "consulta": {
            "estado": "incompleta" if issues else "completada",
            "codigo_salida": 1 if issues else 0,
            "incidencias": issues,
        },
        "ejecucion": execution,
    }


def inspect_run(run_dir):
    inspection = read_inspection(run_dir, emit=print)
    query = inspection["consulta"]
    for issue in query["incidencias"]:
        print(f"Consulta incompleta: {issue}", file=sys.stderr)
    print(f"Consulta: {query['estado']} (código {query['codigo_salida']})")
    return query["codigo_salida"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False, epilog=(
        "Salida: 0 consulta completada, aunque la ejecución haya fallado; "
        "1 consulta incompleta por archivos o datos inválidos; 2 argumentos incorrectos."))
    parser.add_argument("--run", required=True, type=Path, help="Directorio del registro general")
    parser.add_argument("--format", choices=("text", "json"), default="text",
                        help="Formato de salida (predeterminado: text)")
    args = parser.parse_args(argv)
    if args.format == "json":
        inspection = read_inspection(args.run)
        print(json.dumps(inspection, allow_nan=False))
        return inspection["consulta"]["codigo_salida"]
    return inspect_run(args.run)


if __name__ == "__main__":
    sys.exit(main())

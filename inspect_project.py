"""Consulta exclusivamente resultado.json de una orquestación de proyectos."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

from case_evidence import read_regular


TYPES = {"inspect-json": "orquestacion_inspect_json_v1",
         "export-csv": "orquestacion_export_csv_v1"}
ACTIVE = {"en_preparacion", "en_desarrollo", "en_evaluacion", "en_revision"}


class Number:
    """Token numérico JSON: conserva precisión y rango sin convertir a float."""

    def __init__(self, text, integer=False):
        self.text, self.integer = text, integer

    def negative(self):
        return self.text.startswith("-") and any(
            c in "123456789" for c in self.text.lower().split("e", 1)[0])


def parse_summary(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"clave duplicada: {key!r}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"constante no JSON: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_int=lambda value: Number(value, integer=True),
                      parse_float=Number, parse_constant=invalid)


def encode_json(value):
    """Solo Number procede de tokens reconocidos por el parser JSON."""
    if isinstance(value, Number):
        return value.text
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(k) + ": " + encode_json(v)
                                for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(map(encode_json, value)) + "]"
    return json.dumps(value, allow_nan=False)


@dataclass(frozen=True)
class Field:
    kind: object
    optional: bool = False
    nullable: bool = False


@dataclass(frozen=True)
class Mapping:
    item: object


# Esquemas de lectura, no reglas de autorización ni contraste de evidencia.
# Solo se interpretan estos campos; los manifiestos y demás metadatos se omiten.
CALLS = {"desarrollador": "count", "revisor": "count"}
PROCESS = {
    "estado": "text", "codigo_salida": Field("integer", nullable=True),
    **{name: Field("number", optional=True) for name in ("duracion_segundos", "limite_segundos")},
    "directorio_trabajo": Field("text", optional=True),
}
COUNTS = ("metodos", "metodos_con_fallos", "aserciones_fallidas", "errores",
          "fallos_subtest", "subtests_ejecutados")
EVALUATION = {
    "clasificacion": "text", "proceso": Field(PROCESS, nullable=True),
    **{name: Field("count", optional=True) for name in COUNTS},
}
VERDICT = {"decision": "text", "resumen": "text", "hallazgos": [{
    "archivo": "text", "linea": "positive", "requisito": "text",
    "explicacion": "text", "ejemplo": "text"}]}
REVIEW = {
    "registro": Field("text", nullable=True), "decision_controlador": "text",
    "codigo_salida": "integer", "revisor": {**PROCESS, "invocaciones": "count"},
    "dictamen_modelo": Field(VERDICT, nullable=True), "incorporacion": "text",
    "contraste_semantico": "text", "error": Field("text", nullable=True),
}
ATTEMPT = {
    "numero": "positive", "registro": "text", "invocaciones": CALLS,
    "transiciones": [{"etapa": "text", "accion": "text", "motivo": "text"}],
    "revision": Field(REVIEW, nullable=True),
    "desarrollo": Field({"reserva_invocacion": "bool", "agente": {
        "invocaciones": "count", "proceso": Field(PROCESS, nullable=True),
        "version": Field(PROCESS, optional=True), "ayuda": Field(PROCESS, optional=True)}}, optional=True),
    "evaluaciones": Field(Mapping(EVALUATION), optional=True),
}
SUMMARY = {
    "tipo": "text", "tarea": "text", "registro": Field("text", nullable=True),
    "inicio_utc": "text", "estado": "text", "motivo": Field("text", nullable=True),
    "codigo_salida": "integer", "max_intentos": "count", "max_invocaciones": "count",
    "invocaciones": {**CALLS, "total": "count"}, "intentos": [ATTEMPT],
    "reservas": [{"rol": "text", "intento": "positive", "fecha_utc": "text",
                  "limite_segundos": "number", "estado": "text"}],
    "inicial": Mapping(EVALUATION), "limites_segundos": Mapping("number"),
    "incorporacion": "text", "lista_para_revision_humana": "bool",
    "error": Field("text", nullable=True),
    "fin_utc": Field("text", optional=True),
    "duracion_segundos": Field("number", optional=True),
}


def validate(value, spec, path, issues):
    """Retener campos válidos y localizar problemas sin inferir datos faltantes."""
    if isinstance(spec, Field):
        if value is None and spec.nullable:
            return None
        return validate(value, spec.kind, path, issues)
    if isinstance(spec, dict) and isinstance(value, dict):
        result = {}
        for key, child in spec.items():
            location = f"{path}.{key}"
            if key not in value:
                result[key] = None
                if not isinstance(child, Field) or not child.optional:
                    issues.append(f"{location}: falta el campo")
            else:
                result[key] = validate(value[key], child, location, issues)
        return result
    if isinstance(spec, list) and isinstance(value, list):
        return [validate(item, spec[0], f"{path}[{i}]", issues) for i, item in enumerate(value)]
    if isinstance(spec, Mapping) and isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not key.strip():
                issues.append(f"{path}: nombre vacío")
            result[key] = validate(item, spec.item, f"{path}.{key}", issues)
        return result
    valid = False
    if spec == "text":
        valid = type(value) is str and bool(value.strip())
    elif spec == "bool":
        valid = type(value) is bool
    elif spec in ("integer", "count", "positive", "number"):
        valid = isinstance(value, Number) and (spec == "number" or value.integer)
        if valid and spec != "integer":
            valid = not value.negative()
        if valid and spec == "positive":
            valid = any(c in "123456789" for c in value.text)
    if valid:
        return value
    issues.append(f"{path}: valor o estructura inválidos")
    return None


def read_inspection(run_dir):
    issues, summary = [], None
    try:
        raw = read_regular(Path(run_dir) / "resultado.json")
        if raw is None:
            raise ValueError("ausente o no es un archivo regular")
        document = parse_summary(raw)
        summary = validate(document, SUMMARY, "resultado", issues)
    except (OSError, ValueError, RecursionError) as exc:
        issues.append(f"resultado.json: {exc}")
    data = summary or {}
    if summary is not None:
        task = data["tarea"]
        if task not in TYPES or data["tipo"] != TYPES[task]:
            issues.append("resultado.tipo/tarea: formato de orquestación no admitido")
        if data["estado"] not in ACTIVE:
            for key in ("fin_utc", "duracion_segundos"):
                if key not in document:
                    issues.append(f"resultado.{key}: falta en un resumen de estado terminal")
        for i, reservation in enumerate(data["reservas"] or []):
            if reservation and reservation["rol"] not in CALLS:
                issues.append(f"resultado.reservas[{i}].rol: rol no admitido")
            if reservation and reservation["estado"] != "reservada_antes_de_invocar":
                issues.append(f"resultado.reservas[{i}].estado: valor no admitido")
        evaluations = [("resultado.inicial", data["inicial"])]
        for i, attempt in enumerate(data["intentos"] or []):
            evaluations.append((f"resultado.intentos[{i}].evaluaciones", (attempt or {}).get("evaluaciones")))
            review = (attempt or {}).get("revision") or {}
            verdict = review.get("dictamen_modelo") or {}
            if verdict and verdict["decision"] not in ("aprobar", "solicitar_cambios"):
                issues.append(f"resultado.intentos[{i}].revision.dictamen_modelo.decision: valor no admitido")
        for path, groups in evaluations:
            for name, evaluation in (groups or {}).items():
                if evaluation is None:
                    continue
                classification = evaluation["clasificacion"]
                if classification not in ("no_acreditada", "superadas", "fallos_asercion", "error_pruebas"):
                    issues.append(f"{path}.{name}.clasificacion: valor no admitido")
                elif classification != "no_acreditada":
                    for key in COUNTS:
                        if evaluation[key] is None:
                            issues.append(f"{path}.{name}.{key}: recuento no disponible para esa clasificación")
    calls = data.get("invocaciones") or {}
    attempts = data.get("intentos")
    inspection = {
        "version_esquema": 1,
        "consulta": {"estado": "incompleta" if issues else "completada",
                     "codigo_salida": int(bool(issues)), "incidencias": issues},
        "ejecucion": {
            "caso": data.get("tarea"), "estado": data.get("estado"),
            "codigo_salida": data.get("codigo_salida"),
            "presupuestos": {key: data.get(key) for key in ("max_intentos", "max_invocaciones")},
            "intentos_registrados": len(attempts) if attempts is not None else None,
            "invocaciones": {key: calls.get(key) for key in (*CALLS, "total")},
            "duracion_segundos": data.get("duracion_segundos"),
        },
    }
    return inspection, summary


def display(value):
    if value is None:
        return "no consta"
    if isinstance(value, Number):
        return value.text
    if type(value) is bool:
        return "sí" if value else "no"
    return "".join(c if c.isprintable() else " " for c in str(value))


def show_fields(label, data, keys, emit):
    if not keys:
        emit(label + (": no consta" if data is None else ": sin entradas registradas"))
        return
    data = data or {}
    emit(label + ": " + "; ".join(f"{key}={display(data.get(key))}" for key in keys))


def show_process(label, process, emit):
    show_fields(label, process, ("estado", "codigo_salida", "duracion_segundos", "limite_segundos"), emit)
    if process and process.get("directorio_trabajo") is not None:
        emit("    Ubicación de trabajo registrada (sin abrir): " + display(process["directorio_trabajo"]))


def show_evaluations(label, evaluations, emit):
    if evaluations is None:
        emit(label + ": no consta")
    elif not evaluations:
        emit(label + ": sin entradas registradas")
    else:
        for name, evaluation in evaluations.items():
            show_fields(f"{label} / {display(name)}", evaluation, ("clasificacion", *COUNTS), emit)
            show_process("    Proceso registrado", (evaluation or {}).get("proceso"), emit)


def show_text(inspection, summary, emit=print):
    data, execution = summary or {}, inspection["ejecucion"]
    emit("Consulta del resumen de proyectos: solo resultado.json.")
    show_fields("Ejecución registrada", data, ("tarea", "estado", "motivo", "codigo_salida"), emit)
    emit("Intentos registrados: " + display(execution["intentos_registrados"]))
    show_fields("Presupuestos registrados", execution["presupuestos"], ("max_intentos", "max_invocaciones"), emit)
    show_fields("Invocaciones registradas", execution["invocaciones"], (*CALLS, "total"), emit)
    emit("Los contadores y reservas no acreditan que las invocaciones hayan finalizado.")
    show_fields("Cierre registrado", data, ("duracion_segundos", "incorporacion", "lista_para_revision_humana"), emit)
    show_fields("Tiempos registrados", data, ("inicio_utc", "fin_utc"), emit)
    emit("Ubicación general registrada (sin abrir): " + display(data.get("registro")))
    show_fields("Límites registrados (segundos)", data.get("limites_segundos"), data.get("limites_segundos") or (), emit)
    for reservation in data.get("reservas") or []:
        show_fields("Reserva registrada", reservation, ("rol", "intento", "estado", "limite_segundos"), emit)
    show_evaluations("Evaluación inicial registrada", data.get("inicial"), emit)
    for attempt in data.get("intentos") or []:
        attempt = attempt or {}
        emit("Intento registrado: " + display(attempt.get("numero")))
        emit("  Ubicación de evidencia registrada (sin abrir): " + display(attempt.get("registro")))
        show_fields("  Invocaciones registradas", attempt.get("invocaciones"), CALLS, emit)
        developer = (attempt.get("desarrollo") or {}).get("agente") or {}
        show_process("  Proceso del desarrollador registrado", developer.get("proceso"), emit)
        for key in ("version", "ayuda"):
            if developer.get(key) is not None:
                show_process(f"  Consulta CLI {key} registrada", developer[key], emit)
        show_evaluations("  Evaluación registrada", attempt.get("evaluaciones"), emit)
        review = attempt.get("revision") or {}
        show_fields("  Revisión registrada", review, ("decision_controlador", "codigo_salida", "contraste_semantico", "incorporacion"), emit)
        show_process("  Proceso del revisor registrado", review.get("revisor"), emit)
        verdict = review.get("dictamen_modelo") or {}
        show_fields("  Dictamen del modelo registrado", verdict, ("decision", "resumen"), emit)
        findings = verdict.get("hallazgos")
        emit("  Hallazgos registrados, sin contrastar: " + display(len(findings) if findings is not None else None))
        emit("  Ubicación de revisión registrada (sin abrir): " + display(review.get("registro")))
        if review.get("error") is not None:
            emit("  Error de revisión registrado: " + display(review["error"]))
        for transition in attempt.get("transiciones") or []:
            show_fields("  Transición registrada", transition, ("etapa", "accion", "motivo"), emit)
    if data.get("error") is not None:
        emit("Error registrado: " + display(data["error"]))
    emit("Una aprobación del modelo no es auditoría humana ni incorporación realizada. "
         "Esta consulta no acredita disponibilidad de evidencia ni integridad de la ejecución.")
    for issue in inspection["consulta"]["incidencias"]:
        emit("Incidencia de consulta: " + display(issue))
    query = inspection["consulta"]
    emit(f"Consulta: {query['estado']} (código {query['codigo_salida']})")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False, epilog=(
        "Códigos: 0 resumen consultado; 1 consulta incompleta; 2 argumentos incorrectos. "
        "No abre evidencia referenciada ni verifica integridad."))
    parser.add_argument("--run", required=True, type=Path, help="Directorio con resultado.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    inspection, summary = read_inspection(args.run)
    if args.format == "json":
        print(encode_json(inspection))
    else:
        show_text(inspection, summary)
    return inspection["consulta"]["codigo_salida"]


if __name__ == "__main__":
    sys.exit(main())

"""Selección y evidencia mínima, sin copiar credenciales ni configuración privada."""

import json

from case_evidence import require
from evaluate_reviewer import effective_configuration, requested_configuration
from review_case import codex_model_options


SELECTION_KEYS = {"model", "provider", "reasoning_effort"}
MAX_EVENTS_BYTES = 1024 * 1024
MAX_EVENT_LINE = 64 * 1024


def selection(*, model=None, provider=None, reasoning_effort=None):
    codex_model_options(model=model, provider=provider, reasoning_effort=reasoning_effort)
    return {"model": model, "provider": provider, "reasoning_effort": reasoning_effort}


def options(value):
    require(isinstance(value, dict) and set(value) == SELECTION_KEYS,
            "Selección del revisor incompleta o con campos desconocidos")
    return codex_model_options(**value)


def frozen_document(value):
    return {"version": 1, "seleccion": value, "argumentos_cli": options(value)}


def validate_frozen(value):
    require(isinstance(value, dict) and set(value) == {"version", "seleccion", "argumentos_cli"}
            and type(value["version"]) is int and value["version"] == 1,
            "Formato de selección congelada desconocido")
    require(value["argumentos_cli"] == options(value["seleccion"]),
            "Selección congelada y argumentos inconsistentes")
    return value["seleccion"]


def requested(value):
    options(value)
    configuration = requested_configuration(**value)
    return {key: configuration[key] for key in ("modelo", "proveedor", "esfuerzo")}


def invocation_options(value):
    options(value)
    return {key: item for key, item in value.items() if item is not None}


def sent_options(command):
    """Extraer sólo las opciones de selección del comando realmente registrado."""
    if command is None:
        return []
    require(isinstance(command, list) and all(type(part) is str for part in command),
            "Comando del revisor inválido")
    extracted = []
    index = 1
    while index < len(command):
        arg = command[index]
        if arg in ("--model", "-m"):
            require(index + 1 < len(command), "Falta valor de modelo en el comando")
            extracted += command[index:index + 2]
            index += 2
            continue
        if arg.startswith(("--model=", "-m=")):
            extracted.append(arg)
        if arg in ("--config", "-c"):
            require(index + 1 < len(command), "Falta valor de configuración en el comando")
            setting = command[index + 1]
            if setting.split("=", 1)[0].strip() in ("model", "model_provider", "model_reasoning_effort"):
                extracted += [arg, setting]
            index += 2
            continue
        if arg.startswith(("--config=", "-c=")):
            setting = arg.split("=", 1)[1]
            if setting.split("=", 1)[0].strip() in ("model", "model_provider", "model_reasoning_effort"):
                extracted.append(arg)
        index += 1
    return extracted


def _identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return not any(ord(char) < 32 for char in value)


def effective_from_events(path):
    """Sólo respuesta estructurada terminada; ni opciones ni texto de los ítems.

    codex exec puede no emitir estos eventos: en ese caso todo sigue sin constar.
    Se inspecciona un prefijo acotado, sin guardar contenido de las respuestas.
    """
    result = effective_configuration()
    result["procedencia"] = []
    result["observacion"] = ("Sólo se acreditan campos explícitos de response.completed en el prefijo JSONL acotado. "
                              "Opciones enviadas, session_configured y texto de ítems no prueban parámetros efectivos. "
                              "Valores ausentes o contradictorios: no consta. No se infiere proveedor del modelo.")
    values = {key: set() for key in ("modelo", "proveedor", "esfuerzo")}
    try:
        with path.open("rb") as stream:
            remaining = MAX_EVENTS_BYTES
            line_number = 0
            while remaining:
                raw = stream.readline(min(remaining, MAX_EVENT_LINE + 1))
                if not raw:
                    break
                remaining -= len(raw)
                line_number += 1
                if not remaining and not raw.endswith(b"\n"):
                    break  # No interpretar un prefijo recortado de la última línea.
                if len(raw) > MAX_EVENT_LINE:
                    # No interpretar como evento el sufijo de una línea larga.
                    while remaining and not raw.endswith(b"\n"):
                        raw = stream.readline(min(remaining, MAX_EVENT_LINE + 1))
                        if not raw:
                            break
                        remaining -= len(raw)
                    continue
                try:
                    event = json.loads(raw)
                except (ValueError, UnicodeError, RecursionError):
                    continue
                if not isinstance(event, dict) or event.get("type") != "response.completed":
                    continue
                response = event.get("response")
                if not isinstance(response, dict):
                    continue
                reasoning = response.get("reasoning")
                fields = {"modelo": ("response.model", response.get("model")),
                          "proveedor": ("response.provider", response.get("provider")),
                          "esfuerzo": ("response.reasoning.effort", reasoning.get("effort") if isinstance(reasoning, dict) else None)}
                for key, (field, value) in fields.items():
                    if not _identifier(value):
                        continue
                    if value in values[key] or len(values[key]) >= 2:
                        continue
                    values[key].add(value)
                    proof = {"parametro": key, "valor": value, "archivo": path.name,
                             "linea": line_number, "evento": "response.completed", "campo": field}
                    if proof not in result["procedencia"]:
                        result["procedencia"].append(proof)
    except OSError:
        # Un fallo auxiliar de lectura no cambia el resultado original del proceso.
        return result
    for key, observed in values.items():
        if len(observed) == 1:
            result[key] = next(iter(observed))
    return result


def trace(value, agent, events_path, *, synthetic=False):
    return {"version": 1, "solicitada": requested(value),
            "argumentos_cli": [] if synthetic else sent_options(agent.get("comando")),
            "efectiva": effective_from_events(events_path)}


def validate_trace(record, value, events_path, *, synthetic=False):
    expected = trace(value, record["revisor"], events_path, synthetic=synthetic)
    require(type(record.get("version_registro")) is int and record["version_registro"] == 2
            and record.get("configuracion_revisor") == expected,
            "Registro de configuración ausente o inconsistente")
    if not synthetic:
        require(expected["argumentos_cli"] == options(value),
                "Los argumentos enviados no coinciden con la selección congelada")

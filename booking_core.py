"""Nucleo reutilizable de disponibilidad de reservas (contratos 005 y 006)."""

import datetime
import re


_TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})Z"
)


class InvalidInput(ValueError):
    """El documento no cumple el contrato de entrada."""


def _require_object(value, keys, location):
    if not isinstance(value, dict):
        raise InvalidInput(f"{location}: debe ser un objeto")
    if set(value) != set(keys):
        raise InvalidInput(
            f"{location}: claves obligatorias y exclusivas: {', '.join(keys)}"
        )


def _parse_timestamp(value, location):
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        raise InvalidInput(f"{location}: formato requerido YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.datetime(*(int(part) for part in match.groups()))
    except ValueError as exc:
        raise InvalidInput(f"{location}: fecha u hora invalida ({exc})") from exc


def _validate_interval(value, location, reservation=False):
    keys = ("id", "recurso", "inicio", "fin") if reservation else (
        "recurso", "inicio", "fin"
    )
    _require_object(value, keys, location)
    for key in keys:
        if not isinstance(value[key], str):
            raise InvalidInput(f"{location}.{key}: debe ser una cadena")
        if key in ("id", "recurso") and not any(
            not character.isspace() for character in value[key]
        ):
            raise InvalidInput(f"{location}.{key}: debe contener un caracter no blanco")
    start = _parse_timestamp(value["inicio"], f"{location}.inicio")
    end = _parse_timestamp(value["fin"], f"{location}.fin")
    if end <= start:
        raise InvalidInput(f"{location}: fin debe ser posterior a inicio")
    return start, end


def check_booking(document):
    """Valida sin modificar la entrada y devuelve un resultado independiente.

    Los intervalos son [inicio, fin) y los conflictos conservan el orden de
    entrada. Cualquier documento de dominio invalido causa InvalidInput.
    """
    _require_object(document, ("solicitud", "reservas"), "raiz")
    request = document["solicitud"]
    request_start, request_end = _validate_interval(request, "solicitud")
    reservations = document["reservas"]
    if not isinstance(reservations, list):
        raise InvalidInput("reservas: debe ser una lista")

    identifiers = set()
    conflicts = []
    for index, reservation in enumerate(reservations):
        location = f"reservas[{index}]"
        start, end = _validate_interval(reservation, location, reservation=True)
        identifier = reservation["id"]
        if identifier in identifiers:
            raise InvalidInput(f"{location}.id: identificador duplicado {identifier!a}")
        identifiers.add(identifier)
        if (reservation["recurso"] == request["recurso"]
                and start < request_end and end > request_start):
            conflicts.append(identifier)

    return {"disponible": not conflicts, "conflictos": conflicts}

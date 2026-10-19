"""Consulta local de disponibilidad de reservas (contrato 005)."""

import datetime
import json
import re
import sys


USAGE = "Uso: python3 -B check_booking.py [-h | --help] [--] archivo"
TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})Z"
)


class InvalidInput(ValueError):
    """El documento no cumple el contrato de entrada."""


def unique_object(pairs):
    """Detecta duplicados despues de decodificar los escapes de las claves."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput(f"clave JSON duplicada: {key!a}")
        result[key] = value
    return result


def reject_constant(value):
    raise InvalidInput(f"constante JSON no permitida: {value}")


def require_object(value, keys, location):
    if not isinstance(value, dict):
        raise InvalidInput(f"{location}: debe ser un objeto")
    if set(value) != set(keys):
        raise InvalidInput(
            f"{location}: claves obligatorias y exclusivas: {', '.join(keys)}"
        )


def parse_timestamp(value, location):
    match = TIMESTAMP.fullmatch(value)
    if match is None:
        raise InvalidInput(f"{location}: formato requerido YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.datetime(*(int(part) for part in match.groups()))
    except ValueError as exc:
        raise InvalidInput(f"{location}: fecha u hora invalida ({exc})") from exc


def validate_interval(value, location, reservation=False):
    keys = ("id", "recurso", "inicio", "fin") if reservation else (
        "recurso", "inicio", "fin"
    )
    require_object(value, keys, location)
    for key in keys:
        if not isinstance(value[key], str):
            raise InvalidInput(f"{location}.{key}: debe ser una cadena")
        if key in ("id", "recurso") and not any(
            not character.isspace() for character in value[key]
        ):
            raise InvalidInput(f"{location}.{key}: debe contener un caracter no blanco")
    start = parse_timestamp(value["inicio"], f"{location}.inicio")
    end = parse_timestamp(value["fin"], f"{location}.fin")
    if end <= start:
        raise InvalidInput(f"{location}: fin debe ser posterior a inicio")
    return start, end


def check_booking(document):
    """Valida todo el documento y devuelve los conflictos en orden de entrada."""
    require_object(document, ("solicitud", "reservas"), "raiz")
    request = document["solicitud"]
    request_start, request_end = validate_interval(request, "solicitud")
    reservations = document["reservas"]
    if not isinstance(reservations, list):
        raise InvalidInput("reservas: debe ser una lista")

    identifiers = set()
    conflicts = []
    for index, reservation in enumerate(reservations):
        location = f"reservas[{index}]"
        start, end = validate_interval(reservation, location, reservation=True)
        identifier = reservation["id"]
        if identifier in identifiers:
            raise InvalidInput(f"{location}.id: identificador duplicado {identifier!a}")
        identifiers.add(identifier)
        if (reservation["recurso"] == request["recurso"]
                and start < request_end and end > request_start):
            conflicts.append(identifier)

    return {"disponible": not conflicts, "conflictos": conflicts}


def parse_arguments(arguments):
    """Devuelve una ruta literal, o None cuando se solicita ayuda."""
    paths = []
    options = True
    help_requested = False
    for argument in arguments:
        if options and argument == "--":
            options = False
        elif options and argument in ("-h", "--help"):
            help_requested = True
        elif options and argument.startswith("-") and argument != "-":
            raise ValueError(f"opcion desconocida: {argument!a}")
        else:
            paths.append(argument)
    if len(paths) > 1:
        raise ValueError("se requiere exactamente un archivo")
    if help_requested:
        return None
    if not paths:
        raise ValueError("falta la ruta del archivo")
    return paths[0]


def main(arguments=None):
    if arguments is None:
        arguments = sys.argv[1:]
    try:
        path = parse_arguments(arguments)
    except ValueError as exc:
        print(f"{USAGE}\nError de argumentos: {exc}", file=sys.stderr)
        return 2
    if path is None:
        print(f"{USAGE}\nConsulta un documento JSON UTF-8 de solicitud y reservas.\n"
              "Los intervalos son [inicio, fin). No se crean reservas.\n"
              "-- permite rutas que empiezan por guion; -h y --help muestran ayuda.")
        return 0

    try:
        with open(path, "rb") as source:
            text = source.read().decode("utf-8")
        document = json.loads(
            text, object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        result = check_booking(document)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"Archivo {path}: {exc}", file=sys.stderr)
        return 1

    # Los escapes ASCII son JSON UTF-8 y preservan literalmente las cadenas.
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    # Conserva los nombres Unicode en los diagnosticos, incluso con locale ASCII.
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())

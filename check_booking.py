"""Consulta local de disponibilidad de reservas (contrato 005)."""

import json
import sys

import booking_core
from booking_core import InvalidInput


USAGE = "Uso: python3 -B check_booking.py [-h | --help] [--] archivo"


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


def check_booking(document):
    """Conserva el nombre importable y delega las reglas en booking_core."""
    return booking_core.check_booking(document)


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

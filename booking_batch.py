"""CLI de consultas independientes de disponibilidad por lotes."""

import json
import sys

import booking_core


_USAGE = "Uso: python3 -B booking_batch.py [--] archivo"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"clave JSON duplicada: {key!a}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"constante no permitida en JSON: {value}")


def _read_batch(path):
    with open(path, "r", encoding="utf-8", errors="strict") as source:
        documents = json.load(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    if not isinstance(documents, list):
        raise ValueError("la raiz JSON debe ser una lista")
    return documents


def _main():
    arguments = sys.argv[1:]
    if arguments in (["-h"], ["--help"]):
        print(_USAGE)
        print("Lee una lista JSON UTF-8 sin BOM y consulta cada documento.")
        print("Use -- para rutas que empiezan por guion; - es un archivo.")
        return 0

    if len(arguments) == 2 and arguments[0] == "--":
        path = arguments[1]
    elif len(arguments) == 1 and (
        arguments[0] == "-" or not arguments[0].startswith("-")
    ):
        path = arguments[0]
    else:
        print(
            f"{_USAGE}\nSe requiere una unica ruta; use -- antes de una "
            "ruta que empiece por guion. Ayuda: -h o --help como unico argumento.",
            file=sys.stderr,
        )
        return 2

    try:
        documents = _read_batch(path)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"{path!a}: {exc}", file=sys.stderr)
        return 1

    results = []
    for position, document in enumerate(documents, start=1):
        try:
            results.append(booking_core.check_booking(document))
        except booking_core.InvalidInput as exc:
            print(f"{path!a}: consulta {position}: {exc}", file=sys.stderr)
            return 1

    # Serializar solo despues de validar todo el lote evita salidas parciales.
    print(json.dumps(results, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

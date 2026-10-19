"""Exporta documentos v1 del inspector a CSV, sin consultar sus registros."""

import csv
import io
import json
import sys


COLUMNS = (
    "origen", "consulta_estado", "consulta_codigo_salida", "caso",
    "ejecucion_estado", "ejecucion_codigo_salida", "intentos_registrados",
    "max_intentos", "invocaciones_total", "max_invocaciones",
    "duracion_segundos",
)

HELP = """Uso: python3 -B export_runs.py [-h | --help] [--] archivo [archivo ...]

Exporta consultas JSON del inspector (esquema v1) a CSV en stdout.
Los archivos se validan antes de emitir la salida y conservan su orden.
Use -- para indicar archivos cuyos nombres empiezan por guion.

Opciones:
  -h, --help  Muestra esta ayuda y termina.
"""


class JsonNumber:
    """Número ya reconocido por el parser JSON, sin límites de conversión.

    Conservar el token evita tanto el límite de dígitos de int como el rango
    y el redondeo de float/Decimal. Todo token numérico JSON es finito; las
    constantes no JSON se rechazan por separado.
    """

    def __init__(self, text, integer=False):
        self.text = text
        self.integer = integer

    def negative(self):
        significand = self.text.lower().split("e", 1)[0]
        return self.text.startswith("-") and any(
            digit in "123456789" for digit in significand
        )


def parse_integer(text):
    return JsonNumber(text, integer=True)


def reject_constant(text):
    raise ValueError("constante no válida en JSON: " + text)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("clave duplicada: " + repr(key))
        result[key] = value
    return result


def object_fields(value, keys, context):
    if not isinstance(value, dict):
        raise ValueError(context + ": se requiere un objeto")
    missing = set(keys) - value.keys()
    extra = value.keys() - set(keys)
    if missing or extra:
        details = []
        if missing:
            details.append("faltan claves " + repr(sorted(missing)))
        if extra:
            details.append("claves adicionales " + repr(sorted(extra)))
        raise ValueError(context + ": " + "; ".join(details))


def is_integer(value):
    return isinstance(value, JsonNumber) and value.integer


def optional_integer(value, context, nonnegative=False):
    if value is None:
        return
    if not is_integer(value) or (nonnegative and value.negative()):
        expected = "entero no negativo" if nonnegative else "entero"
        raise ValueError(context + ": se requiere " + expected + " o null")


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def validate(document):
    object_fields(document, ("version_esquema", "consulta", "ejecucion"), "raíz")
    version = document["version_esquema"]
    if not is_integer(version) or version.text != "1":
        raise ValueError("version_esquema: se requiere el entero 1")

    query = document["consulta"]
    object_fields(query, ("estado", "codigo_salida", "incidencias"), "consulta")
    state = query["estado"]
    if state not in ("completada", "incompleta"):
        raise ValueError("consulta.estado: debe ser completada o incompleta")
    code = query["codigo_salida"]
    allowed_codes = ("0", "-0") if state == "completada" else ("1",)
    if not is_integer(code) or code.text not in allowed_codes:
        raise ValueError("consulta.codigo_salida: entero incoherente con consulta.estado")
    issues = query["incidencias"]
    if not isinstance(issues, list) or not all(nonblank(item) for item in issues):
        raise ValueError("consulta.incidencias: se requiere una lista de cadenas no blancas")
    if bool(issues) != (state == "incompleta"):
        raise ValueError("consulta.incidencias: incoherentes con consulta.estado")

    run = document["ejecucion"]
    object_fields(run, (
        "caso", "estado", "codigo_salida", "presupuestos",
        "intentos_registrados", "invocaciones", "duracion_segundos",
    ), "ejecucion")
    for key in ("caso", "estado"):
        if run[key] is not None and not nonblank(run[key]):
            raise ValueError("ejecucion." + key + ": se requiere cadena no blanca o null")
    optional_integer(run["codigo_salida"], "ejecucion.codigo_salida")
    optional_integer(run["intentos_registrados"], "ejecucion.intentos_registrados", True)

    for container, keys in (
        ("presupuestos", ("max_intentos", "max_invocaciones")),
        ("invocaciones", ("desarrollador", "revisor", "total")),
    ):
        values = run[container]
        context = "ejecucion." + container
        object_fields(values, keys, context)
        for key in keys:
            optional_integer(values[key], context + "." + key, True)

    duration = run["duracion_segundos"]
    if duration is not None and (
        not isinstance(duration, JsonNumber) or duration.negative()
    ):
        raise ValueError("ejecucion.duracion_segundos: se requiere número no negativo o null")


def read_document(path):
    with open(path, "r", encoding="utf-8", newline="") as source:
        document = json.load(
            source, parse_int=parse_integer, parse_float=JsonNumber,
            parse_constant=reject_constant, object_pairs_hook=unique_object,
        )
    validate(document)
    return document


def project_row(path, document):
    query = document["consulta"]
    run = document["ejecucion"]
    return (
        path, query["estado"], query["codigo_salida"], run["caso"],
        run["estado"], run["codigo_salida"], run["intentos_registrados"],
        run["presupuestos"]["max_intentos"], run["invocaciones"]["total"],
        run["presupuestos"]["max_invocaciones"], run["duracion_segundos"],
    )


def encode_row(values):
    output = io.StringIO(newline="")
    # QUOTE_ALL protege también los CR aislados con terminadores de registro LF.
    writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(value.text if isinstance(value, JsonNumber) else value for value in values)
    return output.getvalue().encode("utf-8")


def parse_arguments(arguments):
    paths = []
    for index, argument in enumerate(arguments):
        if argument == "--":
            paths.extend(arguments[index + 1:])
            break
        if argument in ("-h", "--help"):
            return None
        if argument.startswith("-"):
            raise ValueError("opción desconocida: " + repr(argument))
        paths.append(argument)
    if not paths:
        raise ValueError("se requiere al menos un archivo")
    return paths


def main(arguments=None):
    try:
        paths = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    except ValueError as error:
        print("export_runs.py: " + str(error), file=sys.stderr)
        return 2
    if paths is None:
        sys.stdout.write(HELP)
        return 0

    rows = [encode_row(COLUMNS)]
    for path in paths:
        try:
            document = read_document(path)
            rows.append(encode_row(project_row(path, document)))
        except (OSError, ValueError, RecursionError) as error:
            print("export_runs.py: " + repr(path) + ": " + str(error), file=sys.stderr)
            return 1
    # Ningún byte llega a stdout hasta validar y codificar todas las entradas.
    sys.stdout.buffer.write(b"".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

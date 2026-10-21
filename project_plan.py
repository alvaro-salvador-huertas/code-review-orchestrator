"""Datos de propuesta v1: esquema cerrado, validación local y vista revisable."""

import json
import re

from case_evidence import parse_json, require
from project_task_config import PROTECTED, fields, git, relative_path


MAX_REQUEST = 16000
MAX_RESPONSE = 1048576
PYTHON_FILE = r"[A-Za-z_][A-Za-z0-9_]*\.py"
RESTRICTIONS = {
    "archivos": "Solo archivos Python regulares de la raíz, creados o modificados; sin borrados.",
    "dependencias": "Solo biblioteca estándar de Python.",
    "infraestructura_protegida": sorted(PROTECTED),
    "ejecucion": "Solo planificación: no ejecutar código, comandos, pruebas ni contenido propuesto.",
    "autorizacion": "Toda propuesta requiere revisión humana; no es una configuración ejecutable.",
    "contexto": "Inventario del commit base, sin código ni cambios pendientes del workspace.",
}


def object_schema(properties):
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


def array_schema(items):
    return {"type": "array", "items": items, "maxItems": 100}


def response_schema():
    text = {"type": "string", "minLength": 1, "maxLength": 8000}
    return object_schema({
        "version": {"type": "integer", "enum": [1]},
        "objetivo": text,
        "viabilidad": {"type": "string", "enum": [
            "dentro_del_alcance", "pendiente_de_aclaracion", "fuera_del_alcance"]},
        "requisitos_interpretados": array_schema(text),
        "alcance": array_schema(text),
        "exclusiones": array_schema(text),
        "archivos": array_schema(object_schema({
            "ruta": {"type": "string", "pattern": "^" + PYTHON_FILE + "$"},
            "accion": {"type": "string", "enum": ["crear", "modificar"]},
            "proposito": text,
        })),
        "criterios_aceptacion": array_schema(object_schema({
            "descripcion": text,
            "ejemplos": array_schema(object_schema({
                "entrada": {"type": "string", "maxLength": 8000},
                "resultado_esperado": text,
            })),
        })),
        "preguntas_pendientes": array_schema(text),
        "supuestos": array_schema(text),
        "limitaciones": array_schema(text),
    })


def base_context(root):
    """Solo nombres y tipos del árbol Git: no leer fuentes para el modelo."""
    base = git(root, "rev-parse", "HEAD^{commit}").decode().strip()
    require(re.fullmatch(r"[0-9a-f]{40}", base), "Base Git inválida")
    inventory = []
    for entry in git(root, "ls-tree", "-z", base).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        name = name.decode("utf-8")
        if re.fullmatch(PYTHON_FILE, name) is None:
            continue
        mode, kind, _ = metadata.decode().split()
        regular = kind == "blob" and mode in ("100644", "100755")
        inventory.append({"ruta": name, "tipo": "archivo" if regular else "no_regular",
                          "protegido": name in PROTECTED})
    return {"commit_base": base, "inventario_python": inventory,
            "restricciones": RESTRICTIONS}


def validate_schema(value, schema):
    """Subconjunto explícito del esquema anterior, sin dependencias externas."""
    kind = schema["type"]
    types = {"object": dict, "array": list, "string": str, "integer": int}
    require(type(value) is types[kind], "Tipo JSON incorrecto: " + kind)
    if "enum" in schema:
        require(value in schema["enum"], "Valor fuera del esquema")
    if kind == "object":
        fields(value, schema["required"], "propuesta")
        for name, child in schema["properties"].items():
            validate_schema(value[name], child)
    elif kind == "array":
        require(len(value) <= schema["maxItems"], "Lista demasiado larga")
        serialized = [json.dumps(item, sort_keys=True, ensure_ascii=True) for item in value]
        require(len(serialized) == len(set(serialized)), "Elementos duplicados")
        for item in value:
            validate_schema(item, schema["items"])
    elif kind == "string":
        value.encode("utf-8")  # rechazar sustitutos aislados antes de renderizar/publicar
        require(len(value) <= schema.get("maxLength", 8000), "Texto demasiado largo")
        if schema.get("minLength"):
            require(bool(value.strip()), "Texto requerido vacío")
        if "pattern" in schema:
            require(re.fullmatch(PYTHON_FILE, value), "Solo archivos Python de la raíz")


def validate_response(raw, context):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RESPONSE, "Respuesta ausente o desmesurada")
    plan = parse_json(raw)
    validate_schema(plan, response_schema())
    observed = {item["ruta"]: item["tipo"] for item in context["inventario_python"]}
    names = []
    for item in plan["archivos"]:
        name = relative_path(item["ruta"], suffix=".py")
        require(name not in PROTECTED, "Infraestructura protegida")
        require(observed.get(name) != "no_regular", "Ruta de base no regular")
        require((name in observed) == (item["accion"] == "modificar"),
                "Acción incompatible con la existencia en la base")
        names.append(name)
    require(len(names) == len(set(names)), "Rutas propuestas duplicadas")
    criteria = [item["descripcion"].strip() for item in plan["criterios_aceptacion"]]
    require(len(criteria) == len(set(criteria)), "Criterios duplicados")
    for key in ("requisitos_interpretados", "alcance", "exclusiones",
                "preguntas_pendientes", "supuestos", "limitaciones"):
        texts = [item.strip() for item in plan[key]]
        require(len(texts) == len(set(texts)), "Textos duplicados: " + key)
    viability = plan["viabilidad"]
    if viability == "dentro_del_alcance":
        require(all(plan[key] for key in ("requisitos_interpretados", "alcance",
                                         "archivos", "criterios_aceptacion")),
                "Propuesta dentro del alcance incompleta")
    elif viability == "pendiente_de_aclaracion":
        require(bool(plan["preguntas_pendientes"]), "Faltan preguntas de aclaración")
    else:
        require(bool(plan["limitaciones"]) and not plan["archivos"],
                "Fuera del alcance exige limitaciones y ningún archivo ejecutable propuesto")
    return plan


def plan_state(plan):
    return ("necesita_aclaraciones" if plan["preguntas_pendientes"] or plan["supuestos"]
            or plan["viabilidad"] != "dentro_del_alcance" else "borrador")


def render_proposal(proposal):
    """Toda cadena variable se muestra como texto literal, no como Markdown activo."""
    lines = ["# Borrador de planificación", "",
             "Requiere revisión humana. No autoriza desarrollo ni ejecución.", ""]
    def section(title, value):
        lines.extend(["## " + title, ""])
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        lines.extend("    " + line for line in raw.splitlines())
        lines.append("")
    for label, key in (("Estado", "estado"), ("Petición original", "solicitud_original"),
                       ("Commit base", "commit_base"), ("Procedencia", "procedencia")):
        section(label, proposal[key])
    for name, value in proposal["propuesta"].items():
        section(name.replace("_", " ").capitalize(), value)
    if "continuacion" in proposal:
        section("Continuación del controlador (no texto del modelo)", proposal["continuacion"])
    return "\n".join(lines) + "\n"

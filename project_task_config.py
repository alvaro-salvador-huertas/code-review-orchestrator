"""Configuraciones de confianza: datos cerrados, sin comandos ni permisos configurables."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from case_evidence import digest, parse_json, require
from process_environment import process_environment


TYPE = "orquestacion_configurable_v1"
RESERVED = {"inspect-json", "export-csv"}
LIMITS = {"desarrollador": 600, "revisor": 600, "aceptacion": 300,
          "regresion": 600, "inventario": 120, "consulta_cli": 10}
PRIVATE = {".git", "runs", "__pycache__", ".agents", ".codex", ".aws", ".venv"}


@dataclass
class ConfiguredTask:
    """Selección del controlador, nunca reconstruida desde una entrega del agente."""
    config: dict
    document: dict
    raw: bytes
    materials: dict
    reference_state: dict | None = None


def fields(value, names, context):
    require(type(value) is dict and set(value) == set(names), f"Claves inválidas: {context}")


def relative_path(value, *, prefix=None, suffix=None):
    require(type(value) is str and value and "\\" not in value and "\x00" not in value,
            "Ruta inválida")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..") and not part.startswith(".")
                    and part not in PRIVATE for part in value.split("/")), "Ruta no permitida")
    require(prefix is None or value.startswith(prefix + "/"), f"La ruta debe estar bajo {prefix}")
    require(suffix is None or path.suffix == suffix, f"Extensión requerida: {suffix}")
    return value


def read_material(root, name):
    """Comprobar cada componente antes de leer; no seguir enlaces de directorios."""
    relative_path(name)
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), f"Enlace no permitido: {name}")
        require(stat.S_ISDIR(mode) if path != root / name else stat.S_ISREG(mode),
                f"Material no regular: {name}")
    return path.read_bytes()


def validate_document(document):
    fields(document, ("version", "identificador", "commit_base", "contrato", "archivo_editable",
                      "estado_inicial", "evaluador_aceptacion", "prompts", "referencias", "limites_segundos"), "configuración")
    require(type(document["version"]) is int and document["version"] == 1, "Versión no admitida")
    task = document["identificador"]
    require(type(task) is str and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", task)
            and len(task) <= 64 and task not in RESERVED, "Identificador inválido o reservado")
    require(type(document["commit_base"]) is str and re.fullmatch(r"[0-9a-f]{40}", document["commit_base"]),
            "Se requiere un commit base completo")
    relative_path(document["contrato"], prefix="tasks", suffix=".md")
    relative_path(document["evaluador_aceptacion"], prefix="evals", suffix=".py")
    editable = relative_path(document["archivo_editable"], suffix=".py")
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", editable),
            "Esta versión admite un archivo Python en la raíz del proyecto")
    require(document["estado_inicial"] in ("existente", "ausente"), "Estado inicial inválido")
    fields(document["prompts"], ("desarrollador", "revisor"), "prompts")
    for value in document["prompts"].values():
        relative_path(value, prefix="prompts", suffix=".md")
    references = document["referencias"]
    require(type(references) is list, "Referencias debe ser una lista")
    for name in references:
        relative_path(name)
    materials = [document["contrato"], document["evaluador_aceptacion"], *document["prompts"].values(), *references]
    require(len(set(materials)) == len(materials) and editable not in materials,
            "Materiales duplicados o archivo editable entre autoridades")
    fields(document["limites_segundos"], LIMITS, "límites")
    for name, maximum in LIMITS.items():
        value = document["limites_segundos"][name]
        require(type(value) is int and 1 <= value <= maximum, f"Límite inválido: {name}")
    require(document["limites_segundos"]["consulta_cli"] == 10,
            "Las consultas previas conservan su límite fijo de 10 segundos")
    return materials


def git(root, *args):
    with process_environment("evaluation") as environment:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                              timeout=10, env=environment).stdout


def load_task(root, path):
    """Leer una vez los materiales del usuario y comprobar su base antes de invocar."""
    root = Path(root).absolute()
    name = relative_path(str(path), prefix="tasks/config", suffix=".json")
    raw = read_material(root, name)
    document = parse_json(raw)
    names = validate_document(document)
    require(name not in names, "La configuración no puede ser una referencia de sí misma")
    materials = {item: read_material(root, item) for item in names}
    require(all(content.strip() for content in materials.values()), "Material vacío")
    base = document["commit_base"]
    matches = re.findall(rb"(?m)^Base: `([0-9a-f]{40})`\s*$", materials[document["contrato"]])
    require(matches == [base.encode()], "El contrato debe declarar exactamente la misma base")
    require(git(root, "rev-parse", base + "^{commit}").decode().strip() == base, "Base local no disponible")
    editable = document["archivo_editable"]
    entries = git(root, "ls-tree", "-z", base, "--", editable).split(b"\0")
    entry = entries[0]
    initial = {"tipo": "ausente", "sha256": None, "modo": None}
    if entry:
        metadata, found = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        require(found.decode() == editable and kind == "blob" and mode in ("100644", "100755"),
                "Editable inicial no regular")
        initial = {"tipo": "archivo", "sha256": digest(git(root, "cat-file", "blob", oid)), "modo": int(mode[-3:], 8)}
    absent = document["estado_inicial"] == "ausente"
    require((initial["tipo"] == "ausente") == absent, "Estado inicial distinto de la base Git")
    config = {"tipo": TYPE, "tarea": document["identificador"], "base": base,
              "contrato": document["contrato"], "editable": editable, "ausente": absent, "esquema": None,
              "desarrollo": document["prompts"]["desarrollador"], "revision": document["prompts"]["revisor"],
              "suites": {"aceptacion": document["evaluador_aceptacion"], "regresion": None},
              "limites": document["limites_segundos"], "referencias": document["referencias"],
              "configurable": True, "origen_configuracion": name, "configuracion_sha256": digest(raw),
              "editable_inicial": initial}
    return ConfiguredTask(config, document, raw, materials)

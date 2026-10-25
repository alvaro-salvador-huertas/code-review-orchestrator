"""Preparación local de borradores; no invoca procesos ni autoriza el motor."""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
from urllib.parse import quote

from case_evidence import digest, parse_json, require
from project_plan_continuation import encoded, load_parent, regular_bytes
from project_task_config import LIMITS, relative_path


PROJECT = Path(__file__).resolve().parent
SOURCES = ("prepare_project.py", "project_plan_continuation.py", "project_plan.py",
           "project_task_config.py", "case_evidence.py", "process_environment.py")
AUTHORITIES = {"tasks", "evals", "prompts"}
# Utilidades reservadas por la congelación de materiales del motor.
RESERVED_MATERIALS = {"repair_case.py", "run_case.py", "case_config.py",
                      "case_evidence.py", "process_environment.py", "project_test_inventory.py"}
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def literal(value):
    """Texto simple indentado; JSON reversible para listas, controles y espacios límite."""
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(ord(char) < 32 or char in "\x7f\u0085\u2028\u2029" for char in value)):
        value = json.dumps(value, ensure_ascii=True, indent=2)
    return "\n".join("    " + line for line in value.split("\n")) + "\n\n"


def section(title, value):
    return "## " + title + "\n\n" + literal(value)


def absolute_path(path):
    # En Linux // y / designan el mismo árbol: comparar con una única raíz.
    # No resolver enlaces; el destino se abre después componente a componente.
    return Path("/" + os.path.abspath(path).lstrip("/"))


def configuration(parent):
    context = parse_json(parent.materials["contexto.json"])
    return {
        "tipo": "preparacion_tarea_borrador", "version_borrador": 1, "ejecutable": False,
        "version_configuracion_objetivo": 2,
        "derivado": {
            "commit_base": parent.proposal["commit_base"],
            "archivos_propuestos": [
                {"ruta": item["ruta"], "accion": item["accion"],
                 "estado_inicial_segun_inventario": "ausente" if item["accion"] == "crear" else "existente"}
                for item in parent.proposal["propuesta"]["archivos"]],
            "referencias_planificacion": context.get("referencias", []), "consulta_cli_segundos": 10},
        "por_decidir": {
            "identificador": None, "contrato": None, "evaluador_aceptacion": None,
            "prompts": {"desarrollador": None, "revisor": None}, "referencias": None,
            "limites_segundos": {name: None for name in LIMITS if name != "consulta_cli"}},
        "comprobaciones": {"base_disponible": "no_comprobada", "modos_git": "no_comprobados",
                           "regresion_inicial": "no_ejecutada", "aceptacion_inicial": "no_ejecutada"},
    }


def contract(parent, draft):
    plan = parent.proposal["propuesta"]
    text = ("# Contrato borrador\n\nRequiere revisión humana. No autoriza ejecución.\n\n"
            f"Base: `{parent.proposal['commit_base']}`\n\n"
            "Procedencia: propuesta del registro seleccionado; identidades en revision.md.\n\n")
    text += section("Objetivo", plan["objetivo"])
    for title, key, label in (("Requisitos", "requisitos_interpretados", "R"),
                              ("Alcance", "alcance", "A"), ("Exclusiones", "exclusiones", "E")):
        text += "## " + title + "\n\n"
        for number, value in enumerate(plan[key], 1):
            text += f"{label}{number}:\n\n" + literal(value)
        if not plan[key]:
            text += "No consta en el plan.\n\n"
    text += "## Archivos\n\n"
    for item, initial in zip(plan["archivos"], draft["derivado"]["archivos_propuestos"]):
        text += literal(f"{item['ruta']} | {item['accion']} | "
                        f"{initial['estado_inicial_segun_inventario']} según inventario histórico")
        text += literal(item["proposito"])
    text += "## Criterios existentes\n\n"
    for number, criterion in enumerate(plan["criterios_aceptacion"], 1):
        text += f"C{number}:\n\n" + literal(criterion["descripcion"])
        for example in criterion["ejemplos"]:
            text += "Entrada:\n\n" + literal(example["entrada"])
            text += "Resultado esperado:\n\n" + literal(example["resultado_esperado"])
        if not criterion["ejemplos"]:
            text += "No constan ejemplos en el plan.\n\n"
    text += "## Limitaciones\n\n"
    text += "".join(literal(item) for item in plan["limitaciones"]) or "No consta en el plan.\n\n"
    return text.rstrip("\n") + "\n"


def chain_metadata(parent):
    """Proyectar metadatos ya validados, contrastando los bytes releídos con el lector."""
    chain, path = [], parent.path
    for _ in range(parent.depth + 1):
        file = path / "propuesta.json"
        mode, size, sha = parent.identities[str(file)]
        raw = regular_bytes(file, size)
        require(digest(raw) == sha and stat.S_IMODE(file.lstat().st_mode) == mode,
                "Origen alterado al renderizar")
        proposal = parse_json(raw)
        chain.append({"registro": str(path), "version": proposal["version"],
                      "profundidad": proposal.get("continuacion", {}).get("profundidad", 0),
                      "estado_archivado": proposal["estado"]})
        if proposal["version"] == 1:
            break
        path = Path(proposal["continuacion"]["padre"]["registro"])
    return list(reversed(chain))


def revision(parent, draft, chain, complete):
    plan = parent.proposal["propuesta"]
    text = ("# Revisión de preparación\n\nRequiere revisión humana. No autoriza ejecución.\n\n"
            "Estado: " + ("paquete_borrador" if complete else "solo_diagnostico") + ".\n\n")
    text += section("Procedencia", {"registro": str(parent.path), "commit_base": parent.proposal["commit_base"],
                                    "cadena": chain})
    text += section("Solicitud original", parent.proposal["solicitud_original"])
    text += section("Viabilidad declarada", plan["viabilidad"])
    origins = {item["profundidad"]: item["registro"] for item in chain}

    def question_origin(item):
        generation, index = item["id"].split(":p")
        return dict(item, origen_pregunta={"registro": origins[int(generation[1:])],
                    "campo": f"propuesta.preguntas_pendientes[{int(index) - 1}]"})

    text += section("Preguntas pendientes", [question_origin(item) for item in parent.pending]
                    or "No constan preguntas pendientes.")
    text += section("Supuestos pendientes", [dict(item, origen_supuesto=parent.assumption_origins[item["id"]])
                    for item in parent.pending_assumptions] or "No constan supuestos pendientes.")
    text += section("Respuestas acumuladas", [question_origin(item) for item in parent.answers]
                    or "No constan respuestas.")
    text += section("Decisiones acumuladas", parent.decisions or "No constan decisiones.")
    text += ("Las decisiones no reescriben el contrato: contrastar que el último plan las respeta.\n"
             "Un rechazo no es aceptación de otro supuesto; una omisión no resuelve pendientes.\n\n")
    if not complete:
        text += ("No se generan contrato ni configuración: resolver los pendientes y la viabilidad\n"
                 "mediante los mecanismos de continuidad, en una operación separada.\n\n")
    text += section("Datos trasladables", draft["derivado"])
    refs = draft["derivado"]["referencias_planificacion"]
    if not refs:
        text += "No constan referencias archivadas; no equivale a elegir una tarea sin referencias.\n\n"
    editables = {item["ruta"] for item in plan["archivos"]}
    conflicts = [{"ruta": item["ruta"], "motivo": "Referencia del plan coincidente con un editable."}
                 for item in refs if item["ruta"] in editables]
    conflicts += [{"ruta": item["ruta"], "motivo": "Nombre reservado de utilidad del controlador."}
                  for item in refs if item["ruta"] in RESERVED_MATERIALS]
    conflicts += [{"ruta": item["ruta"], "motivo": "Referencia vacía; el motor exige materiales no vacíos."}
                  for item in refs if item["bytes"] == 0]
    text += section("Incompatibilidades de referencias detectables", conflicts or
                    "No se detectan coincidencias con editables/utilidades ni referencias vacías.")
    text += ("Las referencias conservan sus textos en materiales/referencias.json de los originales.\n"
             "No son autoridades seleccionadas. Revisar colisiones con las futuras autoridades.\n"
             "La línea Base de un contrato consultado puede corresponder a otra tarea: no sustituye\n"
             "la base del plan ni acredita el estado inicial de los editables.\n\n")
    text += section("Materiales y decisiones por preparar", draft["por_decidir"])
    text += ("null significa no aportado como autoridad, no ausencia en el repositorio.\n"
             "Revisar requisitos y contrato definitivo; elegir identificador y rutas bajo tasks/\n"
             "y tasks/config/. Preparar evaluador bajo evals/, con --project, clases explícitas\n"
             "de unittest.TestCase, un TextTestRunner y código 0/1; escribir ambos prompts bajo\n"
             "prompts/. No se han generado ni seleccionado estos materiales de confianza.\n"
             "Elegir referencias y límites variables; consulta_cli conserva 10 segundos.\n\n")
    text += section("Máximos del motor en segundos", LIMITS)
    text += section("Comprobaciones pendientes", draft["comprobaciones"])
    text += ("Verificar disponibilidad del commit y modos Git. Un archivo nuevo requiere modo 0644;\n"
             "uno existente conserva el modo de la base. El inventario no prueba comportamiento.\n\n"
             "## Límite de la aceptación inicial\n\n"
             "El motor exige regresión superada y aceptación inicialmente fallida por aserciones,\n"
             "con identidades, informes, códigos y cierres acreditados; cero errores técnicos.\n"
             "No se ha ejecutado ninguna evaluación. Una aceptación ya superada o un error de\n"
             "importación no habilitan el flujo. Una refactorización que conserva comportamiento\n"
             "puede ser válida sin cumplir esa precondición: preparar, en su caso, trabajo manual\n"
             "supervisado fuera del motor. No fabricar fallos, cambiar criterios/base para forzar\n"
             "rojo ni modificar el motor. El paquete sigue siendo no ejecutable.\n\n"
             "## Mapeo de campos\n\n"
             "Objetivo, R/A/E, archivos, criterios/ejemplos y limitaciones proceden, en orden, de\n"
             "propuesta.objetivo, requisitos_interpretados, alcance, exclusiones, archivos,\n"
             "criterios_aceptacion y limitaciones del registro seleccionado. Los números empiezan\n"
             "en 1; los índices JSON, en 0. Base procede del envoltorio/contexto; estados iniciales,\n"
             "de acciones e inventario; referencias, del contexto y los textos archivados.\n\n"
             "## Conservación\n\n"
             "Paquete local dependiente de la cadena en sus rutas originales. No contiene el\n"
             "repositorio base ni una copia portable. No refresca datos desde HEAD o el checkout.\n"
             "Los hashes acreditan correspondencia, no autenticidad ni aprobación.\n\n")
    text += section("Fuentes locales del lector y exportador (SHA-256)", {
        name: digest(regular_bytes(PROJECT / name)) for name in SOURCES})
    text += "Estas identidades no sustituyen la procedencia del controlador histórico.\n\n"
    text += "## Evidencia original leída\n\n"
    for number, (path, (mode, size, sha)) in enumerate(parent.identities.items(), 1):
        text += f"[Original {number}](<{quote(str(absolute_path(path)), safe='/')}>)\n\n"
        text += literal({"ruta": path, "modo": mode, "bytes": size, "sha256": sha})
    return text.rstrip("\n") + "\n"


def directory_fd(path):
    """Abrir desde / componente a componente, sin seguir enlaces ni lanzar procesos."""
    fd = os.open(path.anchor, DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def identity(info):
    return info.st_dev, info.st_ino


def destination_path(destination, project_root, chain):
    # No normalizar '..' antes de examinarlo: podría ocultar un enlace intermedio.
    require(".." not in Path(destination).parts, "Destino con componente .. no permitido")
    target = absolute_path(destination)
    # Regla compartida: componentes canónicos, no ocultos/privados, sin '\\' ni NUL.
    relative_path(target.relative_to(target.anchor).as_posix())
    root = absolute_path(project_root)
    if target.is_relative_to(root):
        parts = target.relative_to(root).parts
        require(not parts or parts[0] not in AUTHORITIES, "Destino dentro de autoridades del proyecto")
    for item in chain:
        record = absolute_path(item["registro"])
        require(not (target == record or target in record.parents or record in target.parents),
                "Destino solapado con un registro original")
    return target


def write_exclusive(fd, name, raw, created):
    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        created[name] = [identity(os.fstat(output)), b""]
        written = 0
        while written < len(raw):
            count = os.write(output, memoryview(raw)[written:])
            require(count > 0, "Escritura incompleta")
            written += count
            created[name][1] = raw[:written]
    finally:
        os.close(output)


def owned_file(fd, name, expected, raw):
    source = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
    with os.fdopen(source, "rb") as stream:
        info = os.fstat(stream.fileno())
        return (stat.S_ISREG(info.st_mode) and identity(info) == expected
                and info.st_size == len(raw) and stream.read(len(raw) + 1) == raw
                and identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == expected)


def cleanup(fd, created):
    """Retirar solo archivos propios con la identidad y los bytes que escribimos."""
    for name, (expected, raw) in reversed(list(created.items())):
        try:
            if owned_file(fd, name, expected, raw):
                os.unlink(name, dir_fd=fd)
        except OSError:
            pass  # No retirar archivos ajenos, cambiados o inaccesibles.


def export_preparation(source, destination, *, project_root=PROJECT):
    parent = load_parent(source)
    chain = chain_metadata(parent)
    target = destination_path(destination, project_root, chain)
    complete = (parent.proposal["propuesta"]["viabilidad"] == "dentro_del_alcance"
                and not parent.pending and not parent.pending_assumptions)
    draft = configuration(parent)
    files = {}
    if complete:
        files["contrato.borrador.md"] = contract(parent, draft).encode("utf-8")
        files["configuracion.borrador.json"] = encoded(draft)
    files["revision.md"] = revision(parent, draft, chain, complete).encode("utf-8")
    require(parent.intact(), "Origen alterado antes de exportar")
    enclosing = directory_fd(target.parent)
    output, owned, created = None, None, {}
    try:
        os.mkdir(target.name, mode=0o700, dir_fd=enclosing)  # también rechaza enlaces rotos
        owned = identity(os.stat(target.name, dir_fd=enclosing, follow_symlinks=False))
        output = os.open(target.name, DIRECTORY_FLAGS, dir_fd=enclosing)
        require(identity(os.fstat(output)) == owned, "Directorio destino sustituido")
        for name, raw in files.items():
            write_exclusive(output, name, raw, created)  # revision.md se escribe al final
        require(set(os.listdir(output)) == set(files) and
                all(owned_file(output, name, *entry) for name, entry in created.items()),
                "Contenido de destino alterado")
        require(parent.intact(), "Origen alterado durante la exportación")
        current = directory_fd(target.parent)
        try:
            require(identity(os.fstat(current)) == identity(os.fstat(enclosing)) and
                    identity(os.stat(target.name, dir_fd=current, follow_symlinks=False)) == owned,
                    "Ruta de destino sustituida")
        finally:
            os.close(current)
    except BaseException:
        if output is not None and identity(os.fstat(output)) == owned:
            cleanup(output, created)
        if owned is not None:
            try:
                if identity(os.stat(target.name, dir_fd=enclosing, follow_symlinks=False)) == owned:
                    os.rmdir(target.name, dir_fd=enclosing)  # solo vacío; nunca recursivo
            except OSError:
                pass
        raise
    finally:
        if output is not None:
            os.close(output)
        os.close(enclosing)
    return 0 if complete else 3


def path_argument(value):
    try:
        require(bool(value.strip()) and "\0" not in value, "La ruta no puede estar vacía ni contener NUL")
        value.encode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def main(arguments=None, *, project_root=PROJECT):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--from-plan", required=True, type=path_argument, action="append", metavar="REGISTRO")
    parser.add_argument("--output", required=True, type=path_argument, action="append", metavar="DIRECTORIO")
    args = parser.parse_args(arguments)
    if len(args.from_plan) != 1 or len(args.output) != 1:
        parser.error("No se pueden repetir --from-plan ni --output")
    try:
        code = export_preparation(args.from_plan[0], args.output[0], project_root=project_root)
    except (OSError, ValueError, UnicodeError, RecursionError, KeyboardInterrupt) as exc:
        print("Error de preparación: " + ascii(str(exc) or "Interrupción") +
              ". No hay cierre válido; si queda un destino incompleto, no se reutilizará.", file=sys.stderr)
        return 1
    print("Paquete borrador generado; no ejecutable." if code == 0 else
          "Solo diagnóstico generado: quedan pendientes o viabilidad insuficiente.")
    return code


if __name__ == "__main__":
    sys.exit(main())

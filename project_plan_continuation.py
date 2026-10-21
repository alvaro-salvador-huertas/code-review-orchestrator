"""Continuidad local y acotada; los datos del modelo nunca confirman respuestas."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat

from case_evidence import digest, parse_json, require
from project_plan import (MAX_REQUEST, PYTHON_FILE, plan_state, render_proposal,
                          response_schema, validate_response)
from project_task_config import fields, relative_path


MAX_DEPTH = 8  # original + ocho revisiones; se comprueba antes de recorrer padres
MAX_FILE = 8 * 1024 * 1024
MAX_CHAIN_BYTES = 64 * 1024 * 1024
MAX_ANSWERS = 1024 * 1024
MAX_MESSAGE = 4 * 1024 * 1024
MAX_ARTIFACTS = 64
MAX_ANSWER_TEXT = 8000
MATERIALS = ("solicitud.txt", "contexto.json", "respuesta.schema.json", "instrucciones.md")
CONTROLLER_SOURCES = ("plan_project.py", "project_plan.py", "project_plan_continuation.py",
                      "project_task_config.py", "case_evidence.py", "repair_project.py",
                      "review_case.py", "repair_case.py", "process_environment.py",
                      "prompts/planner_project.md")


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def regular_bytes(path, limit=MAX_FILE):
    """No seguir enlaces (tampoco directorios), ni abrir FIFO; lectura limitada."""
    path = Path(os.path.abspath(path))
    for parent in reversed(path.parents):
        require(stat.S_ISDIR(parent.lstat().st_mode), "Directorio no regular: " + str(parent))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), "Archivo no regular: " + str(path))
    require(before.st_size <= limit, "Archivo supera el límite: " + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and (before.st_dev, before.st_ino) ==
                (opened.st_dev, opened.st_ino), "Archivo sustituido durante lectura")
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Archivo supera el límite: " + str(path))
    return raw


def utf8(value, limit, label, *, nonblank=False):
    require(type(value) is str, "Texto requerido: " + label)
    value.encode("utf-8")
    require(len(value) <= limit and "\0" not in value and (not nonblank or value.strip()),
            "Texto inválido o excesivo: " + label)


def context_valid(context):
    fields(context, ("commit_base", "inventario_python", "restricciones"), "contexto")
    require(type(context["commit_base"]) is str and
            re.fullmatch(r"[0-9a-f]{40}", context["commit_base"]), "Commit base inválido")
    inventory = context["inventario_python"]
    require(type(inventory) is list and len(inventory) <= 10000, "Inventario inválido")
    names = []
    for item in inventory:
        fields(item, ("ruta", "tipo", "protegido"), "inventario")
        require(type(item["ruta"]) is str and re.fullmatch(PYTHON_FILE, item["ruta"])
                and item["tipo"] in ("archivo", "no_regular") and type(item["protegido"]) is bool,
                "Entrada de inventario inválida")
        names.append(item["ruta"])
    require(len(names) == len(set(names)), "Inventario duplicado")
    restrictions = context["restricciones"]
    fields(restrictions, ("archivos", "dependencias", "infraestructura_protegida", "ejecucion",
                          "autorizacion", "contexto"), "restricciones")
    for key in restrictions:
        if key != "infraestructura_protegida":
            utf8(restrictions[key], 8000, key, nonblank=True)
    protected = restrictions["infraestructura_protegida"]
    require(type(protected) is list and len(protected) <= 1000 and
            all(type(p) is str and re.fullmatch(PYTHON_FILE, p) for p in protected),
            "Protección inválida")


def questions(plan, depth, carried=()):
    # Cada salida del modelo tiene sus propias preguntas, sin emparejar textos.
    return list(carried) + [{"id": f"r{depth}:p{index}", "pregunta": text}
                            for index, text in enumerate(plan["preguntas_pendientes"], 1)]


def assumptions(plan, depth, carried=()):
    return list(carried) + [{"id": f"r{depth}:s{index}", "supuesto": text}
                            for index, text in enumerate(plan["supuestos"], 1)]


def reference(parent):
    return {"registro": str(parent.path), "propuesta_sha256": digest(parent.proposal_raw),
            "resultado_sha256": digest(parent.result_raw)}


def template(parent):
    return {"version": 1, "tipo": "respuestas_planificacion", "origen": reference(parent),
            "respuestas": [dict(q, respuesta="") for q in parent.pending]}


def decisions_template(parent):
    return {"version": 1, "tipo": "decisiones_planificacion", "origen": reference(parent),
            "decisiones": [dict(item, origen_supuesto=parent.assumption_origins[item["id"]],
                                decision="sin_decidir", explicacion="", alternativa="")
                           for item in parent.pending_assumptions]}


def validate_decisions(raw, parent):
    require(len(raw) <= MAX_ANSWERS, "Decisiones superan 1 MiB")
    value = parse_json(raw)
    expected = decisions_template(parent)
    fields(value, expected, "decisiones")
    require(type(value["version"]) is int and value["version"] == 1 and
            value["tipo"] == expected["tipo"] and value["origen"] == expected["origen"],
            "Origen de decisiones no corresponde al registro exacto")
    require(type(value["decisiones"]) is list and len(value["decisiones"]) == len(expected["decisiones"]),
            "Conjunto de supuestos incorrecto")
    decided, pending = [], []
    for item, original, assumption in zip(value["decisiones"], expected["decisiones"], parent.pending_assumptions):
        fields(item, original, "decisión individual")
        require(all(item[k] == original[k] for k in ("id", "supuesto", "origen_supuesto")),
                "Identificador, supuesto u origen alterados")
        action = item["decision"]
        require(type(action) is str and action in ("sin_decidir", "aceptar", "rechazar", "corregir"),
                "Decisión no admitida")
        utf8(item["explicacion"], MAX_ANSWER_TEXT, "explicación", nonblank=action == "rechazar")
        utf8(item["alternativa"], MAX_ANSWER_TEXT, "alternativa", nonblank=action == "corregir")
        require(action == "rechazar" or item["explicacion"] == "", "Explicación solo para rechazar")
        require(action == "corregir" or item["alternativa"] == "", "Alternativa solo para corregir")
        if action == "sin_decidir":
            pending.append(assumption)
        else:
            decided.append(item)
    return parent.decisions + decided, pending


def validate_answers(raw, parent, *, require_answer=True):
    require(len(raw) <= MAX_ANSWERS, "Respuestas superan 1 MiB")
    value = parse_json(raw)
    expected = template(parent)
    fields(value, expected, "respuestas")
    require(type(value["version"]) is int and value["version"] == 1 and
            value["tipo"] == expected["tipo"] and value["origen"] == expected["origen"],
            "Origen de respuestas no corresponde al registro exacto")
    require(type(value["respuestas"]) is list and
            len(value["respuestas"]) == len(expected["respuestas"]), "Conjunto de preguntas incorrecto")
    answered, pending = [], []
    for item, question in zip(value["respuestas"], parent.pending):
        fields(item, ("id", "pregunta", "respuesta"), "respuesta individual")
        require({key: item[key] for key in question} == question, "Identificador o pregunta incorrectos")
        utf8(item["respuesta"], MAX_ANSWER_TEXT, "respuesta")
        if item["respuesta"].strip():
            answered.append(item)
        else:
            pending.append(question)
    require(answered or not require_answer, "Se necesita al menos una respuesta no blanca")
    return parent.answers + answered, pending


@dataclass
class Parent:
    path: Path
    result_raw: bytes
    proposal_raw: bytes
    proposal: dict
    materials: dict
    depth: int
    pending: list
    answers: list
    identities: dict
    pending_assumptions: list
    decisions: list
    assumption_origins: dict

    def intact(self):
        try:
            return all((stat.S_IMODE(Path(path).lstat().st_mode), Path(path).lstat().st_size,
                        digest(regular_bytes(path, identity[1]))) == identity
                       for path, identity in self.identities.items())
        except (OSError, ValueError):
            return False


def continuation_data(parent, answers_raw=None, decisions_raw=None, *, version=2):
    require(parent.depth < MAX_DEPTH, "Máximo de ocho revisiones alcanzado")
    if version == 1:  # reconstrucción exacta de evidencia histórica, nunca nueva ejecución
        require(parent.proposal["version"] <= 2, "Una revisión v3 no puede continuar como formato histórico v2")
        require(answers_raw is not None and decisions_raw is None, "Faltan respuestas históricas")
        answers, pending = validate_answers(answers_raw, parent)
        return {"version": 1, "profundidad": parent.depth + 1, "padre": reference(parent),
                "respuestas_confirmadas": answers, "pendientes_anteriores": pending}
    require(version == 2, "Versión de continuidad no admitida")
    require(answers_raw is not None or decisions_raw is not None, "Faltan respuestas o decisiones")
    require(sum(len(raw) for raw in (answers_raw, decisions_raw) if raw is not None) <= MAX_ANSWERS,
            "Entradas de continuación superan 1 MiB en conjunto")
    answers, pending = (validate_answers(answers_raw, parent, require_answer=False) if answers_raw is not None
                        else (parent.answers, parent.pending))
    decisions, pending_assumptions = (validate_decisions(decisions_raw, parent) if decisions_raw is not None
                                      else (parent.decisions, parent.pending_assumptions))
    require(len(answers) > len(parent.answers) or len(decisions) > len(parent.decisions),
            "Se necesita una respuesta no blanca o una decisión efectiva nueva")
    return {"version": 2, "profundidad": parent.depth + 1, "padre": reference(parent),
            "respuestas_confirmadas": answers, "pendientes_anteriores": pending,
            "decisiones_confirmadas": decisions, "supuestos_anteriores": pending_assumptions}


def load_parent(path):
    """Verifica la cadena completa acotada. Los hashes no autentican al autor."""
    identities, visited = {}, set()
    total = 0

    def read(path):
        nonlocal total
        raw = regular_bytes(path, min(MAX_FILE, MAX_CHAIN_BYTES - total))
        total += len(raw)
        identities[str(path)] = (stat.S_IMODE(path.lstat().st_mode), len(raw), digest(raw))
        return raw

    def load(path, remaining):
        require(remaining >= 0, "Cadena supera ocho revisiones")
        path = Path(os.path.abspath(path))
        require(path not in visited, "Cadena cíclica")
        visited.add(path)
        result_raw = read(path / "resultado.json")
        result = parse_json(result_raw)
        require(type(result) is dict and type(result.get("version")) is int and result["version"] == 1
                and result.get("tipo") == "planificacion_proyecto" and result.get("rol") == "planificador"
                and type(result.get("codigo_salida")) is int and result["codigo_salida"] == 0
                and result.get("fallo") is None and result.get("aprobada") is False
                and result.get("registro") == str(path), "Registro de planificación no válido")
        require(result.get("invocaciones") == {"planificador": 1} and result.get("limite_segundos") == 300
                and result.get("respuesta_tipo") == "regular", "Contabilidad de origen incoherente")
        agent = result.get("planificador", {})
        require(type(agent) is dict and agent.get("estado") == "finalizada" and agent.get("codigo_salida") == 0
                and agent.get("invocaciones") == 1, "Proceso de origen no válido")
        integrity = result.get("integridad")
        require(type(integrity) is dict and
                {"proyecto_intacto", "base_intacta", "materiales_intactos", "workspace_intacto"} <= set(integrity)
                and all(v is True for v in integrity.values()), "Integridad de origen no acreditada")
        manifest = result.get("artefactos_sha256")
        require(type(manifest) is dict and len(manifest) <= MAX_ARTIFACTS, "Inventario de evidencia excesivo")
        blobs = {}
        for name, sha in manifest.items():
            relative_path(name)
            require(name != "resultado.json" and type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha),
                    "Hash de evidencia inválido")
            blobs[name] = read(path / name)
            require(digest(blobs[name]) == sha, "Hash de evidencia no corresponde: " + name)
        needed = {"propuesta.json", "propuesta.md", "procedencia.json", "reserva.json",
                  "planificador/respuesta_original.txt", "planificador/entrada.txt"}
        needed.update("materiales/" + name for name in MATERIALS)
        require(needed <= set(blobs), "Faltan materiales o propuesta de origen")
        proposal = parse_json(blobs["propuesta.json"])
        require(type(proposal) is dict and type(proposal.get("version")) is int and
                proposal["version"] in (1, 2, 3), "Versión de propuesta no admitida")
        keys = {"version", "tipo", "estado", "solicitud_original", "commit_base", "procedencia", "propuesta"}
        fields(proposal, keys | ({"continuacion"} if proposal["version"] >= 2 else set()), "propuesta archivada")
        materials = {name.removeprefix("materiales/"): raw for name, raw in blobs.items()
                     if name.startswith("materiales/")}
        require(set(materials) == set(MATERIALS) | ({"continuacion.json"} if proposal["version"] >= 2 else set()),
                "Materiales inesperados")
        request = materials["solicitud.txt"].decode("utf-8")
        utf8(request, MAX_REQUEST, "solicitud original", nonblank=True)
        context = parse_json(materials["contexto.json"])
        context_valid(context)
        require(parse_json(materials["respuesta.schema.json"]) == response_schema(), "Esquema de origen distinto")
        raw = blobs["planificador/respuesta_original.txt"]
        plan = validate_response(raw, context)
        require(proposal["tipo"] == "propuesta_planificacion" and proposal["propuesta"] == plan
                and proposal["solicitud_original"] == result.get("solicitud_original") == request
                and proposal["commit_base"] == result.get("commit_base") == context["commit_base"],
                "Propuesta, respuesta y materiales no corresponden")
        require(proposal["procedencia"] == {"rol": "planificador", "registro": path.name,
                "respuesta_sha256": digest(raw), "requiere_revision_humana": True}, "Procedencia de propuesta incorrecta")
        provenance = parse_json(blobs["procedencia.json"])
        require(provenance["rol"] == "planificador" and provenance["commit_base"] == context["commit_base"]
                and provenance["solicitud_sha256"] == digest(materials["solicitud.txt"])
                and provenance["prompt_sha256"] == digest(blobs["planificador/entrada.txt"]), "Procedencia incoherente")
        require(set(provenance["materiales"]) == set(materials), "Inventario de materiales incoherente")
        for name, raw_material in materials.items():
            require(provenance["materiales"][name] == {"tipo": "archivo", "sha256": digest(raw_material),
                    "modo": stat.S_IMODE((path / "materiales" / name).lstat().st_mode)}, "Identidad de material alterada")
        prompt = blobs["planificador/entrada.txt"]
        legacy = materials["instrucciones.md"] + b"\nLee solicitud.txt y contexto.json. Devuelve solo el JSON del esquema.\n"
        if proposal["version"] != 1 or prompt != legacy:
            require(parse_json(prompt) == {"instrucciones": materials["instrucciones.md"].decode("utf-8"),
                    "materiales": {n: b.decode("utf-8") for n, b in materials.items() if n != "instrucciones.md"}},
                    "Entrada no corresponde a materiales")
        reservation = parse_json(blobs["reserva.json"])
        require(type(reservation) is dict and reservation.get("rol") == "planificador" and reservation.get("numero") == 1
                and reservation.get("limite_segundos") == 300, "Reserva de origen incoherente")
        depth, answers, carried = 0, [], []
        decisions, carried_assumptions, origins = [], [], {}
        if proposal["version"] >= 2:
            meta = proposal["continuacion"]
            keys = {"version", "profundidad", "padre", "respuestas_confirmadas",
                    "pendientes_anteriores", "preguntas_pendientes"}
            if proposal["version"] == 3:
                keys.update(("decisiones_confirmadas", "supuestos_anteriores", "supuestos_pendientes"))
            fields(meta, keys, "continuación")
            require(type(meta["version"]) is int and meta["version"] == proposal["version"] - 1 and
                    type(meta["profundidad"]) is int and 1 <= meta["profundidad"] <= MAX_DEPTH,
                    "Profundidad o versión inválidas")
            fields(meta["padre"], ("registro", "propuesta_sha256", "resultado_sha256"), "padre")
            utf8(meta["padre"]["registro"], 4096, "registro padre", nonblank=True)
            parent = load(meta["padre"]["registro"], remaining - 1)
            expected = continuation_data(parent, blobs.get("respuestas_usuario.json"),
                                         blobs.get("decisiones_usuario.json"), version=meta["version"])
            require({k: meta[k] for k in expected} == expected, "Continuación no corresponde al padre y respuestas")
            require(provenance.get("continuacion") == expected, "Procedencia de continuación incoherente")
            controller = provenance.get("controlador")
            fields(controller, ("commit", "fuentes_sha256"), "controlador")
            require(type(controller["commit"]) is str and re.fullmatch(r"[0-9a-f]{40}", controller["commit"])
                    and result.get("commit_controlador") == controller["commit"], "Commit del controlador incoherente")
            fields(controller["fuentes_sha256"], CONTROLLER_SOURCES, "fuentes del controlador")
            require(all(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha)
                        for sha in controller["fuentes_sha256"].values()), "Identidad del controlador inválida")
            require(all(materials[n] == parent.materials[n] for n in ("solicitud.txt", "contexto.json")),
                    "Solicitud o contexto original alterados")
            require(parse_json(materials["continuacion.json"]) == model_data(parent, expected),
                    "Materiales de continuación incoherentes")
            depth, answers, carried = expected["profundidad"], expected["respuestas_confirmadas"], expected["pendientes_anteriores"]
            decisions = expected.get("decisiones_confirmadas", [])
            carried_assumptions = expected.get("supuestos_anteriores", parent.pending_assumptions)
            origins = dict(parent.assumption_origins)
        pending = questions(plan, depth, carried)
        pending_assumptions = assumptions(plan, depth, carried_assumptions)
        if proposal["version"] >= 2:
            require(meta["preguntas_pendientes"] == pending, "Preguntas pendientes alteradas")
        if proposal["version"] == 3:
            require(meta["supuestos_pendientes"] == pending_assumptions, "Supuestos pendientes alterados")
        # No reclasificar estados históricos: v1/v2 no conservaban pendientes de supuestos.
        state = "necesita_aclaraciones" if pending else plan_state(plan)
        if proposal["version"] == 3 and pending_assumptions:
            state = "necesita_aclaraciones"
        require(result.get("estado") == proposal["estado"] == state, "Estado de origen incoherente")
        require(blobs["propuesta.md"] == render_proposal(proposal).encode("utf-8"), "Markdown de origen incoherente")
        loaded = Parent(path, result_raw, blobs["propuesta.json"], proposal, materials,
                        depth, pending, answers, identities, pending_assumptions, decisions, origins)
        for item in assumptions(plan, depth):
            origins[item["id"]] = reference(loaded)
        return loaded

    try:
        return load(path, MAX_DEPTH)
    except (KeyError, TypeError, RecursionError) as exc:
        raise ValueError("Estructura de origen inválida") from exc


def model_data(parent, data):
    # Selección explícita: ningún canal, ruta local, hash ni registro completo.
    material = {"version": data["version"], "propuesta_anterior_del_modelo": parent.proposal["propuesta"],
                "preguntas_identificadas": parent.pending,
                "respuestas_explicitas_del_usuario": data["respuestas_confirmadas"],
                "preguntas_sin_responder": data["pendientes_anteriores"]}
    if data["version"] == 2:
        material.update(supuestos_identificados=parent.pending_assumptions,
                        decisiones_explicitas_del_usuario=[
                            {key: item[key] for key in ("id", "supuesto", "decision", "explicacion", "alternativa")}
                            for item in data["decisiones_confirmadas"]],
                        supuestos_sin_decidir=data["supuestos_anteriores"])
    return material


def export_template(path, destination, *, decisions=False):
    parent = load_parent(path)
    require(parent.depth < MAX_DEPTH, "Máximo de ocho revisiones alcanzado")
    raw = encoded(decisions_template(parent) if decisions else template(parent))
    require(len(raw) <= MAX_ANSWERS, "Plantilla supera 1 MiB")
    require(parent.intact(), "Origen alterado antes de exportar")
    target = Path(destination).resolve()
    records = {Path(p).parent for p in parent.identities if Path(p).name == "resultado.json"}
    require(not any(target == record or record in target.parents for record in records),
            "La plantilla debe guardarse fuera de los registros originales")
    # x también rechaza enlaces y nunca trunca un destino existente.
    with Path(destination).open("xb") as stream:
        stream.write(raw)
    return parent

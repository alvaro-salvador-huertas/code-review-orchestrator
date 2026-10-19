"""Conjuntos editables v2: identidad, copias y contraste; sin ejecutar candidatos."""

import json

from case_evidence import digest, read_regular, require, unified_diff
from repair_case import write_json


ABSENT = {"tipo": "ausente", "sha256": None, "modo": None}


def identity(tree, config):
    """SHA-256 del documento v1 canónico sin su propio campo sha256."""
    files = []
    for name in sorted(config["editables"]):
        item = tree.get(name, ABSENT)
        files.append({"ruta": name, "sha256": None, **item})
    value = {"version": 1, "archivos": files}
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**value, "sha256": digest(raw)}


def contents(root, config):
    return {name: read_regular(root / name) for name in config["editables"]}


def overlay(root, data, config):
    """Solo sobre una copia nueva de la base; la ausencia no crea ningún archivo."""
    require(set(data) == set(config["editables"]), "Conjunto de partida distinto del autorizado")
    for name, content in data.items():
        if content is not None:
            path = root / name
            path.write_bytes(content)
            path.chmod(config["editables_iniciales"][name]["modo"] or 0o644)
        else:
            require(not (root / name).exists(), "Ausencia incompatible con la base")


def scope_valid(before, after, config, *, complete):
    changed = {n for n in before.keys() | after.keys() if before.get(n) != after.get(n)}
    if not changed <= set(config["editables"]):
        return False
    for name in config["editables"]:
        item = after.get(name)
        if item is None:
            # Solo se tolera ausencia todavía no creada tras un fallo técnico.
            if complete or name in before:
                return False
        elif (item["tipo"] != "archivo"
              or item["modo"] != (config["editables_iniciales"][name]["modo"] or 0o644)):
            return False
    return True


def difference(before, after, name):
    return unified_diff(before or b"", after or b"",
                        "/dev/null" if before is None else "a/" + name,
                        "/dev/null" if after is None else "b/" + name)


def save_files(target, data, state):
    target.mkdir()
    for name, content in data.items():
        if content is not None:
            path = target / name
            path.write_bytes(content)
            path.chmod(state[name]["modo"])


def archive(target, workspace, frozen, before, after, starting, config):
    """Conservar bytes regulares y estado real, incluso en una entrega parcial."""
    target.mkdir()
    original = contents(frozen / "proyecto", config)
    candidate = contents(workspace, config)
    save_files(target / "archivos", candidate, after)
    save_files(target / "partida", starting, before)
    save_files(target / "original", original, config["editables_iniciales"])
    for directory, source in (("diff_base", original), ("diff_anterior", starting)):
        (target / directory).mkdir()
        for name in config["editables"]:
            (target / directory / (name + ".diff")).write_bytes(difference(source[name], candidate[name], name))
    for name, tree in (("conjunto", after), ("partida", before), ("original", config["editables_iniciales"])):
        write_json(target / (name + ".json"), identity(tree, config))
    write_json(target / "workspace_despues.json", after)
    write_json(target / "cambios.json", {n: {"antes": before.get(n), "despues": after.get(n)}
        for n in before.keys() | after.keys() if before.get(n) != after.get(n)})
    return candidate


def validate_archive(delivery, reference, previous, record, config):
    """La lista autorizada viene de la selección previa, nunca del manifiesto leído."""
    base = reference.subtree("proyecto")
    workspace = dict(base)
    before = dict(base)
    original_set = identity(base, config)
    for name in config["editables"]:
        original = reference.read("proyecto/" + name) if name in base else None
        starting = previous.read("entrega/archivos/" + name) if previous else original
        candidate = delivery.read("entrega/archivos/" + name)
        mode = config["editables_iniciales"][name]["modo"] or 0o644
        workspace[name] = {"tipo": "archivo", "modo": mode, "sha256": digest(candidate)}
        if starting is not None:
            before[name] = {"tipo": "archivo", "modo": mode, "sha256": digest(starting)}
        for folder, content, state in (("archivos", candidate, workspace), ("partida", starting, before),
                                       ("original", original, base)):
            path = "entrega/" + folder + "/" + name
            if content is None:
                require(path not in delivery.state, "Ausencia fabricada como archivo")
            else:
                require(delivery.read(path) == content and delivery.state[path] == state[name],
                        f"Bytes o modo distintos: {path}")
        for folder, source in (("diff_base", original), ("diff_anterior", starting)):
            require(delivery.read("entrega/" + folder + "/" + name + ".diff") == difference(source, candidate, name),
                    "Diff del conjunto incoherente")
    # No aceptar archivos adicionales tampoco en las copias archivadas.
    for folder, tree in (("archivos", workspace), ("partida", before), ("original", base)):
        require(delivery.subtree("entrega/" + folder) == {n: tree[n] for n in config["editables"] if n in tree},
                "Copia archivada fuera del conjunto autorizado")
    current, start = identity(workspace, config), identity(before, config)
    require(delivery.json("entrega/conjunto.json") == record["conjunto"] == current
            and record["conjunto_sha256"] == current["sha256"]
            and delivery.json("entrega/partida.json") == record["partida_conjunto"] == start
            and record["partida_conjunto_sha256"] == start["sha256"]
            and delivery.json("entrega/original.json") == original_set, "Identidad de conjunto incoherente")
    if previous:
        require(start == previous.json("entrega/conjunto.json"), "Continuidad del conjunto rota")
    feedback = delivery.json("feedback.json")
    require(type(feedback["version"]) is int and feedback["version"] == 2
            and feedback["conjunto_sha256"] == start["sha256"], "Feedback de otro conjunto")
    require(scope_valid(before, workspace, config, complete=True), "Conjunto incompleto o inválido")
    require(delivery.json("entrega/workspace_despues.json") == workspace, "Alcance del conjunto inválido")
    require(delivery.json("entrega/cambios.json") == {
        n: {"antes": before.get(n), "despues": workspace.get(n)}
        for n in before.keys() | workspace.keys() if before.get(n) != workspace.get(n)}, "Cambios incoherentes")
    return workspace


def review_context(delivery, reference, config):
    """Cerrar por separado imports candidatos y originales; ninguna importación real."""
    from review_project import review_dependencies
    candidates = {name: delivery.read("entrega/archivos/" + name) for name in config["editables"]}
    base = reference.subtree("proyecto")
    originals = {name: reference.read("proyecto/" + name) for name in config["editables"] if name in base}
    materials = {**candidates, "contrato.md": reference.read("contrato.md"),
                 "configuracion_tarea.json": reference.read("tarea.json"),
                 "estado_inicial.json": delivery.read("entrega/original.json"),
                 "conjunto.json": delivery.read("entrega/conjunto.json"),
                 "partida.json": delivery.read("entrega/partida.json"),
                 "evaluacion/evaluador_revisado.py": reference.read("autoridades/" + config["suites"]["aceptacion"])}
    materials.update({"original/" + name: data for name, data in originals.items()})
    materials.update({"referencias/" + name: reference.read("materiales/" + name) for name in config["referencias"]})
    for folder in ("diff_base", "diff_anterior"):
        materials.update({folder + "/" + n + ".diff": delivery.read("entrega/" + folder + "/" + n + ".diff")
                          for n in config["editables"]})
    def candidate_read(name):
        return candidates[name] if name in candidates else reference.read("proyecto/" + name)
    try:
        materials.update(review_dependencies(candidates.values(), base.keys() | candidates.keys(), candidate_read,
                                              editables=candidates))
        original_dependencies = review_dependencies(originals.values(), base,
            lambda name: reference.read("proyecto/" + name), editables=originals)
        materials.update({"original/" + name: data for name, data in original_dependencies.items()})
    except SyntaxError as exc:
        raise ValueError(f"Sintaxis inválida en los materiales de revisión: {exc}") from exc
    return materials

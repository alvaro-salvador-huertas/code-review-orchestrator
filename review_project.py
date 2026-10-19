"""Revisión estática de inspect-json: vía histórica o intento explícito de orquestación."""

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from case_evidence import digest, parse_json, read_regular, require, unified_diff
from repair_case import ProcessInterrupted, timestamp, write_json
from repair_project import (ACCEPTANCE, CONTRACT, PROJECT, classify_report, cli_progress,
                            excluded, static_test_ids, tree_state)
from review_case import invoke_reviewer
from process_environment import process_environment


SPECIFIC = "tests/test_inspect_json_evaluator.py"
PROMPT = "prompts/reviewer_inspect_json.md"
ISOLATED_REVIEW = "revision_aislada_inspect_json_v1"
REVIEW_TIMEOUT_RANGE = (60, 600)
REEVALUATION = "reevaluacion_mismo_candidato_evaluador_revisado"
REVIEW_FILES = {
    "contrato.md": "contrato.md", "inspect_run.py": "inspect_run.py",
    "original/inspect_run.py": "original/inspect_run.py", "candidato.diff": "candidato.diff",
    "pruebas/test_inspect_run.py": "regresion/tests/test_inspect_run.py",
    "evaluacion/evaluador_revisado.py": "evaluacion/evaluador_revisado.py",
}
SUMMARY_STAGES = {
    "aceptacion_inicial": "desarrollo/inicial/aceptacion",
    "aceptacion_original_entrega": "desarrollo/posterior/aceptacion",
    "aceptacion_revisada": "reevaluacion/aceptacion",
    "comprobaciones_evaluador": "reevaluacion/comprobaciones",
    "regresion_inicial": "desarrollo/inicial/regresion",
    "regresion_entrega_reutilizada": "desarrollo/posterior/regresion",
}


class Evidence:
    """Lecturas de archivos regulares inventariados; no seguir rutas del contenido."""
    def __init__(self, directory):
        self.path = Path(directory).absolute()
        require(self.path.is_dir() and not self.path.is_symlink(), "Directorio de evidencia inválido")
        self.state = tree_state(self.path)
        require(all(v["tipo"] in ("archivo", "directorio") for v in self.state.values()),
                "La evidencia contiene enlaces o archivos especiales")

    def read(self, name):
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts, "Ruta de evidencia inválida")
        require(self.state.get(name, {}).get("tipo") == "archivo", f"Falta evidencia: {name}")
        data = read_regular(self.path / name)
        require(data is not None and digest(data) == self.state[name]["sha256"],
                f"Evidencia alterada: {name}")
        return data

    def json(self, name):
        return parse_json(self.read(name))

    def subtree(self, name):
        prefix = name + "/"
        return {key[len(prefix):]: value for key, value in self.state.items() if key.startswith(prefix)}

    def unchanged(self):
        return tree_state(self.path) == self.state


def integrity_flags(values, keys):
    require(isinstance(values, dict) and set(keys) <= values.keys()
            and all(v is True for v in values.values()), "Integridad previa incompleta o fallida")


def completed(process):
    require(process["estado"] == "finalizada" and type(process["codigo_salida"]) is int
            and process.get("error") is None, "Proceso no finalizado o inválido")
    duration = process["duracion_segundos"]
    require(type(duration) in (int, float) and math.isfinite(duration) and duration >= 0,
            "Duración de proceso inválida")


def evaluation(record, name, saved, expected, runner, acceptance=None, project=None):
    item = record.json(name + "/evaluacion.json")
    process = record.json(name + "/resultado.json")
    require(item == saved and item["proceso"] == process and item["workspace_intacto"] is True,
            f"Resúmenes de evaluación incoherentes: {name}")
    completed(process)
    cwd, command = process["directorio_trabajo"], process["comando"]
    require(isinstance(cwd, str) and Path(cwd).is_absolute() and isinstance(command, list)
            and command and isinstance(command[0], str) and Path(command[0]).is_absolute(),
            "Comando o cwd de evaluación inválido")
    wanted = [command[0], "-B", str(runner), "--project", cwd,
              "--report", str(record.path / name / "pruebas.json")]
    if acceptance is not None:
        wanted += ["--acceptance", str(acceptance)]
    require(command == wanted and (project is None or cwd == str(project)),
            f"Comando de evaluación mezclado: {name}")
    record.read(name + "/stdout.txt")
    report = record.read(name + "/pruebas.json")
    structured = parse_json(report)
    require(type(structured["version"]) is int and type(structured["sesiones"]) is int,
            "Versión o sesiones del informe inválidas")
    counts = classify_report(report, expected, process, record.read(name + "/stderr.txt").decode())
    require(all(item.get(k) == v for k, v in counts.items()), "Recuentos de evaluación incoherentes")
    require(all(type(item[k]) is int for k in counts if k != "clasificacion"), "Recuentos inválidos")
    return counts


def validate_evidence(development_run, reevaluation_run, project_root=PROJECT):
    """Validar la procedencia real sin ejecutar agentes, candidatos ni pruebas."""
    root = Path(project_root).resolve()
    dev, ree = Evidence(development_run), Evidence(reevaluation_run)
    require(dev.path != ree.path and dev.path not in ree.path.parents
            and ree.path not in dev.path.parents, "Registros de origen solapados")
    try:
        d, r, p = dev.json("resultado.json"), ree.json("resultado.json"), ree.json("procedencia.json")
        base = dev.json("referencia/procedencia.json")
        require(d["registro"] == str(dev.path) and r["registro"] == str(ree.path), "Ubicación de registro incoherente")
        require(d["tarea"] == base["tarea"] == "inspect-json" and base["tipo"] == "proyecto_existente"
                and d["procedencia"] == base, "Procedencia de desarrollo inválida")
        require(d["estado"] == "no_supera_comprobaciones" and type(d["codigo_salida"]) is int
                and d["codigo_salida"] == 1 and d["error"] is None, "Se requiere el rechazo original conservado")
        require(r["tipo"] == p["tipo"] == REEVALUATION
                and r["estado"] == "supera_aceptacion_revisada_y_comprobaciones"
                and type(r["codigo_salida"]) is int and r["codigo_salida"] == 0,
                "Reevaluación no superada")
        require(r["registro_origen"] == p["registro_origen"]
                and (root / p["registro_origen"]).absolute() == dev.path,
                "La reevaluación pertenece a otro desarrollo")
        require(p["resultado_origen"] == {"estado": d["estado"], "codigo_salida": d["codigo_salida"]}
                and p["sha256"]["resultado_origen"] == digest(dev.read("resultado.json")),
                "El resultado original ha cambiado")
        integrity_flags(d["integridad"], ("original_intacto", "referencia_intacta", "registros_intactos", "alcance_respetado"))
        integrity_flags(r["integridad"], ("mismo_workspace_entregado", "copia_evaluada_intacta",
                                        "registros_previos_intactos", "referencia_intacta", "original_intacto", "mismo_candidato"))
        require(dev.subtree("referencia") == d["referencia_sha256"]
                and ree.subtree("referencia") == ree.json("referencia_sha256.json"), "Referencia alterada")
        for record, manifests, required in ((dev, d["evidencia_sha256"], {"inicial", "agente", "entrega"}),
                                            (ree, ree.json("evidencia_sha256.json"),
                                             {"aceptacion", "comprobaciones", "entrega", "regresion_historica"})):
            require(required <= manifests.keys(), "Faltan inventarios de etapas")
            for name in required:
                require(record.subtree(name) == manifests[name], f"Etapa alterada: {name}")
        process = dev.json("agente/resultado.json")
        require(d["agente"]["proceso"] == process and type(d["agente"]["invocaciones"]) is int
                and d["agente"]["invocaciones"] == 1 and d["reserva_invocacion"] is True,
                "Proceso de desarrollo incoherente")
        completed(process)
        require(process["codigo_salida"] == 0, "Desarrollador no finalizado correctamente")
        require(r["invocaciones_nuevas"] == {"desarrollador": 0, "revisor": 0}
                and all(type(v) is int for v in r["invocaciones_nuevas"].values()), "Reevaluación con agentes")

        contract = dev.read("referencia/contrato.md")
        match = re.search(rb"Base: `([0-9a-f]{40})`", contract)
        require(match is not None and match[1].decode() == base["commit_base"] == p["commit_base"]
                and p["head_origen"] == base["head_origen"], "Base o HEAD de origen mezclados")
        require(contract == read_regular(root / CONTRACT) == ree.read("referencia/contrato.md"), "Contrato distinto")
        require(ree.json("referencia/procedencia_original.json") == base, "Procedencia original distinta")
        with process_environment() as environment:
            git_tree = subprocess.run(["git", "-C", str(root), "ls-tree", "-rz", base["commit_base"]],
                                      check=True, capture_output=True, timeout=10, env=environment).stdout
        files = {}
        for entry in git_tree.split(b"\0"):
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            name = name.decode()
            if excluded(name):
                continue
            require(kind == "blob" and mode in ("100644", "100755"), "Base con enlaces o submódulos")
            data = dev.read("referencia/proyecto/" + name)
            # El identificador de blob se recalcula sin importar el código conservado.
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            require(blob == oid, f"Contenido distinto de Git: {name}")
            files[name] = {"objeto_git": oid, "sha256": digest(data), "modo_git": mode}
            require(dev.state["referencia/proyecto/" + name]["modo"] == int(mode[-3:], 8), "Permisos de base distintos")
        require(files == base["archivos_base"] and set(files) == {
            name for name, entry in dev.subtree("referencia/proyecto").items() if entry["tipo"] == "archivo"},
            "Inventario de base incompleto")
        require(dev.subtree("referencia/proyecto") == ree.subtree("referencia/proyecto_base"), "Bases diferentes")
        candidate, original = dev.read("entrega/inspect_run.py"), dev.read("referencia/proyecto/inspect_run.py")
        require(candidate and candidate == dev.read("entrega/archivos_modificados/inspect_run.py")
                == ree.read("entrega/inspect_run.py") and digest(candidate) == d["candidato_sha256"], "Candidato mezclado")
        diff = unified_diff(original, candidate, "a/inspect_run.py", "b/inspect_run.py")
        require(dev.read("entrega/candidato.diff") == diff, "Diff de candidato incoherente")
        workspace = dev.subtree("referencia/proyecto")
        before = workspace["inspect_run.py"]
        after = {**before, "sha256": digest(candidate)}
        workspace["inspect_run.py"] = after
        require(dev.json("entrega/cambios.json") == {"inspect_run.py": {"antes": before, "despues": after}}
                and workspace == dev.json("entrega/workspace_despues.json") == ree.json("proyecto_evaluado_sha256.json"),
                "La copia evaluada no corresponde a la única entrega permitida")

        old, new = dev.read("referencia/evaluar.py"), ree.read("referencia/evaluar.py")
        runner = dev.read("referencia/project_test_runner.py")
        specific = ree.read("referencia/comprobaciones/" + SPECIFIC)
        require(old == ree.read("referencia/evaluador_anterior.py") and old != new
                and new == read_regular(root / ACCEPTANCE) == ree.read("referencia/comprobaciones/" + ACCEPTANCE),
                "El cambio de evaluador no coincide con la autoridad actual")
        require(specific == read_regular(root / SPECIFIC)
                and runner == read_regular(root / "project_test_runner.py") == ree.read("referencia/project_test_runner.py"),
                "Adaptador o comprobaciones específicas distintos")
        evaluator_diff = unified_diff(old, new, "a/evaluar.py", "b/evaluar.py")
        require(evaluator_diff == ree.read("referencia/evaluador.diff"), "Diff del evaluador incoherente")
        require(base["materiales_del_arbol_actual"] == {CONTRACT: digest(contract), ACCEPTANCE: digest(old)},
                "Hashes de autoridades originales incoherentes")
        hashes = {"candidato": digest(candidate), "contrato": digest(contract), "evaluador_anterior": digest(old),
                  "evaluador_revisado": digest(new), "diff_evaluador": digest(evaluator_diff),
                  "adaptador_pruebas": digest(runner), "comprobaciones": digest(specific),
                  "resultado_origen": digest(dev.read("resultado.json"))}
        require(p["sha256"] == hashes, "Hashes de reevaluación incoherentes")
        expected = {"aceptacion": static_test_ids(old, "__main__"), "regresion": sorted(
            identity for name in files if PurePosixPath(name).parent == PurePosixPath("tests")
            and PurePosixPath(name).match("test*.py")
            for identity in static_test_ids(dev.read("referencia/proyecto/" + name), PurePosixPath(name).stem))}
        require(expected == base["pruebas_esperadas"], "Pruebas congeladas incompletas")
        new_expected = {"aceptacion": static_test_ids(new, "__main__"),
                        "comprobaciones": static_test_ids(specific, "test_inspect_json_evaluator")}
        require(new_expected == p["pruebas_esperadas"] and new_expected["aceptacion"] == expected["aceptacion"],
                "Métodos de aceptación cambiados o incompletos")
        for phase in ("inicial", "posterior"):
            for kind in ("aceptacion", "regresion"):
                counts = evaluation(dev, f"{phase}/{kind}", d[phase][kind], expected[kind],
                                    dev.path / "referencia/project_test_runner.py",
                                    dev.path / "referencia/evaluar.py" if kind == "aceptacion" else None)
                require(counts["clasificacion"] == ("superadas" if kind == "regresion" else "fallos_asercion"),
                        "Resultados originales incompatibles con esta reevaluación")
            require(d[phase]["aceptacion"]["proceso"]["directorio_trabajo"]
                    == d[phase]["regresion"]["proceso"]["directorio_trabajo"], "Evaluaciones de copias distintas")
        for kind in ("aceptacion", "comprobaciones"):
            counts = evaluation(ree, kind, r["evaluaciones_nuevas"][kind], new_expected[kind],
                                ree.path / "referencia/project_test_runner.py",
                                ree.path / "referencia/evaluar.py" if kind == "aceptacion" else None,
                                ree.path / "referencia/comprobaciones" if kind == "comprobaciones" else None)
            require(counts["clasificacion"] == "superadas", "La reevaluación no acredita todas las pruebas")
        reused = p["regresion_reutilizada"]
        require(reused == r["regresion_reutilizada"] and reused["ejecutada_ahora"] is False
                and (root / reused["registro"]).absolute() == dev.path / "posterior/regresion"
                and reused["evaluacion_historica"] == d["posterior"]["regresion"], "Regresión reutilizada incoherente")
        require(ree.subtree("regresion_historica") == dev.subtree("posterior/regresion"), "Regresión histórica alterada")

        authorization = {"desarrollo": str(dev.path), "reevaluacion": str(ree.path),
                         "resultado_original": p["resultado_origen"], "commit_base": base["commit_base"],
                         "head_origen": base["head_origen"], "sha256": hashes,
                         "evaluaciones_nuevas": r["evaluaciones_nuevas"], "regresion_reutilizada": reused,
                         "motivo": "Aceptación revisada completa sobre la misma entrega; rechazo original conservado."}
        materials = {"contrato.md": contract, "inspect_run.py": candidate, "original/inspect_run.py": original,
                     "candidato.diff": diff, "evaluacion/evaluador_anterior.py": old,
                     "evaluacion/evaluador_revisado.py": new, "evaluacion/evaluador.diff": evaluator_diff,
                     "evaluacion/project_test_runner.py": runner, "evaluacion/comprobaciones.py": specific,
                     "autorizacion.json": (json.dumps(authorization, ensure_ascii=False, indent=2) + "\n").encode()}
        # La selección del modelo se hace después. Aquí se conserva la evidencia completa.
        # Revisar también imports de las pruebas seleccionadas antes de excluir otras pruebas.
        materials.update(review_dependencies(
            [candidate, original, new, dev.read("referencia/proyecto/tests/test_inspect_run.py")],
            files, lambda name: dev.read("referencia/proyecto/" + name)))
        for name in files:
            if name.startswith("tests/"):
                materials["regresion/" + name] = dev.read("referencia/proyecto/" + name)
        report_sources = [(dev, f"{phase}/{kind}", f"desarrollo/{phase}/{kind}")
                          for phase in ("inicial", "posterior") for kind in ("aceptacion", "regresion")]
        report_sources += [(ree, kind, "reevaluacion/" + kind) for kind in ("aceptacion", "comprobaciones")]
        for record, source, target in report_sources:
            for name in ("evaluacion.json", "resultado.json", "pruebas.json", "stdout.txt", "stderr.txt"):
                materials["evidencia/" + target + "/" + name] = record.read(source + "/" + name)
        for record, label, names in ((dev, "desarrollo", ("resultado.json", "referencia/procedencia.json")),
                                     (ree, "reevaluacion", ("resultado.json", "procedencia.json"))):
            for name in names:
                materials["registros/" + label + "/" + name] = record.read(name)
        require(dev.unchanged() and ree.unchanged(), "Los registros cambiaron durante su validación")
        return materials, authorization, (dev, ree)
    except (KeyError, TypeError, AttributeError, SyntaxError) as exc:
        raise ValueError(f"Evidencia incompleta o inválida: {exc}") from exc


def review_dependencies(sources, files, read_file):
    """Cerrar imports estáticos del código y pruebas pertinentes, sin importarlos."""
    pending, seen, dependencies = list(sources), {"inspect_run.py"}, {}
    while pending:
        for node in ast.walk(ast.parse(pending.pop())):
            require(not isinstance(node, ast.ImportFrom) or node.level == 0,
                    "Dependencia con import relativo no admitida en la selección")
            require(not (isinstance(node, ast.Call) and
                         (isinstance(node.func, ast.Name) and node.func.id == "__import__"
                          or isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")),
                    "Import dinámico: no se puede cerrar la selección de dependencias")
            modules = ([a.name for a in node.names] if isinstance(node, ast.Import)
                       else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for module in modules:
                name = module.split(".")[0] + ".py"
                local = [path for path in (name, "tests/" + name) if path in files]
                require(len(local) <= 1, "Dependencia local ambigua")
                if not local:
                    require(module.split(".")[0] in sys.stdlib_module_names,
                            f"Dependencia no resuelta: {module}")
                    continue
                require("." not in module, "Paquete local no admitido en la selección")
                name = local[0]
                if name not in seen:
                    seen.add(name)
                    data = read_file(name)
                    dependencies["dependencias/" + name] = data
                    pending.append(data)
    return dependencies


def review_materials(evidence, authorization):
    """Seleccionar contexto y resumir solo la salida de validate_evidence, sin ejecutar código.

    La correspondencia queda fuera del workspace: sus rutas son relativas al archivo
    completo de evidencia, nunca enlaces desde el modelo hacia los registros originales.
    """
    selection = dict(REVIEW_FILES)
    selection.update((name, name) for name in sorted(evidence) if name.startswith("dependencias/"))
    context = {target: evidence[source] for target, source in selection.items()}
    stages, stage_sources = {}, {}
    for key, stage in SUMMARY_STAGES.items():
        source = "evidencia/" + stage
        item = parse_json(evidence[source + "/evaluacion.json"])
        process = item["proceso"]
        stages[key] = {field: item[field] for field in
                       ("clasificacion", "metodos", "metodos_con_fallos", "aserciones_fallidas", "fallos_subtest", "errores")}
        stages[key].update(metodos_correctos=item["metodos"] - item["metodos_con_fallos"],
                           estado_proceso=process["estado"], codigo_salida=process["codigo_salida"],
                           informe_sha256=digest(evidence[source + "/pruebas.json"]))
        stage_sources[key] = [source + "/" + name for name in
                             ("evaluacion.json", "resultado.json", "pruebas.json", "stdout.txt", "stderr.txt")]
    provenance_sources = ["autorizacion.json", *sorted(name for name in evidence if name.startswith("registros/"))]
    reevaluation = parse_json(evidence["registros/reevaluacion/resultado.json"])
    summary = {
        "version": 1, "tipo": "resumen_evidencia_validada_no_dictamen",
        "procedencia": {"desarrollo": Path(authorization["desarrollo"]).name,
                        "reevaluacion": Path(authorization["reevaluacion"]).name,
                        "commit_base": authorization["commit_base"], "head_origen": authorization["head_origen"],
                        "resultado_desarrollo": authorization["resultado_original"],
                        "resultado_reevaluacion": {key: reevaluation[key] for key in ("estado", "codigo_salida")}},
        "sha256": authorization["sha256"], "evaluaciones": stages,
        "regresion_reutilizada": {"ejecutada_en_reevaluacion": False, "materiales_coincidentes_verificados": True,
                                  "evaluacion": "regresion_entrega_reutilizada"},
        "alcance": "La aceptación revisada no modifica el rechazo original. Las pruebas no demuestran "
                   "corrección general ni sustituyen el dictamen independiente.",
    }
    context["resumen_evidencia.json"] = (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    context["respuesta.schema.json"] = (json.dumps(response_schema(len(context["inspect_run.py"].splitlines())),
                                                  ensure_ascii=False, indent=2) + "\n").encode()
    sources = set(provenance_sources).union(*(set(paths) for paths in stage_sources.values()))
    mapping = {
        "version": 1,
        "materiales": {name: {"fuente": selection.get(name), "sha256": digest(data), "bytes": len(data)}
                       for name, data in sorted(context.items())},
        "resumen": {"generador": "review_project.review_materials/v1", "procedencia": provenance_sources,
                    "evaluaciones": stage_sources,
                    "fuentes_sha256": {name: digest(evidence[name]) for name in sorted(sources)}},
        "esquema": {"generador": "review_project.response_schema", "lineas_candidato": len(context["inspect_run.py"].splitlines())},
    }
    return context, mapping


def response_schema(line_count, *, editable="inspect_run.py"):
    fields = {"archivo": {"type": "string", "enum": [editable]},
              "linea": {"type": "integer", "minimum": 1, "maximum": line_count},
              **{key: {"type": "string", "minLength": 1} for key in ("requisito", "explicacion", "ejemplo")}}
    return {"type": "object", "additionalProperties": False, "required": ["decision", "resumen", "hallazgos"],
            "properties": {"decision": {"type": "string", "enum": ["aprobar", "solicitar_cambios"]},
                           "resumen": {"type": "string", "minLength": 1},
                           "hallazgos": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                                        "required": list(fields), "properties": fields}}}}


def validate_verdict(raw, line_count, *, editable="inspect_run.py"):
    verdict = parse_json(raw)
    require(isinstance(verdict, dict) and set(verdict) == {"decision", "resumen", "hallazgos"}, "Objeto de dictamen inválido")
    require(verdict["decision"] in ("aprobar", "solicitar_cambios")
            and isinstance(verdict["resumen"], str) and verdict["resumen"].strip(), "Decisión o resumen inválidos")
    findings = verdict["hallazgos"]
    require(isinstance(findings, list) and (bool(findings) == (verdict["decision"] == "solicitar_cambios")),
            "Decisión incompatible con los hallazgos")
    for finding in findings:
        require(isinstance(finding, dict) and set(finding) == {"archivo", "linea", "requisito", "explicacion", "ejemplo"},
                "Estructura de hallazgo inválida")
        require(finding["archivo"] == editable and type(finding["linea"]) is int
                and 1 <= finding["linea"] <= line_count, "Archivo o línea fuera del candidato")
        require(all(isinstance(finding[k], str) and finding[k].strip() for k in ("requisito", "explicacion", "ejemplo")),
                "Falta requisito, explicación o ejemplo")
    return verdict


def run_review(development_run, reevaluation_run, project_root=PROJECT, *, progress=None):
    return _run_review(lambda: validate_evidence(development_run, reevaluation_run, project_root),
                       review_materials, Path(project_root) / PROMPT, project_root, progress=progress)


def run_delivery_review(delivery_run, project_root=PROJECT, *, progress=None, on_invoke=None, task="inspect-json"):
    """Revisar una entrega nueva completa; no acepta la procedencia histórica."""
    from project_flow import task_config, delivery_review_evidence, delivery_review_materials
    config = task_config(task)
    frozen = Path(delivery_run).absolute().parent.parent.parent / "referencia"
    def reserve():
        require(on_invoke is not None, "La entrega nueva requiere una reserva del orquestador; no hay reanudación")
        on_invoke()
    def load():
        evidence, authorization, sources = delivery_review_evidence(delivery_run, project_root)
        require(authorization["tipo"] == config["tipo"], "Tarea de revisión distinta de la entrega")
        return evidence, authorization, sources
    return _run_review(load,
                       delivery_review_materials, frozen / config["revision"], project_root,
                       progress=progress, on_invoke=reserve, task=task, editable=config["editable"],
                       review_timeout=config["limites"]["revisor"] if task == "export-csv" else None,
                       preparation="Validando entrega nueva y sus evaluaciones completas.")


def orchestration_review_evidence(orchestration_run, attempt, project_root=PROJECT):
    """Autorizar por lectura una entrega explícita de un flujo cerrado, sin reevaluar."""
    from project_flow import TYPE, LIMITS, delivery_review_evidence
    require(type(attempt) is int and attempt in (1, 2), "Intento explícito inválido")
    origin = Evidence(orchestration_run)
    try:
        summary = origin.json("resultado.json")
        require(summary.get("tarea") != "export-csv", "La revisión aislada de export-csv no está admitida")
        require(summary["tipo"] == TYPE and summary["tarea"] == "inspect-json"
                and summary["registro"] == str(origin.path), "Registro de orquestación incoherente")
        closed_states = {"lista_para_revision_humana": 0, "intentos_agotados": 1,
                         "fallo_tecnico": 3, "fallo_revisor": 3, "tiempo_agotado": 4,
                         "tiempo_agotado_revisor": 4, "respuesta_invalida": 5,
                         "modificacion_no_permitida": 6, "evidencia_invalida": 7,
                         "preparacion_no_autoriza": 7, "fallo_controlador": 8, "interrumpida": 9}
        require(isinstance(summary["fin_utc"], str) and summary["fin_utc"] >= summary["inicio_utc"]
                and type(summary["codigo_salida"]) is int
                and closed_states.get(summary["estado"]) == summary["codigo_salida"]
                and summary["lista_para_revision_humana"] is (summary["codigo_salida"] == 0),
                "Orquestación no cerrada o resultado incoherente")
        integrity_flags(summary["integridad"], ("original_intacto", "referencia_intacta",
                                               "registros_intactos", "alcance_respetado"))
        config = origin.json("referencia/configuracion.json")
        require(summary["procedencia"] == origin.json("referencia/procedencia.json")
                and summary["referencia_sha256"] == origin.subtree("referencia")
                and summary["limites_segundos"] == LIMITS
                and type(summary["max_intentos"]) is int
                and summary["max_intentos"] == config["max_intentos"]
                and type(summary["max_invocaciones"]) is int
                and summary["max_invocaciones"] == 2 * summary["max_intentos"]
                and summary["incorporacion"] == "no_realizada", "Configuración de origen incoherente")
        entries = summary["intentos"]
        require(isinstance(entries, list) and 1 <= len(entries) <= summary["max_intentos"]
                and all(type(e["numero"]) is int and e["numero"] == n
                        for n, e in enumerate(entries, 1)), "Intentos incompletos o duplicados")
        require(attempt <= len(entries), "El intento seleccionado no existe")
        entry = entries[attempt - 1]
        delivery = origin.path / "intentos" / str(attempt) / "evidencia"
        require(entry["registro"] == str(delivery), "Entrega enlazada de otro origen")
        evidence, authorization, sources = delivery_review_evidence(delivery, project_root)
        record = parse_json(evidence["evidencia/resultado.json"])
        require(all(entry[key] == record[key] for key in
                    ("numero", "registro", "partida_sha256", "candidato_sha256", "desarrollo", "evaluaciones")),
                "Resumen del intento mezclado con otra entrega")
        require(summary["inicial"] == {kind: origin.json(f"inicial/{kind}/evaluacion.json")
                                      for kind in ("aceptacion", "regresion")}, "Preparación mezclada")
        seals = summary["etapas_cerradas"]
        required = {str(delivery), str(origin.path / "inicial"),
                    *(str(delivery / name) for name in ("desarrollo", "entrega")),
                    *(str(delivery / "evaluaciones" / kind) for kind in record["evaluaciones"])}
        totals = {"desarrollador": 0, "revisor": 0}
        reservations, reservation_names, linked = [], set(), {}
        for item in entries:
            number = item["numero"]
            require(item["registro"] == str(origin.path / "intentos" / str(number) / "evidencia"),
                    "Intento enlazado de otro origen")
            previous_record = origin.json(f"intentos/{number}/evidencia/resultado.json")
            require(all(item[key] == previous_record[key] for key in
                        ("numero", "registro", "partida_sha256", "candidato_sha256", "desarrollo", "evaluaciones")
                        if key in item), "Resumen de otro intento mezclado")
            required.add(item["registro"])
            require(set(item["invocaciones"]) == set(totals), "Roles de origen inválidos")
            require(item["invocaciones"]["desarrollador"] == previous_record["desarrollo"]["agente"]["invocaciones"],
                    "Consumo de desarrollo incoherente")
            for role in totals:
                count = item["invocaciones"][role]
                require(type(count) is int and count in (0, 1), "Reserva de origen excedida")
                totals[role] += count
                if count:
                    name = f"reservas/{number}-{role}"
                    reservation = origin.json(name + "/reserva.json")
                    require(reservation["rol"] == role and type(reservation["intento"]) is int
                            and reservation["intento"] == number
                            and reservation["estado"] == "reservada_antes_de_invocar"
                            and reservation["limite_segundos"] == LIMITS[role], "Reserva de origen incoherente")
                    reservations.append(reservation)
                    reservation_names.add(f"{number}-{role}")
                    required.add(str(origin.path / name))
            if item["revision"] is not None:
                path = Path(item["revision"]["registro"])
                require(path.parent == origin.path.parent and path != origin.path
                        and re.fullmatch(r"\d{8}T\d{6}Z_inspect-json_review_[0-9a-f]{32}", path.name),
                        "Referencia de revisión inválida")
                reviewed = Evidence(path)
                require(reviewed.json("resultado.json") == item["revision"], "Revisión enlazada mezclada")
                require(item["invocaciones"]["revisor"] == item["revision"]["revisor"]["invocaciones"],
                        "Consumo de revisión incoherente")
                linked[str(path)] = reviewed
                required.add(str(path))
            else:
                require(item["invocaciones"]["revisor"] == 0, "Revisión reservada sin resultado cerrado")
        require({name.split("/")[0] for name in origin.subtree("reservas")} == reservation_names,
                "Reservas omitidas o ajenas al resumen")
        require(summary["reservas"] == reservations and summary["invocaciones"] == {
            **totals, "total": sum(totals.values())}
            and all(type(v) is int for v in summary["invocaciones"].values()), "Consumos de origen incoherentes")
        require(required <= seals.keys(), "Faltan manifiestos de etapas pertinentes")
        for name, state in seals.items():
            path = Path(name)
            if name in linked:
                actual = linked[name].state
            else:
                require(path.is_absolute() and ".." not in path.parts and origin.path in path.parents,
                        "Manifiesto ajeno al origen")
                relative = path.relative_to(origin.path).as_posix()
                require(origin.state.get(relative, {}).get("tipo") == "directorio", "Etapa ausente")
                actual = origin.subtree(relative)
            require(actual == state, f"Etapa cerrada alterada: {name}")
        sources = (origin, *sources, *linked.values())
        require(all(source.unchanged() for source in sources), "Origen alterado durante la validación")
        authorization.update(operacion=ISOLATED_REVIEW, orquestacion=str(origin.path), intento=attempt,
                             resultado_origen_sha256=digest(origin.read("resultado.json")),
                             resultado_origen={key: summary[key] for key in
                                               ("estado", "codigo_salida", "invocaciones")})
        # Se archiva la procedencia, pero nunca entra en los materiales del modelo.
        evidence["evidencia/orquestacion_resultado.json"] = origin.read("resultado.json")
        return evidence, authorization, sources
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError(f"Orquestación incompleta o inválida: {exc}") from exc


def persist_review_json(path, data, *, exclusive=False):
    """Persistir antes de lanzar; la reserva exclusiva jamás se reutiliza ni se borra."""
    target = path if exclusive else path.with_suffix(".tmp")
    with target.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        target.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_isolated_review(orchestration_run, attempt, operation_id, project_root=PROJECT, *,
                        review_timeout=180, progress=None):
    """Operación independiente identificada explícitamente; nunca reanuda el origen."""
    from project_flow import REVIEW_PROMPT, delivery_review_materials
    require(isinstance(operation_id, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", operation_id),
            "Identificador de operación inválido (1–80 letras ASCII, números, guion o subrayado)")
    require(type(review_timeout) is int and REVIEW_TIMEOUT_RANGE[0] <= review_timeout <= REVIEW_TIMEOUT_RANGE[1],
            "El límite de revisión debe ser un entero entre 60 y 600 segundos")
    operation = {"tipo": ISOLATED_REVIEW, "id": operation_id,
                 "orquestacion": str(Path(orchestration_run).absolute()), "intento": attempt,
                 "limite_solicitado_segundos": review_timeout, "limite_efectivo_segundos": review_timeout,
                 "max_invocaciones": 1, "reanudacion": False}
    return _run_review(lambda: orchestration_review_evidence(orchestration_run, attempt, project_root),
                       delivery_review_materials, Path(orchestration_run) / "referencia" / REVIEW_PROMPT,
                       project_root, progress=progress, operation=operation,
                       preparation="Validando intento explícito y evidencia de la orquestación cerrada.")


def _run_review(load_evidence, select_materials, prompt_path, project_root, *, progress=None, on_invoke=None,
                preparation="Validando desarrollo, reevaluación y regresión histórica.", operation=None,
                task="inspect-json", editable="inspect_run.py", review_timeout=None):
    root = Path(project_root).resolve()
    started = time.monotonic()
    result = {"tarea": task, "registro": None, "inicio_utc": timestamp(),
              "decision_controlador": "en_preparacion", "codigo_salida": 8,
              "evidencia_previa_valida": False, "reserva_invocacion": False, "max_invocaciones": 1,
              "revisor": {"invocaciones": 0, "estado": "no_ejecutado", "codigo_salida": None},
              "dictamen_modelo": None, "contraste_semantico": "pendiente", "incorporacion": "no_realizada",
              "limites_segundos": {"revisor": 180, "consulta_cli": 10},
              "integridad": {}, "error": None}
    log = archive = None
    timeout = operation["limite_efectivo_segundos"] if operation else (180 if review_timeout is None else review_timeout)
    result["limites_segundos"]["revisor"] = timeout
    if operation:
        result["operacion"] = operation
    operation_bytes = reservation_bytes = None
    def save():
        if log is not None:
            (persist_review_json if operation else write_json)(log / "resultado.json", result)
    def notify(message):
        if progress is not None:
            progress(message)
    def stop(code, state, message=None):
        result.update(codigo_salida=code, decision_controlador=state, error=message)
    try:
        notify(preparation)
        evidence, authorization, sources = load_evidence()
        materials, selection = select_materials(evidence, authorization)
        require(all(source.path != root / "runs" and source.path not in (root / "runs").parents for source in sources),
                "El registro nuevo quedaría dentro de una entrada")
        result["evidencia_previa_valida"] = True
        original_state = tree_state(root, filter_local=True)
        prompt = read_regular(prompt_path)
        require(prompt is not None and prompt.strip(), "Faltan las instrucciones específicas")
        line_count = len(materials[editable].splitlines())
        parent = Path(tempfile.gettempdir()).resolve()
        require(parent != root and root not in parent.parents, "El workspace debe estar fuera del proyecto")
        (root / "runs").mkdir(exist_ok=True)
        name = ("inspect-json_isolated-review_" + operation["id"] if operation else
                time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"_{task}_review_" + uuid4().hex)
        destination = root / "runs" / name
        require(all(destination.resolve() != s.path.resolve() and s.path.resolve() not in destination.resolve().parents
                    for s in sources), "La operación quedaría dentro de una entrada")
        try:
            destination.mkdir()
        except FileExistsError:
            if not operation:
                raise
            stop(10, "operacion_ya_existente", "El identificador ya tiene registro; no se permite repetir ni reanudar")
            return result
        log = destination
        result["registro"] = str(log)
        if operation:
            operation.update(candidato_sha256=authorization["candidato_sha256"],
                             resultado_origen_sha256=authorization["resultado_origen_sha256"])
            persist_review_json(log / "operacion.json", operation, exclusive=True)
            operation_bytes = read_regular(log / "operacion.json")
        write_json(log / "origen.json", {"autorizacion": authorization,
                                         "registros": {str(s.path): s.state for s in sources}})
        origin_bytes = (log / "origen.json").read_bytes()
        agent_log = log / "revisor"
        agent_log.mkdir()
        (agent_log / "entrada.txt").write_bytes(prompt)
        archive = log / "materiales"
        archive.mkdir()
        full_archive = log / "evidencia_validada"
        full_archive.mkdir()
        for name, data in evidence.items():
            target = full_archive / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        evidence_state = tree_state(full_archive)
        write_json(log / "seleccion.json", selection)
        selection_bytes = (log / "seleccion.json").read_bytes()
        for name, data in materials.items():
            target = archive / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        archived = tree_state(archive)
        result["materiales_sha256"] = archived
        result["evidencia_sha256"] = evidence_state
        result["contexto"] = {"version": 2, "archivos": len(materials), "bytes": sum(map(len, materials.values())),
                              "seleccion_sha256": digest(selection_bytes)}
        save()
        notify("Materiales verificados; preparando workspace externo de solo lectura.")
        with tempfile.TemporaryDirectory(prefix="review-project-", dir=parent) as temporary:
            workspace = Path(temporary) / "workspace"
            shutil.copytree(archive, workspace)
            final = Path(temporary) / "respuesta.json"
            def check():
                result["integridad"] = {"workspace_intacto": tree_state(workspace) == archived,
                                         "materiales_intactos": tree_state(archive) == archived,
                                         "evidencia_completa_intacta": tree_state(full_archive) == evidence_state,
                                         "seleccion_intacta": read_regular(log / "seleccion.json") == selection_bytes,
                                         "original_intacto": tree_state(root, filter_local=True) == original_state,
                                         "origenes_intactos": all(s.unchanged() for s in sources),
                                         "autorizacion_intacta": read_regular(log / "origen.json") == origin_bytes,
                                         "entrada_intacta": read_regular(agent_log / "entrada.txt") == prompt}
                if operation:
                    result["integridad"].update(
                        operacion_intacta=read_regular(log / "operacion.json") == operation_bytes,
                        reserva_intacta=(read_regular(log / "reserva.json") == reservation_bytes))
                require(all(result["integridad"].values()), "Integridad alterada durante la revisión")
            def reserve():
                nonlocal reservation_bytes
                check()
                require(not result["reserva_invocacion"], "Invocación ya reservada")
                if operation:
                    try:
                        persist_review_json(log / "reserva.json", {
                            "operacion": operation["id"], "rol": "revisor", "fecha_utc": timestamp(),
                            "estado": "reservada_antes_de_invocar", "max_invocaciones": 1,
                            "candidato_sha256": authorization["candidato_sha256"],
                            "limite_solicitado_segundos": operation["limite_solicitado_segundos"],
                            "limite_efectivo_segundos": timeout}, exclusive=True)
                    finally:
                        reservation_bytes = read_regular(log / "reserva.json")
                result["reserva_invocacion"] = True
                if operation:
                    result["revisor"]["invocaciones"] = 1
                save()
                if on_invoke is not None:
                    on_invoke()
                result["revisor"]["invocaciones"] = 1
                notify(f"Revisión 1/1: iniciando Codex en una sesión nueva, límite {timeout} s.")
            try:
                check()
                options = {"timeout": timeout} if operation or review_timeout is not None else {}
                result["revisor"] = invoke_reviewer(workspace, final, prompt, agent_log, on_invoke=reserve, **options)
            except ProcessInterrupted as exc:
                result["revisor"].update(exc.result)
                raise
            finally:
                raw = read_regular(final)
                if raw is not None:
                    (agent_log / "respuesta_original.txt").write_bytes(raw)
                check()
            agent = result["revisor"]
            write_json(agent_log / "resumen.json", agent)
            if agent.get("error_registro"):
                stop(8, "fallo_controlador", agent["error_registro"])
            elif agent["estado"] == "tiempo_agotado":
                stop(4, "tiempo_agotado_revisor")
            elif agent["estado"] != "finalizada" or agent["codigo_salida"] != 0:
                stop(3, "fallo_revisor")
            else:
                notify("Revisor finalizado; validando formato y coherencia del dictamen.")
                try:
                    require(raw is not None, "No hay respuesta final")
                    verdict = validate_verdict(raw, line_count, editable=editable)
                except (ValueError, TypeError) as exc:
                    stop(5, "respuesta_invalida", str(exc))
                else:
                    result["dictamen_modelo"] = verdict
                    write_json(log / "dictamen_validado.json", verdict)
                    stop(0 if verdict["decision"] == "aprobar" else 1,
                         "dictamen_aprobar_validado" if verdict["decision"] == "aprobar" else "cambios_solicitados")
    except KeyboardInterrupt as exc:
        stop(9, "interrumpida", str(exc) or "Interrupción")
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError) as exc:
        if result["integridad"] and not all(result["integridad"].values()):
            stop(6, "modificacion_no_permitida", str(exc))
        else:
            stop(8 if result["evidencia_previa_valida"] else 7,
                 "fallo_controlador" if result["evidencia_previa_valida"] else "evidencia_invalida", str(exc))
    finally:
        result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
        try:
            if operation and log is not None and (log / "revisor").is_dir():
                result["revisor_sha256"] = tree_state(log / "revisor")
            save()
        except OSError as exc:
            stop(8, "fallo_controlador", f"No se pudo guardar resultado.json: {exc}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-run", type=Path)
    parser.add_argument("--reevaluation-run", type=Path)
    parser.add_argument("--orchestration-run", type=Path)
    parser.add_argument("--attempt", type=int, choices=(1, 2))
    parser.add_argument("--operation-id", help="Identidad exclusiva del nuevo registro; no admite repetición")
    parser.add_argument("--review-timeout", type=int, help="Solo revisión aislada: 60–600 segundos; predeterminado 180")
    args = parser.parse_args(argv)
    isolated = any(v is not None for v in (args.orchestration_run, args.attempt, args.operation_id, args.review_timeout))
    if isolated:
        if (args.development_run is not None or args.reevaluation_run is not None
                or args.orchestration_run is None or args.attempt is None or args.operation_id is None):
            parser.error("Use --orchestration-run, --attempt y --operation-id juntos, sin argumentos históricos")
        try:
            result = run_isolated_review(args.orchestration_run, args.attempt, args.operation_id, PROJECT,
                                         review_timeout=180 if args.review_timeout is None else args.review_timeout,
                                         progress=cli_progress)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        if args.development_run is None or args.reevaluation_run is None:
            parser.error("La vía histórica requiere --development-run y --reevaluation-run")
        result = run_review(args.development_run, args.reevaluation_run, PROJECT, progress=cli_progress)
    if result["error"]:
        cli_progress("Detenido: " + result["error"])
    print(f"Decisión del controlador: {result['decision_controlador']}; código: {result['codigo_salida']}")
    print(f"Invocaciones del revisor: {result['revisor']['invocaciones']}/1; contraste semántico: pendiente")
    print(f"Registro: {result['registro'] or 'no creado'}")
    return result["codigo_salida"]


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"Señal {signum}")
    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())

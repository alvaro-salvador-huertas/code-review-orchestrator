"""Revisión estática de inspect-json, autorizada por desarrollo y reevaluación explícitos."""

import argparse
import ast
import hashlib
import json
import math
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


def response_schema(line_count):
    fields = {"archivo": {"type": "string", "enum": ["inspect_run.py"]},
              "linea": {"type": "integer", "minimum": 1, "maximum": line_count},
              **{key: {"type": "string", "minLength": 1} for key in ("requisito", "explicacion", "ejemplo")}}
    return {"type": "object", "additionalProperties": False, "required": ["decision", "resumen", "hallazgos"],
            "properties": {"decision": {"type": "string", "enum": ["aprobar", "solicitar_cambios"]},
                           "resumen": {"type": "string", "minLength": 1},
                           "hallazgos": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                                        "required": list(fields), "properties": fields}}}}


def validate_verdict(raw, line_count):
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
        require(finding["archivo"] == "inspect_run.py" and type(finding["linea"]) is int
                and 1 <= finding["linea"] <= line_count, "Archivo o línea fuera del candidato")
        require(all(isinstance(finding[k], str) and finding[k].strip() for k in ("requisito", "explicacion", "ejemplo")),
                "Falta requisito, explicación o ejemplo")
    return verdict


def run_review(development_run, reevaluation_run, project_root=PROJECT, *, progress=None):
    root = Path(project_root).resolve()
    started = time.monotonic()
    result = {"tarea": "inspect-json", "registro": None, "inicio_utc": timestamp(),
              "decision_controlador": "en_preparacion", "codigo_salida": 8,
              "evidencia_previa_valida": False, "reserva_invocacion": False, "max_invocaciones": 1,
              "revisor": {"invocaciones": 0, "estado": "no_ejecutado", "codigo_salida": None},
              "dictamen_modelo": None, "contraste_semantico": "pendiente", "incorporacion": "no_realizada",
              "limites_segundos": {"revisor": 180, "consulta_cli": 10},
              "integridad": {}, "error": None}
    log = archive = None
    def save():
        if log is not None:
            write_json(log / "resultado.json", result)
    def notify(message):
        if progress is not None:
            progress(message)
    def stop(code, state, message=None):
        result.update(codigo_salida=code, decision_controlador=state, error=message)
    try:
        notify("Validando desarrollo, reevaluación y regresión histórica.")
        evidence, authorization, sources = validate_evidence(development_run, reevaluation_run, root)
        materials, selection = review_materials(evidence, authorization)
        require(all(source.path != root / "runs" and source.path not in (root / "runs").parents for source in sources),
                "El registro nuevo quedaría dentro de una entrada")
        result["evidencia_previa_valida"] = True
        original_state = tree_state(root, filter_local=True)
        prompt = read_regular(root / PROMPT)
        require(prompt is not None and prompt.strip(), "Faltan las instrucciones específicas")
        line_count = len(materials["inspect_run.py"].splitlines())
        parent = Path(tempfile.gettempdir()).resolve()
        require(parent != root and root not in parent.parents, "El workspace debe estar fuera del proyecto")
        (root / "runs").mkdir(exist_ok=True)
        log = root / "runs" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_inspect-json_review_" + uuid4().hex)
        log.mkdir()
        result["registro"] = str(log)
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
                require(all(result["integridad"].values()), "Integridad alterada durante la revisión")
            def reserve():
                check()
                require(not result["reserva_invocacion"], "Invocación ya reservada")
                result["reserva_invocacion"] = True
                save()
                result["revisor"]["invocaciones"] = 1
                notify("Revisión 1/1: iniciando Codex en una sesión nueva, límite 180 s.")
            try:
                check()
                result["revisor"] = invoke_reviewer(workspace, final, prompt, agent_log, on_invoke=reserve)
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
                    verdict = validate_verdict(raw, line_count)
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
            save()
        except OSError as exc:
            stop(8, "fallo_controlador", f"No se pudo guardar resultado.json: {exc}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-run", required=True, type=Path)
    parser.add_argument("--reevaluation-run", required=True, type=Path)
    args = parser.parse_args(argv)
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

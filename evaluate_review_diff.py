"""Congelar, revisar una sola vez y puntuar ocho diffs Python de confianza."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

from case_evidence import digest, parse_json, require, snapshot_tree
from evaluate_reviewer import (
    RUNTIME_FILES, effective_configuration, normalized_command, required_bytes,
    record_git, requested_configuration, save_json,
)
from process_environment import process_environment
import review_diff


PROJECT = Path(__file__).resolve().parent
CORPUS = "evals/review_diff/casos.json"
FIXTURES = "evals/review_diff/informes_sinteticos.json"
SOURCES = tuple(dict.fromkeys((*RUNTIME_FILES, "review_diff.py", "evaluate_review_diff.py",
                              "timeout_diagnostics.py", CORPUS, FIXTURES,
                              "docs/evaluacion-review-diff.md")))
IDS = [f"caso_{i:02d}" for i in range(1, 9)]
ORIGIN = "evaluacion_diff_python_v1"


def read_json(path):
    return parse_json(required_bytes(path))


def catalog(path):
    value = read_json(path)
    require(value["version"] == 1 and [c["id"] for c in value["casos"]] == IDS,
            "Catálogo u orden desconocido")
    cases = value["casos"]
    require(sorted(len(c["expectativa"]["defectos"]) for c in cases) == [0]*4 + [1]*4,
            "Se requieren cuatro casos correctos y cuatro con un defecto")
    for c in cases:
        require(c["archivo"] == "module.py" and c["base"] != c["candidato"], "Diff inválido")
        for side in ("base", "candidato"):
            ast.parse(c[side])  # Solo sintaxis, nunca importar ni ejecutar el candidato.
            require(review_diff.OID.fullmatch(c["commits"][side]), "SHA no fijado")
        require(1 <= len(c["criterios"]) <= 5 and all(0 < len(x) <= 500 for x in c["criterios"]),
                "Criterios inválidos")
        expectation = c["expectativa"]
        require(expectation["justificacion"].strip() and expectation["evidencia"], "Falta evidencia")
        for defect in expectation["defectos"]:
            require(defect["id"] == "D1" and defect["descripcion"].strip(), "Defecto inválido")
            require(type(defect["linea"]) is int and
                    1 <= defect["linea"] <= len(c["candidato"].splitlines()), "Línea inválida")
    return value


def build_repository(repo, cases):
    """Objetos Git portables: contenido y metadatos fijos; sin hooks ni checkout."""
    with process_environment() as env:
        env.update(GIT_AUTHOR_NAME="Synthetic fixture", GIT_COMMITTER_NAME="Synthetic fixture",
                   GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                   GIT_AUTHOR_DATE="2000-01-01T00:00:00+0000",
                   GIT_COMMITTER_DATE="2000-01-01T00:00:00+0000")
        subprocess.run(["git", "init", "-q", "--bare", "--object-format=sha1", "--template=", str(repo)],
                       env=env, check=True, capture_output=True, timeout=10)
        def git(*args, data=None):
            return subprocess.run(["git", "--git-dir", str(repo), *args], input=data,
                                  env=env, check=True, capture_output=True, timeout=10).stdout.decode().strip()
        commits = {}
        for case in cases:
            pair = {}
            for side in ("base", "candidato"):
                blob = git("hash-object", "-w", "--stdin", data=case[side].encode())
                tree = git("mktree", data=f"100644 blob {blob}\tmodule.py\n".encode())
                parents = ("-p", pair["base"]) if side == "candidato" else ()
                pair[side] = git("commit-tree", tree, *parents, data=(side + "\n").encode())
            git("update-ref", "refs/heads/" + case["id"], pair["candidato"])
            commits[case["id"]] = pair
    return commits


def preview(repo, case):
    materials = review_diff.prepare(repo, case["commits"]["base"], case["commits"]["candidato"],
                                    [case["archivo"]], case["criterios"])
    return {"estado": "vista_previa_sin_modelo", "materiales": materials,
            "instrucciones": review_diff.review_prompt(materials),
            "esquema": review_diff.response_schema(materials)}


def prepare(output, root=PROJECT):
    output, root = Path(output).absolute(), Path(root)
    data = catalog(root / CORPUS)
    output.mkdir(mode=0o700)  # Padre existente; no sustituir una preparación.
    frozen = output / "preparacion"
    frozen.mkdir()
    for source in SOURCES:
        path = frozen / "fuentes" / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(required_bytes(root / source))
    record_git(root, frozen, SOURCES)
    commits = build_repository(frozen / "repo.git", data["casos"])
    for case in data["casos"]:
        require(commits[case["id"]] == case["commits"], "Los commits no coinciden con el catálogo")
        save_json(frozen / (case["id"] + ".json"), preview(frozen / "repo.git", case))
    configuration = requested_configuration()
    configuration.update(limite_agente_segundos=review_diff.TIMEOUT, max_invocaciones=8,
                         max_por_caso=1, reintentos=0)
    manifest = {"version": 1, "procedencia": ORIGIN, "estado": "preparada", "orden": IDS,
                "configuracion_solicitada": configuration,
                "configuracion_efectiva": effective_configuration(),
                "sha256": snapshot_tree(frozen)}
    save_json(output / "preparacion.json", manifest)
    return manifest


def validate_preparation(experiment, *, launching=False, root=PROJECT):
    manifest = read_json(experiment / "preparacion.json")
    require(manifest["version"] == 1 and manifest["procedencia"] == ORIGIN and
            manifest["estado"] == "preparada" and manifest["orden"] == IDS, "Preparación inválida")
    frozen = experiment / "preparacion"
    require(snapshot_tree(frozen) == manifest["sha256"], "Preparación alterada")
    data = catalog(frozen / "fuentes" / CORPUS)
    for case in data["casos"]:
        require(read_json(frozen / (case["id"] + ".json")) == preview(frozen / "repo.git", case),
                "Vista previa incoherente")
    if launching:
        for source in SOURCES:
            require(required_bytes(Path(root) / source) == required_bytes(frozen / "fuentes" / source),
                    f"El lanzador o el corpus cambió desde la preparación: {source}")
    return manifest, data["casos"]


def read_record(directory, prepared, mode):
    result = read_json(directory / "resultado.json")
    require(read_json(directory / "materiales.json") == prepared["materiales"] and
            read_json(directory / "respuesta.schema.json") == prepared["esquema"] and
            required_bytes(directory / "instrucciones.txt") == prepared["instrucciones"].encode(),
            "Materiales del informe distintos de los congelados")
    require(result["estado"] == "informe_disponible", result.get("detalle") or
            f"{result['estado']}: {(result.get('revisor') or {}).get('estado', 'sin proceso')}")
    agent = result["revisor"]
    require(agent["estado"] == "finalizada" and type(agent["codigo_salida"]) is int and
            agent["codigo_salida"] == 0 and not agent.get("error_registro"), "Fallo técnico del revisor")
    require(type(agent["invocaciones"]) is int and agent["invocaciones"] == (1 if mode == "real" else 0),
            "Presupuesto de invocaciones incoherente")
    if mode == "real":
        require(read_json(directory / "reserva.json")["max_invocaciones"] == 1, "Falta la reserva")
    raw = required_bytes(directory / "revisor/respuesta_original.json")
    require(len(raw) <= review_diff.MAX_RESPONSE, "Respuesta demasiado grande")
    response = review_diff.validate_response(raw, prepared["materiales"])
    require(response == result["respuesta"], "Respuesta archivada inconsistente")
    return response


def new_launch(experiment, mode):
    directory = experiment / "lanzamiento"
    directory.mkdir(mode=0o700)  # Reserva atómica permanente, sin reanudación.
    result = {"version": 1, "modo": mode, "estado": "en_curso",
              "preparacion_sha256": digest(required_bytes(experiment / "preparacion.json")),
              "casos": [{"id": ident, "estado": "no_ejecutado", "invocaciones": 0,
                         "sha256": None, "error": None} for ident in IDS]}
    save_json(directory / "resultado.json", result)
    return directory, result


def run(experiment, root=PROJECT):
    manifest, cases = validate_preparation(experiment, launching=True, root=root)
    launch, result = new_launch(experiment, "real")
    baseline = None
    def check_closed():
        for closed in result["casos"]:
            if closed["sha256"] is not None:
                require(snapshot_tree(launch / closed["id"]) == closed["sha256"], "Informe anterior alterado")
    try:
        for case, entry in zip(cases, result["casos"]):
            require(digest(required_bytes(experiment / "preparacion.json")) == result["preparacion_sha256"]
                    and snapshot_tree(experiment / "preparacion") == manifest["sha256"], "Preparación alterada")
            check_closed()
            entry.update(estado="en_curso", invocaciones=None)
            save_json(launch / "resultado.json", result)
            directory = launch / case["id"]
            try:
                materials = read_json(experiment / "preparacion" / (case["id"] + ".json"))
                record = review_diff.run_review(materials["materiales"], directory)
                entry["invocaciones"] = (record.get("revisor") or {}).get("invocaciones")
                read_record(directory, materials, "real")
                signature = (normalized_command(record["revisor"]["comando"]),
                             required_bytes(directory / "revisor/codex_version.txt"))
                if baseline is None:
                    baseline = signature
                require(signature == baseline, "Cambió la versión o los argumentos de Codex")
                validate_preparation(experiment, launching=True, root=root)
                check_closed()
                entry["estado"] = "informe_disponible"
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
                entry.update(estado="fallo_tecnico", error=str(exc) or type(exc).__name__)
            finally:
                if directory.is_dir():
                    try:
                        entry["sha256"] = snapshot_tree(directory)
                    except (OSError, ValueError) as exc:
                        entry.update(estado="fallo_tecnico", error=(entry["error"] or "") +
                                     f"; no se pudo cerrar la evidencia: {exc}")
                save_json(launch / "resultado.json", result)
            if entry["estado"] != "informe_disponible":
                break
        result["estado"] = ("completada" if all(c["estado"] == "informe_disponible"
                                               for c in result["casos"]) else "incompleta")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        result.update(estado="incompleta", error=str(exc) or type(exc).__name__)
        # Un fallo de integridad previo a la siguiente llamada no es una omisión del revisor.
        for item in result["casos"]:
            if item["estado"] in ("no_ejecutado", "en_curso"):
                item.update(estado="fallo_tecnico", error=result["error"])
                break
    finally:
        save_json(launch / "resultado.json", result)
    return result


def archives(experiment):
    _, cases = validate_preparation(experiment)
    launch = read_json(experiment / "lanzamiento/resultado.json")
    require(launch["version"] == 1 and launch["modo"] in ("real", "sintetico") and
            [c["id"] for c in launch["casos"]] == IDS and launch["preparacion_sha256"] ==
            digest(required_bytes(experiment / "preparacion.json")), "Campaña incoherente")
    entries = []
    for case, item in zip(cases, launch["casos"]):
        response, error = None, item.get("error")
        state = item["estado"]
        require(state in ("no_ejecutado", "en_curso", "fallo_tecnico", "informe_disponible"), "Estado desconocido")
        if state in ("en_curso", "informe_disponible"):
            try:
                directory = experiment / "lanzamiento" / case["id"]
                require(snapshot_tree(directory) == item["sha256"], "Informe alterado o incompleto")
                response = read_record(directory, read_json(experiment / "preparacion" /
                                       (case["id"] + ".json")), launch["modo"])
                state = "informe_disponible"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                state, error = "fallo_tecnico", str(exc)
        entries.append((case, state, response, error))
    return launch, entries


def judgments_template(experiment):
    launch, entries = archives(experiment)
    return {"version": 1, "origen": "humano" if launch["modo"] == "real" else "fixture_sintetico",
            "autor": "", "lanzamiento_sha256": digest(required_bytes(experiment / "lanzamiento/resultado.json")),
            "casos": [{"id": case["id"], "revision_completa": False, "justificacion": "",
                       "hallazgos": [{"indice": i, "sha256": digest(review_diff.json_bytes(f)),
                                      "respaldado": None, "defecto": None, "justificacion": ""}
                                     for i, f in enumerate(response["hallazgos"], 1)] if response else []}
                      for case, state, response, error in entries]}


def score(experiment, judgments):
    launch, entries = archives(experiment)
    template = judgments_template(experiment)
    require(judgments["version"] == 1 and judgments["origen"] == template["origen"] and
            judgments["lanzamiento_sha256"] == template["lanzamiento_sha256"] and
            [c["id"] for c in judgments["casos"]] == IDS, "Juicio de otro registro o procedencia")
    require(isinstance(judgments["autor"], str) and judgments["autor"].strip(), "Falta autor del juicio")
    rows = []
    for (case, state, response, error), decision, pending in zip(entries, judgments["casos"], template["casos"]):
        expected = len(case["expectativa"]["defectos"])
        row = {"id": case["id"], "estado": state, "error": error, "defectos_esperados": expected,
               "defectos_detectados": None, "defectos_omitidos": None,
               "hallazgos_falsos_en_correctos": 0, "adicionales_no_respaldados": 0,
               "adicionales_respaldados": 0, "menciones_duplicadas": 0, "hallazgos": 0,
               "denominadores": {"defectos": 0, "correctos": 0, "hallazgos": 0}}
        if state != "informe_disponible":
            rows.append(row)
            continue
        require(type(decision["revision_completa"]) is bool, "Revisión completa debe ser booleana")
        if not decision["revision_completa"]:
            row["estado"] = "pendiente_juicio"
            rows.append(row)
            continue
        require(isinstance(decision["justificacion"], str) and decision["justificacion"].strip(),
                "Falta justificación humana del caso")
        require(len(decision["hallazgos"]) == len(pending["hallazgos"]), "Faltan juicios de hallazgos")
        detected, mentions = set(), 0
        for judgment, finding in zip(decision["hallazgos"], pending["hallazgos"]):
            require(judgment["indice"] == finding["indice"] and judgment["sha256"] == finding["sha256"],
                    "Juicio de otro hallazgo")
            require(type(judgment["respaldado"]) is bool and isinstance(judgment["justificacion"], str)
                    and judgment["justificacion"].strip(), "Cada hallazgo necesita un juicio explícito")
            defect = judgment["defecto"]
            require(defect is None or (expected == 1 and defect == "D1" and judgment["respaldado"]),
                    "Asignación de defecto incoherente")
            if not judgment["respaldado"]:
                row["adicionales_no_respaldados" if expected else "hallazgos_falsos_en_correctos"] += 1
            elif defect is None:
                row["adicionales_respaldados"] += 1
            else:
                detected.add(defect)
                mentions += 1
        row.update(estado="puntuado", defectos_detectados=len(detected),
                   defectos_omitidos=expected-len(detected), menciones_duplicadas=mentions-len(detected),
                   hallazgos=len(response["hallazgos"]), denominadores={"defectos": expected,
                   "correctos": int(not expected), "hallazgos": len(response["hallazgos"])})
        rows.append(row)
    evaluated = [r for r in rows if r["estado"] == "puntuado"]
    bad = [r for r in evaluated if r["defectos_esperados"]]
    good = [r for r in evaluated if not r["defectos_esperados"]]
    def ratio(numerator, denominator):
        return {"numerador": numerator, "denominador": denominator,
                "proporcion": numerator / denominator if denominator else None}
    conflicts = sum(r["adicionales_respaldados"] for r in evaluated)
    totals = {"casos_planificados": 8, "correctos_planificados": 4, "defectos_planificados": 4,
              "casos_puntuados": len(evaluated), "defectos_no_evaluables": 4-len(bad),
              "correctos_no_evaluables": 4-len(good),
              "informes_validos": len(evaluated)+sum(r["estado"] == "pendiente_juicio" for r in rows),
              "deteccion": ratio(sum(r["defectos_detectados"] for r in bad), len(bad)),
              "omision": ratio(sum(r["defectos_omitidos"] for r in bad), len(bad)),
              "correctos_con_falsos": ratio(sum(r["hallazgos_falsos_en_correctos"] > 0 for r in good), len(good)),
              "falsos_en_correctos": sum(r["hallazgos_falsos_en_correctos"] for r in good),
              "adicionales_no_respaldados": ratio(sum(r["adicionales_no_respaldados"] for r in bad),
                                                  sum(r["hallazgos"] for r in bad)),
              "menciones_duplicadas": sum(r["menciones_duplicadas"] for r in evaluated),
              "adicionales_respaldados": conflicts,
              "fallos_tecnicos": ratio(sum(r["estado"] == "fallo_tecnico" for r in rows), 8),
              "no_ejecutados": ratio(sum(r["estado"] == "no_ejecutado" for r in rows), 8),
              "pendientes_juicio": sum(r["estado"] == "pendiente_juicio" for r in rows)}
    return {"version": 1, "modo": launch["modo"], "estado": "requiere_revision" if conflicts or
            totals["pendientes_juicio"] else "puntuacion_disponible", "casos": rows, "totales": totals,
            "preparacion_sha256": launch["preparacion_sha256"],
            "lanzamiento_sha256": template["lanzamiento_sha256"],
            "juicios_sha256": digest(review_diff.json_bytes(judgments))}


def check(output, root=PROJECT):
    prepare(output, root)
    launch, result = new_launch(output, "sintetico")
    fixtures = read_json(output / "preparacion/fuentes" / FIXTURES)
    require(fixtures["version"] == 1 and fixtures["procedencia"] == "fixture_sintetico" and
            [c["id"] for c in fixtures["casos"]] == IDS, "Fixtures inválidos")
    for entry, fixture in zip(result["casos"], fixtures["casos"]):
        entry["estado"] = fixture["estado"]
        if fixture["estado"] == "fallo_tecnico":
            entry["error"] = "Fallo técnico sintético, sin invocar runtime ni modelo"
            continue
        directory = launch / entry["id"]
        (directory / "revisor").mkdir(parents=True)
        materials = read_json(output / "preparacion" / (entry["id"] + ".json"))
        save_json(directory / "materiales.json", materials["materiales"])
        save_json(directory / "respuesta.schema.json", materials["esquema"])
        (directory / "instrucciones.txt").write_text(materials["instrucciones"], encoding="utf-8")
        save_json(directory / "revisor/respuesta_original.json", fixture["respuesta"])
        save_json(directory / "resultado.json", {"estado": "informe_disponible",
                  "revision_humana": "pendiente", "pruebas_ejecutadas": False,
                  "respuesta": fixture["respuesta"], "revisor": {"estado": "finalizada",
                  "codigo_salida": 0, "invocaciones": 0, "procedencia": "fixture_sintetico"}})
        entry["sha256"] = snapshot_tree(directory)
    result["estado"] = "fixtures_preparados"
    save_json(launch / "resultado.json", result)
    judgments = judgments_template(output)
    judgments["autor"] = "Fixture sintético: no es un juicio humano real"
    for decision, fixture in zip(judgments["casos"], fixtures["casos"]):
        decision.update(revision_completa=True, justificacion="Adjudicación sintética para probar recuentos.")
        for judgment, fixture_judgment in zip(decision["hallazgos"], fixture["juicios"]):
            judgment.update(fixture_judgment)
    save_json(output / "juicios_sinteticos.json", judgments)
    result = score(output, judgments)
    save_json(output / "comprobacion.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("prepare", "check"):
        p = commands.add_parser(name)
        p.add_argument("--output", type=Path, required=True, help="Directorio nuevo; padre existente")
    for name in ("run", "judgments", "score"):
        p = commands.add_parser(name)
        p.add_argument("--experiment", type=Path, required=True)
        if name == "run":
            p.add_argument("--invoke-model", action="store_true", required=True)
        elif name == "judgments":
            p.add_argument("--output", type=Path, required=True, help="Archivo nuevo de juicio humano")
        else:
            p.add_argument("--judgments", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation in ("prepare", "check"):
            output = args.output.absolute()
            result = prepare(output) if args.operation == "prepare" else check(output)
        else:
            experiment = args.experiment.resolve(strict=True)
            if args.operation == "run":
                result = run(experiment)
            elif args.operation == "judgments":
                result = judgments_template(experiment)
                with args.output.open("xb") as stream:
                    stream.write(review_diff.json_bytes(result))
            else:
                result = score(experiment, read_json(args.judgments))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"evaluate_review_diff: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("estado") in ("incompleta", "requiere_revision") else 0


if __name__ == "__main__":
    sys.exit(main())

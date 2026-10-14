"""Desarrollo, evaluación independiente y revisión con uno o dos intentos."""

import argparse
from pathlib import Path
import sys
import time
from uuid import uuid4

from case_evidence import digest, parse_json, read_regular, require, snapshot_tree, snapshot_matches
from repair_case import inventory, load_reference, run_repair, timestamp, utc_timestamp, write_json
from review_case import correction_context, run_review, validate_repair, validate_review_record


class IntegrityError(ValueError):
    pass


def next_stage(repair, review=None):
    """Acción, motivo y código: solo aserciones o hallazgos permiten corregir."""
    if review is not None:
        code = review["codigo_salida"]
        if code == 0 and review["aprobada"]:
            return "aprobar", "revision_aprobada", 0
        if code == 1 and review["decision_controlador"] == "cambios_solicitados":
            return "corregir", "cambios_solicitados", 1
        return "detener", review["decision_controlador"], code if code in range(3, 9) else 7
    reason = repair.get("detencion")
    if reason:
        code = {"tiempo_agotado": 4, "fallo_agente": 3, "modificacion_no_permitida": 6,
                "evidencia_invalida": 7, "error_pruebas": 8}.get(reason, 8)
        return "detener", reason, code
    code = repair["codigo_salida"]
    if code == 0 and repair["aceptada"]:
        return "revisar", "supera_las_pruebas_disponibles", 0
    if (code == 1 and repair["estado"] == "no_supera_pruebas"
            and repair.get("pruebas_posteriores_clasificacion") == "fallos_asercion"):
        return "corregir", "fallos_asercion", 1
    return "detener", repair["estado"], {3: 3, 4: 4, 5: 6, 6: 8}.get(code, 7)


def run_orchestration(case_id, project_root, max_attempts=2):
    started_at, started = utc_timestamp(), time.monotonic()
    root = Path(project_root).resolve()
    result = {
        "caso": case_id, "version_contrato": 2, "registro": None,
        "inicio_utc": started_at.isoformat().replace("+00:00", "Z"),
        "max_intentos": max_attempts, "max_invocaciones": max_attempts * 2,
        "intentos": [], "invocaciones": {"desarrollador": 0, "revisor": 0, "total": 0},
        "estado": "en_curso", "codigo_salida": None, "aprobada": False,
        "integridad": {}, "errores_controlador": [], "registros_sha256": {},
    }
    run_dir = None
    fixed_hashes = None
    originals = None
    prompt = None

    def save():
        write_json(run_dir / "resultado.json", result)

    def check_integrity():
        checks = {
            "originales_intactos": inventory(root) == originals,
            "referencia_fija_intacta": snapshot_matches(run_dir / "referencia", fixed_hashes),
            "instrucciones_revisor_intactas": read_regular(root / "prompts/reviewer.md") == prompt,
        }
        checks["registros_intactos"] = all(
            snapshot_matches(Path(path), hashes) for path, hashes in result["registros_sha256"].items()
        )
        result["integridad"] = checks
        if not all(checks.values()):
            raise IntegrityError("Se alteraron referencias, instrucciones o registros durante el flujo")

    def collect(child, role):
        calls = child["agente" if role == "desarrollador" else "revisor"]["invocaciones"]
        require(type(calls) is int and calls in (0, 1), "Una etapa excede su límite de invocaciones")
        result["invocaciones"][role] += calls
        result["invocaciones"]["total"] += calls
        require(result["invocaciones"]["total"] <= result["max_invocaciones"],
                "Presupuesto de invocaciones excedido")
        if child["registro"]:
            path = Path(child["registro"])
            # Los fallos de registro pueden carecer de resumen; se guardan sus diagnósticos.
            result["registros_sha256"][str(path)] = snapshot_tree(path)
            if child["codigo_salida"] in (0, 1):
                require(parse_json((path / "resultado.json").read_bytes()) == child,
                        "El resultado interno y el registro no coinciden")

    try:
        require(case_id == "case_02" and type(max_attempts) is int and max_attempts in (1, 2),
                "Solo se admite case_02 y uno o dos intentos")
        reference = load_reference(root)
        require("**Versión 2" in reference["contrato.md"].decode("utf-8"),
                "Se requiere el contrato de versión 2")
        originals = inventory(root)
        prompt = read_regular(root / "prompts/reviewer.md")
        require(prompt is not None and prompt.strip(), "Faltan las instrucciones del revisor")
        runs = root / "runs"
        runs.mkdir(exist_ok=True)
        run_dir = runs / f"{started_at.strftime('%Y%m%dT%H%M%S%fZ')}_case_02_orchestrate_{uuid4().hex}"
        run_dir.mkdir()
        result["registro"] = str(run_dir)
        (run_dir / "referencia").mkdir()
        for name, data in reference.items():
            (run_dir / "referencia" / name).write_bytes(data)
        fixed_hashes = {name: digest(data) for name, data in reference.items()}
        result["sha256"] = {"referencia": fixed_hashes, "originales": originals,
                             "instrucciones_revisor": digest(prompt)}
        starting, feedback, provenance = reference["solution.py"], None, {"tipo": "benchmark"}
        save()
        for number in range(1, max_attempts + 1):
            check_integrity()
            entry = {"numero": number, "partida_sha256": digest(starting),
                     "reparacion": None, "revision": None, "transiciones": []}
            result["intentos"].append(entry)
            save()
            repair = run_repair(case_id, root, reference=reference, originals=originals,
                                starting_candidate=starting, provenance=provenance,
                                feedback=feedback, strict=True)
            entry["reparacion"] = repair
            collect(repair, "desarrollador")
            check_integrity()
            action, reason, code = next_stage(repair)
            entry["transiciones"].append({"etapa": "desarrollo", "accion": action, "motivo": reason})
            save()
            review = None
            if action != "detener":
                validate_repair(Path(repair["registro"]), root, allow_test_failure=True)
            if action == "revisar":
                check_integrity()
                review = run_review(Path(repair["registro"]), root)
                entry["revision"] = review
                collect(review, "revisor")
                check_integrity()
                if review["codigo_salida"] in (0, 1):
                    validate_review_record(Path(review["registro"]), Path(repair["registro"]), root)
                action, reason, code = next_stage(repair, review)
                entry["transiciones"].append({"etapa": "revision", "accion": action, "motivo": reason})
                save()
            if action == "aprobar":
                result.update(estado="aprobada", codigo_salida=0, aprobada=True)
                break
            if action == "detener":
                result.update(estado=reason, codigo_salida=code)
                break
            require(action == "corregir", "Transición desconocida")
            if number == max_attempts:
                entry["transiciones"].append({"etapa": "presupuesto", "accion": "detener",
                                              "motivo": "intentos_agotados"})
                result.update(estado="intentos_agotados", codigo_salida=1)
                break
            starting, feedback, provenance = correction_context(
                Path(repair["registro"]), Path(review["registro"]) if review else None, root)
            check_integrity()
        check_integrity()
    except IntegrityError as exc:
        result.update(estado="modificacion_no_permitida", codigo_salida=6, aprobada=False)
        result["errores_controlador"].append(str(exc))
    except ValueError as exc:
        result.update(estado="evidencia_invalida", codigo_salida=7, aprobada=False)
        result["errores_controlador"].append(str(exc))
    except OSError as exc:
        result.update(estado="fallo_controlador", codigo_salida=8, aprobada=False)
        result["errores_controlador"].append(str(exc))
    result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
    if run_dir is not None:
        try:
            save()
        except OSError as exc:
            result.update(estado="fallo_controlador", codigo_salida=8, aprobada=False)
            result["errores_controlador"].append(f"No se pudo guardar el registro general: {exc}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("caso", choices=("case_02",))
    parser.add_argument("--max-attempts", type=int, choices=(1, 2), default=2,
                        help="Incluye el intento inicial; 2 permite una corrección")
    args = parser.parse_args(argv)
    result = run_orchestration(args.caso, Path(__file__).resolve().parent, args.max_attempts)
    print(f"Estado: {result['estado']}")
    print(f"Intentos: {len(result['intentos'])}/{result['max_intentos']}")
    print(f"Invocaciones: {result['invocaciones']['total']}/{result['max_invocaciones']}")
    print(f"Registro: {result['registro'] or 'no creado'}")
    for error in result["errores_controlador"]:
        print(f"Error del controlador: {error}", file=sys.stderr)
    return result["codigo_salida"]


if __name__ == "__main__":
    sys.exit(main())

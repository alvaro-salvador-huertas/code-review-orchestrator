"""Ejecuta un caso local sobre una copia y conserva su registro."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid4

from case_config import CASES, reference_paths

TIMEOUT_SECONDS = 30


def utc_timestamp():
    return datetime.now(timezone.utc)


def run_case(case_id, project_root):
    """Devuelve 0 solo si el proceso terminó y su registro quedó completo."""
    started_at = utc_timestamp()
    started_clock = time.monotonic()
    run_dir = None
    evaluation_log = None
    errors = []
    result = {
        "version_evaluacion": 2,
        "proceso_pruebas": None,
        "caso": case_id,
        "inicio_utc": started_at.isoformat().replace("+00:00", "Z"),
        "fin_utc": None,
        "duracion_segundos": None,
        "comando": None,
        "directorio_trabajo": None,
        "limite_segundos": TIMEOUT_SECONDS,
        "estado": "error_ejecucion",
        "codigo_salida_pruebas": None,
        "errores_controlador": errors,
        "politica_entorno": "evaluation",
    }

    try:
        project_root = Path(project_root).resolve()
        sources = reference_paths(project_root, case_id)
        contract = sources["contrato.md"]
        required = list(sources.values())
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("Faltan archivos requeridos: " + ", ".join(missing))

        runs_dir = project_root / "runs"
        runs_dir.mkdir(exist_ok=True)
        name = f"{started_at.strftime('%Y%m%dT%H%M%S%fZ')}_{case_id}_{uuid4().hex}"
        destination = runs_dir / name
        destination.mkdir()
        run_dir = destination
        workspace = run_dir / "workspace"
        workspace.mkdir()
        shutil.copy2(required[0], workspace / "solution.py")
        shutil.copy2(required[1], workspace / "test_solution.py")
        shutil.copy2(contract, run_dir / "contrato.md")

        # Imports diferidos: python_evaluator importa repair_case, que reutiliza
        # TIMEOUT_SECONDS y utc_timestamp de este módulo, también en la CLI.
        from python_evaluator import PYTHON, run_isolated, validate_isolation
        from repair_case import ProcessInterrupted, ProcessRecordError, run_process

        command = [
            PYTHON, "-B", "-m", "unittest", "discover",
            "-s", str(workspace), "-p", "test_solution.py", "-v",
        ]
        result["comando"] = command
        result["directorio_trabajo"] = str(workspace)
        # El volumen de salida no puede cubrir el padre del bind de workspace.
        # Los canales se publican después en sus ubicaciones históricas.
        evaluation_log = run_dir / "evaluacion"
        try:
            process = run_isolated(command, workspace, evaluation_log, TIMEOUT_SECONDS,
                                   materials=(), runner=run_process)
        except (ProcessInterrupted, ProcessRecordError) as exc:
            result["proceso_pruebas"] = exc.result
            raise OSError(str(exc)) from exc
        result["proceso_pruebas"] = process
        if process["estado"] == "tiempo_agotado":
            result["estado"] = "tiempo_agotado"
        elif process["estado"] == "finalizada" and process.get("error") is None:
            validate_isolation(process, materials=(), log=evaluation_log)
            if type(process["codigo_salida"]) is not int:
                raise ValueError("Código de unittest ausente o inválido")
            result["codigo_salida_pruebas"] = process["codigo_salida"]
            result["estado"] = "finalizada"
        else:
            errors.append(process.get("error") or "La evaluación aislada no finalizó: " + process["estado"])
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        errors.append(str(exc))

    if run_dir is not None:
        # Mover, sin recapturar ni duplicar bytes: los presupuestos se aplicaron
        # durante la escritura. Un error en un canal no impide publicar el otro.
        for filename in ("stdout.txt", "stderr.txt"):
            try:
                source = evaluation_log / filename if evaluation_log is not None else None
                if source is not None and source.is_file():
                    source.replace(run_dir / filename)
                elif result["proceso_pruebas"] is not None:
                    raise OSError("Falta el canal registrado por la evaluación aislada")
                else:
                    (run_dir / filename).touch()
            except OSError as exc:
                result["estado"] = "error_ejecucion"
                errors.append(f"No se pudo guardar {filename}: {exc}")

    result["fin_utc"] = utc_timestamp().isoformat().replace("+00:00", "Z")
    result["duracion_segundos"] = time.monotonic() - started_clock
    if run_dir is not None:
        try:
            (run_dir / "resultado.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            result["estado"] = "error_ejecucion"
            errors.append(f"No se pudo guardar resultado.json: {exc}")

    print(f"Estado: {result['estado']}")
    test_code = result["codigo_salida_pruebas"]
    print(f"Código de salida de las pruebas: {test_code if test_code is not None else 'null'}")
    print(f"Registro: {run_dir if run_dir is not None else 'no creado'}")
    for error in errors:
        print(f"Error del controlador: {error}", file=sys.stderr)
    return 0 if result["estado"] == "finalizada" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ejecuta las pruebas de un caso sobre una copia y registra el resultado."
    )
    parser.add_argument("caso", choices=CASES)
    args = parser.parse_args(argv)
    return run_case(args.caso, Path(__file__).resolve().parent)


if __name__ == "__main__":
    sys.exit(main())

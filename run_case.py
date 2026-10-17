"""Ejecuta un caso local sobre una copia y conserva su registro."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from case_config import CASES, reference_paths
from process_environment import process_environment

TIMEOUT_SECONDS = 30


def utc_timestamp():
    return datetime.now(timezone.utc)


def run_case(case_id, project_root):
    """Devuelve 0 solo si el proceso terminó y su registro quedó completo."""
    started_at = utc_timestamp()
    started_clock = time.monotonic()
    run_dir = None
    stdout = b""
    stderr = b""
    errors = []
    result = {
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

        command = [
            sys.executable, "-B", "-m", "unittest", "discover",
            "-s", str(workspace), "-p", "test_solution.py", "-v",
        ]
        result["comando"] = command
        result["directorio_trabajo"] = str(workspace)
        with process_environment() as environment:
            completed = subprocess.run(
                command,
                cwd=workspace,
                shell=False,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
                env=environment,
            )
        stdout = completed.stdout
        stderr = completed.stderr
        result["codigo_salida_pruebas"] = completed.returncode
        result["estado"] = "finalizada"
    except subprocess.TimeoutExpired as exc:
        # El modo binario conserva también la salida parcial del proceso.
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        result["estado"] = "tiempo_agotado"
    except OSError as exc:
        errors.append(str(exc))

    if run_dir is not None:
        # Intentar guardar ambos canales aunque falle la escritura de uno.
        for filename, content in (("stdout.txt", stdout), ("stderr.txt", stderr)):
            try:
                (run_dir / filename).write_bytes(content)
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

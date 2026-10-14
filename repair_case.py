"""Un único intento de reparación con Codex y evaluación independiente."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from run_case import CASES, TIMEOUT_SECONDS, utc_timestamp


CODEX_EXECUTABLE = "codex"
AGENT_TIMEOUT_SECONDS = 180
PREFLIGHT_TIMEOUT_SECONDS = 10


def timestamp():
    return utc_timestamp().isoformat().replace("+00:00", "Z")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_regular(path):
    """No seguir enlaces ni abrir dispositivos al recoger entregables."""
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return None
        return path.read_bytes()
    except FileNotFoundError:
        return None


def digest(content):
    return hashlib.sha256(content).hexdigest() if content is not None else None


def inventory(project_root):
    return {
        str(path.relative_to(project_root)): digest(read_regular(path))
        for folder in ("benchmark", "tasks")
        for path in sorted((project_root / folder).rglob("*"))
        if not path.is_dir() or path.is_symlink()
    }


def run_process(command, workspace, log_dir, timeout, prompt=None,
                stdout_name="stdout.txt", stderr_name="stderr.txt"):
    """Registrar los canales en disco y detener el grupo al agotar el tiempo."""
    log_dir.mkdir(exist_ok=True)
    started = time.monotonic()
    result = {
        "comando": command, "directorio_trabajo": str(workspace),
        "inicio_utc": timestamp(), "limite_segundos": timeout,
        "estado": "error_inicio", "codigo_salida": None, "error": None,
    }
    with (log_dir / stdout_name).open("wb") as stdout, (log_dir / stderr_name).open("wb") as stderr:
        try:
            with subprocess.Popen(
                command, cwd=workspace, shell=False,
                stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, start_new_session=(os.name == "posix"),
            ) as process:
                try:
                    process.communicate(input=prompt, timeout=timeout)
                    result["estado"] = "finalizada"
                except subprocess.TimeoutExpired:
                    result["estado"] = "tiempo_agotado"
                    if os.name == "posix":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        process.kill()
                    process.communicate()
                result["codigo_salida"] = process.returncode
        except OSError as exc:
            result["estado"] = "ausente" if isinstance(exc, FileNotFoundError) else "error_inicio"
            result["error"] = str(exc)
            stderr.write((str(exc) + "\n").encode("utf-8"))
    result["fin_utc"] = timestamp()
    result["duracion_segundos"] = time.monotonic() - started
    write_json(log_dir / "resultado.json", result)
    return result


def evaluate(solution, reference_tests, log_dir):
    """Cada evaluación recibe solo el candidato y las pruebas del controlador."""
    log_dir.mkdir()
    workspace = log_dir / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_bytes(solution)
    (workspace / "test_solution.py").write_bytes(reference_tests)
    command = [
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(workspace), "-p", "test_solution.py", "-v",
    ]
    result = run_process(command, workspace, log_dir, TIMEOUT_SECONDS)
    result["pruebas_intactas"] = read_regular(workspace / "test_solution.py") == reference_tests
    result["implementacion_intacta"] = read_regular(workspace / "solution.py") == solution
    write_json(log_dir / "resultado.json", result)
    return result


def prepare_prompt(contract, initial_result, initial_log):
    """Construir el encargo sin README, pistas añadidas ni una solución."""
    stdout = (initial_log / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    stderr = (initial_log / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    return (
        "Corrige únicamente solution.py para que cumpla el contrato siguiente.\n"
        "Trabaja solo en el directorio actual. Puedes leer test_solution.py y ejecutar\n"
        "las pruebas, pero no modificarlas, borrarlas ni reemplazarlas. No instales\n"
        "dependencias, no uses Git, no accedas a la web ni delegues en otros agentes.\n"
        "Usa solo la biblioteca estándar de Python. No leas archivos fuera de esta\n"
        "carpeta. Deja la implementación propuesta en solution.py y termina con una\n"
        "explicación breve. El controlador evaluará el archivo por su cuenta.\n\n"
        "CONTRATO\n" + contract.decode("utf-8") + "\n\n"
        "INFORME INICIAL DEL CONTROLADOR\n"
        f"Estado: {initial_result['estado']}\n"
        f"Código de salida: {initial_result['codigo_salida']}\n"
        f"Límite en segundos: {initial_result['limite_segundos']}\n"
        f"STDOUT\n{stdout}\nSTDERR\n{stderr}\n"
    ).encode("utf-8")


def invoke_codex(workspace, final_path, prompt, log_dir):
    """Comprobar la CLI y ejecutar como máximo un codex exec, sin reintentos."""
    version = run_process(
        [CODEX_EXECUTABLE, "--version"], workspace, log_dir / "version",
        PREFLIGHT_TIMEOUT_SECONDS,
    )
    (log_dir / "codex_version.txt").write_bytes((log_dir / "version" / "stdout.txt").read_bytes())
    if version["estado"] != "finalizada" or version["codigo_salida"] != 0:
        return {"estado": "cli_no_disponible", "codigo_salida": None,
                "invocaciones": 0, "version": version}
    help_result = run_process(
        [CODEX_EXECUTABLE, "exec", "--help"], workspace, log_dir / "ayuda",
        PREFLIGHT_TIMEOUT_SECONDS,
    )
    help_text = (log_dir / "ayuda" / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    required = ("--config", "--sandbox", "--cd", "--skip-git-repo-check",
                "--json", "--output-last-message", "--ephemeral")
    if (help_result["estado"] != "finalizada" or help_result["codigo_salida"] != 0
            or any(option not in help_text for option in required)):
        return {"estado": "cli_incompatible", "codigo_salida": None,
                "invocaciones": 0, "version": version, "ayuda": help_result}
    command = [
        CODEX_EXECUTABLE, "exec", "--sandbox", "workspace-write",
        "--config", 'approval_policy="never"',
        "--config", 'web_search="disabled"',
        "--config", "features.multi_agent=false",
        "--config", "sandbox_workspace_write.writable_roots=[]",
        "--config", "sandbox_workspace_write.network_access=false",
        "--config", "sandbox_workspace_write.exclude_slash_tmp=true",
        "--config", "sandbox_workspace_write.exclude_tmpdir_env_var=true",
        "--cd", str(workspace), "--skip-git-repo-check", "--ephemeral",
        "--json", "--output-last-message", str(final_path), "-",
    ]
    result = run_process(
        command, workspace, log_dir, AGENT_TIMEOUT_SECONDS, prompt=prompt,
        stdout_name="eventos.jsonl", stderr_name="errores.txt",
    )
    result.update(invocaciones=1, version=version, ayuda=help_result)
    return result


def select_outcome(result):
    """La aceptación requiere todos los pasos, no solo el código de Codex."""
    if result["errores_controlador"]:
        return 6, "fallo_controlador"
    if any(value is False for value in result["integridad"].values()):
        return 5, "modificacion_no_permitida"
    agent = result["agente"]
    if agent["estado"] == "tiempo_agotado":
        return 4, "tiempo_agotado_agente"
    if (agent["estado"] != "finalizada" or agent["codigo_salida"] != 0
            or not result["candidato_disponible"]):
        return 3, "fallo_agente"
    after = result["pruebas_posteriores"]
    if after["estado"] != "finalizada" or after["codigo_salida"] != 0:
        return 1, "no_supera_pruebas"
    if not result["integridad"] or not all(result["integridad"].values()):
        return 6, "fallo_controlador"
    return 0, "supera_las_pruebas_disponibles"


def repair_case(case_id, project_root):
    started_at = utc_timestamp()
    started = time.monotonic()
    project_root = Path(project_root).resolve()
    run_dir = None
    original_inventory = None
    reference = {}
    result = {
        "caso": case_id, "inicio_utc": started_at.isoformat().replace("+00:00", "Z"),
        "estado": "fallo_controlador", "aceptada": False,
        "agente": {"estado": "no_ejecutado", "codigo_salida": None, "invocaciones": 0},
        "pruebas_iniciales": {"estado": "no_ejecutadas", "codigo_salida": None},
        "pruebas_posteriores": {"estado": "no_ejecutadas", "codigo_salida": None},
        "integridad": {}, "sha256": {}, "candidato_disponible": False,
        "errores_controlador": [],
    }
    try:
        if case_id != "case_02":
            raise ValueError("Este hito solo admite case_02")
        runs_dir = project_root / "runs"
        runs_dir.mkdir(exist_ok=True)
        run_dir = runs_dir / f"{started_at.strftime('%Y%m%dT%H%M%S%fZ')}_{case_id}_repair_{uuid4().hex}"
        run_dir.mkdir()
        agent_log = run_dir / "agente"
        agent_log.mkdir()
        for filename in ("entrada.txt", "eventos.jsonl", "errores.txt", "respuesta_final.txt", "codex_version.txt"):
            (agent_log / filename).write_bytes(b"")
        reference_dir = run_dir / "referencia"
        reference_dir.mkdir()
        original_inventory = inventory(project_root)
        sources = {
            "solution.py": project_root / "benchmark" / case_id / "solution.py",
            "test_solution.py": project_root / "benchmark" / case_id / "test_solution.py",
            "contrato.md": project_root / "tasks" / CASES[case_id],
        }
        for filename, source in sources.items():
            content = read_regular(source)
            if content is None:
                raise OSError(f"Falta un archivo regular requerido: {source}")
            reference[filename] = content
            (reference_dir / filename).write_bytes(content)
        result["sha256"]["referencia"] = {name: digest(data) for name, data in reference.items()}
        result["pruebas_iniciales"] = evaluate(
            reference["solution.py"], reference["test_solution.py"], run_dir / "inicial",
        )
        if result["pruebas_iniciales"]["estado"] in ("ausente", "error_inicio"):
            raise OSError("No se pudo iniciar el proceso de pruebas iniciales")
        prompt = prepare_prompt(reference["contrato.md"], result["pruebas_iniciales"], run_dir / "inicial")
        (agent_log / "entrada.txt").write_bytes(prompt)
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if temporary_root == project_root or project_root in temporary_root.parents:
            raise ValueError("El directorio temporal debe estar fuera del repositorio")
        with tempfile.TemporaryDirectory(prefix="repair-case-", dir=temporary_root) as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            for name in ("solution.py", "test_solution.py"):
                (workspace / name).write_bytes(reference[name])
            final_path = Path(temporary) / "respuesta_final.txt"
            result["agente"] = invoke_codex(workspace, final_path, prompt, agent_log)
            final_response = read_regular(final_path)
            result["agente"]["respuesta_final_disponible"] = final_response is not None
            if final_response is not None:
                (agent_log / "respuesta_final.txt").write_bytes(final_response)
            delivered_tests = read_regular(workspace / "test_solution.py")
            result["integridad"]["pruebas_agente_intactas"] = delivered_tests == reference["test_solution.py"]
            result["sha256"]["pruebas_agente"] = digest(delivered_tests)
            if delivered_tests is not None:
                (agent_log / "test_solution_despues.py").write_bytes(delivered_tests)
            candidate = read_regular(workspace / "solution.py")
            result["candidato_disponible"] = candidate is not None
            if candidate is not None:
                (run_dir / "candidato.py").write_bytes(candidate)
                result["sha256"]["candidato"] = digest(candidate)
                difference = difflib.diff_bytes(
                    difflib.unified_diff, reference["solution.py"].splitlines(keepends=True),
                    candidate.splitlines(keepends=True), fromfile=b"inicial/solution.py",
                    tofile=b"candidato/solution.py",
                )
                (run_dir / "candidato.diff").write_bytes(b"".join(difference))
        if result["candidato_disponible"]:
            result["pruebas_posteriores"] = evaluate(
                candidate, reference["test_solution.py"], run_dir / "posterior",
            )
            if result["pruebas_posteriores"]["estado"] in ("ausente", "error_inicio"):
                raise OSError("No se pudo iniciar el proceso de pruebas posteriores")
    except (OSError, ValueError) as exc:
        result["errores_controlador"].append(str(exc))

    try:
        if original_inventory is not None:
            result["integridad"]["originales_intactos"] = inventory(project_root) == original_inventory
            result["sha256"]["originales"] = original_inventory
        if run_dir is not None and reference:
            result["integridad"]["referencia_intacta"] = all(
                read_regular(run_dir / "referencia" / name) == content
                for name, content in reference.items()
            )
        for phase in ("pruebas_iniciales", "pruebas_posteriores"):
            for check in ("pruebas_intactas", "implementacion_intacta"):
                if check in result[phase]:
                    result["integridad"][f"{phase}_{check}"] = result[phase][check]
    except OSError as exc:
        result["errores_controlador"].append(str(exc))

    # Guardar el diagnóstico del agente incluso si la recogida o evaluación fallaron.
    if run_dir is not None and (run_dir / "agente").is_dir():
        try:
            write_json(run_dir / "agente" / "resultado.json", result["agente"])
        except OSError as exc:
            result["errores_controlador"].append(f"No se pudo guardar el resultado del agente: {exc}")
    code, result["estado"] = select_outcome(result)
    result.update(codigo_salida=code, aceptada=(code == 0), fin_utc=timestamp(),
                  duracion_segundos=time.monotonic() - started)
    if run_dir is not None:
        try:
            write_json(run_dir / "resultado.json", result)
        except OSError as exc:
            code = 6
            result["estado"] = "fallo_controlador"
            result["errores_controlador"].append(f"No se pudo guardar resultado.json: {exc}")
    print(f"Estado: {result['estado'].replace('_', ' ')}")
    print(f"Pruebas antes: {result['pruebas_iniciales']['codigo_salida']}")
    print(f"Pruebas después: {result['pruebas_posteriores']['codigo_salida']}")
    print(f"Registro: {run_dir if run_dir is not None else 'no creado'}")
    for error in result["errores_controlador"]:
        print(f"Error del controlador: {error}", file=sys.stderr)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("caso", choices=("case_02",))
    args = parser.parse_args(argv)
    return repair_case(args.caso, Path(__file__).resolve().parent)


if __name__ == "__main__":
    sys.exit(main())

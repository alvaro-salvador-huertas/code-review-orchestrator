"""Única frontera de ejecución del recorrido nuevo de proyectos Python.

No hay fallback al anfitrión. Preparar la imagen es una operación explícita.
Los comandos lógicos y sus rutas se conservan para los validadores históricos.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

from process_environment import process_environment
from repair_case import ProcessInterrupted, ProcessRecordError, timestamp, write_json

# Docker Official Image python:3.12.16-bookworm; incluye Git (índice OCI multiarch).
IMAGE = "docker.io/library/python@sha256:4209fae09a3e20afd863e528bfddc235da5fd5977983e1996cd54cc9a72e6267"
PYTHON = "/usr/local/bin/python3"
MEMORY = 512 * 1024 * 1024
PIDS = 128

# Se ejecuta con -I antes de importar cualquier material montado. Verificar los
# límites efectivos evita aceptar un runtime que los ignore con una advertencia.
BOOTSTRAP = r'''
import json, os, pathlib, sys
try:
    assert os.getuid() != 0, 'UID del contenedor debe ser no privilegiado'
    status = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert status['NoNewPrivs'].strip() == '1', 'no-new-privileges ausente'
    assert int(status['CapEff'].strip(), 16) == 0, 'capacidades efectivas presentes'
    assert status['Seccomp'].strip() == '2', 'seccomp ausente'
    assert set(os.listdir('/sys/class/net')) <= {'lo'}, 'interfaz de red externa presente'
    group = pathlib.Path('/sys/fs/cgroup')
    relative = pathlib.Path('/proc/self/cgroup').read_text().strip().split('0::', 1)[1].strip()
    if relative != '/':
        group = group / relative.lstrip('/')
    memory = (group / 'memory.max').read_text().strip()
    pids = (group / 'pids.max').read_text().strip()
    swap = (group / 'memory.swap.max').read_text().strip()
    assert memory != 'max' and 0 < int(memory) <= 536870912, 'memory.max no aplicado'
    assert pids != 'max' and 0 < int(pids) <= 128, 'pids.max no aplicado'
    assert swap == '0', 'swap no limitado'
except BaseException as exc:
    print('Aislamiento no disponible: ' + str(exc), file=sys.stderr, flush=True)
    sys.exit(125)
command = json.loads(sys.argv[1])
if command:
    # No heredar ni siquiera variables adicionales de la imagen.
    environment = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':'/tmp/home',
        'TMPDIR':'/tmp', 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8', 'TZ':'UTC',
        'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONNOUSERSITE':'1', 'PYTHONUTF8':'1',
        'PYTHONIOENCODING':'utf-8'}
    pathlib.Path('/tmp/home').mkdir(exist_ok=True)
    os.execve('/usr/local/bin/python3', ['/usr/local/bin/python3', *command[1:]], environment)
'''


def runtime_call(arguments, *, timeout=15):
    with process_environment("podman") as environment:
        return subprocess.run(["podman", "--remote=false", *arguments], env=environment,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)


def require_runtime():
    if os.geteuid() == 0:
        raise RuntimeError("Se requiere Podman rootless; no ejecutar como root")
    info = runtime_call(["info", "--format", "json"])
    if info.returncode:
        raise RuntimeError("Podman rootless no disponible: " + info.stderr.strip())
    try:
        host = json.loads(info.stdout)["host"]
        supported = host["security"]["rootless"] is True and host["cgroupVersion"] == "v2"
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Informe de capacidades de Podman inválido") from exc
    if not supported:
        raise RuntimeError("Se requiere Podman rootless con cgroups v2")
    available = runtime_call(["image", "exists", IMAGE])
    if available.returncode == 1:
        raise RuntimeError("Imagen Python fijada ausente; ejecutar python_evaluator.py prepare por separado")
    if available.returncode:
        raise RuntimeError("No se pudo comprobar la imagen local: " + available.stderr.strip())


def container_command(name, command, workspace, mounts):
    args = ["podman", "--remote=false", "run", "--name", name, "--pull=never",
            "--network=none", "--userns=keep-id", "--user", f"{os.getuid()}:{os.getgid()}",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--read-only",
            "--read-only-tmpfs=false", "--tmpfs=/tmp:rw,nosuid,nodev,size=128m,mode=1777",
            "--memory=512m", "--memory-swap=512m", "--pids-limit=128", "--cpus=1",
            "--pid=private", "--ipc=private", "--uts=private", "--cgroupns=private",
            "--http-proxy=false", "--image-volume=ignore", "--no-hosts",
            "--log-driver=none", "--workdir", str(workspace), "--entrypoint", PYTHON]
    for source, target, writable in mounts:
        # --mount no interpreta ':'; rechazar comas que alterarían sus opciones.
        if any(',' in str(p) for p in (source, target)):
            raise ValueError("Coma no admitida en rutas de montaje")
        args += ["--mount", f"type=bind,src={source},dst={target},ro={'false' if writable else 'true'}"]
    return [*args, IMAGE, "-I", "-B", "-c", BOOTSTRAP, json.dumps(command)]


def cleanup(name):
    removed = runtime_call(["rm", "--force", "--time=0", "--ignore", name])
    exists = runtime_call(["container", "exists", name])
    if removed.returncode or exists.returncode != 1:
        raise RuntimeError("No se pudo confirmar la limpieza de " + name + ": " + removed.stderr.strip())


def collect_output(source, destination):
    # El proyecto puede escribir salida hostil: nunca seguir enlaces ni especiales.
    for path in sorted(source.rglob('*')):
        if path.relative_to(source).parts[0] not in ("pruebas.json", "pruebas.tmp", "consultas"):
            raise ValueError("Salida no declarada del evaluador: " + str(path))
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Salida del evaluador no regular: " + str(path))
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(exist_ok=True)
        else:
            shutil.copyfile(path, target)


def run_isolated(command, workspace, log, timeout, *, materials, runner):
    """Registrar el comando lógico, el comando Podman y la limpieza confirmada."""
    log.mkdir(exist_ok=True)
    started = time.monotonic()
    name = "cro-eval-" + uuid4().hex
    result = {"comando": command, "directorio_trabajo": str(workspace),
              "inicio_utc": timestamp(), "limite_segundos": timeout, "politica_entorno": "evaluation",
              "estado": "error_inicio", "codigo_salida": None, "error": None}
    isolation = result["aislamiento"] = {"version": 1, "runtime": "podman-rootless", "imagen": IMAGE,
                                         "contenedor": name, "limpieza_confirmada": False}
    pending = None
    attempted = False
    try:
        require_runtime()
        with tempfile.TemporaryDirectory(prefix="salida-evaluador-") as temporary:
            output = Path(temporary)
            isolation["salida_temporal"] = str(output)
            mounts = [(Path(workspace).resolve(), Path(workspace).absolute(), False),
                      *((Path(p).resolve(), Path(p).absolute(), False) for p in materials),
                      (output, log.absolute(), True)]
            actual = container_command(name, command, workspace, mounts)
            isolation["comando_runtime"] = actual
            attempted = True
            try:
                executed = runner(actual, workspace, log, timeout, env_policy="podman")
            except (ProcessInterrupted, ProcessRecordError) as exc:
                executed = exc.result
                pending = exc
            result.update({k: v for k, v in executed.items()
                           if k not in ("comando", "directorio_trabajo", "politica_entorno", "inicio_utc")})
            if result["codigo_salida"] in (125, 126, 127):
                result.update(estado="error_inicio", error="El contenedor no pudo iniciar con el aislamiento exigido; ver stderr.txt")
            if result["estado"] == "tiempo_agotado":
                result["error"] = f"La evaluación aislada agotó su límite de {timeout} segundos; contenedor {name}"
                with (log / "stderr.txt").open("a") as stream:
                    stream.write(result["error"] + "\n")
            # Matar el contenedor también si el cliente Podman murió o fue interrumpido.
            cleanup(name)
            isolation["limpieza_confirmada"] = True
            attempted = False
            try:
                collect_output(output, log)
            except ValueError as exc:
                if result["estado"] != "tiempo_agotado":
                    raise
                result["error_salida"] = str(exc)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        result.update(estado="error_inicio", error="Aislamiento no disponible: " + str(exc))
        with (log / "stderr.txt").open("a") as stream:
            stream.write(result["error"] + "\n")
    finally:
        if attempted:
            try:
                cleanup(name)
                isolation["limpieza_confirmada"] = True
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                result.update(estado="error_inicio", error="Limpieza del contenedor fallida: " + str(exc))
        for channel in ("stdout.txt", "stderr.txt"):
            (log / channel).touch(exist_ok=True)
        result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic() - started)
        write_json(log / "resultado.json", result)
    if pending is not None:
        pending.result = result
        raise pending
    return result


def validate_isolation(process, *, materials, log):
    from case_evidence import require
    stamp = process["aislamiento"]
    require(stamp["version"] == 1 and stamp["runtime"] == "podman-rootless"
            and stamp["imagen"] == IMAGE and stamp["limpieza_confirmada"] is True,
            "Evidencia de aislamiento inválida")
    workspace = Path(process["directorio_trabajo"])
    output = Path(stamp["salida_temporal"])
    require(output.is_absolute() and stamp["contenedor"].startswith("cro-eval-"),
            "Identidad del contenedor inválida")
    mounts = [(workspace, workspace, False), *((Path(p), Path(p), False) for p in materials),
              (output, Path(log), True)]
    expected = container_command(stamp["contenedor"], process["comando"], workspace, mounts)
    # La identidad numérica puede variar al revisar en otra cuenta.
    actual = stamp["comando_runtime"]
    index = expected.index("--user") + 1
    require(isinstance(actual, list) and len(actual) == len(expected), "Comando Podman incompleto")
    user = actual[index]
    require(isinstance(user, str) and len(user.split(':')) == 2
            and all(x.isdigit() for x in user.split(':')) and int(user.split(':')[0]) > 0,
            "UID del evaluador inválido")
    expected[index] = user
    require(actual == expected, "Controles o montajes de aislamiento distintos")


def check_isolated_process(process):
    from repair_project import StopProject, check_process
    if process["estado"] == "error_inicio" and process.get("error"):
        raise StopProject(3, "fallo_tecnico", process["error"])
    check_process(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check"))
    args = parser.parse_args()
    if args.action == "prepare":
        if os.geteuid() == 0:
            parser.error("Preparar como el usuario rootless que ejecutará el controlador")
        try:
            pulled = runtime_call(["pull", IMAGE], timeout=300)
        except (OSError, subprocess.SubprocessError) as exc:
            parser.exit(1, f"No se pudo preparar Podman rootless: {exc}\n")
        print(pulled.stdout, end="")
        if pulled.returncode:
            parser.exit(1, pulled.stderr)
    else:
        from repair_case import run_process
        with tempfile.TemporaryDirectory(prefix="comprobar-evaluador-") as temporary:
            root = Path(temporary)
            # La sonda usa exactamente el mismo bootstrap y límites, sin proyecto.
            result = run_isolated([], root, root / "log", 30, materials=(), runner=run_process)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result["estado"] != "finalizada" or result["codigo_salida"] != 0:
                parser.exit(1, (root / "log/stderr.txt").read_text())


if __name__ == "__main__":
    main()

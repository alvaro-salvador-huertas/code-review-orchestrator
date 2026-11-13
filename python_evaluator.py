"""Única frontera de ejecución del recorrido nuevo de proyectos Python.

No hay fallback al anfitrión. Preparar la imagen es una operación explícita.
Los comandos lógicos y sus rutas se conservan para los validadores históricos.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from process_environment import process_environment
from repair_case import ProcessInterrupted, ProcessRecordError, timestamp, write_json
from bounded_output import output_limits as normalize_limits, collect_output, append_diagnostic

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
    quota, period = (group / 'cpu.max').read_text().split()
    assert memory != 'max' and 0 < int(memory) <= 536870912, 'memory.max no aplicado'
    assert pids != 'max' and 0 < int(pids) <= 128, 'pids.max no aplicado'
    assert swap == '0', 'swap no limitado'
    assert quota != 'max', 'cpu.max sin cuota finita'
    assert 0 < int(quota) <= int(period), 'cpu.max debe limitar a una CPU como máximo'
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


def container_command(name, command, workspace, mounts, *, result_volume=None, result_target=None):
    args = ["podman", "--remote=false", "--default-mounts-file=/dev/null",
            "run", "--name", name, "--pull=never",
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
    if result_volume is not None:
        if ',' in str(result_target):
            raise ValueError('Coma no admitida en el montaje de resultados')
        if ':' in str(result_target):
            raise ValueError('Dos puntos no admitidos en el montaje de resultados')
        args += ['--volume', f'{result_volume}:{result_target}:nocopy']
    return [*args, IMAGE, "-I", "-B", "-c", BOOTSTRAP, json.dumps(command)]


def cleanup(name):
    removed = runtime_call(["rm", "--force", "--time=0", "--ignore", name])
    exists = runtime_call(["container", "exists", name])
    if removed.returncode or exists.returncode != 1:
        raise RuntimeError("No se pudo confirmar la limpieza de " + name + ": " + removed.stderr.strip())


def volume_call(arguments):
    result = runtime_call(arguments)
    if result.returncode:
        raise RuntimeError('Cuota de resultados no disponible: ' + result.stderr.strip()[:1024])
    return result.stdout.strip()


def prepare_result_volume(name, limits):
    volume_call(['volume', 'create', '--opt', 'device=tmpfs', '--opt', 'type=tmpfs',
                 '--opt', f"o=size={limits['resultados']},nr_inodes={limits['inodos']},nodev,nosuid,mode=0700", name])
    # Mantener una referencia explícita: el tmpfs debe sobrevivir al contenedor
    # hasta terminar su recogida. Ninguna ruta de disco se ofrece de alternativa.
    path = volume_call(['unshare', 'podman', 'volume', 'mount', name])
    usage = result_volume_usage(path, limits)
    if usage['excedido']:
        raise RuntimeError('Volumen de resultados ya saturado')
    return path


def result_helper(action, path, limits, *extra):
    return ['unshare', str(Path(sys.executable).resolve()), '-I', '-B',
            str(Path(__file__).with_name('bounded_output.py')), action, path,
            json.dumps(limits, sort_keys=True), *map(str, extra)]


def result_volume_usage(path, limits):
    return json.loads(volume_call(result_helper('inspect', path, limits)))


def collect_result_volume(path, log, limits):
    volume_call(result_helper('collect', path, limits, log))


def cleanup_result_volume(name):
    """Intentar todas las operaciones por nombre, sin forzar contenedores.

    Los fallos de comandos y la ausencia del recurso son hechos distintos:
    una retirada puede confirmar ausencia aunque el desmontaje haya fallado.
    """
    report = {'estado_inicial':'desconocido', 'estado_final':'desconocido',
              'ausente_confirmado':False, 'errores':[]}

    def call(arguments, operation):
        try:
            return runtime_call(arguments)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            report['errores'].append({'operacion':operation, 'error':str(exc)[:1024]})
            return None

    def existence(operation):
        checked = call(['volume', 'exists', name], operation)
        if checked is None:
            return 'desconocido'
        if checked.returncode == 1:
            return 'ausente'
        if checked.returncode == 0:
            return 'presente'
        report['errores'].append({'operacion':operation,
            'error':checked.stderr.strip()[:1024] or 'No se pudo comprobar la existencia del volumen'})
        return 'desconocido'

    report['estado_inicial'] = existence('comprobar_antes')
    if report['estado_inicial'] == 'ausente':
        report.update(estado_final='ausente', ausente_confirmado=True)
        return report  # Incluye la preparación que falló antes de crear el volumen.
    for operation, command in (
        ('desmontar', ['unshare', 'podman', 'volume', 'unmount', name]),
        ('retirar', ['volume', 'rm', name]),
    ):
        completed = call(command, operation)
        if completed is not None and completed.returncode:
            report['errores'].append({'operacion':operation,
                'error':completed.stderr.strip()[:1024] or f'Operación fallida: {operation}'})
    report['estado_final'] = existence('comprobar_despues')
    report['ausente_confirmado'] = report['estado_final'] == 'ausente'
    if report['estado_final'] == 'presente':
        report['errores'].append({'operacion':'comprobar_despues',
                                 'error':'El volumen sigue presente: ' + name})
    return report


def run_isolated(command, workspace, log, timeout, *, materials, runner, output_limits=None):
    """Cuotas durante la escritura; no hay bind de salida al disco del anfitrión."""
    limits = normalize_limits(output_limits)
    log.mkdir(exist_ok=True)
    started = time.monotonic()
    name = 'cro-eval-' + uuid4().hex
    volume = name + '-results'
    result = {'comando':command, 'directorio_trabajo':str(workspace),
              'inicio_utc':timestamp(), 'limite_segundos':timeout, 'politica_entorno':'evaluation',
              'estado':'error_inicio', 'codigo_salida':None, 'error':None}
    isolation = result['aislamiento'] = {'version':2, 'runtime':'podman-rootless', 'imagen':IMAGE,
        'contenedor':name, 'volumen_resultados':volume, 'limites_salida':limits, 'limpieza_confirmada':False}
    pending = None
    attempted = volume_attempted = False
    phase = 'preparacion'

    def failure(message, bucket, **details):
        # Mantener el primer diagnóstico y el estado de fallo existente (por
        # ejemplo timeout o cuota). Los fallos posteriores se anotan aparte.
        message = message[:1024]
        result.setdefault(bucket, []).append({**details, 'error':message})
        if not result['error']:
            result['error'] = message
        if result['estado'] == 'finalizada':
            result['estado'] = 'error_inicio'

    def retire_container():
        nonlocal attempted
        try:
            cleanup(name)
            attempted = False
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failure('Limpieza del contenedor fallida: ' + str(exc), 'errores_limpieza',
                    recurso='contenedor', operacion='retirar')
        return not attempted

    try:
        require_runtime()
        volume_attempted = True
        path = prepare_result_volume(volume, limits)
        mounts = [(Path(workspace).resolve(), Path(workspace).absolute(), False),
                  *((Path(p).resolve(), Path(p).absolute(), False) for p in materials)]
        actual = container_command(name, command, workspace, mounts,
                                   result_volume=volume, result_target=log.absolute())
        isolation['comando_runtime'] = actual
        attempted = True
        phase = 'ejecucion'
        try:
            executed = runner(actual, workspace, log, timeout, env_policy='podman',
                output_limits=limits, monitor_command=['podman', '--remote=false',
                    *result_helper('monitor', path, limits)])
        except (ProcessInterrupted, ProcessRecordError) as exc:
            executed, pending = exc.result, exc
        result.update({k:v for k,v in executed.items()
                       if k not in ('comando','directorio_trabajo','politica_entorno','inicio_utc')})
        if result['estado'] == 'finalizada' and result['codigo_salida'] in (125,126,127):
            result.update(estado='error_inicio', error='El contenedor no pudo iniciar con el aislamiento exigido; ver stderr.txt')
        if result['estado'] == 'tiempo_agotado':
            result['error'] = f'La evaluación aislada agotó su límite de {timeout} segundos; contenedor {name}'
        if retire_container():
            # El kernel ya limitó cada escritura en el tmpfs; esta comprobación
            # final cierra la carrera entre el último sondeo y la salida del hijo.
            phase = 'comprobar_resultados'
            usage = result_volume_usage(path, limits)
            result['uso_resultados'] = usage
            if usage['excedido'] and result['estado'] != 'tiempo_agotado':
                if not result['error']:
                    result.update(estado='limite_salida', salida_excedida='resultados',
                                  error='Límite de resultados alcanzado')
            if result['estado'] == 'finalizada':
                phase = 'recogida'
                collect_result_volume(path, log, limits)
    except KeyboardInterrupt as exc:
        result['estado'] = 'interrumpida'
        failure(str(exc) or 'Evaluación interrumpida', 'errores_operacion', fase=phase)
        pending = ProcessInterrupted(result)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        if phase == 'recogida':
            failure('Recogida de resultados fallida: ' + str(exc), 'errores_recogida', fase=phase)
        else:
            failure('Aislamiento no disponible: ' + str(exc), 'errores_operacion', fase=phase)
    finally:
        container_clean = retire_container() if attempted else True
        volume_clean = not volume_attempted
        if volume_attempted and container_clean:
            try:
                report = cleanup_result_volume(volume)
                isolation['limpieza_volumen'] = report
                volume_clean = report['ausente_confirmado'] is True
                for error in report['errores']:
                    failure('Limpieza del volumen fallida: ' + error['error'], 'errores_limpieza',
                            recurso='volumen', operacion=error['operacion'])
                if not volume_clean and not report['errores']:
                    failure('No se pudo confirmar la ausencia del volumen', 'errores_limpieza',
                            recurso='volumen', operacion='comprobar_despues')
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                failure('Limpieza del volumen fallida: ' + str(exc), 'errores_limpieza',
                        recurso='volumen', operacion='retirar')
        isolation['limpieza_confirmada'] = container_clean and volume_clean
        for channel in ('stdout.txt','stderr.txt'):
            try:
                (log/channel).touch(exist_ok=True)
            except OSError as exc:
                failure('Registro del canal fallido: ' + str(exc), 'errores_limpieza',
                        recurso=channel, operacion='registrar')
        # Un fallo de retirada no puede impedir que se guarde resultado.json.
        # No seguir ni retirar recursivamente directorios con nombres de informe.
        if result['estado'] != 'finalizada':
            for name_report in ('pruebas.json', 'pruebas.tmp'):
                try:
                    (log/name_report).unlink(missing_ok=True)
                except OSError as exc:
                    failure('Retirada del informe parcial fallida: ' + str(exc), 'errores_limpieza',
                            recurso=name_report, operacion='retirar_parcial')
        if result['error']:
            try:
                append_diagnostic(log, result['error'], limits)
            except OSError as exc:
                failure('Registro del diagnóstico fallido: ' + str(exc), 'errores_limpieza',
                        recurso='stderr.txt', operacion='registrar')
        result.update(fin_utc=timestamp(), duracion_segundos=time.monotonic()-started)
        write_json(log/'resultado.json', result)
    if pending is not None:
        pending.result = result
        raise pending
    return result


def validate_isolation(process, *, materials, log, output_limits=None):
    from case_evidence import require
    stamp = process["aislamiento"]
    require(stamp["version"] == 2 and stamp["runtime"] == "podman-rootless"
            and stamp["imagen"] == IMAGE and stamp["limpieza_confirmada"] is True,
            "Evidencia de aislamiento inválida")
    workspace = Path(process["directorio_trabajo"])
    limits = normalize_limits(output_limits)
    require(stamp["limites_salida"] == limits
            and stamp["volumen_resultados"] == stamp["contenedor"] + "-results"
            and stamp["contenedor"].startswith("cro-eval-"),
            "Identidad del contenedor inválida")
    mounts = [(workspace, workspace, False), *((Path(p), Path(p), False) for p in materials)]
    expected = container_command(stamp["contenedor"], process["comando"], workspace, mounts,
        result_volume=stamp["volumen_resultados"], result_target=Path(log))
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
    if process["estado"] == "limite_salida":
        raise StopProject(3, "fallo_tecnico", process["error"])
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

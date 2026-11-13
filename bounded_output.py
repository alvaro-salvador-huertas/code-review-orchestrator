"""Cuotas de salida: capturador por pipes y helper de tmpfs rootless (solo stdlib)."""

import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time


DEFAULT_LIMITS = {'resultados': 32 * 1024 * 1024, 'stdout': 4 * 1024 * 1024,
                  'stderr': 4 * 1024 * 1024, 'inodos': 1024}


def output_limits(limits=None):
    result = dict(DEFAULT_LIMITS if limits is None else limits)
    if set(result) != set(DEFAULT_LIMITS) or any(type(n) is not int or n <= 0 for n in result.values()):
        raise ValueError('Límites de salida inválidos')
    if result['resultados'] % 4096 or result['inodos'] < 16:
        raise ValueError('Resultados requiere múltiplos de 4096 bytes y al menos 16 inodos')
    return result


def filesystem_usage(source, limits):
    """El límite de bloques/inodos lo impone el kernel, no este sondeo."""
    source = Path(source)
    fs = os.statvfs(source)
    capacity = fs.f_blocks * fs.f_frsize
    if not 0 < capacity <= limits['resultados'] or not 0 < fs.f_files <= limits['inodos']:
        raise RuntimeError('El filesystem no aplica los límites de resultados/inodos')
    # Verificar el montaje exacto: nunca aceptar un directorio de disco ordinario.
    escaped = str(source).replace('\\', '\\134').replace(' ', '\\040').replace('\t', '\\011').replace('\n', '\\012')
    entries = Path('/proc/self/mountinfo').read_text().splitlines()
    if not any(line.split()[4] == escaped
               and line.split(' - ', 1)[1].split()[0] == 'tmpfs' for line in entries):
        raise RuntimeError('Los resultados requieren un montaje tmpfs privado')
    used = (fs.f_blocks - fs.f_bfree) * fs.f_frsize
    logical, count = 0, 1
    for parent, directories, files, directory_fd in os.fwalk(source, follow_symlinks=False):
        for name in directories + files:
            try:
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:  # Un rename atómico del informe durante el sondeo.
                continue
            count += 1
            if stat.S_ISREG(info.st_mode):
                logical += info.st_size
            if count > limits['inodos'] or logical > limits['resultados']:
                break
        if count > limits['inodos'] or logical > limits['resultados']:
            break
    full = (used >= limits['resultados'] or fs.f_favail == 0 or logical > limits['resultados']
            or count > limits['inodos'])
    return {'bytes_asignados': used, 'bytes_logicos': logical, 'inodos': count,
            'capacidad_bytes': capacity, 'capacidad_inodos': fs.f_files, 'excedido': full}


def collect_output(source, destination, limits=None):
    """Copiar solo archivos regulares, con presupuesto agregado durante la copia."""
    limits = output_limits(limits)
    source, destination = Path(source), Path(destination)
    remaining, count = limits['resultados'], 0
    for path in sorted(source.rglob('*')):
        count += 1
        if count >= limits['inodos']:
            raise ValueError('Límite de inodos de resultados excedido')
        if path.relative_to(source).parts[0] not in ('pruebas.json', 'pruebas.tmp', 'consultas'):
            raise ValueError('Salida no declarada del evaluador')
        info = path.lstat()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('Salida del evaluador no regular')
        target = destination/path.relative_to(source)
        if stat.S_ISDIR(info.st_mode):
            target.mkdir(exist_ok=True)
        else:
            if info.st_size > remaining:
                raise ValueError('Límite agregado de resultados excedido')
            with path.open('rb') as incoming, target.open('xb') as outgoing:
                while True:
                    data = incoming.read(min(65536, remaining + 1))
                    if not data:
                        break
                    if len(data) > remaining:
                        raise ValueError('Límite agregado de resultados excedido')
                    outgoing.write(data)
                    remaining -= len(data)
    return limits['resultados'] - remaining


def append_diagnostic(log, message, limits):
    """El diagnóstico nunca permite saltarse el límite de stderr."""
    path = Path(log)/'stderr.txt'
    remaining = max(0, limits['stderr'] - (path.stat().st_size if path.exists() else 0))
    with path.open('ab') as stream:
        stream.write((message + '\n').encode('utf-8')[:remaining])


def stop(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)


def run_bounded(command, workspace, log, timeout, *, limits, monitor_command, env_policy):
    """Ningún byte del hijo se escribe en disco sin pasar por el presupuesto."""
    from process_environment import process_environment
    from repair_case import ProcessInterrupted, timestamp, write_json
    log = Path(log)
    log.mkdir(exist_ok=True)
    started = time.monotonic()
    record = {'comando':command, 'directorio_trabajo':str(workspace), 'inicio_utc':timestamp(),
              'limite_segundos':timeout, 'politica_entorno':env_policy, 'estado':'error_inicio',
              'codigo_salida':None, 'error':None, 'bytes_capturados':{'stdout':0, 'stderr':0}}
    interrupted = False
    process = monitor = None
    try:
        with process_environment(env_policy) as env, selectors.DefaultSelector() as selector, \
             (log/'stdout.txt').open('wb') as stdout, (log/'stderr.txt').open('wb') as stderr:
            if monitor_command:
                monitor = subprocess.Popen(monitor_command, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
                selector.register(monitor.stdout, selectors.EVENT_READ, 'resultados')
            process = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            for stream, name in ((process.stdout,'stdout'), (process.stderr,'stderr')):
                selector.register(stream, selectors.EVENT_READ, name)
            record['estado'] = 'finalizada'
            channels = {'stdout':stdout, 'stderr':stderr}
            open_channels = 2
            while open_channels or process.poll() is None:
                if time.monotonic() - started >= timeout:
                    record['estado'] = 'tiempo_agotado'
                    break
                for key, _ in selector.select(min(.05, max(0, timeout - (time.monotonic()-started)))):
                    data = os.read(key.fd, 65536)
                    name = key.data
                    if name == 'resultados':
                        # Solo el helper de confianza escribe aquí. Su salida o
                        # su muerte inesperada detienen la ejecución cerradamente.
                        record.update(estado='limite_salida' if data.startswith(b'FULL') else 'error_inicio',
                                      salida_excedida='resultados' if data.startswith(b'FULL') else None,
                                      error='Límite de resultados alcanzado' if data.startswith(b'FULL')
                                            else 'Monitor de resultados no disponible')
                        break
                    if not data:
                        selector.unregister(key.fileobj)
                        open_channels -= 1
                        continue
                    remaining = limits[name] - record['bytes_capturados'][name]
                    accepted = data[:remaining]
                    channels[name].write(accepted)
                    record['bytes_capturados'][name] += len(accepted)
                    if len(data) > remaining:
                        record.update(estado='limite_salida', salida_excedida=name,
                                      error=f'Límite de {name} excedido: {limits[name]} bytes')
                        break
                if record['estado'] != 'finalizada':
                    break
    except KeyboardInterrupt:
        record['estado'] = 'interrumpida'
        interrupted = True
    except OSError as exc:
        record.update(estado='error_inicio', error=str(exc)[:1024])
    finally:
        for child in (process, monitor):
            if child is not None:
                stop(child)
                for stream in (child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
        if process is not None:
            record['codigo_salida'] = process.returncode
        record.update(fin_utc=timestamp(), duracion_segundos=time.monotonic()-started)
        write_json(log/'resultado.json', record)
    if interrupted:
        raise ProcessInterrupted(record)
    return record


def main():
    action, source, raw = sys.argv[1:4]
    limits = output_limits(json.loads(raw))
    if action == 'inspect':
        print(json.dumps(filesystem_usage(source, limits)))
    elif action == 'monitor':
        try:
            while True:
                if filesystem_usage(source, limits)['excedido']:
                    print('FULL', flush=True)
                    return
                time.sleep(.02)
        except BaseException:
            print('ERROR', flush=True)
            raise
    elif action == 'collect':
        print(json.dumps({'bytes_copiados':collect_output(source, sys.argv[4], limits)}))
    else:
        raise ValueError('Acción de cuota desconocida')


if __name__ == '__main__':
    main()

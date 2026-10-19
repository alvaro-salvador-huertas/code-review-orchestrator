"""Inventario por descubrimiento en un hijo, exclusivamente de una base fiable.

El llamante debe aportar una copia protegida de la referencia anterior al
trabajo del agente, nunca su workspace candidato. Descubrir importa módulos y
puede ejecutar su inicialización: esto no es análisis estático ni un sandbox.
No ejecuta métodos de prueba. No está integrado en los validadores históricos.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from process_environment import process_environment


# Solo biblioteca estándar en el hijo. No carga el controlador ni sus módulos:
# las importaciones del proyecto se resuelven desde la referencia (cwd).
DISCOVER = r'''
import json
from pathlib import Path
import sys
import traceback
import unittest
from unittest.loader import _FailedTest

report_path = Path(sys.argv[1])
report = {"identidades": [], "errores": [], "python": sys.version}
try:
    loader = unittest.TestLoader()
    suite = loader.discover(str(Path.cwd() / "tests"), pattern="test*.py")
    if loader.errors:
        raise ValueError("Errores de descubrimiento/importación:\n" + "\n".join(loader.errors))

    def identities(node):
        if isinstance(node, unittest.TestSuite):
            for child in node:
                yield from identities(child)
        else:
            if isinstance(node, _FailedTest):
                raise ValueError("Prueba sintética de error de unittest")
            if not isinstance(node, unittest.TestCase):
                raise ValueError("Elemento ajeno a TestCase en la suite")
            yield node.id()

    found = list(identities(suite))
    if not found:
        raise ValueError("Suite vacía")
    if any(not isinstance(name, str) or not name.strip() for name in found):
        raise ValueError("Identidad inválida")
    if len(found) != len(set(found)):
        raise ValueError("Identidades duplicadas")
    report["identidades"] = sorted(found)
except BaseException:
    # Incluye SystemExit durante la inicialización; nunca es éxito parcial.
    report["errores"].append(traceback.format_exc())
report_path.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
sys.exit(1 if report["errores"] else 0)
'''


def snapshot(reference):
    """Contenido, entradas, modos y mtime; rechaza enlaces, cachés y especiales."""
    state = {}

    def visit(path):
        info = path.lstat()
        name = path.relative_to(reference).as_posix()
        if path.name == "__pycache__" or path.suffix in (".pyc", ".pyo"):
            raise ValueError(f"Caché Python en la referencia: {name}")
        if stat.S_ISDIR(info.st_mode):
            digest = None
        elif stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise ValueError(f"Enlace o archivo especial en la referencia: {name}")
        state[name] = (info.st_mode, info.st_mtime_ns, digest)
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)

    visit(reference)
    return state


def state_hash(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def inventory_tests(protected_reference, *, interpreter=None, timeout=30):
    """Informe completo/error; el controlador no importa el proyecto inventariado.

    No deduce una referencia del cwd ni acepta resultados parciales. La futura
    integración debe congelar versión, informe y procedencia de esta base.
    """
    reference = Path(protected_reference).absolute()
    executable = Path(interpreter) if interpreter is not None else Path(sys.executable).resolve()
    valid_timeout = (isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
                     and math.isfinite(timeout) and timeout > 0)
    report = {
        "version": 1, "estado": "error", "identidades": [], "total": 0, "errores": [],
        "referencia": str(reference), "conservada": None,
        "arbol_antes_sha256": None, "arbol_despues_sha256": None,
        "utilidad_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "entorno_sha256": hashlib.sha256(Path(__file__).with_name("process_environment.py").read_bytes()).hexdigest(),
        "interprete": str(executable), "python": None, "politica_entorno": "evaluation",
        "timeout_segundos": timeout if valid_timeout else None,
        "codigo_hijo": None, "stdout_hijo": "", "stderr_hijo": "",
    }
    before = None
    found = []
    try:
        if not executable.is_absolute():
            raise ValueError("El intérprete debe ser absoluto")
        if not valid_timeout:
            raise ValueError("El timeout debe ser finito y positivo")
        if not reference.is_dir():
            raise ValueError("La referencia debe ser un directorio")
        before = snapshot(reference)
        report["arbol_antes_sha256"] = state_hash(before)
        with tempfile.TemporaryDirectory(prefix="inventario-pruebas-") as temporary:
            output = Path(temporary) / "descubrimiento.json"
            with process_environment("evaluation") as environment:
                completed = subprocess.run(
                    [str(executable), "-B", "-c", DISCOVER, str(output)],
                    cwd=reference, env=environment, stdin=subprocess.DEVNULL,
                    capture_output=True, timeout=timeout, shell=False,
                )
            report["codigo_hijo"] = completed.returncode
            report["stdout_hijo"] = completed.stdout.decode("utf-8", errors="replace")
            report["stderr_hijo"] = completed.stderr.decode("utf-8", errors="replace")
            child = json.loads(output.read_text(encoding="utf-8"))
            if (not isinstance(child, dict) or set(child) != {"identidades", "errores", "python"}
                    or not isinstance(child["identidades"], list)
                    or not isinstance(child["errores"], list)
                    or not isinstance(child["python"], str)
                    or any(not isinstance(item, str) or not item.strip()
                           for item in child["identidades"] + child["errores"])):
                raise ValueError("Informe de descubrimiento inválido")
            report["python"] = child["python"]
            report["errores"].extend(child["errores"])
            found = child["identidades"]
            if completed.returncode != 0:
                raise ValueError(f"El hijo terminó con código {completed.returncode}")
            if not found or len(found) != len(set(found)):
                raise ValueError("Inventario vacío o con identidades duplicadas")
    except subprocess.TimeoutExpired:
        report["errores"].append(f"El descubrimiento excedió {timeout} segundos")
    except Exception as exc:
        report["errores"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if before is not None:
            try:
                after = snapshot(reference)
                report["arbol_despues_sha256"] = state_hash(after)
                report["conservada"] = before == after
                if not report["conservada"]:
                    report["errores"].append("El descubrimiento alteró la copia protegida")
            except Exception as exc:
                report["conservada"] = False
                report["errores"].append(f"No se pudo comprobar la conservación: {exc}")
    if not report["errores"] and report["conservada"] is True:
        report.update(estado="completado", identidades=sorted(found), total=len(found))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True,
                        help="Copia protegida de la base de confianza anterior al agente; nunca el candidato")
    parser.add_argument("--python", type=Path, default=Path(sys.executable).resolve())
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    report = inventory_tests(args.reference, interpreter=args.python, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0 if report["estado"] == "completado" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Entornos explícitos de hijos; no es un sandbox ni modifica os.environ."""

from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile


# Solo Windows necesita estas rutas del sistema para crear procesos.
SYSTEM_VARIABLES = ("SystemRoot", "WINDIR") if os.name == "nt" else ()
# Lista cerrada: localizar la CLI/configuración y autenticar Codex, no otros servicios.
CODEX_VARIABLES = (
    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "CODEX_HOME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "TMPDIR", "TMP", "TEMP",
    "OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID",
)


def base_environment():
    """Valores del controlador, salvo las rutas de sistema imprescindibles."""
    return {
        **{name: os.environ[name] for name in SYSTEM_VARIABLES if name in os.environ},
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
    }


@contextmanager
def process_environment(policy="evaluation"):
    """Cada evaluación dispone de HOME/configuración/tmp nuevos y luego eliminados.

    Codex conserva solo su lista permitida. Ni nombres ni valores de variables
    se incorporan a los registros. Los hijos normales heredan el entorno reducido.
    """
    if policy not in ("evaluation", "codex"):
        raise ValueError("Política de entorno desconocida")
    environment = base_environment()
    if policy == "codex":
        environment.update({name: os.environ[name] for name in CODEX_VARIABLES if name in os.environ})
        yield environment
        return
    with tempfile.TemporaryDirectory(prefix="evaluacion-entorno-") as temporary:
        root = Path(temporary)
        for directory, names in (
            ("home", ("HOME", "USERPROFILE")),
            ("config", ("XDG_CONFIG_HOME", "APPDATA")),
            ("data", ("XDG_DATA_HOME",)),
            ("cache", ("XDG_CACHE_HOME", "LOCALAPPDATA")),
            ("state", ("XDG_STATE_HOME",)),
            ("runtime", ("XDG_RUNTIME_DIR",)),
            ("tmp", ("TMPDIR", "TMP", "TEMP")),
        ):
            path = root / directory
            path.mkdir(mode=0o700)
            environment.update(dict.fromkeys(names, str(path)))
        # También se utiliza para consultas Git del controlador, sin configuración personal.
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_TERMINAL_PROMPT="0")
        yield environment

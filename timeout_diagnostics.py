"""Observaciones de un timeout, sin inferir su causa ni conservar eventos."""

import json
import os
import stat
import time


JSONL_TAIL_BYTES = 64 * 1024


def boottime_seconds():
    """CLOCK_BOOTTIME puede faltar en Python o no estar soportado por el SO."""
    try:
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    except (AttributeError, OSError):
        return None


def jsonl_tail_summary(path):
    """Leer como máximo 64 KiB; descartar la primera línea si se cortó al buscar."""
    # No bloquear si el archivo dejó de ser regular durante la ejecución.
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError("El JSONL no es un archivo regular")
        offset = max(0, info.st_size - JSONL_TAIL_BYTES)
        stream.seek(offset)
        tail = stream.read(JSONL_TAIL_BYTES)
    lines = tail.split(b"\n")
    if offset:
        # Incluso si parece JSON válido, puede ser el sufijo de otra línea.
        lines.pop(0)
    summary = {"estado": "vacio" if info.st_size == 0 else "sin_evento_completo",
               "cola_limitada": offset > 0}
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            if index == len(lines) - 1 and not tail.endswith(b"\n"):
                summary["estado"] = "linea_incompleta"
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            continue
        last = {"tipo": event["type"]}
        item = event.get("item")
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            last["tipo_item"] = item["type"]
        summary["ultimo_evento"] = last
        if summary["estado"] != "linea_incompleta":
            summary["estado"] = "leido"
        break
    return summary

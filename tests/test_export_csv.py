"""Aceptación CSV permanente por CLI, con las aserciones del evaluador externo.

Cada método heredado participa en el descubrimiento habitual. El evaluador
conserva entorno, timeout e inventarios; no se importa el exportador.
"""

from pathlib import Path

from evals.tareas_reales.export_csv import evaluar


class TestExportCsvAcceptance(evaluar.AcceptanceTests):
    project = Path(__file__).resolve().parents[1]

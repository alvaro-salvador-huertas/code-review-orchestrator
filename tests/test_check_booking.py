"""Aceptación permanente de check-booking mediante CLI y datos sintéticos.

Cada método heredado se descubre por separado; el evaluador conserva entorno,
timeout e inventarios y nunca importa el producto.
"""

from pathlib import Path

from evals.tareas_reales.check_booking import evaluar


class TestCheckBookingAcceptance(evaluar.AcceptanceTests):
    project = Path(__file__).resolve().parents[1]

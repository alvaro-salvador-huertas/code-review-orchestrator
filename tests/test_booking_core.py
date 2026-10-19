"""Aceptación permanente de booking-core mediante CLI y API en procesos hijos.

Cada método heredado se descubre por separado. El evaluador conserva entorno,
timeout e inventarios, sin importar el producto en el proceso de pruebas.
"""

from pathlib import Path

from evals.tareas_reales.booking_core import evaluar


class TestBookingCoreAcceptance(evaluar.AcceptanceTests):
    project = Path(__file__).resolve().parents[1]

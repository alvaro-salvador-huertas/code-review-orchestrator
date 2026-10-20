"""Aceptación HTTP permanente; cada método heredado se descubre por separado."""

from pathlib import Path

from evals.tareas_reales.booking_http import evaluar


class TestBookingHttpAcceptance(evaluar.AcceptanceTests):
    project = Path(__file__).resolve().parents[1]

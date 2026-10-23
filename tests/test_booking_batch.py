"""Aceptación batch permanente; cada método heredado se descubre por separado."""

from pathlib import Path

from evals.tareas_reales.booking_batch import evaluar


class TestBookingBatchAcceptance(evaluar.AcceptanceTests):
    project = Path(__file__).resolve().parents[1]

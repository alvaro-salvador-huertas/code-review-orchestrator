"""Controles del evaluador batch, sin alias global de importación."""

import sys
from unittest.mock import patch

from evals.tareas_reales.booking_batch import evaluar


with patch.dict(sys.modules, {"evaluar": evaluar}):
    from evals.tareas_reales.booking_batch import comprobar_evaluador


class TestBookingBatchEvaluator(comprobar_evaluador.EvaluatorTests):
    pass

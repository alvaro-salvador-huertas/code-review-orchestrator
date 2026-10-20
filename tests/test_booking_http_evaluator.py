"""Controles y fixtures del evaluador HTTP, sin alias global de importación."""

import sys
from unittest.mock import patch

from evals.tareas_reales.booking_http import evaluar


with patch.dict(sys.modules, {"evaluar": evaluar}):
    from evals.tareas_reales.booking_http import comprobar_evaluador


class TestBookingHttpEvaluator(comprobar_evaluador.EvaluatorTests):
    pass


class TestBookingHttpTransportFixtures(comprobar_evaluador.TransportFixtureTests):
    pass

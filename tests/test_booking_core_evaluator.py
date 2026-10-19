"""Controles permanentes del evaluador con respuestas y módulos sintéticos."""

import sys
from unittest.mock import patch

from evals.tareas_reales.booking_core import evaluar


# Resolver el import del comprobador independiente sin dejar un alias global.
with patch.dict(sys.modules, {"evaluar": evaluar}):
    from evals.tareas_reales.booking_core import comprobar_evaluador


class TestBookingCoreEvaluator(comprobar_evaluador.EvaluatorTests):
    pass

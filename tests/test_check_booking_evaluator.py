"""Controles permanentes del evaluador con respuestas prefijadas, sin candidato."""

import sys
from unittest.mock import patch

from evals.tareas_reales.check_booking import evaluar


# Resolver el import del comprobador independiente sin dejar un alias global.
with patch.dict(sys.modules, {"evaluar": evaluar}):
    from evals.tareas_reales.check_booking import comprobar_evaluador


class TestCheckBookingEvaluator(comprobar_evaluador.EvaluatorTests):
    pass

"""Controles permanentes del evaluador CSV con sus respuestas prefijadas."""

import sys
from unittest.mock import patch

from evals.tareas_reales.export_csv import evaluar


# El comprobador independiente usa «import evaluar». Resolverlo solo durante
# su importación mantiene intacta esa autoridad y restaura los módulos previos.
with patch.dict(sys.modules, {"evaluar": evaluar}):
    from evals.tareas_reales.export_csv import comprobar_evaluador


class TestExportCsvEvaluator(comprobar_evaluador.EvaluatorTests):
    pass

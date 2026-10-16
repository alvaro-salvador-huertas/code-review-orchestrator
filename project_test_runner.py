"""Adaptador de unittest para procesos de evaluación de proyectos, no de benchmark."""

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import unittest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path)
    args = parser.parse_args(argv)
    record = {"version": 1, "completo": False, "metodos": [], "terminados": [],
              "fallos": [], "errores": [], "omitidos": [], "esperados": [], "inesperados": [],
              "total": 0, "sesiones": 0}

    def save():
        temporary = args.report.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, args.report)

    class RecordedResult(unittest.TextTestResult):
        def startTest(self, test):
            super().startTest(test)
            record["metodos"].append(test.id())
            record["total"] = self.testsRun
            save()

        def stopTest(self, test):
            super().stopTest(test)
            record["terminados"].append(test.id())
            save()

        def addFailure(self, test, err):
            super().addFailure(test, err)
            record["fallos"].append({"metodo": test.id(), "subtest": None})
            save()

        def addError(self, test, err):
            super().addError(test, err)
            record["errores"].append({"metodo": test.id(), "subtest": None})
            save()

        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            if err is not None:
                key = "fallos" if issubclass(err[0], test.failureException) else "errores"
                record[key].append({"metodo": test.id(), "subtest": str(subtest)})
                save()

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            record["omitidos"].append(test.id())
            save()

        def addExpectedFailure(self, test, err):
            super().addExpectedFailure(test, err)
            record["esperados"].append(test.id())
            save()

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test)
            record["inesperados"].append(test.id())
            save()

    class RecordedRunner(unittest.TextTestRunner):
        resultclass = RecordedResult

        def run(self, suite):
            record["sesiones"] += 1
            save()
            result = super().run(suite)
            record["completo"] = True
            save()
            return result

    save()
    # Solo se ejecuta el evaluador congelado, nunca se importa el inspector aquí.
    # Las pruebas de regresión existentes sí importan módulos en este proceso hijo.
    unittest.TextTestRunner = RecordedRunner
    if args.acceptance:
        sys.argv = [str(args.acceptance), "--project", str(args.project)]
        runpy.run_path(str(args.acceptance), run_name="__main__")
        return 0
    sys.path.insert(0, str(args.project))
    suite = unittest.defaultTestLoader.discover(str(args.project / "tests"))
    result = RecordedRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

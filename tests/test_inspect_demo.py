"""Consulta los ejemplos estáticos por CLI; nunca ejecuta sus referencias."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/inspect_run"


def snapshot(directory):
    """Detectar creación, eliminación o escritura, incluidas cachés y carpetas."""
    return {
        path.relative_to(directory).as_posix(): (
            path.read_bytes() if path.is_file() else None,
            path.stat().st_mtime_ns,
            path.stat().st_mode,
        )
        for path in (directory, *directory.rglob("*"))
    }


class TestInspectDemo(unittest.TestCase):
    def query(self, scenario, output_format=None, *, root=ROOT, cwd=ROOT):
        examples = root / "examples/inspect_run"
        before = snapshot(examples)
        command = [sys.executable, "-B", str(root / "inspect_run.py"),
                   "--run", os.path.relpath(examples / scenario, cwd)]
        if output_format is not None:
            command.extend(["--format", output_format])
        # Sin credenciales heredadas ni ejecutables externos disponibles en PATH.
        environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR")
                       if key in os.environ}
        environment.update(PATH="", PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1")
        try:
            return subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                                  text=True, encoding="utf-8", timeout=10)
        finally:
            self.assertEqual(snapshot(examples), before, "La consulta modificó la demo")

    def check_scenario(self, scenario, state, run_code, query_code, *, root=ROOT, cwd=ROOT):
        text = self.query(scenario, root=root, cwd=cwd)
        explicit = self.query(scenario, "text", root=root, cwd=cwd)
        self.assertEqual((explicit.returncode, explicit.stdout, explicit.stderr),
                         (text.returncode, text.stdout, text.stderr))
        exported = self.query(scenario, "json", root=root, cwd=cwd)
        self.assertEqual(text.returncode, query_code, text.stderr)
        self.assertEqual(exported.returncode, query_code, exported.stderr)
        self.assertEqual(exported.stderr, "")
        data = json.loads(exported.stdout)  # Rechaza texto o un segundo objeto adicional.
        self.assertEqual(data["version_esquema"], 1)
        query_state = "incompleta" if query_code else "completada"
        self.assertEqual(data["consulta"]["estado"], query_state)
        self.assertEqual(data["consulta"]["codigo_salida"], query_code)
        self.assertIn(f"Consulta: {query_state} (código {query_code})", text.stdout)
        self.assertIn(f"Estado del controlador: {state}; código de la ejecución: {run_code}",
                      text.stdout)
        failed = scenario == "fallo_agente"
        self.assertEqual(data["ejecucion"], {
            "caso": "demo_inspector", "estado": state, "codigo_salida": run_code,
            "presupuestos": {"max_intentos": 1, "max_invocaciones": 2},
            "intentos_registrados": 1,
            "invocaciones": {"desarrollador": 1, "revisor": 0 if failed else 1,
                             "total": 1 if failed else 2},
            "duracion_segundos": 1.0 if failed else 2.0,
        })
        self.assertIn("fallos de aserción; total 2, correctas 1, fallos 1", text.stdout)
        if query_code:
            missing = str(root / "examples/inspect_run/incompleta/reparacion/posterior/stderr.txt")
            self.assertEqual(len(data["consulta"]["incidencias"]), 1)
            self.assertIn(missing, data["consulta"]["incidencias"][0])
            self.assertIn(missing, text.stderr)
            self.assertIn("incompleto; recuentos: no consta", text.stdout)
        else:
            self.assertEqual(data["consulta"]["incidencias"], [])
            self.assertEqual(text.stderr, "")
        return text.stdout

    def test_aprobada_texto_y_json(self):
        output = self.check_scenario("aprobada", "aprobada", 0, 0)
        self.assertIn("pruebas superadas; total 2, correctas 2, fallos 0", output)
        self.assertIn("Dictamen registrado del modelo: aprobar; hallazgos: 0", output)
        self.assertIn("Transición: revision -> aprobar (revision_aprobada)", output)

    def test_fallo_agente_texto_y_json(self):
        output = self.check_scenario("fallo_agente", "fallo_agente", 3, 0)
        self.assertIn("Desarrollador: finalizada; invocaciones registradas: 1; código: 9", output)
        self.assertIn("recuentos: no consta (no ejecutadas)", output)
        self.assertIn("Revisión: no ejecutada según las etapas registradas", output)
        self.assertIn("Transición: desarrollo -> detener (fallo_agente)", output)

    def test_incompleta_conserva_datos_e_incidencias(self):
        self.assertFalse((EXAMPLES / "incompleta/reparacion/posterior/stderr.txt").exists())
        output = self.check_scenario("incompleta", "aprobada", 0, 1)
        self.assertIn("Dictamen registrado del modelo: aprobar; hallazgos: 0", output)
        self.assertIn("Intentos registrados: 1/1", output)

    def test_copia_portable_sin_tests_runs_ni_codex(self):
        with tempfile.TemporaryDirectory(prefix="test-demo-") as temporary:
            cwd = Path(temporary)
            root = cwd / "clon con espacios"
            shutil.copytree(EXAMPLES, root / "examples/inspect_run")
            for name in ("inspect_run.py", "case_evidence.py"):
                shutil.copyfile(ROOT / name, root / name)
            before = snapshot(root)
            for scenario, state, run_code, query_code in (
                ("aprobada", "aprobada", 0, 0),
                ("fallo_agente", "fallo_agente", 3, 0),
                ("incompleta", "aprobada", 0, 1),
            ):
                with self.subTest(scenario=scenario):
                    self.check_scenario(scenario, state, run_code, query_code, root=root, cwd=cwd)
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()

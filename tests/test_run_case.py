from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import ANY, patch

import run_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestRunCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix=".test-run-case-", dir=PROJECT_ROOT)
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.project = self.temporary / "proyecto con espacios"
        self.project.mkdir()
        (self.project / "tasks").mkdir()
        for case_id, contract_name in run_case.CASES.items():
            case_dir = self.project / "benchmark" / case_id
            case_dir.mkdir(parents=True)
            (case_dir / "solution.py").write_text("VALOR = 7\n", encoding="utf-8")
            (self.project / "tasks" / contract_name).write_text(
                f"Contrato de prueba de {case_id}.\n", encoding="utf-8"
            )
            self.write_test(case_id=case_id)
        self.script = self.project / "run_case.py"
        for name in ("run_case.py", "case_config.py", "case_evidence.py", "process_environment.py"):
            shutil.copy2(PROJECT_ROOT / name, self.project / name)

    def write_test(self, body="self.assertEqual(VALOR, 7)", case_id="case_01"):
        content = (
            "from pathlib import Path\n"
            "import sys\n"
            "import unittest\n"
            "from solution import VALOR\n\n"
            "class TestEjemplo(unittest.TestCase):\n"
            "    def test_ejemplo(self):\n"
            "        print('salida del proceso')\n"
            "        print('diagnostico del proceso', file=sys.stderr)\n"
            f"        {body}\n"
        )
        (self.project / "benchmark" / case_id / "test_solution.py").write_text(
            content, encoding="utf-8"
        )

    def execute(self, case_id="case_01"):
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = run_case.run_case(case_id, self.project)
        return code, output.getvalue(), errors.getvalue()

    def record(self):
        directories = list((self.project / "runs").iterdir())
        self.assertEqual(len(directories), 1)
        directory = directories[0]
        result = json.loads((directory / "resultado.json").read_text(encoding="utf-8"))
        return directory, result

    def test_proceso_con_codigo_cero_y_registro_reproducible(self):
        code, output, errors = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual(result["estado"], "finalizada")
        self.assertEqual(result["codigo_salida_pruebas"], 0)
        self.assertEqual(result["caso"], "case_01")
        self.assertEqual(result["errores_controlador"], [])
        self.assertEqual(result["limite_segundos"], 30)
        start = datetime.fromisoformat(result["inicio_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(result["fin_utc"].replace("Z", "+00:00"))
        self.assertEqual(start.utcoffset(), timedelta(0))
        self.assertEqual(end.utcoffset(), timedelta(0))
        self.assertGreaterEqual(end, start)
        self.assertGreaterEqual(result["duracion_segundos"], 0)
        self.assertEqual(result["directorio_trabajo"], str(directory / "workspace"))
        self.assertEqual(result["comando"][0], sys.executable)
        self.assertIn("-B", result["comando"])
        self.assertIn(str(directory / "workspace"), result["comando"])
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"salida del proceso\n")
        report = (directory / "stderr.txt").read_text(encoding="utf-8")
        self.assertIn("diagnostico del proceso", report)
        self.assertIn("Ran 1 test", report)
        self.assertIn("OK", report)
        for filename in ("solution.py", "test_solution.py"):
            self.assertEqual(
                (directory / "workspace" / filename).read_bytes(),
                (self.project / "benchmark" / "case_01" / filename).read_bytes(),
            )
        self.assertEqual(
            (directory / "contrato.md").read_bytes(),
            (self.project / "tasks" / run_case.CASES["case_01"]).read_bytes(),
        )
        self.assertFalse(list(directory.rglob("*.pyc")))
        self.assertIn("Estado: finalizada", output)
        self.assertIn("Código de salida de las pruebas: 0", output)
        self.assertIn(str(directory), output)

    def test_proceso_con_codigo_uno_conserva_ambas_salidas(self):
        self.write_test(body="self.assertEqual(VALOR, 8)")
        code, output, errors = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual(result["estado"], "finalizada")
        self.assertEqual(result["codigo_salida_pruebas"], 1)
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"salida del proceso\n")
        report = (directory / "stderr.txt").read_text(encoding="utf-8")
        self.assertIn("diagnostico del proceso", report)
        self.assertIn("FAILED (failures=1)", report)
        self.assertIn("Código de salida de las pruebas: 1", output)

    def test_error_en_las_pruebas_tambien_es_ejecucion_finalizada(self):
        self.write_test(body="raise RuntimeError('error de la prueba')")
        code, _, _ = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 0)
        self.assertEqual(result["estado"], "finalizada")
        self.assertEqual(result["codigo_salida_pruebas"], 1)
        self.assertIn(
            "FAILED (errors=1)", (directory / "stderr.txt").read_text(encoding="utf-8")
        )

    def test_tiempo_agotado_conserva_salida_parcial(self):
        timeout = subprocess.TimeoutExpired(
            cmd=["python"], timeout=30, output=b"salida parcial\n", stderr=b"error parcial\n"
        )
        with patch("run_case.subprocess.run", side_effect=timeout) as process:
            code, output, errors = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 1)
        self.assertEqual(errors, "")
        self.assertEqual(result["estado"], "tiempo_agotado")
        self.assertIsNone(result["codigo_salida_pruebas"])
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"salida parcial\n")
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"error parcial\n")
        self.assertIn("Estado: tiempo_agotado", output)
        self.assertIn("Código de salida de las pruebas: null", output)
        process.assert_called_once_with(
            result["comando"], cwd=directory / "workspace", shell=False,
            capture_output=True, timeout=30, check=False, env=ANY,
        )

    def test_tiempo_agotado_sin_salida(self):
        with patch(
            "run_case.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=30),
        ):
            code, _, _ = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 1)
        self.assertEqual(result["estado"], "tiempo_agotado")
        self.assertIsNone(result["codigo_salida_pruebas"])
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"")
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"")

    def test_error_al_iniciar_proceso(self):
        with patch("run_case.subprocess.run", side_effect=OSError("no se pudo iniciar")):
            code, output, errors = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 1)
        self.assertEqual(result["estado"], "error_ejecucion")
        self.assertIsNone(result["codigo_salida_pruebas"])
        self.assertIn("no se pudo iniciar", result["errores_controlador"][0])
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"")
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"")
        self.assertIn("Estado: error_ejecucion", output)
        self.assertIn("no se pudo iniciar", errors)

    def test_originales_intactos_y_registros_diferentes(self):
        self.write_test(body="Path('solution.py').write_text('# cambio en la copia\\n')")
        originals = {
            path: path.read_bytes()
            for folder in ("benchmark", "tasks")
            for path in (self.project / folder).rglob("*") if path.is_file()
        }
        for _ in range(2):
            self.assertEqual(self.execute()[0], 0)
        directories = list((self.project / "runs").iterdir())

        self.assertEqual(len(directories), 2)
        self.assertNotEqual(directories[0], directories[1])
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        for directory in directories:
            self.assertRegex(directory.name, r"^\d{8}T\d{12}Z_case_01_[0-9a-f]{32}$")
            self.assertEqual(
                (directory / "workspace" / "solution.py").read_text(),
                "# cambio en la copia\n",
            )

    def test_archivos_requeridos_ausentes_impiden_lanzar_pruebas(self):
        required = [
            self.project / "tasks" / run_case.CASES["case_01"],
            self.project / "benchmark" / "case_01" / "solution.py",
            self.project / "benchmark" / "case_01" / "test_solution.py",
        ]
        for path in required:
            with self.subTest(archivo=path.name):
                original = path.read_bytes()
                path.unlink()
                with patch("run_case.subprocess.run") as process:
                    code, output, errors = self.execute()
                path.write_bytes(original)

                self.assertEqual(code, 1)
                process.assert_not_called()
                self.assertIn("Estado: error_ejecucion", output)
                self.assertIn("Registro: no creado", output)
                self.assertIn(str(path), errors)
                self.assertFalse((self.project / "runs").exists())

    def test_error_al_crear_registro_no_lanza_pruebas(self):
        (self.project / "runs").write_text("ocupado", encoding="utf-8")
        with patch("run_case.subprocess.run") as process:
            code, output, errors = self.execute()

        self.assertEqual(code, 1)
        process.assert_not_called()
        self.assertIn("Estado: error_ejecucion", output)
        self.assertIn("Registro: no creado", output)
        self.assertTrue(errors)

    def test_error_al_copiar_no_lanza_pruebas(self):
        with patch("run_case.shutil.copy2", side_effect=OSError("copia fallida")):
            with patch("run_case.subprocess.run") as process:
                code, _, _ = self.execute()
        _, result = self.record()

        self.assertEqual(code, 1)
        process.assert_not_called()
        self.assertEqual(result["estado"], "error_ejecucion")
        self.assertIsNone(result["codigo_salida_pruebas"])
        self.assertIn("copia fallida", result["errores_controlador"][0])

    def test_error_al_guardar_salida_conserva_el_otro_canal(self):
        write_bytes = Path.write_bytes

        def fail_stdout(path, content):
            if path.name == "stdout.txt":
                raise OSError("escritura fallida")
            return write_bytes(path, content)

        with patch.object(Path, "write_bytes", fail_stdout):
            code, output, errors = self.execute()
        directory, result = self.record()

        self.assertEqual(code, 1)
        self.assertEqual(result["estado"], "error_ejecucion")
        self.assertEqual(result["codigo_salida_pruebas"], 0)
        self.assertIn("OK", (directory / "stderr.txt").read_text(encoding="utf-8"))
        self.assertIn("Estado: error_ejecucion", output)
        self.assertIn("stdout.txt", errors)
        self.assertIn("stdout.txt", result["errores_controlador"][0])

    def test_error_al_guardar_json_conserva_salidas_y_devuelve_error(self):
        with patch.object(Path, "write_text", side_effect=OSError("registro fallido")):
            code, output, errors = self.execute()
        directories = list((self.project / "runs").iterdir())

        self.assertEqual(code, 1)
        self.assertEqual(len(directories), 1)
        self.assertEqual(
            (directories[0] / "stdout.txt").read_bytes(), b"salida del proceso\n"
        )
        self.assertIn("OK", (directories[0] / "stderr.txt").read_text(encoding="utf-8"))
        self.assertIn("Estado: error_ejecucion", output)
        self.assertIn("resultado.json", errors)

    def test_cli_desde_otro_directorio_selecciona_case_02(self):
        other_directory = self.temporary / "otro directorio"
        other_directory.mkdir()
        process = subprocess.run(
            [sys.executable, "-B", str(self.script), "case_02"],
            cwd=other_directory, capture_output=True, text=True, timeout=10,
        )
        directory, result = self.record()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        self.assertEqual(result["caso"], "case_02")
        self.assertEqual(result["estado"], "finalizada")
        self.assertEqual(result["codigo_salida_pruebas"], 0)
        self.assertEqual(result["directorio_trabajo"], str(directory / "workspace"))
        self.assertEqual(
            (directory / "contrato.md").read_bytes(),
            (self.project / "tasks" / run_case.CASES["case_02"]).read_bytes(),
        )
        self.assertFalse((other_directory / "runs").exists())
        self.assertIn(str(directory), process.stdout)

    def test_cli_rechaza_identificadores_no_admitidos(self):
        process = subprocess.run(
            [sys.executable, "-B", str(self.script), "case_03"],
            cwd=self.temporary, capture_output=True, text=True, timeout=10,
        )

        self.assertEqual(process.returncode, 2)
        self.assertIn("case_01", process.stderr)
        self.assertIn("case_02", process.stderr)
        self.assertFalse((self.project / "runs").exists())


if __name__ == "__main__":
    unittest.main()

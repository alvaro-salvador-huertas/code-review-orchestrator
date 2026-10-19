"""Descubrimiento en hijos sobre referencias sintéticas, sin ejecutar sus tests."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from project_test_inventory import inventory_tests, snapshot


class TestProjectTestInventory(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="prueba-inventario-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reference = self.root / "referencia-confiable"
        (self.reference / "tests").mkdir(parents=True)
        self.executed = self.root / "metodo_ejecutado"

    def write(self, name, source):
        path = self.reference / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")

    def simple_test(self):
        self.write("tests/test_sentinel_inventory.py", f'''
            import unittest
            from pathlib import Path
            class Sentinel(unittest.TestCase):
                def setUp(self):
                    raise AssertionError("No ejecutar setUp")
                def test_discovered(self):
                    Path({str(self.executed)!r}).write_text("Ejecutado")
                    raise AssertionError("No ejecutar el método")
        ''')

    def assert_error(self, report, message, *, conserved=True):
        self.assertEqual(report["estado"], "error", report)
        self.assertEqual(report["identidades"], [])
        self.assertEqual(report["total"], 0)
        self.assertIn(message, "\n".join(report["errores"]))
        self.assertIs(report["conservada"], conserved)
        self.assertFalse(self.executed.exists())

    def test_herencia_local_importada_propios_y_sobrescritura(self):
        self.write("inventory_parents.py", '''
            import unittest
            class Parent(unittest.TestCase):
                def test_inherited(self):
                    raise AssertionError("No ejecutar")
                def test_override(self):
                    raise AssertionError("No ejecutar")
        ''')
        self.write("tests/test_inventory_inheritance.py", '''
            import unittest
            import inventory_parents
            class Local(unittest.TestCase):
                def test_inherited(self):
                    raise AssertionError("No ejecutar")
                def test_override(self):
                    raise AssertionError("No ejecutar")
            class LocalChild(Local):
                def test_own(self):
                    raise AssertionError("No ejecutar")
                def test_override(self):
                    raise AssertionError("No ejecutar sobrescritura")
            class ImportedChild(inventory_parents.Parent):
                def test_own(self):
                    raise AssertionError("No ejecutar")
                def test_override(self):
                    raise AssertionError("No ejecutar sobrescritura")
        ''')
        before = snapshot(self.reference)
        report = inventory_tests(self.reference)
        expected = sorted(f"test_inventory_inheritance.{cls}.test_{method}"
                          for cls, methods in (("Local", ("inherited", "override")),
                                               ("LocalChild", ("inherited", "override", "own")),
                                               ("ImportedChild", ("inherited", "override", "own")))
                          for method in methods)
        self.assertEqual(report["estado"], "completado", report)
        self.assertEqual(report["identidades"], expected)
        self.assertEqual(report["total"], len(expected))
        self.assertEqual(report["errores"], [])
        self.assertTrue(report["conservada"])
        self.assertEqual(snapshot(self.reference), before)
        self.assertEqual(report["arbol_antes_sha256"], report["arbol_despues_sha256"])
        self.assertNotIn("inventory_parents", sys.modules)
        self.assertNotIn("test_inventory_inheritance", sys.modules)

    def test_sentinela_importacion_y_entorno_del_hijo(self):
        self.simple_test()
        imported = self.root / "inicializacion_ejecutada"
        self.write("tests/test_inventory_initialization.py", f'''
            import os
            import sys
            from pathlib import Path
            assert sys.dont_write_bytecode
            assert Path.cwd() == Path({str(self.reference)!r})
            assert "OPENAI_API_KEY" not in os.environ
            assert "PYTHONPATH" not in os.environ
            Path({str(imported)!r}).write_text("Inicialización en el hijo")
            print("stdout de inicialización")
            print("stderr de inicialización", file=sys.stderr)
        ''')
        original_run = subprocess.run
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SINTETICA", "PYTHONPATH": "SINTETICA"}), \
                patch("project_test_inventory.subprocess.run", wraps=original_run) as run:
            report = inventory_tests(self.reference, timeout=10)
        self.assertEqual(report["estado"], "completado", report)
        self.assertEqual(report["identidades"], ["test_sentinel_inventory.Sentinel.test_discovered"])
        self.assertEqual(report["total"], 1)
        self.assertTrue(imported.exists())
        self.assertFalse(self.executed.exists())
        self.assertIn("stdout de inicialización", report["stdout_hijo"])
        self.assertIn("stderr de inicialización", report["stderr_hijo"])
        self.assertNotIn("test_sentinel_inventory", sys.modules)
        self.assertNotIn("test_inventory_initialization", sys.modules)
        self.assertFalse(list(self.reference.rglob("__pycache__")))
        command = run.call_args.args[0]
        options = run.call_args.kwargs
        self.assertEqual(command[:2], [str(Path(sys.executable).resolve()), "-B"])
        self.assertEqual(options["cwd"], self.reference)
        self.assertEqual(options["timeout"], 10)
        self.assertEqual(options["stdin"], subprocess.DEVNULL)
        self.assertFalse(options["shell"])
        self.assertNotEqual(options["env"]["HOME"], os.environ.get("HOME"))
        self.assertNotIn("OPENAI_API_KEY", options["env"])
        self.assertEqual(report["politica_entorno"], "evaluation")

    def test_error_importacion_no_produce_inventario_parcial(self):
        self.simple_test()
        self.write("tests/test_broken.py", "import modulo_sintetico_inexistente_974\n")
        self.assert_error(inventory_tests(self.reference), "ModuleNotFoundError")

    def test_error_de_load_tests_se_rechaza(self):
        self.simple_test()
        self.write("tests/test_broken.py", '''
            def load_tests(loader, suite, pattern):
                raise RuntimeError("Fallo sintético de descubrimiento")
        ''')
        self.assert_error(inventory_tests(self.reference), "Fallo sintético de descubrimiento")

    def test_system_exit_durante_importacion_se_rechaza(self):
        self.write("tests/test_broken.py", "raise SystemExit(0)\n")
        self.assert_error(inventory_tests(self.reference), "SystemExit")

    def test_failed_test_incluso_sin_loader_errors_se_rechaza(self):
        self.write("tests/test_broken.py", '''
            import unittest
            from unittest.loader import _FailedTest
            def load_tests(loader, suite, pattern):
                return unittest.TestSuite([_FailedTest("error", ImportError("sintético"))])
        ''')
        self.assert_error(inventory_tests(self.reference), "Prueba sintética de error")

    def test_duplicados_en_suites_anidadas_se_rechazan(self):
        self.write("tests/test_duplicates.py", '''
            import unittest
            class Repeated(unittest.TestCase):
                def test_once(self):
                    raise AssertionError("No ejecutar")
            def load_tests(loader, suite, pattern):
                return unittest.TestSuite([suite, unittest.TestSuite([Repeated("test_once")])])
        ''')
        self.assert_error(inventory_tests(self.reference), "Identidades duplicadas")

    def test_suite_vacia_se_rechaza(self):
        self.assert_error(inventory_tests(self.reference), "Suite vacía")

    def test_directorio_de_descubrimiento_ausente_se_rechaza(self):
        (self.reference / "tests").rmdir()
        self.assert_error(inventory_tests(self.reference), "ImportError")

    def test_detecta_alteraciones_incluso_si_falla_importacion(self):
        self.simple_test()
        self.write("protegido.txt", "Original\n")
        for suffix in ("", "raise RuntimeError('Error tras alterar')\n"):
            with self.subTest(error=bool(suffix)):
                self.write("protegido.txt", "Original\n")
                self.write("tests/test_changes.py", 'from pathlib import Path\n'
                           'Path("protegido.txt").write_text("Alterado")\n' + suffix)
                self.assert_error(inventory_tests(self.reference), "alteró la copia protegida", conserved=False)

    def test_detecta_archivos_nuevos_caches_y_metadatos(self):
        self.simple_test()
        self.write("protegido.txt", "Original\n")
        for source, diagnostic in (
            ('Path("nuevo.txt").write_text("nuevo")', "alteró la copia protegida"),
            ('Path("__pycache__").mkdir()', "Caché Python"),
            ('os.utime("protegido.txt", ns=(1, 1))', "alteró la copia protegida"),
        ):
            with self.subTest(inicializacion=source):
                self.write("tests/test_changes.py", "from pathlib import Path\nimport os\n" + source + "\n")
                self.assert_error(inventory_tests(self.reference), diagnostic, conserved=False)
                (self.reference / "nuevo.txt").unlink(missing_ok=True)
                cache = self.reference / "__pycache__"
                if cache.exists():
                    cache.rmdir()

    def test_timeout_comprueba_conservacion(self):
        self.simple_test()
        self.write("tests/test_wait.py", "import time\ntime.sleep(10)\n")
        self.assert_error(inventory_tests(self.reference, timeout=0.5), "excedió")

    def test_enlaces_no_se_siguen(self):
        self.simple_test()
        outside = self.root / "externo.txt"
        outside.write_text("No inventariar fuera de la copia", encoding="utf-8")
        (self.reference / "enlace").symlink_to(outside)
        self.assert_error(inventory_tests(self.reference), "Enlace o archivo especial", conserved=None)

    def test_cli_emite_un_objeto_json_y_codigo_coherente(self):
        self.simple_test()
        script = Path(__file__).resolve().parents[1] / "project_test_inventory.py"
        for broken in (False, True):
            if broken:
                self.write("tests/test_broken.py", "raise ImportError('Fallo sintético')\n")
            with self.subTest(error=broken):
                completed = subprocess.run(
                    [str(Path(sys.executable).resolve()), "-B", str(script),
                     "--reference", str(self.reference), "--timeout", "10"],
                    cwd=self.root, capture_output=True, timeout=15, check=False,
                )
                self.assertEqual(completed.returncode, int(broken), completed.stderr)
                self.assertEqual(completed.stderr, b"")
                report = json.loads(completed.stdout)
                self.assertEqual(report["estado"], "error" if broken else "completado")
                self.assertTrue(report["conservada"])
                self.assertFalse(self.executed.exists())


if __name__ == "__main__":
    unittest.main()

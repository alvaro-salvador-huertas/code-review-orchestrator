"""Preparación con identidades sintéticas y revisor simulado; nunca llama a modelos."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from project_delivery import identity
from repair_project import tree_state
import review_project as controller


APPROVE = {"decision": "aprobar", "resumen": "Revisor simulado.", "hallazgos": []}


def simulated_reviewer(workspace, final, prompt, log, *, on_invoke, **kwargs):
    on_invoke()
    final.write_text(json.dumps(APPROVE))
    return {"invocaciones": 1, "estado": "finalizada", "codigo_salida": 0}


class Preparation:
    """Frontera de carga simulada: la identidad se calcula antes de preparar copias."""
    def __init__(self, root, multiple=False):
        self.root = root
        self.root.mkdir()
        self.source = root / "entrega_validada"
        self.source.mkdir()
        self.names = ("consulta.py", "reglas.py") if multiple else ("consulta.py",)
        for name in self.names:
            path = self.source / name
            path.write_bytes(("# Marcador sintético: " + name + "\n").encode())
            path.chmod(0o755 if name == "reglas.py" else 0o644)
        self.validated = controller.Evidence(self.source)
        self.expected = identity(self.validated.state, {"editables": self.names})
        self.aliases = {"evidencia/entrega/archivos/" + name: name for name in self.names}
        self.evidence = {name: self.validated.read(name) for name in self.names}
        self.evidence.update({path: self.evidence[name] for path, name in self.aliases.items()})
        self.evidence["contrato.md"] = b"Documento ajeno al conjunto candidato.\n"
        self.prompt = root / "prompt.txt"
        self.prompt.write_text("Revisión simulada.")
        self.reservation = Mock()

    def load(self):
        return dict(self.evidence), {
            "tipo": "orquestacion_configurable_v2" if len(self.names) > 1 else "orquestacion_configurable_v1",
            "conjunto": self.expected, "conjunto_sha256": self.expected["sha256"],
            "candidatos": self.validated.state, "copias_candidato": self.aliases,
        }, (self.validated,)

    def select(self, evidence, authorization):
        return {n: b for n, b in evidence.items() if not n.startswith("evidencia/")}, {}

    def run(self):
        return controller._run_review(
            self.load, self.select, self.prompt, self.root, on_invoke=self.reservation,
            editable=self.names if len(self.names) > 1 else self.names[0])


def probe(multiple=False, historical=False):
    """Se ejecuta en un hijo cuya umask fija Popen; no modifica la del padre."""
    if historical:
        import test_review_project as fixture
        test = fixture.ProjectReviewTests()
        try:
            test.setUp()
            with patch.object(controller, "invoke_reviewer", side_effect=simulated_reviewer):
                result = test.run_review()
            log = Path(result["registro"])
            return {"resultado": result,
                    "materiales": tree_state(log / "materiales"),
                    "evidencia": tree_state(log / "evidencia_validada")}
        finally:
            test.doCleanups()
    with tempfile.TemporaryDirectory(prefix="identidad-revision-") as temporary:
        setup = Preparation(Path(temporary) / "proyecto", multiple)
        seen = {}

        def reviewer(workspace, *args, **kwargs):
            seen.update(tree_state(workspace))
            return simulated_reviewer(workspace, *args, **kwargs)

        with patch.object(controller, "invoke_reviewer", side_effect=reviewer):
            result = setup.run()
        log = Path(result["registro"])
        return {"resultado": result, "esperado": setup.expected, "workspace": seen,
                "materiales": tree_state(log / "materiales"),
                "evidencia": tree_state(log / "evidencia_validada"),
                "reservas": setup.reservation.call_count,
                "fuente_intacta": setup.validated.unchanged()}


class CandidateIdentityTests(unittest.TestCase):
    def child(self, mask, **options):
        code = ("import json,sys; sys.path.insert(0, 'tests'); "
                "from test_review_candidate_identity import probe; "
                f"print(json.dumps(probe(**{options!r})))")
        process = subprocess.run([sys.executable, "-B", "-c", code],
                                 cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True, timeout=30, umask=mask)
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        return json.loads(process.stdout)

    def test_umask_en_hijos_preserva_un_archivo_y_conjunto_ejecutable(self):
        for mask in (0o022, 0o002):
            for multiple in (False, True):
                with self.subTest(umask=oct(mask), multiples=multiple):
                    data = self.child(mask, multiple=multiple)
                    self.assertEqual(data["resultado"]["codigo_salida"], 0, data["resultado"])
                    expected = data["esperado"]
                    names = [v["ruta"] for v in expected["archivos"]]
                    for folder in ("materiales", "workspace", "evidencia"):
                        self.assertEqual(identity(data[folder], {"editables": names}), expected, folder)
                        # Ninguna normalización de permisos para documentos ajenos.
                        self.assertEqual(data[folder]["contrato.md"]["modo"], 0o666 & ~mask)
                    for item in expected["archivos"]:
                        copied = data["evidencia"]["evidencia/entrega/archivos/" + item["ruta"]]
                        self.assertEqual(copied, {k: v for k, v in item.items() if k != "ruta"})
                    self.assertEqual(data["reservas"], 1)
                    self.assertEqual(data["resultado"]["revisor"]["invocaciones"], 1)
                    self.assertTrue(data["fuente_intacta"])

    def test_via_historica_toma_el_modo_del_workspace_validado(self):
        for mask in (0o022, 0o002):
            with self.subTest(umask=oct(mask)):
                data = self.child(mask, historical=True)
                self.assertEqual(data["resultado"]["codigo_salida"], 0, data["resultado"])
                for folder in ("materiales", "evidencia"):
                    self.assertEqual(data[folder]["inspect_run.py"]["modo"], 0o644)

    def assert_preparation_error(self, setup, adapter, result):
        adapter.assert_not_called()
        setup.reservation.assert_not_called()
        self.assertEqual(result["codigo_salida"], 8, result)
        self.assertEqual(result["decision_controlador"], "fallo_controlador")
        self.assertFalse(result["reserva_invocacion"])
        self.assertEqual(result["revisor"]["invocaciones"], 0)
        self.assertIsNone(result["dictamen_modelo"])
        self.assertTrue(setup.validated.unchanged())

    def test_rechaza_cambios_tras_copiar_antes_de_entrar_en_adaptador(self):
        for location in ("workspace", "materiales", "evidencia_validada", "ambos"):
            for change in ("modo", "contenido", "enlace", "ruta"):
                with self.subTest(ubicacion=location, cambio=change), \
                        tempfile.TemporaryDirectory() as temporary:
                    setup = Preparation(Path(temporary) / "proyecto", multiple=True)
                    copytree = shutil.copytree

                    def tamper(source, target, *args, **kwargs):
                        copied = copytree(source, target, *args, **kwargs)
                        if Path(source).name == "materiales":
                            paths = {
                                "workspace": [Path(target) / "reglas.py"],
                                "materiales": [Path(source) / "reglas.py"],
                                "evidencia_validada": [Path(source).parent / "evidencia_validada/evidencia/entrega/archivos/reglas.py"],
                                "ambos": [Path(target) / "reglas.py", Path(source) / "reglas.py"],
                            }[location]
                            for path in paths:
                                if change == "modo":
                                    path.chmod(0o644)
                                elif change == "contenido":
                                    path.write_bytes(b"# alterado\n")
                                elif change == "enlace":
                                    path.unlink()
                                    path.symlink_to(setup.source / "reglas.py")
                                else:
                                    path.rename(path.with_name("otro.py"))
                        return copied

                    with patch.object(controller.shutil, "copytree", side_effect=tamper), \
                            patch.object(controller, "invoke_reviewer") as adapter:
                        result = setup.run()
                    self.assert_preparation_error(setup, adapter, result)

    def test_rechaza_copia_alterada_antes_de_tomar_su_inventario(self):
        # Un inventario recién calculado de bytes/modos erróneos no es autoridad.
        for folder in ("materiales", "evidencia_validada"):
            for change in ("modo", "contenido"):
                with self.subTest(carpeta=folder, cambio=change), \
                        tempfile.TemporaryDirectory() as temporary:
                    setup = Preparation(Path(temporary) / "proyecto")
                    state = controller.tree_state
                    mutated = False

                    def inventory(path, **kwargs):
                        nonlocal mutated
                        if Path(path).name == folder and not mutated:
                            mutated = True
                            candidate = Path(path) / "consulta.py"
                            if change == "modo":
                                candidate.chmod(0o600)
                            else:
                                candidate.write_bytes(b"# distinto\n")
                        return state(path, **kwargs)

                    with patch.object(controller, "tree_state", side_effect=inventory), \
                            patch.object(controller, "invoke_reviewer", side_effect=simulated_reviewer) as adapter:
                        result = setup.run()
                    self.assertTrue(mutated)
                    self.assert_preparation_error(setup, adapter, result)


if __name__ == "__main__":
    unittest.main()

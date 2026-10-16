"""Lanzador controlado con procesos y Git temporales; nunca usa Codex real."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import evaluate_reviewer as launcher
import review_case
from case_evidence import digest, snapshot_tree


PROJECT = Path(__file__).resolve().parents[1]
HELP = "--config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema"
APPROVAL = {"decision": "aprobar", "resumen": "Respuesta simulada.", "hallazgos": []}
CHANGES = {
    "decision": "solicitar_cambios", "resumen": "Solicitud simulada, no evaluada.",
    "hallazgos": [{"archivo": "candidato.py", "linea": 1,
                   "explicacion": "Hallazgo simulado para probar la continuación.",
                   "ejemplo": "Ejemplo simulado, pendiente de contraste."}],
}


class TestEvaluateReviewer(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-evaluate-reviewer-")
        self.addCleanup(temporary.cleanup)
        self.temporary = Path(temporary.name)
        self.root = self.temporary / "proyecto con espacios"
        self.root.mkdir()
        for name in launcher.source_paths(PROJECT):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((PROJECT / name).read_bytes())
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture temporal")
        # No se deben leer ni copiar estos materiales, ni aun al registrar Git.
        for name in (".env", ".codex/config.toml", "evals/revisor/expectativas.md",
                     "tests/test_reviewer_candidates.py", "runs/historico/privado.txt"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("SECRETO_DEL_EVALUADOR", encoding="utf-8")
        self.fake = self.temporary / "codex"
        self.calls = self.temporary / "llamadas.jsonl"
        self.settings = self.temporary / "simulacion.json"
        self.configure_fake()
        self.addCleanup(patch.stopall)
        patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)).start()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, check=True, timeout=10).stdout

    def configure_fake(self, **settings):
        self.settings.write_text(json.dumps(settings), encoding="utf-8")
        source = f'''#!{sys.executable}
import json
import os
from pathlib import Path
import sys
import time

settings = json.loads(Path({str(self.settings)!r}).read_text())
calls = Path({str(self.calls)!r})
args = sys.argv[1:]
if args == ["--version"]:
    print("codex-simulado 1.0")
    sys.exit(0)
if args == ["exec", "--help"]:
    print("incompatible" if settings.get("incompatible") else {HELP!r})
    sys.exit(0)
assert args[0] == "exec" and args[-1] == "-", args
workspace = Path.cwd()
files = {{p.name: p.read_text() for p in workspace.iterdir()}}
prompt = sys.stdin.read()
with calls.open("a", encoding="utf-8") as out:
    out.write(json.dumps({{"args": args, "cwd": str(workspace), "files": files,
                          "prompt": prompt, "pid": os.getpid()}}) + "\\n")
number = len(calls.read_text().splitlines())
print(json.dumps({{"type": "simulacion", "numero": number}}), flush=True)
print("stderr de la simulación", file=sys.stderr, flush=True)
if settings.get("mutate_workspace"):
    (workspace / "candidato.py").write_text("alterado")
if settings.get("mutate_path") and number == settings.get("mutate_on", 1):
    Path(settings["mutate_path"]).write_text("alterado")
if settings.get("block"):
    time.sleep(30)
reply = {APPROVAL!r}
if settings.get("changes"):
    reply = {CHANGES!r}
final = Path(args[args.index("--output-last-message") + 1])
final.write_text("{{JSON inválido" if settings.get("invalid") else json.dumps(reply))
sys.exit(settings.get("exit_code", 0))
'''
        self.fake.write_text(source, encoding="utf-8")
        self.fake.chmod(0o755)

    def prepare(self):
        result = launcher.prepare(self.root)
        self.assertEqual(result["codigo_salida"], 0, result)
        return Path(result["experimento"])

    def read_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def run_experiment(self, experiment):
        return launcher.run_experiment(experiment, self.root)

    def cli(self, *args):
        # El ejecutable simulado va primero; no se depende de la CLI personal.
        return subprocess.run(
            [sys.executable, "-B", "evaluate_reviewer.py", *map(str, args)], cwd=self.root,
            env={**os.environ, "PATH": str(self.temporary) + os.pathsep + os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=20,
        )

    def assert_stopped(self, result, state, count=1):
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertFalse(result["evidencia_completa_verificada"])
        self.assertEqual(len(self.read_calls()), count)
        self.assertEqual(result["candidatos"][count - 1]["estado"], state)
        self.assertTrue(all(item["estado"] == "pendiente" and item["invocaciones"] == 0
                            for item in result["candidatos"][count:]))

    def test_prepare_congela_procedencia_git_y_evaluaciones_reales_sin_cli(self):
        candidate = self.root / "evals/revisor/candidatos/candidato_01.py"
        candidate.write_bytes(candidate.read_bytes() + b"\n")
        instructions = "evals/revisor/instrucciones_case_01.md"
        self.git("rm", "--cached", instructions)  # Fuente no versionada, conservada igualmente.
        with patch.object(review_case, "invoke_reviewer", side_effect=AssertionError("No invocar")):
            experiment = self.prepare()
        self.assertEqual(self.read_calls(), [])
        prepared, _ = launcher.validate_preparation(experiment, self.root)
        self.assertEqual(prepared["procedencia"], "candidatos_preparados_para_evaluacion")
        frozen = experiment / "preparacion"
        git = json.loads((frozen / "git.json").read_text())
        self.assertEqual(git["revision"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertIn("candidato_01.py", git["estado_relevante"])
        self.assertIn(instructions, git["estado_relevante"])
        self.assertIn(b"candidato_01.py", (frozen / "cambios.patch").read_bytes())
        self.assertEqual((frozen / "fuentes" / instructions).read_bytes(), (self.root / instructions).read_bytes())
        self.assertEqual(prepared["sha256"], snapshot_tree(frozen))
        for path in frozen.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"SECRETO_DEL_EVALUADOR", path.read_bytes())
        for candidate_id, case_id in launcher.CANDIDATES:
            evaluation = frozen / "evaluaciones" / candidate_id
            report = json.loads((evaluation / "resultado.json").read_text())
            self.assertEqual(report["codigo_salida"], 0)
            self.assertNotIn(self.root, Path(report["directorio_trabajo"]).parents)
            count = 4 if case_id == "case_01" else 16
            self.assertIn(f"Ran {count} tests", (evaluation / "stderr.txt").read_text())
            self.assertIn("-B", report["comando"])

    def test_prepare_fallida_conserva_informe_y_no_autoriza_run(self):
        (self.root / "evals/revisor/candidatos/candidato_01.py").write_text(
            "def calcular_totales_por_asignatura(sesiones):\n    return {}\n")
        prepared = launcher.prepare(self.root)
        self.assertEqual(prepared["codigo_salida"], 1)
        experiment = Path(prepared["experimento"])
        report = experiment / "preparacion/evaluaciones/candidato_01/stderr.txt"
        self.assertIn("FAILED", report.read_text())
        result = self.run_experiment(experiment)
        self.assertEqual(result["codigo_salida"], 1)
        self.assertEqual(self.read_calls(), [])
        self.assertFalse((experiment / "lanzamiento").exists())

    def test_recorrido_completo_continua_cambios_contexto_y_limite_cuatro(self):
        self.configure_fake(changes=True)
        experiment = self.prepare()
        frozen = snapshot_tree(experiment / "preparacion")
        # El lanzamiento usa las fuentes congeladas aunque las fuentes de trabajo cambien.
        (self.root / "evals/revisor/candidatos/candidato_01.py").write_text("cambio posterior")
        (self.root / "evals/revisor/instrucciones_case_01.md").write_text("cambio posterior")
        result = self.run_experiment(experiment)
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertTrue(result["evidencia_completa_verificada"])
        self.assertEqual(result["revisiones_reservadas"], 4)
        self.assertEqual(snapshot_tree(experiment / "preparacion"), frozen)
        calls = self.read_calls()
        self.assertEqual(len(calls), 4)
        self.assertEqual(len({call["cwd"] for call in calls}), 4)
        self.assertEqual(calls[0]["prompt"], calls[1]["prompt"])
        self.assertEqual(calls[2]["prompt"], calls[3]["prompt"])
        expected_files = {"candidato.py", "contrato.md", "test_solution.py", "posterior.json",
                          "posterior.stdout.txt", "posterior.stderr.txt", "respuesta.schema.json"}
        for call, entry, (candidate_id, case_id) in zip(calls, result["candidatos"], launcher.CANDIDATES):
            self.assertEqual(entry["id"], candidate_id)
            self.assertEqual(entry["estado"], "completada")
            self.assertEqual(entry["invocaciones"], 1)
            self.assertEqual(entry["dictamen"], CHANGES)
            self.assertEqual(entry["validez_hallazgos"], "pendiente_de_contraste")
            self.assertEqual(set(call["files"]), expected_files)
            self.assertNotIn(self.root, Path(call["cwd"]).parents)
            self.assertEqual(call["files"]["candidato.py"].encode(),
                             (experiment / "preparacion/fuentes/evals/revisor/candidatos" / f"{candidate_id}.py").read_bytes())
            context = call["prompt"] + json.dumps(call["files"])
            for excluded in ("SECRETO_DEL_EVALUADOR", "expectativas.md", "test_reviewer_candidates",
                             "candidato_01", "candidato_02", "candidato_03", "candidato_04",
                             "cambio posterior", "reparación previa", "Hallazgo simulado"):
                self.assertNotIn(excluded, context)
            self.assertIn("preparado", call["prompt"])
            self.assertIn("read-only", call["args"])
            self.assertIn("features.multi_agent=false", call["args"])
            self.assertIn("--ephemeral", call["args"])
            self.assertEqual(entry["revisor"]["limite_segundos"], 180)
            self.assertTrue(all(entry["integridad"].values()))
            directory = Path(entry["registro"])
            self.assertEqual(entry["instrucciones_sha256"], digest((directory / "revisor/entrada.txt").read_bytes()))
            self.assertEqual(json.loads((directory / "dictamen_validado.json").read_text()), CHANGES)
            self.assertIn("simulacion", (directory / "revisor/eventos.jsonl").read_text())
            self.assertIn("simulación", (directory / "revisor/stderr.txt").read_text())
            self.assertEqual((directory / "revisor/codex_version.txt").read_text(), "codex-simulado 1.0\n")
            self.assertEqual(entry["configuracion_efectiva"]["modelo"], "no consta")
        self.assertEqual(len({json.dumps(launcher.normalized_command(c["args"])) for c in calls}), 1)
        before = snapshot_tree(experiment)
        duplicate = self.run_experiment(experiment)
        self.assertEqual(duplicate["estado"], "rechazado")
        self.assertEqual(duplicate["codigo_salida"], 1)
        self.assertEqual(len(self.read_calls()), 4)
        self.assertEqual(snapshot_tree(experiment), before)

    def test_hashes_alterados_rechazados_antes_de_invocar(self):
        experiment = self.prepare()
        for relative in ("fuentes/evals/revisor/candidatos/candidato_01.py",
                         "fuentes/evals/revisor/instrucciones_case_01.md",
                         "evaluaciones/candidato_01/stderr.txt"):
            with self.subTest(path=relative):
                target = experiment / "preparacion" / relative
                original = target.read_bytes()
                target.write_bytes(original + b"alterado")
                result = self.run_experiment(experiment)
                self.assertEqual(result["codigo_salida"], 1)
                self.assertIn("Hashes", result["error"])
                self.assertFalse((experiment / "lanzamiento").exists())
                cli = self.cli("run", "--experiment", experiment)
                self.assertEqual(cli.returncode, 1)
                self.assertNotIn("iniciando", cli.stderr)
                self.assertNotIn("Revisión", cli.stderr)
                self.assertIn("Hashes de la preparación alterados", cli.stderr)
                self.assertIn(f"registro: {experiment}", cli.stderr)
                target.write_bytes(original)
        self.assertEqual(self.read_calls(), [])

    def test_lanzador_cambiado_rechazado_antes_de_invocar(self):
        experiment = self.prepare()
        with (self.root / "review_case.py").open("a") as out:
            out.write("\n# cambio posterior\n")
        result = self.run_experiment(experiment)
        self.assertEqual(result["codigo_salida"], 1)
        self.assertIn("cambió", result["error"])
        self.assertEqual(self.read_calls(), [])

    def test_json_invalido_detiene_y_conserva_salida(self):
        self.configure_fake(invalid=True)
        result = self.run_experiment(self.prepare())
        self.assert_stopped(result, "respuesta_invalida")
        self.assertIsNone(result["candidatos"][0]["dictamen"])
        raw = Path(result["candidatos"][0]["registro"]) / "revisor/respuesta_original.txt"
        self.assertEqual(raw.read_text(), "{JSON inválido")

    def test_fallo_tecnico_detiene_aunque_haya_dictamen_valido(self):
        self.configure_fake(exit_code=7)
        result = self.run_experiment(self.prepare())
        self.assert_stopped(result, "fallo_tecnico")
        entry = result["candidatos"][0]
        self.assertEqual(entry["revisor"]["codigo_salida"], 7)
        self.assertEqual(entry["dictamen"], APPROVAL)

    def test_timeout_detiene_y_conserva_eventos_parciales(self):
        self.configure_fake(block=True)
        with patch.object(review_case, "AGENT_TIMEOUT_SECONDS", 0.3):
            result = self.run_experiment(self.prepare())
        self.assert_stopped(result, "fallo_tecnico")
        entry = result["candidatos"][0]
        self.assertEqual(entry["revisor"]["estado"], "tiempo_agotado")
        self.assertIn("simulacion", (Path(entry["registro"]) / "revisor/eventos.jsonl").read_text())

    def test_workspace_alterado_detiene_con_integridad_falsa(self):
        self.configure_fake(mutate_workspace=True)
        result = self.run_experiment(self.prepare())
        self.assert_stopped(result, "integridad_alterada")
        self.assertFalse(result["candidatos"][0]["integridad"]["workspace_intacto"])

    def test_preparacion_alterada_durante_revision_detiene(self):
        experiment = self.prepare()
        target = experiment / "preparacion/fuentes/evals/revisor/instrucciones_case_02.md"
        self.configure_fake(mutate_path=str(target))
        result = self.run_experiment(experiment)
        self.assert_stopped(result, "fallo_evidencia")
        self.assertIn("preparación cambió", result["error"])
        entry = result["candidatos"][0]
        self.assertEqual(json.loads((Path(entry["registro"]) / "resultado.json").read_text()), entry)

    def test_evidencia_previa_alterada_detiene_siguiente_revision(self):
        experiment = self.prepare()
        target = experiment / "lanzamiento/candidato_01/revisor/respuesta_original.txt"
        self.configure_fake(mutate_path=str(target), mutate_on=2)
        result = self.run_experiment(experiment)
        self.assert_stopped(result, "fallo_evidencia", count=2)
        self.assertIn("revisión anterior", result["error"])

    def test_preflight_incompatible_no_invoca_ni_pasa_al_siguiente(self):
        self.configure_fake(incompatible=True)
        experiment = self.prepare()
        cli = self.cli("run", "--experiment", experiment)
        self.assertEqual(cli.returncode, 1)
        self.assertNotIn("iniciando", cli.stderr)
        self.assertIn("candidato_01: fallo_tecnico.", cli.stderr)
        self.assertIn("cli_incompatible", cli.stderr)
        self.assertIn(f"registro: {experiment / 'lanzamiento/candidato_01'}", cli.stderr)
        result = json.loads((experiment / "lanzamiento/resultado.json").read_text())
        self.assertEqual(result["codigo_salida"], 1)
        self.assertEqual(self.read_calls(), [])
        self.assertEqual(result["candidatos"][0]["invocaciones"], 0)
        self.assertEqual(result["candidatos"][0]["revisor"]["estado"], "cli_incompatible")
        self.assertTrue(all(e["estado"] == "pendiente" for e in result["candidatos"][1:]))

    def test_fallo_al_guardar_reserva_no_permite_repetir(self):
        experiment = self.prepare()
        with patch.object(launcher, "save_json", side_effect=OSError("disco simulado lleno")):
            result = self.run_experiment(experiment)
        self.assertEqual(result["codigo_salida"], 1)
        self.assertTrue((experiment / "lanzamiento").is_dir())
        self.assertEqual(self.run_experiment(experiment)["estado"], "rechazado")
        self.assertEqual(self.read_calls(), [])

    @unittest.skipUnless(os.name == "posix", "La comprobación de SIGINT requiere POSIX")
    def test_lanzamiento_concurrente_interrupcion_y_reserva_permanente(self):
        self.configure_fake(block=True)
        experiment = self.prepare()
        command = [sys.executable, "-B", "evaluate_reviewer.py", "run", "--experiment", str(experiment)]
        with subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env={**os.environ, "PATH": str(self.temporary) + os.pathsep + os.environ.get("PATH", "")}) as first:
            try:
                deadline = time.monotonic() + 10
                while not self.calls.exists() and first.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(self.calls.exists(), "El proceso simulado no comenzó")
                # El aviso debe ser legible por una tubería antes de terminar el proceso.
                ready, _, _ = select.select([first.stderr], [], [], 3)
                self.assertTrue(ready, "No se recibió progreso inmediato")
                self.assertEqual(first.stderr.readline().decode(),
                                 "Revisión 1/4: iniciando candidato_01…\n")
                self.assertIsNone(first.poll())
                duplicate = self.cli("run", "--experiment", experiment)
                self.assertEqual(duplicate.returncode, 1, duplicate.stdout + duplicate.stderr)
                self.assertIn("ya reservado", duplicate.stderr)
                self.assertNotIn("Revisión", duplicate.stderr)
                self.assertEqual(len(self.read_calls()), 1)
                first.send_signal(signal.SIGINT)
                stdout, stderr = first.communicate(timeout=10)
                self.assertEqual(first.returncode, 1, stdout + stderr)
                self.assertIn("candidato_01: interrumpida.", stderr.decode())
                self.assertIn("Detenido:", stderr.decode())
                self.assertNotIn("Revisión 2/4", stderr.decode())
            finally:
                if first.poll() is None:
                    first.send_signal(signal.SIGINT)
                    first.communicate(timeout=10)
        result = json.loads((experiment / "lanzamiento/resultado.json").read_text())
        self.assert_stopped(result, "interrumpida")
        entry = result["candidatos"][0]
        self.assertEqual(entry["revisor"]["codigo_salida"], -signal.SIGKILL)
        self.assertIn("simulacion", (Path(entry["registro"]) / "revisor/eventos.jsonl").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(self.read_calls()[0]["pid"], 0)
        before = snapshot_tree(experiment)
        self.assertEqual(self.cli("run", "--experiment", experiment).returncode, 1)
        self.assertEqual(snapshot_tree(experiment), before)

    def test_cli_prepare_run_y_argumentos_incorrectos(self):
        for args in ((), ("run",), ("prepare", "--experiment", "irrelevante")):
            with self.subTest(args=args):
                incorrect = self.cli(*args)
                self.assertEqual(incorrect.returncode, 2)
                self.assertNotIn("Preparando", incorrect.stderr)
                self.assertNotIn("Revisión", incorrect.stderr)
        result = self.cli("prepare")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "Preparando materiales y comprobando candidatos.\n")
        self.assertTrue(result.stdout.startswith("Estado: preparada; código: 0\nExperimento: "))
        self.assertNotIn("Preparando", result.stdout)
        self.assertEqual(self.read_calls(), [])
        experiment = next(path for path in (self.root / "runs").iterdir() if path.name != "historico")
        self.configure_fake(changes=True)
        result = self.cli("run", "--experiment", experiment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = []
        for number in range(1, 5):
            expected.extend([f"Revisión {number}/4: iniciando candidato_{number:02d}…",
                             f"candidato_{number:02d}: completada; dictamen: solicitar_cambios."])
        self.assertEqual(result.stderr.splitlines(), expected)
        self.assertTrue(result.stdout.startswith("Estado: completado; código: 0\nExperimento: "))
        self.assertNotIn("Revisión", result.stdout)
        self.assertNotIn("Estado:", result.stderr)
        for private in ("Revisa `candidato.py`", "simulacion", "stderr de la simulación", "Hallazgo simulado"):
            self.assertNotIn(private, result.stdout + result.stderr)
        self.assertEqual(len(self.read_calls()), 4)

    def test_funciones_reutilizables_silenciosas_por_defecto(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.run_experiment(self.prepare())
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(len(self.read_calls()), 4)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_progreso_de_fallo_tecnico_detiene_y_mantiene_resumen(self):
        self.configure_fake(exit_code=7)
        experiment = self.prepare()
        result = self.cli("run", "--experiment", experiment)
        self.assertEqual(result.returncode, 1)
        lines = result.stderr.splitlines()
        self.assertEqual(lines[0], "Revisión 1/4: iniciando candidato_01…")
        self.assertEqual(lines[1], "candidato_01: fallo_tecnico; dictamen: aprobar.")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[2].startswith("Detenido: Detención en candidato_01: fallo_tecnico"))
        self.assertIn("revisor: finalizada, código 7", lines[2])
        self.assertIn(f"registro: {experiment / 'lanzamiento/candidato_01'}", lines[2])
        self.assertNotIn("iniciando candidato_02", result.stderr)
        self.assertTrue(result.stdout.startswith("Estado: incompleto; código: 1\n"))
        for number in range(2, 5):
            self.assertIn(f"candidato_{number:02d}: pendiente; invocaciones: 0", result.stdout)
        self.assertNotIn("Detenido:", result.stdout)
        self.assertNotIn("Respuesta simulada", result.stdout + result.stderr)
        self.assertNotIn("stderr de la simulación", result.stderr)
        self.assertEqual(len(self.read_calls()), 1)

    def test_progreso_de_json_invalido_no_anuncia_revisiones_posteriores(self):
        self.configure_fake(invalid=True)
        experiment = self.prepare()
        result = self.cli("run", "--experiment", experiment)
        self.assertEqual(result.returncode, 1)
        lines = result.stderr.splitlines()
        self.assertEqual(lines[:2], ["Revisión 1/4: iniciando candidato_01…",
                                    "candidato_01: respuesta_invalida."])
        self.assertEqual(len(lines), 3)
        record = json.loads((experiment / "lanzamiento/candidato_01/resultado.json").read_text())
        self.assertIn(record["error_respuesta"], lines[2])
        self.assertIn(f"registro: {experiment / 'lanzamiento/candidato_01'}", lines[2])
        self.assertNotIn("Revisión 2/4", result.stderr)
        self.assertNotIn("{JSON inválido", result.stderr)
        self.assertEqual(len(self.read_calls()), 1)

    def test_progreso_rechaza_reserva_existente_sin_anunciar_invocacion(self):
        experiment = self.prepare()
        (experiment / "lanzamiento").mkdir()
        before = snapshot_tree(experiment)
        result = self.cli("run", "--experiment", experiment)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "Detenido: Experimento ya reservado: no se permite repetir ni reanudar; "
                         f"registro: {experiment}.\n")
        self.assertNotIn("iniciando", result.stderr)
        self.assertTrue(result.stdout.startswith("Estado: rechazado; código: 1\n"))
        self.assertEqual(snapshot_tree(experiment), before)
        self.assertEqual(self.read_calls(), [])

    def test_progreso_prepare_fallida_da_motivo_y_registro(self):
        (self.root / "evals/revisor/candidatos/candidato_01.py").write_text(
            "def calcular_totales_por_asignatura(sesiones):\n    return {}\n")
        result = self.cli("prepare")
        self.assertEqual(result.returncode, 1)
        lines = result.stderr.splitlines()
        self.assertEqual(lines[0], "Preparando materiales y comprobando candidatos.")
        self.assertEqual(len(lines), 2)
        self.assertIn("Detenido: Las pruebas originales no terminaron correctamente", lines[1])
        experiment = next(path for path in (self.root / "runs").iterdir() if path.name != "historico")
        self.assertIn(f"registro: {experiment}", lines[1])
        self.assertTrue(result.stdout.startswith("Estado: fallida; código: 1\n"))
        self.assertEqual(self.read_calls(), [])

    def test_instrucciones_conservan_criterios_y_esquema_de_produccion(self):
        for case_id, source in (("case_01", "reviewer_case_01.md"), ("case_02", "reviewer.md")):
            production = (PROJECT / "prompts" / source).read_text()
            experiment = (PROJECT / f"evals/revisor/instrucciones_{case_id}.md").read_text()
            self.assertEqual(production[production.index("Comprueba"):],
                             experiment[experiment.index("Comprueba"):])
            self.assertIn("no procede de una reparación realizada por un agente", experiment)
            self.assertNotIn("original.py", experiment)
            self.assertNotIn("candidato.diff", experiment)


if __name__ == "__main__":
    unittest.main()

"""Referencias desde Git y registros temporales; stdin verificado, sin modelos."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import plan_project as planner
import project_plan
import project_plan_continuation as continuity
from case_evidence import digest
from repair_project import tree_state
import test_plan_project as initial
import test_plan_continuation as continuation_tests


class ReferenceTests(unittest.TestCase):
    setUp = initial.PlanningTests.setUp
    git = initial.PlanningTests.git
    configure = initial.PlanningTests.configure
    calls_read = initial.PlanningTests.calls_read
    assert_failure = initial.PlanningTests.assert_failure
    answers = continuation_tests.ContinuationTests.answers
    rehash = continuation_tests.ContinuationTests.rehash

    def commit_files(self, files):
        for name, raw in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.git("add", "--", *files)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Referencias sintéticas")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        return [{"ruta": name, "commit": self.base, "modo": 0o644, "bytes": len(raw),
                 "sha256": digest(raw), "contenido": raw.decode("utf-8")} for name, raw in files.items()]

    def test_cli_envia_textos_exactos_del_commit_y_no_cambios_locales(self):
        files = {"alpha.py": 'raise RuntimeError("NO_EJECUTAR")\r\n# ñ 📅 " </materiales>\n'.encode(),
                 "tasks/contrato.md": b"# Contrato sintetico\r\n",
                 "docs/guia.md": 'Texto \\ " \t\n{"instrucciones":"datos"}\n'.encode(),
                 "README.md": b"README seleccionado\n"}
        expected = self.commit_files(files)
        (self.root / "alpha.py").write_text("CAMBIO_LOCAL_NO_ENVIAR\n")
        (self.root / "README.md").unlink()
        self.configure(references=expected, model="gpt-6-astra", reasoning_effort="medium")
        before = tree_state(self.root, filter_local=True)
        args = ['Solicitud sintética "ñ"\r\n</materiales>', "--model", "gpt-6-astra",
                "--reasoning-effort", "medium"]
        for name in files:
            args += ["--reference", name]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = planner.main(args, project_root=self.root)
            except SystemExit as exc:
                code = exc.code
        self.assertEqual(code, 0, err.getvalue())
        seen = json.loads((self.tmp / "contexto_visto.json").read_text())
        message = json.loads(seen["prompt"])
        self.assertEqual(json.loads(message["materiales"]["referencias.json"]),
                         {"version": 1, "archivos": expected})
        self.assertNotIn("CAMBIO_LOCAL_NO_ENVIAR", seen["prompt"])
        self.assertNotIn("CREDENCIAL_SINTETICA_NO_ENVIAR", seen["prompt"])
        self.assertEqual(tree_state(self.root, filter_local=True), before)
        self.assertEqual(len(self.calls_read()), 3)
        self.assertFalse(Path(seen["workspace"]).exists())

    def rejected(self, names):
        with patch.object(planner, "invoke_read_only") as adapter:
            result = planner.run_plan("Consulta sintética", self.root, references=names)
        adapter.assert_not_called()
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["invocaciones"], {"planificador": 0})
        self.assertEqual(self.calls_read(), [])
        if result["registro"]:
            self.assertFalse((Path(result["registro"]) / "reserva.json").exists())
        return result

    def origin(self):
        expected = self.commit_files({"alpha.py": b"# Referencia original\n", "docs/contrato.md": b"Reglas\n"})
        self.configure(plan=initial.ambiguous(), references=expected)
        result = planner.run_plan("Consulta sintética", self.root, references=[i["ruta"] for i in expected])
        self.assertEqual(result["codigo_salida"], 0, result)
        return Path(result["registro"]), expected

    def test_rutas_ambiguas_privadas_fuera_de_alcance_y_duplicadas(self):
        for name in ("/alpha.py", "./alpha.py", "docs/../README.md", "docs//x.md", "docs/./x.md",
                     "docs/x.md/", "docs\\x.md", "docs/.oculto.md", "docs/runs/x.md", "docs/\0.md",
                     "", "README.txt", "sub/alpha.py", "runs/x.md", ".env", "tasks/config/x.json"):
            with self.subTest(name=name):
                self.rejected([name])
        self.rejected(["alpha.py", "alpha.py"])

    def test_ausente_no_se_sustituye_por_archivo_sin_commit(self):
        for name in ("ausente.py", "pendiente.py", "docs/ausente.md"):
            with self.subTest(name=name):
                self.rejected([name])

    def test_rechaza_enlaces_componentes_y_submodulos_de_git(self):
        (self.root / "docs").symlink_to("folder.py", target_is_directory=True)
        self.git("add", "docs")
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.base + ",submodule.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Tipos no regulares")
        for name in ("linked.py", "folder.py", "docs/x.md", "submodule.py"):
            with self.subTest(name=name):
                self.rejected([name])

    def test_modo_y_commit_fijos_no_dependen_del_checkout(self):
        expected = self.commit_files({"alpha.py": b"# Base exacta\n"})
        self.git("update-index", "--chmod=+x", "alpha.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Modo ejecutable en Git")
        base = self.git("rev-parse", "HEAD").decode().strip()
        expected[0].update(commit=base, modo=0o755)
        self.commit_files({"alpha.py": b"# Otra base\n"})
        (self.root / "alpha.py").unlink()
        (self.root / "alpha.py").symlink_to(".env")
        self.assertEqual(project_plan.read_references(self.root, base, ["alpha.py"]),
                         {"version": 1, "archivos": expected})

    def test_markdown_anidado_unicode_y_pathspec_literal(self):
        expected = self.commit_files({"docs/sub/ñ[1].md": b"literal\n", "módulo-lectura.py": b"# leer\n",
                                      "docs/sub/otro.md": b"no enviar"})
        self.assertEqual(project_plan.read_references(self.root, self.base, [i["ruta"] for i in expected[:2]]),
                         {"version": 1, "archivos": expected[:2]})

    def test_utf8_invalido_se_rechaza_antes_de_cli_y_reserva(self):
        (self.root / "alpha.py").write_bytes(b"\xff\xfe\x00")
        self.git("add", "alpha.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "UTF8 inválido")
        self.rejected(["alpha.py"])

    def test_diecisiete_referencias_rechazadas_antes_de_git_o_cli(self):
        with patch.object(project_plan, "git") as git:
            self.rejected([f"docs/{i}.md" for i in range(17)])
        git.assert_not_called()

    def test_limite_dieciséis_referencias_y_texto_vacio(self):
        expected = self.commit_files({f"docs/{i}.md": b"" for i in range(16)})
        self.configure(references=expected)
        result = planner.run_plan("Consulta sintética", self.root, references=[i["ruta"] for i in expected])
        self.assertEqual(result["codigo_salida"], 0, result)
        continuity.load_parent(result["registro"])

    def test_limites_inclusivos_128k_por_archivo_y_un_mib_total(self):
        expected = self.commit_files({f"docs/{i}.md": ("ñ" * 65536).encode() for i in range(8)})
        self.configure(references=expected)
        result = planner.run_plan("Consulta sintética", self.root, references=[i["ruta"] for i in expected])
        self.assertEqual(result["codigo_salida"], 0, result)
        parent = continuity.load_parent(result["registro"])
        self.assertEqual(sum(i["bytes"] for i in json.loads(parent.materials["referencias.json"])["archivos"]),
                         1024 * 1024)

    def test_tamanos_excesivos_se_rechazan_antes_de_leer_blobs(self):
        files = {f"docs/{i}.md": b"a" * (128 * 1024) for i in range(8)}
        files.update({"docs/exceso.md": b"b", "docs/grande.md": b"x" * (128 * 1024 + 1)})
        self.commit_files(files)
        for names in (["docs/grande.md"], [f"docs/{i}.md" for i in range(8)] + ["docs/exceso.md"]):
            with self.subTest(names=names), patch.object(project_plan, "git", wraps=project_plan.git) as git:
                self.rejected(names)
            self.assertFalse(any(call.args[1:3] == ("cat-file", "blob") for call in git.call_args_list))

    def test_mensaje_completo_con_escapes_conserva_limite_cuatro_mib(self):
        files = {f"docs/{i}.md": b"\x00" * (128 * 1024) for i in range(8)}
        self.commit_files(files)
        result = self.rejected(list(files))
        self.assertIn("4 MiB", result["fallo"]["mensaje"])

    def test_reference_excluye_continuacion_y_exportaciones_antes_de_leer_origen(self):
        for extra in ([], ["--answers-template", "plantilla.json"], ["--decisions-template", "plantilla.json"]):
            with self.subTest(extra=extra), patch.object(planner, "run_plan") as run, \
                    patch.object(planner, "export_template") as export, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    planner.main(["--from-plan", "no-leer", "--reference", "alpha.py", *extra], project_root=self.root)
                self.assertEqual(caught.exception.code, 2)
                run.assert_not_called()
                export.assert_not_called()
        self.assertEqual(self.calls_read(), [])

    def test_continuaciones_heredan_bytes_sin_releer_git_y_admiten_modelo_esfuerzo(self):
        parent, expected = self.origin()
        original = (parent / "materiales/referencias.json").read_bytes()
        self.commit_files({"alpha.py": b"# Checkout posterior NO_ENVIAR\n"})
        (self.root / "docs/contrato.md").unlink()
        answer = self.answers(parent, "Solo consulta sintética")
        self.configure(plan=initial.ambiguous(), references=expected, model="gpt-6-astra", reasoning_effort="medium")
        before = tree_state(parent)
        with patch.object(planner, "read_references", side_effect=AssertionError("No releer Git")):
            result = planner.run_plan(None, self.root, from_plan=parent, answers=answer,
                                      model="gpt-6-astra", reasoning_effort="medium")
        self.assertEqual(result["codigo_salida"], 0, result)
        child = continuity.load_parent(result["registro"])
        self.assertEqual(child.materials["referencias.json"], original)
        self.assertEqual(tree_state(parent), before)
        seen = json.loads((self.tmp / "contexto_visto.json").read_text())
        self.assertNotIn("Checkout posterior NO_ENVIAR", seen["prompt"])
        self.assertFalse(Path(seen["workspace"]).exists())

    def test_evidencia_alterada_no_se_acepta_ni_con_hash_exterior_actualizado(self):
        parent, _ = self.origin()
        target = parent / "materiales/referencias.json"
        value = json.loads(target.read_bytes())
        value["archivos"][0]["contenido"] = "alterado"
        target.write_bytes(continuity.encoded(value))
        with self.assertRaisesRegex(ValueError, "Hash de evidencia"):
            continuity.load_parent(parent)
        self.rehash(parent)
        with self.assertRaisesRegex(ValueError, "Contenido de referencia alterado"):
            continuity.load_parent(parent)
        calls = self.calls_read()
        with patch.object(planner, "invoke_read_only") as adapter:
            result = planner.run_plan(None, self.root, from_plan=parent, answers=self.tmp / "ausente.json")
        adapter.assert_not_called()
        self.assertEqual(result["invocaciones"], {"planificador": 0})
        self.assertEqual(self.calls_read(), calls)

    def test_metadatos_y_textos_se_validan_sin_coerciones(self):
        expected = self.commit_files({"docs/contrato.md": b"x"})
        context = project_plan.base_context(self.root)
        metadata = [{k: v for k, v in i.items() if k != "contenido"} for i in expected]
        context["referencias"] = metadata
        value = {"version": 1, "archivos": expected}
        for key, bad in (("commit", "0" * 40), ("modo", 0o664), ("bytes", True),
                         ("bytes", 2), ("sha256", "0" * 64), ("ruta", "runs/privado.md"),
                         ("contenido", "y"), ("contenido", "\ud800")):
            altered = copy.deepcopy(value)
            altered["archivos"][0][key] = bad
            with self.subTest(key=key, bad=repr(bad)), self.assertRaises((ValueError, UnicodeError)):
                raw = json.dumps(altered, ensure_ascii=True).encode()
                project_plan.validate_reference_material(raw, context)
        for bad in (None, continuity.encoded({"version": 1, "archivos": []}),
                    continuity.encoded(dict(value, extra=True))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                project_plan.validate_reference_material(bad, context)
        with self.assertRaises(ValueError):
            project_plan.validate_reference_material(continuity.encoded(value), project_plan.base_context(self.root))

    def test_continuacion_no_admite_reformatear_referencias_aunque_recalcule_hashes(self):
        parent, expected = self.origin()
        answer = self.answers(parent, "Solo consulta sintética")
        self.configure(plan=initial.ambiguous(), references=expected)
        result = planner.run_plan(None, self.root, from_plan=parent, answers=answer)
        self.assertEqual(result["codigo_salida"], 0, result)
        child = Path(result["registro"])
        continuity.load_parent(child)
        target = child / "materiales/referencias.json"
        target.write_bytes(target.read_bytes() + b"\n")
        # Rehacer las correspondencias locales deja como única discrepancia
        # los bytes heredados: ni siquiera ese reformateo se admite.
        provenance_path = child / "procedencia.json"
        provenance = json.loads(provenance_path.read_bytes())
        provenance["materiales"] = tree_state(child / "materiales")
        prompt_path = child / "planificador/entrada.txt"
        prompt = json.loads(prompt_path.read_bytes())
        prompt["materiales"]["referencias.json"] = target.read_bytes().decode()
        prompt_path.write_bytes(continuity.encoded(prompt))
        provenance["prompt_sha256"] = digest(prompt_path.read_bytes())
        provenance_path.write_bytes(continuity.encoded(provenance))
        self.rehash(child)
        with self.assertRaisesRegex(ValueError, "Referencias originales alteradas"):
            continuity.load_parent(child)

    def test_fixture_rechaza_stdin_sin_referencias_aunque_workspace_sea_correcto(self):
        expected = self.commit_files({"alpha.py": "# Sintético\n".encode()})
        self.configure(references=expected)
        original_adapter = planner.invoke_read_only
        def omit(workspace, final, prompt, log, **kwargs):
            message = json.loads(prompt)
            del message["materiales"]["referencias.json"]
            return original_adapter(workspace, final, continuity.encoded(message), log, **kwargs)
        with patch.object(planner, "invoke_read_only", side_effect=omit):
            result = planner.run_plan("Consulta sintética", self.root, references=["alpha.py"])
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["invocaciones"], {"planificador": 1})
        self.assertEqual(result["respuesta_tipo"], "ausente")
        self.assertFalse((Path(result["registro"]) / "propuesta.json").exists())
        self.assertIn("AssertionError", (Path(result["registro"]) / "planificador/stderr.txt").read_text())

    def test_sin_referencias_conserva_materiales_y_lector_historicos(self):
        self.configure(plan=initial.ambiguous())
        result = planner.run_plan("Consulta sintética", self.root)
        self.assertEqual(result["codigo_salida"], 0, result)
        parent = Path(result["registro"])
        self.assertEqual(set(continuity.load_parent(parent).materials), set(continuity.MATERIALS))
        answer = self.answers(parent, "Consulta sintética")
        child = planner.run_plan(None, self.root, from_plan=parent, answers=answer)
        self.assertEqual(child["codigo_salida"], 0, child)
        self.assertNotIn("referencias.json", continuity.load_parent(child["registro"]).materials)

    def test_leer_infraestructura_protegida_no_autoriza_modificarla(self):
        expected = project_plan.read_references(self.root, self.base, ["review_case.py"])["archivos"]
        plan = initial.concrete()
        plan["archivos"] = [{"ruta": "review_case.py", "accion": "modificar", "proposito": "No permitido"}]
        self.configure(plan=plan, references=expected)
        result = planner.run_plan("Consulta sintética", self.root, references=["review_case.py"])
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["fallo"]["tipo"], "respuesta_invalida")
        self.assertIn("Infraestructura protegida", result["fallo"]["mensaje"])

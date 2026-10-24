"""Repositorios y CLI sintéticos; nunca se llama a un modelo real ni a sockets."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import plan_project as planner
import project_plan
import project_task_config
import review_case
from case_evidence import digest
from process_environment import process_environment
from repair_case import ProcessInterrupted
from repair_project import tree_state


HELP = "--model --config --sandbox read-only --cd --skip-git-repo-check --ephemeral --json --output-last-message --output-schema"


def concrete():
    return {
        "version": 1, "objetivo": "Consultar un marcador sintético.",
        "viabilidad": "dentro_del_alcance",
        "requisitos_interpretados": ["Devolver el marcador solicitado."],
        "alcance": ["Consulta en memoria con biblioteca estándar."],
        "exclusiones": ["No persistir datos."],
        "archivos": [{"ruta": "alpha.py", "accion": "modificar", "proposito": "Exponer la consulta."},
                     {"ruta": "consulta.py", "accion": "crear", "proposito": "Añadir una entrada CLI."}],
        "criterios_aceptacion": [{"descripcion": "Una consulta conocida devuelve su valor.",
                                 "ejemplos": [{"entrada": "consulta alfa", "resultado_esperado": "valor alfa"}]}],
        "preguntas_pendientes": [], "supuestos": [], "limitaciones": ["Plan sintético sin inspección de fuentes."],
    }


def ambiguous():
    plan = concrete()
    plan.update(objetivo="Definir una API de reservas.", viabilidad="pendiente_de_aclaracion",
                requisitos_interpretados=["Ofrecer una API de reservas."], alcance=[], archivos=[],
                criterios_aceptacion=[], supuestos=["La interfaz podría ser HTTP; falta confirmarlo."],
                preguntas_pendientes=["¿Qué operaciones incluye?", "¿Debe persistir reservas?",
                                     "¿Qué interfaz necesita el usuario?"])
    return plan


def blocked():
    plan = ambiguous()
    plan.update(viabilidad="fuera_del_alcance", preguntas_pendientes=[],
                supuestos=[], limitaciones=["Una aplicación móvil y PostgreSQL exceden Python raíz y biblioteca estándar."])
    return plan


class PlanningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="planificacion-sintetica-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "proyecto con espacios"
        self.root.mkdir()
        (self.root / "alpha.py").write_text("raise AssertionError('FUENTE_NO_EJECUTAR_NI_ENVIAR')\n")
        (self.root / "review_case.py").write_text("# Infraestructura sintética protegida\n")
        (self.root / "README.md").write_text("CONTENIDO_NO_ENVIAR\n")
        (self.root / "linked.py").symlink_to("alpha.py")
        (self.root / "folder.py").mkdir()
        (self.root / "folder.py/data.txt").write_text("directorio, no módulo\n")
        self.git("init", "-q")
        self.git("add", "alpha.py", "review_case.py", "README.md", "linked.py", "folder.py")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Base sintética")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        (self.root / "pendiente.py").write_text("# Cambio pendiente del usuario\n")
        (self.root / ".env").write_text("CREDENCIAL_SINTETICA_NO_ENVIAR\n")
        (self.root / "runs/historico").mkdir(parents=True)
        (self.root / "runs/historico/resultado.json").write_text('{"historico": true}\n')
        self.settings = self.tmp / "opciones.json"
        self.calls = self.tmp / "llamadas.jsonl"
        self.fake = self.tmp / "codex-simulado"
        self.configure()
        self.addCleanup(patch.stopall)
        patch.object(review_case, "CODEX_EXECUTABLE", str(self.fake)).start()

    def git(self, *args):
        with process_environment("evaluation") as environment:
            return subprocess.run(["git", "-C", str(self.root), *args], env=environment,
                                  capture_output=True, check=True, timeout=10).stdout

    def configure(self, *, plan=None, raw=None, mode="normal", code=0,
                  model=None, reasoning_effort=None, cli_help=HELP, references=None):
        self.settings.write_text(json.dumps({"raw": json.dumps(concrete() if plan is None else plan)
                                            if raw is None else raw, "mode": mode, "code": code,
                                            "model": model, "reasoning_effort": reasoning_effort,
                                            "references": references}))
        self.fake.write_text(f'''#!{sys.executable}
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
options = json.loads(Path({str(self.settings)!r}).read_text())
mode = options["mode"]
with Path({str(self.calls)!r}).open("a") as stream:
    stream.write(json.dumps({{"args": args}}) + "\\n")
if args == ["--version"]:
    print("CLI simulada, no modelo", flush=True)
    if mode == "version_timeout": time.sleep(60)
    sys.exit(7 if mode == "version_fail" else 0)
if args == ["exec", "--help"]:
    print("incompatible" if mode == "incompatible" else {cli_help!r}, flush=True)
    if mode == "vanish": Path(sys.argv[0]).unlink()
    if mode == "tamper_help": Path("solicitud.txt").write_text("alterado antes de reservar")
    sys.exit(0)
assert args[0] == "exec" and args[-1] == "-"
assert args[args.index("--sandbox") + 1] == "read-only"
assert args[args.index("--cd") + 1] == str(Path.cwd())
assert "--ephemeral" in args and "--json" in args
assert "resume" not in args and "fork" not in args
assert 'approval_policy="never"' in args and 'web_search="disabled"' in args
assert "features.multi_agent=false" in args
# Comprobar argv antes de emitir la respuesta prefijada, no solo el workspace.
if options["model"] is None:
    assert "--model" not in args
else:
    assert args.count("--model") == 1
    assert args[args.index("--model") + 1] == options["model"]
configs = [args[i + 1] for i, arg in enumerate(args) if arg == "--config"]
expected_configs = ['approval_policy="never"', 'web_search="disabled"', "features.multi_agent=false"]
if options["reasoning_effort"] is not None:
    expected_configs.append("model_reasoning_effort=" + json.dumps(options["reasoning_effort"]))
assert configs == expected_configs
root = Path({str(self.root)!r})
logs = [p for p in (root/"runs").iterdir() if "_plan_project_" in p.name]
log = max(logs, key=lambda p: p.stat().st_mtime_ns)
summary = json.loads((log/"resultado.json").read_text())
reservation = json.loads((log/"reserva.json").read_text())
assert summary["invocaciones"] == {{"planificador": 1}}
assert reservation["rol"] == "planificador" and reservation["limite_segundos"] == 300
seen = {{"workspace": str(Path.cwd()),
        "archivos": {{p.name: p.read_bytes().decode("utf-8") for p in Path.cwd().iterdir()}},
        "prompt": sys.stdin.buffer.read().decode("utf-8"), "reserva_previa": True}}
Path({str(self.tmp / "contexto_visto.json")!r}).write_text(json.dumps(seen))
# La respuesta prefijada solo se emite si stdin entrega todos los materiales.
message = json.loads(seen["prompt"])
assert set(message) == {{"instrucciones", "materiales"}}
assert message["instrucciones"].encode("utf-8") == (log/"materiales/instrucciones.md").read_bytes()
names = {{"solicitud.txt", "contexto.json", "respuesta.schema.json"}}
if (log/"materiales/continuacion.json").exists():
    names.add("continuacion.json")
if options["references"] is not None:
    names.add("referencias.json")
assert set(message["materiales"]) == names
for name, text in message["materiales"].items():
    assert text.encode("utf-8") == (log/"materiales"/name).read_bytes()
    assert text.encode("utf-8") == Path(name).read_bytes()
assert Path(args[args.index("--output-schema") + 1]).read_bytes() == message["materiales"]["respuesta.schema.json"].encode("utf-8")
if options["references"] is not None:
    assert json.loads(message["materiales"]["referencias.json"]) == {{"version": 1, "archivos": options["references"]}}
    context = json.loads(message["materiales"]["contexto.json"])
    assert context["referencias"] == [{{k: v for k, v in item.items() if k != "contenido"}}
                                     for item in options["references"]]
if "continuacion.json" in names:
    data = json.loads(message["materiales"]["continuacion.json"])
    provenance = json.loads((log/"procedencia.json").read_text())["continuacion"]
    parent = Path(provenance["padre"]["registro"])
    proposal = json.loads((parent/"propuesta.json").read_text())
    fields = {{"version", "propuesta_anterior_del_modelo", "preguntas_identificadas",
               "respuestas_explicitas_del_usuario", "preguntas_sin_responder"}}
    if data["version"] == 2:
        fields.update(("supuestos_identificados", "decisiones_explicitas_del_usuario", "supuestos_sin_decidir"))
        assert data["supuestos_sin_decidir"] == provenance["supuestos_anteriores"]
        assert data["decisiones_explicitas_del_usuario"] == [
            {{k: item[k] for k in ("id", "supuesto", "decision", "explicacion", "alternativa")}}
            for item in provenance["decisiones_confirmadas"]]
    assert set(data) == fields
    assert data["propuesta_anterior_del_modelo"] == proposal["propuesta"]
    assert data["respuestas_explicitas_del_usuario"] == provenance["respuestas_confirmadas"]
    assert data["preguntas_sin_responder"] == provenance["pendientes_anteriores"]
    for name in ("solicitud.txt", "contexto.json", *(["referencias.json"] if options["references"] is not None else [])):
        assert message["materiales"][name].encode("utf-8") == (parent/"materiales"/name).read_bytes()
print('{{"type":"turn.completed","simulado":true}}', flush=True)
print("Diagnóstico de la CLI simulada", file=sys.stderr, flush=True)
final = Path(args[args.index("--output-last-message") + 1])
if mode == "linked_response": final.symlink_to(root/"alpha.py")
elif mode != "missing_response": final.write_text(options["raw"])
if mode == "workspace_tamper": Path("solicitud.txt").write_text("alterado")
if mode == "project_tamper": (root/"alpha.py").write_text("# alterado")
if mode == "timeout": time.sleep(60)
sys.exit(options["code"])
''')
        self.fake.chmod(0o755)

    def run_plan(self, request="Añade una consulta de marcador sin persistencia."):
        return planner.run_plan(request, self.root)

    def calls_read(self):
        return [json.loads(line)["args"] for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def assert_failure(self, result, kind, count):
        self.assertEqual(result["codigo_salida"], 1, result)
        self.assertEqual(result["estado"], "fallo_tecnico")
        self.assertEqual(result["fallo"]["tipo"], kind)
        self.assertEqual(result["invocaciones"], {"planificador": count})
        if result["registro"]:
            log = Path(result["registro"])
            self.assertFalse((log / "propuesta.json").exists())
            self.assertFalse((log / "propuesta.md").exists())
            self.assertEqual((log / "reserva.json").exists(), bool(count))

    def test_propuesta_concreta_procedencia_y_registro_completos(self):
        request = "  Añade una consulta de marcador sin persistencia.  "
        before = tree_state(self.root, filter_local=True)
        result = self.run_plan(request)
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["estado"], "borrador")
        self.assertFalse(result["aprobada"])
        self.assertEqual(result["invocaciones"], {"planificador": 1})
        log = Path(result["registro"])
        saved = json.loads((log / "propuesta.json").read_text())
        self.assertEqual(saved["solicitud_original"], request)
        self.assertEqual(saved["commit_base"], self.base)
        self.assertEqual(saved["propuesta"], concrete())
        self.assertTrue(saved["procedencia"]["requiere_revision_humana"])
        self.assertEqual(saved["procedencia"]["rol"], "planificador")
        self.assertEqual((log / "materiales/solicitud.txt").read_text(), request)
        self.assertEqual(saved["procedencia"]["respuesta_sha256"],
                         digest((log / "planificador/respuesta_original.txt").read_bytes()))
        self.assertEqual(json.loads((log / "resultado.json").read_text()), result)
        for name, expected in result["artefactos_sha256"].items():
            self.assertEqual(digest((log / name).read_bytes()), expected)
        self.assertIn("planificador/version/resultado.json", result["artefactos_sha256"])
        self.assertEqual(tree_state(self.root, filter_local=True), before)
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.base)
        self.assertEqual((self.root / "runs/historico/resultado.json").read_text(), '{"historico": true}\n')
        self.assertFalse((self.root / "tasks").exists())
        self.assertEqual(len(self.calls_read()), 3)
        self.assertTrue(all(result["integridad"].values()))

    def test_aclaraciones_sin_archivos_no_imponen_persistencia_ni_interfaz(self):
        self.configure(plan=ambiguous())
        result = self.run_plan("créame una API de reservas")
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["estado"], "necesita_aclaraciones")
        plan = json.loads((Path(result["registro"]) / "propuesta.json").read_text())["propuesta"]
        self.assertEqual(plan["archivos"], [])
        self.assertIn("¿Debe persistir reservas?", plan["preguntas_pendientes"])
        self.assertEqual(plan, ambiguous())

    def test_fuera_de_alcance_es_borrador_bloqueado_sin_ampliar_capacidades(self):
        self.configure(plan=blocked())
        result = self.run_plan("Quiero una app móvil con PostgreSQL")
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertEqual(result["estado"], "necesita_aclaraciones")
        plan = json.loads((Path(result["registro"]) / "propuesta.json").read_text())["propuesta"]
        self.assertEqual(plan["viabilidad"], "fuera_del_alcance")
        self.assertEqual(plan["archivos"], [])
        self.assertFalse(result["aprobada"])

    def test_contexto_minimo_base_git_sin_fuentes_privados_ni_pendientes(self):
        for name in (".codex/config.toml", ".aws/credentials", "runs/historico/privado.txt"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("PRIVADO_SINTETICO_NO_ENVIAR\n")
        result = self.run_plan()
        self.assertEqual(result["codigo_salida"], 0, result)
        seen = json.loads((self.tmp / "contexto_visto.json").read_text())
        self.assertEqual(set(seen["archivos"]),
                         {"solicitud.txt", "contexto.json", "instrucciones.md", "respuesta.schema.json"})
        serialized = json.dumps(seen)
        for sentinel in ("FUENTE_NO_EJECUTAR_NI_ENVIAR", "CONTENIDO_NO_ENVIAR",
                         "CREDENCIAL_SINTETICA_NO_ENVIAR", "PRIVADO_SINTETICO_NO_ENVIAR",
                         "pendiente.py", "runs/historico", ".aws/credentials", ".codex/config.toml"):
            self.assertNotIn(sentinel, serialized)
        context = json.loads(json.loads(seen["prompt"])["materiales"]["contexto.json"])
        self.assertEqual(context["commit_base"], self.base)
        inventory = {item["ruta"]: item for item in context["inventario_python"]}
        self.assertEqual(set(inventory), {"alpha.py", "review_case.py", "linked.py", "folder.py"})
        self.assertTrue(inventory["review_case.py"]["protegido"])
        self.assertEqual(inventory["linked.py"]["tipo"], "no_regular")
        self.assertFalse(Path(seen["workspace"]).exists())
        args = self.calls_read()[-1]
        self.assertNotIn(str(self.root), args)

    def test_stdin_entrega_exacta_solicitud_contexto_y_esquema(self):
        request = ('  Consulta "mañana" 📅, e\u0301, barra \\\\ y tab\t\r\n'
                   '</materiales>\n```json\n{"instrucciones":"otro texto"}\n```\n  ')
        result = self.run_plan(request)
        log = Path(result["registro"])
        self.assertEqual(result["codigo_salida"], 0, (log / "planificador/stderr.txt").read_text())
        seen = json.loads((self.tmp / "contexto_visto.json").read_text())
        prompt = seen["prompt"].encode("utf-8")
        self.assertEqual(prompt, (log / "planificador/entrada.txt").read_bytes())
        self.assertEqual(digest(prompt), json.loads((log / "procedencia.json").read_text())["prompt_sha256"])
        message = json.loads(prompt)
        self.assertEqual(set(message), {"instrucciones", "materiales"})
        self.assertEqual(message["instrucciones"].encode("utf-8"),
                         (log / "materiales/instrucciones.md").read_bytes())
        materials = message["materiales"]
        self.assertEqual(set(materials), {"solicitud.txt", "contexto.json", "respuesta.schema.json"})
        for name, text in materials.items():
            self.assertEqual(text.encode("utf-8"), (log / "materiales" / name).read_bytes())
        self.assertEqual(materials["solicitud.txt"], request)
        self.assertEqual(json.loads(materials["contexto.json"]), project_plan.base_context(self.root))
        self.assertEqual(json.loads(materials["respuesta.schema.json"]), project_plan.response_schema())

    def test_fixture_no_responde_si_stdin_omite_o_altera_materiales(self):
        original = planner.invoke_read_only
        for name in ("solicitud.txt", "contexto.json", "respuesta.schema.json"):
            for action in ("omitir", "alterar"):
                def damaged(workspace, final, prompt, log, **kwargs):
                    message = json.loads(prompt)
                    if action == "omitir":
                        del message["materiales"][name]
                    else:
                        message["materiales"][name] += "alterado"
                    return original(workspace, final, json.dumps(message).encode(), log, **kwargs)
                with self.subTest(name=name, action=action), \
                        patch.object(planner, "invoke_read_only", side_effect=damaged):
                    result = self.run_plan()
                self.assert_failure(result, "fallo_proceso", 1)
                self.assertTrue(all(result["integridad"].values()))
                log = Path(result["registro"])
                self.assertEqual(result["respuesta_tipo"], "ausente")
                self.assertEqual((log / "planificador/eventos.jsonl").read_bytes(), b"")
                self.assertEqual((log / "planificador/respuesta_original.txt").read_bytes(), b"")
                # Los archivos completos existen; eso no permite suplir el stdin defectuoso.
                seen = json.loads((self.tmp / "contexto_visto.json").read_text())
                for material, text in seen["archivos"].items():
                    self.assertEqual(text.encode("utf-8"), (log / "materiales" / material).read_bytes())

    def test_json_invalido_duplicados_constantes_y_tipos_sin_propuesta_parcial(self):
        invalid = [b"{", b'{"version":1,"version":1}', b'{"version":NaN}', b"\xff",
                   b"[]", b"null", b"1", b'""', b'{"x":Infinity}',
                   b'{"archivos":[{"ruta":"a.py","ruta":"b.py"}]}']
        context = project_plan.base_context(self.root)
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                project_plan.validate_response(raw, context)
        self.configure(raw='{"version":1,"version":1}')
        result = self.run_plan()
        self.assert_failure(result, "respuesta_invalida", 1)
        self.assertEqual((Path(result["registro"]) / "planificador/respuesta_original.txt").read_text(),
                         '{"version":1,"version":1}')

    def test_claves_exactas_en_todos_los_niveles_y_metadatos_no_del_modelo(self):
        context = project_plan.base_context(self.root)
        for key in ("estado", "commit_base", "solicitud_original", "procedencia", "aprobada"):
            plan = concrete()
            plan[key] = "inventado"
            with self.subTest(key=key), self.assertRaises(ValueError):
                project_plan.validate_response(json.dumps(plan).encode(), context)
        for address in ((), ("archivos", 0), ("criterios_aceptacion", 0),
                        ("criterios_aceptacion", 0, "ejemplos", 0)):
            for action in ("extra", "ausente"):
                plan = concrete()
                target = plan
                for key in address:
                    target = target[key]
                if action == "extra":
                    target["extra"] = "no admitido"
                else:
                    del target[next(iter(target))]
                with self.subTest(address=address, action=action), self.assertRaises(ValueError):
                    project_plan.validate_response(json.dumps(plan).encode(), context)

    def test_tipos_estrictos_y_textos_requeridos(self):
        context = project_plan.base_context(self.root)
        for key, values in (("version", [True, 1.0, "1", 2]), ("objetivo", [" ", None, 0]),
                            ("archivos", [{}, None]), ("preguntas_pendientes", ["texto", [False]]),
                            ("viabilidad", ["aprobar", 1]), ("supuestos", [[" "], ["x"] * 101])):
            for value in values:
                plan = concrete()
                plan[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    project_plan.validate_response(json.dumps(plan).encode(), context)

    def test_sustituto_unicode_es_respuesta_invalida_con_bruto_conservado(self):
        plan = concrete()
        plan["objetivo"] = "\ud800"
        self.configure(plan=plan)
        result = self.run_plan()
        self.assert_failure(result, "respuesta_invalida", 1)
        self.assertIn(b"\\ud800", (Path(result["registro"]) / "planificador/respuesta_original.txt").read_bytes())

    def test_clave_duplicada_unicode_invalida_conserva_diagnostico_y_bruto(self):
        raw = '{"\\ud800":1,"\\ud800":2}'
        self.configure(raw=raw)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(planner.main(["Consulta sintética"], project_root=self.root), 1)
        logs = list((self.root / "runs").glob("*_plan_project_*"))
        self.assertEqual(len(logs), 1)
        result = json.loads((logs[0] / "resultado.json").read_text(encoding="utf-8"))
        self.assert_failure(result, "respuesta_invalida", 1)
        self.assertEqual((logs[0] / "planificador/respuesta_original.txt").read_bytes(), raw.encode())
        self.assertIn("\\ud800", result["fallo"]["mensaje"])
        self.assertEqual(out.getvalue(), "")
        self.assertIn("respuesta_invalida", err.getvalue())
        err.getvalue().encode("utf-8")
        self.assertEqual(len(self.calls_read()), 3)

    def test_rutas_prohibidas_infraestructura_y_tipos_no_regulares(self):
        context = project_plan.base_context(self.root)
        names = ["../fuera.py", "/tmp/fuera.py", "sub/modulo.py", ".env", ".secreto.py",
                 "runs/extra.py", "foo\\bar.py", "módulo.py", "README.md", "alpha.py\n",
                 "linked.py", "folder.py", *sorted(project_task_config.PROTECTED)]
        for name in names:
            plan = concrete()
            plan["archivos"][0]["ruta"] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                project_plan.validate_response(json.dumps(plan).encode(), context)

    def test_accion_coincide_con_existencia_en_base_no_con_el_workspace(self):
        context = project_plan.base_context(self.root)
        for name, action in (("alpha.py", "crear"), ("ausente.py", "modificar"),
                             ("pendiente.py", "modificar"), ("alpha.py", "borrar")):
            plan = concrete()
            plan["archivos"] = [{"ruta": name, "accion": action, "proposito": "Cambio propuesto."}]
            with self.subTest(name=name, action=action), self.assertRaises(ValueError):
                project_plan.validate_response(json.dumps(plan).encode(), context)

    def test_duplicados_de_rutas_criterios_y_listas(self):
        context = project_plan.base_context(self.root)
        for key in ("archivos", "criterios_aceptacion", "requisitos_interpretados", "alcance"):
            plan = concrete()
            plan[key].append(copy.deepcopy(plan[key][0]))
            if key == "archivos":
                plan[key][-1]["proposito"] = "Otro propósito no permite duplicar la ruta."
            with self.subTest(key=key), self.assertRaises(ValueError):
                project_plan.validate_response(json.dumps(plan).encode(), context)

    def test_coherencia_estructural_no_es_calidad_semantica(self):
        context = project_plan.base_context(self.root)
        plans = []
        for key in ("archivos", "criterios_aceptacion", "alcance", "requisitos_interpretados"):
            plan = concrete()
            plan[key] = []
            plans.append(plan)
        plan = ambiguous()
        plan["preguntas_pendientes"] = []
        plans.append(plan)
        plan = blocked()
        plan["archivos"] = concrete()["archivos"]
        plans.append(plan)
        plan = blocked()
        plan["limitaciones"] = []
        plans.append(plan)
        for plan in plans:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                project_plan.validate_response(json.dumps(plan).encode(), context)
        # No pretende detectar semánticamente un objetivo equivocado.
        plan = concrete()
        plan["objetivo"] = "Un objetivo estructuralmente válido que requiere revisión humana."
        self.assertEqual(project_plan.validate_response(json.dumps(plan).encode(), context), plan)

    def test_supuesto_sin_preguntas_sigue_necesitando_aclaracion(self):
        plan = concrete()
        plan["supuestos"] = ["Supuesto pendiente de confirmación."]
        self.configure(plan=plan)
        result = self.run_plan()
        self.assertEqual(result["codigo_salida"], 0)
        self.assertEqual(result["estado"], "necesita_aclaraciones")

    def test_respuesta_ausente_no_regular_y_grande(self):
        for mode in ("missing_response", "linked_response"):
            self.configure(mode=mode)
            with self.subTest(mode=mode):
                result = self.run_plan()
                self.assert_failure(result, "respuesta_invalida", 1)
                self.assertEqual((Path(result["registro"]) / "planificador/respuesta_original.txt").read_bytes(), b"")
        with self.assertRaises(ValueError):
            project_plan.validate_response(b" " * (project_plan.MAX_RESPONSE + 1),
                                           project_plan.base_context(self.root))

    def test_cli_ausente_cero_reservas(self):
        self.fake.unlink()
        result = self.run_plan()
        self.assert_failure(result, "cli_no_disponible", 0)
        self.assertEqual(self.calls_read(), [])
        self.assertEqual(result["planificador"]["version"]["estado"], "ausente")

    def test_cli_incompatible_cero_reservas(self):
        self.configure(mode="incompatible")
        result = self.run_plan()
        self.assert_failure(result, "cli_incompatible", 0)
        self.assertEqual(self.calls_read(), [["--version"], ["exec", "--help"]])

    def test_alteracion_antes_de_reserva_no_lanza_modelo(self):
        self.configure(mode="tamper_help")
        result = self.run_plan()
        self.assert_failure(result, "integridad", 0)
        self.assertEqual(self.calls_read(), [["--version"], ["exec", "--help"]])

    def test_fallo_consulta_cli_no_es_incompatibilidad_ni_invocacion(self):
        self.configure(mode="version_fail")
        result = self.run_plan()
        self.assert_failure(result, "fallo_proceso", 0)
        self.assertEqual(self.calls_read(), [["--version"]])

    def test_fallo_de_proceso_con_respuesta_conserva_bruto_sin_propuesta(self):
        self.configure(code=7)
        result = self.run_plan()
        self.assert_failure(result, "fallo_proceso", 1)
        self.assertEqual(result["planificador"]["codigo_salida"], 7)
        self.assertEqual(json.loads((Path(result["registro"]) / "planificador/respuesta_original.txt").read_text()),
                         concrete())
        self.assertEqual(len(self.calls_read()), 3)

    def test_cli_desaparece_despues_de_reservar_no_reintenta(self):
        self.configure(mode="vanish")
        result = self.run_plan()
        self.assert_failure(result, "cli_no_disponible", 1)
        self.assertEqual(result["planificador"]["estado"], "ausente")
        self.assertEqual(len(self.calls_read()), 2)

    def test_timeout_real_de_hijo_simulado_y_plazo_de_produccion(self):
        original = review_case.run_process
        seen = []
        def shortened(command, cwd, logs, timeout, *args, **kwargs):
            seen.append(timeout)
            return original(command, cwd, logs, 0.3 if "--output-last-message" in command else timeout,
                            *args, **kwargs)
        self.configure(mode="timeout")
        with patch.object(review_case, "run_process", side_effect=shortened):
            result = self.run_plan()
        self.assert_failure(result, "tiempo_agotado", 1)
        self.assertEqual(seen, [10, 10, 300])
        self.assertIsNotNone(result["planificador"]["codigo_salida"])
        self.assertEqual(len(self.calls_read()), 3)
        self.assertTrue((Path(result["registro"]) / "planificador/respuesta_original.txt").stat().st_size)
        self.assertFalse(Path(json.loads((self.tmp / "contexto_visto.json").read_text())["workspace"]).exists())

    def test_timeout_preflight_no_consume_invocacion(self):
        original = review_case.run_process
        self.configure(mode="version_timeout")
        with patch.object(review_case, "run_process",
                          side_effect=lambda cmd, cwd, log, timeout, **kw: original(cmd, cwd, log, 0.3, **kw)):
            result = self.run_plan()
        self.assert_failure(result, "tiempo_agotado", 0)
        self.assertEqual(len(self.calls_read()), 1)

    def test_interrupcion_antes_y_despues_de_reserva_conserva_bruto(self):
        original = review_case.run_process
        for at_model in (False, True):
            count = 0
            def interrupted(command, cwd, log, timeout, *args, **kwargs):
                nonlocal count
                count += 1
                if not at_model or "--output-last-message" in command:
                    if at_model:
                        Path(command[command.index("--output-last-message") + 1]).write_text('{"parcial":')
                    raise ProcessInterrupted({"estado": "interrumpida", "codigo_salida": -9})
                return original(command, cwd, log, timeout, *args, **kwargs)
            with self.subTest(at_model=at_model), patch.object(review_case, "run_process", side_effect=interrupted):
                result = self.run_plan()
                self.assert_failure(result, "interrumpida", int(at_model))
                self.assertEqual(count, 3 if at_model else 1)
                self.assertEqual(result["planificador"]["estado"], "interrumpida")
                raw = (Path(result["registro"]) / "planificador/respuesta_original.txt").read_bytes()
                self.assertEqual(raw, b'{"parcial":' if at_model else b"")

    def test_alteraciones_de_materiales_o_proyecto_impiden_borrador(self):
        for mode in ("workspace_tamper", "project_tamper"):
            self.configure(mode=mode)
            with self.subTest(mode=mode):
                result = self.run_plan()
                self.assert_failure(result, "integridad", 1)
                self.assertFalse(all(result["integridad"].values()))

    def test_reserva_persistida_y_limite_impiden_segunda_invocacion(self):
        def twice(workspace, final, prompt, log, *, on_invoke, timeout):
            on_invoke()
            self.assertEqual(json.loads((log.parent / "resultado.json").read_text())["invocaciones"], {"planificador": 1})
            on_invoke()
            self.fail("No puede permitir una segunda reserva")
        with patch.object(planner, "invoke_read_only", side_effect=twice) as invoke:
            result = self.run_plan()
        self.assert_failure(result, "error_controlador", 1)
        invoke.assert_called_once()

    def test_registros_exclusivos_colision_no_sobrescribe(self):
        with patch.object(planner, "uuid4", return_value=SimpleNamespace(hex="fijo")), \
                patch.object(planner, "timestamp", return_value="2026-01-01T00:00:00Z"):
            first = self.run_plan()
            log = Path(first["registro"])
            before = tree_state(log)
            second = self.run_plan()
        self.assert_failure(second, "error_controlador", 0)
        self.assertIsNone(second["registro"])
        self.assertEqual(tree_state(log), before)
        self.assertEqual(len(self.calls_read()), 3)

    def test_runs_enlace_no_escribe_fuera_ni_invoca(self):
        (self.root / "runs").rename(self.tmp / "registros_previos")
        outside = self.tmp / "fuera"
        outside.mkdir()
        (self.root / "runs").symlink_to(outside, target_is_directory=True)
        result = self.run_plan()
        self.assert_failure(result, "error_controlador", 0)
        self.assertIsNone(result["registro"])
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.calls_read(), [])

    def test_fallo_publicacion_no_deja_propuesta_parcial(self):
        original = Path.open
        def denied(path, *args, **kwargs):
            if path.name == "propuesta.md":
                raise OSError("Fallo de escritura simulado")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", denied):
            result = self.run_plan()
        self.assert_failure(result, "error_controlador", 1)
        self.assertTrue((Path(result["registro"]) / "planificador/respuesta_original.txt").stat().st_size)

    def test_salida_es_datos_no_se_ejecuta_y_markdown_es_literal(self):
        sentinel = self.tmp / "NO_CREAR"
        plan = concrete()
        payload = f'__import__("pathlib").Path({str(sentinel)!r}).write_text("ejecutado")'
        plan["criterios_aceptacion"][0]["ejemplos"][0]["entrada"] = payload
        plan["objetivo"] = "# Título inyectado\n<script>no ejecutar</script>\n[enlace](file:///etc/passwd)"
        self.configure(plan=plan)
        result = self.run_plan()
        self.assertEqual(result["codigo_salida"], 0, result)
        self.assertFalse(sentinel.exists())
        markdown = (Path(result["registro"]) / "propuesta.md").read_text()
        self.assertIn("    # Título inyectado", markdown)
        self.assertIn("    <script>no ejecutar</script>", markdown)
        self.assertNotIn("\n<script>", markdown)

    def test_no_registra_valores_del_entorno(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "CREDENCIAL_SINTETICA_NO_REGISTRAR",
                                     "AWS_SECRET_ACCESS_KEY": "OTRA_CREDENCIAL_SINTETICA"}):
            result = self.run_plan()
        self.assertEqual(result["codigo_salida"], 0, result)
        for path in Path(result["registro"]).rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                self.assertNotIn(b"CREDENCIAL_SINTETICA_NO_REGISTRAR", raw)
                self.assertNotIn(b"OTRA_CREDENCIAL_SINTETICA", raw)

    def test_cli_ayuda_argumentos_y_canales_sin_llamadas_accidentales(self):
        for args, code in ((["--help"], 0), ([], 2), ([""], 2), (["  "], 2),
                           (["x" * 16001], 2), (["a", "b"], 2), (["--desarrollar", "a"], 2)):
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(args=args[:1]), redirect_stdout(out), redirect_stderr(err), \
                    patch.object(planner, "run_plan") as run:
                with self.assertRaises(SystemExit) as exc:
                    planner.main(args, project_root=self.root)
                self.assertEqual(exc.exception.code, code)
                run.assert_not_called()
                self.assertFalse(err.getvalue() if code == 0 else out.getvalue())
        self.assertEqual(self.calls_read(), [])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(planner.main(["Consulta sintética"], project_root=self.root), 0)
        self.assertIn("Registro:", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        self.configure(mode="incompatible")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(planner.main(["Consulta sintética"], project_root=self.root), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("cli_incompatible", err.getvalue())

    def test_cli_rechaza_solicitud_no_utf8_antes_de_registrar_o_invocar(self):
        before = tree_state(self.root)
        for request in ("\ud800", "solicitud \udcff"):
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(request=repr(request)), redirect_stdout(out), redirect_stderr(err):
                with self.assertRaises(SystemExit) as exc:
                    planner.main([request], project_root=self.root)
                self.assertEqual(exc.exception.code, 2)
                self.assertEqual(out.getvalue(), "")
                self.assertIn("UTF-8", err.getvalue())
                err.getvalue().encode("utf-8")
            self.assertEqual(tree_state(self.root), before)
        self.assertEqual(self.calls_read(), [])
        # Acentos y caracteres fuera del BMP válidos no se rechazan ni sustituyen.
        request = "Consulta de disponibilidad en español \U0001f4c5"
        result = self.run_plan(request)
        self.assertEqual(result["codigo_salida"], 0, result)
        saved = json.loads((Path(result["registro"]) / "propuesta.json").read_text())
        self.assertEqual(saved["solicitud_original"], request)

    def test_infraestructura_planificacion_no_editable_en_v2(self):
        config = {
            "version": 2, "identificador": "sintetica", "commit_base": self.base,
            "contrato": "tasks/sintetica.md", "archivos_editables": [],
            "evaluador_aceptacion": "evals/sintetica/evaluar.py",
            "prompts": {"desarrollador": "prompts/d.md", "revisor": "prompts/r.md"},
            "referencias": [], "limites_segundos": dict(project_task_config.LIMITS),
        }
        for name in ("plan_project.py", "project_plan.py", "project_plan_continuation.py"):
            config["archivos_editables"] = [{"ruta": name, "estado_inicial": "ausente"}]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "infraestructura"):
                project_task_config.validate_document(config)


if __name__ == "__main__":
    unittest.main()

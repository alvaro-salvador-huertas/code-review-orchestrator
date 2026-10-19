"""Resúmenes sintéticos: lectura por CLI, sin agentes ni orquestaciones."""

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import inspect_project
from process_environment import process_environment


ROOT = Path(__file__).resolve().parents[1]
TASKS = ("inspect-json", "export-csv")


def process(state="finalizada", code=0):
    return {"estado": state, "codigo_salida": code, "duracion_segundos": 1.25,
            "limite_segundos": 10, "directorio_trabajo": "/evidencia-sintetica/no-disponible"}


def evaluation(failed=False):
    return {"proceso": process(code=int(failed)),
            "clasificacion": "fallos_asercion" if failed else "superadas", "metodos": 3,
            "metodos_con_fallos": int(failed), "aserciones_fallidas": int(failed),
            "errores": 0, "fallos_subtest": 0, "subtests_ejecutados": 0}


def attempt(task, number=1, decision="aprobar"):
    verdict = {"decision": decision, "resumen": "Dictamen sintético, no humano", "hallazgos": []}
    if decision == "solicitar_cambios":
        verdict["hallazgos"] = [{"archivo": "candidato-sintetico.py", "linea": 1,
            "requisito": "Requisito sintético", "explicacion": "Observación no contrastada", "ejemplo": "Ejemplo"}]
    return {"numero": number, "registro": f"/evidencia-sintetica/{number}",
            "invocaciones": {"desarrollador": 1, "revisor": 1},
            "desarrollo": {"reserva_invocacion": True, "agente": {"invocaciones": 1, "proceso": process()}},
            "evaluaciones": {name: evaluation() for name in
                (("aceptacion", "regresion", "hallazgos", "anidamiento") if task == "inspect-json"
                 else ("aceptacion", "regresion"))},
            "revision": {"registro": "/revision-sintetica/ausente", "decision_controlador":
                "dictamen_aprobar_validado" if decision == "aprobar" else "cambios_solicitados",
                "codigo_salida": int(decision != "aprobar"), "revisor": {**process(), "invocaciones": 1},
                "dictamen_modelo": verdict, "incorporacion": "no_realizada",
                "contraste_semantico": "pendiente", "error": None},
            "transiciones": [{"etapa": "revision", "accion": "aprobar" if decision == "aprobar" else "corregir",
                              "motivo": "revision_aprobada" if decision == "aprobar" else "cambios_solicitados"}]}


def summary(task="export-csv"):
    return {"tipo": "orquestacion_inspect_json_v1" if task == "inspect-json" else "orquestacion_export_csv_v1",
            "tarea": task, "registro": "/registro-sintetico/ya-eliminado",
            "inicio_utc": "2026-01-01T00:00:00Z", "fin_utc": "2026-01-01T00:00:12Z",
            "estado": "lista_para_revision_humana", "motivo": "revision_aprobada", "codigo_salida": 0,
            "max_intentos": 2, "max_invocaciones": 4, "duracion_segundos": 12.3456789,
            "invocaciones": {"desarrollador": 1, "revisor": 1, "total": 2},
            "reservas": [{"rol": role, "intento": 1, "fecha_utc": "2026-01-01T00:00:00Z",
                          "limite_segundos": 10, "estado": "reservada_antes_de_invocar"} for role in ("desarrollador", "revisor")],
            "intentos": [attempt(task)], "inicial": {"aceptacion": evaluation(True), "regresion": evaluation()},
            "limites_segundos": {"desarrollador": 10, "revisor": 10, "aceptacion": 10},
            "lista_para_revision_humana": True, "incorporacion": "no_realizada", "error": None,
            "integridad": {"original_intacto": True}, "etapas_cerradas": {"/no/abrir": {}},
            "procedencia": {"documento_sintetico": True}}


class TestInspectProject(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="inspector-proyectos-sintetico-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run = self.root / "nombre-ajeno-a-la-tarea"
        self.run.mkdir()
        self.source = self.run / "resultado.json"

    def write(self, data):
        self.source.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")

    def inventory(self):
        return {str(p.relative_to(self.root)): (p.lstat().st_mode,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.root.rglob("*")}

    def cli(self, script, *args):
        before = self.inventory()
        with process_environment("evaluation") as environment:
            completed = subprocess.run([str(Path(sys.executable).resolve()), "-B", str(ROOT / script), *map(str, args)],
                cwd=self.root, env=environment, capture_output=True, timeout=10)
        self.assertEqual(self.inventory(), before, "La consulta no debe modificar entradas ni crear cachés")
        return completed

    def query(self, data=None, code=0):
        if data is not None:
            self.write(data)
        completed = self.cli("inspect_project.py", "--run", self.run, "--format", "json")
        self.assertEqual(completed.returncode, code, completed.stdout)
        self.assertEqual(completed.stderr, b"")
        document = json.loads(completed.stdout)  # Rechaza objetos concatenados o texto adicional.
        self.assertIs(type(document), dict)
        self.assertEqual(set(document), {"version_esquema", "consulta", "ejecucion"})
        self.assertEqual(document["consulta"]["codigo_salida"], code)
        self.assertEqual(document["consulta"]["estado"], "completada" if code == 0 else "incompleta")
        self.assertEqual(bool(document["consulta"]["incidencias"]), bool(code))
        return document

    def test_approval_both_tasks_exact_v1_projection(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                result = self.query(data)
                self.assertEqual(result, {"version_esquema": 1,
                    "consulta": {"estado": "completada", "codigo_salida": 0, "incidencias": []},
                    "ejecucion": {"caso": task, "estado": "lista_para_revision_humana", "codigo_salida": 0,
                        "presupuestos": {"max_intentos": 2, "max_invocaciones": 4}, "intentos_registrados": 1,
                        "invocaciones": {"desarrollador": 1, "revisor": 1, "total": 2}, "duracion_segundos": 12.3456789}})

    def test_correction_then_approval_both_tasks(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                data["intentos"] = [attempt(task, decision="solicitar_cambios"), attempt(task, 2)]
                data["invocaciones"] = {"desarrollador": 2, "revisor": 2, "total": 4}
                data["reservas"] += [{**item, "intento": 2} for item in data["reservas"]]
                self.assertEqual(self.query(data)["ejecucion"]["intentos_registrados"], 2)

    def test_exhaustion_without_review_both_tasks(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                data.update(estado="intentos_agotados", motivo="fallos_asercion", codigo_salida=1,
                            lista_para_revision_humana=False, max_intentos=1, max_invocaciones=2,
                            invocaciones={"desarrollador": 1, "revisor": 0, "total": 1})
                data["reservas"] = data["reservas"][:1]
                entry = data["intentos"][0]
                entry["invocaciones"]["revisor"] = 0
                entry["revision"] = None
                entry["evaluaciones"]["aceptacion"] = evaluation(True)
                entry["transiciones"] = [{"etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"}]
                self.assertEqual(self.query(data)["ejecucion"]["codigo_salida"], 1)

    def test_developer_timeout_both_tasks(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                data.update(estado="tiempo_agotado", motivo="tiempo_agotado", codigo_salida=4,
                            error="Timeout sintético", lista_para_revision_humana=False,
                            invocaciones={"desarrollador": 1, "revisor": 0, "total": 1})
                data["reservas"] = data["reservas"][:1]
                entry = data["intentos"][0]
                entry["invocaciones"]["revisor"] = 0
                entry["desarrollo"]["agente"]["proceso"] = process("tiempo_agotado", -15)
                entry.update(revision=None, transiciones=[])
                del entry["evaluaciones"]
                self.assertEqual(self.query(data)["ejecucion"]["codigo_salida"], 4)

    def test_reviewer_timeout_without_verdict_both_tasks(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                data.update(estado="tiempo_agotado_revisor", motivo="tiempo_agotado_revisor",
                            codigo_salida=4, lista_para_revision_humana=False)
                review = data["intentos"][0]["revision"]
                review.update(decision_controlador="tiempo_agotado_revisor", codigo_salida=4, dictamen_modelo=None)
                review["revisor"].update(estado="tiempo_agotado", codigo_salida=-15)
                data["intentos"][0]["transiciones"] = [{"etapa": "evaluacion", "accion": "revisar", "motivo": "superadas"}]
                self.query(data)

    def test_preparation_failure_both_tasks(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = summary(task)
                data.update(estado="preparacion_no_autoriza", codigo_salida=7, motivo="preparacion_no_autoriza",
                            intentos=[], reservas=[], inicial={}, invocaciones={"desarrollador": 0, "revisor": 0, "total": 0},
                            lista_para_revision_humana=False, error="Preparación sintética fallida")
                self.assertEqual(self.query(data)["ejecucion"]["intentos_registrados"], 0)

    def test_active_snapshot_and_reserved_call_without_process(self):
        data = summary()
        data.update(estado="en_desarrollo", motivo=None, codigo_salida=8, lista_para_revision_humana=False)
        data["invocaciones"] = {"desarrollador": 1, "revisor": 0, "total": 1}
        data["reservas"] = data["reservas"][:1]
        del data["fin_utc"], data["duracion_segundos"]
        entry = data["intentos"][0]
        entry["invocaciones"]["revisor"] = 0
        del entry["desarrollo"], entry["evaluaciones"]
        entry.update(revision=None, transiciones=[])
        self.assertIsNone(self.query(data)["ejecucion"]["duracion_segundos"])
        text = self.cli("inspect_project.py", "--run", self.run).stdout.decode()
        self.assertIn("no acreditan que las invocaciones hayan finalizado", text)
        self.assertIn("Proceso del desarrollador registrado: estado=no consta", text)

    def test_pending_evaluation_can_lack_counts(self):
        data = summary()
        data.update(estado="en_preparacion", motivo=None, codigo_salida=8, lista_para_revision_humana=False,
                    intentos=[], reservas=[], invocaciones={"desarrollador": 0, "revisor": 0, "total": 0})
        del data["fin_utc"], data["duracion_segundos"]
        data["inicial"] = {"aceptacion": {"proceso": None, "clasificacion": "no_acreditada"}}
        self.query(data)

    def test_preflight_failure_without_developer_execution(self):
        data = summary()
        data.update(estado="fallo_tecnico", motivo="fallo_tecnico", codigo_salida=3,
                    lista_para_revision_humana=False, reservas=[], invocaciones={"desarrollador": 0, "revisor": 0, "total": 0})
        entry = data["intentos"][0]
        entry.update(revision=None, transiciones=[])
        entry["invocaciones"] = {"desarrollador": 0, "revisor": 0}
        entry["desarrollo"] = {"reserva_invocacion": False, "agente": {"invocaciones": 0, "proceso": None,
                              "version": process("ausente", None)}}
        del entry["evaluaciones"]
        self.query(data)

    def test_partial_summary_preserves_valid_fields(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.query({"tipo": summary(task)["tipo"], "tarea": task, "estado": "fallo_tecnico",
                                     "codigo_salida": 3, "invocaciones": {"desarrollador": 1}}, code=1)
                run = result["ejecucion"]
                self.assertEqual((run["caso"], run["codigo_salida"], run["invocaciones"]["desarrollador"]), (task, 3, 1))
                self.assertIsNone(run["intentos_registrados"])
                self.assertIsNone(run["invocaciones"]["total"])
                self.assertIsNone(run["presupuestos"]["max_intentos"])

    def test_missing_terminal_duration_is_incomplete(self):
        data = summary()
        del data["duracion_segundos"]
        result = self.query(data, code=1)
        self.assertIsNone(result["ejecucion"]["duracion_segundos"])

    def test_totals_are_not_recomputed_or_used_to_authorize(self):
        data = summary()
        data["invocaciones"]["total"] = 19
        self.assertEqual(self.query(data)["ejecucion"]["invocaciones"]["total"], 19)

    def test_missing_summary_and_nonregular_files(self):
        result = self.query(code=1)
        self.assertIsNone(result["ejecucion"]["caso"])
        self.source.mkdir()
        self.query(code=1)
        self.source.rmdir()
        target = self.root / "otro.json"
        target.write_text(json.dumps(summary()))
        self.source.symlink_to(target)
        self.query(code=1)

    def test_unreadable_summary_reports_error(self):
        with patch.object(inspect_project, "read_regular", side_effect=PermissionError("lectura denegada sintética")):
            output = io.StringIO()
            with patch("sys.stdout", output), patch("sys.stderr", io.StringIO()) as stderr:
                code = inspect_project.main(["--run", str(self.run), "--format", "json"])
        self.assertEqual(code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("lectura denegada", json.loads(output.getvalue())["consulta"]["incidencias"][0])

    def test_invalid_json_duplicate_keys_constants_and_depth(self):
        for raw in (b"{", b"[]", b"null", b"{} {}", b"\xff", b'{"tarea":1,"tarea":2}',
                    b'{"extra":{"a":0,"a":1}}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                    b"[" * 2000 + b"0" + b"]" * 2000):
            with self.subTest(raw=raw[:60]):
                self.source.write_bytes(raw)
                self.query(code=1)

    def test_unsupported_formats_and_task_mismatch(self):
        for changes in ({"tipo": "orquestacion_benchmark_v1", "tarea": "case_01"},
                        {"tipo": "revision_aislada_inspect_json_v1"}, {"tipo": "orquestacion_export_csv_v2"},
                        {"tarea": "inspect-json"}, {"tipo": None}):
            with self.subTest(changes=changes):
                data = summary()
                data.update(changes)
                result = self.query(data, code=1)
                self.assertTrue(any("formato de orquestación no admitido" in x for x in result["consulta"]["incidencias"]))

    def test_invalid_scalar_values_are_not_projected(self):
        for field, values in (("max_intentos", [True, -1, 1.0, "2", None]),
                              ("codigo_salida", [False, 0.0, "0"]),
                              ("duracion_segundos", [True, -0.5, "1", None]),
                              ("estado", [[], " ", 4])):
            for value in values:
                with self.subTest(field=field, value=value):
                    data = summary()
                    data[field] = value
                    run = self.query(data, code=1)["ejecucion"]
                    self.assertIsNone(run["presupuestos"][field] if field == "max_intentos" else run[field])

    def test_nested_corruption_is_localized(self):
        cases = (("intentos", 0, "invocaciones", "revisor"),
                 ("invocaciones", "total"),
                 ("intentos", 0, "numero"), ("intentos", 0, "desarrollo", "agente", "invocaciones"),
                 ("intentos", 0, "evaluaciones", "aceptacion", "metodos"),
                 ("intentos", 0, "revision", "revisor", "codigo_salida"),
                 ("reservas", 0, "intento"), ("limites_segundos", "revisor"))
        for path in cases:
            with self.subTest(path=path):
                data = summary()
                parent = data
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = True
                result = self.query(data, code=1)
                self.assertTrue(any(str(path[-1]) in x for x in result["consulta"]["incidencias"]))
                self.assertEqual(result["ejecucion"]["caso"], "export-csv")

    def test_missing_nested_fields_and_wrong_containers(self):
        for target in ("desarrollo", "revision", "evaluaciones", "transiciones"):
            with self.subTest(target=target):
                data = summary()
                data["intentos"][0][target] = [] if target != "transiciones" else {}
                self.query(data, code=1)
        data = summary()
        del data["intentos"][0]["revision"]
        self.query(data, code=1)
        data = summary()
        del data["inicial"]["aceptacion"]["metodos"]
        self.query(data, code=1)

    def test_invalid_classification_reservation_and_verdict(self):
        for location, key in (("evaluation", "clasificacion"), ("reservation", "rol"),
                              ("reservation", "estado"), ("verdict", "decision")):
            with self.subTest(location=location, key=key):
                data = summary()
                target = {"evaluation": data["inicial"]["aceptacion"], "reservation": data["reservas"][0],
                          "verdict": data["intentos"][0]["revision"]["dictamen_modelo"]}[location]
                target[key] = "valor_invalido"
                result = self.query(data, code=1)
                self.assertTrue(any(key in issue for issue in result["consulta"]["incidencias"]))

    def test_empty_attempt_list_differs_from_unknown(self):
        data = summary()
        data["intentos"] = []
        self.assertEqual(self.query(data)["ejecucion"]["intentos_registrados"], 0)
        data["intentos"] = None
        self.assertIsNone(self.query(data, code=1)["ejecucion"]["intentos_registrados"])

    def test_only_summary_read_no_referenced_files_or_execution(self):
        data = summary()
        trap = self.root / "referencia.py"
        trap.write_text("raise RuntimeError('ESTE CONTENIDO NO SE EJECUTA')\n")
        data["registro"] = data["intentos"][0]["registro"] = str(trap)
        data["etapas_cerradas"] = {str(trap): {"sha256": "no se contrasta"}}
        self.query(data)
        original = Path.read_bytes
        opened = []

        def read(path):
            opened.append(path)
            self.assertEqual(path, self.source)
            return original(path)

        with patch.object(Path, "read_bytes", read):
            inspection, _ = inspect_project.read_inspection(self.run)
        self.assertEqual(opened, [self.source])
        self.assertEqual(inspection["consulta"]["codigo_salida"], 0)

    def test_text_default_and_explicit_identical_with_registered_details(self):
        self.write(summary())
        default = self.cli("inspect_project.py", "--run", self.run)
        explicit = self.cli("inspect_project.py", "--run", self.run, "--format", "text")
        self.assertEqual((default.stdout, default.stderr, default.returncode), (explicit.stdout, b"", 0))
        text = default.stdout.decode()
        for expected in ("tarea=export-csv", "motivo=revision_aprobada", "duracion_segundos=12.3456789",
                         "incorporacion=no_realizada", "Evaluación inicial registrada / aceptacion", "metodos=3",
                         "Proceso del desarrollador registrado: estado=finalizada", "decision=aprobar",
                         "Transición registrada", "sin abrir", "no es auditoría humana", "Consulta: completada"):
            self.assertIn(expected, text)

    def test_incomplete_text_contains_issues_without_fake_state(self):
        self.write({})
        result = self.cli("inspect_project.py", "--run", self.run)
        self.assertEqual((result.returncode, result.stderr), (1, b""))
        self.assertIn("estado=no consta", result.stdout.decode())
        self.assertIn("Incidencia de consulta:", result.stdout.decode())

    def test_help_and_argument_errors(self):
        result = self.cli("inspect_project.py", "--help")
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        for arguments in ((), ("--run",), ("--run", self.run, "--format", "yaml"),
                          ("--run", self.run, "--unknown"), ("--ru", self.run)):
            with self.subTest(arguments=arguments):
                result = self.cli("inspect_project.py", *arguments)
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertTrue(result.stderr)

    def export(self, data, code):
        document = self.query(data, code=code)
        completed = self.cli("inspect_project.py", "--run", self.run, "--format", "json")
        path = self.root / "consulta sintética.json"
        path.write_bytes(completed.stdout)
        exported = self.cli("export_runs.py", path)
        self.assertEqual((exported.returncode, exported.stderr), (0, b""))
        rows = list(csv.DictReader(io.StringIO(exported.stdout.decode(), newline="")))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origen"], str(path))
        self.assertEqual(rows[0]["caso"], document["ejecucion"]["caso"])
        return rows[0]

    def test_cli_json_to_csv_failed_execution_is_consultable(self):
        data = summary()
        data.update(estado="tiempo_agotado_revisor", motivo="tiempo_agotado_revisor",
                    codigo_salida=4, lista_para_revision_humana=False)
        entry = data["intentos"][0]
        entry["revision"].update(decision_controlador="tiempo_agotado_revisor", codigo_salida=4, dictamen_modelo=None)
        entry["revision"]["revisor"].update(estado="tiempo_agotado", codigo_salida=-15)
        entry["transiciones"] = [{"etapa": "evaluacion", "accion": "revisar", "motivo": "superadas"}]
        row = self.export(data, 0)
        self.assertEqual((row["consulta_estado"], row["consulta_codigo_salida"], row["ejecucion_codigo_salida"]),
                         ("completada", "0", "4"))

    def test_cli_json_to_csv_incomplete_query_is_exportable(self):
        row = self.export({"tipo": "orquestacion_inspect_json_v1", "tarea": "inspect-json", "codigo_salida": 7}, 1)
        self.assertEqual((row["consulta_estado"], row["consulta_codigo_salida"], row["ejecucion_codigo_salida"]),
                         ("incompleta", "1", "7"))
        self.assertEqual((row["intentos_registrados"], row["duracion_segundos"], row["max_intentos"]), ("", "", ""))

    def test_numeric_precision_range_and_integer_representation(self):
        data = summary()
        for token in ("1.234567890123456789", "1e400", "7" * 5001, "0", "-0.0"):
            with self.subTest(token=token[:40]):
                raw = json.dumps(data).replace('"duracion_segundos": 12.3456789', '"duracion_segundos": ' + token)
                raw = raw.replace('"max_invocaciones": 4', '"max_invocaciones": ' + "9" * 5001)
                self.source.write_text(raw)
                completed = self.cli("inspect_project.py", "--run", self.run, "--format", "json")
                self.assertEqual((completed.returncode, completed.stderr), (0, b""))
                doc = json.loads(completed.stdout, parse_int=str, parse_float=str)
                self.assertEqual(doc["ejecucion"]["duracion_segundos"], token)
                self.assertEqual(doc["ejecucion"]["presupuestos"]["max_invocaciones"], "9" * 5001)

    def configurable_summary(self):
        data = summary()
        data.update(tipo="orquestacion_configurable_v1", tarea="tarea-sintetica",
                    configuracion={"version": 1, "identificador": "tarea-sintetica",
                        "origen": "/no/abrir/configuracion.json", "sha256": "a" * 64, "commit_base": "b" * 40})
        return data

    def test_configurable_summary_only_reads_result(self):
        result = self.query(self.configurable_summary())
        self.assertEqual(result["ejecucion"]["caso"], "tarea-sintetica")
        text = self.cli("inspect_project.py", "--run", self.run)
        self.assertEqual((text.returncode, text.stderr), (0, b""))
        self.assertIn("Configuración registrada (sin abrir ni verificar hashes)", text.stdout.decode())
        self.assertIn("/no/abrir/configuracion.json", text.stdout.decode())

    def test_configurable_metadata_invalid_or_missing(self):
        for key, value in (("version", True), ("version", 2), ("identificador", "otra-tarea"),
                           ("sha256", None), ("commit_base", "main"), ("origen", [])):
            with self.subTest(key=key):
                data = self.configurable_summary()
                data["configuracion"][key] = value
                result = self.query(data, code=1)
                self.assertEqual(result["ejecucion"]["caso"], "tarea-sintetica")
        data = self.configurable_summary()
        del data["configuracion"]
        self.query(data, code=1)

    def test_configurable_format_cannot_impersonate_historical_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                data = self.configurable_summary()
                data["tarea"] = data["configuracion"]["identificador"] = task
                self.query(data, code=1)

    def test_configurable_v2_failed_summary_and_incomplete_export(self):
        data = self.configurable_summary()
        data.update(tipo="orquestacion_configurable_v2", estado="tiempo_agotado", codigo_salida=4,
                    lista_para_revision_humana=False)
        data["configuracion"]["version"] = 2
        data["intentos"][0]["conjunto"] = {"ruta_registrada": "/no/abrir/entrega.json"}
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete):
                if incomplete:
                    del data["duracion_segundos"]
                document = self.query(data, code=int(incomplete))
                self.assertEqual(document["ejecucion"]["codigo_salida"], 4)
                query = self.cli("inspect_project.py", "--run", self.run, "--format", "json")
                path = self.run / "consulta.json"
                path.write_bytes(query.stdout)
                exported = self.cli("export_runs.py", path)
                self.assertEqual((exported.returncode, exported.stderr), (0, b""))
                self.assertIn(b'"tarea-sintetica"', exported.stdout)
                if incomplete:
                    self.assertIsNone(document["ejecucion"]["duracion_segundos"])

    def test_configurable_v2_requires_matching_metadata_version(self):
        for version in (1, True, 2.0, None, 3):
            with self.subTest(version=version):
                data = self.configurable_summary()
                data["tipo"] = "orquestacion_configurable_v2"
                data["configuracion"]["version"] = version
                self.query(data, code=1)


if __name__ == "__main__":
    unittest.main()

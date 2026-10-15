"""Registros temporales escritos como datos; no se ejecutan agentes ni candidatos."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import inspect_run
from case_evidence import snapshot_tree


SCRIPT = Path(__file__).resolve().parents[1] / "inspect_run.py"
REFERENCE = ("raise RuntimeError('ESTAS PRUEBAS NO DEBEN IMPORTARSE')\n"
             "import unittest\nclass Historicas(unittest.TestCase):\n"
             "    def test_a(self): pass\n    def test_b(self): pass\n")


def report(statuses):
    names = ["test_a", "test_b"]
    text = "\n".join(f"{name} (test_solution.Historicas.{name}) ... {status}"
                     for name, status in zip(names, statuses)) + "\n"
    for name, status in zip(names, statuses):
        if status != "ok":
            text += (f"\n{'='*70}\n{status}: {name} (test_solution.Historicas.{name})\n"
                     + "-"*70 + "\nTraceback (most recent call last):\n"
                     + ("AssertionError: defecto\n" if status == "FAIL" else "RuntimeError: técnico\n"))
    text += "\n" + "-"*70 + "\nRan 2 tests in 0.001s\n\n"
    parts = [f"{key}={statuses.count(status)}" for key, status in
             (("failures", "FAIL"), ("errors", "ERROR")) if status in statuses]
    return text + ("FAILED (" + ", ".join(parts) + ")\n" if parts else "OK\n")


class TestInspectRun(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-inspect-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.general = self.root / "registro general"
        self.general.mkdir()
        self.result = {
            "caso": "case_01", "estado": "aprobada", "codigo_salida": 0,
            "registro": str(self.general), "max_intentos": 2, "max_invocaciones": 4,
            "invocaciones": {"desarrollador": 1, "revisor": 1, "total": 2},
            "duracion_segundos": 12.3456, "integridad": {"originales_intactos": True},
            "errores_controlador": [], "intentos": [],
        }
        self.result["intentos"] = [self.attempt(1)]

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def attempt(self, number, *, failed=False, verdict="aprobar"):
        directory = self.root / f"reparacion {number}"
        self.save(directory / "referencia/test_solution.py", REFERENCE)
        self.save(directory / "referencia/contrato.md", "Contrato histórico diferente del benchmark actual.")
        self.save(directory / "candidato.py", "raise RuntimeError('NO EJECUTAR CANDIDATO')\n")
        self.save(directory / "agente/entrada.txt", "PROMPT PRIVADO NO MOSTRAR")
        self.save(directory / "agente/eventos.jsonl", "EVENTOS PRIVADOS, ni siquiera JSON\n" * 20)
        repair = {
            "caso": self.result["caso"], "registro": str(directory),
            "estado": "no_supera_pruebas" if failed else "supera_las_pruebas_disponibles",
            "codigo_salida": int(failed), "integridad": {"referencia_intacta": True},
            "errores_controlador": [],
            "agente": {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1},
        }
        for phase, key, statuses in (
            ("inicial", "pruebas_iniciales", ["FAIL", "ok"]),
            ("posterior", "pruebas_posteriores", ["FAIL" if failed else "ok", "ok"]),
        ):
            evaluation = {"estado": "finalizada", "codigo_salida": int("FAIL" in statuses)}
            repair[key] = evaluation
            self.save(directory / phase / "resultado.json", evaluation)
            self.save(directory / phase / "stderr.txt", report(statuses))
        review = None
        transitions = [{"etapa": "desarrollo", "accion": "corregir" if failed else "revisar",
                        "motivo": "fallos_asercion" if failed else "supera_las_pruebas_disponibles"}]
        if not failed:
            review = {
                "caso": self.result["caso"], "registro": str(self.root / f"revision {number}"),
                "dictamen_modelo": {"decision": verdict, "hallazgos": [] if verdict == "aprobar" else
                                    [{"explicacion": "Debe corregirse"}]},
                "decision_controlador": "aprobada" if verdict == "aprobar" else "cambios_solicitados",
                "codigo_salida": int(verdict != "aprobar"), "integridad": {"workspace_intacto": True},
                "errores_controlador": [],
                "revisor": {"estado": "finalizada", "codigo_salida": 0, "invocaciones": 1},
            }
            transitions.append({"etapa": "revision", "accion": "aprobar" if verdict == "aprobar" else
                                "corregir", "motivo": review["decision_controlador"]})
        return {"numero": number, "reparacion": repair, "revision": review, "transiciones": transitions}

    def write_records(self):
        for entry in self.result.get("intentos", []):
            if not isinstance(entry, dict):
                continue
            for role in ("reparacion", "revision"):
                stage = entry.get(role)
                if isinstance(stage, dict) and stage.get("registro"):
                    directory = Path(stage["registro"])
                    if not directory.is_absolute():
                        directory = self.general / directory
                    self.save(directory / "resultado.json", stage)
        self.save(self.general / "resultado.json", self.result)

    def query(self, *, write=True):
        if write:
            self.write_records()
        before = snapshot_tree(self.root)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), \
                patch("subprocess.Popen", side_effect=AssertionError("No ejecutar procesos")), \
                patch("os.system", side_effect=AssertionError("No ejecutar órdenes")):
            code = inspect_run.main(["--run", str(self.general)])
        self.assertEqual(snapshot_tree(self.root), before)
        self.assertNotIn("PROMPT PRIVADO", out.getvalue())
        self.assertNotIn("EVENTOS PRIVADOS", out.getvalue())
        return code, out.getvalue(), err.getvalue()

    def test_aprobacion_de_ambos_casos_con_referencias_historicas_y_sin_eventos(self):
        for case in ("case_01", "case_02"):
            with self.subTest(case=case):
                self.result["caso"] = case
                self.result["intentos"] = [self.attempt(1)]
                code, out, err = self.query()
                self.assertEqual((code, err), (0, ""))
                self.assertIn(f"Caso: {case}", out)
                self.assertIn("total 2, correctas 1, fallos 1, errores 0, omisiones 0", out)
                self.assertIn("pruebas superadas; total 2, correctas 2", out)
                self.assertIn("Dictamen registrado del modelo: aprobar; hallazgos: 0", out)
                self.assertIn("Decisión del controlador de revisión: aprobada; código 0", out)
                self.assertIn("desarrollador 1, revisor 1, total 2/4", out)
                self.assertIn("Segundo intento: no registrado", out)
                self.assertIn("Duración: 12.346 s", out)
                self.assertIn("Modelo / proveedor / esfuerzo (Revisor): no consta", out)

    def test_segundo_intento_tras_aserciones_con_tres_invocaciones(self):
        self.result["intentos"] = [self.attempt(1, failed=True), self.attempt(2)]
        self.result["invocaciones"] = {"desarrollador": 2, "revisor": 1, "total": 3}
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Intentos registrados: 2/2", out)
        self.assertIn("total 3/4", out)
        self.assertIn("desarrollo -> corregir (fallos_asercion)", out)
        self.assertIn("Revisión: no ejecutada según las etapas registradas", out)
        self.assertIn("Segundo intento: registrado; no se verifica su continuidad", out)

    def test_segundo_intento_tras_dictamen_y_agotamiento(self):
        self.result["intentos"] = [self.attempt(i, verdict="solicitar_cambios") for i in (1, 2)]
        self.result.update(estado="intentos_agotados", codigo_salida=1)
        self.result["invocaciones"] = {"desarrollador": 2, "revisor": 2, "total": 4}
        self.result["intentos"][-1]["transiciones"].append({
            "etapa": "presupuesto", "accion": "detener", "motivo": "intentos_agotados"})
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("código de la ejecución: 1", out)
        self.assertIn("Dictamen registrado del modelo: solicitar_cambios; hallazgos: 1", out)
        self.assertIn("presupuesto -> detener (intentos_agotados)", out)
        self.assertIn("Consulta: completada (código 0)", out)

    def technical_stop(self):
        entry = self.result["intentos"][0]
        entry["revision"] = None
        entry["transiciones"] = [{"etapa": "desarrollo", "accion": "detener", "motivo": "fallo_agente"}]
        repair = entry["reparacion"]
        repair.update(estado="fallo_agente", codigo_salida=3, detencion="fallo_agente")
        repair["agente"].update(estado="error_inicio", codigo_salida=9, error="falló el arranque")
        repair["pruebas_posteriores"] = {"estado": "no_ejecutadas", "codigo_salida": None}
        self.result.update(estado="fallo_agente", codigo_salida=3)
        self.result["invocaciones"] = {"desarrollador": 1, "revisor": 0, "total": 1}
        return repair

    def test_detencion_tecnica_consultada_con_exito_y_sin_inventar_ceros(self):
        self.technical_stop()
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Estado del controlador: fallo_agente; código de la ejecución: 3", out)
        self.assertIn("recuentos: no consta (no ejecutadas)", out)
        self.assertIn("Error registrado (Desarrollador): falló el arranque", out)

    def test_timeout_con_informe_parcial_no_es_material_ausente(self):
        repair = self.technical_stop()
        repair["pruebas_iniciales"] = {"estado": "tiempo_agotado", "codigo_salida": -9}
        directory = Path(repair["registro"])
        self.save(directory / "inicial/resultado.json", repair["pruebas_iniciales"])
        self.save(directory / "inicial/stderr.txt", "test_a (test_solution.Historicas.test_a) ... ")
        self.result.update(estado="tiempo_agotado", codigo_salida=4)
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("evaluación incompleta; recuentos: no consta", out)

    def test_dictamen_aprobar_no_oculta_fallo_del_revisor_o_integridad(self):
        review = self.result["intentos"][0]["revision"]
        review.update(decision_controlador="fallo_revisor", codigo_salida=3)
        review["revisor"].update(codigo_salida=9, error="fallo técnico")
        review["integridad"]["workspace_intacto"] = False
        self.result.update(estado="fallo_revisor", codigo_salida=3)
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Dictamen registrado del modelo: aprobar", out)
        self.assertIn("Decisión del controlador de revisión: fallo_revisor; código 3", out)
        self.assertIn("Integridad registrada (revisión): workspace_intacto=false", out)
        self.assertIn("no se recalculan hashes", out)

    def test_revisor_no_invocado_y_respuesta_invalida(self):
        for state, invocations, decision in [("no_ejecutado", 0, "evidencia_invalida"),
                                              ("finalizada", 1, "respuesta_invalida")]:
            with self.subTest(state=state):
                review = self.result["intentos"][0]["revision"]
                review.update(dictamen_modelo=None, decision_controlador=decision, error_respuesta="sin dictamen válido")
                review["revisor"].update(estado=state, invocaciones=invocations)
                code, out, err = self.query()
                self.assertEqual((code, err), (0, ""))
                self.assertIn("Dictamen registrado del modelo: no consta", out)
                self.assertIn(f"Revisor: {state}; invocaciones registradas: {invocations}", out)

    def test_campos_ausentes_no_se_convierten_en_cero(self):
        del self.result["invocaciones"]["desarrollador"]
        del self.result["max_intentos"]
        del self.result["duracion_segundos"]
        del self.result["integridad"]
        del self.result["errores_controlador"]
        code, out, err = self.query()
        self.assertEqual(code, 1)
        self.assertIn("desarrollador no consta, revisor 1, total 2/4", out)
        self.assertIn("Intentos registrados: 1/no consta", out)
        self.assertIn("Duración: no consta", out)
        self.assertIn("Integridad registrada (general): no consta", out)
        self.assertIn("Errores del controlador (general): no consta", out)
        self.assertIn("falta desarrollador", err)

    def test_etapa_interrumpida_conserva_resumen_parcial(self):
        self.result.update(estado="en_curso", codigo_salida=None, duracion_segundos=None)
        self.result["intentos"] = [{"numero": 1, "reparacion": None, "revision": None, "transiciones": []}]
        code, out, err = self.query()
        self.assertEqual(code, 1)
        self.assertIn("en_curso; código de la ejecución: no consta", out)
        self.assertIn("Reparación: no consta; intento incompleto", out)
        self.assertIn("falta el resultado de reparación", err)

    def test_revision_prevista_sin_resultado_es_incompleta(self):
        entry = self.result["intentos"][0]
        entry["revision"] = None
        entry["transiciones"] = entry["transiciones"][:1]
        code, out, err = self.query()
        self.assertEqual(code, 1)
        self.assertIn("Revisión: incompleta; sin resultado registrado", out)
        self.assertIn("revisión prevista sin resultado", err)

    def test_materiales_ausentes_o_json_enlazado_invalido(self):
        repair = Path(self.result["intentos"][0]["reparacion"]["registro"])
        review = Path(self.result["intentos"][0]["revision"]["registro"])
        for path in [repair/"posterior/stderr.txt", repair/"referencia/test_solution.py",
                     repair/"posterior/resultado.json", review/"resultado.json"]:
            for replacement in (None, b"\xff"):
                with self.subTest(path=path.name, replacement=replacement):
                    self.write_records()
                    old = path.read_bytes()
                    try:
                        if replacement is None:
                            path.unlink()
                        else:
                            path.write_bytes(replacement)
                        code, out, err = self.query(write=False)
                        self.assertEqual(code, 1)
                        self.assertIn("Estado del controlador: aprobada", out)
                        self.assertIn(str(path), err)
                    finally:
                        path.write_bytes(old)

    def test_informes_sin_pruebas_cruzados_duplicados_o_truncados(self):
        directory = Path(self.result["intentos"][0]["reparacion"]["registro"])
        for text in ["OK\n", report(["ok", "ok"]).replace("Historicas", "OtroCaso"),
                     report(["ok", "ok"]).replace("test_b", "test_a"),
                     report(["ok", "ok"]).replace("Ran 2", "Ran 20"),
                     report(["ok", "ok"]).removesuffix("OK\n")]:
            with self.subTest(text=text):
                self.save(directory/"posterior/stderr.txt", text)
                code, out, err = self.query()
                self.assertEqual(code, 1)
                self.assertIn("informe incompleto o no acreditado; recuentos: no consta", out)
                self.assertNotIn("pruebas superadas;", out)

    def test_error_de_pruebas_con_recuentos_y_cierre_coherentes(self):
        repair = self.technical_stop()
        repair["pruebas_iniciales"]["codigo_salida"] = 1
        directory = Path(repair["registro"])
        self.save(directory/"inicial/resultado.json", repair["pruebas_iniciales"])
        text = report(["ERROR", "ok"])
        self.save(directory/"inicial/stderr.txt", text)
        code, out, err = self.query()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("errores de pruebas; total 2, correctas 1, fallos 0, errores 1", out)
        self.save(directory/"inicial/stderr.txt", text.replace("errors=1", "errors=0"))
        self.assertEqual(self.query()[0], 1)

    def test_json_general_invalido_o_ambiguo(self):
        for raw in ('{', '[]', 'null', '{"caso":1,"caso":2}', '{"duracion_segundos":NaN}'):
            with self.subTest(raw=raw):
                self.save(self.general/"resultado.json", raw)
                code, out, err = self.query(write=False)
                self.assertEqual(code, 1)
                self.assertIn("JSON inválido", err)
                self.assertNotIn("Traceback", err)

    def test_tipos_incorrectos_no_producen_traceback(self):
        for field, value in [("intentos", {}), ("invocaciones", []), ("max_intentos", True),
                             ("max_invocaciones", -1), ("duracion_segundos", "doce")]:
            with self.subTest(field=field):
                old = self.result[field]
                self.result[field] = value
                self.save(self.general/"resultado.json", self.result)
                self.assertEqual(self.query(write=False)[0], 1)
                self.result[field] = old

    def test_resumen_enlazado_distinto_no_sustituye_decision_general(self):
        self.write_records()
        review = Path(self.result["intentos"][0]["revision"]["registro"])
        self.save(review/"resultado.json", {"decision_controlador": "fallo_revisor"})
        code, out, err = self.query(write=False)
        self.assertEqual(code, 1)
        self.assertIn("difiere del resumen general", err)
        self.assertIn("Decisión del controlador de revisión: aprobada", out)

    def test_rutas_relativas_se_resuelven_desde_registro_general(self):
        entry = self.result["intentos"][0]
        entry["reparacion"]["registro"] = "../reparacion 1"
        entry["revision"]["registro"] = "../revision 1"
        self.assertEqual(self.query()[0], 0)

    def test_cli_codigos_propios_desde_otro_directorio(self):
        self.technical_stop()
        self.write_records()
        command = [sys.executable, "-B", str(SCRIPT)]
        def call(args):
            return subprocess.run(command+args, cwd=self.root, capture_output=True,
                                  env=dict(os.environ, PATH=""), text=True, timeout=5)
        before = snapshot_tree(self.root)
        completed = call(["--run", "registro general"])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("código de la ejecución: 3", completed.stdout)
        self.assertEqual(call(["--run", "ausente"]).returncode, 1)
        for args in ([], ["--run"], ["--otro", "x"]):
            self.assertEqual(call(args).returncode, 2)
        self.assertEqual(snapshot_tree(self.root), before)


if __name__ == "__main__":
    unittest.main()

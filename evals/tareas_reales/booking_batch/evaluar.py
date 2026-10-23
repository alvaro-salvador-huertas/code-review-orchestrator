"""Aceptación 008 en hijos; sin oráculo de dominio ni importación del candidato.

Autoridades junto al evaluador congelado, nunca desde --project. Las sondas no
son aislamiento de seguridad ni prueba exhaustiva de ausencia de efectos.
"""
import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
AUTHORITY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AUTHORITY_ROOT))
from repair_case import run_process

TIMEOUT = 10
QUERIES = []
PRIVATE = {".git", "runs", ".codex", ".agents", ".aws", ".venv", ".env"}
AVAILABLE = {"disponible": True, "conflictos": []}


def snapshot(directory, *, project=False):
    result = {}
    def visit(path):
        info = path.lstat()
        private = project and path != directory and (path.name in PRIVATE or path.name.startswith(".env."))
        value = None
        if stat.S_ISREG(info.st_mode) and not private:
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            value = os.readlink(path)
        result[path.relative_to(directory).as_posix()] = (info.st_mode, info.st_mtime_ns, value)
        if stat.S_ISDIR(info.st_mode) and not private:
            for child in sorted(path.iterdir()):
                visit(child)
    visit(directory)
    return result


def booking(identifier, start="10:00:00", end="11:00:00", resource="Sala Norte"):
    return {"id": identifier, "recurso": resource,
            "inicio": "2026-10-23T" + start + "Z", "fin": "2026-10-23T" + end + "Z"}


def document(reservations=(), resource="Sala Norte"):
    return {"solicitud": {"recurso": resource, "inicio": "2026-10-23T10:00:00Z",
                          "fin": "2026-10-23T11:00:00Z"},
            "reservas": copy.deepcopy(list(reservations))}


def encode(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clave duplicada")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Constante no JSON: " + value)


def decode(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


# Ejecutado solo en el hijo. No exige helper público ni forma de importación.
PROBE = r'''
import copy
import importlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

project, mode, filename = sys.argv[1:]
sys.path.insert(0, project)
import booking_core
calls, references = [], []
results = [{"disponible": False, "conflictos": ["centinela 1 ñ"]},
           {"disponible": True, "conflictos": []},
           {"disponible": False, "conflictos": ["centinela 3"]}]

def delegated(data):
    calls.append(copy.deepcopy(data))
    references.append((data, copy.deepcopy(data)))
    if mode == "error" and len(calls) == 2:
        raise booking_core.InvalidInput("dominio sintético inválido")
    return copy.deepcopy(results[(len(calls) - 1) % len(results)])

if mode != "import":
    booking_core.check_booking = delegated
report = {"codigo": 0, "excepcion": None, "efectos": []}
active = False

def forbidden(effect):
    report["efectos"].append(effect)
    raise RuntimeError("Efecto propio prohibido: " + effect)

class NoInput:
    @property
    def buffer(self): return self
    def read(self, *args, **kwargs): forbidden("stdin")
    readline = read
    readlines = read
    def __iter__(self): forbidden("stdin")
    def fileno(self): forbidden("stdin")
sys.stdin = sys.__stdin__ = NoInput()
original_read = os.read

def read(fd, size):
    if active and fd == 0: forbidden("stdin")
    return original_read(fd, size)
os.read = read

def audit(event, args):
    if not active:
        return
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"):
        forbidden(event)
    if mode == "import" and event == "open":
        # El llamador inmediato distingue get_data del importador de open/Path
        # propios del producto. No basta con que importlib aparezca en la pila.
        caller = sys._getframe(1).f_globals.get("__name__", "")
        flags = args[2]
        loader = caller in ("_frozen_importlib_external", "importlib._bootstrap_external", "zipimport")
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        if writing or not loader:
            forbidden("open")
sys.addaudithook(audit)
saved = os.dup(1), os.dup(2)
# Descriptores reales: print, .buffer, reconfigure y os.write.
with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(out.fileno(), 1)
    os.dup2(err.fileno(), 2)
    try:
        active = True
        if mode == "import":
            sys.argv = [str(Path(project) / "booking_batch.py"), "ENTRADA_NO_ABRIR"]
            importlib.import_module("booking_batch")
        else:
            sys.argv = [str(Path(project) / "booking_batch.py"), filename]
            runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        report["codigo"] = exc.code if isinstance(exc.code, int) else 0 if exc.code is None else 1
        if mode == "import": report["excepcion"] = "SystemExit durante importación"
    except BaseException as exc:
        report["excepcion"] = type(exc).__name__ + ": " + str(exc)
    finally:
        active = False
        sys.stdout.flush()
        sys.stderr.flush()
        for fd, destination in zip(saved, (1, 2)):
            os.dup2(fd, destination)
            os.close(fd)
    out.seek(0)
    err.seek(0)
    report.update(stdout_hex=out.read().hex(), stderr_hex=err.read().hex())
def identity(value):
    # True == 1 en Python; comparar valores JSON incluyendo sus tipos, sin
    # convertir el orden de claves de un objeto en un requisito contractual.
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
report.update(llamadas=calls, conservadas=all(identity(data) == identity(before)
                                            for data, before in references))
print(json.dumps(report, ensure_ascii=True))
'''


class AcceptanceTests(unittest.TestCase):
    project = None

    def check_candidate(self):
        path = self.project / "booking_batch.py"
        try:
            info = path.lstat()
        except FileNotFoundError:
            self.fail("Funcionalidad pendiente: falta booking_batch.py regular 0644; hijo no invocado")
        self.assertTrue(stat.S_ISREG(info.st_mode), "booking_batch.py no es regular; hijo no invocado")
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o644, "booking_batch.py requiere 0644; hijo no invocado")
        return path

    def setUp(self):
        self.script = self.check_candidate()
        for attr, prefix in (("root", "entrada-booking-batch-"), ("logs", "canales-booking-batch-")):
            temporary = tempfile.TemporaryDirectory(prefix=prefix)
            self.addCleanup(temporary.cleanup)
            setattr(self, attr, Path(temporary.name))

    def save(self, value=None, *, raw=None, name="lote sintético.json"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else encode([] if value is None else value))
        return name

    @contextmanager
    def query(self, arguments, *, probe=None):
        self.check_candidate()
        command = [str(Path(sys.executable).resolve()), "-B"]
        if probe:
            core = self.project / "booking_core.py"
            self.assertTrue(core.exists() and stat.S_ISREG(core.lstat().st_mode), "Falta núcleo protegido regular")
            command += ["-c", PROBE, str(self.project), probe, *arguments]
        else:
            command += [str(self.script), *arguments]
        before = snapshot(self.root), snapshot(self.project, project=True)
        record = {"tipo": probe or "cli", "entradas_hex": {
            str(p.relative_to(self.root)): p.read_bytes().hex()
            for p in self.root.rglob("*") if p.is_file()}}
        QUERIES.append(record)
        try:
            directory = self.logs / str(len(QUERIES))
            result = run_process(command, self.root, directory, TIMEOUT, env_policy="evaluation")
            stdout, stderr = (directory / "stdout.txt").read_bytes(), (directory / "stderr.txt").read_bytes()
            record.update(result, stdout_hex=stdout.hex(), stderr_hex=stderr.hex())
            self.assertEqual(result["estado"], "finalizada", result)
            yield result["codigo_salida"], stdout, stderr
        finally:
            with self.subTest(conservacion="entradas"):
                self.assertEqual(snapshot(self.root), before[0], "El hijo alteró entradas o creó archivos")
            with self.subTest(conservacion="proyecto"):
                self.assertEqual(snapshot(self.project, project=True), before[1], "El hijo alteró el proyecto")

    def assert_success(self, result, expected):
        code, stdout, stderr = result
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, b"")
        self.assertTrue(stdout.endswith(b"\n"), "Falta salto de línea final")
        try:
            actual = decode(stdout)
        except (ValueError, UnicodeError, RecursionError) as exc:
            self.fail(f"stdout no es un único JSON UTF-8: {exc}")
        self.assertIs(type(actual), list)
        for item in actual:
            self.assertIs(type(item), dict)
            self.assertEqual(set(item), {"disponible", "conflictos"})
            self.assertIs(type(item["disponible"]), bool)
            self.assertIs(type(item["conflictos"]), list)
            self.assertTrue(all(type(x) is str for x in item["conflictos"]))
        self.assertEqual(actual, expected)

    def assert_error(self, result, *, code=1, position=None):
        actual, stdout, stderr = result
        self.assertEqual(actual, code, stderr)
        self.assertEqual(stdout, b"", "Salida parcial ante error")
        self.assertTrue(stderr.strip(), "Diagnóstico vacío")
        if position is not None:
            diagnostic = stderr.decode("utf-8", errors="replace")
            words = {1: r"primera?|first", 2: r"segunda?|second", 3: r"tercera?|third"}
            pattern = rf"(?<!\d){position}(?!\d)|\b(?:{words[position]})\b"
            self.assertRegex(diagnostic.lower(), pattern, "Falta posición de consulta desde 1")
            cause = re.sub(pattern, "", diagnostic, flags=re.IGNORECASE)
            cause = re.sub(r"\b(?:error|consulta|query|posición|position|index|índice)\b", "", cause, flags=re.IGNORECASE)
            self.assertTrue(any(ch.isalpha() for ch in cause), "Falta causa además de la posición")

    def success(self, data, expected, *, name="lote sintético.json", prefix=()):
        with self.query([*prefix, self.save(data, name=name)]) as result:
            self.assert_success(result, expected)

    def invalid(self, *, value=None, raw=None, position=None):
        with self.query([self.save(value, raw=raw)]) as result:
            self.assert_error(result, position=position)

    def probe(self, mode, data=None):
        name = self.save(data)
        with self.query([name], probe=mode) as result:
            code, stdout, stderr = result
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stderr, b"")
            try:
                report = decode(stdout)
            except (ValueError, UnicodeError) as exc:
                self.fail(f"Informe de sonda inválido: {exc}")
            self.assertIsNone(report["excepcion"], report)
            self.assertEqual(report["efectos"], [])
            return report

    def test_01_lote_vacio_y_espacio_exterior(self):
        for raw in (b"[]", b" \r\n\t[] \t\n"):
            with self.subTest(entrada=raw), self.query([self.save(raw=raw)]) as result:
                self.assert_success(result, [])

    def test_02_consulta_disponible(self):
        self.success([document()], [AVAILABLE])

    def test_03_mixtas_orden_y_conflictos(self):
        data = document([booking("r2", "10:15:00", "10:45:00"), booking("r1", "10:30:00", "11:30:00")])
        self.success([document(), data, document()], [AVAILABLE, {"disponible": False, "conflictos": ["r2", "r1"]}, AVAILABLE])

    def test_04_repeticiones_e_independencia(self):
        first = document([booking("mismo")])
        second = document([booking("mismo", resource="Otra")])
        self.success([first, second, first], [{"disponible": False, "conflictos": ["mismo"]}, AVAILABLE,
                                            {"disponible": False, "conflictos": ["mismo"]}])

    def test_05_extremos_de_intervalo(self):
        self.success([document([booking("antes", "09:00:00", "10:00:00"), booking("después", "11:00:00", "12:00:00")]),
                      document([booking("igual"), booking("contiene", "09:00:00", "12:00:00")])],
                     [AVAILABLE, {"disponible": False, "conflictos": ["igual", "contiene"]}])

    def test_06_unicode_y_escapes_literales(self):
        resource, identifier = ' Sala É "norte"\n🪑 ', ' id "uno"\r\nñ '
        data = document([booking(identifier, resource=resource), booking("otro", resource=resource.strip())], resource)
        for escaped in (False, True):
            raw = json.dumps([data], ensure_ascii=escaped).encode("utf-8")
            with self.subTest(escapes=escaped), self.query([self.save(raw=raw)]) as result:
                self.assert_success(result, [{"disponible": False, "conflictos": [identifier]}])

    def test_07_ids_duplicados_dentro_de_consulta(self):
        self.invalid(value=[document([booking("r"), booking("r", resource="Otra")])], position=1)

    def test_08_dominio_invalido_primera_consulta(self):
        for value in (None, {}, [], True, {**document(), "extra": 1}):
            with self.subTest(valor=value):
                self.invalid(value=[value, document()], position=1)

    def test_09_error_ultima_consulta_sin_salida_parcial(self):
        data = document([booking("conflicto"), booking("posterior", resource="Otra")])
        del data["reservas"][1]["fin"]
        self.invalid(value=[document(), document([booking("r")]), data], position=3)

    def test_10_fechas_y_tipos_delegados(self):
        for field, value in (("inicio", "2026-10-23T10:00:00+00:00"), ("inicio", "2026-02-30T10:00:00Z"),
                             ("fin", "2026-10-23T10:00:00Z"), ("recurso", 7), ("recurso", "\t ")):
            data = document()
            data["solicitud"][field] = value
            with self.subTest(campo=field, valor=value):
                self.invalid(value=[data], position=1)

    def test_11_json_invalido_y_concatenado(self):
        for raw in (b"", b"[", b"[] []", b"[]texto", b"[1,]"):
            with self.subTest(entrada=raw): self.invalid(raw=raw)

    def test_12_constantes_no_json(self):
        for raw in (b"[NaN]", b"[Infinity]", b"[-Infinity]"):
            with self.subTest(entrada=raw): self.invalid(raw=raw)

    def test_13_utf8_invalido_y_bom(self):
        for raw in (b"\xff", b"\xef\xbb\xbf[]", '[]'.encode('utf-16'), b'["\xc3("]'):
            with self.subTest(entrada=raw): self.invalid(raw=raw)

    def test_14_raiz_no_lista(self):
        for raw in (b"{}", b"null", b"true", b"1", b'"texto"'):
            with self.subTest(entrada=raw): self.invalid(raw=raw)

    def test_15_claves_duplicadas_en_varios_niveles(self):
        good = encode([document([booking("r")])])
        for before, after in ((b'"solicitud":', b'"solicitud": {}, "solicitud":'),
                              (b'"recurso": "Sala Norte"', b'"recurso": "Sala Norte", "recurso": "Sala Norte"'),
                              (b'"id": "r"', b'"id": "r", "\\u0069d": "r"')):
            with self.subTest(duplicado=before): self.invalid(raw=good.replace(before, after, 1))

    def test_16_archivo_inexistente_y_directorio(self):
        (self.root / "directorio").mkdir()
        for name in ("no existe.json", "directorio"):
            with self.subTest(ruta=name), self.query([name]) as result:
                self.assert_error(result)

    def test_17_ayuda_unicamente_argumento_unico(self):
        for arg in ("-h", "--help"):
            with self.subTest(argumento=arg), self.query([arg]) as (code, out, err):
                self.assertEqual(code, 0)
                self.assertTrue(out.strip())
                self.assertEqual(err, b"")

    def test_18_argumentos_invalidos(self):
        name = self.save([])
        cases = [[], ["--"], [name, name], ["--", name, name], ["--help", name], [name, "--help"],
                 ["-h", name], ["--help", "-h"], ["-h", "-h"], ["--desconocido"], ["--he"], ["-lote"]]
        for args in cases:
            with self.subTest(argumentos=args), self.query(args) as result:
                self.assert_error(result, code=2)

    def test_19_rutas_literales_con_guiones(self):
        for name in ("-h", "--help", "-lote", "--", "lote.json"):
            with self.subTest(nombre=name): self.success([], [], name=name, prefix=("--",))

    def test_20_guion_es_archivo_no_stdin(self):
        self.success([document()], [AVAILABLE], name="-")

    def test_21_rutas_absolutas_relativas_y_sin_extension(self):
        name = self.save([document()], name="carpeta con espacios/consulta ñ")
        for path in (name, str(self.root / name)):
            with self.subTest(ruta=path), self.query([path]) as result:
                self.assert_success(result, [AVAILABLE])

    def test_22_texto_se_trata_como_datos(self):
        marker = "__import__('pathlib').Path('NO_EJECUTAR').write_text('marca')"
        self.success([document([booking(marker)])], [{"disponible": False, "conflictos": [marker]}])

    def test_23_importacion_sin_efectos(self):
        report = self.probe("import")
        self.assertEqual(report["codigo"], 0)
        self.assertEqual(report["stdout_hex"], "")
        self.assertEqual(report["stderr_hex"], "")

    def test_24_delegacion_completa_resultados_y_conservacion(self):
        data = [{"marca": " ñ ", "anidado": [1, {"x": True}]}, {"marca": "segunda"}, {"marca": "tercera"}]
        report = self.probe("ok", data)
        self.assertEqual(json.dumps(report["llamadas"], sort_keys=True), json.dumps(data, sort_keys=True))
        self.assertIs(report["conservadas"], True)
        self.assert_success((report["codigo"], bytes.fromhex(report["stdout_hex"]), bytes.fromhex(report["stderr_hex"])),
                            [{"disponible": False, "conflictos": ["centinela 1 ñ"]}, AVAILABLE,
                             {"disponible": False, "conflictos": ["centinela 3"]}])

    def test_25_invalidinput_delegado_sin_resultado_parcial(self):
        data = [{"marca": 1}, {"marca": 2}, {"marca": 3}]
        report = self.probe("error", data)
        self.assertIn(len(report["llamadas"]), (2, 3))
        self.assertEqual(json.dumps(report["llamadas"], sort_keys=True),
                         json.dumps(data[:len(report["llamadas"])], sort_keys=True))
        self.assertIs(report["conservadas"], True)
        self.assert_error((report["codigo"], bytes.fromhex(report["stdout_hex"]), bytes.fromhex(report["stderr_hex"])), position=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Traza fuera del proyecto evaluado")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if not project.is_dir(): parser.error("--project debe ser un directorio")
    AcceptanceTests.project = project
    QUERIES.clear()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests))
    trace = {"procesos": len(QUERIES), "consultas": QUERIES}
    if args.output:
        args.output.write_text(json.dumps(trace, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(trace, ensure_ascii=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

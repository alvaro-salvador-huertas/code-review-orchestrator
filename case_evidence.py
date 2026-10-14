"""Lectura e integridad de evidencia; nunca importa ni ejecuta candidatos."""

import ast
import difflib
import hashlib
import json
import re
import stat


def read_regular(path):
    """No seguir enlaces ni abrir dispositivos al recoger entregables."""
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return None
        return path.read_bytes()
    except FileNotFoundError:
        return None


def digest(content):
    return hashlib.sha256(content).hexdigest() if content is not None else None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_json(content):
    """Rechazar JSON ambiguo: claves duplicadas, NaN e infinitos."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Clave JSON duplicada: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Constante JSON no admitida: {value}")

    return json.loads(content.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def snapshot_tree(directory):
    """Inventariar archivos sin aceptar enlaces ni archivos especiales."""
    require(directory.is_dir() and not directory.is_symlink(), f"Directorio inválido: {directory}")
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"Enlace no permitido: {path}")
        if path.is_dir():
            continue
        content = read_regular(path)
        require(content is not None, f"No es un archivo regular: {path}")
        result[path.relative_to(directory).as_posix()] = digest(content)
    return result


def snapshot_matches(directory, expected):
    try:
        return snapshot_tree(directory) == expected
    except (OSError, ValueError):
        return False


def reference_test_ids(reference):
    """Leer las pruebas explícitas de unittest mediante AST, sin importarlas."""
    try:
        tree = ast.parse(reference, filename="test_solution.py")
    except SyntaxError as exc:
        raise ValueError(f"Pruebas de referencia con sintaxis inválida: {exc}") from exc
    identifiers = []
    for node in tree.body:
        require(not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == "load_tests"),
                "No se admite descubrimiento dinámico mediante load_tests")
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [method.name for method in node.body
                   if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and method.name.startswith("test")]
        if not methods:
            continue
        require(any(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                    and base.value.id == "unittest" and base.attr == "TestCase"
                    or isinstance(base, ast.Name) and base.id == "TestCase"
                    for base in node.bases),
                f"Clase de pruebas no admitida para lectura estática: {node.name}")
        identifiers.extend(f"test_solution.{node.name}.{method}" for method in methods)
    require(identifiers and len(set(identifiers)) == len(identifiers),
            "Las referencias deben declarar pruebas explícitas sin identificadores duplicados")
    return sorted(identifiers)


def validate_test_report(reference, report):
    require(classify_test_report(reference, report, 0) == "superadas",
            "El informe no acredita todas las pruebas superadas")


def classify_test_report(reference, report, exit_code):
    """Solo un informe completo de aserciones permite corregir un candidato."""
    expected = reference_test_ids(reference)
    summaries = list(re.finditer(r"(?m)^Ran (\d+) tests? in [0-9.]+s$", report))
    require(len(summaries) == 1 and int(summaries[0].group(1)) == len(expected),
            "El total no acredita las pruebas de referencia completas")
    rows = [line for line in report.splitlines() if line.startswith("test")]
    actual, failed, errors = [], [], []
    for row in rows:
        match = re.fullmatch(r"(test\w*) \((test_solution\.\w+\.(test\w*))\) \.\.\. (ok|FAIL|ERROR)", row)
        require(match is not None and match.group(1) == match.group(3),
                "Prueba omitida, fallida o fila de informe inválida")
        actual.append(match.group(2))
        if match.group(4) == "FAIL":
            failed.append(match.group(2))
        if match.group(4) == "ERROR":
            errors.append(match.group(2))
    require(sorted(actual) == expected,
            "El número y los nombres del informe no coinciden con las pruebas conservadas")
    ending = report[summaries[0].end():]
    if errors:
        require(exit_code == 1 and "FAILED (" in ending, "Código o cierre inconsistente")
        return "error_pruebas"
    if not failed:
        require(type(exit_code) is int and exit_code == 0
                and re.fullmatch(r"\n\nOK\s*", ending) is not None
                and re.search(r"(?m)^(FAIL:|ERROR:|Traceback \()", report) is None,
                "El código o el cierre no acredita pruebas superadas")
        return "superadas"
    require(type(exit_code) is int and exit_code == 1
            and re.fullmatch(rf"\n\nFAILED \(failures={len(failed)}\)\s*", ending) is not None,
            "Código o cierre de fallos inconsistente")
    require(len(re.findall(r"(?m)^FAIL:", report)) == len(failed)
            and re.search(r"(?m)^ERROR:", report) is None, "Diagnósticos de fallos incoherentes")
    details = re.findall(
        r"(?ms)^FAIL: (test\w*) \((test_solution\.\w+\.(test\w*))\)\n"
        r"-+\n(.*?)(?=^=+\n|^-+\nRan |\Z)", report[:summaries[0].start()])
    require(sorted(item[1] for item in details) == sorted(failed),
            "Faltan diagnósticos de los fallos de aserción")
    for name, _, method, detail in details:
        require(name == method and "Traceback (most recent call last):" in detail
                and re.search(r"(?m)^AssertionError(?::.*)?$", detail) is not None,
                "El fallo no acredita una aserción del candidato")
    return "fallos_asercion"


def unified_diff(before, after, fromfile, tofile):
    return b"".join(difflib.diff_bytes(
        difflib.unified_diff, before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=fromfile.encode(), tofile=tofile.encode(),
    ))

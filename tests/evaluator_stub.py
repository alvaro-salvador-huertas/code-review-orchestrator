"""Sustitución SOLO en fixtures: ejecuta código sintético en el anfitrión.

No comprueba aislamiento. La integración real está en test_python_isolation_real.
No existe ninguna opción equivalente en el controlador de producción.
"""

import json
from pathlib import Path
import sys
from unittest.mock import patch

import project_flow


STUB = r'''
def run_isolated(command, workspace, log, timeout, *, materials, runner):
    import sys
    logical = list(command)
    result = runner([sys.executable, *command[1:]], workspace, log, timeout, env_policy='evaluation')
    result['comando'] = logical
    result['aislamiento'] = {'version': 2, 'runtime': 'podman-rootless', 'imagen': IMAGE,
        'contenedor': 'cro-eval-simulado', 'limpieza_confirmada': True, 'volumen_resultados':'cro-eval-simulado-results', 'limites_salida':normalize_limits(),
        'comando_runtime': container_command('cro-eval-simulado', logical, workspace,
            [(workspace, workspace, False), *((p, p, False) for p in materials)],
            result_volume='cro-eval-simulado-results', result_target=log)}
    if len(command) > 2 and command[2].endswith('project_test_inventory.py'):
        try:
            report = json.loads((log / 'stdout.txt').read_text())
            report['interprete'] = logical[0]
            write_json(log / 'stdout.txt', report)
        except (ValueError, FileNotFoundError):
            pass
    write_json(log / 'resultado.json', result)
    return result
'''


def simulated():
    import python_evaluator
    namespace = vars(python_evaluator).copy()
    exec(STUB, namespace)
    return namespace['run_isolated']


def install(testcase):
    import python_evaluator
    import repair_project
    substitute = simulated()
    testcase.addCleanup(patch.stopall)
    patch.object(project_flow, 'run_isolated', substitute).start()
    patch.object(repair_project, 'run_isolated', substitute).start()
    # Las CLI de los fixtures importan una copia privada del controlador.
    target = testcase.root / 'python_evaluator.py'
    target.write_text(Path(python_evaluator.__file__).read_text() + '\n' + STUB)


def install_case(testcase, directory):
    """Solo fixtures de casos: sustituir la frontera y la CLI privada."""
    import python_evaluator
    substitute = patch.object(python_evaluator, 'run_isolated', simulated())
    substitute.start()
    testcase.addCleanup(substitute.stop)
    directory = Path(directory)
    directory.joinpath('bounded_output.py').write_bytes(
        Path(python_evaluator.__file__).with_name('bounded_output.py').read_bytes())
    directory.joinpath('python_evaluator.py').write_text(
        Path(python_evaluator.__file__).read_text() + '\n' + STUB)

# code-review-orchestrator

Proyecto de aprendizaje sobre desarrollo y revisión de código con agentes.

## Estado actual

Hay un primer controlador local, `run_case.py`, que ejecuta un caso sobre una
copia de trabajo y guarda su registro. Hay dos casos preparados para el futuro
flujo de reparación. Cada uno incluye su contrato, una implementación con un
defecto intencionado y pruebas con `unittest`:

- **Caso 01: sumar minutos por asignatura.** Conserva el ejercicio inicial y
  sus cuatro pruebas. Cuando una asignatura se repite, la implementación
  sobrescribe su total con los últimos minutos en lugar de acumularlos.
- **Caso 02: clasificar una ejecución.** Añade ocho pruebas independientes para
  distinguir tiempo agotado, fallo de ejecución, respuesta vacía y ejecución
  completada. La implementación respeta las prioridades de tiempo agotado y
  fallo de ejecución, pero clasifica como `"completada"` cualquier ejecución con
  código cero, sin comprobar la respuesta. El archivo de tarea describe solo
  el comportamiento exigido y la implementación no incluye pistas en comentarios.

Los defectos se conservan deliberadamente. Las pruebas fallan de verdad:
ninguna está omitida ni marcada con `expectedFailure`.

En el caso 02, `"completada"` significa que la ejecución terminó técnicamente y
produjo texto; no certifica que la respuesta sea correcta. La función es pura:
clasifica los datos recibidos sin ejecutar procesos ni realizar entrada/salida.

El controlador ya prepara copias, ejecuta pruebas y registra resultados. Todavía
no hay agentes, reparaciones ni llamadas a modelos. La coordinación de un agente
desarrollador y otro revisor, junto con el límite de intentos de corrección,
sigue siendo una intención de diseño.

El siguiente hito será integrar el agente desarrollador.

## Estructura

```text
README.md
.gitignore                    # Excluye registros, cachés y configuración local
run_case.py                   # Controlador local
tests/
└── test_run_case.py           # Pruebas propias del controlador
tasks/
├── 001-sum-by-subject.md       # Contrato de suma por asignatura
└── 002-classify-run.md        # Contrato de clasificación de ejecuciones
benchmark/
├── case_01/
│   ├── solution.py            # Implementación inicial de suma
│   └── test_solution.py       # Cuatro pruebas con unittest
└── case_02/
    ├── solution.py            # Implementación inicial de clasificación
    └── test_solution.py       # Ocho pruebas con unittest
runs/                         # Registros locales generados; fuera de Git
```

## Ejecutar los casos

Solo se necesita Python 3 y su biblioteca estándar; no hay dependencias que
instalar. Desde la raíz del proyecto:

```sh
python3 run_case.py case_01
python3 run_case.py case_02
```

La interfaz acepta únicamente `case_01` y `case_02` mediante `argparse`.
El proyecto se localiza a partir de la ubicación del script, por lo que también
puede invocarse desde otro directorio:

```sh
python3 /ruta/al/proyecto/run_case.py case_01
```

Antes de iniciar las pruebas se comprueba que existen `solution.py`,
`test_solution.py` y el contrato del caso. Si falta alguno, el controlador
informa del problema, termina con código 1 y no crea un registro ni lanza pruebas.

Cada ejecución crea un registro único cuyo nombre contiene la fecha UTC, el
identificador del caso y un UUID. Copia la implementación y las pruebas al
`workspace/` del registro, y el contrato a `contrato.md`.

Las pruebas se ejecutan en un proceso separado con `subprocess.run`, usando el
mismo intérprete mediante `sys.executable`, argumentos en una lista y
`shell=False`. El comando usa `-B` y `unittest discover`, limitado al
`test_solution.py` del workspace. El directorio de trabajo (`cwd`) también es
ese workspace y el tiempo máximo es de 30 segundos. Así cada caso tiene su
propio proceso, sin conflictos entre los módulos llamados `solution`.

El controlador no importa las implementaciones de los casos ni utiliza la
función defectuosa del caso 02 para clasificar sus ejecuciones.

## Registros y estados

Una ejecución que consigue guardar su registro produce:

```text
runs/<fecha_UTC>_<caso>_<uuid>/
├── contrato.md
├── workspace/
│   ├── solution.py
│   └── test_solution.py
├── stdout.txt
├── stderr.txt
└── resultado.json
```

`stdout.txt` y `stderr.txt` conservan por separado la salida capturada, también
cuando las pruebas fallan o se agota el tiempo. `unittest` suele escribir su
informe en `stderr.txt`; `stdout.txt` puede estar vacío.

`resultado.json` guarda `caso`, `inicio_utc`, `fin_utc`, `duracion_segundos`,
`comando`, `directorio_trabajo`, `limite_segundos`, `estado`,
`codigo_salida_pruebas` y `errores_controlador`. Las fechas se expresan en UTC
con sufijo `Z`; la duración se mide con un reloj monotónico desde el inicio
del intento hasta antes de escribir el JSON. Las rutas del comando y del
directorio de trabajo son absolutas.

| Estado del controlador | Significado | Código del controlador |
| --- | --- | --- |
| `finalizada` | El proceso terminó y se guardó el resultado, aunque las pruebas devuelvan un código distinto de cero. | 0 |
| `tiempo_agotado` | El proceso alcanzó el límite de 30 segundos; se conserva la salida parcial disponible. | 1 |
| `error_ejecucion` | No se pudo preparar la ejecución, iniciar el proceso o completar el registro. | 1 |

`codigo_salida_pruebas` guarda por separado el código del proceso de pruebas.
Es `null` cuando no está disponible, incluidos el tiempo agotado y el error
al iniciar el proceso. Un código 1 puede deberse tanto a fallos de aserción
como a otros errores: el controlador no lo interpreta automáticamente.
Hay que consultar el informe de `stderr.txt`.

En terminal se muestran el estado, el código de las pruebas y la ubicación del
registro. **Ejecución finalizada no significa pruebas superadas.** Si se produce
un error de escritura, el controlador intenta conservar los demás archivos,
informa del error y termina con código 1; el registro puede quedar incompleto.
Los argumentos no admitidos se rechazan antes de ejecutar nada, con código 2.

## Validación

Las pruebas del controlador están separadas de los casos defectuosos:

```sh
python3 -B -m unittest discover -s tests -v
```

Última validación, realizada al implementar el controlador: **14 pruebas
correctas**, código de salida 0. Usan proyectos
temporales que se eliminan al terminar. Cubren procesos con códigos 0 y 1,
salidas separadas, registros diferentes, conservación de los originales,
invocación desde otro directorio, selección de casos, archivos requeridos
ausentes y errores al preparar o guardar el registro. El tiempo agotado y
el error al iniciar el proceso se simulan, sin esperar 30 segundos.

Después se ejecutaron ambos casos mediante `run_case.py` y se comprobaron sus
informes y las copias guardadas:

| Caso | Pruebas | Correctas | Fallos | Código de pruebas | Estado | Código del controlador |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | 4 | 3 | 1 | 1 | `finalizada` | 0 |
| 02 | 8 | 5 | 3 | 1 | `finalizada` | 0 |

No hubo errores de importación. Los dos contratos y los cuatro archivos de
`benchmark/` permanecieron idénticos a sus versiones anteriores a la ejecución.

El caso 01 terminó con `FAILED (failures=1)`. Pasaron lista vacía, asignaturas
distintas y conservación de la entrada. Falló únicamente la acumulación:
para `Python: 20`, `Redes: 30` y `Python: 15`, se obtuvo
`{"Python": 15, "Redes": 30}` en lugar de `{"Python": 35, "Redes": 30}`.

El caso 02 terminó con `FAILED (failures=3)`. Fallaron únicamente las tres
pruebas de código cero con respuesta vacía: cadena vacía, espacios y saltos de
línea, y `None`. En las tres se obtuvo `"completada"` en lugar de
`"respuesta_vacia"`. Pasaron las otras cinco pruebas: código cero con texto,
código distinto de cero con texto, código distinto de cero con respuesta
vacía, código `None` sin tiempo agotado y prioridad del tiempo agotado.

Para ejecutar directamente las pruebas originales, sin crear registros,
siguen disponibles estos comandos desde la raíz, cada uno en su propio proceso:

```sh
python3 -B -m unittest discover -s benchmark/case_01 -v
python3 -B -m unittest discover -s benchmark/case_02 -v
```

En la ejecución directa, ambos comandos terminan con código 1 por los defectos
intencionados. La opción `-B` evita generar archivos de bytecode.

## Alcance de los ejercicios

Estos ejercicios controlados ofrecen fallos reales y reproducibles para
comprobar más adelante el flujo de reparación: corregir cada defecto y
mantener los comportamientos que ya pasan las pruebas. Todavía no permiten
afirmar que exista un orquestador de agentes funcional ni medir su eficacia
general.

La copia de trabajo conserva los originales durante este flujo, pero **no
constituye un aislamiento de seguridad**. El proceso mantiene los permisos del
usuario y podría acceder a archivos fuera del workspace; `cwd` solo establece
el directorio de trabajo.

El orden de las condiciones del caso 02 preserva la prioridad del resultado:
el tiempo agotado prevalece sobre cualquier código o texto, y un fallo de
ejecución prevalece sobre una respuesta vacía. Solo tras descartar ambos se
evalúa si hubo texto para distinguir `"respuesta_vacia"` de `"completada"`.

# code-review-orchestrator

Proyecto de aprendizaje sobre desarrollo y revisión de código con agentes.

## Estado actual

`run_case.py` ejecuta un caso sobre una copia de trabajo y guarda su registro.
`repair_case.py case_02` añade un único intento de reparación mediante Codex CLI,
seguido de una evaluación independiente. `review_case.py --run <registro>`
revisa una reparación aceptada del caso 02 mediante otro agente, sin ejecutar
el candidato ni volver a llamar al desarrollador. `orchestrate_case.py case_02`
coordina ambas etapas con un máximo de dos intentos de desarrollo, incluidas
sus evaluaciones independientes. Además de la validación con Codex simulado,
la primera ejecución real coordinada terminó aprobada en **un intento y dos
invocaciones**. La corrección automática de un segundo intento todavía no se
ha observado con el modelo real.

Cada caso incluye su contrato, una implementación con un defecto intencionado
y pruebas con `unittest`:

- **Caso 01: sumar minutos por asignatura.** Conserva el ejercicio inicial y
  sus cuatro pruebas. Cuando una asignatura se repite, la implementación
  sobrescribe su total con los últimos minutos en lugar de acumularlos.
- **Caso 02: clasificar una ejecución (contrato versión 2).** Incluye 16 pruebas para
  distinguir tiempo agotado, fallo de ejecución, respuesta vacía y ejecución
  completada. La implementación respeta las prioridades de tiempo agotado y
  fallo de ejecución, pero clasifica como `"completada"` cualquier ejecución con
  código cero, sin comprobar la respuesta. El contrato define ahora los espacios
  en blanco mediante `str.isspace()`, incluidos tabuladores, retornos de carro
  y espacios Unicode. La implementación defectuosa se conserva intacta.

Los defectos se conservan deliberadamente. Las pruebas fallan de verdad:
ninguna está omitida ni marcada con `expectedFailure`.

En el caso 02, `"completada"` significa que la ejecución terminó técnicamente y
produjo texto; no certifica que la respuesta sea correcta. La función es pura:
clasifica los datos recibidos sin ejecutar procesos ni realizar entrada/salida.

El agente desarrollador recibe el contrato y el informe inicial, y puede editar
una copia de `solution.py`. El controlador conserva los originales y decide si
el candidato **supera las pruebas disponibles**. No hay reintentos automáticos
dentro de `repair_case.py`. El orquestador permite una sola corrección adicional
si hay presupuesto y la evidencia la justifica.

El hito anterior contó con una reparación y una revisión reales bajo versión 2,
lanzadas manualmente mediante dos comandos separados. La reparación pasó de
**9 pruebas correctas y 7 fallidas a 16 correctas**. El revisor emitió
**`aprobar`, sin hallazgos**, y el controlador registró **`aprobada`, código 0**,
con evidencia previa válida e integridad conservada. Sus acciones registradas
se limitaron a consultar y leer los materiales. Esta aprobación de un caso
sencillo no demuestra fiabilidad general.

La primera revisión real de la reparación de versión 1 solicitó cambios por
la interpretación de «espacios y saltos de línea». Ese dictamen motivó la
aclaración funcional de versión 2 y se conserva sin reclasificar. La coordinación
acotada descrita más abajo añade la posibilidad de una corrección. Se distinguen
las pruebas simuladas, estas etapas manuales históricas y la nueva ejecución
real coordinada.

El 14 de octubre de 2026, el segundo intento real del caso 02, lanzado
manualmente desde la terminal, produjo el primer candidato que supera sus ocho
pruebas de referencia de versión 1. El primer intento falló al inicializar Codex y se
conserva junto al satisfactorio. La evidencia, el diff exacto y las limitaciones
están en el [informe de resultados](evals/resultados-2026-10-14.md), junto con la
revisión y una reevaluación local posterior: el mismo candidato supera las
16 pruebas de versión 2. Esa comprobación local es anterior e independiente
de la nueva reparación y revisión de versión 2; no se le atribuye su aprobación.

## Estructura

```text
README.md
.gitignore                    # Excluye registros, cachés y configuración local
run_case.py                   # Controlador local
repair_case.py                # Un intento de reparación del caso 02
review_case.py                # Revisión estática de una reparación aceptada
orchestrate_case.py           # Desarrollo y revisión, máximo dos intentos
case_evidence.py              # Lectura estática de informes, hashes y diffs
prompts/
└── reviewer.md               # Instrucciones y formato del dictamen del revisor
tests/
├── test_run_case.py           # Pruebas del controlador inicial
├── test_repair_case.py        # Reparación con una CLI simulada, sin modelo
├── test_review_case.py        # Evidencia, dictámenes y fallos con CLI simulada
└── test_orchestrate_case.py   # Transiciones, continuidad y presupuesto simulados
tasks/
├── 001-sum-by-subject.md       # Contrato de suma por asignatura
└── 002-classify-run.md        # Contrato de clasificación de ejecuciones
benchmark/
├── case_01/
│   ├── solution.py            # Implementación inicial de suma
│   └── test_solution.py       # Cuatro pruebas con unittest
└── case_02/
    ├── solution.py            # Implementación inicial de clasificación
    └── test_solution.py       # 16 pruebas de referencia de la versión 2
evals/
└── resultados-2026-10-14.md    # Historia v1/v2, reevaluación y orquestación real
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

Validación del controlador inicial: **14 pruebas
correctas**, código de salida 0. Usan proyectos
temporales que se eliminan al terminar. Cubren procesos con códigos 0 y 1,
salidas separadas, registros diferentes, conservación de los originales,
invocación desde otro directorio, selección de casos, archivos requeridos
ausentes y errores al preparar o guardar el registro. El tiempo agotado y
el error al iniciar el proceso se simulan, sin esperar 30 segundos.

En la validación inicial, con la versión 1 del caso 02, se ejecutaron ambos
casos mediante `run_case.py` y se comprobaron sus
informes y las copias guardadas:

| Caso | Pruebas | Correctas | Fallos | Código de pruebas | Estado | Código del controlador |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | 4 | 3 | 1 | 1 | `finalizada` | 0 |
| 02 | 8 | 5 | 3 | 1 | `finalizada` | 0 |

No hubo errores de importación. Los dos contratos y los cuatro archivos de
`benchmark/` permanecieron idénticos a sus versiones anteriores a aquellas
ejecuciones. Los resultados de esa tabla son históricos, no de la versión 2.

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

## Orquestación acotada del caso 02

Desde la raíz del proyecto:

```sh
python3 orchestrate_case.py case_02 --max-attempts 2
```

Solo admite `case_02` y valores 1 o 2 para `--max-attempts`, con **2 por defecto**.
El número incluye el intento inicial: 2 permite un desarrollo y, como máximo,
una corrección. El proyecto se localiza junto al script, también si se lanza
desde otro directorio. La primera ejecución real registrada usó un presupuesto
de dos intentos y terminó aprobada tras el primero.

### Flujo y condiciones para continuar

1. Conserva el contrato de versión 2, las pruebas y la implementación original
   en un registro general. Mantiene sus bytes y hashes fijos durante todo el flujo.
2. Evalúa la implementación de partida en una copia. Un informe completo de
   aserciones fallidas permite encargar la reparación; un timeout o un problema
   técnico detiene el flujo antes de llamar al desarrollador.
3. Invoca al desarrollador una sola vez y recoge el candidato. Comprueba la
   integridad y el resultado técnico antes de evaluarlo en otra copia, con las
   pruebas de referencia y un proceso nuevo.
4. Si el candidato supera todas las pruebas y la evidencia es coherente,
   invoca al revisor en una sesión nueva de solo lectura. Este recibe los
   materiales de código y evaluación, sin la explicación final del desarrollador.
5. Una aprobación del controlador termina con éxito. Si quedan intentos y hay
   fallos de aserción completos o un dictamen válido de `solicitar_cambios`,
   comienza una corrección desde **los bytes exactos del candidato anterior**.
   Entrega el informe posterior que falló o el dictamen validado correspondiente.
6. Evalúa y, cuando procede, revisa la corrección de la misma manera. Si se
   agotan los intentos sin aprobación, termina con `intentos_agotados`.

Los hallazgos son observaciones que el desarrollador debe contrastar con el
contrato; no autorizan cambios de requisitos. El controlador no modifica
contratos, pruebas ni implementaciones del benchmark para lograr una aprobación.

Un código 1 no basta para corregir. `classify_test_report()` contrasta los
identificadores y el total con el AST de las pruebas conservadas. Exige filas
completas, cierre coherente y diagnósticos `AssertionError` para los fallos.
Las pruebas omitidas, informes truncados, `OK` sin pruebas, errores de importación
o de ejecución y salidas no explicadas no habilitan una corrección. Se adopta
un criterio conservador: incluso una excepción causada por el candidato detiene
el ciclo si no está acreditada como fallo de aserción. Los errores se conservan
en el registro para que una persona decida el siguiente paso.

Los fallos de infraestructura, timeouts, evidencia inválida, respuesta inválida
del revisor o alteraciones de integridad detienen el flujo aunque quede
presupuesto. No hay reintentos técnicos, concurrencia ni reanudación automática.

### Presupuesto, interfaces internas y continuidad

`run_orchestration()` recorre como máximo `max_attempts` intentos. En cada uno
hay una sola llamada a `run_repair()` y como máximo una a `run_review()`.
`next_stage()` decide si revisar, corregir, aprobar o detenerse; la comprobación
del presupuesto impide comenzar una corrección cuando se alcanza el límite.
El resumen contabiliza las invocaciones de ambos roles y verifica los límites:
**máximo cuatro `codex exec` con dos intentos**, o dos con uno. Las consultas
`--version` y `exec --help` son comprobaciones locales, no invocaciones al modelo.
Una sesión puede realizar varias acciones internas; ese número no es el
presupuesto del orquestador.

`run_repair()` y `run_review()` devuelven diccionarios con estado, código, datos
de proceso y `registro` (ruta absoluta, o `null` si no se pudo crear). Las CLI
existentes siguen imprimiendo sus resultados y conservan sus códigos. No se
busca la carpeta más reciente ni se analizan mensajes de terminal para enlazar
las etapas. La orquestación usa el modo estricto de reparación, que detiene las
etapas dependientes ante errores; la CLI independiente conserva su evaluación
del archivo residual para diagnóstico cuando el agente falla.

Los registros de reparación nuevos usan `version_registro: 2`, que identifica
el formato del registro y es distinto de la versión del contrato. Distinguen:

| Material | Significado |
| --- | --- |
| `referencia/solution.py` | Original defectuoso del benchmark, fijo en todos los intentos. |
| `partida.py` | Entrada exacta del desarrollador; original en el primero y candidato anterior en la corrección. |
| `candidato.py` | Salida del desarrollador, idéntica a la implementación evaluada después. |
| `partida.diff` | Diferencia del original a la implementación de partida. |
| `correccion.diff` | Diferencia de la partida al candidato resultante. |
| `candidato.diff` | Diferencia acumulada del original al candidato resultante. |
| `feedback.json` | Evidencia que motiva la corrección; `null` en el primer intento. |

`correction_context()` valida la reparación previa y, cuando corresponde, su
revisión antes de construir el feedback. `validate_repair()` verifica también
esta continuidad: partida, hashes, diffs, inventarios de los registros anteriores
y coincidencia del feedback con el informe o dictamen conservado. La evaluación
inicial del segundo intento corresponde a `partida.py`; su referencia original
sigue siendo la del benchmark. No se falsea esa referencia ni se elimina la
comparación con los originales actuales. Los registros históricos conservan su
formato y sus bytes; no se migran ni se retocan sus hashes. La validación histórica
continúa disponible, sujeta a las mismas restricciones de versión del contrato.

### Registro general, códigos y límites

```text
runs/<fecha_UTC>_case_02_orchestrate_<uuid>/
├── referencia/
│   ├── contrato.md
│   ├── solution.py
│   └── test_solution.py
└── resultado.json
```

Las reparaciones y revisiones mantienen sus registros separados bajo `runs/`.
El resumen general incluye sus rutas y resultados estructurados, el número de
intento, hashes de partida y referencias, inventarios de registros relacionados,
transiciones y motivos, invocaciones realizadas, tiempos e integridad. Se guarda
antes de comenzar y entre etapas. `en_curso` es un estado provisional con código
`null` y `aprobada: false`; no acredita éxito si el controlador se interrumpe.
Un fallo de escritura devuelve error y conserva los diagnósticos disponibles.

| Código | Estado | Significado |
| --- | --- | --- |
| 0 | `aprobada` | Pruebas superadas, revisión aprobada por el controlador, integridad conservada y registro guardado. |
| 1 | `intentos_agotados` | Fallos de aserción o cambios solicitados pendientes, sin más intentos disponibles. |
| 2 | Error de argumentos | Caso o presupuesto no admitido; no comienza el flujo. |
| 3 | `fallo_agente` / `fallo_revisor` | CLI ausente o incompatible, fallo del proceso, salida no cero o candidato ausente. |
| 4 | `tiempo_agotado` / `tiempo_agotado_revisor` | Timeout de pruebas, agente o comprobaciones previas. |
| 5 | `respuesta_invalida` | El revisor no entrega un dictamen válido. |
| 6 | `modificacion_no_permitida` | Integridad de originales, referencias, materiales o registros alterada. |
| 7 | `evidencia_invalida` | Contrato incorrecto, informe incompleto o evidencia/continuidad inconsistente. |
| 8 | `fallo_controlador` / `error_pruebas` | Fallo de preparación, escritura o proceso de evaluación no atribuible a aserciones. |

Se mantienen 180 segundos por agente, 30 por evaluación y 10 por consulta de
versión o ayuda. No hay un timeout global adicional. Se conservan argumentos
en lista, `shell=False`, prompt por stdin, autenticación existente, aprobaciones
`never`, búsqueda web y delegación desactivadas. El desarrollador usa
`workspace-write` limitado a su copia temporal y el revisor `read-only`; no se
añaden permisos sobre el repositorio ni se omite el sandbox. Las limitaciones
de aislamiento descritas al final siguen vigentes.

La suite automatizada de este hito usa exclusivamente Codex simulado. Se prueban
las transiciones, los límites de uno y dos intentos, el feedback y la partida exactos,
la conservación de las CLI y las detenciones técnicas, incluidos fallos al
guardar registros de procesos después de invocar un agente. Las 57 pruebas
previas se conservan y se añaden 21 de orquestación. Se ejecutó:

```sh
python3 -B -m unittest discover -s tests -v
```

Resultado observado: **78 pruebas correctas en 22,166 segundos, código 0**.
`git diff --check` también terminó sin errores. Esta validación es anterior a
la ejecución real descrita a continuación y no se repitió para el cierre
documental. El contrato y las 16 pruebas del caso no cambian.

### Primera ejecución real coordinada

El 14/10/2026, de **16:03:32 a 16:04:29 (Europe/Madrid)**, el orquestador
completó desarrollo, evaluación independiente y revisión en **57,361 s**.
El registro general es
`runs/20261014T140332296667Z_case_02_orchestrate_599245bb19684d73aabd766745c56579/resultado.json`.
Relaciona la reparación
`20261014T140332299453Z_case_02_repair_b677ef2959f54e07800d505d08e14229`
y la revisión
`20261014T140403668438Z_case_02_review_0fc8d2b0921e480181729f2e92845d76`.

| Evidencia contrastada | Resultado |
| --- | --- |
| Presupuesto y consumo | 1 de 2 intentos; 2 de 4 invocaciones: un desarrollador y un revisor en sesiones distintas. |
| Pruebas del caso v2 | Iniciales: 16, con 9 correctas y 7 fallidas, código 1. Posteriores: 16 correctas, código 0. |
| Reparación | `supera_las_pruebas_disponibles`, `aceptada: true`; agente y controlador con código 0. |
| Revisión | Modelo: `aprobar`, `hallazgos: []`. Controlador: `aprobada`, código 0; revisor con código 0. |
| Orquestación | `aprobada`, `aprobada: true`, código 0; transiciones `revisar` → `aprobar`. |
| Integridad registrada | 4/4 comprobaciones positivas en el registro general, 9/9 en reparación y 6/6 en revisión; sin errores del controlador. |

La partida coincide con el original defectuoso. El candidato añade la condición
`respuesta is None or respuesta == "" or respuesta.isspace()` después de las
prioridades de timeout y fallo, y devuelve `"respuesta_vacia"` en esos casos.
Sus bytes coinciden con el candidato de la reparación manual v2 anterior;
esta es una ejecución distinta, con sus propias evaluaciones y registros.
Se contrastaron hashes, inventarios, diffs, copias evaluadas y materiales de
revisión. Los eventos del revisor registran seis consultas y lecturas, todas
con código 0, sin ejecución del candidato ni edición.

El [informe de resultados](evals/resultados-2026-10-14.md) conserva el diff,
los tiempos y el contraste de evidencia. Estas **dos invocaciones reales nuevas**
se añaden a las cinco históricas; no son las 78 pruebas automatizadas ni la
reevaluación local anterior. No hubo segundo intento ni feedback de corrección
en esta ejecución. Esa transición solo se ha validado con simulaciones; una
aprobación en este caso sencillo no demuestra fiabilidad general.

## Un intento de reparación con Codex CLI

Se necesita Python 3, Codex CLI instalado y su autenticación ya configurada.
Todo el código Python usa la biblioteca estándar. El controlador no lee ni copia
credenciales, no inicia sesión y conserva la configuración y reglas de seguridad
existentes. La versión comprobada en este equipo es **codex-cli 0.162.1**.

```sh
codex --version
codex exec --help
python3 repair_case.py case_02
```

Solo se admite `case_02` en este hito. El script encuentra el proyecto por su
propia ubicación, también cuando se invoca desde otro directorio.
`run_case.py` conserva su comportamiento y sus códigos de salida originales.

El flujo es el siguiente:

1. Crea un registro único en `runs/`, conserva los bytes del contrato, la
   implementación inicial y las pruebas de referencia, y registra hashes SHA-256.
2. Ejecuta las pruebas iniciales en una copia, en un proceso nuevo con un límite
   de 30 segundos. Conserva stdout, stderr, estado, tiempos y código de salida.
3. Prepara un workspace temporal fuera del repositorio con solo `solution.py`
   y `test_solution.py`. El prompt contiene el contrato y el informe inicial;
   no contiene el README ni una solución preparada por el controlador.
4. Pide corregir únicamente `solution.py`, permite leer y ejecutar las pruebas
   y prohíbe modificarlas, instalar dependencias, usar Git, acceder a la web,
   leer fuera del workspace o delegar en otros agentes.
5. Comprueba y registra `codex --version` y `codex exec --help`. Si la CLI está
   disponible y anuncia las opciones necesarias, ejecuta **una sola vez**
   `codex exec`. Las comprobaciones de versión y ayuda no llaman al modelo.
6. Conserva el archivo resultante como `candidato.py` y su diff frente al
   original, aunque Codex falle o se agote el tiempo. Comprueba que las pruebas
   entregadas al agente siguen siendo archivos regulares con los mismos bytes;
   borrarlas o reemplazarlas por un enlace también impide aceptar la reparación.
7. Evalúa el candidato en otra copia, con las pruebas de referencia conservadas
   en memoria por el controlador. No copia otros archivos creados por el agente
   ni usa como evidencia las pruebas que este afirme haber ejecutado. El nuevo
   proceso de evaluación tiene su propio límite de 30 segundos.
8. Comprueba la integridad de `benchmark/`, `tasks/`, las referencias y los
   archivos usados en ambas evaluaciones. Guarda el resumen y elimina el
   directorio temporal del agente.

La invocación utiliza `subprocess.Popen`, argumentos en una lista,
`shell=False` y el prompt exacto en UTF-8 por stdin (`-`). Usa `--sandbox
workspace-write`, `approval_policy="never"`, `web_search="disabled"`,
`features.multi_agent=false`, `--json`, `--output-last-message`, `--ephemeral`
y `--skip-git-repo-check`. El cwd y `--cd` señalan el workspace temporal.
Se vacían las raíces adicionales de escritura y se excluyen `/tmp` y `$TMPDIR`
como raíces generales; el workspace temporal sigue siendo escribible.
La red de los comandos del agente queda desactivada. No se usan opciones para
omitir el sandbox, ignorar reglas o añadir escritura sobre el repositorio.
Estos ajustes se contrastaron con la ayuda instalada y la
[referencia oficial de configuración de Codex](https://learn.chatgpt.com/docs/config-file/config-reference).

El límite de Codex es **180 segundos**. En POSIX, un tiempo agotado termina el
grupo de procesos con SIGKILL y conserva las salidas parciales; el código del
proceso puede ser negativo por la señal. No hay reanudaciones ni reintentos en
el controlador. Una sesión de Codex puede realizar varias acciones internas.
Si Codex falla, se evalúa igualmente el archivo que haya quedado para conservar
el diagnóstico. Si falta el candidato, no se lanza la evaluación posterior.

### Registro de reparación

```text
runs/<fecha_UTC>_case_02_repair_<uuid>/
├── referencia/
│   ├── contrato.md
│   ├── solution.py
│   └── test_solution.py
├── inicial/
│   ├── workspace/             # Copia para las pruebas iniciales
│   ├── stdout.txt
│   ├── stderr.txt
│   └── resultado.json
├── agente/
│   ├── entrada.txt            # Bytes exactos enviados por stdin
│   ├── codex_version.txt
│   ├── version/               # stdout, stderr y resultado.json de --version
│   ├── ayuda/                 # stdout, stderr y resultado.json de exec --help
│   ├── eventos.jsonl
│   ├── errores.txt
│   ├── respuesta_final.txt
│   ├── test_solution_despues.py
│   └── resultado.json
├── candidato.py
├── candidato.diff
├── partida.py                # Entrada exacta del desarrollador
├── partida.diff              # Original → partida
├── correccion.diff           # Partida → candidato
├── feedback.json             # Motivo de corrección o null
├── posterior/
│   ├── workspace/             # Solo candidato y pruebas de referencia
│   ├── stdout.txt
│   ├── stderr.txt
│   └── resultado.json
└── resultado.json
```

El resumen guarda estados independientes de agente y pruebas, comandos, códigos,
tiempos UTC, duraciones monotónicas, número de invocaciones, hashes,
comprobaciones de integridad, aceptación y errores del controlador. Los JSON
de cada proceso conservan su propio código. Los canales se escriben por separado
directamente a disco. `respuesta_final_disponible` distingue una respuesta
recogida de un archivo vacío creado para el registro.

Si un paso no puede ejecutarse, se registra como tal: por ejemplo, Codex ausente
impide crear el registro de ayuda, y un candidato eliminado impide crear la
evaluación posterior. Si falla la escritura del registro, los diagnósticos ya
guardados se conservan y el controlador devuelve error; puede quedar un registro
incompleto. `runs/` sigue excluido de Git.

### Códigos de salida de repair_case.py

| Código | Estado | Significado |
| --- | --- | --- |
| 0 | `supera_las_pruebas_disponibles` | Flujo completado, Codex terminó con 0, integridad conservada y pruebas de referencia superadas. No afirma corrección general. |
| 1 | `no_supera_pruebas` | La evaluación posterior falló o agotó sus 30 segundos. |
| 2 | Error de argumentos | Uso inválido, rechazado por `argparse` antes de iniciar el flujo. |
| 3 | `fallo_agente` | CLI ausente o incompatible, fallo de arranque, salida no cero de Codex o candidato ausente. |
| 4 | `tiempo_agotado_agente` | Codex alcanzó sus 180 segundos. |
| 5 | `modificacion_no_permitida` | Falló alguna comprobación de integridad, aunque las pruebas posteriores pasen. |
| 6 | `fallo_controlador` | Error de preparación, ejecución de las pruebas o conservación del registro. |

Cuando coinciden fallos, se priorizan: controlador, integridad, agente y pruebas.
El JSON conserva las causas de cada etapa. Un timeout de las comprobaciones de
versión o ayuda se registra en su propio proceso e impide lanzar el agente
(código 3). **Que Codex termine con código cero no demuestra una reparación.**

### Validación y resultados reales de este hito

El 14 de octubre de 2026 se ejecutó:

```sh
python3 -B -m unittest discover -s tests -v
```

Resultado de esa validación previa: **30 pruebas correctas**, código 0:
14 de `run_case.py` y 16 de
`repair_case.py`. Las nuevas pruebas usan un ejecutable local que simula Codex;
no llaman al modelo. Ejecutan realmente los procesos de evaluación y cubren
candidato válido y fallido, CLI ausente o incompatible, salida no cero, timeout,
pruebas modificadas, borradas o enlazadas, candidato ausente, conservación de
originales y diagnósticos, registros únicos, fallo de escritura e invocación
desde otro directorio. También comprueban que alterar las pruebas desde el
candidato durante la evaluación impide aceptar el resultado.

Se conservan **dos intentos reales independientes bajo versión 1** del caso 02,
con una invocación de `codex exec` en cada uno y Codex CLI 0.162.1 en ambos. El segundo
fue lanzado manualmente desde la terminal, según lo indicado por el usuario;
no fue un reintento automático del controlador. Los registros no identifican
el contexto del proceso que lanzó cada ejecución.

| Intento y comienzo (Europe/Madrid) | Antes: correctas/fallidas; código | Después: correctas/fallidas; código | Código de Codex | Estado y código del controlador |
| --- | --- | --- | --- | --- |
| 1 — 14/10/2026 11:46:43 | 5/3; 1 | 5/3; 1 | 1 | `fallo_agente`; 3 |
| 2 — 14/10/2026 11:59:01 | 5/3; 1 | 8/0; 0 | 0 | `supera_las_pruebas_disponibles`; 0 |

Cada evaluación de la tabla ejecutó **las mismas ocho pruebas del caso 02 de versión 1**.
Son distintas de las 30 pruebas automatizadas del controlador, que no llaman
al modelo. Las comprobaciones `codex --version` y `codex exec --help` tampoco
son llamadas al modelo.

En el primer intento, Codex terminó en aproximadamente **0,47 segundos** con
este error de inicialización:

```text
Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
```

El stderr también conserva avisos de escritura en una base de datos de solo
lectura. No hubo eventos JSONL ni respuesta final, y el candidato quedó idéntico
al original: **diff vacío, 0 bytes; `aceptada: false`**. La causa concreta sigue
sin confirmarse: atribuirla a restricciones del entorno de lanzamiento es una
hipótesis; el éxito posterior no demuestra qué permiso o ruta provocó el fallo.

En el segundo intento, Codex terminó con código 0 en **28,57 segundos**, produjo
eventos y respuesta final, y añadió esta condición después de descartar tiempo
agotado y fallo de ejecución:

```python
if respuesta is None or not respuesta.strip():
    return "respuesta_vacia"
```

La comprobación de `None` evita llamar a `strip()` sobre ese valor. Para una
cadena vacía o formada solo por espacios en blanco, incluidos saltos de línea,
`strip()` devuelve una cadena vacía. Se mantienen las prioridades anteriores.
La evaluación independiente del controlador terminó con **8/8 pruebas de versión 1
correctas**, código 0 y **`aceptada: true`**; no se basa únicamente en la
afirmación del agente.

En ambos intentos, las siete comprobaciones de integridad fueron positivas y
no hubo errores del controlador. En aquella validación se contrastaron los
hashes y los archivos de versión 1. Sus referencias guardadas permanecen
intactas; el contrato y las pruebas actuales han evolucionado a versión 2.
La reparación se conserva como candidato, sin aplicar
el cambio al caso defectuoso original.

El [informe del 14 de octubre](evals/resultados-2026-10-14.md) incluye los
identificadores de ambos registros, el diff exacto y la evidencia suficiente
para entender los resultados sin acceder a `runs/`, que sigue excluido de Git.
Esos registros no acreditan una evaluación de versión 2. La comprobación local
posterior se documenta por separado y no modifica sus hashes ni resultados.

## Aclaración del contrato: versión 2

La versión 1 decía «espacios y saltos de línea» sin definir si incluía todos
los caracteres de espacio en blanco. El revisor interpretó esa expresión de
forma restringida y señaló que el candidato también vaciaba `"\t"` mediante
`strip()`. El usuario decidió que ese comportamiento debía admitirse y aclaró
el [contrato como versión 2](tasks/002-classify-run.md).

Con código cero, `None`, la cadena vacía y las cadenas no vacías para las que
`str.isspace()` devuelve `True` producen `"respuesta_vacia"`. Cualquier cadena
con un carácter que no sea espacio en blanco produce `"completada"`. Se mantienen
los tipos admitidos, la pureza y las prioridades de timeout y fallo de ejecución.
Las ocho pruebas anteriores se conservan y se añaden ocho para tabuladores,
retorno de carro, combinaciones de espacios en blanco, U+00A0, texto rodeado de
espacios en blanco y las prioridades con estas entradas.

El 14 de octubre de 2026 se ejecutaron **57 pruebas del controlador, todas
correctas**, sin modelo. Después se copió el candidato de la reparación
satisfactoria de versión 1 y las pruebas de versión 2 a una carpeta temporal
fuera del repositorio. Un nuevo proceso Python, limitado a 30 segundos, terminó
con **16/16 pruebas correctas y código 0**. La copia temporal se eliminó;
los materiales y salidas se conservaron en:

```text
runs/20261014T104559983435Z_case_02_reevaluacion_local_v2_318ba7c432cd4c3f807be871ca4ef3c4/
```

Es una **reevaluación local**, con cero llamadas al modelo. No forma parte de
la reparación antigua ni del dictamen del revisor. La implementación defectuosa
de `benchmark/case_02/solution.py` sigue intacta. Las nuevas etapas con agentes
se realizaron después y se documentan a continuación. Ningún registro histórico
se modifica para hacerlo aceptable con las nuevas referencias.

## Reparación y revisión reales bajo versión 2

El usuario lanzó manualmente estas dos etapas, seleccionando para la revisión
el registro aceptado de la reparación. En aquella ejecución no hubo
encadenamiento automático ni un ciclo de corrección entre agentes:

```sh
python3 repair_case.py case_02
python3 review_case.py --run runs/20261014T105547244465Z_case_02_repair_1bd0e59ca7654489ba7f455fa6e03929
```

Registros conservados bajo `runs/`:

```text
20261014T105547244465Z_case_02_repair_1bd0e59ca7654489ba7f455fa6e03929/
20261014T105754354270Z_case_02_review_2b4d717cb28e4b91adcf5b4ae462651e/
```

| Etapa, 14/10/2026 (Europe/Madrid) | Evidencia observada | Códigos |
| --- | --- | --- |
| Reparación, 12:55:47 | Antes: 16 pruebas, 9 correctas y 7 fallidas. Después: 16 correctas, sin fallos. | Pruebas: 1 → 0; Codex: 0; controlador: 0. |
| Revisión, 12:57:54 | Modelo: `aprobar`, `hallazgos: []`. Controlador: `aprobada`, `aprobada: true`. | Codex: 0; controlador: 0. |

El nuevo candidato parte otra vez de la implementación defectuosa conservada,
no del candidato histórico con `strip()`. Este es su diff completo:

```diff
--- inicial/solution.py
+++ candidato/solution.py
@@ -3,4 +3,6 @@
         return "tiempo_agotado"
     if codigo_salida is None or codigo_salida != 0:
         return "fallo_ejecucion"
+    if respuesta is None or respuesta == "" or respuesta.isspace():
+        return "respuesta_vacia"
     return "completada"
```

El cortocircuito evita invocar el método sobre `None`; la cadena vacía se
contempla por separado porque `"".isspace()` devuelve `False`. Las prioridades
de timeout y fallo permanecen antes de esta condición. El candidato **supera
las pruebas disponibles**, según la evaluación posterior del controlador en
otro proceso, no solo según la respuesta del desarrollador.

Ambos agentes usaron Codex CLI 0.162.1, una invocación por etapa y límite de
180 segundos: 27,229 s para desarrollar y 25,408 s para revisar. La reparación
registra `aceptada: true`, siete comprobaciones de integridad positivas y
ningún error del controlador. La revisión acredita evidencia previa válida,
seis comprobaciones positivas, respuesta JSON válida y ningún error. Los hashes
del candidato, la copia evaluada y los materiales revisados coinciden; también
se contrastaron las referencias y el inventario completo del registro de origen.

Los eventos del revisor contienen **seis comandos terminados con código 0**:
`pwd`, una enumeración con `rg --files`, dos lecturas con `cat` y dos con `nl`.
Leyó contrato, original, candidato, diff, pruebas, informe posterior y esquema.
No hay acciones registradas de ejecución o importación del candidato o las
pruebas, ni de edición. Esta conclusión procede de los eventos y las copias,
no de aceptar sin contraste su afirmación de haber hecho una revisión estática.

Estas son **dos nuevas invocaciones reales de `codex exec`**, diferentes de las
57 pruebas automatizadas del controlador y de la reevaluación local anterior.
El cierre documental no volvió a ejecutar pruebas ni llamó al modelo. El
[informe de resultados](evals/resultados-2026-10-14.md) conserva los detalles,
hashes, acciones y diferencias entre esas evidencias. Las dos etapas manuales
cerraron el hito anterior. La primera ejecución real del nuevo orquestador se
documenta por separado más arriba: aprobó en un intento, sin llegar a corregir.

## Revisar una reparación existente

Después de obtener una reparación aceptada bajo versión 2, se puede revisar
su registro nuevo. Sustituye `REGISTRO_DE_REPARACION_V2` por su nombre:

```sh
python3 review_case.py --run runs/REGISTRO_DE_REPARACION_V2
```

`--run` acepta una ruta absoluta o relativa al directorio desde el que se lanza
el comando. El proyecto y `prompts/reviewer.md` se localizan junto al script.
Se reutiliza la autenticación existente sin leer ni copiar credenciales.
No se vuelve a invocar al desarrollador ni se ejecutan las pruebas del caso.
`run_case.py` y `repair_case.py` conservan su comportamiento.

### Evidencia previa y materiales

`validate_repair()` comprueba que el registro corresponde a `case_02`, está
aceptado con código 0 y acredita todas las comprobaciones de integridad de la
reparación. Contrasta los resúmenes generales y de cada proceso, los comandos
de evaluación, las copias, los hashes de referencias y candidato, y el diff.
El candidato debe coincidir byte a byte con la implementación evaluada después.
El informe posterior debe acreditar todas las pruebas de referencia conservadas
en ese registro, y su proceso debe haber terminado con código 0.
`reference_test_ids()` obtiene sus nombres completos mediante AST sin importar
ni ejecutar el archivo; `validate_test_report()` contrasta esos nombres con las
filas del informe, su número total y un cierre correcto. Se rechazan pruebas
omitidas, duplicadas, desconocidas, de otra clase, fallidas o informes incompletos,
aunque contengan `OK`. No se fija el número a ocho ni a dieciséis.
La lectura estática admite métodos explícitos de clases `unittest.TestCase`;
no admite descubrimiento dinámico mediante `load_tests` ni bases de pruebas
desconocidas.

También se exige que los originales actuales de `benchmark/` y `tasks/`
coincidan con los hashes registrados: este hito no admite cambiar las referencias
entre reparación y revisión. Se rechazan archivos requeridos ausentes,
enlaces, referencias alteradas o evidencia contradictoria. Una entrada rechazada
termina con código 7, informa del motivo y no crea un registro de revisión ni
invoca Codex, ni siquiera para consultar la versión.
Por ello, los registros históricos de versión 1 ya no son entradas válidas con
las referencias actuales de versión 2. Esta comprobación de integridad se
conserva; no se retocan hashes antiguos para eludirla.

Tras la validación, el controlador crea un registro nuevo e inventaría los
archivos del intento original. Conserva copias de ocho materiales: contrato,
implementación original, candidato, diff, pruebas de referencia y resultado,
stdout y stderr de la evaluación posterior. Añade un esquema JSON para la
respuesta. Copia esos materiales a un workspace temporal fuera del repositorio;
la explicación final del desarrollador, sus eventos y su prompt no forman parte
de los materiales enviados al revisor.

Las [instrucciones del revisor](prompts/reviewer.md) exigen una revisión estática
del contrato, las prioridades de clasificación, la pureza, los efectos
secundarios y las entradas admitidas no cubiertas por las pruebas. Prohíben
ejecutar o importar el candidato, la implementación inicial o las pruebas,
modificar archivos, instalar dependencias, usar Git, navegar o delegar. Los
hallazgos deben demostrar incumplimientos concretos, sin inventar problemas ni
exigir comportamientos fuera del contrato. Una prueba ausente no constituye
por sí sola un defecto.

### Invocación y dictamen

`invoke_reviewer()` comprueba y registra `codex --version` y `codex exec --help`
antes de invocar el agente. Las opciones se contrastaron con **Codex CLI
0.162.1** instalado. Ejecuta una sola sesión nueva mediante `codex exec`, sin
`resume` ni `fork`, con `--sandbox read-only`, aprobaciones `never`, búsqueda
web desactivada, delegación desactivada y un límite de **180 segundos**.
Usa `--ephemeral`, `--skip-git-repo-check`, eventos `--json`, respuesta final
separada y `--output-schema`. No añade permisos de escritura ni omite el sandbox
o las reglas existentes.

Se reutiliza `run_process()` de `repair_case.py`: argumentos en lista,
`shell=False`, entrada exacta en UTF-8 por stdin, canales separados y terminación
del grupo de procesos al agotar el tiempo en POSIX. Las consultas previas tienen
un límite propio de 10 segundos. Una sesión puede realizar varias lecturas;
el controlador no reintenta el dictamen.

La respuesta debe ser un objeto JSON sin Markdown con `decision`, `resumen` y
`hallazgos`. `decision` admite `aprobar` o `solicitar_cambios`; `resumen` debe
ser un texto no vacío. Cada hallazgo requiere:

| Campo | Validación |
| --- | --- |
| `archivo` | Exactamente `candidato.py`. |
| `linea` | Entero positivo que identifica una línea existente, numerada desde 1. |
| `explicacion` | Texto no vacío que identifica el incumplimiento. |
| `ejemplo` | Texto no vacío con entradas admitidas, resultado esperado y comportamiento deducido del código. |

`validate_verdict()` valida la estructura en Python, rechaza campos adicionales,
claves duplicadas, valores JSON no estándar y tipos incorrectos. Una solicitud
de cambios requiere al menos un hallazgo; una aprobación exige una lista vacía.
El controlador valida la estructura y la coherencia del dictamen, no demuestra
automáticamente la verdad de sus explicaciones o ejemplos.

Después se comparan los hashes del workspace, los materiales conservados y el
registro completo de reparación, además de los originales y las instrucciones.
`decide()` separa el **dictamen del modelo** de la **decisión del controlador**.
Aunque el modelo diga `aprobar`, un timeout, salida no cero, fallo de registro
o modificación de materiales impide aprobar. Una respuesta estructuralmente
válida puede conservarse para diagnóstico aunque el proceso haya fallado.

### Registro y códigos de salida de review_case.py

```text
runs/<fecha_UTC>_case_02_review_<uuid>/
├── origen.json               # Ruta de reparación, inventario y hashes
├── materiales/
│   ├── contrato.md
│   ├── original.py
│   ├── candidato.py
│   ├── candidato.diff
│   ├── test_solution.py
│   ├── posterior.json
│   ├── posterior.stdout.txt
│   ├── posterior.stderr.txt
│   └── respuesta.schema.json
├── revisor/
│   ├── entrada.txt           # Bytes exactos de prompts/reviewer.md enviados por stdin
│   ├── codex_version.txt
│   ├── version/              # stdout, stderr y resultado de --version
│   ├── ayuda/                # stdout, stderr y resultado de exec --help
│   ├── eventos.jsonl
│   ├── stderr.txt
│   ├── respuesta_original.txt
│   └── resultado.json        # Proceso, comando, códigos y tiempos
├── dictamen_validado.json    # Solo si la respuesta cumple la estructura
└── resultado.json            # Dictamen, decisión, integridad y errores separados
```

El registro de reparación no se modifica. Los registros nuevos también quedan
excluidos de Git bajo `runs/`. El workspace temporal se elimina al terminar.
Los resúmenes incluyen tiempos UTC y duraciones monotónicas. Si falta la respuesta
o la CLI, se conserva el diagnóstico disponible; si falla una escritura, el
registro puede quedar incompleto y no se devuelve éxito.

| Código | Decisión del controlador | Significado |
| --- | --- | --- |
| 0 | `aprobada` | Evidencia válida, proceso correcto, dictamen `aprobar`, integridad conservada y registro guardado. |
| 1 | `cambios_solicitados` | Dictamen válido con al menos un hallazgo, sin fallos técnicos o de integridad. |
| 2 | Error de argumentos | Falta `--run` o el uso de la interfaz es inválido. |
| 3 | `fallo_revisor` | CLI ausente o incompatible, fallo de arranque o salida no cero. |
| 4 | `tiempo_agotado_revisor` | Timeout de la invocación o de una comprobación previa de la CLI. |
| 5 | `respuesta_invalida` | El proceso terminó con 0 pero la respuesta falta o no cumple el formato y la coherencia exigidos. |
| 6 | `modificacion_no_permitida` | Falló una comprobación de integridad. |
| 7 | `evidencia_invalida` | La reparación de entrada no acredita los requisitos; no se invoca al revisor. |
| 8 | `fallo_controlador` | Fallo al preparar la revisión o conservar su registro. |

Durante la revisión se priorizan los fallos del controlador, de integridad,
del proceso y de respuesta sobre el dictamen del modelo. Ningún fallo técnico
se transforma en una aprobación. Aprobar sigue sin demostrar corrección general.

### Validación de este hito

La suite del controlador se ejecutó el 14 de octubre de 2026 con:

```sh
python3 -B -m unittest discover -s tests -v
```

La validación inicial del revisor tuvo 51 pruebas correctas. Tras adaptar la
comprobación del informe a las referencias de cada registro, aquella suite
terminó con **57 pruebas correctas**, código 0: 14 del controlador inicial,
16 de reparación y 27 de revisión. Son pruebas del controlador, distintas de
las 16 pruebas del caso 02 de versión 2.

Las pruebas nuevas usan registros construidos como fixtures y un ejecutable
local que simula Codex; no necesitan los registros ignorados de `runs/` ni
llaman al modelo. Cubren aprobación, cambios solicitados, respuestas inválidas,
timeouts, errores de proceso y escritura, evidencia incompleta, candidatos
alterados, copias evaluadas distintas, informes incoherentes y alteraciones de
materiales. Comprueban la conservación del registro original y la ausencia de
ejecución del candidato por el controlador.

La revisión real de versión 1 está conservada en
`runs/20261014T103340644225Z_case_02_review_997b002f363c46cb94c2ce362f0db416`.
Codex terminó con código 0 tras 51,83 segundos; su dictamen fue
**`solicitar_cambios`**, con un hallazgo en la línea 6 del candidato sobre el
tabulador. El controlador registró **`cambios_solicitados`, código 1,
`aprobada: false`**, con seis comprobaciones de integridad positivas y sin
errores técnicos. El ejemplo asumía que `"\t"` debía producir `"completada"`
según la redacción de versión 1; motivó la decisión funcional explícita de
versión 2. El dictamen histórico no se reclasifica como aprobación.

Antes de la orquestación constaban **cinco invocaciones reales de `codex exec`**:
dos de reparación y una de revisión bajo versión 1, más una reparación y una revisión bajo
versión 2. La primera falló al inicializarse; este recuento no equivale al número
de solicitudes internas al modelo. La reevaluación local no añadió ninguna
invocación. La ejecución coordinada añade una reparación y una revisión:
**siete invocaciones reales en total**. La suite creció de 57 a 78 pruebas en el
hito de orquestación; su validación previa no se repitió para este cierre documental.
El [informe de resultados](evals/resultados-2026-10-14.md) separa esas evidencias
y conserva sus resultados originales, incluido el rechazo de versión 1.

Los hashes y las comprobaciones de coherencia no autentican un registro que se
haya falsificado de forma consistente. El sandbox de solo lectura limita las
escrituras, pero no demuestra que el modelo haya seguido todas las instrucciones
ni impide por sí solo ejecutar un intérprete; no ejecutar el candidato es una
restricción explícita del encargo. Las limitaciones de lectura e integridad
final descritas a continuación también se aplican a este flujo.

## Alcance de los ejercicios

Estos ejercicios controlados ofrecen fallos reales y reproducibles para
comprobar el flujo de reparación: corregir cada defecto y mantener los
comportamientos que ya pasan las pruebas. El segundo intento produjo la primera
reparación que supera las pruebas disponibles. **Un caso sencillo, reparaciones
satisfactorias y una aprobación bajo versión 2 no demuestran fiabilidad general**
ni permiten estimar una tasa de éxito. El fallo del primer intento también
forma parte del resultado; su causa concreta no se ha aislado.

La copia de trabajo conserva los originales durante este flujo, pero **no
constituye un aislamiento de seguridad**. El proceso mantiene los permisos del
usuario y podría acceder a archivos fuera del workspace; `cwd` solo establece
el directorio de trabajo. **Una carpeta temporal no garantiza aislamiento de
lecturas**: el sandbox de Codex puede permitir leer fuera del workspace. No
entregar el README y pedir que no se lea fuera limita el encargo, pero no
constituye una barrera de lectura.

**Las pruebas ejecutadas por el controlador no heredan automáticamente el
sandbox de Codex.** Son procesos Python con los permisos disponibles para el
controlador. Un candidato malicioso podría acceder a otros archivos o ejecutar
acciones; las copias, los hashes y los límites de tiempo no sustituyen un
aislamiento del sistema operativo. Este hito está pensado para estos ejercicios
locales controlados, no para ejecutar código arbitrario no confiable.
Las comprobaciones de integridad comparan el estado final, no detectan cambios
transitorios revertidos. En sistemas no POSIX se termina el proceso directo al
agotar el tiempo; no se garantiza la terminación de todos sus descendientes.
Superar las pruebas disponibles no prueba corrección general ni cumplimiento
de todos los comportamientos posibles del contrato.

El orden de las condiciones del caso 02 preserva la prioridad del resultado:
el tiempo agotado prevalece sobre cualquier código o texto, y un fallo de
ejecución prevalece sobre una respuesta vacía. Solo tras descartar ambos se
evalúa si hubo texto para distinguir `"respuesta_vacia"` de `"completada"`.

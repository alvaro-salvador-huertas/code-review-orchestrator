# Funcionamiento e interfaces

Guía de la implementación actual. Los resultados de cada hito están en el
[historial](historial.md); los informes originales no se han reescrito al
separar estos detalles del [README](../README.md).

## Interfaces

Todos los comandos siguientes se lanzan desde la raíz del proyecto. Los
controladores localizan el proyecto junto al script; `--run` recibe una ruta
absoluta o relativa al directorio desde el que se lanza la CLI. Los registros
de las etapas se enlazan por sus rutas explícitas, nunca buscando el más reciente.

| Interfaz | Operación | Agentes reales |
| --- | --- | --- |
| `python3 -B run_case.py case_01` | Evalúa el original en una copia y conserva su registro. | Ninguno |
| `python3 -B repair_case.py case_01` | Un desarrollo y una evaluación independiente del candidato. | Como máximo un desarrollador |
| `python3 -B review_case.py --run "$REGISTRO_REPARACION"` | Valida y revisa una reparación aceptada. | Como máximo un revisor |
| `python3 -B orchestrate_case.py case_01 --max-attempts 2` | Coordina desarrollo, evaluación y revisión con presupuesto. | Hasta cuatro invocaciones |
| `python3 -B inspect_run.py --run "$REGISTRO_ORQUESTACION"` | Consulta el registro general existente. | Ninguno |
| `python3 -B inspect_run.py --run "$REGISTRO_ORQUESTACION" --format json` | Exporta la consulta con el esquema JSON v1. | Ninguno |

`run_case.py`, `repair_case.py` y `orchestrate_case.py` aceptan `case_01` y
`case_02`. La revisión identifica el caso a partir de la evidencia del registro,
sin otro argumento que pueda cambiarlo. El inspector está pensado para registros
generales de orquestación, no para los de `run_case.py` o una reparación aislada.

Para usar reparación y revisión por separado, primero ejecuta una reparación:

```bash
python3 -B repair_case.py case_02
```

Solo si terminó aceptada, copia la ruta de su línea `Registro:` y revisa esa
reparación con una nueva invocación real:

```bash
read -r -p 'Ruta del registro de reparación aceptada: ' REGISTRO_REPARACION
python3 -B review_case.py --run "$REGISTRO_REPARACION"
```

Estas operaciones crean registros propios; no reanudan el experimento multicaso
documentado. Una aprobación no modifica automáticamente el benchmark.

## Casos y referencias

[`case_config.py`](../case_config.py) resuelve contrato, implementación,
pruebas y prompt. Los defectos intencionados y las pruebas se conservan.

| Caso | Contrato y versión | Requisitos que revisa el agente |
| --- | --- | --- |
| `case_01` | [Suma por asignatura](../tasks/001-sum-by-subject.md), sin versión declarada | Acumulación de todas las sesiones, comparación exacta de nombres, entrada vacía, conservación de la lista y sus diccionarios, ausencia de entrada/salida. |
| `case_02` | [Clasificación de ejecución](../tasks/002-classify-run.md), versión 2 | Prioridad de timeout, después fallo de ejecución, después respuesta vacía según `str.isspace()`; tipos admitidos y pureza. |

En el caso 02, `completada` significa ejecución técnicamente terminada con
texto; no certifica la corrección de ese texto. La función del benchmark es
pura: no ejecuta procesos ni se usa para clasificar al propio controlador.

`version_contrato` es `null` para el caso 01 y `2` para el caso 02.
`version_registro: 2` identifica el formato de reparación, no el contrato.

## Flujo y presupuesto

1. El orquestador conserva contrato, pruebas y original, y fija sus hashes.
2. Evalúa la partida en una copia. Solo un informe completo de pruebas
   superadas o fallos de aserción permite continuar. Un fallo técnico detiene
   el flujo antes de invocar al desarrollador.
3. El desarrollador recibe el contrato y el informe inicial. Puede modificar
   únicamente la copia de `solution.py`; no recibe el README ni una solución
   preparada. Se conservan el candidato y su diff.
4. El controlador comprueba el proceso y la integridad, y evalúa el candidato
   en otro proceso con las pruebas de referencia. No toma como evidencia de
   aceptación las pruebas que el agente afirme haber ejecutado.
5. Si el candidato supera las pruebas y la evidencia es coherente, el revisor
   recibe contrato, original, candidato, diff, pruebas e informe posterior.
   No recibe la explicación final, el prompt o los eventos del desarrollador.
6. El controlador aprueba, corrige o se detiene. Solo aserciones acreditadas o
   un dictamen válido de cambios permiten una corrección, si queda un intento.

`--max-attempts` admite 1 o 2 y vale 2 por defecto. Incluye el intento inicial.
Cada intento contiene una llamada a `run_repair()` y, cuando procede, una a
`run_review()`: como máximo dos invocaciones con un intento o cuatro con dos.
`codex --version` y `codex exec --help` son consultas locales, no invocaciones
al modelo. Las acciones internas de una sesión tampoco incrementan ese presupuesto.

Los límites son **180 s por agente, 30 s por evaluación y 10 s por consulta
previa**, sin timeout global. Los procesos usan argumentos en lista y
`shell=False`. En POSIX, un timeout termina el grupo de procesos; fuera de
POSIX se termina el proceso directo, sin garantizar la terminación de sus
descendientes. Se conservan las salidas parciales.

Los fallos técnicos, errores de pruebas, informes inválidos, respuestas
inválidas, problemas de escritura e integridad alterada detienen la
orquestación aunque quede presupuesto. No hay reintentos técnicos ni
concurrencia. `intentos_agotados` significa que se consumió el presupuesto sin
aprobación; no habilita un tercer intento.

Los lanzadores actuales separan el entorno mínimo de evaluación del utilizado
para autenticar Codex. Los registros nuevos identifican `politica_entorno` sin
guardar valores de variables. Véanse las [listas permitidas, comprobaciones y
límites](credenciales-y-entornos.md); esta protección no se atribuye a las
implementaciones conservadas en registros históricos.

La CLI independiente de reparación conserva una evaluación del archivo residual
para diagnóstico si el agente falla y hay candidato. El orquestador utiliza su
modo estricto y detiene las etapas dependientes ante ese fallo. Esta diferencia
es deliberada; los códigos de las dos interfaces tampoco son intercambiables.

## Continuidad y validación de evidencia

[`case_evidence.py`](../case_evidence.py) lee referencias e informes sin importar
los módulos `solution` o `test_solution`. Los identificadores de pruebas se
obtienen del AST de métodos explícitos de clases `unittest.TestCase`; no admite
descubrimiento dinámico mediante `load_tests`. Se contrastan nombres, clases,
total, filas y cierre. Para corregir tras fallos se exigen diagnósticos
`AssertionError`: un código 1 aislado no basta. Omisiones, duplicados,
informes truncados, errores de importación o un `OK` sin pruebas no autorizan
una corrección.

Las evaluaciones se ejecutan en procesos Python separados, con `-B` y
`unittest discover` limitado al `test_solution.py` de cada copia. Así se evitan
conflictos entre módulos del mismo nombre de ambos casos.

| Archivo de reparación | Función |
| --- | --- |
| `referencia/solution.py` | Original defectuoso, fijo durante todos los intentos. |
| `partida.py` | Original en el primero; bytes exactos del candidato anterior en el segundo. |
| `candidato.py` | Propuesta del desarrollador, conservada para evaluación y revisión. |
| `partida.diff` | Original → partida. |
| `correccion.diff` | Partida → candidato; también existe en el primer intento. |
| `candidato.diff` | Original → candidato. |
| `feedback.json` | Informe o dictamen que motiva la corrección; `null` en el primero. |

`correction_context()` y `validate_repair()` comprueban partida, feedback,
hashes, diffs e inventarios previos. La evaluación inicial del segundo intento
corresponde al candidato anterior; la referencia original sigue siendo el
benchmark. El caso declarado debe concordar con contratos, pruebas, candidatos
y etapas enlazadas. No se puede usar evidencia de otro caso como procedencia.

Para autorizar una nueva revisión se exige también que los originales actuales
de `benchmark/` y `tasks/` coincidan con las referencias registradas. Se admiten
formatos antiguos legítimos del caso 02, con versión de registro 1 o sin esa
clave, siempre que su evidencia coincida. Los registros con contrato v1 no se
convierten en registros v2 ni se modifican sus hashes para hacerlos aceptables.
La evidencia rechazada no invoca al revisor, ni siquiera para consultar su CLI.

Estas exigencias de autorización son distintas de la consulta del inspector,
que puede leer un registro histórico con referencias diferentes de las actuales.

## Revisión y decisión del controlador

Los [prompts del caso 01](../prompts/reviewer_case_01.md) y
[del caso 02](../prompts/reviewer.md) exigen una revisión estática contra el
contrato, incluidas entradas admitidas no cubiertas por las pruebas. Prohíben
ejecutar o importar el candidato, editar archivos, instalar dependencias, usar
Git, navegar o delegar. Una prueba ausente no es por sí sola un defecto.

El revisor debe entregar JSON con `decision`, `resumen` y `hallazgos`.
`aprobar` requiere una lista vacía; `solicitar_cambios`, al menos un hallazgo.
Cada hallazgo identifica `candidato.py`, una línea existente, una explicación
y un ejemplo con entrada válida, resultado esperado y comportamiento deducido.
Se rechazan claves duplicadas, campos adicionales, tipos incorrectos y JSON
no estándar. La estructura válida no demuestra la verdad del razonamiento.

La decisión del controlador es independiente del dictamen: un `aprobar`
acompañado de timeout, salida no cero, error de registro o integridad alterada
no produce aprobación. Un dictamen válido puede conservarse para diagnóstico
aunque el proceso falle.

Las opciones construidas por los controladores incluyen aprobaciones `never`,
web y delegación desactivadas, `--ephemeral`, `--json`, entrada por stdin y
respuesta final separada. El desarrollador usa `workspace-write`, sin raíces
adicionales y con red desactivada; el revisor usa `read-only` y un esquema JSON.
El directorio temporal del agente se elimina al terminar. Modelo, proveedor y
esfuerzo efectivos no se deducen de esas opciones o de la versión de la CLI.

## Archivos de los registros locales

Todo lo siguiente se genera bajo `runs/`, excluido de Git. Los nombres llevan
fecha UTC, caso, tipo de etapa y UUID; el resumen general enlaza las etapas.

| Registro | Materiales conservados |
| --- | --- |
| Evaluación local (`run_case.py`) | `contrato.md`, `workspace/`, `stdout.txt`, `stderr.txt`, `resultado.json`. |
| General de orquestación | `referencia/` con contrato, original y pruebas; `resultado.json` con etapas, rutas, transiciones, presupuestos, tiempos e integridad. |
| Reparación | `referencia/`, partida, candidato, tres diffs y feedback; `inicial/` y `posterior/` con workspace, stdout, stderr y resultado; `agente/` con entrada, eventos, errores, respuesta, copia final de pruebas, versión, ayuda y resultado. |
| Revisión | `origen.json`, `materiales/`, `revisor/`, `dictamen_validado.json` si existe y `resultado.json`. |

`materiales/` conserva contrato, original, candidato, diff, pruebas, resultado,
stdout y stderr posteriores y `respuesta.schema.json`. Los directorios de
agente conservan por separado la versión y ayuda de CLI, sus canales y JSON.
`respuesta_final_disponible` o `respuesta_disponible` distinguen una respuesta
recogida de un archivo vacío preparado para el registro.

`unittest` escribe normalmente en `stderr.txt`; stdout vacío no implica que
no haya informe. Fechas UTC, duración monotónica, estado del proceso y código
de salida se guardan por separado. Las rutas de proceso son absolutas.
`en_curso`, código `null` o archivos ausentes no acreditan éxito. Si falla una
escritura se intenta conservar el resto de los diagnósticos.

## Consulta con el inspector

El inspector presenta los campos del registro general y comprueba su coherencia
con los JSON enlazados. Cuenta los intentos de la lista y toma invocaciones y
presupuestos de los campos del controlador, sin contar eventos internos.

El modo predeterminado y `--format text` conservan la presentación textual.
`--format json`, incorporado localmente, devuelve exclusivamente un objeto del
[esquema v1](../tasks/003-inspect-run-json.md): `version_esquema`, `consulta` y
`ejecucion`. Los valores desconocidos son `null`; los datos válidos del general
se conservan aunque una evidencia enlazada sea inválida. No incluye detalles
por intento, dictámenes completos ni certificaciones de integridad.

Con argumentos válidos, JSON deja stderr vacío e incluye las incidencias en
`consulta.incidencias`. Devuelve 0 cuando completa la consulta y 1 si la evidencia
es incompleta o incoherente; ambos resultados contienen JSON válido. Ese código
coincide con `consulta.codigo_salida`, no necesariamente con
`ejecucion.codigo_salida`: una ejecución fallida con código 3 puede consultarse
con código 0. Los argumentos inválidos conservan código 2, stdout vacío y
diagnóstico en stderr. La consulta JSON no prepara el formateo textual y conserva
exactamente las duraciones enteras válidas, incluso mayores que el rango de float.

Para calcular recuentos lee los JSON de evaluación, sus informes stderr y
`referencia/test_solution.py` de cada reparación. Solo informa de pruebas
superadas o cantidades cuando puede contrastar referencias, filas, total,
cierre y código. No exige el benchmark actual. Un timeout conservado puede
consultarse con éxito mostrando recuentos desconocidos; un informe necesario
ausente o inválido deja una consulta parcial con código 1.

No lee candidatos, prompts o eventos; las pruebas se leen solo para el análisis
estático del informe. No ejecuta candidatos, pruebas, Git o Codex ni inspecciona
variables de entorno. Muestra dónde consultar esos materiales.
«Integridad registrada» reproduce los valores del controlador:
no es un recálculo de hashes ni una auditoría independiente. Dos intentos
registrados tampoco prueban por sí solos una corrección satisfactoria.

En texto, duración, configuración u otros datos ausentes se muestran como «no consta»;
no se convierten en cero. Modelo, proveedor y esfuerzo no constan en el formato
de resumen utilizado. Los mensajes de error se abrevian a 240 caracteres y
se muestran hasta cinco errores del controlador por etapa; el resto se consulta
en sus archivos. Las rutas relativas de etapas se resuelven desde el registro
general; las absolutas deben seguir accesibles, por lo que mover solo una
carpeta de un experimento puede dejar enlaces rotos.

## Códigos de salida

Cada interfaz tiene su propio significado. Los códigos originales de agentes
y procesos de pruebas permanecen dentro de sus registros.

| Código | `orchestrate_case.py` | `review_case.py` |
| --- | --- | --- |
| 0 | `aprobada` | `aprobada` |
| 1 | `intentos_agotados` | `cambios_solicitados` |
| 2 | Argumentos incorrectos | Argumentos incorrectos |
| 3 | Fallo del desarrollador o revisor | `fallo_revisor` |
| 4 | Timeout de una etapa | `tiempo_agotado_revisor` |
| 5 | Respuesta inválida del revisor | `respuesta_invalida` |
| 6 | `modificacion_no_permitida` | `modificacion_no_permitida` |
| 7 | `evidencia_invalida` | `evidencia_invalida` |
| 8 | Fallo del controlador o error de pruebas | `fallo_controlador` |

| Código | `repair_case.py` |
| --- | --- |
| 0 | `supera_las_pruebas_disponibles`, con aceptación e integridad. |
| 1 | `no_supera_pruebas`: fallo o timeout de evaluación posterior. |
| 2 | Argumentos incorrectos. |
| 3 | `fallo_agente`: CLI, proceso o candidato ausente. |
| 4 | `tiempo_agotado_agente`. |
| 5 | `modificacion_no_permitida`. |
| 6 | `fallo_controlador`. |

La reparación independiente puede devolver 3 ante un timeout de comprobación
previa de CLI; la orquestación estricta identifica ese timeout y se detiene
con 4. No se traducen los códigos de una CLI como si fueran los de otra.

| Código | `run_case.py` | `inspect_run.py` |
| --- | --- | --- |
| 0 | Proceso terminado y registro conservado, aunque las pruebas fallen. | Consulta completada, aunque la ejecución consultada fallara. |
| 1 | Timeout o error al preparar, ejecutar o guardar. | Consulta incompleta por archivos o datos; muestra lo disponible y el diagnóstico. |
| 2 | Argumentos incorrectos. | Argumentos incorrectos. |

## Comprobaciones y límites

La suite del controlador usa fixtures temporales y agentes simulados. No
necesita los registros personales de `runs/`. Incluye los métodos de aceptación
JSON, hallazgos y anidamiento mediante [clases de CI](../tests/test_inspect_json.py),
sin duplicar las suites ni modificar sus aserciones. Las comprobaciones nuevas
no dependen de Git histórico ni de credenciales. Para ejecutarla en otro momento:

```bash
python3 -B -m unittest discover -s tests -v
```

Los benchmarks defectuosos se evalúan por separado, si se desea observar sus
fallos, con un proceso por caso para evitar conflictos de nombres:

```bash
python3 -B -m unittest discover -s benchmark/case_01 -v
python3 -B -m unittest discover -s benchmark/case_02 -v
```

Las pruebas del benchmark fallan deliberadamente; no están omitidas ni usan
`expectedFailure`. Estos comandos de referencia no se han ejecutado durante
la reorganización documental.

Una carpeta temporal o un cwd no garantiza aislamiento de lecturas. El sandbox
del revisor tampoco impide por sí solo ejecutar un intérprete; la revisión
estática es una restricción del encargo que debe contrastarse con los eventos.
Las evaluaciones Python del controlador no heredan automáticamente el sandbox
de Codex. Los hashes comparan el estado conservado: no detectan modificaciones
transitorias revertidas ni autentican una falsificación consistente. El
prototipo no ofrece una barrera de seguridad para código arbitrario no confiable.

# Segunda tarea real: CSV de consultas del inspector

Preparación del **19 de octubre de 2026**, rama `feat/tarea-exportacion-csv`,
sobre `main` actualizado y limpio, base completa
`4cda45e2ccda3f7091f8ab15e55087516c09bec0`. La base incorpora la corrección AST
del inspector. **Exportador incorporado explícitamente el 19 de octubre:**
[export_runs.py](../../../export_runs.py) conserva los bytes exactos de la entrega
autorizada, con modo 0644. La preparación e integración descritas abajo se comprobaron
sin invocar modelos, con agentes simulados donde correspondía. Posteriormente
se realizó un primer recorrido real con un desarrollador y un revisor; su
[contraste del 19 de octubre](contraste-real-2026-10-19.md) acredita aceptación
17/17 y regresión congelada 286/286, y revisó estáticamente la entrega sin
incorporarla en aquel paso. Fue una revisión automática asistida por Codex,
no una auditoría humana. La [incorporación posterior y cobertura permanente](#incorporación-explícita-y-cobertura-permanente)
se documentan por separado, conservando los resultados de cada hito.

El [contrato 004](../../../tasks/004-export-runs-csv.md) permitirá reunir
consultas del [esquema JSON v1](../../../tasks/003-inspect-run-json.md) en CSV,
con orden y duplicados conservados, desconocidos como celdas vacías y códigos
de consulta y ejecución separados. Consume archivos ya exportados; no recibe
directorios ni invoca el inspector. El formato general del orquestador de
proyectos queda fuera de este contrato.

## Uso incorporado

```bash
python3 -B export_runs.py consulta_1.json consulta_2.json
```

Cada entrada es un archivo UTF-8 con un único documento completo del esquema
JSON v1 del inspector. Las rutas relativas se interpretan desde el cwd; su texto
se conserva en `origen`, junto con el orden y los argumentos duplicados. `--`
permite nombres que empiezan por guion. No recibe directamente registros del
orquestador de proyectos ni su JSON general, y no ejecuta el inspector.

Produce una cabecera y una fila por argumento, con las once columnas del contrato,
UTF-8 y terminadores LF. Conserva cadenas y números exactos; `null` produce una
celda vacía, distinta de cero. Valida todos los archivos antes de emitir CSV.

| Código del exportador | Resultado |
| --- | --- |
| 0 | CSV completo en stdout y stderr vacío, incluso para consultas incompletas o ejecuciones fallidas válidas. |
| 1 | Archivo ilegible o documento inválido; stdout vacío y diagnóstico localizado en stderr. |
| 2 | Argumentos incorrectos; stdout vacío y diagnóstico en stderr. |

`-h` y `--help` muestran ayuda en stdout con código 0, sin CSV. El código del
exportador no sustituye los valores declarados en `consulta_codigo_salida` y
`ejecucion_codigo_salida`, que permanecen como columnas independientes.

## Evaluador independiente

Desde la raíz del repositorio, con Python 3.12 y biblioteca estándar:

```bash
python3 -B evals/tareas_reales/export_csv/evaluar.py --project .
python3 -B evals/tareas_reales/export_csv/comprobar_evaluador.py
```

El primer comando evalúa el proyecto indicado; `--project` admite una ruta
absoluta a otra copia. Ambos evaluadores se reutilizan ahora desde `tests/`:
para validar el árbol completo basta el descubrimiento habitual de unittest,
sin repetir estos comandos por separado. En el flujo CSV,
[evaluar.py](evaluar.py) y su utilidad de entorno deben ejecutarse desde una
autoridad congelada externa al workspace editable. La utilidad
[process_environment.py](../../../process_environment.py) se resuelve respecto
a la ubicación del evaluador, nunca respecto a `--project`. Se debe preservar
la disposición `evals/tareas_reales/export_csv/evaluar.py` respecto a esa raíz.

La CLI candidata se ejecuta con intérprete absoluto, `-B`, stdin cerrado,
cwd temporal, `PATH` vacío y entorno de evaluación sin credenciales heredadas,
con HOME/configuración/tmp temporales. Límite de **10 segundos por consulta**.
No se importa el candidato. La captura usa bytes para no normalizar CRLF y
ocultar un incumplimiento de los terminadores LF del CSV.

Los **17 métodos** usan exclusivamente documentos sintéticos y variantes
`subTest`: cabecera, correspondencia de columnas, orden y duplicados, null y
ceros, estados y códigos independientes, enteros de hasta 5001 dígitos,
precisión decimal y exponentes finitos fuera del rango float, comillas/comas/
saltos de línea/Unicode, origen literal, nombres con guion, ayuda, estructura
completa, tipos, coherencia de consulta, JSON ambiguo o inválido, archivos
ausentes y directorios, y ausencia de CSV parcial si falla una entrada posterior.
Se validan también incidencias, desarrollador y revisor aunque no sean columnas.
No se construye una implementación de referencia del exportador.

En `finally` se inventarían los dos árboles, incluso ante una aserción fallida,
timeout o excepción: entradas temporales y proyecto evaluado. Se comparan
entradas, modos, mtime y SHA-256 de archivos regulares, sin seguir enlaces ni
incluir atime. Los cachés Python y archivos nuevos sí se detectan. En un checkout
local no se leen contenidos de `.git`, `runs`, `.codex`, `.agents`, `.aws`,
`.venv` ni `.env*`; solo se inventaría la entrada de esas rutas. No se certifica
la conservación de su contenido privado. En el futuro workspace de evaluación
esas rutas deben quedar fuera de la copia. Esto comprueba conservación en los
escenarios evaluados; no constituye un sandbox ni demuestra ausencia de toda
posible actividad de red de un candidato adversarial.

El evaluador devuelve 0 si todo pasa, 1 ante fallos o errores y 2 si sus propios
argumentos son inválidos. No hay omisiones ni `expectedFailure`. La falta del
archivo editable es una aserción explícita en la preparación de cada método:
`Funcionalidad pendiente: falta export_runs.py como archivo regular; CLI no invocada`.
Así conserva las mismas identidades de métodos antes y después de implementar
la tarea, sin inventar un código de salida del exportador inexistente.

## Resultados reales de preparación

Con **Python 3.12.3**, se ejecutó **una vez** la aceptación contra una copia
temporal obtenida mediante `git archive` del SHA base indicado arriba. Se usó
el [runner actual](../../../project_flow_runner.py) para registrar métodos,
aserciones fallidas, errores y cierre de unittest, sin ejecutar controladores:

```bash
python3 -B project_flow_runner.py \
  --project "$BASE_CSV" --report "$EVIDENCIA_CSV/pruebas.json" \
  --acceptance "$PWD/evals/tareas_reales/export_csv/evaluar.py"
```

`BASE_CSV` designaba la copia extraída y `EVIDENCIA_CSV` un directorio temporal
externo al repositorio, donde se conservaron también stdout, stderr y un resumen.

| Comprobación | Métodos | Aserciones fallidas registradas | Errores | Resultado |
| --- | ---: | ---: | ---: | --- |
| Aceptación contra la base sin `export_runs.py` | 17 | 17 | 0 | Código 1; 0,006 s; 0 omisiones y 0 invocaciones de la CLI candidata. |
| Comprobaciones del evaluador, estado final | 12 | 0 | 0 | Código 0; 0,114 s. |

Los 17 fallos son la misma precondición de disponibilidad en 17 métodos; **no
significan que se hayan ejecutado 17 escenarios CSV**. La copia base quedó
intacta, incluidos contenido, entradas y metadatos. El runner dejó una sesión
completa y los 17 métodos iniciados y terminados. Unittest no cuenta el total
de aserciones correctas; las variantes/subtests no se suman como métodos.

[comprobar_evaluador.py](comprobar_evaluador.py) usa respuestas prefijadas y
parches del proceso, sin crear `export_runs.py`. Verifica el lanzamiento y el
entorno, acepta CSV válido con comillas opcionales, rechaza redondeo, formatos,
canales o diagnósticos incorrectos y CSV parcial, comprueba ambos inventarios
tras fallos, timeouts y errores técnicos, y verifica las identidades estáticas
del evaluador. Los fallos inducidos dentro de esos controles son resultados
esperados de las respuestas prefijadas, no una ejecución de un exportador real.

La primera ejecución de esas comprobaciones obtuvo 12 métodos, 1 fallo de
aserción y 0 errores: un doble de prueba reutilizaba un directorio de entradas
entre respuestas. Se corrigió su aislamiento sin rebajar aserciones; la tabla
recoge la ejecución posterior. Es distinto del rechazo inicial de aceptación.

En aquel hito, la aceptación CSV y sus comprobaciones permanecían **fuera de `tests/` y de CI**.
Solo se inventarió el descubrimiento habitual: 286 métodos, ninguno de CSV;
no se ejecutaron. No se repitió la regresión completa porque el código y las
pruebas existentes no han cambiado. Sus resultados anteriores no se atribuyen
a esta nueva aceptación ni acreditan la funcionalidad pendiente.

También se comprobaron **49 enlaces locales y sus anclas**, la sintaxis de los
dos módulos nuevos y la concordancia de cabecera y ejemplos JSON/CSV del
contrato. `git diff --check` pasó. SHA-256 del evaluador usado en la aceptación
inicial: `45881081fafb14403af3b28714954f61bc02f2a9456b045291567a3596b77ebf`.

## Revisión del evaluador: duraciones equivalentes

Revisión posterior del **19 de octubre de 2026**, sin cambiar el contrato.
`assert_export` comparaba filas completas como cadenas: rechazaba
`1.23456789e1` cuando esperaba `12.3456789`, pese a representar exactamente
la misma duración real. La reproducción usó una respuesta CSV prefijada,
con `subprocess.run` sustituido: **1 método, 1 fallo, 0 errores**, código 1.
No creó ni ejecutó el exportador. El log anterior al arreglo se conserva
localmente en `/tmp/csv-duracion-reproduccion.log`; el evaluador tenía el hash
histórico indicado arriba. Los 17 fallos iniciales por ausencia del exportador
son otro resultado, que no se ha repetido ni reinterpretado.

Las duraciones esperadas de entradas reales se marcan con `Decimal` y se
comparan por valor decimal exacto, sin conversión a float ni redondeo por el
contexto decimal. Solo se admite notación decimal o científica finita. Las
duraciones enteras y null conservan comparación literal, igual que origen,
cadenas, cabeceras y el resto de columnas. Vacío no equivale a cero. Se mantienen
los rechazos de valores alterados, espacios añadidos, valores no finitos,
canales incorrectos y CSV parcial.

Validación de esta revisión con Python 3.12.3:

```bash
python3 -B evals/tareas_reales/export_csv/comprobar_evaluador.py
python3 -B -m unittest discover -s tests -p 'test_project_test_inventory.py' -v
```

| Comprobación posterior | Métodos | Fallos | Errores | Resultado |
| --- | ---: | ---: | ---: | --- |
| Controles del evaluador con respuestas prefijadas | 17 | 0 | 0 | Código 0; 0,194 s. |
| Pruebas enfocadas de la utilidad de inventario | 14 | 0 | 0 | Código 0; 1,209 s. |

Los controles aceptan notaciones equivalentes, incluido un exponente fuera
del rango float, y rechazan una diferencia posterior a 28 cifras, redondeos,
cero convertido en vacío, null convertido en cero y representaciones no
enteras de entradas enteras de hasta 5001 dígitos. Los 17 métodos de aceptación
conservan sus identidades; no se ha ejecutado la aceptación contra un exportador.

SHA-256 del evaluador **revisado**:
`55b47eb7b34d208cc465bd59363f4f82b4e43b32cae56377ff1f40ced3175f1d`.
Logs locales: `/tmp/csv-evaluador-revision.log` y
`/tmp/csv-inventario-pruebas.log`. La primera ejecución de las 14 pruebas del
inventario detectó 1 fallo en un fixture con indentación incorrecta; se corrigió
el fixture antes de la ejecución satisfactoria, sin rebajar la comprobación
de conservación tras un error de importación. Su log es
`/tmp/csv-inventario-pruebas-inicial.log`.

Se revisó el diff y se comprobaron 50 enlaces locales y sus anclas, sin errores.
La comprobación de espacios del diff incluyó también los archivos nuevos.
El contrato 004 y el cambio previo del README principal se conservaron byte
por byte; inspector, controladores y autoridades históricas siguen intactos.

## Inventario de una base protegida

[project_test_inventory.py](../../../project_test_inventory.py) prepara una
vía independiente que ahora utiliza la preparación CSV; no sustituye
`static_test_ids` ni participa en los validadores históricos. Su API `inventory_tests` y su CLI
requieren una referencia explícita. **El llamante debe proporcionar una copia
protegida de la base de confianza anterior al trabajo del agente, nunca el
workspace candidato**. La utilidad no puede acreditar por sí sola esa confianza.

```bash
# BASE_PROTEGIDA: copia externa de la revisión de confianza, sin cachés.
# PYTHON_ABSOLUTO: ruta absoluta al intérprete seleccionado.
# INFORME_INVENTARIO: archivo fuera de la copia protegida.
"$PYTHON_ABSOLUTO" -B project_test_inventory.py \
  --reference "$BASE_PROTEGIDA" --python "$PYTHON_ABSOLUTO" --timeout 30 \
  > "$INFORME_INVENTARIO"
```

El controlador no importa módulos de esa base. Lanza un hijo con intérprete
absoluto, `-B`, entorno `evaluation`, stdin cerrado, cwd explícito en la copia
y timeout. El hijo usa el descubrimiento habitual de unittest (`tests`,
patrón `test*.py`) y recorre la suite para recoger `id()`. No llama a `run`,
`TextTestRunner` ni a métodos de prueba. **El descubrimiento importa módulos
y puede ejecutar código de inicialización y hooks `load_tests`**: no es análisis
estático ni aislamiento de seguridad. Debe usarse solo con la base de confianza.

Stdout contiene un objeto JSON con versión, estado `completado` o `error`,
identidades únicas ordenadas, total, diagnósticos y procedencia técnica. Incluye
ruta de referencia, intérprete/versión de Python, política de entorno, timeout,
hashes de la utilidad y su dependencia de entorno, y hashes del árbol antes y
después. Conserva stdout/stderr del hijo como datos; los mensajes de
inicialización no se confunden con el informe. La CLI devuelve 0 solo con
inventario completo y copia intacta; devuelve 1 ante error. Los argumentos
incorrectos de argparse conservan código 2.

Se rechazan errores de importación o descubrimiento, pruebas sintéticas
`_FailedTest` incluso sin `loader.errors`, identidades duplicadas y suites
vacías. Un error produce identidades vacías y total 0, nunca un inventario
parcial utilizable. Se comprueban entradas, contenido SHA-256, modos y mtime
en `finally`, también tras error o timeout; no se siguen enlaces y se rechazan
archivos especiales y cachés Python. La utilidad no modifica la copia ni
restaura silenciosamente alteraciones. Los hashes y comprobaciones detectan
cambios observables; no impiden toda actividad de código importado.

Las [pruebas enfocadas](../../../tests/test_project_test_inventory.py) usan
proyectos sintéticos con herencia local e importada, métodos propios y
heredados y sobrescrituras. Cubren los rechazos anteriores, errores `SystemExit`,
timeout, alteraciones de contenido/metadatos, creación de archivos/cachés,
enlaces, canales de la CLI y entorno del hijo. Un centinela acredita que se
descubre el método sin ejecutar ni su cuerpo ni `setUp`; otro demuestra que
la inicialización sí ocurre en el hijo y no se importan esos módulos en el
controlador. Estas pruebas sí pertenecen al descubrimiento habitual de `tests/`.

### Contraste real de identidades

Se reconstruyó con `git archive` una copia temporal del commit completo
`4cda45e2ccda3f7091f8ab15e55087516c09bec0`, anterior a los cambios de esta rama.
Se quitaron los permisos de escritura de archivos y directorios antes del
inventario. Con Python 3.12.3, el informe quedó `completado`, código 0, sin
errores, sin cachés y con el mismo hash del árbol antes/después. **Solo se
inventariaron pruebas: no se ejecutó la regresión de la base ni se acredita
que sus métodos hayan pasado.**

| Comparación de identidades | Resultado |
| --- | ---: |
| Descubrimiento de la base protegida | 286 |
| `static_test_ids` sobre los mismos archivos | 252 |
| Solo en descubrimiento | 34, todas en `test_inspect_json` |
| Solo en el inventario estático | 0 |
| `TestInspectJsonAcceptance` omitidas | 21: 14 heredadas y 7 propias |
| `TestInspectJsonHallazgos` omitidas | 6 heredadas |
| `TestInspectJsonAnidamiento` omitidas | 7 heredadas |

Se compararon los conjuntos completos de identidades, no solo sus totales.
`static_test_ids` reconoce herencia local, pero no las bases importadas de esas
tres clases. Al no reconocerlas como `TestCase`, descarta también los siete
métodos propios de `TestInspectJsonAcceptance`. Por eso devuelve una lista
vacía para ese módulo: faltan **27 heredados y 7 propios**. No hubo discrepancia
con los valores comunicados, y la utilidad no contiene un total esperado fijo.

Evidencia local en `/tmp/csv-inventario-base-2f9xgo53/`: `inventario.json`
contiene las 286 identidades; `comparacion_identidades.json`, las listas estáticas
omitidas y la diferencia de conjuntos; `procedencia.json`, el commit, hash del
archivo Git, comando y cwd. La copia protegida se conserva en `base/`.
SHA-256 de `inventario.json`:
`b11bf61ca19d9dc6ca3ad9615fc0aeb04e62fce810688c74b67fc467e70662d6`.
SHA-256 de la utilidad empleada:
`b0b4aca8f40db44ec33dcc3749187ff670bcac08be9518fbd014ed79534cfac2`.
Son evidencias de aquella comprobación local, no autoridades congeladas
de una ejecución del flujo. La integración debe congelar **versión de
la utilidad y su dependencia, informe y procedencia de la base**, antes de
crear el workspace del agente, y validar después las identidades contra ese
informe sin reinterpretar registros históricos.

## Diagnóstico previo de integración

Antes de este hito, el flujo admitía únicamente `inspect-json`. Se documentaron
estos puntos de adaptación; la implementación posterior se describe en la
sección siguiente y conserva la vía histórica.

| Archivo / interfaz | Supuesto detectado antes de integrar CSV |
| --- | --- |
| [repair_project.py](../../../repair_project.py): `CONTRACT`, `ACCEPTANCE`, `EDITABLE`, `freeze`, `run_project`, `build_prompt`, `main` | Fija contrato 003, aceptación JSON e `inspect_run.py`; `freeze` exige `required(source / EDITABLE)`. La precondición busca literalmente `unrecognized arguments: --format json`; las rutas, prompts, procedencia y diff fijan inspect-json. El control de alcance indexa el modo previo del archivo. |
| [orchestrate_project.py](../../../orchestrate_project.py): `main`, `run_orchestration` | CLI y validación interna solo admiten inspect-json. Exige el diagnóstico inicial anterior, lee `starting` como archivo existente, lo escribe en el primer workspace y compara modos anteriores. Las entregas, diffs, continuidad y feedback parten de esos bytes. |
| [project_flow.py](../../../project_flow.py): `TYPE`, `SUITES`, `freeze_flow`, `evaluate_flow`, `validate_delivery` | Fija el tipo `orquestacion_inspect_json_v1`, los prompts y cuatro suites: aceptación, regresión, hallazgos y anidamiento de JSON. Incluso en la evaluación inicial calcula el hash con `required(workspace / EDITABLE)`. Valida contrato 003, originales existentes, diffs de inspect_run y entradas previas del inventario. |
| [project_flow_runner.py](../../../project_flow_runner.py): `--project`, `--report`, `--acceptance`, `--checks-output` | Ya puede ejecutar esta aceptación externa mediante `--acceptance`; conserva identidades y subtests. CSV no necesita `--checks-output` ni las suites auxiliares específicas de JSON. La selección de suites y sus límites se hace en `project_flow.py`. |
| [review_project.py](../../../review_project.py): `validate_evidence`, `run_review`, `run_delivery_review`, `run_isolated_review` | La vía histórica exige el rechazo y la reevaluación originales de inspect-json: debe permanecer intacta. La revisión de entregas y la aislada dependen del tipo/procedencia inspect-json y de la validación de `project_flow`. `response_schema`, `validate_verdict`, `_run_review` y `review_dependencies` fijan `inspect_run.py` para archivo, líneas o selección. |
| [project_flow.py](../../../project_flow.py): `delivery_review_evidence`, `delivery_review_materials` | Entrega al revisor contrato 003, candidato y original de inspect_run, `test_inspect_run.py`, evaluador JSON, diff y resumen de evidencia. Debe seleccionar materiales propios de CSV y representar la ausencia inicial sin fabricar un original. |

Adaptación mínima prevista en la preparación inicial:

1. Seleccionar explícitamente entre dos tareas conocidas: contrato, aceptación,
   archivo editable, prompts, suites y precondición inicial. CSV usará este
   contrato/base y aceptación más regresión de esa base. Mantener la selección
   y las autoridades existentes de inspect-json; no hace falta un sistema de plugins.
2. Representar ausencia inicial de `export_runs.py` en procedencia, inventarios
   y hashes con un estado explícito distinto de archivo vacío. Conservar esa
   ausencia en la evaluación inicial y el primer workspace. Autorizar solo su
   creación como archivo regular, con modo permitido; usar diff de alta desde
   `/dev/null`. Tras la primera entrega, conservar la continuidad del candidato
   exacto. Ajustar los accesos a entradas/modos previos y la validación de
   `partida.py`, hashes, cambios y diffs para ese estado ausente.
3. Congelar el evaluador CSV y `process_environment.py` fuera del alcance del
   desarrollador, conservando su disposición y hashes. La preparación debe
   acreditar ausencia real del archivo, rechazo explícito de aceptación y
   regresión superada, en lugar de buscar el antiguo error de `--format`.
   La aceptación posterior debe ejecutarse completa con sus 17 identidades.
4. Conectar el inventario de bases nuevas: la utilidad preparada arriba recoge
   las **286 identidades**, incluidas las **34** omitidas por el inventario
   estático. Congelar su versión, dependencia, informe y procedencia sobre la
   base protegida anterior al agente. Consumir esas identidades en la nueva vía
   sin sustituir `static_test_ids`, relajar la validación de informes ni
   reescribir inventarios históricos. Medir los límites de evaluación al
   integrar; el límite por consulta CSV no es el presupuesto de toda la suite.
5. Preparar prompts y revisión propios: contrato 004, esquema 003 protegido,
   `export_runs.py`, diff de creación, constancia de ausencia original, aceptación
   CSV y evidencia del candidato exacto más regresión pertinente. Adaptar archivo
   permitido y número de líneas del dictamen, las dependencias y la procedencia
   para CSV, también si se habilita revisión aislada. Conservar sin cambios la
   vía histórica y los registros rechazados. Mantener reservas de invocación,
   presupuestos, sellado, detenciones y ausencia de incorporación automática.

En aquella revisión solo estaba preparada la utilidad de inventario. El hito
siguiente conecta la nueva vía, sin crear el exportador ni reanudar el experimento.

## Integración CSV validada con simulaciones

El controlador comparte el bucle de intentos entre las dos selecciones conocidas,
sin plugins. [project_flow.py](../../../project_flow.py) concentra contrato,
base, archivo editable, prompts, suites y límites de cada selección. Las
interfaces, autoridades y presupuestos de `inspect-json` se conservan.

Comando preparado para una **futura ejecución real**, no ejecutado con modelos
en este hito:

```bash
python3 -B orchestrate_project.py export-csv --max-attempts 2
```

Con Codex disponible ese comando invocará agentes. Admite uno o dos intentos,
con dos por defecto: una reserva de desarrollador y una de revisor como máximo
por intento, cuatro invocaciones en total. No aumenta presupuestos, reintenta
fallos técnicos, reanuda registros ni aplica candidatos al proyecto original.
Los registros llevan tarea `export-csv` y tipo `orquestacion_export_csv_v1`.

| Etapa CSV | Límite |
| --- | ---: |
| Desarrollador | 300 s por invocación |
| Revisor | 300 s por invocación |
| Aceptación | 60 s por suite |
| Regresión | 300 s por suite |
| Inventario | 30 s |
| Consultas previas de versión y ayuda | 10 s cada una |

La preparación reconstruye los blobs de Git del commit
`4cda45e2ccda3f7091f8ab15e55087516c09bec0` y verifica sus identificadores, contenidos
y modos. Congela fuera del workspace contrato 004, esquema 003, evaluador CSV,
dependencias, utilidades, controladores, prompts y configuración. Preserva la
disposición del evaluador bajo `autoridades/evals/tareas_reales/export_csv/`,
con `process_environment.py` en la raíz de esa autoridad.

Antes de cualquier agente, inventaría exclusivamente la copia Git verificada.
Guarda el informe, identidades, snapshot previo, hashes de utilidad y entorno,
comando, tiempos, canales y procedencia en `referencia/inventario/` y
`referencia/procedencia.json`. La validación posterior lee esa autoridad; nunca
descubre las identidades esperadas desde el candidato ni de sus resultados.
Un inventario incompleto, alterado, con identidades incoherentes o con error
detiene la preparación. El descubrimiento importa código de confianza; copias,
entornos y hashes **no son un sandbox**.

Después ejecuta aceptación y regresión sobre otra copia de la base. Exige
ausencia real del editable, todos los métodos de aceptación terminados con
fallo de disponibilidad y sin errores técnicos, y regresión superada con todas
las identidades congeladas. El antiguo diagnóstico de `--format json` no
autoriza CSV. El inventario por sí solo tampoco acredita una regresión superada.

La ausencia se representa como `{"tipo":"ausente","sha256":null,"modo":null}`
en la procedencia y partida, y como entrada ausente en el árbol de archivos.
El primer workspace no contiene `export_runs.py`. No se fabrica un original
vacío, hash de bytes inexistentes ni `partida.py`. La entrega permitida es
únicamente un archivo regular `export_runs.py` con modo **0644**; se rechazan
enlaces, especiales, otros modos y cambios fuera de alcance. Se conserva
`partida.json` y un diff de creación desde `/dev/null`. En una corrección,
`partida.py` contiene exactamente la entrega anterior y coincide su SHA-256;
`anterior.diff` representa esa modificación y `candidato.diff` la creación
respecto a la base.

Cada candidato válido se incorpora exclusivamente a una nueva copia reconstruida
de la referencia. Solo se ejecutan aceptación CSV y regresión; no las suites
de hallazgos y anidamiento de inspect-json. Se contrastan identidades completas,
códigos, cierres, informes y conservación del árbol. Un candidato ausente o fuera
de alcance termina como `entrega_invalida` (6), sin evaluación ni revisión;
los fallos de aserción de un archivo válido pueden autorizar una corrección.
Una reserva o consulta CLI fallida conserva su fallo técnico y la ausencia,
sin simular que se recibió una entrega.

El [prompt de desarrollo](../../../prompts/developer_export_csv_flow.md) incluye
contrato, esquema protegido y feedback trazable. El [prompt de revisión](../../../prompts/reviewer_export_csv_flow.md)
recibe el candidato exacto, ambos contratos, constancia de ausencia, partida,
diffs, aceptación y un resumen de evaluaciones con hashes. Los informes extensos,
eventos, explicación del desarrollador y dictámenes anteriores se conservan
aparte. El esquema y el validador restringen hallazgos a `export_runs.py` y sus
líneas reales. Un dictamen válido no demuestra la verdad de sus hallazgos.
La revisión aislada de CSV se rechaza explícitamente antes de consultar la CLI.

| Salida del flujo | Código | Consecuencia |
| --- | ---: | --- |
| `lista_para_revision_humana` | 0 | Evaluaciones y aprobación válidas; no incorpora. |
| `intentos_agotados` | 1 | Pruebas fallidas o cambios solicitados al agotar intentos. |
| `fallo_tecnico` / `fallo_revisor` | 3 | Detención sin reintento. |
| `tiempo_agotado` / `tiempo_agotado_revisor` | 4 | Conserva las salidas parciales y reservas. |
| `respuesta_invalida` | 5 | No pide al revisor reparar su respuesta. |
| `entrega_invalida` / `modificacion_no_permitida` | 6 | Entrega o integridad no acreditadas. |
| `preparacion_no_autoriza` / `evidencia_invalida` | 7 | Detención; preparación inválida no reserva desarrollador. |
| `fallo_controlador` | 8 | Error de infraestructura o persistencia. |
| `interrumpida` | 9 | Conserva etapas disponibles y consumos; no reanuda. |

Los argumentos CLI inválidos mantienen código 2. Las reservas se persisten antes
de invocar y se consumen aunque el proceso falle después. Una solicitud válida
de cambios o fallos de aserción solo permiten continuar si queda otro intento;
no se repite hasta obtener una aprobación.

### Comprobaciones de la integración

Las [21 pruebas CSV](../../../tests/test_export_csv_flow.py) usan proyectos Git
temporales, ejecutables de agente simulados y evaluadores mínimos de marcadores.
Los candidatos son comentarios Python: **no son soluciones de referencia ni
acreditan aceptación real del exportador CSV**. Cubren creación y ausencia,
diffs, identidad y continuidad, preparación inválida, inventarios alterados o
incompletos, herencia importada, regresión inicial fallida, aprobación, corrección
por pruebas o dictamen, agotamiento, errores, timeout, interrupción, reservas
fallidas, dictámenes inválidos, alcance y conservación del original.

```bash
python3 -B -m unittest discover -s tests -p 'test_export_csv_flow.py' -v
python3 -B -m unittest discover -s tests -v
```

Con Python 3.12.3, las 21 enfocadas pasaron en 25,015 s, sin fallos ni errores.
También pasaron las 20 pruebas existentes de orquestación inspect-json en
28,638 s. Logs locales: `/tmp/csv-flujo-pruebas-final.log` y
`/tmp/csv-flujo-inspect-inicial.log`. La primera tanda CSV contenía 18 métodos,
todos superados; se amplió la cobertura antes de la ejecución de 21.

La regresión completa final del árbol actual pasó: **321 métodos, 0 fallos,
0 errores**, en 167,950 s; log `/tmp/csv-flujo-regresion-completa.log`. Incluye
las 21 pruebas nuevas del flujo CSV y las 14 de inventario preparadas en el hito
anterior. Se distingue de la regresión de 286 métodos de la base congelada.
No se modificó CI: su descubrimiento habitual recoge estas pruebas y utiliza
agentes simulados, sin llamar a modelos. Los cambios posteriores a esta ejecución
son documentales, por lo que no se repitieron las suites.

Además se ejecutó la preparación real, **sin agentes**, sobre la base Git:
inventario de 286 identidades; aceptación corregida con 17 fallos esperados por
ausencia, 0 errores y 0 subtests ejecutados; regresión de **286 métodos superada**
en 142,856 s. Se verificaron los conjuntos completos de identidades. El informe
de preparación acredita copia de evaluación, referencia y original intactos.
La evidencia local está en `/tmp/csv-flujo-base-real-k1ovjhk4/resumen.json` y
sus directorios `referencia/inventario/` e `inicial/`. Esta comprobación posterior
usa el evaluador corregido; no reemplaza los 17 fallos ni el hash histórico de
la preparación original.

### Traza simulada conservada

Registro completo bajo `/tmp/csv-flujo-traza-3kqtbkm3/`, con resumen en
`traza.json`. La base de esta traza es un fixture Git sintético y su regresión
tiene tres métodos, distintos de la base real. El recorrido observado fue:

| Paso | Resultado | Consumo acumulado |
| --- | --- | --- |
| Preparación | Editable ausente; aceptación del marcador falla; regresión 3/3. | D 0, R 0 |
| Intento 1: creación | Candidato A; aceptación 1 fallo, regresión 3/3; no se revisa. | D 1, R 0 |
| Intento 2: corrección | Parte de A exacto; candidato B; aceptación 1/1 y regresión 3/3. | D 2, R 0 |
| Revisión simulada | Dictamen aprobar; `lista_para_revision_humana`; sin incorporación. | D 2, R 1: 3/4 |

SHA-256 de A, idéntico a la partida del segundo intento:
`b41263fcc4d256eabb495cd041ab7bcb66bedc13d2eaef15694ed004d978de5d`.
SHA-256 de B:
`09292042b12b15e4b3e9698695d3d6b53591b64bcd6572907ecb56b7f5cd3b74`.
Los desarrollos simulados consumieron 0,0325 y 0,0322 s; la revisión, 0,0321 s,
con límites configurados de 300 s. Se utilizaron los dos intentos disponibles,
sin gastar una cuarta invocación. La traza demuestra el mecanismo sobre
fixtures; al cerrar aquel hito seguían pendientes la implementación y evaluación
real de un exportador. El [recorrido real posterior](contraste-real-2026-10-19.md)
se documenta por separado y no cambia la clasificación de esta simulación.

## Incorporación explícita y cobertura permanente

El **19 de octubre de 2026**, por autorización explícita, se incorporó
`export_runs.py` desde:

```text
runs/20261019T105401Z_export-csv_orchestrate_90b3b8fb88aa42ba8979db8f2037295a/intentos/1/evidencia/entrega/export_runs.py
```

SHA-256 de origen y destino, verificado antes y después de copiar:

```text
6449a52e8e3d7109454bc0208eb3df62ffc55116181039112746d17a7225bca7
```

El destino estaba ausente y se creó exclusivamente como archivo regular
**0644**, sin refactorizar ni reformatear sus bytes. La fuente archivada continúa
regular **0664**, con contenido y metadatos conservados. Los registros anteriores
no se modificaron, tampoco el informe de contraste que documenta el estado
anterior a esta incorporación.

La procedencia comprende **un desarrollo y una revisión reales**, aceptación
17/17, regresión congelada 286/286 y dictamen `aprobar` sin hallazgos. Después
se hizo el [contraste automático asistido por Codex](contraste-real-2026-10-19.md),
sin identificar incumplimientos concretos. La incorporación actual es una acción
explícita posterior, separada de la aprobación del controlador y del contraste;
no equivale a una auditoría humana ni a una nueva ejecución de agentes.

Los dos adaptadores permanentes son:

- [tests/test_export_csv.py](../../../tests/test_export_csv.py): hereda los 17
  métodos de `evaluar.AcceptanceTests` y fija el proyecto actual. Conserva CLI
  en proceso hijo, intérprete absoluto, `-B`, entorno `evaluation`, timeout de
  10 s y comprobaciones de inmutabilidad de entradas y proyecto. No importa
  el exportador.
- [tests/test_export_csv_evaluator.py](../../../tests/test_export_csv_evaluator.py):
  hereda los 17 métodos de `comprobar_evaluador.EvaluatorTests`. Conserva las
  respuestas prefijadas y sus controles de precisión, equivalencia decimal y
  científica, enteros grandes, null, cero, canales, CSV parcial y conservación
  ante fallos. Resuelve temporalmente el `import evaluar` del comprobador y
  restaura los módulos previos, sin modificar esa autoridad.

Cada método heredado aparece individualmente en el descubrimiento habitual;
se importan módulos, no clases base sueltas que se descubrirían otra vez.
Los adaptadores no lanzan suites secundarias. Los controles del comprobador
siguen ejercitando casos individuales con el proceso sustituido por respuestas
prefijadas; esos casos internos no son métodos adicionales del descubrimiento.
El nombre histórico de su control `test_identidades_compatibles_con_runner_y_sin_descubrimiento_en_ci`
se conserva: comprueba que el evaluador fuente está fuera de `tests/`; ahora
sus métodos entran en CI a través del adaptador.

El [workflow existente](../../../.github/workflows/tests.yml) ya ejecuta
`python3 -B -m unittest discover -s tests -v`, por lo que recoge ambas clases
sin cambios de configuración. No se modificaron contratos, evaluadores,
criterios, inspector, controladores ni base contractual. Los inventarios de
286 métodos siguen congelados; los 321 de preparación pertenecen a un hito
anterior. Esta incorporación añade 34 métodos al descubrimiento del árbol
actual y se valida conjuntamente, sin repetir la aceptación por separado.

### Validación del árbol incorporado

Una vez terminados los cambios de código y pruebas, se ejecutó **una sola vez**
desde la raíz:

```bash
python3 -B -m unittest discover -s tests -v
```

| Resultado local del 19 de octubre de 2026 | Valor |
| --- | --- |
| Python | 3.12.3; intérprete `/usr/bin/python3.12` |
| Métodos descubiertos y terminados | **355**, identidades únicas; todos `ok` |
| Fallos de aserción / errores / omisiones | **0 / 0 / 0** |
| Aceptación CSV / controles del evaluador incluidos | **17 / 17**, cada método una vez |
| Duración del cierre de unittest | **182,354 s** |
| Duración del proceso completo | **182,544681 s** |
| Código de salida / cierre | **0 / OK** |
| Stdout del runner | Vacío; resultados de unittest conservados en stderr |

No hubo fallos que exigieran corregir o repetir comprobaciones. Las identidades
CSV del log se contrastaron con los métodos de las clases fuente, sin ejecutar
nuevas suites. Los 355 corresponden al árbol actual: los 321 de preparación
más los 34 métodos permanentes incorporados aquí. La regresión contractual
de 286 y los resultados históricos anteriores permanecen separados e intactos.

La evidencia local, excluida de Git, se conserva en:

```text
runs/20261019T124001Z_export-csv_incorporacion_local_b311e71b2f3441fdb966e7409047f896/
```

`incorporacion.json` registra origen y destino, hashes, modos y ausencia previa;
`validacion.json`, comando, cwd, Python, tiempos, límite y código;
`stdout.txt` y `stderr.txt`, las salidas originales; `resumen_pruebas.json`,
las 355 identidades, recuentos y conservación. `antes.json` y las copias de
documentación previas permiten distinguir los cambios de este paso del trabajo
pendiente. Es evidencia de incorporación y validación local, no una ejecución
del flujo de agentes. No se publica el contenido de `runs/` ni configuración
privada; los registros anteriores se conservaron sin cambios.

Se verificaron de nuevo SHA-256, regularidad y permisos después de la suite:
destino **0644**, origen **0664**, contenido idéntico. Se revisaron diff,
espacios, enlaces y exclusiones. No se ejecutó Actions remoto ni se hizo
commit, push o merge. Tras la suite solo se completó esta documentación,
sin modificar código o pruebas y sin repetir su ejecución.

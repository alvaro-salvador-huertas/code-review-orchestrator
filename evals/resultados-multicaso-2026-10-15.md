# Resultados del experimento multicaso — 15 de octubre de 2026

**Revisión automática realizada por Codex**, posterior a las dos ejecuciones.
No se atribuye al usuario una revisión del código, los informes o los dictámenes.
Se ha auditado la evidencia conservada, sin volver a ejecutar candidatos,
pruebas ni agentes. La lectura humana prevista por el protocolo **no consta**;
este informe no acredita que se haya realizado.

Ambos casos terminaron **aprobados en el primer intento**, con una invocación
del desarrollador y una del revisor por caso: **cuatro invocaciones reales en
total**. Los informes posteriores acreditan 4/4 y 16/16 pruebas correctas.
**Segunda corrección automática no observada**. Hubo una incidencia interna
en la sesión del desarrollador del caso 02, descrita más abajo, aunque las
etapas del controlador finalizaron correctamente.

## Fuentes y alcance de la comprobación

El [protocolo original congelado][protocolo-congelado] fijó una ejecución por
caso, en orden y sin concurrencia, con un máximo de dos intentos y cuatro
invocaciones por ejecución. La [preparación][preparacion] conserva las fuentes
efectivas y las comprobaciones anteriores. Se siguieron las rutas explícitas
de `intentos[0].reparacion.registro` e `intentos[0].revision.registro` de cada
resumen general; no se seleccionaron etapas por fecha o semejanza de nombres.

| Caso | Registro general | Reparación enlazada | Revisión enlazada | Salida de terminal |
| --- | --- | --- | --- | --- |
| `case_01` | [resultado.json][g01] | [resultado.json][r01] | [resultado.json][v01] | [stdout][terminal01] |
| `case_02` | [resultado.json][g02] | [resultado.json][r02] | [resultado.json][v02] | [stdout][terminal02] |

Antes de modificar documentación se comprobó lo siguiente:

- Rama `feat/orquestacion-multicaso`, revisión
  `deb475b0b2f06f8a613016aec057730ce2b4b723`. Rama, revisión, `git status --short`
  y `git diff --binary HEAD` coincidían byte a byte con la preparación. El
  árbol ya contenía cambios sin commit: la revisión Git por sí sola no
  identifica la implementación usada.
- Las **21 fuentes** actuales coincidían byte a byte con `fuentes/` y con
  `fuentes.sha256.json`. Se incluyen los cuatro archivos no versionados:
  `case_config.py`, `evals/protocolo-multicaso.md`,
  `prompts/reviewer_case_01.md` y `tests/test_multicase.py`.
- Los **36 archivos** enumerados en `evidencia.sha256.json` conservaban sus
  hashes; también coincidían los seis logs de comprobaciones previas con
  `comprobaciones_previas/origenes.sha256.json`. El manifiesto de preparación
  no incluye las salidas de terminal añadidas después de preparar el experimento.
- Cada resumen general conservaba exactamente el inventario y los SHA-256
  de **33 archivos de reparación y 24 de revisión**: **114 archivos** entre
  ambos casos, sin faltantes ni archivos adicionales en esas etapas. Los
  resúmenes de etapas embebidos coincidían con sus respectivos `resultado.json`.
- Se contrastaron contratos, originales, pruebas, partida, candidatos, los
  tres diffs, feedback, informes, prompts enviados, materiales del revisor y
  respuestas originales con los dictámenes validados. Se leyeron completos
  los cuatro archivos `eventos.jsonl`.

Se recalcularon hashes e inventarios y se aplicaron las validaciones de solo
lectura `validate_repair` y `validate_review_record`. Además, se contaron las
filas de los informes y se contrastaron los identificadores mediante AST,
sin importar `solution` ni `test_solution`. No se ejecutó la suite para hacer
esta auditoría. No se detectó mezcla de contratos, pruebas o candidatos entre
casos: las referencias de cada etapa coinciden con las del caso declarado y
las copias evaluadas y revisadas contienen los mismos bytes del candidato.

## Resultados verificados

Los recuentos proceden de las filas y cierres completos de los informes
`inicial/stderr.txt` y `posterior/stderr.txt`, contrastados con las pruebas de
referencia. Los cuatro `stdout.txt` de evaluación están vacíos. Los códigos
de salida se comprobaron por separado; no se usaron para deducir los recuentos.

| Observación | `case_01` | `case_02` |
| --- | --- | --- |
| Contrato | Suma por asignatura, sin versión declarada (`null`) | Clasificación de ejecución, versión 2 |
| Funcionamiento del controlador | Conforme en el recorrido observado | Conforme en el recorrido observado |
| Evaluación inicial | 4 pruebas: 3 correctas, 1 fallo de aserción, 0 errores, 0 omisiones; código 1 | 16 pruebas: 9 correctas, 7 fallos de aserción, 0 errores, 0 omisiones; código 1 |
| Evaluación posterior independiente | 4 pruebas: 4 correctas, 0 fallos, 0 errores, 0 omisiones; código 0 | 16 pruebas: 16 correctas, 0 fallos, 0 errores, 0 omisiones; código 0 |
| Criterio de pruebas del candidato | `superadas` | `superadas` |
| Dictamen válido del revisor | `aprobar`, `hallazgos: []` | `aprobar`, `hallazgos: []` |
| Decisión del controlador de revisión | `aprobada`, código 0 | `aprobada`, código 0 |
| Resultado general | `estado: aprobada`, `aprobada: true`, código 0 | `estado: aprobada`, `aprobada: true`, código 0 |
| Intentos iniciados / máximo | 1 / 2 | 1 / 2 |
| Invocaciones por rol | Desarrollador 1; revisor 1 | Desarrollador 1; revisor 1 |
| Invocaciones totales / máximo | 2 / 4 | 2 / 4 |
| Integridad registrada y contrastada | 4 comprobaciones generales, 9 de reparación y 6 de revisión: todas `true` | 4 comprobaciones generales, 9 de reparación y 6 de revisión: todas `true` |
| Inicio y fin UTC, 15/10/2026 | 17:42:36.378387–17:43:33.480195 | 18:25:00.868031–18:26:02.574258 |
| Duración general monotónica | 57,102 s | 61,706 s |
| Duración de reparación / revisión, con preparación de cada etapa | 30,442 s / 26,608 s | 30,801 s / 30,872 s |
| Duración de `codex exec`, desarrollador / revisor | 29,966 s / 26,456 s | 30,524 s / 30,760 s |
| Evaluaciones independientes inicial / posterior, duración del proceso | 0,065 s / 0,065 s | 0,064 s / 0,065 s |
| Segunda corrección automática | No observada | No observada |

Las duraciones se redondean a milisegundos; los JSON conservan su precisión
original. Las marcas UTC son coherentes con las duraciones monotónicas y
acreditan que el caso 01 terminó antes de comenzar el caso 02. En Europe/Madrid,
los intervalos son aproximadamente 19:42:36–19:43:33 y 20:25:00–20:26:02 CEST.
Las duraciones de proceso incluyen más trabajo que el tiempo que imprime
`unittest` en su línea `Ran`; no se confunden ambas mediciones.

Los dos `case_*.stdout.txt` de la preparación coinciden con los resúmenes:
`Estado: aprobada`, `Intentos: 1/2`, `Invocaciones: 2/4` y la ruta general
correspondiente. Sus `case_*.stderr.txt` están vacíos y sus `case_*.codigo.txt`
contienen `0`. Las marcas `case_01.lanzamiento/` y `case_02.lanzamiento/` existen.
El comando externo completo escrito en la terminal **no consta** en esos
archivos; los presupuestos del resumen y los comandos de cada proceso interno
sí están conservados. Los comandos del protocolo son instrucciones previas,
no una transcripción del historial de la terminal.

## Identidad y resultados de las pruebas

La referencia del caso 01 declara cuatro métodos de
`test_solution.TestCalcularTotalesPorAsignatura`. La del caso 02 declara dieciséis
de `test_solution.TestClasificarEjecucion`. Los informes inicial y posterior
contienen exactamente esos identificadores, una vez cada uno, con totales
`Ran 4 tests` y `Ran 16 tests`, respectivamente. No hay errores de importación,
pruebas omitidas ni cierres incompletos. `FAIL` designa una aserción fallida.

| Caso 01: método | Inicial | Posterior |
| --- | --- | --- |
| `test_acumulacion_asignatura_repetida` | FAIL | ok |
| `test_dos_asignaturas_distintas` | ok | ok |
| `test_entrada_permanece_intacta` | ok | ok |
| `test_lista_vacia` | ok | ok |

El fallo inicial compara 15 minutos de Python con los 35 esperados: el
original conserva la última sesión en vez de sumar ambas. El cierre es
`FAILED (failures=1)`; el posterior es `OK`.

| Caso 02: método | Inicial | Posterior |
| --- | --- | --- |
| `test_codigo_cero_y_cadena_vacia` | FAIL | ok |
| `test_codigo_cero_y_combinacion_de_espacios_en_blanco` | FAIL | ok |
| `test_codigo_cero_y_espacio_no_separable_unicode` | FAIL | ok |
| `test_codigo_cero_y_espacios_y_saltos_de_linea` | FAIL | ok |
| `test_codigo_cero_y_respuesta_none` | FAIL | ok |
| `test_codigo_cero_y_retorno_de_carro` | FAIL | ok |
| `test_codigo_cero_y_tabuladores` | FAIL | ok |
| `test_codigo_cero_y_texto_rodeado_de_espacios_en_blanco` | ok | ok |
| `test_codigo_cero_y_texto_valido` | ok | ok |
| `test_codigo_distinto_de_cero_prevalece_sobre_espacios_en_blanco` | ok | ok |
| `test_codigo_distinto_de_cero_y_respuesta_vacia` | ok | ok |
| `test_codigo_distinto_de_cero_y_texto_presente` | ok | ok |
| `test_codigo_none_sin_tiempo_agotado` | ok | ok |
| `test_tiempo_agotado_prevalece_con_codigo_cero_y_espacios_en_blanco` | ok | ok |
| `test_tiempo_agotado_prevalece_con_codigo_cero_y_texto` | ok | ok |
| `test_tiempo_agotado_prevalece_sobre_fallo_y_espacios_en_blanco` | ok | ok |

Los siete diagnósticos iniciales son `AssertionError`: se obtiene `completada`
en lugar de `respuesta_vacia`. El cierre es `FAILED (failures=7)`; el posterior
es `OK`. Se leyeron los [informes inicial y posterior del caso 01][informes01]
y los [del caso 02][informes02], incluidas las trazas completas.

## Contraste estático de candidatos y dictámenes

En el [candidato del caso 01][candidato01], el diff sustituye la sobrescritura
por `totales[asignatura] = totales.get(asignatura, 0) + sesion["minutos"]` y
actualiza la documentación del defecto inicial. Cada sesión añade sus minutos
al total previo; la cadena de asignatura se usa directamente como clave, sin
normalización, por lo que nombres que difieren en mayúsculas no se combinan.
La lista vacía deja el diccionario nuevo vacío. Solo se escribe en ese nuevo
diccionario: no se altera la lista ni sus diccionarios, incluso si una misma
referencia aparece varias veces. No hay entrada/salida ni dependencias externas.
Esto es coherente con el contrato para sus entradas válidas.

El dictamen del caso 01 afirma haber valorado acumulación, comparación exacta,
vacío, conservación de la entrada y ausencia de entrada/salida, incluidas
repeticiones múltiples y referencias repetidas. No formula hallazgos. Esta
lectura automática no identifica una contradicción concreta entre el candidato
y ese dictamen. Los eventos acreditan qué leyó el revisor; no acreditan por sí
solos todas las comprobaciones mentales que afirma haber hecho. Las cuatro
pruebas no ejercitan por separado la comparación entre nombres que solo
difieren en mayúsculas: ese punto se sostiene aquí mediante lectura estática.

El [candidato del caso 02][candidato02] conserva primero la prioridad de
`tiempo_agotado`, después `codigo_salida is None or codigo_salida != 0`, y añade
la condición `respuesta is None or respuesta == "" or respuesta.isspace()`
para devolver `respuesta_vacia`. El cortocircuito evita llamar a `isspace()`
sobre `None`; una cadena con algún carácter que no sea blanco llega a
`completada`. Conserva el valor predeterminado `False` y la pureza de la
función. Para los tipos admitidos no se identifica incumplimiento de versión 2.
El dictamen `aprobar`, sin hallazgos, es coherente con esa lectura; no supone
garantía de corrección general ni de comportamiento fuera del contrato.

En ambos casos, `partida.py` coincide con el original defectuoso,
`procedencia` es `{"tipo": "benchmark"}`, `feedback.json` contiene `null`
y `partida.diff` está vacío. `candidato.diff` y `correccion.diff` corresponden
exactamente al cambio entregado. Que exista un archivo `correccion.diff` no
demuestra un segundo intento: no hay candidato previo de otro intento ni
feedback de revisión que motive una nueva invocación. La continuidad observada
abarca original, partida, evaluación inicial, candidato, evaluación posterior
y materiales de revisión; la continuidad entre dos intentos no se ejercitó.

SHA-256 recalculados durante la auditoría:

| Archivo | `case_01` | `case_02` |
| --- | --- | --- |
| `candidato.py` | `763ba5e11c06ad3077048f05d1d1983858f113189b185884cdc4dbb108346ec1` | `7d3d635fbc248020f69cb15b1cc9050f1be4ca2ede558969068ba313d94fd03d` |
| `resultado.json` general | `617b0555621fd309061452464e597a55bc0e2f0b0d3dbc3ff0a35b25d85ebfb5` | `fb8c155cb6828b06140939b771ccc1a06bea74d1889ed64b602df807fb4d79fb` |

Los hashes de candidatos coinciden con los guardados en reparación y revisión.
Los hashes generales anteriores son una referencia de esta auditoría, no una
firma o autenticación externa. Los hashes de contratos, pruebas, originales,
prompts y archivos de etapas permanecen en los manifiestos y JSON enlazados.

## Acciones registradas, presupuesto y configuración

Cada archivo de eventos contiene un `thread.started`, un `turn.started` y un
`turn.completed`, con cuatro identificadores de sesión distintos. Los procesos
`codex exec` tienen `invocaciones: 1`, estado `finalizada` y código 0. No hay
reanudación ni delegación registrada. Las consultas locales de versión y ayuda
no se contabilizan como llamadas al modelo.

| Sesión | Eventos JSONL | Comandos internos terminados | Ediciones registradas |
| --- | --- | --- | --- |
| Desarrollador 01 | 15 | 4, todos con código 0 | Una actualización de `solution.py` |
| Revisor 01 | 15 | 5, todos con código 0 | Ninguna |
| Desarrollador 02 | 17 | 5: cuatro con código 0 y uno con código 127 | Una actualización de `solution.py` |
| Revisor 02 | 17 | 6, todos con código 0 | Ninguna |

Los desarrolladores leyeron implementación y pruebas, editaron la copia de
`solution.py` y ejecutaron sus propias pruebas. En los [eventos del caso 02][eventos-dev02],
`item_5` intenta `python -B -m unittest -v test_solution.py` y termina con
**código 127**, `python: command not found`. `item_6` usa después
`python3 -B -m unittest -v test_solution.py`, con 16 pruebas correctas y código 0.
Se conserva el fallo: es una incidencia técnica de una herramienta dentro
de una misma sesión, no una segunda invocación del desarrollador, otro intento
del orquestador ni una segunda corrección del candidato. Tampoco acredita una
detención del controlador ante un fallo técnico de etapa. El proceso Codex y
la evaluación independiente posterior terminaron correctamente.

Los [eventos del revisor 01][eventos-rev01] y [del revisor 02][eventos-rev02]
registran localización y lectura de materiales con `pwd`, `rg`, `cat` y, en el
caso 02, `nl`. Incluyen contrato, original, candidato, diff, pruebas, informe
posterior y esquema de respuesta. No registran ejecución del candidato,
pruebas, escrituras, navegación ni delegación. Las respuestas originales,
los mensajes finales de los eventos y los dictámenes validados coinciden.
Las explicaciones de los agentes se distinguen de estas acciones observadas
y de las evaluaciones independientes del controlador.

En ambos resúmenes la transición de desarrollo es `revisar`, motivada por
`supera_las_pruebas_disponibles`, y la transición de revisión es `aprobar`,
motivada por `revision_aprobada`. No hay transición `corregir`. Se consumieron
2 de las 4 invocaciones disponibles por ejecución: 4 de las 8 máximas conjuntas,
sin transferencia de presupuesto. No hay intentos agotados, etapas incompletas,
timeouts ni errores del controlador registrados. La incidencia interna anterior
impide describir toda la actividad como libre de fallos técnicos.

Los límites registrados son 180 s por agente, 30 s por evaluación y 10 s por
consulta de versión o ayuda. Todos esos procesos terminaron dentro de su límite;
las consultas locales terminaron con código 0. No existe timeout global adicional.
Las evaluaciones independientes usaron `/usr/bin/python3 -B -m unittest discover`,
cada una en su propio proceso y directorio, con `-p test_solution.py -v`.

| Dato | Evidencia disponible |
| --- | --- |
| Codex CLI | `codex-cli 0.162.1` en los cuatro `codex_version.txt`, idénticos a sus `version/stdout.txt`; ayuda conservada por cada etapa. |
| Modelo efectivo, proveedor, esfuerzo de razonamiento | **No consta**, para ninguno de los cuatro agentes. No hay selección explícita de modelo en sus comandos ni identificación en los eventos conservados. |
| Python y sistema en la preparación | `entorno.json`: Python 3.12.3, GCC 13.3.0, `/usr/bin/python3`, `Linux-7.0.0-38-generic-x86_64-with-glibc2.39`. |
| Versión de Python y sistema reidentificados al lanzar cada caso | **No consta**. Los comandos acreditan `/usr/bin/python3`, pero no una nueva captura de su versión o del entorno completo de la terminal. |
| Ruta de Codex en la preparación | `/home/alvaarosalvador/.nvm/versions/node/v24.12.0/bin/codex`; los procesos registrados invocan `codex` mediante PATH. La resolución absoluta de PATH durante cada lanzamiento **no consta**. |
| Configuración registrada en las cuatro invocaciones | `approval_policy="never"`, `web_search="disabled"`, `features.multi_agent=false`, `--ephemeral`, `--json`, `--skip-git-repo-check`, `--cd` y archivo de respuesta final. |
| Desarrolladores | `--sandbox workspace-write`; `sandbox_workspace_write.writable_roots=[]`, `network_access=false`, `exclude_slash_tmp=true`, `exclude_tmpdir_env_var=true`. |
| Revisores | `--sandbox read-only`, `--output-schema` con el esquema conservado. |
| Configuración adicional de usuario y mecanismo de autenticación | **No consta**; no se han leído ni copiado credenciales. |

Las opciones registradas son iguales entre casos para cada rol, salvo las
rutas temporales. Esto no permite afirmar que el modelo o toda la configuración
efectiva fueran iguales, ni demuestra aislamiento de seguridad: los eventos
y las comprobaciones de integridad observan las acciones registradas y el
estado conservado, y los hashes no autentican una falsificación consistente.

## Comprobaciones previas y límites de la conclusión

Se reutiliza el [log de regresión anterior][regresion]: **108 pruebas correctas
en 39,797 s**, con Codex simulado. Sus 108 filas y cierre `OK` se han leído;
el código 0 está documentado en las notas de preparación. Las comprobaciones
específicas previas de 42 pruebas de orquestación y 8 de evidencia multicaso
forman parte de esa regresión, no son nuevas ejecuciones reales. No se han
sumado a las 4 y 16 pruebas de candidatos observadas aquí ni se ha repetido
ninguna comprobación con ejecución de pruebas durante esta auditoría.

La evidencia permite concluir que el controlador funcionó de forma coherente
en estos dos recorridos de aprobación inicial, que ambos candidatos superaron
sus pruebas disponibles y que recibieron dictámenes válidos de aprobación,
coherentes con esta lectura estática. Son tres criterios separados. No se
detectaron discrepancias de hashes, identidad de pruebas, candidatos, recuentos,
transiciones o presupuestos. La incidencia `python`/127 permanece registrada;
las ausencias de configuración y de transcripción del comando externo limitan
la reproducción exacta del entorno.

**Dos casos pequeños no permiten medir fiabilidad general**, estimar una tasa
de éxito representativa ni comparar modelos. La aprobación tampoco garantiza
corrección general. El caso 01 contiene pistas explícitas del defecto en el
contrato, el docstring y un comentario del original; el desarrollador las
recibió. Su reparación no mide diagnóstico ciego. Además, la comparación
exacta de nombres tiene cobertura estática aquí, sin una prueba específica
de diferencias de mayúsculas en la referencia.

Quedan sin observar con estas ejecuciones la segunda corrección automática,
la continuidad entre intentos, la respuesta del controlador a un dictamen
`solicitar_cambios`, el agotamiento y las detenciones por fallos técnicos o
evidencia cruzada. Su cobertura simulada no se convierte en evidencia real.
La lectura humana prevista por el protocolo sigue sin constar. No se propone
repetir los casos para obtener otro resultado ni completar esos recorridos.

## Documentación posterior al experimento

Este informe, la actualización breve del README y la nota de enlace añadida al
[protocolo actual](protocolo-multicaso.md) son cambios documentales posteriores.
Las copias congeladas de README y protocolo en `fuentes/` se conservan intactas:
su estado «pendiente» describe el momento de preparación. También se mantiene
`notas.md` de la preparación sin actualizar sus resultados retrospectivamente.
Los resultados completos se documentan aquí; no se reescriben los registros
para sustituir sus estados históricos. La tabla pendiente original del protocolo
se conserva como parte del diseño previo, junto con sus criterios y presupuestos.

Código, contratos, pruebas, prompts, benchmark, informe histórico y todos los
archivos de `runs/` se conservan. La comprobación final confirma que, de los
403 archivos previos, solo cambiaron README y protocolo; se añadió este informe.
Los 380 archivos y 104 directorios de `runs/` permanecen intactos. Se comprobó
que el protocolo original se recupera exactamente retirando la nota posterior.
`git diff --check` terminó sin errores y los 34 enlaces locales de los tres
documentos son válidos. Estas comprobaciones no ejecutaron agentes ni pruebas.
Los enlaces a `runs/` necesitan la evidencia local, que está excluida de Git.

[preparacion]: ../runs/protocolo-multicaso-DelwGYlP/
[protocolo-congelado]: ../runs/protocolo-multicaso-DelwGYlP/fuentes/evals/protocolo-multicaso.md
[regresion]: ../runs/protocolo-multicaso-DelwGYlP/comprobaciones_previas/multicaso-regresion.log
[terminal01]: ../runs/protocolo-multicaso-DelwGYlP/case_01.stdout.txt
[terminal02]: ../runs/protocolo-multicaso-DelwGYlP/case_02.stdout.txt
[g01]: ../runs/20261015T174236378387Z_case_01_orchestrate_8faa907f95424bfbb9dd01b7fe60f1cd/resultado.json
[r01]: ../runs/20261015T174236380803Z_case_01_repair_42506b2a1f2649efb85ef5e0521a9133/resultado.json
[v01]: ../runs/20261015T174306843216Z_case_01_review_2de8f8da2314474aa7e7946efe1691fc/resultado.json
[g02]: ../runs/20261015T182500868031Z_case_02_orchestrate_d790f02d507e44129aaf67a05a04c404/resultado.json
[r02]: ../runs/20261015T182500869636Z_case_02_repair_b6692f2af3944f8a86a19c8c45249177/resultado.json
[v02]: ../runs/20261015T182531684479Z_case_02_review_8d52598b457e4ef6a02b7bc926c32fe4/resultado.json
[informes01]: ../runs/20261015T174236380803Z_case_01_repair_42506b2a1f2649efb85ef5e0521a9133/
[informes02]: ../runs/20261015T182500869636Z_case_02_repair_b6692f2af3944f8a86a19c8c45249177/
[candidato01]: ../runs/20261015T174236380803Z_case_01_repair_42506b2a1f2649efb85ef5e0521a9133/candidato.py
[candidato02]: ../runs/20261015T182500869636Z_case_02_repair_b6692f2af3944f8a86a19c8c45249177/candidato.py
[eventos-dev02]: ../runs/20261015T182500869636Z_case_02_repair_b6692f2af3944f8a86a19c8c45249177/agente/eventos.jsonl
[eventos-rev01]: ../runs/20261015T174306843216Z_case_01_review_2de8f8da2314474aa7e7946efe1691fc/revisor/eventos.jsonl
[eventos-rev02]: ../runs/20261015T182531684479Z_case_02_review_8d52598b457e4ef6a02b7bc926c32fe4/revisor/eventos.jsonl

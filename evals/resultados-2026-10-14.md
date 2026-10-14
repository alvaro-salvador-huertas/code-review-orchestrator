# Resultados del caso 02 — 14 de octubre de 2026

La nueva reparación con contrato de versión 2 pasó de **9 pruebas correctas y
7 fallidas a 16 correctas**. Una revisión independiente emitió **`aprobar`, sin
hallazgos**; el controlador registró **`aprobada`, código 0**. Las dos etapas
se lanzaron manualmente con comandos separados. La evidencia permite cerrar
este hito de desarrollo y revisión para el caso 02, sin demostrar fiabilidad
general ni constituir un ciclo automático de corrección.

Se conserva toda la secuencia anterior. El segundo intento real produjo el
primer candidato que **supera las pruebas disponibles de versión 1**: pasó
de cinco pruebas correctas y tres fallidas a ocho correctas.
El controlador lo aceptó con las siete comprobaciones de integridad positivas.
El primer intento se conserva: Codex falló al inicializarse por un error de
sistema de archivos de solo lectura y dejó la implementación sin cambios.

Una revisión posterior de esa reparación solicitó cambios por la interpretación
de los espacios en blanco. El usuario aclaró el contrato como versión 2, y una
reevaluación local del mismo candidato superó las 16 pruebas nuevas y existentes.
Son evidencias distintas de la nueva reparación y revisión de versión 2.
El dictamen de versión 1 sigue siendo `solicitar_cambios`.

Este informe corresponde a la rama `feat/agente-desarrollador`. Su versión
inicial era documental; una ampliación previa incluyó la suite de 57 pruebas
del controlador y una reevaluación local. Este cierre solo lee y contrasta los
registros posteriores: no repite pruebas ni hace llamadas al modelo. Ningún
candidato se aplicó a `benchmark/case_02/solution.py`, que conserva su defecto.

## Fuentes y alcance de la evidencia

Se leyeron los resúmenes JSON generales y de cada proceso, las salidas de pruebas,
los errores y eventos del agente, su respuesta final, las referencias, los
candidatos y sus diffs. Se contrastaron los hashes SHA-256 con las copias
conservadas y, para versión 2, con los originales actuales; se verificó que
los diffs guardados corresponden a esas copias.

| Etapa | Directorio local bajo `runs/` | Inicio UTC | Inicio Europe/Madrid |
| --- | --- | --- | --- |
| 1 — reparación v1 | `20261014T094643807324Z_case_02_repair_a9aa41d08571475a8b4a35c9f4329392` | 2026-10-14 09:46:43.807324Z | 14/10/2026 11:46:43 |
| 2 — reparación v1 | `20261014T095901094866Z_case_02_repair_0cadfee826344e2b9d8aa00b5ce4e289` | 2026-10-14 09:59:01.094866Z | 14/10/2026 11:59:01 |
| Revisión v1 | `20261014T103340644225Z_case_02_review_997b002f363c46cb94c2ce362f0db416` | 2026-10-14 10:33:40.644225Z | 14/10/2026 12:33:40 |
| Reevaluación local v2 | `20261014T104559983435Z_case_02_reevaluacion_local_v2_318ba7c432cd4c3f807be871ca4ef3c4` | 2026-10-14 10:45:59.983435Z | 14/10/2026 12:45:59 |
| 3 — reparación v2 | `20261014T105547244465Z_case_02_repair_1bd0e59ca7654489ba7f455fa6e03929` | 2026-10-14 10:55:47.244465Z | 14/10/2026 12:55:47 |
| Revisión v2 | `20261014T105754354270Z_case_02_review_2b4d717cb28e4b91adcf5b4ae462651e` | 2026-10-14 10:57:54.354270Z | 14/10/2026 12:57:54 |

El usuario indica que el segundo intento fue lanzado manualmente desde la
terminal. Los registros confirman una ejecución separada, con su propio
directorio y una invocación de Codex; no registran quién la lanzó ni los permisos
efectivos del proceso padre. Esa procedencia manual se atribuye al usuario.

Los registros completos permanecen locales y excluidos de Git. Este informe
incluye los resultados y el cambio exacto para poder revisarlos sin esos archivos.
El flujo y los códigos de salida están documentados en el [README](../README.md).

## Ejecuciones de reparación bajo versión 1

| Tipo | Evidencia y alcance |
| --- | --- |
| Pruebas automatizadas del controlador | La validación previa del hito terminó con 30 pruebas correctas: 14 de `run_case.py` y 16 de `repair_case.py`, código 0. Las pruebas de reparación usan una CLI simulada, sin modelo. Esa validación corresponde a la fase previa; la ampliación a versión 2 se valida por separado más adelante. Los dos registros de reparación no contienen la salida de esa suite. |
| Pruebas del caso 02, versión 1 | Son ocho pruebas de referencia. El controlador las ejecutó antes y después en cada intento: cuatro evaluaciones independientes, siempre sobre copias. No son evaluaciones de versión 2. |
| Invocaciones reales de Codex para reparar | Dos procesos `codex exec`, uno por intento. El primero falló al inicializarse; el segundo produjo una sesión con acciones y respuesta final. Más adelante hubo una invocación distinta para revisar, documentada por separado. El número de procesos no permite contar solicitudes internas al modelo. `--version` y `exec --help` son comprobaciones locales, no llamadas al modelo. |

No hubo reintentos automáticos del controlador dentro de ninguna de las dos
ejecuciones. Varias acciones internas del agente pertenecen a la misma sesión.

## Resultado de ambos intentos

Ambos registran `codex-cli 0.162.1`, un límite de 180 segundos para el agente y
de 30 segundos para cada evaluación. Los comandos de Codex conservan los mismos
argumentos de configuración; cambian las rutas temporales. Incluyen
`workspace-write`, aprobaciones `never`, búsqueda web desactivada y delegación
desactivada, sin añadir raíces de escritura sobre el repositorio original.

| Dato del resumen | Intento 1 | Intento 2 |
| --- | --- | --- |
| Estado del proceso Codex | `finalizada` | `finalizada` |
| Código del proceso Codex | 1 | 0 |
| Duración de Codex | 0,466 s | 28,567 s |
| Invocaciones de reparación | 1 | 1 |
| Respuesta final disponible | `false` | `true` |
| Eventos JSONL | Archivo vacío | Sesión iniciada y turno completado; edición y comandos registrados |
| Errores del agente, stderr | 570 bytes; error de inicialización y avisos | Vacío, 0 bytes |
| Estado del controlador | `fallo_agente` | `supera_las_pruebas_disponibles` |
| Código del controlador | 3 | 0 |
| `aceptada` | `false` | `true` |
| Errores del controlador | Lista vacía | Lista vacía |
| Integridad | 7 de 7 comprobaciones positivas | 7 de 7 comprobaciones positivas |
| Duración total | 0,733 s | 28,801 s |

`finalizada` indica que el proceso terminó; no implica que reparase el caso.
La aceptación del segundo intento depende también de la integridad y del
resultado de la evaluación independiente.

### Primer intento: fallo de inicialización

El archivo de errores registra:

```text
Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
```

También aparecen un aviso al crear alias de PATH y errores al depurar o hacer
checkpoint de los registros de diagnóstico en una base de datos de solo lectura.
Los archivos de eventos y respuesta final están vacíos. No hay trabajo del
agente registrado; el candidato coincide byte a byte con la implementación
inicial y su diff tiene **0 bytes**. Las pruebas posteriores siguen fallando.

Esto demuestra un fallo de inicialización asociado a operaciones de escritura
rechazadas por solo lectura. **No identifica la causa concreta del entorno que
impuso esa restricción ni la ruta causante del error fatal.** Atribuirlo al
sandbox o a los permisos del entorno desde el que se lanzó es una hipótesis.
Que la segunda ejecución manual tenga éxito no aísla esa causa; no se dispone
de una comparación controlada de permisos ni de evidencia adicional concluyente.

### Segundo intento: candidato aceptado

Los eventos muestran lectura de `solution.py` y `test_solution.py`, una edición
de `solution.py` y una respuesta final. El agente intentó ejecutar las pruebas
con `python`, que no estaba disponible (código 127), y después con
`python3 -B -m unittest -v test_solution.py`, que terminó con ocho pruebas
correctas y código 0. Ambas acciones pertenecen a la misma sesión de Codex;
no constituyen nuevas invocaciones de reparación del controlador.

La respuesta final del agente afirma que corrigió únicamente `solution.py` y
que las ocho pruebas pasan. La evidencia de aceptación es la evaluación
posterior del controlador, en otro proceso y con sus pruebas de referencia,
no esa afirmación ni solo el código cero de Codex.

## Pruebas del caso antes y después

| Intento | Evaluación del controlador | Ejecutadas | Correctas | Fallidas | Código |
| --- | --- | --- | --- | --- | --- |
| 1 | Inicial | 8 | 5 | 3 | 1 |
| 1 | Posterior | 8 | 5 | 3 | 1 |
| 2 | Inicial | 8 | 5 | 3 | 1 |
| 2 | Posterior | 8 | 8 | 0 | 0 |

Las tres evaluaciones fallidas terminan con `FAILED (failures=3)`; la posterior
del segundo intento termina con `Ran 8 tests` y `OK`. No se registran errores
de importación ni tiempos agotados en esas evaluaciones.

| Prueba de referencia | Inicial en ambos intentos y posterior del primero | Posterior del segundo |
| --- | --- | --- |
| `test_codigo_cero_y_cadena_vacia` | Falla | Pasa |
| `test_codigo_cero_y_espacios_y_saltos_de_linea` | Falla | Pasa |
| `test_codigo_cero_y_respuesta_none` | Falla | Pasa |
| `test_codigo_cero_y_texto_valido` | Pasa | Pasa |
| `test_codigo_distinto_de_cero_y_respuesta_vacia` | Pasa | Pasa |
| `test_codigo_distinto_de_cero_y_texto_presente` | Pasa | Pasa |
| `test_codigo_none_sin_tiempo_agotado` | Pasa | Pasa |
| `test_tiempo_agotado_prevalece_con_codigo_cero_y_texto` | Pasa | Pasa |

En los tres fallos se obtenía `"completada"` en lugar de `"respuesta_vacia"`.

## Cambio exacto del candidato satisfactorio

Este es el contenido completo del diff del segundo intento, contrastado con
las copias inicial y candidata:

```diff
--- inicial/solution.py
+++ candidato/solution.py
@@ -3,4 +3,6 @@
         return "tiempo_agotado"
     if codigo_salida is None or codigo_salida != 0:
         return "fallo_ejecucion"
+    if respuesta is None or not respuesta.strip():
+        return "respuesta_vacia"
     return "completada"
```

La condición se evalúa después de descartar tiempo agotado y fallo de ejecución,
por lo que conserva sus prioridades. `respuesta is None` activa el cortocircuito
del `or` y evita llamar a `strip()` sobre `None`. Para cadenas, `strip()` elimina
los espacios en blanco de los extremos; una cadena vacía o compuesta únicamente
por espacios en blanco, incluidos saltos de línea, queda vacía y `not` resulta
verdadero. Si queda texto, se conserva `"completada"`.

El cambio superó las ocho pruebas conservadas con el contrato de versión 1.
Esa redacción no precisaba si los tabuladores estaban incluidos y motivó el
hallazgo posterior. El [contrato actual del caso 02](../tasks/002-classify-run.md)
es la versión 2; no debe usarse para reinterpretar el dictamen histórico.
La [implementación original](../benchmark/case_02/solution.py)
conserva el defecto: no se reemplazó por el candidato.

## Integridad y conservación

Los dos resúmenes registran `true` para `pruebas_agente_intactas`,
`originales_intactos`, `referencia_intacta`,
`pruebas_iniciales_pruebas_intactas`, `pruebas_iniciales_implementacion_intacta`,
`pruebas_posteriores_pruebas_intactas` y
`pruebas_posteriores_implementacion_intacta`.

La comprobación documental de los archivos confirma que las referencias guardadas de
ambos intentos coinciden; las pruebas entregadas al agente y las de las copias
de evaluación mantienen los mismos bytes. Los seis archivos originales de
`benchmark/` y `tasks/` coincidían con los hashes registrados antes de la
aclaración. Ahora el contrato y las pruebas actuales han cambiado a versión 2;
las implementaciones y las referencias históricas no se modificaron.
Las copias evaluadas corresponden a la implementación inicial y al candidato
respectivo. Los JSON de cada proceso coinciden con el resumen general.

| Archivo o contenido | SHA-256 verificado |
| --- | --- |
| Implementación inicial del caso 02 y candidato del intento 1 | `4c373f13f90ef6c25d10aa71bbbfcd2235ea72f7839b9d5041a408cd94618cea` |
| Candidato del intento 2 | `0f76797fafdd4857ac80369b0c6a4f4d6529bd9a61f45717858b4a99c1f165cb` |
| Pruebas de referencia del caso 02, versión 1 | `be3969fb52dcf9b8c6cae0ce6cabec7433306f82ca514989f1b6b98a98621d1e` |
| Contrato del caso 02, versión 1 | `a18d05a7708801eabde9f2da5137cf04d9254f0592677e560a01c1df13c0f3f5` |

Los registros de ambos intentos se conservan íntegros bajo `runs/`; la regla
`/runs/` de [.gitignore](../.gitignore) evita incluirlos en Git. El informe
documenta el éxito y el fallo sin sustituir ninguno de los registros.

## Revisión real de la reparación de versión 1

Registro conservado:
`runs/20261014T103340644225Z_case_02_review_997b002f363c46cb94c2ce362f0db416`.
Revisa el candidato del segundo intento de reparación, con su contrato y sus
ocho pruebas de versión 1. No es una revisión del contrato de versión 2.

| Dato | Resultado registrado |
| --- | --- |
| Inicio | 2026-10-14 10:33:40.644225 UTC; 12:33:40 Europe/Madrid |
| Versión de Codex | `codex-cli 0.162.1` |
| Invocaciones del revisor | 1, sesión nueva con sandbox `read-only` |
| Estado y código del proceso | `finalizada`, 0 |
| Duración del proceso | 51,829 s |
| Dictamen del modelo | `solicitar_cambios` |
| Hallazgos | 1, en `candidato.py`, línea 6 |
| Decisión y código del controlador | `cambios_solicitados`, 1 |
| Aprobación | `aprobada: false` |
| Integridad | Las seis comprobaciones son `true` |
| Errores del controlador | Lista vacía |
| Stderr del revisor | Vacío |

El dictamen validado, la respuesta original y el resumen general coinciden.
Los hashes de los materiales coinciden con los archivos conservados y con el
inventario posterior. El manifiesto de origen coincide con el registro de
reparación. Los eventos muestran comandos de lectura (`pwd`, `rg`, `cat`, `nl`);
no registran ejecución del candidato ni de las pruebas.

El resumen del modelo fue:

> La prioridad y la pureza se respetan, pero la condición de respuesta vacía incluye caracteres adicionales a los especificados por el contrato.

Su hallazgo señalaba que `strip()` elimina también tabuladores. Para
`codigo_salida=0`, `respuesta="\t"` y `tiempo_agotado=False`, interpretó que
la versión 1 exigía `"completada"`, mientras que el código devolvería
`"respuesta_vacia"`. Esa lectura restringida de «espacios y saltos de línea»
motivó una aclaración funcional del usuario. **Se conserva el dictamen
`solicitar_cambios`; no se reclasifica retroactivamente como aprobación.**

## Decisión funcional y contrato de versión 2

La versión 1 no definía si «espacios» significaba solo el espacio ordinario o
todos los caracteres de espacio en blanco. El usuario decidió adoptar
`str.isspace()` de Python: con código cero, `None`, la cadena vacía y cualquier
cadena no vacía compuesta únicamente por esos caracteres producen
`"respuesta_vacia"`. Si hay algún carácter que no sea espacio en blanco, el
resultado es `"completada"`. Se conservan tipos admitidos, pureza y prioridades.

El contrato actual está marcado como **versión 2, 14 de octubre de 2026**.
La revisión no decidió esta política de producto: señaló una diferencia de
interpretación y el usuario resolvió la ambigüedad. El comportamiento para
`"\t"` queda ahora explícitamente definido como `"respuesta_vacia"`.

Las ocho pruebas de versión 1 se mantienen y se añaden estas ocho:

| Prueba nueva | Entrada representativa | Resultado exigido |
| --- | --- | --- |
| Tabuladores | Código 0, `"\t\t"` | `respuesta_vacia` |
| Retorno de carro | Código 0, `"\r\r"` | `respuesta_vacia` |
| Combinación de espacios en blanco | Código 0, `" \t\n\r\v\f "` | `respuesta_vacia` |
| Espacio no separable Unicode | Código 0, `"\u00a0"` | `respuesta_vacia` |
| Texto rodeado de espacios en blanco | Código 0, texto entre espacios, tabuladores, CR, LF y U+00A0 | `completada` |
| Prioridad de fallo | Código -1, `" \t\r\n\u00a0"` | `fallo_ejecucion` |
| Prioridad de timeout | Código 0, `"\t\r\u00a0"`, timeout | `tiempo_agotado` |
| Timeout sobre fallo | Código 1, `"\t\r\u00a0"`, timeout | `tiempo_agotado` |

`review_case.py` ya no exige exactamente ocho pruebas. Analiza el AST del
archivo de referencia conservado, sin importarlo, y contrasta número e
identificadores completos (módulo, clase y método) con las filas del informe.
Exige también un único resumen con ese total y un cierre correcto. Sigue
rechazando omisiones, duplicados, nombres desconocidos, clases incorrectas,
pruebas omitidas o fallidas e informes incompletos o contradictorios.

Se conservan las comprobaciones de hashes y la exigencia de que los originales
actuales coincidan con el registro. Por ello los registros de versión 1 no son
entradas aceptables para una nueva revisión con las referencias de versión 2.
No se han cambiado sus hashes ni sus contratos guardados para eludir esa regla.

## Validación y reevaluación local bajo versión 2

La suite del controlador terminó con **57 pruebas correctas y código 0**:
14 de ejecución inicial, 16 de reparación y 27 de revisión. Incluye los seis
tests añadidos para el recuento variable, informes incompletos u omitidos,
referencias vacías, cambios de contrato, identificación estática y referencias
inválidas o dinámicas. Las pruebas de agentes usan Codex simulado, sin modelo.
Este resultado sustituye como última validación a las 51 pruebas del hito previo;
no cambia los resultados históricos de las ocho pruebas del caso.

Después se hizo una **reevaluación local independiente**, el 14 de octubre
de 2026 a las 12:45:59 Europe/Madrid (10:45:59 UTC). Se copiaron a una carpeta
temporal fuera del repositorio el candidato del segundo intento, el contrato
de versión 2 y las 16 pruebas actuales. El proceso fue:

```text
/usr/bin/python3 -B -m unittest discover -s /tmp/case-02-reevaluacion-v2-sdly0us4 -p test_solution.py -v
```

| Dato | Reevaluación local |
| --- | --- |
| Versión del contrato usado | 2 |
| Procedencia del candidato | Reparación aceptada de versión 1, sin modificar su contenido |
| Pruebas ejecutadas | 16 |
| Correctas / fallidas | 16 / 0 |
| Código del proceso | 0 |
| Límite / duración del proceso | 30 s / 0,064 s |
| Integridad | Materiales temporales y registro de origen intactos |
| Llamadas al modelo | 0 |
| Dictamen nuevo del revisor | Ninguno |

El informe de unittest terminó con `Ran 16 tests` y `OK`. El candidato **supera
las pruebas disponibles de versión 2** en esta comprobación local. No se
atribuye ese resultado a la reparación antigua ni al revisor, ni equivale a
haber realizado una nueva reparación mediante agente.

La carpeta temporal se eliminó al terminar. El registro nuevo conserva
`materiales/`, `evaluacion/stdout.txt`, `evaluacion/stderr.txt`, el resultado
del proceso y un resumen con `tipo: reevaluacion_local`, versiones de origen y
destino, hashes y `llamadas_modelo: 0`:

```text
runs/20261014T104559983435Z_case_02_reevaluacion_local_v2_318ba7c432cd4c3f807be871ca4ef3c4/
```

| Material usado en la reevaluación | SHA-256 |
| --- | --- |
| Candidato sin cambios | `0f76797fafdd4857ac80369b0c6a4f4d6529bd9a61f45717858b4a99c1f165cb` |
| Pruebas de referencia de versión 2 | `c5fd3075772133bdd01972a634a22e1663bad2bf8fa6695a97ef43a6bd3761b3` |
| Contrato de versión 2 | `ecc5b162cdf2b78a85709f94f1386393e87ee83e2271085a9a933c2119262455` |

Los registros completos siguen excluidos de Git. Las dos reparaciones y la
revisión de versión 1 se conservaron sin modificaciones, al igual que la
implementación defectuosa inicial. Esta reevaluación no llamó al modelo.

## Nueva reparación y revisión reales de versión 2

El usuario lanzó manualmente las dos etapas desde la terminal, usando el
registro aceptado de la primera como entrada de la segunda:

```sh
python3 repair_case.py case_02
python3 review_case.py --run runs/20261014T105547244465Z_case_02_repair_1bd0e59ca7654489ba7f455fa6e03929
```

La reparación produjo el registro `20261014T105547244465Z_case_02_repair_1bd0e59ca7654489ba7f455fa6e03929`
y la revisión el registro `20261014T105754354270Z_case_02_review_2b4d717cb28e4b91adcf5b4ae462651e`.
El origen de la revisión referencia exactamente esa reparación y su inventario
de archivos. Los tiempos, directorios y sesiones son distintos. El lanzamiento
manual se atribuye al usuario; los registros no identifican al proceso padre.
El código ofrece dos entradas independientes: `repair_case.py` no llama a
`review_case.py`, y este no vuelve a invocar al desarrollador. No hubo un ciclo
automático ni una reparación adicional dentro de la revisión.

### Pruebas antes y después y cambio exacto

| Evaluación independiente del controlador | Ejecutadas | Correctas | Fallidas | Código | Duración del proceso |
| --- | --- | --- | --- | --- | --- |
| Inicial, implementación defectuosa | 16 | 9 | 7 | 1 | 0,065 s |
| Posterior, nuevo candidato | 16 | 16 | 0 | 0 | 0,065 s |

Ambos informes contienen los 16 identificadores de las pruebas conservadas,
sin omisiones ni duplicados. El inicial termina con `FAILED (failures=7)` y
el posterior con `OK`; sus códigos coinciden con los JSON individuales y el
resumen general. Los dos procesos terminaron dentro del límite de 30 segundos,
sin errores de importación. Sus archivos stdout están vacíos.

Fallaban las siete pruebas con código cero y respuesta vacía: cadena vacía,
`None`, espacios y saltos de línea, tabuladores, retorno de carro, combinación
de espacios en blanco y espacio no separable Unicode. Todas devolvían
`"completada"` en lugar de `"respuesta_vacia"`. Las otras nueve ya pasaban,
incluidas las prioridades y el texto rodeado de espacios en blanco.

Este es el diff completo, contrastado con la implementación original y la
copia realmente evaluada. El agente partió del original defectuoso, no del
candidato anterior con `strip()`:

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

La lectura del código confirma que primero se resuelven timeout y fallo de
ejecución. Después, el cortocircuito del `or` evita llamar a `isspace()` sobre
`None`; la cadena vacía tiene su condición propia porque `"".isspace()` es
`False`. Las demás cadenas se clasifican usando el criterio elegido por el
usuario. No se añaden importaciones, escrituras, procesos ni entrada/salida.
El candidato **supera las pruebas disponibles de versión 2**.

Los eventos del desarrollador registran lecturas y una edición de `solution.py`.
Su primer comando de pruebas con `python` falló con código 127 porque ese
ejecutable no estaba disponible; el siguiente, con
`python3 -B -m unittest -v test_solution.py`, pasó las 16 pruebas con código 0.
Son acciones de la misma invocación. Su respuesta final afirma el éxito, pero
la aceptación se fundamenta en la evaluación posterior del controlador,
ejecutada en otra copia y otro proceso con las referencias conservadas.

### Procesos, dictamen y decisión del controlador

| Dato | Reparación v2 | Revisión v2 |
| --- | --- | --- |
| Codex CLI | 0.162.1 | 0.162.1 |
| Invocaciones `codex exec` | 1 | 1, sesión nueva |
| Sandbox | `workspace-write` | `read-only` |
| Límite | 180 s | 180 s |
| Estado y código de Codex | `finalizada`, 0 | `finalizada`, 0 |
| Duración de Codex | 27,229 s | 25,408 s |
| Respuesta final disponible | `true` | `true` |
| Stderr del agente | Vacío | Vacío |
| Estado o decisión del controlador | `supera_las_pruebas_disponibles` | `aprobada` |
| Código del controlador | 0 | 0 |
| Aceptación o aprobación | `aceptada: true` | `aprobada: true` |
| Integridad registrada | 7/7 positivas | 6/6 positivas |
| Errores del controlador | Lista vacía | Lista vacía |
| Duración total | 27,496 s | 25,555 s |

Las consultas previas de versión y ayuda terminaron con código 0. Los comandos
registrados desactivan aprobaciones, búsqueda web y delegación; usan eventos
JSONL, respuesta final separada y las opciones de sandbox indicadas, sin omitirlo.

La respuesta original del revisor contiene:

```json
{
  "decision": "aprobar",
  "resumen": "No identifico incumplimientos concretos en la revisión estática, incluidas combinaciones admitidas no cubiertas por las pruebas. El código respeta las prioridades, distingue None y cadena vacía, aplica str.isspace() y mantiene la pureza sin efectos secundarios.",
  "hallazgos": []
}
```

Su contenido coincide con `dictamen_validado.json`, el último mensaje de los
eventos y `dictamen_modelo` en el resumen. El controlador registra
`evidencia_previa_valida: true` y `error_respuesta: null`. Conforme a
`validate_repair()`, `validate_verdict()` y `decide()` en
[review_case.py](../review_case.py), la aprobación depende también de la
evidencia previa, el proceso correcto y la integridad. El código cero de Codex
o la frase del modelo por sí solos no bastan. La validación estructural tampoco
demuestra la verdad de todas las afirmaciones del modelo ni una cobertura
exhaustiva de entradas no probadas.

### Acciones observadas del revisor

Se leyó completo `revisor/eventos.jsonl`. Contiene estos seis comandos de
consulta y lectura, todos envueltos en `/bin/bash -lc` y terminados con código 0:

| Acción | Contenido observado |
| --- | --- |
| `pwd` | Directorio temporal `/tmp/review-case-cpdah4f2/workspace`. |
| `rg --files --hidden` con filtros de nombres | Enumera los nueve materiales; busca también `AGENTS.md`, sin encontrarlo. |
| `cat test_solution.py posterior.json posterior.stdout.txt posterior.stderr.txt respuesta.schema.json` | Lee las pruebas, el resultado y las salidas guardadas, y el esquema JSON. |
| `cat candidato.diff original.py` | Lee el diff y la implementación original. |
| `nl -ba candidato.py` | Lee las ocho líneas del candidato. |
| `nl -ba contrato.md` | Lee el contrato de versión 2. |

Las salidas de lectura corresponden a los materiales conservados. No hay
eventos de edición, importación o ejecución del candidato ni de las pruebas,
ni comandos de instalación, Git, navegación o delegación. **En las acciones
registradas, el revisor se limitó a consultar y leer los materiales**. Leer el
informe posterior con `cat` no constituye una nueva ejecución de esas pruebas.
Esta conclusión se apoya en los eventos, no solo en su descripción de la tarea.
El sandbox de solo lectura y los hashes finales no son por sí solos prueba
de ausencia de toda acción no observada.

### Contraste de integridad

Se recalcularon los hashes y se compararon los bytes sin ejecutar los archivos.
Las referencias coinciden con los originales actuales de versión 2; las pruebas
entregadas al desarrollador y las copias inicial y posterior son idénticas.
El candidato coincide con la implementación evaluada y con el material leído
por el revisor. El diff se reconstruyó y coincide exactamente con el guardado.

El inventario completo de la reparación coincide con `origen.json` de la
revisión. Los nueve materiales coinciden con los hashes de origen y de antes y
después en el resumen de revisión. La entrada del revisor coincide con
[prompts/reviewer.md](../prompts/reviewer.md) y su hash registrado. La explicación
final del desarrollador no está entre los materiales entregados al revisor.

La reparación conserva las mismas siete comprobaciones positivas descritas
para versión 1. La revisión registra `true` para `workspace_intacto`,
`registro_reparacion_intacto`, `materiales_conservados_intactos`,
`originales_intactos`, `instrucciones_intactas` y `entrada_intacta`.
La carpeta temporal ya no se conserva; su estado final se acredita por el
inventario registrado, mientras que las copias archivadas se han contrastado
directamente en este cierre.

| Material | SHA-256 verificado |
| --- | --- |
| Nuevo candidato de versión 2 | `7d3d635fbc248020f69cb15b1cc9050f1be4ca2ede558969068ba313d94fd03d` |
| Diff del nuevo candidato | `f2b13bed9333806eab4ec7a482ee75ee943c4221f19dc5831af03e405b3d3bad` |
| Pruebas de versión 2 | `c5fd3075772133bdd01972a634a22e1663bad2bf8fa6695a97ef43a6bd3761b3` |
| Contrato de versión 2 | `ecc5b162cdf2b78a85709f94f1386393e87ee83e2271085a9a933c2119262455` |

La implementación inicial mantiene el hash `4c373f13f90ef6c25d10aa71bbbfcd2235ea72f7839b9d5041a408cd94618cea`
y su defecto. Ningún registro histórico se modifica: permanecen tanto el fallo
de inicialización como la solicitud de cambios bajo versión 1. La decisión
humana que aclaró el contrato no convierte aquel rechazo en aprobación.

## Separación de evidencias al cierre

| Evidencia | Resultado y alcance |
| --- | --- |
| Suite automatizada del controlador | 57 pruebas correctas: 14 de ejecución, 16 de reparación y 27 de revisión; Codex simulado. Validación previa, no repetida en este cierre. |
| Reevaluación local anterior | Candidato histórico con `strip()` frente a las 16 pruebas de versión 2: 16 correctas, código 0, cero invocaciones de Codex. No pertenece a la nueva reparación ni a un dictamen. |
| Nueva reparación real v2 | Una invocación de Codex. El controlador ejecuta las 16 pruebas antes (9/7) y después (16/0) en procesos separados. |
| Pruebas internas del desarrollador v2 | El intento con `python` falla al arrancar; con `python3` pasan 16. Son acciones de su sesión y no sustituyen la evaluación del controlador. |
| Nueva revisión real v2 | Una invocación de Codex, seis comandos de lectura; dictamen `aprobar` y decisión `aprobada`. No ejecuta otra suite del caso según sus eventos. |
| Este cierre documental | Lectura, comparación de archivos y hashes, revisión del diff y enlaces. Sin pruebas de código ni nuevas llamadas al modelo. |

La secuencia completa conserva **cinco invocaciones de `codex exec`**: tres de
reparación (incluido el fallo de inicialización) y dos de revisión. No se
confunden con solicitudes internas al modelo, cuyo número no se deduce de ese
recuento, ni con las consultas locales de versión y ayuda. Los registros siguen
intactos y excluidos de Git; este informe permite entenderlos sin acceso a ellos.

## Limitaciones

Un caso sencillo, reparaciones que superan las pruebas disponibles, dos
revisiones y una reevaluación local **no demuestran
fiabilidad general**, una tasa de éxito ni corrección para todas las entradas.
La aprobación de versión 2 es el resultado de esta revisión concreta.
La aclaración del contrato tampoco demuestra por sí sola la fiabilidad del
revisor. No se ha implementado un ciclo automático de corrección. El primer
fallo se conserva y su causa concreta continúa sin confirmarse.

Una carpeta temporal no garantiza aislamiento de lecturas. Las pruebas
ejecutadas por el controlador no heredan automáticamente el sandbox de Codex:
sus procesos Python disponen de los permisos del controlador. Las comparaciones
de integridad verifican el estado final; no detectan modificaciones transitorias
que luego se reviertan ni sustituyen un aislamiento del sistema operativo.

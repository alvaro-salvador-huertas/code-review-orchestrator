# Primera ejecución real del flujo acotado — 18 de octubre de 2026

**Resultado conservado: `tiempo_agotado_revisor`, código 4.** Queda acreditada
una corrección automática tras fallos de pruebas y una segunda entrega que
supera las cuatro evaluaciones exigidas. La revisión incluida en esa orquestación
no obtuvo dictamen final. Una [revisión adicional posterior y su contraste](#revisión-adicional-y-contraste-de-sus-hallazgos)
dejaron dos defectos confirmados y cambios pendientes, sin incorporación.
Pasar pruebas no sustituye la revisión ni demuestra corrección
general. Es una reproducción de la tarea conocida sobre la base del contrato
003, `9bec53279d82058fe188c0038bab5ba66ce64003`, no una tarea desconocida.

Fuentes locales, excluidas de Git. Todos los enlaces a `runs/` de este informe
requieren el workspace que conserva la evidencia; **no están disponibles en
un clon público del repositorio**:

- [Registro principal (local)](../../../runs/20261018T174000Z_inspect-json_orchestrate_de62ce3d195248f9aecbd9b3c9f99d1f/resultado.json).
- [Revisión enlazada (local)](../../../runs/20261018T175100Z_inspect-json_review_b31ecd79588b455391be3192214734e2/resultado.json).

El análisis inicial solo lee JSON, texto, AST y objetos Git y recalcula hashes y
manifiestos. No relanza el flujo, agentes, candidatos ni pruebas. Conserva la
rama `feat/orquestacion-proyectos` y todos los cambios pendientes. Las horas
siguientes corresponden a Europe/Madrid, UTC+2 en esta fecha. El contraste
posterior, descrito al final, ejecuta únicamente consultas sintéticas enfocadas
en copias temporales y procesos hijos; no repite las evaluaciones originales.

## Transiciones y evaluaciones

El flujo transcurrió entre las 19:40:00,569 y las 19:54:02,310, durante
841,740 s. La preparación acreditó ausencia de JSON en la base: aceptación
14 métodos, 12 con fallos, 26 aserciones fallidas —20 en subtests—, código 1;
regresión 153 métodos, sin fallos, código 0. Ambas terminaron sin errores ni
omisiones. **Hallazgos y anidamiento no se ejecutaron en la preparación**;
su ausencia no se cuenta como cero pruebas ni como éxito.

| Entrega | Suite | Métodos ejecutados/terminados | Métodos con fallos | Aserciones fallidas | Errores | Omisiones | Código |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Aceptación revisada | 14/14 | 0 | 0 | 0 | 0 | 0 |
| 1 | Regresión | 153/153 | 0 | 0 | 0 | 0 | 0 |
| 1 | Hallazgos | 6/6 | 3 | 3 | 0 | 0 | 1 |
| 1 | Anidamiento | 7/7 | 1 | 1 | 0 | 0 | 1 |
| 2 | Aceptación revisada | 14/14 | 0 | 0 | 0 | 0 | 0 |
| 2 | Regresión | 153/153 | 0 | 0 | 0 | 0 | 0 |
| 2 | Hallazgos | 6/6 | 0 | 0 | 0 | 0 | 0 |
| 2 | Anidamiento | 7/7 | 0 | 0 | 0 | 0 | 0 |

En cada entrega se registran, respectivamente, 27, 177, 0 y 2 subtests; ninguno
falla. Los cuatro fallos de la entrega 1 son de métodos sin subtest asociado.
«Aserciones» en la tabla significa fallos reportados por unittest, no un recuento
de todas las aserciones ejecutadas; las exitosas no se inventarían desde estos
informes.

Se contrastaron las identidades de `metodos` y `terminados` con el AST de las
referencias congeladas, incluida la herencia local de la regresión. Coinciden con
`procedencia.json`; cada informe acredita una sesión completa, sin omisiones,
fallos esperados ni éxitos inesperados. Los cierres textuales dicen `Ran N tests`
con los mismos totales: `FAILED (failures=3)` y `FAILED (failures=1)` en las dos
suites fallidas de la entrega 1; `OK` en las otras seis. Los códigos, comandos,
resúmenes estructurados y manifiestos de las copias evaluadas coinciden. La
regresión se ejecutó sobre cada entrega; no se reutilizó la histórica.

La transición registrada del intento 1 es `evaluacion → corregir`, motivo
`fallos_asercion`, con revisión ausente. Esos cuatro fallos, con un intento
disponible, autorizaron el segundo desarrollo: **la aceptación revisada y la
regresión ya pasaban**. El intento 2 registra `evaluacion → revisar`, motivo
`superadas`. El timeout posterior está en el resultado de revisión y en el
general; no hay transición de aprobación, solicitud de cambios ni agotamiento
del presupuesto. El controlador detuvo el flujo por código 4.

## Corrección y continuidad

| Artefacto | SHA-256 recalculado |
| --- | --- |
| Candidato 1, recogido | `f406cb295ce946426c8b2ff816e720e4cb41030ddf5facd628150bb1252aa467` |
| Partida del desarrollo 2 (`entrega/partida.py`) | `f406cb295ce946426c8b2ff816e720e4cb41030ddf5facd628150bb1252aa467` |
| Candidato 2, recogido y evaluado | `b3156ae2f1ae2ff7129cf462f159f926f6ddef5b10f16bc74e562b607e27ebdc` |

La igualdad entre candidato 1 y partida 2 es también byte a byte. Coinciden los
hashes del general, ambas entregas, feedback, manifiestos de evaluación y
autorización de revisión. Los diffs contra la base y entre entregas se
reconstruyeron y coinciden con los guardados.

El `feedback.json` efectivo del intento 2 contiene únicamente `hallazgos` y
`anidamiento` bajo `pruebas`, con sus diagnósticos, informes, rutas y hashes;
`revision` es `null`. Sus bytes están incorporados en `desarrollo/entrada.txt`,
junto al prompt congelado y al contrato. Se contrastó esa composición exacta y
las fuentes de los diagnósticos. No hubo feedback del revisor.

Los defectos observados y la corrección de `entrega/anterior.diff` son:

- `test_resumen_cero_a_false` y `test_resumen_uno_a_true`: se devolvía código 0
  cuando un resumen enlazado cambiaba un número por un booleano y debía señalar
  discrepancia con código 1. También fallaba
  `test_booleano_profundo_distinto_de_numero`. La corrección reemplaza la igualdad
  directa de resúmenes por `same_json`, una comparación iterativa que distingue
  booleanos y números, conserva la equivalencia entre entero y float y compara
  claves y elementos anidados.
- `test_duracion_entera_grande`: `10**309` se proyectaba como `null`. La corrección
  reserva `math.isfinite` para floats, conserva los enteros no negativos y añade
  una alternativa de presentación textual si el formato decimal desborda.

Los cuatro métodos pasan después, junto con las restantes comprobaciones de
sus suites, aceptación y regresión. Esto respalda la corrección de los escenarios
observados. **No hubo `RecursionError` registrado en la primera entrega**: la
comparación iterativa no se presenta como corrección de un fallo de recursión
reproducido en esta ejecución. Las comprobaciones que los desarrolladores dicen
haber hecho por su cuenta no se suman a la evaluación independiente.

## Presupuesto e integridad

| Invocación | Reserva | Inicio del proceso | Duración / límite | Código del proceso |
| --- | --- | --- | ---: | ---: |
| Desarrollo 1 | 19:41:10,033 | 19:41:10,036 | 260,589 / 300 s | 0 |
| Desarrollo 2 | 19:46:35,570 | 19:46:35,576 | 198,451 / 300 s | 0 |
| Revisión del candidato 2 | 19:51:01,385 | 19:51:01,399 | 180,006 / 180 s | −9 |

Las tres reservas existen en disco y preceden a sus procesos. Concuerdan con
los contadores por intento y globales: **2 desarrolladores, 1 revisor, 3/4**,
sin exceder una llamada por rol e intento. Las seis consultas de versión/ayuda
se registran aparte: todas código 0, con límite de 10 s. Las evaluaciones
respetaron 60 s por aceptación/hallazgos/anidamiento y 180 s por regresión.

Recalculado ahora: coinciden los **21 manifiestos de etapas cerradas**, la
referencia completa, los 42 archivos de la base con sus objetos Git, los
manifiestos por entrega y los cinco orígenes enlazados de revisión. También
coinciden materiales, selección, evidencia extensa y hashes de sus fuentes.
Los cambios guardados de ambos desarrollos se limitan a `inspect_run.py`, sin
cambios de permisos. Los cuatro inventarios de evaluación de cada candidato
corresponden a la base con únicamente ese inspector sustituido.

Antes de estos cambios documentales, el inventario filtrado actual del proyecto
coincidía íntegramente con `original_sha256`. El inspector del repositorio sigue
en `8abca5003639de7ddbed2c5f242c60d2a030be2548538b5f2a0b1507e78e7b87`, igual que
al comienzo de la ejecución y que `HEAD`; no es ninguno de los dos candidatos.

Los workspaces temporales de preparación, desarrollo, evaluación y revisión ya
no existen. Su conservación antes/después y la verificación de la partida en
el workspace son comprobaciones **registradas entonces**, no inspecciones
repetibles ahora sobre esos directorios. Sí se han contrastado sus inventarios
con las copias y bytes conservados. Los hashes no constituyen aislamiento de
seguridad ni certifican por sí solos la corrección semántica.

## Evidencia del timeout del revisor

La revisión registra `tiempo_agotado`, 180,006 s para un límite de 180 s,
código de proceso −9, `error: null`; su etapa completa duró 181,488 s.
El lanzador congelado captura `TimeoutExpired` y envía `SIGKILL` al grupo de
procesos. Ese mecanismo y el código −9 son coherentes con la detención por el
límite, no con una aprobación ni con una salida voluntaria del revisor.

Las tres consultas de versión indican **`codex-cli 0.162.1`**. El comando de
revisión acredita `exec`, sandbox `read-only`, `approval_policy="never"`,
`web_search="disabled"`, `features.multi_agent=false`, workspace externo,
`--skip-git-repo-check`, `--ephemeral`, `--json`, esquema de respuesta y ruta de
último mensaje. El proceso registra la política de entorno `codex`. No se
registran el modelo resuelto, esfuerzo de razonamiento, proveedor ni una
configuración efectiva completa: no se deducen de opciones predeterminadas ni
se consulta configuración personal para rellenar ese vacío.

El contexto conservado y contrastado con su selección es:

| Archivo | Bytes |
| --- | ---: |
| `contrato.md` | 8.444 |
| `inspect_run.py` | 17.240 |
| `original/inspect_run.py` | 14.499 |
| `candidato.diff` | 16.773 |
| `dependencias/case_evidence.py` | 6.726 |
| `pruebas/test_inspect_run.py` | 19.495 |
| `evaluacion/evaluador_revisado.py` | 17.363 |
| `resumen_evidencia.json` | 4.039 |
| `respuesta.schema.json` | 683 |
| **9 archivos** | **105.262** |

El prompt separado ocupa 4.001 bytes: 109.263 bytes entre materiales y prompt,
sin equivaler a tokens ni medir la carga interna del servicio. La evidencia
extensa y la explicación del desarrollador quedaron fuera del workspace.

`eventos.jsonl` conserva 26 eventos: inicio de sesión y turno, y 12 pares de
comando iniciado/completado. Los 12 comandos terminaron con código 0. Hubo
listado de archivos, lectura de contrato/esquema y resumen, recuento de líneas,
lectura numerada de candidato, dependencia y original, lectura de pruebas y
diff, y finalmente del evaluador. Se releyeron las líneas 1–125 del original
y 330–359 del candidato después de sus lecturas completas; no hay comandos
idénticos repetidos. Las salidas acumuladas contienen 117.672 bytes de texto.
El último evento, `item_11` completado, es `cat evaluacion/evaluador_revisado.py`,
con código 0 y 17.363 bytes de salida.

No existen `revisor/respuesta_original.txt` ni `dictamen_validado.json`;
`dictamen_modelo` es `null`. Tampoco hay eventos `agent_message`, `turn.completed`,
`turn.failed` o `error`: se conserva **salida parcial de herramientas de lectura**,
no un dictamen parcial ni mensajes de progreso redactados por el modelo.
Los eventos carecen de tiempos individuales; no permiten medir cada lectura,
cuánto duró el intervalo posterior al último evento o el tiempo de razonamiento.
No hay observaciones preliminares que elevar a hallazgos confirmados.

El stderr de la revisión está vacío; no consta error de conexión, autenticación,
lanzamiento ni de los comandos leídos. Sí hubo dos errores de actualización del
catálogo de modelos por `request timed out` **en el primer desarrollo**, a las
19:41:15,548 y 19:41:15,586; este terminó con código 0. Allí también una búsqueda
de `AGENTS.md` devolvió 1 sin salida. El segundo desarrollo no registra errores
de comandos ni stderr. Estos incidentes anteriores no prueban una causa del
timeout del revisor. Ni el tamaño del contexto ni las relecturas permiten
atribuirle una causa: falta telemetría temporal y del servicio para ello.

## Conclusión y siguiente paso del análisis inicial

Está acreditada la corrección automática tras pruebas fallidas; el segundo
candidato supera las cuatro suites requeridas. **Al cerrar la orquestación
faltaba una revisión final válida**, el contraste semántico de sus posibles hallazgos y la decisión humana
antes de incorporar una entrega. El estado histórico permanece en código 4;
no se convierte en aprobación ni en agotamiento de cuatro llamadas.

Se propuso una **revisión independiente adicional de la segunda entrega exacta**,
sin repetir desarrollos: conservar el SHA-256 `b3156ae2…7ebdc`, vincular un
registro nuevo a `intentos/2/evidencia` y a sus referencias/evaluaciones selladas,
validar de nuevo esa procedencia por lectura y conservar aparte el timeout.
La nueva sesión no recibiría explicaciones del desarrollador ni los eventos de
la revisión interrumpida. No debe usarse la CLI histórica con rechazos ficticios,
relanzarse `orchestrate_project.py` ni simular una reanudación: entonces el hito no
ofrecía revisión aislada sin la reserva del orquestador. Hacía falta habilitar y
autorizar explícitamente esa operación separada con su propia reserva persistente.
Ese análisis no la implementó ni la ejecutó, y no propuso aumentar todavía los
180 s: el diagnóstico disponible no lo justifica.

## Implementación posterior de la operación adicional

Tras este análisis se implementó el modo explícito de revisión aislada en
`review_project.py`, con registro propio y una reserva persistente máxima del
revisor. La [guía del flujo](../../../docs/orquestacion-proyectos.md#revisión-aislada-de-una-entrega-terminada)
documenta interfaz, presupuesto, códigos y el comando preparado con 300 s por
petición posterior del usuario. Durante la implementación no se ejecutó esa
revisión real ni se repitieron los desarrollos o evaluaciones originales.

La nueva validación en lectura acepta el intento 2: el SHA-256 recalculado del
candidato, su resumen y las cuatro evaluaciones coinciden en
`b3156ae2f1ae2ff7129cf462f159f926f6ddef5b10f16bc74e562b607e27ebdc`;
los 21 manifiestos cerrados y las autoridades pertinentes coinciden. El origen
y la revisión enlazada permanecen intactos, con el resultado histórico
`tiempo_agotado_revisor`, código 4. Los 300 s no constituyen un diagnóstico
de aquel timeout ni una garantía de aprobación. Se dejó preparada la operación
adicional cuya ejecución posterior se describe a continuación.

## Revisión adicional y contraste de sus hallazgos

La operación `inspect-json-20261018-intento-2-r1` se ejecutó después, entre las
22:00:56,769 y las 22:04:09,880 del 18 de octubre. Su [registro propio (local)](../../../runs/inspect-json_isolated-review_inspect-json-20261018-intento-2-r1/resultado.json)
conserva una única reserva del revisor, límite solicitado y efectivo de 300 s,
Codex CLI 0.162.1 y proceso finalizado con **código 0 en 191,706 s**. La operación
completa duró 193,112 s. El [dictamen válido (local)](../../../runs/inspect-json_isolated-review_inspect-json-20261018-intento-2-r1/dictamen_validado.json)
solicitó cambios con dos hallazgos: el controlador devolvió **código 1**.
Es una operación adicional con presupuesto propio, no una cuarta llamada de
la orquestación reanudada. No demuestra por qué agotó el tiempo la revisión
anterior. Su `contraste_semantico: pendiente` histórico no se reescribe.

El contraste posterior es **verificación automática asistida, no auditoría
humana**. Antes de ejecutar se verificaron por lectura candidato, base Git,
dependencia `case_evidence.py`, contrato, dictamen, materiales seleccionados,
autorización y manifiestos. El candidato recogido, evaluado y revisado coincide
en `b3156ae2f1ae2ff7129cf462f159f926f6ddef5b10f16bc74e562b607e27ebdc`.

La evidencia nueva queda local, excluida de Git, en
[`20261018T200951Z_inspect-json_contraste_aislado_93e1d770eade45bfaa591231283023a3` (local)](../../../runs/20261018T200951Z_inspect-json_contraste_aislado_93e1d770eade45bfaa591231283023a3/resultado.json).
Conserva scripts, entradas sintéticas completas, copias exactas de ambos
inspectores y su dependencia, comandos, canales, objetos JSON, firmas de API,
comparaciones de bytes, traza AST, aserciones fallidas y manifiesto. Se usó
`/usr/bin/python3.12`: **3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]**,
política `evaluation`, límite de 10 s por hijo y temporales externos. Fueron
16 procesos: versión, 12 consultas de duración y tres consultas AST, incluida
la traza. El controlador no importó ningún inspector.

### Hallazgo 1: compatibilidad textual — confirmado

El contrato exige conservar contenido, canales y códigos textuales, incluida
`inspect_run(run_dir)`. La firma `(run_dir)` se verificó y llamó en hijos
separados. La base no admite `--format`; su modo predeterminado y su API son
la referencia textual. Los registros sintéticos incluyen resúmenes enlazados,
transiciones, referencias explícitas e informes coherentes; estos informes
son datos sintéticos, no pruebas históricas realmente ejecutadas.

| Entrada y comprobación | Esperado / base congelada | Candidato observado |
| --- | --- | --- |
| Control `12.3456`, texto predeterminado/API y texto explícito del candidato | Código 0, `Duración: 12.346 s`, stderr vacío. | Códigos y ambos canales idénticos byte a byte en todas esas vías. |
| Entero decimal `10**400`, texto predeterminado/API y texto explícito del candidato | Código 1; `Duración: no consta`; stderr: `Consulta incompleta: general: duración inválida`. | Código 0; imprime los 401 dígitos seguidos de `.000 s`; stderr vacío. Las tres vías difieren de la base en código, stdout y stderr. |
| Ese mismo entero, JSON del candidato | Código 0, entero exacto conservado, stderr vacío. | Cumple: tipo `int`, valor igual a `10**400`, sin incidencias. |

El entero se escribió como 401 dígitos decimales, sin exponente ni conversión a
`float`. No se confunde esta regresión textual con un defecto de JSON: la
conservación del entero grande en JSON sigue siendo correcta y exigida.
Evidencia: `entradas_duracion.json`, `comparaciones_textuales.json` y
`procesos/{ordinaria,entero_grande}_*/` del registro nuevo.

### Hallazgo 2: advertencias del análisis AST — confirmado

El contrato exige stderr vacío en consultas JSON con argumentos válidos. El
control completo devuelve código 0, objeto de consulta `completada` y stderr
vacío. Se añadió **solo** a `etapas/reparacion/referencia/test_solution.py` la
línea `patron = "\d"`, con bytes hexadecimales
`706174726f6e203d20225c64220a`. El constructor usa el byte `0x5c`, no un literal
Python con escape inválido. Las pruebas `Historicas.test_a` y `Historicas.test_b`,
sus identificadores e informes inicial/posterior permanecen iguales.

La consulta mutada conserva código 0 y un objeto JSON idéntico al control,
pero escribe cuatro veces en stderr:

```text
test_solution.py:8: SyntaxWarning: invalid escape sequence '\d'
```

Una consulta adicional con observación pasiva (`sys.setprofile` y eventos de
auditoría) reproduce los mismos canales byte a byte. Acredita cuatro llamadas
a `ast.parse` sobre los bytes de la referencia mutada y la pila
`inspect_run_json → collect_run → attempt_summary → test_summary →
classify_test_report/test_report_rows → reference_test_ids → ast.parse →
warnings._showwarnmsg`. Se analiza dos veces cada fase histórica.
No hubo ejecución/importación de esas referencias: el registro de `exec` de
la referencia está vacío y sus centinelas e inventarios permanecen intactos.
No se usaron `-W`, `-X dev`, `PYTHONWARNINGS` ni filtros para forzar o suprimir
advertencias; la traza conserva los filtros. Evidencia: `mutacion_ast.json`,
`procesos/ast_{control,escape,traza}/` y `traza.json` dentro de esta última etapa.

### Resultado y límites del experimento

Las comprobaciones exigieron el comportamiento contractual: **7 métodos,
2 con fallos, 4 aserciones fallidas —tres variantes textuales y stderr JSON—,
0 errores y 0 omisiones; código 1**. Las aserciones y su cierre `FAILED` quedan
conservados; no se presentan como aceptación superada. Los controles ordinario,
JSON con entero grande, AST limpio e integridad pasaron. No se repitieron
aceptación, regresión ni llamadas al modelo.

Se distinguen cinco hechos: corrección automática tras fallos de pruebas;
segundo candidato que pasó 14/153/6/7 métodos de las cuatro suites; timeout
original a 180 s, código 4; revisión adicional a 300 s con solicitud de cambios;
y dos defectos reproducidos en este contraste. El experimento prueba estos
casos concretos bajo Python 3.12.3, no corrección general ni una auditoría humana.
**La entrega experimental queda sin incorporar y con cambios pendientes.**
No se corrigió ningún candidato. El inspector integrado, los registros
anteriores y sus resultados permanecen intactos, al igual que los contratos,
evaluadores y cambios de implementación previos. Durante este contraste se
conservó la rama y no se hizo commit, push ni merge.

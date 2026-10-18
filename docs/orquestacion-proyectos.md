# Flujo acotado de inspect-json

```bash
python3 -B orchestrate_project.py inspect-json --max-attempts 2
```

Admite uno o dos intentos; dos es el valor predeterminado. Este comando **invoca
agentes reales** cuando se ejecuta con Codex disponible. El hito se validó
inicialmente con ejecutables simulados. La [primera ejecución real del 18 de
octubre](../evals/tareas_reales/inspect_json/orquestacion-real-2026-10-18.md)
acredita una corrección automática tras fallos de pruebas y una segunda entrega
que supera todas las evaluaciones; se detuvo por `tiempo_agotado_revisor`, código
4, sin dictamen final. Una revisión adicional a 300 s solicitó cambios y el
[contraste posterior](../evals/tareas_reales/inspect_json/orquestacion-real-2026-10-18.md#revisión-adicional-y-contraste-de-sus-hallazgos)
confirmó dos defectos. No acredita un ciclo completo con aprobación.
No hace commit, push, merge ni aplica la entrega al proyecto original.

Reproduce la tarea conocida del contrato 003 desde
`9bec53279d82058fe188c0038bab5ba66ce64003`. Aunque `main` ya contiene exportación
JSON, la base congelada todavía no la implementa. No es una tarea nueva ni
desconocida. Los rechazos, reevaluaciones, revisiones y correcciones asistidas
anteriores conservan sus resultados y su interpretación histórica.

## Transiciones y presupuestos

1. Congelar una vez la base Git, contrato, autoridades actuales, prompts,
   adaptadores y configuración. Ejecutar aceptación revisada sobre la base y
   regresión de la base: debe faltar `--format json` y pasar la regresión.
2. Reservar persistentemente una invocación del desarrollador antes de lanzar
   su proceso. Solo `inspect_run.py` es editable en su copia temporal.
3. Recoger el candidato, SHA-256, estado de archivos y diffs contra la base y
   contra la partida. Reconstruir otra copia desde la referencia, incorporando
   exclusivamente el inspector recogido.
4. Ejecutar sobre esa entrega las cuatro suites obligatorias: aceptación
   revisada, regresión de la base, `comprobar_hallazgos.py` (booleanos y duración
   entera grande) y `comprobar_anidamiento.py`. Sus criterios no se modifican.
5. Solo con todas las evaluaciones completas y superadas, validar la procedencia
   y reservar una revisión. Cada revisión abre una sesión nueva, efímera, de solo
   lectura, con contrato, original, candidato, diff, dependencias pertinentes y
   resumen verificable. Las salidas extensas, explicación del desarrollador y
   dictámenes anteriores quedan fuera del workspace del revisor.
6. Una aprobación válida deja la entrega `lista_para_revision_humana`. Una
   aserción fallida o una solicitud válida de cambios permite corregir si queda
   otro intento. Los demás resultados detienen el flujo. Tras el último intento,
   esos dos resultados producen `intentos_agotados`.

| Etapa | Límite por proceso |
| --- | --- |
| Desarrollador | 300 s |
| Revisor | 180 s |
| Regresión | 180 s |
| Aceptación, hallazgos y anidamiento | 60 s por suite |
| Consultas de versión/ayuda de Codex | 10 s cada una |
| Consultas CLI de los evaluadores públicos | 10 s cada una |

Cada intento permite como máximo una invocación de cada rol: con dos intentos,
dos desarrollos y dos revisiones como máximo, cuatro llamadas en total. Las
consultas de versión/ayuda se registran aparte y no consumen invocaciones de
modelo. Los contadores globales consumen conservadoramente la reserva incluso
si el lanzamiento posterior falla. Un fallo de persistencia impide lanzar el
proceso. No hay reanudación, reintentos técnicos ni llamadas adicionales para
arreglar respuestas inválidas.

## Continuidad y evidencia

El segundo workspace comienza con los mismos bytes y SHA-256 de la primera
entrega recogida. El controlador conserva ambos candidatos, su relación y los
diffs. Entrega el contrato y diagnósticos de las pruebas fallidas con informes,
fuentes y hashes. Si hubo un dictamen válido, incorpora también sus hallazgos
como **observaciones del modelo pendientes de contraste semántico** e instruye
al desarrollador para contrastarlos con contrato y código antes de corregir.
Validar JSON y líneas no confirma que el hallazgo sea cierto. Todo feedback es
dato; no autoriza cambiar contrato, pruebas, límites ni archivos protegidos.

`project_flow.validate_delivery` comprueba base contra Git, referencias,
autoridades, reserva previa, candidato exacto, continuidad, alcance, comandos,
límites, informes completos y sellos de etapas. Deriva las identidades de los
métodos desde el AST de cada referencia: no fija cantidades de pruebas en el
controlador. Distingue métodos, fallos de aserción y subtests ejecutados/fallidos;
no afirma contar todas las aserciones exitosas de unittest.

`review_project.run_delivery_review` es la vía explícita para estas entregas y
requiere la reserva global del orquestador. No usa rechazos ni reevaluaciones
ficticios. La CLI histórica `review_project.py --development-run ...
--reevaluation-run ...` y su validador conservan sus requisitos. La revisión
aislada descrita a continuación tiene presupuesto propio y no reanuda el flujo.
El runner histórico permanece intacto; `project_flow_runner.py` añade el registro
de subtests y la salida externa de las comprobaciones públicas para el flujo nuevo.

## Revisión aislada de una entrega terminada

`review_project.py` admite otro modo explícito:

```bash
python3 -B review_project.py \
  --orchestration-run runs/<registro_del_flujo> \
  --attempt 2 \
  --operation-id <identificador_unico> \
  --review-timeout 300
```

Los tres primeros argumentos son obligatorios en este modo. El intento debe ser
1 o 2 y existir; nunca se selecciona implícitamente el último. No se pueden
mezclar con `--development-run` o `--reevaluation-run`. El identificador admite
1–80 letras ASCII, números, guion o subrayado, comenzando por letra o número.
El límite opcional admite **enteros entre 60 y 600 segundos**, con **180 s por
defecto**. Los recorridos históricos y las revisiones dentro de la orquestación
mantienen sus 180 s; la configuración congelada del origen no cambia.

Primero se valida por lectura la orquestación cerrada y el intento explícito.
Se reutiliza `project_flow.validate_delivery`: desarrollo satisfactorio,
candidato recogido y evaluado idéntico, continuidad, cuatro evaluaciones
completas y superadas, comandos, límites, autoridades congeladas, inventarios
y cierres estructurados/textuales. Además se contrastan el resumen global,
consumos, reservas, manifiestos de etapas y revisiones enlazadas. Un timeout
previo del revisor no invalida las evaluaciones terminadas ni permite omitir
comprobaciones. Una discrepancia rechaza la operación antes de consultar Codex.
No se ejecutan candidatos, pruebas ni desarrollos para autorizar la revisión.

El registro nuevo es `runs/inspect-json_isolated-review_<identificador>/`.
Su creación exclusiva impide que dos procesos con el mismo identificador
continúen simultáneamente. `operacion.json` vincula origen, intento y SHA-256
completo, resultado original y límites solicitado/efectivo. Tras las consultas
de versión/ayuda, `reserva.json` se crea exclusivamente y se persiste junto al
contador **antes** del lanzamiento. El presupuesto propio es **un revisor como
máximo, cero desarrolladores**. La reserva se consume conservadoramente aunque
el proceso no llegue a arrancar. Un error de persistencia impide el lanzamiento.

La existencia del registro bloquea también una repetición después de timeout,
interrupción, fallo previo o caída del controlador: no hay reanudación ni
reintentos automáticos. No se borra ni reutiliza el registro para volver a llamar.
Otro identificador representa una operación adicional explícita con otro
presupuesto, nunca una continuación de la misma operación. El identificador es
único dentro del repositorio, incluso si se cambian los demás argumentos.

La sesión es nueva, efímera y de solo lectura. Recibe el candidato exacto,
contrato, original/diff, dependencias y evidencia pertinente verificada. El
resumen identifica las evaluaciones como conservadas y verificadas por lectura;
no inventa una reevaluación. Se usa el mismo prompt y los mismos criterios del
flujo; las explicaciones del desarrollador y los mensajes de revisiones
anteriores quedan fuera del contexto. Se conservan aparte procedencia y
manifiestos, selección, respuesta disponible, eventos, stderr, comandos,
versión, tiempos, configuración explícita y hashes del registro del revisor.
No se afirma una versión de modelo o configuración efectiva que la CLI no
acredite en esos registros.

| Código de la revisión aislada | Significado |
| --- | --- |
| 0 | Ejecución satisfactoria y dictamen de aprobar con formato/coherencia válidos. |
| 1 | Solicitud de cambios válida; no invoca al desarrollador. |
| 2 | Argumentos inválidos o combinación ambigua. |
| 3 | Fallo técnico del revisor o de su CLI. |
| 4 | Timeout del revisor o de una consulta CLI. |
| 5 | Respuesta ausente, inválida o incoherente. |
| 6 | Integridad alterada durante la revisión. |
| 7 | Evidencia previa inválida, incompleta, mezclada o no superada. |
| 8 | Fallo del controlador o persistencia. |
| 9 | Interrupción. |
| 10 | Identificador ya existente; no se invoca ni se sobrescribe la operación anterior. |

El resultado técnico (`revisor`), el dictamen validado (`dictamen_modelo`), el
`contraste_semantico: pendiente` y la `incorporacion: no_realizada` se mantienen
separados. Una aprobación de formato no confirma la verdad de los hallazgos ni
autoriza incorporar automáticamente. Los fallos técnicos conservan cualquier
respuesta parcial disponible sin aceptarla como dictamen.

### Comando de la revisión adicional observada

La comprobación de lectura del 18 de octubre de 2026 autoriza el intento 2 del
registro analizado: el candidato recogido y las cuatro evaluaciones coinciden
en `b3156ae2f1ae2ff7129cf462f159f926f6ddef5b10f16bc74e562b607e27ebdc`.
Los 21 manifiestos cerrados coinciden. No se reconstruyen los workspaces
temporales desaparecidos: se contrastan sus inventarios y comprobaciones
registradas. Véase el [análisis de origen](../evals/tareas_reales/inspect_json/orquestacion-real-2026-10-18.md).

Comando preparado durante la implementación y ejecutado posteriormente en una
operación independiente; **no se ha vuelto a ejecutar durante el contraste**.
El identificador ya tiene registro y no admite repetición:

```bash
python3 -B review_project.py \
  --orchestration-run runs/20261018T174000Z_inspect-json_orchestrate_de62ce3d195248f9aecbd9b3c9f99d1f \
  --attempt 2 \
  --operation-id inspect-json-20261018-intento-2-r1 \
  --review-timeout 300
```

Es una operación adicional, no la cuarta llamada de una orquestación reanudada.
El origen conserva `tiempo_agotado_revisor`, código 4, dos desarrollos y una
revisión. Los 300 s son un presupuesto nuevo solicitado expresamente: no
demuestran la causa del timeout anterior ni garantizan éxito. La revisión
adicional terminó técnicamente con código 0 y solicitó cambios (controlador 1).
El [contraste enfocado de sus dos hallazgos](../evals/tareas_reales/inspect_json/orquestacion-real-2026-10-18.md#revisión-adicional-y-contraste-de-sus-hallazgos)
confirmó una regresión textual con `10**400` y advertencias de `ast.parse` en
stderr JSON bajo Python 3.12.3: siete métodos, dos fallidos y cuatro aserciones
fallidas, código 1. Es verificación automática asistida, no auditoría humana ni
aceptación completa. La entrega experimental sigue sin incorporar y con cambios
pendientes; no se corrigió el candidato ni se cambió el inspector integrado.

## Registros y códigos

Los registros de `runs/` son evidencia local excluida de Git. Las rutas y enlaces
a esos registros solo se pueden consultar en el workspace que los conserva;
no están disponibles en un clon público del repositorio.

El progreso aparece inmediatamente en stderr; stdout contiene el resumen final.
Las funciones reutilizables son silenciosas salvo que reciban un callback de
progreso. `runs/*_inspect-json_orchestrate_*/resultado.json` guarda estado,
motivo, código, tiempos, límites, reservas, consumos, intentos, evaluaciones,
dictámenes, integridad y referencias a los registros detallados. Conserva:

- `referencia/`: proyecto base, autoridades, prompts, configuración y procedencia.
- `inicial/`: comprobaciones previas y sus canales, comandos e informes.
- `reservas/`: documentos persistidos antes de cada llamada.
- `intentos/N/evidencia/`: partida, candidato, diffs, feedback, desarrollo y
  evaluaciones de esa entrega, incluidas salidas parciales y desfavorables.
- Los registros de revisión enlazados: evidencia extensa, selección del contexto,
  materiales compactos, respuesta original y dictamen validado, cuando exista.

Cada evaluación se sella al cerrar su etapa, también ante fallos. Las etapas
anteriores se contrastan antes y después de las siguientes llamadas. Los
registros parciales de desarrollo también se conservan al detenerse.

| Código de `orchestrate_project.py` | Significado |
| --- | --- |
| 0 | Pruebas superadas y aprobación válida; lista para revisión humana. |
| 1 | Intentos agotados por aserciones o solicitud de cambios. |
| 2 | Argumentos CLI inválidos. |
| 3 | Fallo técnico de proceso/agente o error de pruebas. |
| 4 | Timeout de una etapa o consulta CLI. |
| 5 | Respuesta del revisor inválida. |
| 6 | Alteración de integridad o del alcance permitido. |
| 7 | Evidencia inválida/incompleta o preparación que no autoriza desarrollo. |
| 8 | Fallo de controlador o persistencia. |
| 9 | Interrupción. |

El esquema JSON v1 y el inspector integrado **no cambian**. Estos registros son
de tipo `orquestacion_inspect_json_v1`, distinto de los registros de benchmark
que consulta `inspect_run.py`. Para consultarlos se necesita un lector JSON
general; no hay aún inspector específico. Por ejemplo:

```bash
python3 -m json.tool runs/<registro_del_flujo>/resultado.json
```

Se reutilizan las políticas `evaluation` y `codex` de
[`process_environment.py`](../process_environment.py), sin volcar variables de
entorno ni copiar configuración personal. Las copias, hashes, prompts y
comprobaciones posteriores **no constituyen aislamiento de seguridad**. Los
procesos de pruebas ejecutan código candidato; el controlador no lo importa.
Los hashes detectan cambios respecto de estados observados, no certifican
evidencia frente a un atacante capaz de reescribir a la vez archivos y registros.

## Validación simulada

Las pruebas de [`tests/test_orchestrate_project.py`](../tests/test_orchestrate_project.py)
usan proyectos Git mínimos temporales, procesos reales de evaluación y una CLI
de agentes simulada. Las correcciones cambian realmente el candidato. Cubren
ambas rutas de corrección, presupuestos, continuidad, reservas, canales,
fallos técnicos, timeout, interrupción, respuesta inválida, evidencia incompleta,
alteraciones de integridad y ausencia de integración. Las pruebas existentes
de revisión mantienen la compatibilidad histórica.

Ejemplo reproducible en `test_fallo_aceptacion_correccion_aprobacion_y_continuidad`:

| Intento | Entrega y evaluaciones | Revisión | Consumo acumulado |
| --- | --- | --- | --- |
| 1 | El simulado devuelve la base sin JSON; fallan aceptación y comprobaciones públicas, pasa regresión. | No autorizada. | 1 desarrollador, 0 revisores. |
| 2 | Comienza con los bytes del candidato 1 y escribe la entrega sintética que supera las cuatro suites. | Aprobación simulada válida. | 2 desarrolladores, 1 revisor: 3/4. |

Es un resultado del fixture, no una implementación descubierta por un modelo.
La ruta de solicitud de cambios consume 2 desarrolladores y 2 revisores, 4/4,
con un cambio verificable y sin pasar el dictamen anterior a la nueva revisión.

Además, el 18 de octubre de 2026 se ejecutó una simulación sobre la base Git
real con las autoridades públicas intactas. En el primer intento se devolvió
la base conocida `c4122912…e422b`; en el segundo se colocó, exclusivamente en
la copia temporal, el inspector integrado conocido `8abca500…e7b87`. La partida
del segundo coincide exactamente con la primera entrega. La corrección pasó
14 métodos de aceptación, 153 de regresión, 6 de hallazgos y 7 de anidamiento.
La regresión se ejecutó tres veces: preparación y cada entrega. La revisión
devolvió una aprobación fija simulada: **2 desarrollos + 1 revisión = 3/4**,
código 0, 171,941 s y cero modelos reales. No es evidencia de generación ni de
contraste semántico por un modelo. El registro local, excluido de Git, es
`runs/20261018T173050Z_inspect-json_orchestrate_23829212760744e383085009979479eb/`;
`simulacion.json` identifica expresamente esta preparación con artefactos conocidos.

Para comprobar localmente sin modelos:

```bash
python3 -B -m unittest discover -s tests -p 'test_*project.py' -v
python3 -B -m unittest discover -s tests -v
```

Validación local final del 18 de octubre de 2026: **20 métodos nuevos superados
en 29,263 s** y **262 métodos en la regresión completa, en 132,736 s**, sin fallos
ni errores, código 0. Los 262 incluyen los 242 anteriores y los 20 nuevos; las
evaluaciones internas de los fixtures y la simulación con base real no se suman
a ese total. Durante el desarrollo se corrigió una incompatibilidad del mensaje
de progreso histórico y se repitieron sus pruebas. Estos resultados son locales,
no una ejecución de GitHub Actions ni un recorrido con modelos reales.

La revisión aislada añade [19 métodos con agentes simulados](../tests/test_isolated_review_project.py).
Cubren autorización tras timeout del origen, aprobación y cambios, desarrollo
fallido, candidatos alterados, autoridades distintas, evaluaciones fallidas,
incompletas o mezcladas, resúmenes/manifiestos incoherentes, reservas duplicadas
y fallo de persistencia, dos CLI simultáneas, presupuesto configurable y
predeterminado, CLI ausente, timeout, interrupción, respuesta inválida,
integridad, inmutabilidad del origen y ausencia de incorporación. Todas las
invocaciones usan ejecutables simulados y registros temporales; el timeout del
fixture se acorta explícitamente, sin cambiar los límites de producción.

Comandos ejecutados para esta implementación:

```bash
python3 -B -m unittest discover -s tests -p test_isolated_review_project.py -v
python3 -B -m unittest discover -s tests -v
```

Resultado del 18 de octubre de 2026: **281 métodos en 157,086 s**, sin fallos ni
errores, código 0, incluyendo las interfaces históricas y los 19 nuevos. Esta
regresión completa precede al último refuerzo del contraste del estado/código
de origen; no acredita ese cambio posterior. Tras el refuerzo, la repetición
final de los **19 métodos enfocados pasó en 48,932 s**, código 0. Los fixtures internos
no se suman a estos totales. La lectura del intento 2 real pasó el validador;
durante esa implementación no hubo llamadas reales al modelo ni nuevas
evaluaciones de esa entrega. Esas pruebas simuladas no se repitieron en el
contraste posterior ni se suman a sus siete comprobaciones enfocadas.

La revisión real adicional solicitó cambios; los dos defectos contrastados
siguen pendientes de corrección en la entrega experimental. No hay aprobación
del recorrido ni incorporación. Las pruebas simuladas verifican el mecanismo
del flujo; el experimento real muestra sus resultados y límites en esta tarea
conocida. Ninguno sustituye la decisión humana de incorporación.

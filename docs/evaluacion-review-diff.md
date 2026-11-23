# Evaluación de ocho diffs Python con review_diff

El protocolo y el corpus se incorporaron a `main` mediante la
[PR #34](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/34),
ya fusionada. Su preparación inicial se validó sin modelos. Después se
autorizaron por separado cuatro campañas, de `review-diff-real-01` a
`review-diff-real-04`. Cada sección recoge los resultados y la adjudicación
aprobada por Álvaro. A partir de la segunda se utiliza el diagnóstico de
timeout incorporado en la
[PR #35](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/35),
también fusionada. El modo C++ snapshot queda fuera.
`review_diff.py` conserva su interfaz y su política Codex;
`evaluate_review_diff.py` reutiliza sus materiales, esquema, validación
de citas y `run_review()`. No desarrolla, incorpora ni ejecuta candidatos.

## Casos y expectativas anteriores a la campaña

El [catálogo](../evals/review_diff/casos.json) es la fuente canónica: ocho IDs
neutros, dos versiones completas de `module.py`, criterios literales, SHA
completos de ambos commits, expectativa y justificación con un ejemplo razonado.
Solo se consideran las entradas del dominio declarado. Cuatro cambios conservan
el contrato; los otros cuatro introducen exactamente un defecto funcional D1.
Los ejemplos son evidencia razonada, **no resultados de haber ejecutado esos
candidatos**. La preparación analiza sintaxis y lee objetos Git; no los importa.

| Caso | Contrato entregado (resumen; texto literal en el catálogo) | Expectativa y evidencia |
| --- | --- | --- |
| caso_01 | Seleccionar enteros dentro de [low, high], inclusivo; conservar orden, duplicados, vacío y entrada. | Correcto. La comparación encadenada equivale a las dos desigualdades; `[1,2,2,3]`, límites 1 y 2 → `[1,2,2]`. |
| caso_02 | Contar todas las cadenas, suma de recuentos igual a longitud; vacío `{}`, sin mutación. | D1: sobrescribe con 1 en vez de acumular. `['a','a','b']` → `{'a':1,'b':1}`, esperado `{'a':2,'b':1}`. |
| caso_03 | Seleccionar enteros menores o iguales al límite; preservar orden, duplicados y vacío. | D1: cambia `<=` por `<`. `[2,3,3]`, límite 3 → `[2]`, esperado `[2,3,3]`. |
| caso_04 | Sumar una lista finita de enteros, incluidos negativos; vacío 0, sin mutación. | Correcto. `sum(values, 0)` conserva el neutro y las sumas del bucle; `[-2,5,-1]` → 2. |
| caso_05 | Último entero de una lista o `None` si está vacía; sin mutación. | D1: elimina la guarda. `[]` lanza `IndexError`, esperado `None`. |
| caso_06 | Mínimo número de lotes: count entero no negativo y size entero positivo. | Correcto. Cociente más uno si hay resto equivale al techo; `(7,3)` → 3 y `(0,3)` → 0. |
| caso_07 | Separar enteros negativos/no negativos en listas nuevas, sin perder orden, duplicados ni recuento; vacío `([],[])`. | Correcto. `<0` y `>=0` son una partición exhaustiva; `[-1,0,-1,2]` → `([-1,-1],[0,2])`. |
| caso_08 | Media con división real de hasta 1000 enteros entre -1000 y 1000; vacío 0, sin mutación. | D1: usa `//`. `[1,2]` → 1, esperado 1.5. El dominio acotado evita un problema previo de representabilidad de float. |

Los commits se reconstruyen en un repositorio Git bare privado con blobs, árboles,
autor, fecha, mensajes y formato SHA-1 fijos. No dependen de la configuración
personal ni del reloj. La preparación verifica los 16 SHA contra el catálogo;
las refs del repositorio sintético conservan los objetos. No se agregan esos
commits al historial del orquestador. No se promete identidad de los bytes
comprimidos de `.git` entre versiones de Git: sí los IDs de los objetos.

## Preparación y comprobación sin modelo

Desde la raíz de un clon completo, Python 3.12, Git y biblioteca estándar:

```bash
mkdir -p runs
python3 -B evaluate_review_diff.py check --output runs/review-diff-comprobacion-01
```

El destino debe ser nuevo y su padre existir. Este comando congela corpus,
protocolo, herramientas y vistas previas; crea **informes y juicios sintéticos**
marcados como tales, con cero invocaciones; conserva los archivos y escribe
`comprobacion.json` con resultados por caso y totales. No busca ni llama a Codex,
no necesita autenticación o red y no requiere Podman: aquí no se ejecuta Python
de un proyecto. Los agentes siguen la política Codex existente, fuera de la
frontera Podman de ejecución de pruebas.

`preparacion.json` contiene inventarios SHA-256, orden y configuración solicitada.
`preparacion/fuentes/` conserva los bytes y `git.json`/`cambios.patch` la revisión
del orquestador y el estado de las rutas relevantes, como `evaluate_reviewer.py`.
Los no versionados de esas rutas se conservan como fuentes aunque no aparezcan
en el diff Git. Cada `preparacion/caso_NN.json` es una vista previa reproducible.
Para comprobar una de ellas mediante la CLI de producción, usar los SHA completos
y los dos criterios literales de ese caso en el catálogo:

```bash
python3 -B - <<'PYTHON'
import json, subprocess, sys
from pathlib import Path
experiment = Path('runs/review-diff-comprobacion-01').resolve()
cases = json.loads((experiment/'preparacion/fuentes/evals/review_diff/casos.json').read_text())['casos']
for case in cases:
    command = [sys.executable, '-B', 'review_diff.py', '--repo', str(experiment/'preparacion/repo.git'),
               '--base', case['commits']['base'], '--candidate', case['commits']['candidato'],
               '--file', case['archivo']]
    for criterion in case['criterios']:
        command += ['--criterion', criterion]
    preview = json.loads(subprocess.check_output(command))
    assert preview == json.loads((experiment/'preparacion'/f"{case['id']}.json").read_text())
    print(case['id'], preview['estado'])
PYTHON
```

Cada contexto contiene únicamente las dos versiones seleccionadas, sus hashes,
el diff y los criterios. El workspace temporal del revisor contiene exactamente
`materiales.json` y `respuesta.schema.json`; recibe las instrucciones originales
de `review_diff`. **No se copian las expectativas, los contraejemplos del evaluador,
el catálogo, los informes sintéticos ni los juicios.** Los IDs de caso tampoco
se añaden al material. Esta separación de contexto no convierte el modo Codex de
solo lectura en una garantía de confidencialidad frente a un agente que incumpla
las instrucciones; se conserva el alcance del [piloto](revision-diff.md).

## Selección congelada para campañas nuevas

`prepare` admite las opciones `--model`, `--provider` y `--reasoning-effort`
descritas en [la selección del revisor](revision-diff.md#selección-explícita-y-trazabilidad-del-revisor).
Este ejemplo **ilustrativo** solo prepara archivos: los IDs `modelo-ejemplo` y
`proveedor_ejemplo` deben sustituirse por los admitidos por la instalación, con
el proveedor ya configurado. Preparar no llama a Codex ni reserva llamadas.

```bash
python3 -B evaluate_review_diff.py prepare --output runs/campana-nueva \
  --model modelo-ejemplo --provider proveedor_ejemplo --reasoning-effort high
# Revisar las ocho vistas y autorizar por separado antes de ejecutar:
# python3 -B evaluate_review_diff.py run --experiment runs/campana-nueva --invoke-model
```

El nuevo manifiesto `preparacion.json` usa **versión 2**. Congela la selección en
`preparacion/configuracion-revisor.json` (formato propio versión 1), incluido en
su inventario SHA-256 junto con las fuentes, incluido `reviewer_configuration.py`.
Ese archivo conserva `seleccion` con `model`, `provider` y `reasoning_effort`
(valor `null` si se omitieron) y la lista `argumentos_cli` que corresponde a ella.
El manifiesto conserva además la configuración solicitada; los parámetros
efectivos de la preparación son siempre `no consta`. Las vistas, los materiales,
el corpus, las expectativas, el orden y las instrucciones no cambian.
Se congelan los IDs seleccionados; no se copia la definición privada del
proveedor ni se resuelven los valores predeterminados que herede Codex.

`run` utiliza esa selección para los ocho casos y no admite opciones para
sobrescribirla. Antes de reservar el lanzamiento comprueba hashes, coherencia
entre selección y manifiesto, fuentes congeladas y disponibilidad local del ID
de proveedor explícito. Tras cada revisión contrasta sus argumentos con la
selección congelada y con el comando del registro original del proceso. Una
incoherencia es un fallo técnico y detiene la campaña. Se conserva el presupuesto
de ocho llamadas, una por caso, 180 s y cero reintentos.

Cada registro nuevo separa configuración solicitada, opciones realmente
enviadas y parámetros efectivos con procedencia, según el formato documentado
en `revision-diff.md`. La igualdad de argumentos no implica igualdad de
parámetros aplicados por el servicio. En ausencia de evidencia estructurada
siguen figurando como `no consta`.

La lectura de archivos conservados, `judgments` y `score` admiten los manifiestos
de **versión 1**, que no contienen el nuevo archivo ni los nuevos campos del
registro. No se infieren selecciones ni parámetros efectivos retrospectivos,
no se modifican esas preparaciones y no se exige disponer del proveedor local
para puntuarlas. El lanzamiento exige las fuentes del protocolo congelado;
no se utiliza el código nuevo para relanzar o reanudar campañas históricas.
Las campañas 01 a 03 conservan su formato y resultados históricos. La campaña
04 utiliza el manifiesto de versión 2 con selección explícita.

## Comando y reserva de la campaña real

Esta secuencia documenta el lanzamiento histórico de `review-diff-real-01`
desde su commit revisado limpio. **La campaña ya fue lanzada y terminó
incompleta: no repetir ni reanudar estos comandos.** Su directorio original
estaba ausente al preparar y documentar la segunda campaña; estos comandos
no indican que sus archivos sigan disponibles.

```bash
mkdir -p runs
python3 -B evaluate_review_diff.py prepare --output runs/review-diff-real-01
# Revisar preparacion.json y las ocho vistas previas antes de autorizar el envío.
python3 -B evaluate_review_diff.py run --experiment runs/review-diff-real-01 --invoke-model
```

`prepare` no usa modelos. `run --invoke-model` autoriza el envío y llama a
`review_diff.run_review()` una sola vez por caso en orden fijo: **hasta ocho
llamadas, una por caso, 180 s por llamada y cero reintentos**. Los preflights
locales de versión/ayuda de Codex no son llamadas al modelo. La creación exclusiva
de `lanzamiento/` es la reserva permanente: se rechaza repetir o reanudar, incluso
tras un fallo o interrupción. No abrir otra preparación para ocultar intentos;
cualquier nueva campaña debe declararse y aprobarse por separado.

Un informe disponible continúa al siguiente caso aunque esté vacío o contenga
hallazgos. Un fallo técnico (CLI, timeout, respuesta inválida, integridad,
archivo incompleto o cambio de versión/argumentos de Codex) detiene el lanzamiento;
los casos restantes quedan `no_ejecutado`, no como defectos omitidos. Se conservan
materiales, respuesta original, eventos, diagnósticos, reservas e inventarios de
cada revisión. El código 0 de `run` significa ocho informes disponibles, **no ocho
respuestas correctas**; 1 es campaña incompleta; 2 es entrada/reserva inválida.
No se reemplaza evidencia de una ejecución anterior.

Se registra la configuración solicitada y la versión/argumentos observados de
CLI; se exige continuidad de estos últimos. `review_diff` no fija modelo,
proveedor o esfuerzo en estas campañas históricas ni cuando se omiten las nuevas
opciones: pueden proceder de la configuración Codex personal. Los
parámetros efectivos quedan «no consta» salvo evidencia de los eventos; no se
leen ni publican credenciales. El protocolo es repetible, no una promesa de
determinismo del servicio ni de igualdad de parámetros efectivos.

## Juicio humano y puntuación de archivos conservados

```bash
python3 -B evaluate_review_diff.py judgments --experiment runs/review-diff-real-01 \
  --output runs/review-diff-real-01/juicios.json
# Una persona rellena autor, revision_completa, justificacion y cada hallazgo.
python3 -B evaluate_review_diff.py score --experiment runs/review-diff-real-01 \
  --judgments runs/review-diff-real-01/juicios.json > runs/review-diff-real-01/puntuacion.json
```

El lector no importa fuentes ni ejecuta materiales archivados. Verifica la
preparación, los hashes de cada informe, las citas con el validador existente y
la correspondencia entre respuesta original y resumen. Admite los registros de
este protocolo, que envuelven el formato original de `review_diff`; no acepta
un informe suelto sin vincularlo a su preparación. Los hashes son integridad local,
no una firma frente a reescribir toda la evidencia.

Cada caso necesita `revision_completa: true` y razón, incluso si no hay hallazgos.
Para cada hallazgo, una persona debe declarar `respaldado` (booleano), justificarlo
con contrato/código y, si detecta la regresión fijada, asignar `defecto: "D1"`.
Las posiciones y hashes vinculan el juicio al hallazgo y al lanzamiento exactos.
No basta con una cita válida, una palabra clave o un dictamen del modelo.

- D1 respaldado se cuenta una vez por caso, aunque aparezca varias veces; se
  muestra aparte el número de menciones duplicadas.
- Sin D1 en un informe válido y juzgado, el defecto esperado está omitido.
- Hallazgos no respaldados en casos correctos son falsos; se cuentan hallazgos
  y casos afectados por separado.
- Hallazgos no respaldados adicionales en casos defectuosos se cuentan aparte;
  no se convierten en detecciones ni se ocultan por haber detectado D1.
- Un hallazgo respaldado que no corresponde a D1 se marca como adicional
  respaldado y exige revisar la expectativa; no se cambia la verdad fijada ni
  se convierte automáticamente en falso.
- Juicios pendientes y fallos técnicos no se computan como omisiones del revisor.
  Un archivo alterado/incompleto es fallo técnico. Un denominador cero produce
  proporción `null`, nunca un cero inventado.

Se muestran por caso los denominadores de defectos, correctos y hallazgos
evaluables. Los totales separan 8 casos planificados, 4 correctos y 4 defectos,
cobertura, detección/omisión entre defectos evaluables, correctos afectados entre
correctos juzgados y adicionales no respaldados entre hallazgos en defectuosos.
Fallos técnicos y no ejecutados usan denominador 8. Publicar siempre numerador,
denominador y no evaluables; no esconder la cobertura tras una proporción alta.
`score` devuelve 1 si faltan juicios o hay adicionales respaldados; 0 significa
puntuación disponible, que puede incluir fallos técnicos; 2 rechaza evidencia o
juicio incoherentes. No es una aprobación para incorporar cambios.

## Lo comprobado con los fixtures, no con un revisor real

Los [informes sintéticos](../evals/review_diff/informes_sinteticos.json) contienen
adjudicaciones ficticias, identificadas como tales. `check` escribe esas razones
en `juicios_sinteticos.json`; no afirma que las haya firmado una persona.
Se ensamblan independientemente para probar el lector y todos sus recuentos:
no simulan el orden de un lanzamiento real, que se detendría en caso_07 y
dejaría caso_08 sin ejecutar. Esa detención se comprueba con el adaptador simulado.

| Caso | Resultado sintético | Detectados / evaluables | Omitidos | Falsos en correcto | Adicional no respaldado | Duplicados |
| --- | --- | --- | --- | --- | --- | --- |
| caso_01 | Informe vacío | 0 / 0 | 0 | 0 | 0 | 0 |
| caso_02 | D1 dos veces y una afirmación adicional falsa | 1 / 1 | 0 | 0 | 1 | 1 |
| caso_03 | Informe vacío | 0 / 1 | 1 | 0 | 0 | 0 |
| caso_04 | Afirmación falsa sobre negativos | 0 / 0 | 0 | 1 | 0 | 0 |
| caso_05 | D1 respaldado | 1 / 1 | 0 | 0 | 0 | 0 |
| caso_06 | Informe vacío | 0 / 0 | 0 | 0 | 0 | 0 |
| caso_07 | Fallo técnico ficticio | no evaluable | no evaluable | no evaluable | no evaluable | no evaluable |
| caso_08 | Informe vacío | 0 / 1 | 1 | 0 | 0 | 0 |

Resultado esperado del fixture: 7/8 informes puntuados; detección 2/4 y omisión
2/4; un falso hallazgo afecta a 1/3 correctos evaluables (otro correcto no es
evaluable); un adicional no respaldado entre 4 hallazgos en defectuosos; una
mención duplicada; 1/8 fallos técnicos. **Estas cifras verifican la puntuación,
no miden calidad, sensibilidad ni tasa de alucinación de un modelo.**

Pruebas enfocadas sin modelo:

```bash
python3 -B -m unittest discover -s tests -p test_evaluate_review_diff.py -v
python3 -B -m unittest discover -s tests -p test_review_diff.py -v
python3 -B -m unittest discover -s tests -p test_review_snapshot.py -v
git diff --check
```

Comprueban los commits reproducibles, las ocho vistas previas por la CLI real,
el contexto limitado, juicios explícitos y ligados a sus archivos, denominadores,
duplicados, archivos alterados, reserva sin repetición y detención sin reintentos
con el adaptador simulado. Los dos jobs existentes de CI siguen comprobando la
suite ordinaria y las 13 integraciones reales de Podman; estas últimas acreditan
la frontera de pruebas de proyectos, **no una campaña real de revisión**.
Los recuentos y enlaces del SHA final se registran en la PR.

## Resultado parcial real: review-diff-real-01

Se realizó un único lanzamiento desde el SHA revisado
`67e16983f511dedb04b81cddd5d3ecffb9a3156c`, con las ocho vistas previas comprobadas
antes de invocar al revisor. Se registraron **3 invocaciones**, una por caso y
sin reintentos. La campaña terminó `incompleta`, con salida 1, al detenerse en
`caso_03`. Los dos informes disponibles se adjudicaron con decisiones aprobadas
por Álvaro, conservando los hashes e índices del juicio:

- `caso_01`: informe sin hallazgos. Se confirmó la equivalencia de la comparación
  encadenada para el dominio del contrato, incluidos límites, orden y duplicados.
- `caso_02`: el único hallazgo se marcó respaldado y correspondiente a D1.
  La comprensión asigna 1 a cada clave, perdiendo los recuentos repetidos.
- `caso_03`: fallo técnico por timeout, no un defecto omitido por el revisor.
- `caso_04` a `caso_08`: sin ejecutar, no informes vacíos ni resultados negativos.

La puntuación parcial documentada históricamente distingue cobertura y resultados
evaluables:

| Magnitud | Recuento y denominador |
| --- | --- |
| Informes adjudicados | **2/8** casos planificados |
| Cobertura de defectos | **1/4** defectos planificados; 3 no evaluables |
| Cobertura de casos correctos | **1/4** correctos planificados; 3 no evaluables |
| Defectos detectados | **1/1** defecto evaluable |
| Defectos omitidos | **0/1** defecto evaluable |
| Casos correctos con falsos hallazgos | **0/1** caso correcto evaluable |
| Fallos técnicos entre invocaciones realizadas | **1/3** invocaciones |
| Fallos técnicos entre casos planificados | **1/8** casos |
| Casos sin ejecutar | **5/8** casos planificados |

El resultado 1/1 describe únicamente el defecto evaluable; no acredita detección
de los otros tres defectos ni éxito sobre los ocho casos. Los no evaluables no
se cuentan como omisiones. Estas cifras reales parciales son distintas de los
recuentos sintéticos de la sección anterior y no estiman fiabilidad general.

### Timeout de caso_03: observación y límites del diagnóstico

El último evento observable, en la línea 5 de `eventos.jsonl`, fue
`item.completed` para `command_execution`: la lectura de `materiales.json`
mediante `/bin/bash -lc 'cat materiales.json'` terminó con código **0**, y su
salida coincide con los materiales congelados. Después no consta respuesta
final ni evento `turn.completed`; `stderr` está vacío.

El proceso registra `tiempo_agotado`, límite de 180 s y salida **-9**. Su
`duracion_segundos`, calculada con el reloj monotónico, es **180.018 s**
(redondeada de 180.01781967599527). Entre las marcas UTC de inicio
`2026-11-16T10:56:16.277374Z` y fin `2026-11-16T11:12:07.304370Z` hay
**951.027 s** (redondeados de 951.026996). Son mediciones distintas y no se
sustituye una por otra. **No se pudo determinar la causa del timeout ni de
la diferencia entre relojes con la evidencia conservada.** La lectura finalizada
no permite atribuir la demora a `cat`, al modelo, al servicio o al anfitrión.

La documentación histórica situó los originales en `runs/review-diff-real-01/`,
fuera de Git: `preparacion/`, `lanzamiento/`, `juicios.json`,
`puntuacion-parcial.json` y `resumen-adjudicacion-parcial.json`. La ruta indicada
posteriormente fue `/tmp/cro-review-diff-evaluation/runs/review-diff-real-01/`.
Ese directorio no estaba disponible al preparar ni al documentar la segunda
campaña. Los resultados anteriores se conservan como evidencia histórica
publicada en la PR #34; no se presentan como una nueva validación de archivos
originales actualmente accesibles. No se recreó ni modificó aquella campaña.
Cualquier campaña nueva requiere autorización separada.

## Resultado parcial adjudicado: review-diff-real-02

Se realizó un único lanzamiento con el protocolo y puntuador del commit
`9685f4270158b0a716f6ab34c3326371208ce624`, desde un worktree en ese mismo SHA.
Se conservaron los ocho casos, su orden y expectativas, el límite de **180 s
por caso**, el máximo de ocho llamadas y una llamada por caso. Se registraron
**siete invocaciones y cero reintentos**. El lanzamiento se detuvo ante el
primer fallo técnico, en `caso_07`, y dejó `caso_08` sin ejecutar.

### Preparación, comparación y procedencia

Las ocho vistas previas se validaron con la CLI de producción y se compararon
con una **reconstrucción reproducible del piloto desde Git**, usando
`67e16983f511dedb04b81cddd5d3ecffb9a3156c`. Coincidieron el catálogo y su orden,
los materiales, las instrucciones y el esquema de las ocho vistas. Como la
ruta original de `review-diff-real-01` estaba ausente, esta comprobación no fue
un cotejo directo con sus archivos archivados. La limitación quedó registrada
en `validacion/resultado.json` de la segunda campaña.

El manifiesto congela `timeout_diagnostics.py` entre las fuentes. La preparación
pasó `validate_preparation(..., launching=True)` y el `check` documentado,
ejecutado aparte con fixtures sintéticos y cero invocaciones. Las expectativas
y adjudicaciones quedaron fuera del material entregado al revisor.

Los seis informes disponibles se revisaron estáticamente contra contratos,
base, candidato y expectativas congeladas. **Álvaro aprobó las seis decisiones
procedentes del análisis asistido**: revisiones completas sin hallazgos para
`caso_01`, `caso_04` y `caso_06`; hallazgo 1 respaldado y asignado a D1 para
`caso_02`, `caso_03` y `caso_05`. Se conservaron índices y hashes de los hallazgos,
la propuesta asistida original y una copia de `juicios.json` anterior a completarlo.
`aprobacion-adjudicacion.json` vincula la aprobación humana, la procedencia
asistida, los juicios y la puntuación mediante hashes. Los ejemplos de las
justificaciones son razonados, no resultados de ejecutar candidatos.

### Estado por caso y denominadores

| Caso | Estado de la campaña | Invocaciones | Hallazgos del informe | Adjudicación o límite |
| --- | --- | --- | --- | --- |
| caso_01 | `informe_disponible` | 1 | 0 | Sin hallazgos; conserva selección inclusiva, orden y duplicados. |
| caso_02 | `informe_disponible` | 1 | 1 | Respaldado, D1: pierde los recuentos repetidos. |
| caso_03 | `informe_disponible` | 1 | 1 | Respaldado, D1: excluye los valores iguales al límite. |
| caso_04 | `informe_disponible` | 1 | 0 | Sin hallazgos; conserva suma, negativos y vacío. |
| caso_05 | `informe_disponible` | 1 | 1 | Respaldado, D1: `IndexError` en vacío en vez de `None`. |
| caso_06 | `informe_disponible` | 1 | 0 | Sin hallazgos; conserva el mínimo de lotes mediante cociente y resto. |
| caso_07 | `fallo_tecnico` | 1 | No hay informe | Timeout; caso no evaluable para calidad. |
| caso_08 | `no_ejecutado` | 0 | No hay informe | Sin llamada; su defecto esperado queda no evaluable. |

`run` terminó con **código 1**, estado `incompleta`: hubo seis informes de los
ocho previstos. Después de la aprobación humana, `score` terminó con **código
0**, estado `puntuacion_disponible`: pudo puntuar los seis informes adjudicados.
Ese 0 corresponde a la operación de puntuación; no convierte el lanzamiento
en completo ni acredita los dos casos no evaluables.

| Magnitud | Recuento y denominador |
| --- | --- |
| Informes adjudicados | **6/8** casos planificados |
| Cobertura de defectos | **3/4** defectos planificados; 1 no evaluable |
| Cobertura de casos correctos | **3/4** correctos planificados; 1 no evaluable |
| Defectos detectados | **3/3** defectos evaluables |
| Defectos omitidos | **0/3** defectos evaluables |
| Casos correctos con falsos hallazgos | **0/3** correctos evaluables; 0 falsos hallazgos |
| Adicionales no respaldados | **0/3** hallazgos en casos defectuosos evaluables |
| Adicionales respaldados | **0** entre 3 hallazgos evaluables |
| Menciones duplicadas | **0** entre 3 menciones de D1 |
| Juicios pendientes | **0/6** informes disponibles |
| Fallos técnicos entre invocaciones realizadas | **1/7** invocaciones |
| Fallos técnicos entre casos planificados | **1/8** casos |
| Casos sin ejecutar | **1/8** casos planificados |

Los recuentos proceden de `puntuacion-parcial.json`, contrastado con una nueva
evaluación de los mismos juicios mediante el puntuador del SHA indicado.
Coberturas y denominadores complementarios se derivan de esos recuentos y de
las siete invocaciones archivadas. El correcto `caso_07` y el defecto de
`caso_08` no se cuentan como éxitos, falsos ni omisiones del revisor.

### Timeout de caso_07: mediciones conservadas

El registro conserva literalmente estos valores:

```text
inicio_utc:                  2026-11-17T16:06:18.635577Z
timeout_utc:                 2026-11-18T08:44:08.986383Z
fin_utc:                     2026-11-18T08:44:09.003819Z
limite_segundos:             180
estado:                      tiempo_agotado
codigo_salida:               -9
duracion_segundos:           180.01876194499982
duracion_monotonica_segundos: 180.001328714
duracion_boottime_segundos:   59870.350848044
ultimo_evento.tipo:          turn.started
```

Entre inicio UTC y detección hay **59870.350806 s**; hasta el fin UTC hay
**59870.368242 s**. El intervalo hasta detección coincide aproximadamente con
CLOCK_BOOTTIME, con una diferencia de **0.000042044 s**, unos 42 microsegundos.
La duración monotónica del diagnóstico termina al detectar el timeout;
`duracion_segundos` incluye la terminación del proceso. El último evento
completo registrado fue `turn.started`, sin tipo de ítem; no consta una
respuesta final ni `turn.completed` y `stderr` está vacío.

**La causa del timeout y de la diferencia con el reloj monotónico sigue
indeterminada.** La coincidencia aproximada de UTC y CLOCK_BOOTTIME es una
observación; no establece una explicación causal. Cualquier explicación
requeriría evidencia adicional y debe mantenerse como hipótesis.

### Alcance y conservación de la evidencia

Se observó más cobertura en la segunda campaña: **6/8** informes frente a
**2/8** en la primera, y **3/4** frente a **1/4** en cada clase de casos.
Son campañas independientes, con distintos denominadores evaluables. La
diferencia observada **no demuestra un efecto causal del cambio de diagnóstico**
ni una mejora del modelo; no es una comparación controlada.

El alcance son **ocho ejemplos sintéticos pequeños de Python**, cuatro correctos
y cuatro con un único defecto esperado. Una detección 3/3 entre los defectos
evaluables no acredita el cuarto defecto, generalización a repositorios reales,
fiabilidad global ni resultados en C++.

En las siete invocaciones se registró `codex-cli 0.167.0`. La configuración
solicitada no fijó modelo, proveedor ni esfuerzo; la preparación los registra
como «no consta» en la configuración efectiva. Los eventos conservados tampoco
acreditan esos parámetros efectivos. No se deducen de la versión de CLI ni de
una configuración local observada, ni se presupone igualdad entre campañas.

La evidencia de esta segunda campaña sigue exclusivamente en local, bajo
`runs/review-diff-real-02/`: preparación y fuentes congeladas, validación,
lanzamiento y reservas, propuesta asistida, copia previa de juicios,
`juicios.json`, `aprobacion-adjudicacion.json` y `puntuacion-parcial.json`.
Ambas campañas mantienen sus resultados separados y fuera de Git. Esta
actualización documental utiliza sólo registros existentes: no modifica
campañas, no reanuda lanzamientos ni realiza nuevas llamadas a modelos.

## Resultado completo adjudicado: review-diff-real-03

La tercera campaña independiente se preparó y ejecutó desde un worktree en
`9e3540f78ef7eb27432c7eba4e398c178c2dfbc5`, usando el protocolo y puntuador de
ese mismo SHA. Se conservaron corpus, expectativas, orden, prompt y política
del revisor. Las ocho vistas previas coincidieron con las de
`review-diff-real-02`, incluidos materiales, instrucciones y esquema; también
se comprobaron las fuentes de la política y el presupuesto congelado.

Hubo **un único lanzamiento, ocho llamadas, una por caso y cero reintentos**,
con el límite de **180 s por caso** y la detención ante el primer fallo técnico
habilitada. `run` terminó con **código 0**, estado `completada`: produjo los
ocho informes y no registró fallos técnicos ni timeouts. Ningún caso quedó sin
ejecutar. Esta campaña ya tiene lanzamiento y no debe repetirse ni reanudarse.

### Adjudicación humana con procedencia asistida

Se validaron preparación, ocho registros, ocho respuestas, citas, reservas,
índices y hashes. La propuesta de análisis asistido revisó cada informe contra
contratos, base, candidato y expectativas de esta tercera campaña, sin ejecutar
candidatos. Los ejemplos de sus justificaciones son razonados por inspección.

**Álvaro aprobó las ocho decisiones**. `juicios.json` registra autor humano
«Álvaro», ocho revisiones completas y las justificaciones específicas de esta
campaña. Se conservó una copia previa en `juicios.antes-adjudicacion.json`.
La propuesta original `propuesta-adjudicacion-asistida.json` permanece intacta;
`aprobacion-adjudicacion.json` documenta su aprobación posterior y vincula por
hashes propuesta, copia previa, juicios completados y puntuación.

| Caso | Estado del lanzamiento | Llamadas | Hallazgos | Adjudicación aprobada |
| --- | --- | --- | --- | --- |
| caso_01 | `informe_disponible` | 1 | 0 | Sin hallazgos; selección inclusiva equivalente. |
| caso_02 | `informe_disponible` | 1 | 1 | Hallazgo 1 respaldado, D1: pérdida de recuentos repetidos. |
| caso_03 | `informe_disponible` | 1 | 1 | Hallazgo 1 respaldado, D1: exclusión del límite inclusivo. |
| caso_04 | `informe_disponible` | 1 | 0 | Sin hallazgos; suma entera equivalente. |
| caso_05 | `informe_disponible` | 1 | 1 | Hallazgo 1 respaldado, D1: `IndexError` para lista vacía. |
| caso_06 | `informe_disponible` | 1 | 0 | Sin hallazgos; mínimo de lotes equivalente. |
| caso_07 | `informe_disponible` | 1 | 0 | Sin hallazgos; partición conserva cero, orden, duplicados y vacío. |
| caso_08 | `informe_disponible` | 1 | 1 | Hallazgo 1 respaldado, D1: división entera en vez de media real. |

Después de esa aprobación, el comando `score` del SHA indicado terminó con
**código 0**, estado `puntuacion_disponible`. Su salida se guardó directamente
en `puntuacion.json` y se contrastó con un nuevo cálculo local sobre los mismos
juicios: coincidió exactamente. El 0 de `run` acredita ocho informes disponibles;
el 0 de `score` acredita una puntuación disponible con juicios aprobados.

| Magnitud | Recuento y denominador |
| --- | --- |
| Informes adjudicados | **8/8** casos planificados |
| Cobertura de defectos | **4/4** defectos planificados; 0 no evaluables |
| Cobertura de casos correctos | **4/4** correctos planificados; 0 no evaluables |
| Defectos detectados | **4/4** defectos evaluables |
| Defectos omitidos | **0/4** defectos evaluables |
| Casos correctos con falsos hallazgos | **0/4** correctos evaluables; 0 falsos hallazgos |
| Adicionales no respaldados | **0/4** hallazgos en casos defectuosos evaluables |
| Adicionales respaldados | **0** entre 4 hallazgos evaluables |
| Menciones duplicadas | **0** entre 4 menciones de D1 |
| Juicios pendientes | **0/8** informes disponibles |
| Fallos técnicos entre casos planificados | **0/8** casos |
| Fallos técnicos entre invocaciones realizadas | **0/8** invocaciones |
| Casos sin ejecutar | **0/8** casos planificados |

Las métricas de calidad proceden de la salida real del puntuador; las coberturas
y denominadores complementarios se derivan de sus recuentos y del registro de
invocaciones. No se añadieron resultados esperados manualmente a la puntuación.

### Duración e inhibidor temporal observado

Antes de las llamadas se comprobaron localmente `systemd-inhibit`, su versión
y ayuda, y un proceso sintético corto acreditó adquisición de `sleep:idle` en
modo `block`, observación del bloqueo activo y retirada al terminar. La prueba
no llamó a modelos. Quedó registrada en `validacion/prueba-inhibidor.json`.

El mismo mecanismo, `systemd-inhibit --what=sleep:idle --mode=block`, envolvió
el supervisor que ejecutó `run` una sola vez. El bloqueo propio se observó antes
de iniciar las llamadas, en **siete muestras durante el intervalo de `run`** y
después de su retorno. Tras terminar el comando protegido se comprobó que ya
no figuraba su inhibidor. La protección fue temporal, ligada a ese comando;
no se hicieron cambios persistentes en la configuración energética.

Las mediciones externas del intervalo de `run`, tomadas por el supervisor,
fueron:

| Reloj | Muestra de inicio | Muestra de fin | Duración derivada (s) |
| --- | --- | --- | --- |
| UTC | `2026-11-19T11:27:26.777801Z` | `2026-11-19T11:29:18.435418Z` | **111.657617** |
| Monotónico | `35387.274569259` | `35498.932192576` | **111.657623317** |
| CLOCK_BOOTTIME | `177934.663597988` | `178046.321221604` | **111.657623616** |

Los valores corresponden al intervalo alrededor de la invocación de `run`,
no a una suma de duraciones individuales de revisión. El comando completo,
versiones, marcas y muestras se conservan en `validacion/ejecucion-inhibida.json`
y `validacion/run-fin.json`; las observaciones periódicas están en
`validacion/inhibidor-durante.jsonl`. Se registraron Python **3.12.3**, Git
**2.43.0**, `codex-cli 0.167.0` y `systemd 255 (255.4-1ubuntu8.18)`.

Modelo, proveedor y esfuerzo **efectivos: «no consta»**, conforme a los eventos
y metadatos conservados en `validacion/configuracion-efectiva.json`. La
configuración local declarada se registró por separado y no se usa como prueba
de los parámetros efectivos del servicio. No se publican credenciales ni
volcados completos de configuración.

### Límites de la observación y conservación

Las tres campañas mantienen resultados independientes y sus propios
denominadores. Esta ejecución completa con inhibidor es una observación de
un único lanzamiento: **no establece por sí sola la causa de los timeouts de
las campañas anteriores ni una mejora de calidad del modelo**. La causa de
aquellos timeouts sigue indeterminada. No hay una comparación controlada ni
evidencia que acredite igualdad de configuración efectiva entre campañas.

El alcance continúa siendo **ocho ejemplos sintéticos pequeños de Python**,
cuatro correctos y cuatro con un defecto esperado. Los resultados adjudicados
describen esos ocho ejemplos; no acreditan generalización a repositorios reales,
fiabilidad global ni resultados en otros lenguajes.

La evidencia de la tercera campaña permanece fuera de Git, separada bajo
`runs/review-diff-real-03/`. Se conservan preparación y fuentes, ocho registros,
respuestas y reservas, evidencia del inhibidor, propuesta asistida, copia previa,
`juicios.json`, `aprobacion-adjudicacion.json` y `puntuacion.json`. El resumen de
ejecución original se mantiene como registro anterior a la adjudicación; la
aprobación posterior consta por separado. No se modifican las campañas anteriores.
Esta publicación añade sólo el resumen documental, con cero llamadas nuevas
a modelos, sin repetir ni reanudar ningún lanzamiento.

## Resultado completo adjudicado: review-diff-real-04

La cuarta campaña se lanzó el 21 de noviembre de 2026 desde
`3800d587353c409c953ad9daf790c12c42924c99`, el merge de la
[PR #38](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/38).
La preparación usó un manifiesto de versión 2. Sus ocho vistas previas
coincidieron con los materiales, las instrucciones y el esquema originales
conservados de la campaña 03. El corpus y las expectativas también coincidieron.

Codex CLI 0.170.0 recibió en los ocho casos los argumentos congelados de la
selección solicitada (`gpt-6.1-sol`, `openai`, `high`).

```bash
--model gpt-6.1-sol \
--config 'model_reasoning_effort="high"' \
--config 'model_provider="openai"'
```

Los parámetros efectivos de modelo, proveedor y esfuerzo figuran como
**«no consta»** en los ocho registros, al faltar la evidencia estructurada que
requiere el protocolo.

El lanzamiento terminó con código 0 y estado `completada`. Las ocho
invocaciones entregaron informes válidos en un único lanzamiento, con una
invocación por caso y cero reintentos. El inhibidor `sleep:idle` en modo
`block` se observó en diez muestras y se comprobó su retirada. La duración
externa fue **98,36 s** por reloj monotónico e incluye las comprobaciones
previas y el lanzamiento. Los intervalos UTC y `CLOCK_BOOTTIME` también
redondean a 98,36 s.

Álvaro aprobó el análisis asistido de los ocho informes. Los casos 01, 04,
06 y 07 se adjudicaron sin hallazgos. En los casos 02, 03, 05 y 08, el
hallazgo 1 se adjudicó como respaldado y correspondiente a D1. La
revalidación comprobó citas, índices y hashes. Para puntuar se utilizaron
las fuentes archivadas del protocolo, verificadas byte por byte contra
Git. `score` devolvió código 0 y estado `puntuacion_disponible`.

| Magnitud | Recuento y denominador |
| --- | --- |
| Informes válidos y casos puntuados | **8/8** planificados |
| Cobertura de casos con defecto | **4/4** planificados |
| Cobertura de casos correctos | **4/4** planificados |
| Defectos detectados | **4/4** evaluables |
| Defectos omitidos | **0/4** evaluables |
| Casos correctos con falsos hallazgos | **0/4** evaluables, con 0 hallazgos falsos |
| Adicionales no respaldados | **0/4** hallazgos en casos con defecto |
| Adicionales respaldados | **0/4** hallazgos evaluados |
| Menciones duplicadas | **0/4** menciones de D1 |
| Juicios pendientes | **0/8** informes |
| Fallos técnicos | **0/8** casos y **0/8** invocaciones |
| Casos sin ejecutar | **0/8** planificados |

La campaña comprueba el registro de los argumentos explícitos en un
lanzamiento completo. La puntuación se circunscribe a los ocho ejemplos
sintéticos del corpus y el intervalo medido describe ese lanzamiento.
La evidencia local incluye la preparación, los registros, el resumen
operativo, las mediciones del inhibidor, los juicios, la constancia de
aprobación y la salida original de `score`.

## Piloto adjudicado de cuatro cambios históricos

`piloto-review-diff-historico-01` revisó cuatro cambios reales desde
`fb67b98c649413d4ff8b2c98281daf69d0197344`. Cada vista incluyó un archivo
Python modificado, sus versiones base y candidata, el diff y criterios
explícitos. Las expectativas y las pruebas históricas se consultaron durante
la adjudicación asistida, que Álvaro aprobó después.

| Caso y archivo | Base y candidato | Resultado adjudicado y antecedente |
| --- | --- | --- |
| 01 · Orquestador · `booking_batch.py` | [Base `8e6415f`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/8e6415f117d1056f560801574297890d5ead9e17) · [Candidato `9318c5b`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/9318c5b02c20daa7362194f40a2e4c2ee36ce38d) | Sin hallazgos en el recorte de lectura y publicación del lote. [PR #25](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/25) |
| 02 · ShiftLab · `experiments/abstention.py` | [Base `67d8d23`](https://github.com/alvaro-salvador-huertas/shift-lab/commit/67d8d230e61737f741d0c5ed4f648699abadcdc5) · [Candidato `67c6756`](https://github.com/alvaro-salvador-huertas/shift-lab/commit/67c67567ad0a8b92dce674350613f94a271b5436) | Un hallazgo respaldado. Un fallo de codificación UTF-8 durante la escritura puede dejar artefactos parciales. [Corrección `5608f77`](https://github.com/alvaro-salvador-huertas/shift-lab/commit/5608f77f7d7e4f25d02d0bfb27bb1a758f620da8) |
| 03 · Orquestador · `inspect_run.py` | [Base `c8a38c9`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/c8a38c9bfb7d8105371567d8b7a6854d1f048d33) · [Candidato `7bcf3e3`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/7bcf3e35752f6819958fe65926e5141fbe2b0e75) | Sin hallazgos en el recorte de avisos AST del modo JSON. [PR #9](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/9) |
| 04 · Orquestador · `plan_project.py` | [Base `faed5dd`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/faed5ddb655500e7e81350301cc3b8d625bf1f5b) · [Candidato `19b7b2f`](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/commit/19b7b2f65d5bb3f6ab8cc8a5ebfa573bc486ccdf) | Sin hallazgos en el recorte de entrega de materiales al planificador. [PR #17](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/17) |

Álvaro confirmó que habría pedido cambios antes de fusionar el commit
intermedio de ShiftLab. Por inspección, el candidato crea el destino antes
de codificar los archivos, y la corrección codifica primero. Su prueba
histórica introduce un sustituto Unicode aislado en el contenido JSON y
exige un diagnóstico y la ausencia del destino. La variante del informe
con un nombre de archivo POSIX quedó **no verificada**.
[Prueba histórica de ShiftLab](https://github.com/alvaro-salvador-huertas/shift-lab/blob/5608f77f7d7e4f25d02d0bfb27bb1a758f620da8/tests/test_abstention_from_results.py#L105-L122)

Hubo **4/4 intentos autorizados**, **4/4 informes válidos**, **0/4 fallos
técnicos** y cero reintentos. Se detectó **1/1 regresión conocida evaluable**
y hubo **0/3 casos correctos evaluables con hallazgos no respaldados**.
El piloto cubre cuatro recortes seleccionados y su adjudicación fue estática.
Las cifras describen esos recortes y el ahorro de tiempo queda **«no medido»**.
Se enviaron los argumentos de la selección `gpt-6.1-sol`, `openai`, `high`.
Modelo, proveedor y esfuerzo efectivos figuran como **«no consta»**.
Los informes y registros de adjudicación se conservan en local, fuera de Git.

# check-booking: disponibilidad local

La herramienta [check_booking.py](../../../check_booking.py) está incorporada
explícitamente. Usa solo biblioteca estándar y consulta un archivo JSON local:

```bash
python3 -B check_booking.py solicitud.json
```

Ejemplo sintético de `solicitud.json`:

```json
{
  "solicitud": {
    "recurso": "Sala Norte",
    "inicio": "2026-10-20T10:00:00Z",
    "fin": "2026-10-20T11:00:00Z"
  },
  "reservas": []
}
```

Devuelve `{"disponible": true, "conflictos": []}`. Si `reservas` contiene
`{"id":"r-2","recurso":"Sala Norte","inicio":"2026-10-20T10:30:00Z","fin":"2026-10-20T11:30:00Z"}`,
devuelve `{"disponible": false, "conflictos": ["r-2"]}`. En ambos casos:
código **0**, un único JSON en stdout y stderr vacío. Un conflicto no es un
error de consulta. Archivo/entrada inválidos usan **1**, argumentos incorrectos
**2**; los errores dejan stdout vacío. `-h` y `--help` muestran ayuda.

Valida el documento entero, fechas UTC estrictas e intervalos `[inicio, fin)`;
los adyacentes no se solapan. Conserva recursos, identificadores y orden de
conflictos. No guarda ni crea reservas, consulta servicios ni resuelve
concurrencia. Una futura API y el almacenamiento quedan fuera del
[contrato 005](../../../tasks/005-check-booking.md).

## Incorporación explícita y revisión del evaluador

El 19 de octubre de 2026 se incorporan exactamente los bytes autorizados de
`runs/20261019T155332Z_check-booking_orchestrate_2437750e2eed4ac38b300357cf30b49e/intentos/2/evidencia/entrega/check_booking.py`.
Origen y destino tienen SHA-256
**`9a9038910c41d8642fa0deb22554dd192fd61d6415deb88a573b5c4d1465fbfe`**.
El producto nuevo es regular **0644**; la copia archivada conserva **0664**.
Se comprobaron base Git, autoridades, manifiestos, evaluaciones y materiales del
revisor antes de copiar. No se refactorizó ni reformateó la entrega.

Procede de **dos invocaciones de desarrollo y una de revisión reales**, con
aprobación sin hallazgos y sin incorporación automática. El
[contraste posterior](contraste-real-2026-10-19.md) fue una revisión automática
asistida por Codex, no auditoría humana ni independencia de proveedor. La
corrección entre intentos solo hizo literal el nombre Unicode del archivo en el
diagnóstico y configuró stderr UTF-8; no cambió la lógica de disponibilidad.

El contrato exige identificar archivo y causa, sin imponer su representación.
La aserción histórica `assertIn(affected, diagnostic)` rechazó
`Archivo 'solicitud sint\xe9tica.json': fecha imposible`. El evaluador **actual**
admite el nombre literal y sus representaciones estándar `repr`, `ascii` y
cadena JSON (incluidas sus comillas). Calcula variantes del nombre conocido;
no decodifica todo el mensaje con `unicode_escape`. Tras retirar las
representaciones reconocidas exige contenido adicional como causa, conservando
las comprobaciones de código 1, stdout vacío, stderr UTF-8 e identificación.
Como antes, este control comprueba contenido adicional, no la adecuación
semántica de cualquier causa posible. Rechaza nombres distintos, diagnósticos
genéricos, falta de causa, códigos incorrectos y salida parcial.

Se añaden seis controles de diagnóstico a los trece existentes. Dos adaptadores
pequeños, [aceptación](../../../tests/test_check_booking.py) y
[controles](../../../tests/test_check_booking_evaluator.py), heredan los métodos
para que cada uno entre individualmente en el descubrimiento habitual de CI.
La aceptación conserva CLI hija, intérprete absoluto, `-B`, entorno `evaluation`,
timeout e inventarios; los controles sustituyen el lanzador por respuestas
prefijadas y nunca crean/importan el candidato. No se ejecutan suites durante
el descubrimiento ni se exponen clases importadas duplicadas.

La comprobación de identidades usa ahora el nombre real del módulo importado y
un `TestLoader` local sin el filtro `-k` de la selección exterior; sigue
contrastando todas las identidades. La enumeración de casos inválidos usa
también un cargador local para evitar que ese filtro omita sus controles.

| Revisión actual posterior al experimento | SHA-256 |
| --- | --- |
| `evaluar.py` | `74f1fef60e8ebb3f9842faa8ffa1c06b25a54387b9a9664df835e20a094c058e` |
| `comprobar_evaluador.py` | `c053baad62fd4246ec72b2b418fdc0cdfac2a5d6bcd8aeb35853174458d34828` |

La autoridad congelada del experimento mantiene SHA-256
`b1b5101143912af710f571fda8b3a1aa5c1b7e383bcc852824fa4da2bf2b10db`.
Sus **186 fallos** de aceptación del primer intento (10 métodos; 184 fallos de
subtest) se conservan. No se ha reevaluado ningún candidato histórico con el
evaluador revisado ni modificado contrato, motor, otras herramientas o registros.

## Validación local de la incorporación

Evidencia local separada y excluida de Git:
`runs/20261019T164748Z_check-booking_incorporacion_03124f34e85f4a41a6936bb052c925ba/`.
Conserva origen/destino, hashes, modos, inventarios anteriores y posteriores,
comandos, Python, stdout, stderr, códigos y cierres de unittest.

Comprobaciones enfocadas con Python 3.12.3:

| Comprobación | Resultado real |
| --- | --- |
| Control nuevo `test_diagnostico_ascii_del_nombre`, antes de corregir el evaluador | 1 método, 1 fallo, 0,002 s, código 1: reproducción con respuesta prefijada. |
| Descubrimiento `test_check_booking_evaluator.py` tras ajustar el diagnóstico | 19 métodos, 1 fallo, 0,453 s, código 1: los 18 restantes pasan; la identidad esperaba el módulo corto `evaluar`. |
| Solo identidad, con el nombre real del módulo | 1 método, 1 fallo, 0,014 s, código 1: el cargador global heredó `-k` y produjo una suite vacía. |
| Solo identidad, tras usar un cargador local | 1 método correcto, 0,015 s, código 0. |

Estos fallos de integración se conservaron y corrigieron sin modificar el
producto ni relajar las identidades esperadas. Con código y adaptadores cerrados
se ejecutó **una sola regresión completa**:

```bash
python3 -B -m unittest discover -s tests -v
```

**448 métodos correctos en 215,223 s, código 0, Python 3.12.3**, sin fallos,
errores ni omisiones. Son 405 identidades de la base congelada más 24 métodos de
aceptación y 19 controles del evaluador, cada uno descubierto una vez. La
aceptación revisada del producto está incluida; no se repitió por separado.
El proceso duró 215,457 s, con stdout vacío y el log de unittest en stderr.

`regresion/resultado.json`, sus canales y `identidades.json` acreditan ese
resultado; los inventarios anteriores/posteriores coinciden. `reproduccion/`,
`controles/`, `control-identidades/` y `control-identidades-corregido/` conservan
los cuatro pasos enfocados y sus comandos exactos. Los hashes actuales de
producto, evaluador y controles quedan vinculados a la validación. Después de
ella solo se completó documentación, sin repetir suites verdes.

Este es el resultado local del árbol incorporado, distinto de las 405 pruebas
históricas de la base y de la preparación de 13 controles. Se conservan los
41 registros previos, incluido el experimento y su evaluador congelado. Las
pruebas de controladores simulan agentes: no hubo llamadas reales nuevas ni
orquestación, y no se atribuye ninguna ejecución remota de Actions.

## Evidencia histórica de preparación

**Estado anterior al experimento y a la incorporación.** Los apartados de esta
sección conservan la preparación original; «pendiente», «futuro» y «no se ha
ejecutado» describen aquel momento, no el estado actual. Los hashes y resultados
de sus tablas son históricos; los enlaces al evaluador y controles apuntan a sus
versiones actuales, cuya revisión posterior se documenta arriba.

La [tarea 005](../../../tasks/005-check-booking.md) prepara un comprobador local
de disponibilidad de reservas, como posible componente de una API futura.
**Implementación y ejecución con agentes pendientes.** No hay `check_booking.py`
en la raíz ni en la base `b54e352b3abba5a0075b512fdd84c0094cee44fa`, merge de
la PR #12. No se crea un archivo vacío para simular existencia.

La futura CLI leerá una solicitud y una lista de reservas de un archivo JSON,
validará todas las entradas y responderá con disponibilidad e identificadores
conflictivos en orden. Los intervalos son [inicio, fin), las fechas son UTC de
formato estricto y los recursos se comparan literalmente. Un conflicto sigue
siendo una consulta válida con código 0. No guarda reservas, usa servicios ni
resuelve concurrencia. Los ejemplos del contrato son sintéticos.

### Materiales y límites

- [Contrato 005](../../../tasks/005-check-booking.md).
- [Configuración v1](../../../tasks/config/check-booking.json), identificador
  `check-booking`, sin condiciones nuevas en el motor.
- [Aceptación externa](evaluar.py) y [controles del evaluador](comprobar_evaluador.py).
- [Prompt de desarrollo](../../../prompts/developer_check_booking_flow.md) y
  [prompt de revisión](../../../prompts/reviewer_check_booking_flow.md).

Se usa exactamente el [esquema configurable existente](../../../docs/tareas-configurables.md):
un único archivo Python editable, inicialmente ausente, biblioteca estándar,
300 s por desarrollador/revisor, 60 s para aceptación, 600 s para regresión,
30 s para inventario y 10 s para consultas CLI. Las referencias adicionales
son una lista vacía: el contrato contiene las reglas y ejemplos necesarios.

El futuro comando será, con un máximo de dos intentos:

```bash
python3 -B orchestrate_project.py --task-config tasks/config/check-booking.json --max-attempts 2
```

**No se ha ejecutado este comando.** La futura CLI del producto será
`python3 -B check_booking.py solicitud.json`; todavía no está disponible.

### Evaluador y alcance de las comprobaciones

`evaluar.py --project <copia>` define una clase explícita de `unittest.TestCase`,
compatible con el inventario AST de aceptación. Cada método comprueba primero
que exista un candidato regular; si falta, falla una aserción sin lanzar Python
contra una ruta inexistente. Después usa intérprete absoluto, `-B`, cwd temporal,
timeout de 10 s por consulta y `process_environment("evaluation")`, con PATH
vacío y sin heredar credenciales. Nunca importa el candidato.

Los resultados esperados son explícitos: lista vacía, otros recursos,
solapamientos parciales, igualdad, contención en ambas direcciones, adyacencia,
orden, Unicode literal, bisiestos, fechas límite y entradas inválidas. También
se comprueban claves duplicadas, tipos, validación de reservas ajenas al recurso,
canales, códigos, ayuda, opciones, rutas con guion y conservación de entradas y
proyecto (contenido, modos, mtime y creación de archivos/cachés).

Los controles sustituyen `subprocess.run` por respuestas prefijadas: no crean
`check_booking.py`, no implementan un algoritmo alternativo de disponibilidad
ni constituyen consultas reales del producto. Comprueban sensibilidad a falsos
positivos/negativos, cambios de orden, pérdida de cadenas, JSON/tipos incorrectos,
salida parcial, canales y diagnósticos ausentes. Se comprueba que el diagnóstico
localice el archivo y tenga contenido adicional; la adecuación semántica de la
causa también debe revisarse en el candidato. El entorno reducido y los
inventarios no son aislamiento de seguridad ni demuestran ausencia de todos
los efectos externos posibles.

```bash
python3 -B evals/tareas_reales/check_booking/comprobar_evaluador.py -v
```

### Evidencia de preparación

La [CI del merge de la PR #12](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39274207439)
terminó correctamente sobre `b54e352b3abba5a0075b512fdd84c0094cee44fa` (evento
`push` a `main`): **405 métodos en 257,681 s**, Python 3.12.15, con el comando
`python3 -B -m unittest discover -s tests -v`. Es la CI de la base, distinta
de una validación del futuro producto y de la CI previa de la PR.

Comprobaciones locales de esta preparación, con Python 3.12.3:

| Comprobación | Resultado observado |
| --- | --- |
| `load_task` y congelación mediante `freeze_flow`, sin iniciar orquestación | Configuración válida; base y contrato coinciden; ausencia acreditada; materiales e inventario conservados. |
| Inventario por descubrimiento en un hijo sobre la base protegida | 405 identidades únicas; coinciden una a una con los logs de CI de esa base. No se ejecutaron métodos de regresión. |
| Aceptación inicial, una sola ejecución | 24 métodos terminados, 24 fallos de aserción, cero errores, omisiones o fallos de subtest; 0,014 s, código **1**, stdout vacío. |
| `comprobar_evaluador.py -v` | 13 métodos, 0,436 s, código **0**; sin fallos, errores ni omisiones. |

Los 24 fallos iniciales se producen en `setUp` al comprobar la ausencia del
archivo. **Hubo cero invocaciones de la CLI candidata**; los fallos acreditan
la ausencia inicial, sin atribuir consultas al comprobador de reservas.
Los controles del evaluador comprueban por separado que esa aserción ocurre
antes de llamar a `subprocess.run`.

Se utilizó el adaptador existente para conservar informe estructurado,
identidades, canales, cierre textual y código. El comando real queda en
`inicial/aceptacion/resultado.json`; con sus rutas locales abreviadas fue:

```bash
/usr/bin/python3 -B <registro>/referencia/project_flow_runner.py \
  --project <copia-temporal-base>/proyecto \
  --report <registro>/inicial/aceptacion/pruebas.json \
  --acceptance <registro>/referencia/autoridades/evals/tareas_reales/check_booking/evaluar.py
```

Se ejecutó con cwd en la copia temporal, entorno `evaluation` y límite de 60 s.
La copia se eliminó después de comprobar que no había cambiado y que el
editable seguía ausente. Se conservan sus inventarios anterior/posterior, la
referencia Git reconstruida, configuración efectiva, autoridades y procedencia.
Durante esa comprobación también permanecieron intactos proyecto original y
referencia congelada.

Registro local nuevo, excluido de Git:
`runs/20261019T154724Z_check-booking_preparacion_911971a4d8bb4eb18f088393154daad2/`.
`preparacion.json` resume la preparación; `controles/` conserva comandos, salidas,
códigos y los logs de CI leídos. No es un registro de orquestación ni se han
alterado registros históricos.

| Material o informe | SHA-256 conservado |
| --- | --- |
| Configuración | `4cf85a493af4b632c70ba277a78bc23516e43a6d99c250419b9e2543d5db088c` |
| Contrato | `1cab6e505ba1fd0dadf687d7e6d23facc63bf2827d6802ba9b8e982d30c98198` |
| Evaluador | `b1b5101143912af710f571fda8b3a1aa5c1b7e383bcc852824fa4da2bf2b10db` |
| Controles del evaluador | `32836bcbc5346f9e4add72ab4025911899eb090807c17e582dee6042a9f43e50` |
| Prompt de desarrollo | `541d24a906fd17d6a1b4210da55e7bf7f91dbe7471e078266af5c1511eea9208` |
| Prompt de revisión | `f4709e1cebf4f5e9bf3e7baf302949f4acb45fbd861925b30630ff774c673153` |
| Informe estructurado de aceptación | `a4235943a8bbd03d69dc8798e093349d041c048d36018f0e213dff50dbf1e112` |
| Informe de inventario de regresión | `84072b78d0934b6dac85d112b993fb2d2b2979a6c311f2370e971ddc82aa66a1` |

No se repitió la regresión completa local ni se inició la orquestación. No se
encontró un bloqueo del motor durante esta preparación; su recorrido con una
entrega real sigue pendiente. Tras medir estos resultados solo se completó la
documentación, sin cambiar criterios ni repetir la aceptación.

### Qué quedaba pendiente en la preparación

El flujo real deberá congelar estos materiales, inventariar la base de confianza,
ejecutar su aceptación inicial **y** su regresión, y solo después autorizar el
desarrollo si cumple la precondición genérica. La CI de la base y esta preparación
no sustituyen esas comprobaciones iniciales de la futura ejecución.

Un experimento posterior podrá demostrar si una tarea de dominio distinta
recorre la vía declarativa existente, genera el único archivo autorizado,
supera su aceptación y regresión y recibe un dictamen independiente dentro del
presupuesto. Si consume una corrección, también podrá acreditar continuidad.
No demostrará fiabilidad general de modelos, capacidad para proyectos de varios
archivos, disponibilidad de una API, seguridad de despliegue ni reservas atómicas.
Una aprobación seguirá requiriendo contraste e incorporación explícita.

No se han invocado modelos, orquestado agentes ni incorporado candidatos.

## Contraste histórico del primer recorrido real

Los apartados anteriores conservan el estado y los resultados de la preparación.
El [contraste del recorrido real del 19 de octubre](contraste-real-2026-10-19.md)
documenta por separado los dos intentos, la corrección del diagnóstico, las
evaluaciones y la aprobación conservadas, y la revisión automática asistida
por Codex posterior. Recomendó preparar la incorporación explícita cuando la
entrega aún no se había incorporado. El informe se conserva sin reescribirlo;
la incorporación posterior y su validación se documentan al principio de esta guía.

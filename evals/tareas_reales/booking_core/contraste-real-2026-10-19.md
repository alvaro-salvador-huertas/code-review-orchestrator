# Contraste del primer experimento real v2 de booking-core

**Revisión automática asistida por Codex, por lectura, 19 de octubre de 2026.**
No es auditoría humana ni revisión independiente de proveedor. No se ejecutaron
candidatos, suites, agentes u orquestaciones durante este contraste.

**Recomendación: preparar la incorporación explícita del conjunto exacto.**
La evidencia conservada es coherente y la lectura completa de ambos módulos no
identifica un incumplimiento concreto de los [contratos 006](../../../tasks/006-booking-core.md)
y [005 protegido](../../../tasks/005-check-booking.md). La entrega sigue sin
incorporarse; esta recomendación no modifica esa decisión histórica.

Registro contrastado, relativo a la raíz del repositorio:
`runs/20261019T204925Z_booking-core_orchestrate_36de525c846a41a5bae8186e800187fb/`.
Su `resultado.json` enlaza el registro de revisión
`runs/20261019T210031Z_booking-core_review_fb2f4d52d6f3457c85f93c2df65d8696/`.
En lo siguiente se denominan **R** y **V**, respectivamente; son evidencia local
excluida de Git, no enlaces públicos ni nuevas ejecuciones.

## Procedencia y alcance de la comprobación

La rama conservada es `feat/tarea-nucleo-reservas`, con sus materiales pendientes.
La base declarada es `2448d88a8fd89f73415140f3b789292df6a97482`. Se contrastaron
sus objetos Git locales con los **127 blobs**, modos y rutas de
`R/referencia/proyecto/` y `R/referencia/procedencia.json`, sin exclusiones.
`check_booking.py` existe en Git como 100644, blob
`e9d1ab76d12d3adf7ae8f08e1451a13d1ad0ab84`, SHA-256
`9a9038910c41d8642fa0deb22554dd192fd61d6415deb88a573b5c4d1465fbfe`;
`booking_core.py` está ausente. No se fabricó un original vacío.

`referencia/tarea.json` declara exclusivamente esos dos editables, versión 2,
estados existente/ausente y el contrato 005 como referencia protegida. Sus bytes,
el contrato 006, ambos prompts, evaluador y contrato 005 coinciden con los hashes
de procedencia y con los materiales actuales. También coinciden las utilidades
congeladas y las copias del motor. Identidades relevantes:

| Material | SHA-256 |
| --- | --- |
| Configuración congelada | `ffebe88dbb05661c0de2be2020728c5d27def794831310db4ec503b97c3b5cf0` |
| Contrato 006 | `e30d2f38831c90c70ccd57f4bc74d1c592f0f6f73f543506132c641d72c93830` |
| Contrato 005 protegido | `1cab6e505ba1fd0dadf687d7e6d23facc63bf2827d6802ba9b8e982d30c98198` |
| Evaluador de este experimento | `84309467852b50ff6cbdeb191328c931256595b42ee5008e72c7ec68fd51d655` |
| Informe del inventario congelado | `8862030c2a7b3311443fb3248af9b69077e8e2509f272d1b8b256e4b0b6e6b87` |

El inventario conservado acredita **462 identidades únicas y ordenadas**, estado
completado, código 0, referencia conservada y canales del hijo vacíos; registra
Python 3.12.3. Sus hashes de utilidad, entorno e inventarios de archivos concuerdan
con la procedencia y la base Git. Aquí se leyó ese informe, sin redescubrir ni
importar pruebas. Las 38 identidades de aceptación se contrastaron además con
los métodos explícitos del evaluador leído mediante AST, sin ejecutarlo.

Se recalcularon los hashes y modos de la referencia y de las **11 etapas
cerradas**, incluidas las reservas y la revisión; coincidieron con sus
manifiestos. También coincidieron los tres sellos de etapas del intento, las
fuentes de `V/origen.json`, `V/seleccion.json`, los 16 materiales seleccionados y
la evidencia completa archivada por el revisor. Antes de editar esta
documentación, el proyecto original coincidía con `R/resultado.json` →
`original_sha256`, incluidos los cambios de preparación pendientes.

Son comprobaciones posteriores de consistencia por lectura, hashes y objetos
Git. No se reconstruyó un objeto de autoridad desde manifiestos del candidato,
no se inyectó estado previo en memoria ni se invocaron validadores históricos
incompatibles con v2. No equivalen a repetir la autorización previa del
controlador ni ofrecen un sello externo contra una alteración coordinada de los
registros. Las banderas de integridad del controlador se conservan como tales.

## Identidad del conjunto y archivos entregados

Origen exacto: `R/intentos/1/evidencia/entrega/archivos/`.

| Archivo regular | SHA-256 de sus bytes | Modo de entrega | Líneas |
| --- | --- | --- | ---: |
| `booking_core.py` | `78cbf2cbfca3d1a4ff9c51e6701cdfbe97f7f6d672b5a5cec8780766ea1aa0e0` | 0644 | 81 |
| `check_booking.py` | `e4e7c2a312cb723bb59d85f4420685477990d56c7b25dbe09ae44db8ab9ea4b8` | 0644 | 88 |

Identidad canónica inicial y de partida:
`f4761a0179c35b11c57f4f5defcc131c38bbf4a4bc40cbfb6f43d72b358fa5ad`.
Identidad canónica final:
**`68c53e14800a6c8e9dbebaa59bfafee4b0da030ab0ba42898746d95ba8a288f0`**.
Se recalcularon a partir del documento v1 con rutas ordenadas, presencia,
SHA-256 y modos, JSON UTF-8 con claves ordenadas, separadores compactos y sin
incluir el campo exterior `sha256`; no son hashes del JSON formateado en disco.

`original.json`, `partida.json`, configuración y procedencia coinciden en la
partida. `conjunto.json`, resumen del intento, ambas evaluaciones posteriores,
autorización registrada y `conjunto_revisado` coinciden en la entrega final.
Los inventarios de las copias evaluadas contienen exactamente esos hashes y
modos; respecto a la base solo cambia `check_booking.py` y se crea
`booking_core.py`. `cambios.json` concuerda. Los diffs archivados frente a base y
partida se reprodujeron por comparación textual y coinciden; la creación parte
de `/dev/null`. No hay un segundo intento ni otro conjunto anterior.

Los bytes de ambos módulos también coinciden en `V/materiales/`,
`V/evidencia_validada/` y su copia de la evidencia de entrega. **Las copias del
revisor tienen modo físico 0664**, como registran sus propios manifiestos;
no se confunden con los archivos de entrega 0644 ni cambian la identidad del
conjunto revisado. Se conservan sin alterar. El original separado del revisor
es la CLI de la base; no sustituye al núcleo candidato como dependencia.

## Evaluaciones conservadas del experimento

Fuentes: `R/inicial/{aceptacion,regresion}/` y
`R/intentos/1/evidencia/evaluaciones/{aceptacion,regresion}/`, cada una con
`pruebas.json`, `evaluacion.json`, `resultado.json`, `proyecto_evaluado.json` y
canales. Se contrastaron identidades iniciadas y terminadas, cierres textuales,
subtests, códigos y resúmenes, no solo totales.

| Evaluación | Métodos | Correctos | Con fallos | Aserciones fallidas | Subtests correctos/fallidos | Errores | Omisiones | Código |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Aceptación inicial | 38 | 24 | 14 | 15 | 644 / 2 | 0 | 0 | 1 |
| Regresión inicial | 462 | 462 | 0 | 0 | 1844 / 0 | 0 | 0 | 0 |
| Aceptación posterior | 38 | 38 | 0 | 0 | 858 / 0 | 0 | 0 | 0 |
| Regresión posterior | 462 | 462 | 0 | 0 | 1844 / 0 | 0 | 0 | 0 |

Los 15 fallos iniciales son aserciones de núcleo ausente anteriores a su
importación: 13 métodos con un fallo y el método de delegación con dos subtests
fallidos. No son 15 métodos ni errores técnicos. Los 24 métodos CLI iniciales
pasaron. En aceptación, la traza acredita **218 consultas CLI y 0 procesos API
iniciales**, y **218 consultas CLI y 15 procesos API posteriores**; estos últimos
incluyen lotes de llamadas y las dos variantes de delegación. No se suman como
métodos. En regresión no consta una traza agregada equivalente de consultas CLI
o procesos API; stdout está vacío, lo que no significa cero hijos.

| Evaluación | Duración unittest | Duración del proceso | Límite |
| --- | ---: | ---: | ---: |
| Aceptación inicial | 7,943 s | 8,039 s | 60 s |
| Regresión inicial | 232,062 s | 232,276 s | 600 s |
| Aceptación posterior | 9,251 s | 9,343 s | 60 s |
| Regresión posterior | 232,153 s | 232,348 s | 600 s |

Los comandos registrados usan `/usr/bin/python3 -B` y el runner congelado; la
aceptación selecciona el evaluador congelado de hash `84309467…`. Los hijos de
su traza usan intérprete absoluto, `-B`, política `evaluation` y límite de 10 s.
La versión de Python consta en el inventario; no hay una impresión independiente
de versión en cada cierre de evaluación.

**Esta aceptación inicial es nueva y propia del experimento.** No se atribuye
a él la ejecución de preparación de 8,423 s, ni su evaluador anterior
`9ec5c250e4815d2df519d90b31960f08fc50e6aec25ae8176861a5e6cb54dfd7`.
La regresión posterior tampoco fue reutilizada: conserva su proceso y cierre
propios. Las simulaciones de preparación del motor y sus pruebas internas no
son nuevas invocaciones reales de agentes de este experimento.

## Invocaciones, dictamen y decisión

Se registró **un desarrollo y una revisión, 2/4 invocaciones**, un intento de
dos posibles. Las reservas preceden a los procesos y sus eventos contienen un
cierre `turn.completed` por rol, ambos con código 0; los contadores de reserva
por sí solos no se usan como acreditación de finalización.

- Desarrollador: **182,226 s**, límite 300 s; ocho comandos internos. Uno falló
  en la aserción de permisos del archivo nuevo: `eventos.jsonl`, `item_7`, código
  1. `item_9` identifica el modo 0664 y `item_10` ejecuta el ajuste a 0644, código
  0. La entrega final conserva 0644. Fue un ajuste dentro de la misma invocación,
  no una corrección automática del controlador ni un segundo desarrollo.
- Su respuesta final declara 470 comprobaciones de dominio/API, 28 casos CLI en
  memoria y seis procesos hijos; el cierre interno de `item_11` conserva esos
  recuentos. Son comprobaciones del agente, separadas de la aceptación externa
  y regresión de la tabla; no se agregan a ellas. El agente indica que no ejecutó
  la aceptación 006 ni la regresión completa dentro de su workspace.
- Revisor: **58,536 s** de proceso, límite 300 s; 58,884 s de etapa. Sus 14 comandos
  registrados leen materiales. `revisor/respuesta_original.txt`,
  `dictamen_validado.json` y los resúmenes contienen el mismo objeto:
  **`aprobar`**, `hallazgos: []`. El resumen declara lectura íntegra, delegación,
  compatibilidad y entradas/resultados independientes.

Los límites de consultas previas de versión/ayuda fueron 10 s, y el de inventario
30 s; no son invocaciones adicionales de modelos. Los eventos conservan consumo
de entrada/salida de **289.297 / 10.818 tokens** para desarrollo y
**122.682 / 2.108** para revisión; entrada en caché: 252.544 y 81.024,
respectivamente. Son cifras registradas por la CLI, no una estimación de coste.

La ejecución completa abarca **20:49:25.471144–21:01:30.291635 UTC**, duración
registrada **724,821 s**. Las transiciones son evaluación → `revisar/superadas`
y revisión → `aprobar/revision_aprobada`. La decisión del revisor fue
`dictamen_aprobar_validado`; la del orquestador, `lista_para_revision_humana`,
código 0 e `incorporacion: no_realizada`. Se conserva el campo histórico
`contraste_semantico: pendiente`; este informe posterior no lo sobrescribe.

## Lectura estática de la entrega completa

Referencias de línea a los bytes identificados arriba; **deducciones estáticas,
sin reproducciones ejecutadas en este contraste**:

| Requisito | Lectura y conclusión |
| --- | --- |
| Separación y nombres públicos | `check_booking.py:6–7,27–29,75`: importa el núcleo, reexporta su misma clase `InvalidInput` y delega mediante un wrapper. No conserva calendario, validación de intervalos ni algoritmo de conflictos independiente. |
| Objetos y tipos | `booking_core.py:17–23,36–47,61–66`: claves exclusivas, contenedores y cadenas sin coerción; números, booleanos y null no se aceptan como campos. |
| Fechas e intervalos | `booking_core.py:7–10,26–33,48–51`: patrón ASCII y `fullmatch`, calendario validado por `datetime`, año y segundos válidos, fin posterior al inicio. Solo se admite Z; comparar estos instantes UTC como datetimes sin zona no introduce otra zona ni consulta el reloj. |
| Validación total e igualdad literal | `booking_core.py:68–79`: valida cada reserva antes de usarla, incluso ajena al recurso o posterior a un conflicto; IDs únicos globalmente, recursos e IDs sin normalización. |
| Adyacencia, solapamiento y orden | `booking_core.py:77–81`: desigualdades estrictas para `[inicio,fin)`, conserva el orden de la lista, permite reservas existentes solapadas y devuelve booleano coherente con los conflictos. |
| Errores, entrada y resultados | `booking_core.py:13–14,17–81`: errores de dominio como `InvalidInput(ValueError)` con explicación; solo lecturas de la entrada, set/lista/dict nuevos por llamada; compartir cadenas inmutables no comparte resultados mutables. Tampoco modifica entrada antes de un error. |
| Importación y dependencias | Núcleo de 81 líneas completo: solo `datetime`, `re`, regex, clase y funciones; sin llamadas a consultas, archivos, stdin, servicios o reloj. CLI: `json`, `sys` y el módulo candidato. No hay imports dinámicos/relativos, paquetes o dependencias externas. La dependencia candidata está presente en los materiales del revisor. |
| CLI compatible | `check_booking.py:13–24,32–82`: duplicados tras decodificar claves y constantes inválidas rechazados, lectura binaria y UTF-8, JSON único, validación antes de salida; errores de archivo/dominio con archivo y causa, códigos 0/1/2, ayuda y argumentos preservados. `-` es una ruta, no stdin. `85–88` protege el arranque y configura stderr UTF-8 solo al ejecutar la CLI. |

No se encontró un incumplimiento concreto que el evaluador o revisor hubieran
omitido. La ausencia de hallazgos no prueba todas las entradas o comportamientos
posibles ni convierte la aprobación del modelo en garantía general.

## Qué sigue disponible y siguiente decisión

Se conservan la base, autoridades, entrega regular, diffs, canales, informes,
eventos y materiales del revisor. Ya no existen las cuatro copias temporales
evaluadas ni los workspaces del desarrollador y revisor: su conservación durante
la ejecución solo consta en inventarios y banderas registradas. No se puede
inspeccionar ahora su estado final vivo ni repetir retrospectivamente aquellas
comprobaciones; sí se verifican los bytes archivados y sus correspondencias.

El proyecto original aún tiene la CLI de SHA-256 `9a903891…` y carece de
`booking_core.py`. Se mantuvieron intactos los registros durante este contraste.
Solo se añade este informe y su enlace, conservando la preparación histórica.

El resultado acredita un recorrido real v2 de refactorización de **dos módulos**,
con evaluación independiente del conjunto y aprobación en el primer intento.
Permite **preparar la incorporación explícita de esos bytes y modos**, seguida
de cobertura permanente y validación del árbol que se decida incorporar.
No incorpora ahora la entrega, no crea una API HTTP, no almacena reservas ni
establece fiabilidad general del motor o de los modelos.

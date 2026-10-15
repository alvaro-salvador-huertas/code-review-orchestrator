# Historial y mapa de evaluación

Este documento recoge los hitos antes repartidos por el README y enlaza sus
informes originales. Distingue implementación, pruebas simuladas, evaluaciones
locales y agentes reales. No añade ejecuciones ni reinterpreta los resultados
históricos. La [guía de funcionamiento](funcionamiento.md) describe las interfaces
actuales; los comandos concretos de un informe antiguo documentan su propio hito.

## Cómo leer la evidencia sin runs

Los documentos de `evals/` están destinados a Git y contienen recuentos,
dictámenes, tiempos, cambios de candidato y limitaciones. Se pueden leer sin
los registros originales. Los nombres de carpetas `runs/...` son identificadores
de evidencia local, no rutas necesarias para usar un clon público.

El informe multicaso contiene enlaces a `../runs/`: apuntan a la preparación,
los JSON, candidatos, eventos e informes completos **excluidos de Git**.
En un clon sin esa evidencia no estarán disponibles. La ausencia de esos
archivos limita la posibilidad de repetir la auditoría de bytes; no impide
entender los resultados publicados. Las pruebas automatizadas no dependen
de ellos y construyen sus propios registros temporales.

El [protocolo del 15 de octubre](../evals/protocolo-multicaso.md) conserva su
redacción previa y la nota posterior que enlaza los resultados. Su estado
pendiente, tabla vacía y ruta de trabajo histórica no son la guía de uso
actual. No se editan para adaptarlos retrospectivamente. Para nuevas
ejecuciones se utilizan los [comandos del README](../README.md#uso-desde-la-raíz-del-proyecto).

## Comprobaciones del controlador

Estos números corresponden a suites o comprobaciones en diferentes momentos;
no se suman como si fueran experimentos independientes con modelos.

| Hito | Resultado documentado | Naturaleza |
| --- | --- | --- |
| Controlador local inicial | 14 pruebas correctas, código 0. | Proyectos temporales; timeout y fallo de arranque simulados. |
| Reparación independiente, 14/10/2026 | 30 correctas: 14 de ejecución y 16 de reparación. | Codex simulado; procesos de evaluación reales. |
| Incorporación del revisor, 14/10/2026 | 51 en su validación inicial; después 57 correctas: 14 de ejecución, 16 de reparación y 27 de revisión. | Fixtures y CLI simulada; lectura estática de referencias. |
| Orquestación acotada, 14/10/2026 | 78 correctas en 22,166 s, código 0. | Las 57 anteriores más 21 escenarios de orquestación. |
| Base previa a la ampliación multicaso, 15/10/2026 | 78 correctas en 23,058 s. | Otra comprobación de la base; no sustituye el tiempo del hito anterior. |
| Ampliación multicaso, 15/10/2026 | 108 correctas en 39,797 s, código 0. | Escenarios para ambos casos y rechazo de evidencia cruzada. |
| Inspector de registros | 18 pruebas específicas correctas en 0,291 s; suite completa de **126 correctas en 40,147 s**, código 0. | Última regresión documentada, sin llamadas reales al modelo. |

Las comprobaciones específicas de la ampliación fueron 42 de orquestación
en 23,809 s y 8 de evidencia multicaso en 5,039 s; están incluidas en las 108.
Los 21 escenarios de orquestación se ejercitan para ambos casos. Cubren
aprobación inicial, corrección tras aserciones o dictámenes, agotamiento,
timeouts, fallos de escritura, integridad y continuidad. La CLI simulada
recibe candidatos y respuestas preparados por las pruebas: esto valida
transiciones del controlador, no la capacidad general del modelo.

Las pruebas del inspector usan registros temporales, referencias históricas
diferentes del benchmark actual, segundos intentos, detenciones técnicas,
datos ausentes e informes o JSON inválidos. Sus consultas de las dos ejecuciones
reales del protocolo terminaron con código 0, sin ejecutar sus candidatos:
caso 01, 3/4 → 4/4; caso 02, 9/16 → 16/16. Un código 0 del inspector significa
consulta completada, no aprobación independiente de una ejecución.

Esta reorganización solo cambia documentación y reutiliza las comprobaciones
anteriores. No se ejecutan suites para actualizar sus tiempos ni se mezclan
las 126 pruebas automatizadas con las 4 y 16 de los candidatos reales.

## Evaluaciones iniciales sin agentes

El controlador inicial se comprobó sobre los dos defectos intencionados.
En ese momento el caso 02 todavía tenía contrato versión 1:

| Caso histórico | Total | Correctas / fallidas | Código de pruebas | Estado / código del controlador |
| --- | --- | --- | --- | --- |
| `case_01` | 4 | 3 / 1 | 1 | `finalizada` / 0 |
| `case_02`, v1 | 8 | 5 / 3 | 1 | `finalizada` / 0 |

No hubo errores de importación ni cambios en los originales. En el caso 01
falló la acumulación: para dos sesiones de Python de 20 y 15 minutos se
obtenían 15 en vez de 35; pasaron vacío, asignaturas distintas y conservación
de la entrada. En el caso 02 fallaron código cero con `None`, cadena vacía y
espacios/saltos de línea; las otras cinco pruebas pasaron.

Tras la aclaración a versión 2, el original del caso 02 conserva 7 fallos entre
16 pruebas. La ampliación multicaso comprobó los originales en procesos
separados: caso 01, 4 pruebas con 1 fallo; caso 02, 16 con 7 fallos. Los defectos
siguen presentes; no se aplicaron los candidatos al benchmark.

## Agentes reales del 14 de octubre

El [informe original](../evals/resultados-2026-10-14.md) conserva registros,
diffs, hashes, tiempos y acciones. La secuencia incluye los resultados fallidos:

| Etapa | Resultado | Invocaciones de `codex exec` |
| --- | --- | --- |
| Primera reparación v1 | Fallo al inicializar Codex por escritura rechazada en sistema de archivos de solo lectura; candidato sin cambios, pruebas 5/8 antes y después. | 1 |
| Segunda reparación v1, lanzamiento separado | Candidato con `strip()`, pasa de 5/8 a 8/8; aceptado. Fue un lanzamiento manual indicado por el usuario, no una corrección automática. | 1 |
| Revisión del candidato v1 | `solicitar_cambios`, un hallazgo sobre tabuladores; controlador `cambios_solicitados`. | 1 |
| Aclaración del contrato y reevaluación local v2 | Se define el espacio en blanco mediante `str.isspace()`; el candidato histórico pasa las 16 pruebas en una copia temporal. No es un nuevo dictamen. | 0 |
| Nueva reparación manual v2 | Parte del original defectuoso; pasa de 9/16 a 16/16 con condición explícita para `None`, vacío e `isspace()`. | 1 |
| Revisión manual v2 | `aprobar`, sin hallazgos; controlador `aprobada`, código 0. | 1 |
| Primera ejecución coordinada v2 | Un intento, dos invocaciones, 9/16 → 16/16 y aprobación; 57,361 s. No hay segundo intento. | 2 |

Son **siete invocaciones históricas**, distintas de las cuatro del experimento
multicaso posterior. La causa concreta del entorno que provocó el primer fallo
no se aisló; el éxito del lanzamiento posterior no demuestra esa causa.

La redacción de versión 1 no precisaba todos los caracteres blancos. El revisor
interpretó que `"\t"` debía conservarse como texto; el usuario resolvió la
ambigüedad al aclarar versión 2. El dictamen antiguo sigue siendo de cambios,
sin convertirlo retrospectivamente en una aprobación. Las ocho pruebas
anteriores se conservaron y se añadieron ocho; los registros v1 no se reescriben
para autorizarlos bajo referencias v2.

El informe distingue las pruebas internas de las sesiones de las evaluaciones
independientes. También conserva comandos internos fallidos con `python` y
posteriores ejecuciones con `python3`, dentro de las mismas invocaciones.
Las revisiones registran lecturas de materiales; la revisión de su encargo
estático se apoya en esos eventos, no solo en las afirmaciones finales.

## Experimento multicaso del 15 de octubre

El [protocolo](../evals/protocolo-multicaso.md) fijó antes de los lanzamientos
una ejecución por caso, máximo dos intentos y cuatro invocaciones por ejecución,
sin repetir hasta aprobar. El [informe posterior](../evals/resultados-multicaso-2026-10-15.md)
describe una **revisión automática realizada por Codex**, sin atribuir lectura
humana al usuario.

| Caso | Inicial: correctas / fallidas | Posterior | Dictamen / controlador | Consumo | Duración |
| --- | --- | --- | --- | --- | --- |
| `case_01` | 3 / 1 | 4/4 | `aprobar` sin hallazgos / `aprobada`, 0 | 1 intento; 1 desarrollador y 1 revisor | 57,102 s |
| `case_02` v2 | 9 / 7 | 16/16 | `aprobar` sin hallazgos / `aprobada`, 0 | 1 intento; 1 desarrollador y 1 revisor | 61,706 s |

**Cuatro invocaciones reales; segunda corrección automática no observada.**
El informe contrasta fuentes congeladas, JSON enlazados, informes completos,
identificadores de pruebas, candidatos, diffs, dictámenes, eventos, hashes,
transiciones y presupuestos. Se registran integridad positiva y ausencia de
errores del controlador. Se conserva la incidencia interna de código 127
por ausencia de `python` en el desarrollador 02, seguida de `python3` en la
misma sesión; no equivale a un fallo de etapa que el controlador reintentara.

Los cuatro procesos conservan Codex CLI 0.162.1 y sus opciones de invocación.
Modelo, proveedor, esfuerzo efectivo y lectura humana: **no consta**. La
configuración adicional y la transcripción completa del comando externo de
terminal tampoco constan; las opciones registradas no identifican todo el
entorno efectivo. Los informes no se han ampliado con atribuciones posteriores.

Dos casos pequeños no permiten medir fiabilidad general ni garantizar
corrección fuera de las pruebas. El caso 01 anuncia su defecto en el contrato,
docstring y comentario, y sus pruebas no comprueban por separado nombres que
solo difieren en mayúsculas. La segunda corrección, el agotamiento, los fallos
técnicos del controlador y el rechazo de evidencia cruzada tienen cobertura
simulada, pero no se ejercitaron en estas dos ejecuciones reales.

Las fuentes congeladas y las notas de preparación permanecen en `runs/`.
El inspector se incorporó después del experimento y la reorganización de
documentación es posterior a ambos. Ninguno de esos cambios altera los bytes
o los resultados históricos conservados.

# Cierre de la v1

La v1 presenta **orquestación supervisada para tareas Python acotadas**. Separa
desarrollo, evaluación independiente, revisión y control del flujo, con
materiales fijados, presupuestos limitados y registros conservados. Incluye un
planificador de borradores, dos ejercicios de reparación, tareas de proyecto
configurables e inspectores con una demo sin modelo.

Este cierre documental parte de `main` en
`6acd51eee1e98d2741457f93c4dc59c744fc557d`. No añade funcionalidades ni modifica
código, pruebas, contratos o producto. Las [notas para v1.0.0](notas-v1.0.0.md)
quedan preparadas; crear el tag o la release es una actuación posterior.

## Supervisión humana

Una persona prepara el contrato, el alcance editable y los evaluadores; revisa
su correspondencia con la necesidad real y autoriza la ejecución con sus límites.
También resuelve preguntas y supuestos del plan, contrasta los resultados y
autoriza cualquier incorporación de los bytes concretos del candidato.

La aprobación del controlador significa que se cumplieron sus condiciones
registradas. No incorpora código ni sustituye esa revisión humana. Las copias,
los hashes y los timeouts tampoco constituyen aislamiento para código arbitrario
no confiable. La v1 no pretende demostrar autonomía general. Las ampliaciones
futuras quedan fuera de este cierre y no son requisitos para terminarlo.

## Demostración real de planificación con referencias

El 25 de octubre de 2026 se contrastó **solo por lectura** una llamada ya
realizada: resultado, propuesta JSON y Markdown, respuesta original, stdin,
materiales, hashes y correspondencia con los blobs de Git. No se repitió la
llamada ni se implementó el refactor.

La solicitud pedía extraer la lectura y decodificación del lote de
`booking_batch.py` a una función privada del mismo archivo, conservando su
comportamiento y el contrato 008. Las cinco referencias archivadas corresponden
al commit base `6acd51e`: `booking_batch.py`, `booking_core.py` y los contratos
[005](../tasks/005-check-booking.md), [006](../tasks/006-booking-core.md) y
[008](../tasks/008-booking-batch.md). Se comprobaron contenido UTF-8 completo,
ruta, commit, modo, tamaño y SHA-256, además de su igualdad con el inventario de
referencias del contexto y los textos enviados en el mensaje.

| Observación | Resultado del registro |
| --- | --- |
| Estado / código del controlador | `borrador` / 0. |
| Invocaciones | Una del planificador, proceso finalizado con código 0. |
| Duración del proceso | 55,482458838 s, con límite de 300 s. |
| Aprobación | `aprobada: false`; requiere revisión humana. |
| Preguntas y supuestos | Listas vacías; no equivalen a autorización. |
| Integridad | El controlador registra proyecto, base, materiales y workspace intactos. |
| Modelo solicitado | `gpt-6-astra`, según las opciones y el comando archivados. |
| Esfuerzo solicitado | `medium`; no se atribuye un esfuerzo efectivo distinto de lo registrado como solicitud. |

El plan **identifica el archivo y el código existentes**: propone modificar,
no crear, `booking_batch.py`. Reconoce que la instrucción de creación del
contrato 008 corresponde a la tarea histórica original. La extracción se limita
al bloque de apertura, lectura, decodificación y comprobación de raíz:

- Conserva UTF-8 estricto sin BOM, un único JSON con raíz lista y el rechazo de
  constantes no JSON y claves duplicadas mediante los hooks existentes.
- Mantiene en `_main` argumentos, ayuda, diagnósticos y captura de errores;
  la función privada devuelve la lista y propaga las excepciones.
- Conserva la delegación de cada documento completo a
  `booking_core.check_booking`, en orden, sin mezclar ni deduplicar consultas.
- Mantiene la acumulación antes de serializar: un error, incluso en la última
  consulta, deja stdout vacío. No propone modificar `booking_core.py` ni otros
  archivos, añadir dependencias o ampliar el comportamiento.

Es una observación favorable de utilidad del contexto en este caso. Los ejemplos
de aceptación de la propuesta son resultados esperados, **no pruebas ejecutadas**.
El cotejo de integridad no acredita por sí solo la calidad semántica del plan ni
generaliza su comportamiento a otras solicitudes. El refactor permanece sin
implementar y fuera de este cierre.

Las opciones solicitadas y el comando archivados coinciden en `gpt-6-astra` y
esfuerzo `medium`. Esos valores describen la solicitud; no acreditan por sí solos
el **modelo efectivamente servido**, que no se afirma sin evidencia adicional.

Identificador de la evidencia local, excluida de Git:
`2026-10-25T144213.333304Z_plan_project_749ad2678c1e4605ae208f5ca4bca141`.
SHA-256 de la respuesta original contrastada:
`01818dc08a09ced08e8b43c7a5eb74adb08838659824ec5a6654da153c932267`.
Este resumen no incorpora el registro privado ni cambia sus informes originales.

## Recorridos de producto

Los informes publicados distinguen llamadas reales, simulaciones, correcciones
asistidas e incorporaciones posteriores autorizadas:

| Recorrido | Resultado y límite documentados |
| --- | --- |
| [Inspect-json](../evals/tareas_reales/inspect_json/revision.md) | Incorporación tras revisiones y correcciones asistidas; no acredita un ciclo automático completo aprobado. |
| [Orquestación real de inspect-json](../evals/tareas_reales/inspect_json/orquestacion-real-2026-10-18.md) | Corrección automática observada y detención por timeout del revisor; la revisión adicional solicitó cambios. El experimento conserva su fallo. |
| [CSV](../evals/tareas_reales/export_csv/contraste-real-2026-10-19.md) | Desarrollo y revisión reales; incorporación exacta autorizada tras el contraste. |
| [Check-booking](../evals/tareas_reales/check_booking/contraste-real-2026-10-19.md) | Dos desarrollos y una revisión; los fallos del evaluador y su revisión posterior se conservan por separado. |
| [Booking-core](../evals/tareas_reales/booking_core/contraste-real-2026-10-19.md) | Un desarrollo y una revisión para el conjunto de dos archivos; incorporación posterior explícita. |
| [Booking-http](../evals/tareas_reales/booking_http/contraste-correccion-asistida-2026-10-20.md) | Experimento agotado; incorporación de una corrección asistida posterior. No se reclasifica el experimento como exitoso. |
| [Booking-batch](../evals/tareas_reales/booking_batch/README.md) | Un desarrollo y una revisión, aceptación de 25 métodos y regresión de 699; incorporación local posterior autorizada. |

El [historial del benchmark](historial.md) y el
[detalle técnico trasladado del README](recorrido-v1.md) conservan el resto de
la cronología. Sus recuentos corresponden a árboles y evaluaciones distintos;
no se suman como experimentos independientes ni como una tasa de éxito.

## Validación reutilizada

La validación integrada del usuario del 24 de octubre superó **768 métodos**,
código 0, sin fallos, errores ni omisiones, en **378,462 s de unittest** y
**379,212918797 s de proceso**. La
[CI de la PR #22](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/40106396007)
superó las mismas 768 identidades en su primer intento, en **345,246 s de unittest**.
Probó `97f181ef1555ab344271d746e30323744cb4ad8a`, cuyo árbol era idéntico al
commit publicado `b7056dc22fdb3fc5108fda3710e4c559e4e25e65`. Son resultados
existentes reutilizados, separados de la CI automática del PR de este cierre.

Las pruebas del controlador utilizan agentes simulados; los procesos Python de
evaluación sí se ejecutan. Los informes sintéticos de la demo no acreditan
pruebas reales. Este cierre revisa enlaces, ejemplos, diff y alcance documental
sin ejecutar suites locales, modelos, orquestaciones ni servicios. La CI de su
publicación se comprueba en el PR sin relanzarla por rutina.

Se conserva el intento integrado previo con 25 fallos por la precondición de
permisos, así como la restauración documentada de `booking_batch.py` a `0644`:
archivo regular, 2213 bytes y SHA-256
`7274cb76fb53df6572b03a519c46cda0107bd4399bdf579b89b74f0328792435`.
La causa histórica del modo incorrecto sigue sin determinarse. El
[cierre de referencias](planificacion-proyectos.md#referencias-explícitas-de-lectura)
mantiene esa distinción; no se cambian registros, contratos ni exigencias.

La v1 queda delimitada por estos resultados y por la intervención humana descrita.
Las notas de publicación están preparadas, sin crear tag o release ni realizar
merge, auto-merge o cambios de visibilidad en este cierre.

# Revisión de la corrección asistida de booking-http

Este informe conserva el estado previo a la incorporación. El estado posterior
de incorporación y validación conjunta se documenta en la
[guía HTTP](README.md#validación-conjunta-local-y-publicación-en-la-pr-16).
Sus referencias a `runs/` son evidencia local privada, disponible en el workspace
y excluida de Git; esos enlaces no estarán disponibles en GitHub. El
[producto incorporado](../../../booking_http.py), el [contrato 007](../../../tasks/007-booking-http.md)
y el [núcleo](../../../booking_core.py) sí forman parte del repositorio.

**20 de octubre de 2026. Revisión automática asistida por Codex**, solicitada
por el usuario. Rama `feat/tarea-api-reservas`, HEAD
`5c2f1b325f52adc4751b70e7d2886eb0c109bfa3`.

**Recomendación: preparar la incorporación del candidato exacto como
`booking_http.py`, regular 0644.** No se encontraron incumplimientos concretos
del contrato 007 que requieran otra corrección del producto antes de ese paso.
La recomendación se apoya en la lectura completa, el diff y la correspondencia
de la evidencia conservada. La incorporación sigue pendiente de decisión
explícita; esta revisión no copia el servidor a la raíz.

Archivo revisado: [entrega/booking_http.py][candidato], **8775 bytes**,
archivo regular **0644**, SHA-256:

```text
4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5
```

Se leyeron el candidato completo, su [diff][diff], el [contrato 007 congelado][007],
los contratos heredados [005][005] y [006][006], el [núcleo protegido][core],
la instrumentación y los informes referenciados. En este paso solo se hicieron
lecturas, cálculos de hashes, comparación de datos archivados y análisis AST.
**No se ejecutó ni importó el candidato, no se repitieron suites, no se
abrieron sockets ni se invocaron agentes u orquestaciones.** Las únicas
escrituras son este informe y su enlace en la guía HTTP.

## Procedencia y correspondencia

La [orquestación original][orquestacion] terminó con `intentos_agotados`,
código 1, dos desarrollos y dos revisiones. Ese resultado se conserva.
La entrega del segundo intento tiene SHA-256
`623105148632a048428cf5c26e70ec304ee58b49facacd4faceb64993e963413`.
El candidato aquí revisado procede de una **corrección asistida posterior bajo
instrucciones del usuario**. No se atribuye al éxito de aquel experimento
ni se presenta como continuación autónoma de su flujo.

Se recalculó el hash del candidato y se cotejó su identidad completa con:

- La [ejecución TCP y aceptación del usuario][terminal] y el resumen de
  [capturas][capturas].
- El [reanálisis separado][reanalisis] y la [aceptación reutilizada][aceptacion].
- La [copia de regresión archivada como inventario][copia] y el
  [resultado verificado de regresión][regresion].

El diff recalculado coincide exactamente con `cambio.diff`. Solo cambian
`_Handler.handle` y la condición de escritura de `_reply`; el AST restante
coincide con la entrega original. No hay cambios en la delegación ni en las
reglas de dominio.

Se verificaron las **32 entradas** del manifiesto de la corrección asistida,
las **132** de `validacion_terminal/` y las **26** del registro de reanálisis
y regresión. Son entradas de manifiestos, no un recuento de archivos únicos.
Se cotejaron las 30 peticiones y respuestas binarias con sus hashes, estados,
cuerpos, eventos y resultados archivados. Los informes de aceptación y
regresión coinciden exactamente con sus inventarios congelados: métodos únicos,
terminaciones, una sesión completa, códigos y ausencia de incidencias.

| Autoridad o referencia | SHA-256 cotejado |
| --- | --- |
| Contrato 007 | `17ee69e0a2d84bdf27e9759781aa60356e15cf89df8c73a0ea7a14983a22e083` |
| Núcleo protegido | `78cbf2cbfca3d1a4ff9c51e6701cdfbe97f7f6d672b5a5cec8780766ea1aa0e0` |
| Evaluador congelado | `c7a6f6a64ebe1a89be04643f955cd122ac2bb693fbf55115e45eae9e02ffa525` |
| Runner congelado | `337d40b234776961268e4962c25fb6fe835a2f74b5b4eb8d22681114f473cd5f` |
| Identidad agregada de la referencia | `92fe93293bf34c85835ca269dafc11e149c3afb164ebd1bcdb00bd5b5ac806e9` |

El núcleo, los contratos 005/006 y el contrato 007 del árbol actual coinciden
en bytes con sus referencias congeladas. Las copias temporales de evaluación
ya fueron eliminadas: la correspondencia se sustenta en los archivos
archivados, el código de preparación conservado, las identidades de las copias,
los comandos y sus comprobaciones de integridad. No se afirma haber vuelto
a inspeccionar aquellos temporales.

## Revisión del producto

**Hallazgos de incumplimiento concretos en esta entrega: ninguno.** La tabla
expone el requisito, el lugar revisado y ejemplos que permiten valorar esa
conclusión. Las líneas se refieren al candidato de hash indicado, no a un
servidor incorporado a la raíz.

| Requisito del contrato 007 | Archivo y líneas revisadas | Contraste y ejemplo concreto |
| --- | --- | --- |
| HEAD sin cuerpo, incluidos errores; líneas 90–93 | `booking_http.py:58–113` | La marca se inicializa en cada petición y reconoce exactamente `b"HEAD "` en cinco bytes antes del error 414 o de la segunda lectura. Sobrevive al reinicio de `command` en el analizador. `_reply:71` impide escribir el cuerpo por cualquiera de las dos identificaciones de HEAD. Las rutas de 70000 y 70001 bytes tienen 414 y cuerpo efectivo cero en ambas versiones. |
| Conservar otros métodos y los límites del analizador | `booking_http.py:88–95` y `:119–125` | HEADX y `head` no coinciden con `HEAD `; sus respuestas largas y las de GET conservan 46 bytes de cuerpo. La suma de las lecturas sigue limitada a 65537 bytes, con rechazo si supera 65536. Una línea corta terminada no consume la siguiente. No se reclasifica 414 frente a 404 como otro defecto. |
| Ruta literal antes del método y de cabeceras de cuerpo; líneas 48–59 y 81–84 | `booking_http.py:99–126` | Se recupera la ruta literal después del analizador, incluso su prefijo `//`; no se eliminan query ni barra final. POST `/otra` es 404 sin exigir longitud; GET `/availability` es 405 con `Allow: POST`; HEAD `/health` es 405 con `Allow: GET` y cuerpo vacío. Aceptación 15–17. |
| TE/CL y longitudes; líneas 58–63 | `booking_http.py:146–174` | TE+CL produce 400 antes de tamaño/tipo, y TE solo 501. CL ausente da 411; duplicados, signo, coma o decimal no entero dan 400. Tras retirar OWS solo se aceptan dígitos ASCII. Se eliminan ceros iniciales y se compara longitud/texto antes de `int`: 65536 cabe, 65537 y 5001 nueves dan 413 sin desbordamiento. Aceptación 20–25. |
| Tipo de contenido; líneas 64–68 | `booking_http.py:18–22` y `:175–179` | Una sola cabecera; comparación de tipo y charset sin distinción de mayúsculas, con OWS y comillas permitidas. `Application/Json ; CHARSET = "UTF-8"` se admite; `text/plain`, charset distinto, parámetros adicionales/repetidos y cabecera duplicada se rechazan. El tipo prima sobre el JSON: `{` con `text/plain` da 415. Aceptación 18–19 y 28. |
| Lectura exacta y plazo total de 2 s; líneas 69–72 | `booking_http.py:128–144` y `:180–187` | Se fija una fecha límite monotónica una sola vez; cada `read1` solicita como máximo lo restante y usa el tiempo restante, comprobado también después de leer. No reinicia el plazo por fragmento. EOF prematuro da 400; cuerpo incompleto que mantiene abierta la conexión da 408. El caso de goteo de aceptación 30 contrasta el plazo total, además del caso 27. |
| JSON UTF-8 estricto, duplicados y constantes; líneas 73–75 | `booking_http.py:25–35` y `:188–197` | Se decodifica UTF-8 antes de `json.loads`, sin autodetección UTF-16/32; BOM y documentos concatenados se rechazan. `object_pairs_hook` detecta duplicados a cualquier profundidad, incluidas claves equivalentes tras escapes; `parse_constant` rechaza NaN/Infinity. Los errores de decodificación y recursión producen 400. Aceptación 13–14. |
| Delegación y dominio protegido; líneas 76–79 y 94–95 | `booking_http.py:12` y `:198–203`; `booking_core.py:55–81` | El adaptador llama a `booking_core.check_booking` con el documento y devuelve su resultado; convierte `InvalidInput` en 400. No recalcula intervalos, fechas ni conflictos. El núcleo valida todas las reservas, conserva orden e igualdad literal. Una reserva de otro recurso con fecha imposible invalida todo; una adyacente no causa conflicto. Aceptación 7–12 y sonda de delegación 29. |
| Respuestas JSON, longitud en bytes, cierre y recuperación; líneas 86–95 | `booking_http.py:58–76`, `:104–113` y `:224–227` | La representación se serializa una vez, se codifica en UTF-8 y su longitud se calcula sobre bytes. Los errores tienen solo `error` no vacío. En HEAD se permite la longitud de la representación omitida. Se atiende una petición por conexión; errores de cliente no salen del bucle del servidor. Las 30 capturas registran EOF y los GET de recuperación responden 200. |
| CLI, arranque, canales, importación y ausencia de efectos propios; líneas 15–17 y 25–44 | `booking_http.py:3–22`, `:38–56` y `:206–237` | IPv4 y host fijo 127.0.0.1; puerto 0–65535, predeterminado 8000, sin opción de host. `TCPServer.server_bind` evita la resolución de nombre de `HTTPServer`. Solo después de enlazar/activar se anuncia el puerto real con `flush=True`. Errores de argumentos dan 2; puerto ocupado da 1 sin anuncio; Ctrl+C sale del contexto y cierra. Importar solo define objetos y carga el núcleo; el arranque queda tras la guarda `__main__`. Aceptación 1–6. |

La lectura de `/usr/lib/python3.12/http/server.py` confirma que
`parse_request` reinicia `command` y puede emitir errores antes de asignarlo;
la marca independiente resuelve precisamente esa separación. El delimitador
espacio corresponde a la sintaxis bien formada del ámbito contractual.
No se exige reconocer anticipadamente un método incompleto cuyo delimitador
todavía no ha llegado ni implementar un analizador HTTP general.

El rechazo 414 sigue siendo una decisión del límite del analizador anterior
al despacho de aplicación. La corrección revisada garantiza que ese error
tampoco escriba cuerpo para HEAD; no cambia estados, rutas o precedencia.

## Sonda adicional y evidencia reutilizada

La [sonda corregida][sonda], `validate_case:107–129`, mantiene estado, cabeceras
completas, cuerpo, JSON cuando procede y cierre observado. En `:125–128`
separa nombre y valor: compara el nombre de cabecera sin distinguir mayúsculas
y conserva `GET` exacto, tras el OWS exterior. La comprobación `allow` sigue
activa para los 405 de `/health` de esta matriz.

El defecto anterior estaba en
`runs/20261020_booking-http_head_correccion_asistida/comprobar_tcp.py:125`:
buscaba literalmente `allow: GET` y rechazó dos respuestas con `Allow: GET`.
El requisito es el `Allow: GET` de 007:54–55. Ambas respuestas reales tienen
SHA-256
`a7820efa154f5592c6856edae4f24080aa8b41ea03f50cf94bed42121ecbe074`,
estado 405, cuerpo vacío y EOF. Es un defecto cerrado de instrumentación.

La obligación anterior de `Connection: close`, en la sonda original `:123`,
excedía 007:91–93. Se retiró sin retirar la comprobación `cierre` de la
sonda nueva `:111`. Ejemplo contractual: una respuesta completa seguida de
EOF cumple aunque no incluya esa cabecera; la misma cabecera sin cierre no
cumple. Esta exigencia extra no causó el fallo original: las 30 capturas
contenían la cabecera y terminaron en EOF.

Los [controles conservados][controles] acreditan cuatro métodos correctos
con ocho casos: Allow/allow/aLlOw con GET aceptados; ausencia, POST y get
rechazados; cierre sin cabecera aceptado y cabecera sin cierre rechazada.
La sonda sigue siendo específica de su matriz; por ejemplo, el `Allow: POST`
de `/availability` lo contrasta la aceptación congelada, método 16. La sonda
adicional no sustituye ni modifica esa aceptación.

| Evidencia conservada | Atribución y resultado reutilizado |
| --- | --- |
| 30 capturas TCP | Ejecución del usuario del candidato corregido. Cuatro HEAD largos con 414/cuerpo cero; HEAD ordinarios con 405 o 404/cuerpo cero; GET, HEADX y `head` largos con cuerpo de 46 bytes; 30 EOF y recuperaciones correctas. |
| Reanálisis de esas 30 capturas | Realizado en el paso anterior, sin sockets ni peticiones nuevas; 30/30 correctas. `reanalisis.json` identifica explícitamente su naturaleza y conserva los indicadores previos. La ejecución original de la sonda y su resumen siguen con código 1. |
| Aceptación congelada | Ejecución del usuario reutilizada: 30 métodos y 167 subtests, una sesión, código 0, cero fallos/errores/omisiones. 6,854 s de unittest; 6,942 s exteriores, límite 180 s. Las trazas conservan 38 procesos y 137 peticiones. |
| Regresión congelada | Una ejecución en el paso anterior sobre la base `d6e576d9fe756604881c171693ca48e8d0d19a36` más el candidato exacto: 530 métodos y 2792 subtests, código 0 y cero incidencias. 273,541 s de unittest; 273,777 s exteriores, límite 600 s. Copia intacta y temporal eliminado. |

La aceptación verifica Content-Type, Content-Length, cuerpos reales y valores
Allow por separado; la sonda adicional no relaja esas obligaciones. Su
recepción conserva bytes anteriores a EOF/reset incluso si falla el envío.
El cuerpo HEAD se comprueba con los bytes posteriores al separador de
cabeceras; no se infiere únicamente de Content-Length ni de un lector que
descarte automáticamente ese cuerpo.

## Recomendación y límites

Preparar la incorporación **exclusiva de los bytes de hash
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`**,
con modo 0644 y procedencia de corrección asistida. En el paso de incorporación
corresponderá cotejar otra vez origen, destino y referencias protegidas,
conservando los cambios pendientes del controlador. No se identifica una
corrección adicional del producto ni una repetición de las suites acreditadas
como requisito derivado de esta revisión.

La conclusión queda limitada al contrato 007, sus referencias y el entorno
registrado Python 3.12.3/Linux. No acredita comportamiento exhaustivo para
toda entrada, otras versiones del intérprete, carga o concurrencia; el contrato
no exige un servidor público, TLS, persistencia ni un analizador HTTP completo.
La regresión de 530 corresponde a la base congelada; la validación previa de
534 métodos del controlador es distinta y no se presenta como prueba conjunta
de este candidato sobre todo el árbol pendiente.

Esta es una revisión automática asistida, no una revisión humana independiente.
La incorporación y cualquier commit, push o merge siguen sin realizarse.
Los históricos, las autoridades, el candidato y la corrección pendiente de
permisos del controlador se conservan; no se cambia el estado agotado original.

[candidato]: ../../../runs/20261020_booking-http_head_correccion_asistida/entrega/booking_http.py
[diff]: ../../../runs/20261020_booking-http_head_correccion_asistida/cambio.diff
[007]: ../../../runs/20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4/referencia/contrato.md
[005]: ../../../runs/20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4/referencia/materiales/tasks/005-check-booking.md
[006]: ../../../runs/20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4/referencia/materiales/tasks/006-booking-core.md
[core]: ../../../runs/20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4/referencia/proyecto/booking_core.py
[orquestacion]: ../../../runs/20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4/resultado.json
[terminal]: ../../../runs/20261020_booking-http_head_correccion_asistida/validacion_terminal/resultado.json
[capturas]: ../../../runs/20261020_booking-http_head_correccion_asistida/validacion_terminal/tcp/captura/resultado.json
[reanalisis]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/reanalisis.json
[aceptacion]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/aceptacion_reutilizada.json
[copia]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/copia_regresion.json
[regresion]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/regresion_verificada.json
[sonda]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/comprobar_tcp.py
[controles]: ../../../runs/20261020_booking-http_sonda_reanalisis_regresion/controles/stderr.txt

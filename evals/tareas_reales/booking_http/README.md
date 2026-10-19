# Preparación de booking-http, tarea 007

**20 de octubre de 2026. Producto y ejecución de agentes pendientes.**
Se preparan ocho archivos en `feat/tarea-api-reservas`, desde la base exacta
`d6e576d9fe756604881c171693ca48e8d0d19a36`. `booking_http.py` sigue ausente;
no se ha creado ni siquiera como fixture. No se ha ejecutado el orquestador.

**Estado actual:** el usuario comunicó una ejecución correcta del fixture original
desde su terminal habitual. Es evidencia aportada, separada de los errores de
`PermissionError: [Errno 1] Operation not permitted` del entorno de Codex.
La ampliación del plazo total y la corrección de trazas tienen controles prefijados
correctos; sus tres fixtures de transporte quedan pendientes de validación con
loopback autorizado. Véanse los resultados y el comando pendiente más abajo.

## Materiales y contrato previsto

- [Contrato 007](../../../tasks/007-booking-http.md): CLI de servidor, protocolo,
  precedencia, límites, canales y cierre. Hereda el dominio del
  [005](../../../tasks/005-check-booking.md) y la API del
  [006](../../../tasks/006-booking-core.md).
- [Configuración v2](../../../tasks/config/booking-http.json): **un único editable**,
  `booking_http.py` ausente, futuro archivo regular 0644. No se fuerza un segundo
  archivo por usar v2. Núcleo y contratos 005/006 son referencias protegidas.
- [Prompt de desarrollo](../../../prompts/developer_booking_http_flow.md) y
  [prompt de revisión](../../../prompts/reviewer_booking_http_flow.md): solo pruebas
  locales para el desarrollador; revisión estática sin conexiones ni ejecución.
- [Evaluador](evaluar.py) y [controles](comprobar_evaluador.py): autoridades nuevas;
  no se modifican el motor, el producto booking-core ni sus evaluadores anteriores.

La futura interfaz es `python3 -B booking_http.py --port 8000`, solo en IPv4
127.0.0.1. Puerto 0 solicita asignación del sistema; el servidor anuncia una única
línea JSON con host y puerto real después de enlazar, con vaciado inmediato.
GET `/health` devuelve salud y POST `/availability` delega el documento en
`booking_core.check_booking`. No hay almacenamiento ni exposición pública.

Se define precedencia **antes de las pruebas**: ruta → método → TE/CL → longitud
→ tamaño → tipo → lectura → JSON → dominio. Rutas exactas, HEAD sin cuerpo,
Allow en 405, cierre tras cada respuesta y recuperación tras errores. Content-Type
JSON admite equivalencias documentadas; Content-Length es único, decimal ASCII
no negativo, con límite inclusivo de 65.536 bytes. TE+CL da 400, TE solo 501;
longitud ausente 411, inválida 400, exceso 413, tipo incompatible 415, EOF prematuro
400 y lectura de cuerpo bloqueada 408. El contrato fija un máximo total de 2 s
para esa lectura. No se exige un parser HTTP completo.

| Límite configurado | Segundos |
| --- | ---: |
| Desarrollador / revisor | 300 / 300 |
| Aceptación / regresión | 180 / 600 |
| Inventario / consulta previa CLI | 30 / 10 |

## Instrumentación y límites de lo comprobado

La aceptación actual tiene **30 métodos explícitos** (29 en la preparación inicial),
una sola suite principal y `--project`.
El runner existente conserva identidades y resultados estructurados. El evaluador
no importa el candidato: arranques, importación y sustitución del núcleo ocurren
en hijos con intérprete absoluto, `-B`, entorno `evaluation` y cwd temporal.
El contexto del entorno permanece vivo hasta recoger al hijo. No usa el núcleo
como oráculo: las disponibilidades y conflictos esperados son datos explícitos.

Se arranca con `--port 0`. El anuncio se valida antes de conectar: host exactamente
127.0.0.1 y puerto entero no booleano entre 1 y 65535. Los clientes usan siempre
el literal 127.0.0.1, nunca un host arbitrario anunciado. Se usa `http.client`
para peticiones normales y sockets para duplicados, EOF y cuerpos incompletos.
El caso de puerto ocupado mantiene su socket reservado hasta terminar el hijo;
no busca un puerto libre mediante cierre y reutilización. La sonda de puerto
predeterminado intercepta bind en el hijo y provoca un fallo prefijado, sin
necesitar adquirir el puerto 8000.

Arranque y procesos cortos tienen 5 s; las operaciones de cliente tienen timeout
y la recepción hasta EOF un plazo total de 5 s. Hay margen de transporte respecto
al máximo de 2 s del cuerpo. Los canales se guardan en archivos temporales separados
para evitar llenar un PIPE; se registra anuncio, peticiones/respuestas, errores,
canales y terminación. `finally` cierra clientes y recoge el hijo: SIGINT, después
terminate y kill si hace falta, cada espera con 3 s. La terminación forzada hace
fallar un recorrido normal. Se permiten logs de servicio en stderr; stdout adicional
y tracebacks fallan. También se contrastan contenido, modos y mtimes del proyecto
y de las entradas.

Se verifica la recogida del proceso y el cierre de los clientes propios. No se
infiere que un puerto pertenece al mismo proceso mediante conectar o volver a
enlazar después de cerrarlo: un tercero podría adquirirlo. Esto no es un sandbox
ni una prueba exhaustiva de efectos transitorios, descendientes o accesos externos;
la revisión estática debe contrastar esos límites y ausencia de reglas duplicadas.
La sonda de delegación sustituye la función protegida solo en un hijo, antes de
arrancar el candidato; no exige helpers nuevos ni una sintaxis concreta de import.

## CI de la base e inventario protegido

La [ejecución 39336125781](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39336125781)
es la CI **del merge de la PR #15 en main**, evento `push`, SHA base `d6e576d…`:
**530 métodos correctos, 337,360 s, Python 3.12.15**, sin fallos, errores u omisiones.
Sus logs contienen `python3 -B -m unittest discover -s tests -v` y ese checkout.
Es distinta de la [CI de la PR #15](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39334461138),
que probó un merge temporal y tardó 344,067 s. No se atribuye ninguna de ellas a
la aceptación del producto HTTP todavía inexistente.

Se validó la selección mediante `load_task` y se congeló con `freeze_flow`, sin
invocar el flujo de agentes. La base se reconstruyó desde sus objetos Git, con
modos y ausencia real. Se conservaron contrato, configuración, prompts, evaluador,
referencias, utilidades y procedencia. El inventario habitual en un hijo sobre
esa copia protegida encontró **530 identidades únicas y ordenadas**, idénticas
a las de los logs de la CI del merge, código 0 y copia conservada.
Descubrir importa módulos y puede ejecutar su inicialización; no ejecutó métodos,
`run` ni `TextTestRunner`. No es análisis estático ni aislamiento de seguridad.
**No se ejecutó aquí la regresión completa.**

## Ejecuciones de la preparación inicial: evidencia histórica

Python local **3.12.3**; comandos con `-B`, cwd y política `evaluation` conservados.

| Ejecución | Métodos | Correctos | Métodos con fallos | Aserciones fallidas | Errores | Omisiones | Código | Duración unittest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Única aceptación inicial de la base | 29 | 0 | 29 | 29 | 0 | 0 | 1 | 0,013 s |
| Controles del evaluador, incluidos fixtures | 35 | 34 | 0 | 0 | 1 | 0 | 1 | 0,215 s |

La aceptación inicial se ejecutó **una sola vez**, con el evaluador congelado y
el runner estructurado, sobre una copia temporal de la base protegida. Las 29
aserciones ocurren en la precondición de ausencia: **cero procesos del producto y
cero peticiones HTTP**. No son consultas fallidas al servidor ni errores técnicos.
Se contrastaron identidades, `pruebas.json`, cierre textual y código. La copia
evaluada y la referencia conservaron archivos y metadatos; el temporal se eliminó.
Duración del proceso exterior: 0,116 s.

Comando de aceptación, con rutas completas conservadas en el registro:

```bash
/usr/bin/python3.12 -B referencia/project_flow_runner.py --project COPIA_BASE \
  --report aceptacion-inicial/pruebas.json \
  --acceptance referencia/autoridades/evals/tareas_reales/booking_http/evaluar.py
```

Comando de controles (0,316 s del proceso exterior):

```bash
python3 -B evals/tareas_reales/booking_http/comprobar_evaluador.py
```

Los 34 controles correctos incluyen respuestas prefijadas, falsos resultados,
booleanos, orden, Unicode, códigos, cuerpos, cabeceras y anuncio; simulaciones
de timeout, cierre de clientes, terminate/kill y conservación; además de sondas
reales en hijos contra módulos prefijados y un fixture de proceso **sin sockets**.
No implementan un segundo producto ni crean `booking_http.py`. Las ejecuciones
auxiliares no se suman como métodos principales; las trazas de procesos simulados
no se cuentan como invocaciones reales del producto.

El único error es `TransportFixtureTests.test_fixture_real_loopback_y_limpieza`:
el fixture mínimo de respuesta constante falló al crear `socket.socket`, antes
de enlazar. Stderr conserva `PermissionError: [Errno 1] Operation not permitted`;
stdout vacío, hijo código 1, recogido sin terminación forzada y cero peticiones.
El padre registra error por proceso terminado sin anuncio. Ya había fallado la
sonda inicial de loopback por la misma restricción. No se alteró el evaluador para
dar verde ni se repitió la batería; no hay una corrección de producto que atribuir.
En aquella ejecución quedó pendiente comprobar realmente lectura HTTP, cierre y
vuelta completa del fixture con loopback. No se presenta esa batería como toda correcta.

## Autoridades y evidencia conservada

SHA-256 históricos de los materiales usados en las comprobaciones iniciales:

| Material | SHA-256 |
| --- | --- |
| Contrato 007 | `17ee69e0a2d84bdf27e9759781aa60356e15cf89df8c73a0ea7a14983a22e083` |
| Configuración v2 | `a8f8d62e64e8eec771a917eb84c0a6b5a4a3e88ec9e8e4b8d89f89e0e29a387e` |
| Prompt de desarrollo | `a28b89f57f40db1047b262e913e7a2acf041590a77a2240a72542c6e2495206d` |
| Prompt de revisión | `19559a7a61a8acfd1357a16fb56eecfeff6ae907ca4493d77459a93afa9add58` |
| Evaluador | `97db290152d30ec3d67bbb852e2cc203a3ab81b7cfeebfad60c68e9b2541bf28` |
| Controles | `83645a90ec757dd8f9360a3e6f82a7ef32b43480daca5ca83357618d5e4b50d4` |
| Núcleo protegido | `78cbf2cbfca3d1a4ff9c51e6701cdfbe97f7f6d672b5a5cec8780766ea1aa0e0` |
| CLI protegida | `e4e7c2a312cb723bb59d85f4420685477990d56c7b25dbe09ae44db8ab9ea4b8` |

Registro local excluido de Git:
`runs/20261019T230156Z_booking-http_preparacion_e8a3e25fbbe740728d23f477168e0680/`.
El nombre y marcas horarias del registro usan UTC; la preparación corresponde al
20 de octubre en Europe/Madrid. Incluye CI de la base, estado previo, sonda de
loopback, selección, `referencia/` e inventario, `aceptacion-inicial/` y
`controles-01/` con versiones de fuentes, comandos, canales, códigos y tiempos.
En ese cierre las autoridades comprobadas no cambiaron tras las ejecuciones;
solo se redactó documentación. La revisión posterior se identifica por separado
a continuación. No se modifican ni reclasifican registros históricos.

La comprobación final conserva el contraste de hashes, identidades, enlaces y
las 8.482 entradas históricas intactas. Registra también una aserción fallida del
script de comprobación: confundía el hash de los bytes de `base_antes.json` con
el hash canónico de su estado. Se corrigió usando `state_hash` de la utilidad
existente; no cambiaron autoridades ni se repitieron pruebas.

## Revisión posterior: plazo total y metadatos de trazas

El usuario aportó el resultado de este comando, ejecutado **por él desde su terminal
habitual**, no por Codex:

```bash
python3 -B evals/tareas_reales/booking_http/comprobar_evaluador.py TransportFixtureTests.test_fixture_real_loopback_y_limpieza
```

Resultado comunicado: **1 método correcto, 0,093 s, código 0**; dos peticiones con
200 y proceso terminado con código 0, `forzado=false`, `recogido=true`. No se adjuntó
el log original completo ni constan su versión de Python o hashes ejecutados.
Los 34 controles correctos anteriores y este control posterior **no son una nueva
ejecución conjunta de 35 métodos**. El PermissionError histórico se conserva.

La prueba anterior de cuerpo bloqueado no distinguía una lectura con plazo total
de otra que reiniciaba el timeout tras cada byte. El nuevo método
`test_30_plazo_total_con_fragmentos_y_recuperacion` declara 100 bytes y envía un
cuerpo incompleto: `{` y espacios de un byte cada **0,4 s**, sin cerrar el envío.
`select` y un socket no bloqueante permiten recibir mientras se envía; recibir
cabeceras parciales tampoco detiene los fragmentos. Se exige 408 con JSON válido,
longitud correcta y cierre efectivo, seguido de una consulta de salud correcta.

El reloj es monotónico y hay un límite global observable de **2,5 s**, contado
desde antes de enviar cabeceras, hasta recibir la respuesta y el cierre. Los
**0,5 s de tolerancia** cubren tránsito local, entrega de cabeceras, planificación
de ambos procesos y recepción de EOF: **el contrato sigue fijando 2 s para leer
el cuerpo**. No certifica mediciones de precisión inferior a ese margen. Con
fragmentos cada 0,4 s, una lectura que reinicia 2 s de inactividad seguiría
esperando al vencer 2,5 s (tras el fragmento de 2,4 s esperaría hasta 4,4 s).
Por eso el margen no hace pasar esa implementación.

La traza registra tiempos y bytes de fragmentos, primera respuesta, cierre y
errores de envío. Un intervalo de envío superior a 0,8 s invalida la medición con
error; no se atribuye al producto ni se convierte en éxito. `BrokenPipeError`
o reset durante el envío no ocultan la respuesta: el cliente sigue recibiendo
dentro del plazo global y exige todos los bytes del JSON y el estado 408. Un reset
al recibir solo cuenta como cierre si los bytes acumulados forman una respuesta
completa y válida. Los contextos cierran el cliente y recogen el servidor también
ante errores o aserciones; no se crean hilos ni procesos emisores adicionales.

En peticiones crudas, método y ruta proceden ahora de la línea enviada; si no se
puede interpretar, son `null`. Cabeceras/cuerpo normalizados quedan en `null` y
se conservan los bytes crudos exactos. Así `GET /fixture HTTP/1.0` ya no aparece
como `/health` por un valor predeterminado del helper. No se corrigen trazas antiguas.

Los controles prefijados aceptan 408 en plazo, incluida la tolerancia, y rechazan
inactividad reiniciada, cierre tardío, respuestas incorrectas o incompletas y
mediciones irregulares. Incluyen recepción temprana de cabeceras para demostrar
que el cliente no deja de enviar antes de tiempo. Dos fixtures mínimos prueban
la política total y la de inactividad; devuelven respuestas constantes, sin reglas
de reservas, candidato ni producto alternativo.

Comprobaciones ejecutadas por Codex con Python **3.12.3**, intérprete absoluto,
`-B`, cwd explícito y entorno `evaluation`:

| Ejecución separada | Métodos | Correctos | Fallos | Errores | Omisiones | Código | Duración unittest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Controles nuevos y afectados, revisión 1 | 12 | 12 | 0 | 0 | 0 | 0 | 0,035 s |
| Tres fixtures de transporte, revisión 1 | 3 | 0 | 0 | 3 | 0 | 1 | 0,280 s |
| Solo controles de goteo tras mantener envío ante cabeceras parciales, revisión 2 | 7 | 7 | 0 | 0 | 0 | 0 | 0,019 s |

No se suman como métodos distintos: la última ejecución repite seis controles
afectados y añade uno. Las llamadas auxiliares al nuevo método de aceptación son
sondas con transportes prefijados, no aceptación del producto ausente. El control
de identidades comprobó los 30 métodos sin ejecutar la aceptación. No se repitieron
la aceptación inicial por ausencia, la regresión completa ni la batería histórica.

Los tres fixtures fallaron al crear el socket, antes del anuncio: stderr del hijo
contiene PermissionError; cero peticiones, código 1, `forzado=false`, `recogido=true`
en cada caso. No se repitieron después del ajuste de cabeceras parciales, porque
ese ajuste no resuelve la restricción del entorno. La vuelta real de transporte
de la revisión final sigue pendiente, sin skips ni evasión de restricciones.

SHA-256 de esta revisión final (no sustituyen los históricos):

| Material | SHA-256 |
| --- | --- |
| Evaluador | `c7a6f6a64ebe1a89be04643f955cd122ac2bb693fbf55115e45eae9e02ffa525` |
| Controles | `a96599357e1237414face7810702d84030a9f8ace7f906616db719d16b854159` |
| Aclaración del prompt de desarrollo | `6b306115ab822464d4ac747108f8d4aa04d051b026de36731141f539e695e9b7` |

Evidencia nueva, excluida de Git:
`runs/20261019T233347Z_booking-http_plazo-total_135fe20507114af0b3b2f4e0ea8924ed/`.
Contiene el estado previo, fuentes por revisión, hashes, comandos con selección
exacta, canales, códigos y duración exterior: 0,166 s, 0,416 s y 0,116 s,
respectivamente. `evidencia-aportada-usuario.json` atribuye separadamente el dato
comunicado por el usuario. No modifica el registro de preparación anterior.

## Siguiente paso pendiente

En una terminal autorizada con loopback, ejecutar los **tres controles pendientes
de transporte de la revisión actual**:

```bash
python3 -B evals/tareas_reales/booking_http/comprobar_evaluador.py \
  TransportFixtureTests.test_fixture_real_loopback_y_limpieza \
  TransportFixtureTests.test_fixture_goteo_plazo_total \
  TransportFixtureTests.test_fixture_goteo_rechaza_inactividad
```

El desarrollador conserva `network_access=false`. Puede escribir el servidor
aunque su entorno impida probar sockets y debe informar de esa limitación.
Las evaluaciones HTTP externas requieren un entorno autorizado con loopback;
no se cambia la configuración de red ni los límites de la tarea.

Después de comprobar la instrumentación, una autorización nueva podrá lanzar:

```bash
python3 -B orchestrate_project.py --task-config tasks/config/booking-http.json --max-attempts 2
```

**Comando no ejecutado.** La futura ejecución congelará otra vez los materiales y
ejecutará aceptación y regresión iniciales completas; esta preparación no sustituye
sus precondiciones. No hay candidato HTTP, incorporación, commit, push ni merge.

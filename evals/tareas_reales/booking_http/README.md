# Booking-http, tarea 007

**Estado actual, 20 de octubre de 2026:** servidor incorporado por autorización
explícita del usuario; **validación conjunta local de 616 métodos superada** en
su terminal con loopback. Véanse [incorporación y cobertura permanente](#incorporación-autorizada-y-cobertura-permanente)
y [validación local y publicación](#validación-conjunta-local-y-publicación-en-la-pr-16).
La CI automática de la publicación se comprueba por separado. Los apartados
anteriores a esa validación conservan la cronología, resultados y pendientes de
cada etapa; sus comandos antiguos no son instrucciones de reejecución.

## Preparación histórica

**20 de octubre de 2026. Producto y ejecución de agentes pendientes.**
Se preparan ocho archivos en `feat/tarea-api-reservas`, desde la base exacta
`d6e576d9fe756604881c171693ca48e8d0d19a36`. `booking_http.py` sigue ausente;
no se ha creado ni siquiera como fixture. No se ha ejecutado el orquestador.

**Estado de aquella preparación:** el usuario comunicó una ejecución correcta del fixture original
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

## Corrección asistida de HEAD, 20 de octubre de 2026

Esta actualización conserva los resultados anteriores como historia. Por
instrucción explícita del usuario se prepara una **corrección asistida**, con
registro independiente en `runs/20261020_booking-http_head_correccion_asistida/`.
No continúa el experimento agotado ni representa una reparación autónoma del
flujo. La orquestación
`20261020T130836Z_booking-http_orchestrate_73c8e492ac9c412d92ab8a8277b315d4`
conserva `intentos_agotados`, código 1, dos desarrollos y dos revisiones.
La revisión del cambio y la decisión de incorporación siguen pendientes.

Se parte exactamente de
`intentos/2/evidencia/entrega/archivos/booking_http.py` de esa orquestación,
regular 0644, SHA-256
`623105148632a048428cf5c26e70ec304ee58b49facacd4faceb64993e963413`.
La captura TCP en
`runs/20261020_booking-http_contraste_local/head_terminal/resultado.json`
es **una ejecución aportada por el usuario**: ambos HEAD largos recibieron 414
y 46 bytes efectivos de cuerpo, terminaron en EOF y permitieron después
GET `/health` con 200. No se repite aquí la ejecución del candidato anterior.
El defecto acreditado es el cuerpo en HEAD; no se añade un defecto por 414
frente a 404 ni se amplía el contrato.

La entrega nueva está en
`runs/20261020_booking-http_head_correccion_asistida/entrega/booking_http.py`,
regular **0644**, SHA-256
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`.
El diff solo cambia `handle` y la condición de escritura en `_reply`:
reconoce el método exacto `HEAD ` en cinco bytes antes de los errores tempranos
y conserva esa información aunque `parse_request` reinicie `command`.
La segunda lectura completa el mismo máximo de 65.537 bytes, respetando una
línea corta ya terminada. HEADX, HEADER y `head` no se confunden con HEAD.
Se mantienen estados, cabeceras, cierre, rutas, límites y delegación al núcleo.
La corrección pendiente del controlador sobre permisos de revisión es otro
cambio; sus archivos y su validación previa se conservan sin modificaciones.

Comprobaciones realizadas por el asistente con Python 3.12.3:

| Comprobación | Resultado real |
| --- | --- |
| Lectura completa y comparación AST fuera de `handle`/`_reply` | Resto del candidato idéntico; núcleo y autoridades intactos |
| 26 casos con flujos en memoria | Correctos; código 0; 0,065 s. No son una reproducción TCP |
| TCP enfocado sobre copia temporal nueva | Bloqueado al crear el socket: `Operation not permitted`; código 2; cero peticiones; hijo recogido; 0,166 s exteriores |
| Aceptación congelada, 30 identidades exactas, una sesión | 3 métodos correctos, 27 con errores (28 errores contando subcasos), cero fallos de aserción y cero omisiones; código 1; 2,532 s de unittest |
| Regresión congelada, 530 métodos | Pendiente: no se ejecuta sin TCP y aceptación correctos |

Los errores de aceptación corresponden a la restricción de sockets: 25
servidores terminaron sin anuncio y fueron recogidos; el caso de puerto ocupado
falló al crear el socket y las dos sondas de bind no llegaron a generar su
archivo de dirección. Los stderr de los hijos conservan la denegación.
Se registraron 37 procesos en aceptación y cero peticiones HTTP. Ayuda,
argumentos inválidos e importación sin efectos sí pasaron. No se presenta esta
aceptación como superada ni esos errores como defectos nuevos del producto.
Los temporales se eliminaron. La regresión de **534** métodos del árbol actual,
acreditada al corregir el controlador, no se ha repetido.

Desde la raíz del repositorio, este único comando completa la validación
pendiente en la terminal del usuario con loopback autorizado:

```bash
python3 -B runs/20261020_booking-http_head_correccion_asistida/validar.py --output runs/20261020_booking-http_head_correccion_asistida/validacion_terminal --ejecutor usuario
```

Exige una salida nueva y verifica hashes y modos antes de copiar. La prueba TCP
adicional usa 127.0.0.1 y puerto 0, conserva peticiones/respuestas crudas,
errores de envío, EOF/resets y tiempos; sigue recibiendo tras un error de envío.
Cubre ambos HEAD largos, HEAD ordinario a `/health` y `/otra`, GET largo,
controles HEADX/`head` y recuperación con GET `/health`, en HTTP/1.0 y HTTP/1.1.
No utiliza un lector que descarte cuerpos HEAD ni deduce su ausencia de
Content-Length. Son 30 intercambios previstos, distintos de los 30 métodos
de aceptación.

El comando ejecuta la aceptación congelada y, solo si las dos comprobaciones
pasan, **una** regresión de la base congelada con 530 identidades. Usa copias
temporales, entorno `evaluation`, plazos de 120/180/600 s, recogida de hijos y
terminación del grupo ante timeout o interrupción. Conserva canales, códigos,
inventarios de métodos, trazas y SHA-256, sin cambiar `network_access=false`.
`diagnostico.txt`, `entrega.json`, `cambio.diff`, `memoria_resultado.json` y
`validacion_local/` distinguen procedencia, comprobaciones y pendientes.
El servidor sigue ausente de la raíz; no se invocaron modelos, agentes ni
la orquestación, y no hay commit, push ni merge.

## Reanálisis de la sonda adicional y aceptación reutilizada

**20 de octubre de 2026.** El usuario ejecutó el comando anterior a las
14:46:39 UTC. Su registro `validacion_terminal/` conserva **código 1**:
la sonda adicional marcó dos falsos negativos, aunque la aceptación congelada
pasó sus **30 métodos**, sin fallos, errores ni omisiones (6,854 s de unittest).
Ese registro y la sonda original permanecen intactos.

El contraste y la versión corregida de la sonda se guardan por separado en
`runs/20261020_booking-http_sonda_reanalisis_regresion/`. Se verificaron las
132 entradas del manifiesto de la ejecución del usuario, los binarios de las
30 peticiones y respuestas, sus hashes, tamaños y representaciones hexadecimales.
Los únicos indicadores falsos eran `allow` en HEAD `/health`, para HTTP/1.0 y
HTTP/1.1. Ambas respuestas contienen **`Allow: GET`**, con cuerpo vacío y EOF,
y tienen SHA-256
`a7820efa154f5592c6856edae4f24080aa8b41ea03f50cf94bed42121ecbe074`.
La sonda buscaba literalmente `allow: GET` distinguiendo mayúsculas del nombre.

La sonda nueva analiza el nombre sin distinguir mayúsculas y conserva la
comparación exacta del valor `GET`. También retira la exigencia adicional de
`Connection: close`, manteniendo el cierre observado mediante EOF/reset:
el contrato no exige esa cabecera literal. Esta segunda exigencia **no causó
el fallo actual**; era verdadera en las 30 capturas y todas registraron EOF.

Los cuatro métodos de controles pequeños pasaron: `Allow`, `allow` y `aLlOw`
con `GET` se aceptan; ausencia, `POST` y `get` se rechazan. Cierre sin cabecera
se acepta y cabecera sin cierre se rechaza. La comprobación `allow` se conserva.

El **reanálisis sin sockets** dio **30/30 casos correctos**, con código 0:
es una nueva interpretación de la ejecución TCP del usuario, sin nuevas
peticiones y sin modificar el resultado histórico. Los cuatro HEAD largos
(dos rutas por versión) tienen cero bytes efectivos de cuerpo; GET largo
conserva 46 bytes. HEAD ordinario, controles de método, los 30 EOF y las
recuperaciones mediante GET `/health` también corresponden. `reanalisis.json`
conserva comprobaciones anteriores y nuevas, hashes, cabeceras y eventos,
separando tiempos de transporte originales y tiempo de reanálisis.

Se **reutiliza la aceptación del usuario**, sin repetirla: se cotejaron sus
30 identidades, sesión completa, subtests, códigos, comandos, trazas y hashes.
`aceptacion_reutilizada.json` acredita la correspondencia con el candidato
regular 0644 de SHA-256
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`
y el evaluador congelado
`c7a6f6a64ebe1a89be04643f955cd122ac2bb693fbf55115e45eae9e02ffa525`.
Las copias temporales originales ya se eliminaron; el cotejo actual utiliza
los scripts, identidades, informes y trazas conservados.

La nueva regresión se registra aparte en `regresion_verificada.json`, con
canales e informe en `regresion/`. Parte de otra copia temporal de los 138
archivos de la base congelada `d6e576d9fe756604881c171693ca48e8d0d19a36`,
cotejados contra su procedencia, y añade únicamente el candidato exacto.
Usa runner y entorno `evaluation` congelados, límite 600 s, un marcador que
impide repetirla accidentalmente y cotejo de las **530 identidades**.
No ejecuta de nuevo TCP, aceptación ni la regresión de 534 del controlador.

**Resultado de la nueva regresión:** una ejecución, **530 métodos correctos**
y 2.792 subtests superados, cero fallos, errores u omisiones, código 0.
Duración unittest: **273,541 s**; proceso exterior: 273,777 s, dentro de 600 s.
Las identidades y terminaciones coinciden exactamente con el inventario
congelado. Copia, candidato y referencia intactos; temporal eliminado.

Queda completada la validación de la corrección asistida mediante controles
de sonda, reanálisis de TCP del usuario, aceptación reutilizada y nueva regresión.
`resultado.json`, `diagnostico.txt` y `SHA256SUMS` del registro nuevo reúnen
procedencia, resultados y conservación. No apareció otra discrepancia.
El candidato y los cambios pendientes del controlador permanecen intactos,
igual que los históricos: `intentos_agotados`, código 1, dos desarrollos
y dos revisiones. Siguen pendientes **la revisión del cambio del producto y
la decisión explícita de incorporación**. No hay servidor en raíz, nuevas
invocaciones de agentes, orquestación, commit, push ni merge.

La [revisión automática asistida por Codex del 20 de octubre de 2026](contraste-correccion-asistida-2026-10-20.md)
contrasta el candidato completo, el contrato y la evidencia conservada, sin
ejecutar el producto ni repetir pruebas. No identifica incumplimientos concretos
y recomienda preparar la incorporación del hash exacto
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`,
regular 0644, con los límites documentados. La decisión de incorporación sigue
pendiente; esta recomendación no cambia el resultado del experimento agotado.

## Incorporación autorizada y cobertura permanente

**20 de octubre de 2026.** Tras la revisión anterior, el usuario autoriza incorporar
exactamente la entrega corregida. [booking_http.py](../../../booking_http.py)
ya existe en la raíz como archivo regular **0644**, SHA-256
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`.
El destino estaba ausente; se copiaron los bytes autorizados y se comprobaron
hash, tipo y modo antes y después. El origen
`runs/20261020_booking-http_head_correccion_asistida/entrega/booking_http.py`
permanece intacto. No se aplica otra corrección del producto.

Es una **incorporación explícita de una corrección asistida bajo instrucciones
del usuario**, posterior al experimento agotado. El registro original conserva
`intentos_agotados`, código 1, dos desarrollos y dos revisiones. No se reanuda
ese flujo ni se atribuye esta entrega al éxito de su orquestación. La corrección
pendiente de identidad y permisos del controlador se conserva.

Uso local, desde la raíz:

```bash
python3 -B booking_http.py --port 8000
```

Solo enlaza IPv4 `127.0.0.1`. `--port 0` permite asignación del sistema; la única
línea de stdout anuncia el host y puerto efectivo después de enlazar. GET
`/health` devuelve `{"estado": "ok"}`. POST `/availability`, con Content-Type
JSON y Content-Length, recibe el documento de solicitud y reservas descrito en
el [contrato 007](../../../tasks/007-booking-http.md) y delega en
`booking_core.check_booking`. No persiste reservas. Cada respuesta cierra la
conexión; HEAD conserva el estado y las cabeceras correspondientes sin enviar
cuerpo, incluidos los errores tempranos. Ctrl+C recoge el servidor.

La cobertura permanente usa entradas sintéticas, sin depender de `runs/` ni
ejecutar candidatos históricos. Los evaluadores y contratos congelados no cambian:

| Adaptador o regresión | Métodos descubiertos |
| --- | ---: |
| [Aceptación HTTP](../../../tests/test_booking_http.py), herencia íntegra de la aceptación | 30 |
| [Controles del evaluador](../../../tests/test_booking_http_evaluator.py), aserciones originales | 42 |
| Fixtures del mismo adaptador, incluidos los dos del plazo total | 3 |
| [Regresión HEAD](../../../tests/test_booking_http_head.py), HTTP/1.0 y HTTP/1.1 | 2 |
| Controles simulados del transporte de esa regresión | 5 |

Los adaptadores siguen el precedente de booking-core y restauran el alias temporal
`evaluar` al importar los controles. Cada método heredado se descubre por separado.
La regresión HEAD usa el arranque y la recogida del evaluador, exclusivamente
127.0.0.1 y puerto 0, y un intercambio concurrente con plazo total de 5 s y
respuesta acotada. Conserva bytes recibidos aunque falle el envío, exige EOF o
reset y valida una respuesta completa; no exige una cabecera literal
`Connection: close`. El analizador solo interpreta cabeceras y conserva el cuerpo
crudo, sin ocultarlo por tratarse de HEAD.

Por versión se prueban HEAD ordinario a salud y a ruta desconocida, dos rutas
largas de 70.000 y 70.001 caracteres, y GET/HEADX/`head` largos como controles con
cuerpo JSON obligatorio. Una consulta de salud inicial y otra tras cada caso
comprueban recuperación: **30 intercambios previstos**, distribuidos en dos
métodos. Los contextos cierran los clientes y recogen los hijos aun ante fallos.
Los cinco controles sin sockets verifican nombres de Allow equivalentes, valor
exacto GET, cierre sin cabecera, rechazo de cabecera sin cierre, datos tras un
error de envío/reset y rechazo de respuestas incompletas o de un cuerpo HEAD.

Comprobaciones efectivamente realizadas por Codex, con Python **3.12.3**, `-B`
y entorno `evaluation`:

- **42 controles del evaluador correctos**, código 0, 0,273 s de unittest.
- **5 controles de transporte simulado correctos**, código 0, 0,012 s.
- Descubrimiento sin ejecutar métodos ni importar el producto: **616 identidades
  únicas**; correspondencia exacta de los tres grupos heredados y alias global
  restaurado. Son los 534 métodos anteriores y 82 incorporados.

El primer script de inventario falló con `KeyError`: buscaba el comprobador en
`sys.modules`, de donde el contexto de importación lo había retirado correctamente.
Se conservan esa versión y sus canales; el inventario corregido consulta el
módulo retenido por el adaptador. Solo se repitió el descubrimiento, sin repetir
los 47 controles aprobados. No fue un fallo del producto ni de los adaptadores.
No se han intentado conexiones ni ejecutado aquí la aceptación, los fixtures o
la regresión HEAD con sockets.

El registro nuevo, excluido de Git, es
`runs/20261020_booking-http_incorporacion_integrada/`. Conserva procedencia,
estado previo, comandos, Python, stdout/stderr, códigos, tiempos, inventario,
identidades y hashes. La aceptación congelada de **30 métodos**, el reanálisis
de **30 capturas de la ejecución TCP del usuario**, la regresión congelada
posterior de **530 métodos** y la regresión previa del controlador de **534**
se conservan como validaciones separadas. Ninguna acredita todavía la suite
conjunta integrada.

Desde la raíz, ejecutar **una sola vez** en la terminal autorizada con loopback:

```bash
python3 -B runs/20261020_booking-http_incorporacion_integrada/validar_integracion.py
```

Ese comando comprueba la identidad del árbol preparado y del candidato, reserva
una salida nueva `validacion_terminal/` y ejecuta exactamente una vez
`python3 -B -m unittest discover -s tests -v`, con el intérprete absoluto,
entorno `evaluation` y límite de **600 s**. Registra ambos canales, código,
versión de Python, identidades ejecutadas y hashes; coteja las 616 identidades
y la conservación del árbol y del origen. Recoge el proceso y mata su grupo
ante timeout o interrupción. Si el árbol cambió, se detiene antes de lanzar
pruebas; si ya existe la salida, no la reutiliza ni repite la suite.

**Validación conjunta pendiente: no se presenta como superada.** Se requiere
examinar ese resultado antes de dar por validada la integración. No se modifica
la configuración de red ni se repiten aquí las suites anteriores. No hay nuevas
llamadas al modelo, agentes, orquestación, commit, push ni merge.

## Validación conjunta local y publicación en la PR #16

El usuario ejecutó desde su terminal autorizada el comando preparado:
`python3 -B runs/20261020_booking-http_incorporacion_integrada/validar_integracion.py`.
Este lanzó una sola vez `python3 -B -m unittest discover -s tests -v`, mediante
`/usr/bin/python3`, con Python **3.12.3**, entorno `evaluation` y límite de 600 s.
La ejecución transcurrió el 20 de octubre de 2026, de **16:07:51 a 16:13:17 UTC**.

**Resultado local: 616 métodos correctos, código 0, sin fallos, errores ni
omisiones; 325,413 s de unittest y 325,783 s exteriores.** Es una ejecución
aportada por el usuario, no una ejecución de sockets realizada por Codex.
Incluye aceptación HTTP, controles y fixtures del evaluador, regresión HEAD
y pruebas del controlador sobre el árbol integrado.

Antes de publicar se cotejaron las cinco entradas del manifiesto de
`runs/20261020_booking-http_incorporacion_integrada/validacion_terminal/`,
los canales completos, el informe y el inventario. Las **616 identidades
ordenadas** coinciden; stdout está vacío y stderr termina en `OK`.
Los **151 archivos** del árbol preparado coinciden con los evaluados, incluido
el candidato regular 0644 de hash
`4bd8b1a50906672d576e9fc29cb7984d3665c74e71df976cccfec432ce516bf5`.
Árbol, candidato y origen se conservaron durante la ejecución. Después solo
se actualiza documentación de estado; código, pruebas y dependencias permanecen
idénticos. Se reutiliza esta validación sin repetir suites locales.

La publicación autorizada en la
[PR #16](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/16)
reúne HTTP local sobre `booking_core`, la corrección asistida de HEAD, la
[conservación de identidad y permisos al revisar](../../../docs/orquestacion-proyectos.md#identidad-de-las-copias-de-revisión)
y su cobertura permanente. Conserva los materiales de preparación ya publicados.
Los registros privados siguen excluidos de Git; la evidencia de contraste y
publicación se guarda en `runs/20261020_booking-http_publicacion_pr16/`.

La CI automática es una validación distinta, todavía no ejecutada para esta
publicación al preparar el commit. Se comprobarán su comando, Python, resultado,
las 616 identidades y el commit probado en Actions frente a la cabecera de la PR.
El checkout temporal de `refs/pull/16/merge`, si se utiliza, comprueba una
combinación con la base y **no constituye una fusión real**. El resultado y la
ejecución concreta quedarán vinculados en la PR; no se inicia un workflow manual.

El experimento original sigue agotado, con dos desarrollos y dos revisiones.
La corrección asistida posterior, la reparación del controlador, la regresión
congelada de 530, la anterior del controlador de 534, esta validación local de
616 y la CI de publicación son etapas distintas. No se reescriben sus resultados
ni se atribuye el producto corregido al éxito del experimento original.
No se autoriza merge ni auto-merge.

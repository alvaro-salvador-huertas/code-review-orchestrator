# Planificación de proyectos por lenguaje natural

Desde la raíz, **cuando decidas invocar un modelo real**:

```bash
python3 -B plan_project.py "Descripción del trabajo que quiero realizar"
```

Necesita Codex CLI disponible y autenticado. Genera un borrador revisable con una
sola sesión nueva de solo lectura, sin desarrollo, evaluación, revisión del
producto ni incorporación. La entrega de materiales en el mensaje tiene pruebas
con una CLI simulada y un contraste real favorable para una petición abierta de
API de reservas. Un caso no acredita fiabilidad general ni aprueba el borrador.
`python3 -B plan_project.py --help` no invoca modelos ni crea registros.

El controlador fija la petición original y el commit `HEAD` de la base. Sin
`--reference`, el modelo recibe petición, instrucciones, restricciones, esquema y
nombres/tipos de los archivos Python de la raíz de esa base, sin sus fuentes.
La selección explícita permite añadir los documentos descritos a continuación;
no explora otras fuentes, registros privados ni configuración personal.
Los cambios pendientes se conservan, pero no se entregan al modelo. Sin las fuentes,
inferir el comportamiento de un módulo por su nombre no constituye un hecho comprobado.

El stdin enviado al adaptador es un único objeto JSON con `instrucciones` y
`materiales`. Este último contiene los textos UTF-8 íntegros de `solicitud.txt`,
`contexto.json` y `respuesta.schema.json`, obtenidos de los mismos bytes que se
archivan. La serialización conserva comillas, Unicode y saltos de línea sin
confundir el texto del usuario con delimitadores. El modelo dispone de los datos
en el mensaje y no necesita herramientas de lectura. Se mantienen el esquema
por `--output-schema`, la validación local y `planificador/entrada.txt` con su hash.

## Referencias explícitas de lectura

Al iniciar, puedes repetir `--reference RUTA`. Por ejemplo, **este comando
invocaría un modelo real** si decides ejecutarlo:

```bash
python3 -B plan_project.py "Contrasta una propuesta de consulta con el contrato" \
  --reference booking_core.py --reference tasks/006-booking-core.md
```

Cada ruta se resuelve en el mismo commit base fijado para el inventario. Se leen
los blobs de Git, nunca el contenido ni los permisos del checkout; un cambio local
o un archivo sin commit no reemplazan una referencia. Solo se admiten archivos
regulares `.py` de la raíz, `README.md` y `.md` bajo `tasks/` o `docs/`. Las rutas
deben ser relativas y canónicas, sin componentes ocultos o privados, `.` ni `..`,
separadores duplicados o inversos. Se rechazan duplicados, ausencias, directorios,
enlaces y submódulos, también en componentes intermedios del árbol Git. Los
nombres se consultan literalmente, sin expandir patrones.

El máximo es **16 referencias, 128 KiB por archivo y 1 MiB total**, contado en
bytes UTF-8. Se comprueban todos los tamaños antes de cargar los blobs; un texto
que no sea UTF-8 válido se rechaza. Se conserva además el límite de **4 MiB del
mensaje completo**: el escape JSON puede alcanzar ese límite antes que el de
contenidos. Toda referencia inválida se rechaza antes de consultar la versión o
ayuda de Codex y antes de reservar una invocación.

`materiales/referencias.json` guarda `version: 1` y una lista `archivos`, en el
orden solicitado. Cada entrada contiene `ruta`, `commit`, `modo` (entero de
permisos Git, 0644 o 0755), `bytes`, `sha256` del contenido UTF-8 y `contenido`
íntegro. `contexto.json.referencias` repite las identidades sin el texto. El JSON
de referencias viaja como texto completo en `materiales["referencias.json"]`
del stdin, obtenido de los mismos bytes archivados. Se conservan Unicode,
comillas, CRLF y texto que parezca un delimitador. No se solicita abrir archivos.

Las instrucciones, la solicitud y los documentos ocupan campos distintos.
Consultar un documento no autoriza modificarlo ni ejecutar su contenido: siguen
vigentes los archivos protegidos, el alcance de Python raíz y biblioteca estándar,
la prohibición de comandos, código, pruebas y agentes, y la revisión humana del
borrador. Esta separación **no garantiza resistencia a instrucciones maliciosas**
dentro de los textos ni acredita la veracidad de su contenido.

`--reference` es incompatible con `--from-plan` y las exportaciones de plantillas.
Una continuación hereda los bytes exactos de `referencias.json` de su origen,
incluido el commit original, aunque cambien HEAD o el checkout. El lector valida
conjunto, metadatos, tamaños, hashes, textos y correspondencia con stdin y contexto;
también coteja la igualdad exacta entre generaciones. No reconsulta las fuentes.
Los registros históricos sin referencias conservan sus materiales anteriores y su
lectura; el esquema de respuesta v1 no cambia. Sin la opción no se añade material
de referencias. Las opciones de modelo/esfuerzo, reserva previa, máximo de una
invocación de 300 s y ausencia de reintentos permanecen iguales.

Validación local de este cambio (Python 3.12.3, repositorios temporales y CLI
simulada): **20 métodos nuevos correctos** en 4,326 s; después, **103 métodos de
planificación** en 26,273 s (incluyen esos 20) y **39 de compatibilidad** en
10,904 s, todos con código 0, sin fallos, errores ni omisiones. El fixture verifica
stdin antes de responder y rechaza omitir las referencias aunque estén en disco.
Se conservan por separado la reproducción previa del argumento aún no admitido
y un error intermedio de sintaxis en una prueba, corregido antes de estos resultados.
Las [pruebas de referencias](../tests/test_plan_references.py) cubren selección en
Git frente al checkout, límites, rutas y tipos rechazados, UTF-8, herencia,
alteraciones de evidencia y compatibilidad sin referencias.

La **validación integrada está superada**. El usuario ejecutó la suite en su
terminal autorizada el 24 de octubre de 2026 con Python 3.12.3: **768 métodos,
378,462 s de unittest y 379,212918797 s de proceso**, código 0, sin fallos, errores
ni omisiones. El runner existente utilizó `repair_case.run_process`, entorno
`evaluation`, límite de 600 s y canales separados. Se cotejaron los canales
completos, las 768 identidades ordenadas, los hashes y modos de los 171 archivos,
HEAD, rama e índice con el árbol evaluado. Este cierre reutiliza esa ejecución;
solo README y esta guía se actualizan después, sin repetir suites locales.

El primer intento integrado conserva su resultado `no_superada` en
`runs/20261023_contexto_planificador/validacion_terminal/`: sus 25 fallos de
booking-batch ocurrieron en `setUp/check_candidate`, antes de invocar el hijo,
porque el modo `0664`, ya registrado en el árbol preparado, incumplía el `0644`
contractual. La evidencia no determina qué originó ese modo. Tras registrar que
`booking_batch.py` era regular, de 2213 bytes y SHA-256
`7274cb76fb53df6572b03a519c46cda0107bd4399bdf579b89b74f0328792435`, se restauró
únicamente su modo a `0644`, conservando los bytes. La aceptación enfocada superó
25 métodos en 8,815 s de unittest, código 0, sin fallos, errores ni omisiones;
la exigencia contractual de permisos permanece intacta.

La restauración y sus comprobaciones se conservan en
`runs/20261024_contexto_planificador_permisos/`; la ejecución integrada posterior
está en su subdirectorio `validacion_terminal/`, con manifiesto corregido y salida
independiente. El cotejo de cierre queda en
`runs/20261024_contexto_planificador_cierre/`. Son registros locales excluidos de
Git; el fallo anterior y los demás históricos permanecen intactos. No se han
invocado modelos reales para este cambio: la utilidad semántica de las referencias
queda pendiente de una ejecución posterior.

## Esquema cerrado de propuesta v1

El esquema se define en [project_plan.py](../project_plan.py), mediante
`response_schema()`, y se guarda en cada registro. No es una configuración
ejecutable v1/v2 del motor. La respuesta del modelo exige exactamente estas claves:

| Campo | Tipo y significado |
| --- | --- |
| `version` | Entero 1, no booleano. |
| `objetivo` | Texto no vacío que interpreta el trabajo. |
| `viabilidad` | `dentro_del_alcance`, `pendiente_de_aclaracion` o `fuera_del_alcance`. |
| `requisitos_interpretados` | Lista de textos; interpretaciones pendientes de revisión. |
| `alcance`, `exclusiones` | Listas de textos que delimitan el borrador. |
| `archivos` | Lista de objetos con solo `ruta`, `accion` y `proposito`. Acción `crear` o `modificar`; propósito no vacío. |
| `criterios_aceptacion` | Lista de objetos con solo `descripcion` y `ejemplos`. Cada ejemplo contiene solo `entrada` y `resultado_esperado`, ambos textos; entrada puede estar vacía. |
| `preguntas_pendientes` | Lista de dudas que requieren intervención del usuario. |
| `supuestos` | Lista de supuestos explícitos, no decisiones atribuidas al usuario. |
| `limitaciones` | Lista de restricciones o incertidumbres del plan. |

Todos los objetos son cerrados. Se rechazan claves duplicadas a cualquier nivel,
constantes no JSON, tipos distintos, textos requeridos vacíos, rutas repetidas y
duplicados en listas y criterios. Los textos deben ser representables en UTF-8,
con un máximo de 8.000 caracteres; las listas admiten hasta 100 elementos.
La petición admite hasta 16.000 caracteres y la respuesta bruta hasta 1 MiB.
Una petición no representable en UTF-8 se rechaza como argumento inválido antes
de crear registros o consultar la CLI. Los diagnósticos escapan sustitutos Unicode
aislados procedentes de datos rechazados; la respuesta original se conserva exacta.
El controlador valida localmente incluso si Codex recibió el esquema.

Las rutas deben cumplir `[A-Za-z_][A-Za-z0-9_]*\.py` en la raíz, sin directorios,
enlaces, rutas absolutas ni infraestructura protegida. `crear` exige ausencia
en la base Git; `modificar`, presencia como archivo regular. No se permiten
borrados ni dependencias ajenas a la biblioteca estándar. Los nuevos módulos
`plan_project.py` y `project_plan.py` se añaden a la protección de infraestructura
de las configuraciones v2; la validación del plan los prohíbe también. No se
cambian las reglas históricas de configuración v1 ni los presupuestos del motor.

Una propuesta `dentro_del_alcance` necesita requisitos, alcance, archivos y
criterios. `pendiente_de_aclaracion` necesita preguntas y puede no definir todavía
archivos ni criterios. `fuera_del_alcance` necesita limitaciones y no admite
archivos propuestos: permite documentar un bloqueo o preguntar cómo redefinirlo.
No convierte capacidades nuevas en permisos disponibles.

El controlador envuelve la respuesta validada en `propuesta.json`, con claves
exactas `version`, `tipo`, `estado`, `solicitud_original`, `commit_base`,
`procedencia` y `propuesta`. `tipo` es `propuesta_planificacion`; `procedencia`
contiene `rol`, `registro`, `respuesta_sha256` y `requiere_revision_humana=true`.
El modelo no suministra ni puede sobrescribir esos metadatos.
`propuesta.md` se renderiza desde ese mismo objeto, con los datos variables como
texto literal. No ejecuta comandos, código ni pruebas presentes en la respuesta.

## Ejemplo exclusivamente sintético

Para «créame una API de reservas», una respuesta simulada válida es:

```json
{
  "version": 1,
  "objetivo": "Definir una API de reservas.",
  "viabilidad": "pendiente_de_aclaracion",
  "requisitos_interpretados": ["Ofrecer una API de reservas."],
  "alcance": [],
  "exclusiones": [],
  "archivos": [],
  "criterios_aceptacion": [],
  "preguntas_pendientes": [
    "¿Qué operaciones debe ofrecer?",
    "¿Necesita persistencia?",
    "¿Qué interfaz se espera?"
  ],
  "supuestos": [],
  "limitaciones": ["Todavía no hay requisitos suficientes para definir archivos."]
}
```

Se obtiene estado `necesita_aclaraciones` y código 0. No decide por el usuario
que deba ser HTTP ni que los datos deban persistirse. Una propuesta concreta
sin preguntas ni supuestos puede quedar como `borrador`; tampoco es aprobación.
Los supuestos pendientes o la viabilidad aún no resuelta producen
`necesita_aclaraciones`, aunque la lista de preguntas esté vacía.

## Sesión, estados y evidencia

Se reutiliza `review_case.invoke_reviewer` como adaptador de solo lectura, con
rol registrado **planificador**, y `repair_case.run_process` para canales,
timeouts y recogida de procesos. No se altera su comportamiento histórico:
`--ephemeral`, sandbox `read-only`, aprobación `never`, web desactivada y
subagentes desactivados. El prompt también prohíbe ejecutar o leer fuera del
contexto entregado. El entorno utiliza la política existente `codex` para su
autenticación; no se enumeran ni copian valores de variables a los registros.

Hay un máximo de **una invocación, con 300 s**, sin reintento. Versión y ayuda
tienen 10 s por consulta y no cuentan como invocaciones del modelo. Antes de
lanzar se guardan `reserva.json` y el contador en `resultado.json`. La reserva
es conservadora: si después desaparece la CLI, sigue contabilizada como un intento,
sin afirmar que el servicio haya recibido o completado una llamada.

| Salida | Significado |
| --- | --- |
| 0 | Borrador generado, incluso con aclaraciones o fuera del alcance actual. |
| 1 | Fallo de planificación; no se publica una propuesta válida parcial. |
| 2 | Argumentos incorrectos. La ayuda termina con 0. |

Los estados finales son `borrador`, `necesita_aclaraciones` y `fallo_tecnico`;
`preparando` y `planificando` son estados transitorios. `fallo.tipo` distingue
CLI ausente, incompatibilidad, fallo de proceso, timeout, interrupción, respuesta
inválida, integridad y errores de controlador/registro. Los canales normales van
a stdout; un fallo va a stderr. Una interrupción también termina con código 1.

Cada ejecución crea exclusivamente `runs/<fecha>_plan_project_<id>/`:

- `materiales/`: solicitud, contexto, instrucciones, esquema y, si se seleccionaron,
  referencias explícitas; en continuaciones, también los datos de continuación.
- `planificador/`: prompt de entrada, versión, consultas previas, eventos,
  stderr y respuesta original, también ante errores.
- `procedencia.json`, `proyecto_antes.json`, `resultado.json`, tiempos y hashes.
- `reserva.json` solo si se reservó la invocación.
- `propuesta.json` y `propuesta.md` solo tras respuesta válida e integridad correcta.

Se cotejan base, proyecto y materiales antes de reservar y al finalizar.
El inventario de conservación excluye registros y configuración privada, según
las reglas existentes. Un temporal, un hash y la detección de modificaciones
**no constituyen aislamiento de seguridad** ni deshacen una alteración externa.
Si el sistema de archivos impide guardar evidencia, la CLI informa del fallo;
no puede garantizar un registro completo en un soporte que no permite escribir.

## Comprobaciones y siguiente paso

Las [pruebas permanentes](../tests/test_plan_project.py) usan repositorios
sintéticos y una CLI prefijada. Comprueban estructura, protocolos, presupuesto,
errores y conservación. **No acreditan la calidad semántica de un modelo real**
ni que sus interpretaciones correspondan a la intención del usuario.

Se ejecutaron 32 métodos enfocados correctos (3,926 s) y dos controles de
compatibilidad v1/v2 correctos (0,030 s y 0,048 s), con Python 3.12.3, sin modelos
ni sockets. Una primera versión había superado 29 métodos; el registro conserva
ambas ejecuciones y las fuentes correspondientes. El cambio posterior añadió el
rechazo temprano de sustitutos Unicode aislados y tres controles adicionales.

La auditoría previa detectó `booking_http.py` con modo local 0664 y el hash
autorizado intacto. Se restauró únicamente su modo 0644, exigido por el contrato
007 y la incorporación anterior; no se cambiaron sus bytes ni permisos de
registros históricos. La causa del modo observado no está determinada. Se
conservan el fallo de auditoría y las identidades antes y después.

La evidencia y las demostraciones simuladas se conservan, fuera de Git, en
`runs/20261020_planificacion_proyectos_desarrollo/`. Su
`validacion_terminal/` acredita la ejecución del usuario del 20 de octubre:
**648 métodos, 259,953 s, Python 3.12.3, código 0**, sin fallos, errores ni omisiones.
El runner ejecutó una vez `python3 -B -m unittest discover -s tests -v`, con
entorno `evaluation`, límite de 600 s y recogida del grupo de procesos.
El cotejo posterior comprobó terminación, canales, las 648 identidades ordenadas,
hashes y conservación del árbol. No se repitió esa ejecución.

Una revisión automática asistida por Codex posterior encontró dos defectos:

- Una solicitud con un sustituto aislado, como `"\ud800"`, atravesaba el parser
  de argumentos y provocaba una excepción al escribir el registro. Ahora se
  rechaza antes de cualquier escritura o invocación, con código 2.
- Una respuesta `{"\ud800":1,"\ud800":2}` generaba un diagnóstico de clave
  duplicada que tampoco podía escribirse como UTF-8. Ahora conserva el bruto
  y registra `respuesta_invalida`, código 1, sin propuesta parcial.

La reproducción anterior al ajuste ejecutó dos métodos: código 1, un fallo y
dos errores. Tras corregir únicamente esas fronteras de Unicode, pasaron
**34 métodos enfocados en 5,173 s**, Python 3.12.3 y código 0. Los controles
incluyen acentos y caracteres válidos fuera del BMP, sin sustituirlos ni
rechazarlos. Los resultados y fuentes están en el registro nuevo excluido de Git
`runs/20261020_planificacion_proyectos_revision_publicacion/`; los anteriores
permanecen intactos.

El descubrimiento de la publicación anterior contó **650 identidades únicas**:
616 anteriores y 34 de planificación. La validación de 648 corresponde al árbol
anterior a estas dos correcciones; no acredita por sí sola aquel árbol final.
La CI automática de la PR hacia `main` ejecuta el descubrimiento completo sobre
la publicación final; su resultado, comando y commit se contrastan por separado.
No se han abierto sockets desde el entorno restringido ni repetido regresiones
de bases congeladas. El servidor HTTP y el controlador de permisos se conservan.

El paso posterior a un borrador revisado es resolver preguntas y supuestos,
definir un contrato y un evaluador **de confianza del usuario**, y preparar
manualmente una configuración admitida por el motor. No hay promoción automática
a `tasks/config`, evaluador generado ni autorización implícita para desarrollar.

## Experimentos reales y corrección de entrega, 21 de octubre de 2026

Los registros reales se conservan sin reescribir sus resultados. El intento
del 20 de octubre, `2026-10-20T182957.275784Z_plan_project_6962b930a7f345b58d015de10ad871b4`,
terminó con `fallo_tecnico`, código 1 y una reserva consumida, durante el arranque
de la CLI. Es distinto de la ejecución aportada del 21 de octubre,
`2026-10-21T123558.309159Z_plan_project_a0cdaf1e30e843e381b5e177e3d22962`:
esta terminó con `necesita_aclaraciones` y código 0, pero pidió el contenido de
los archivos de entrada porque no podía leerlos sin ejecutar comandos.
Su respuesta era estructuralmente válida y semánticamente insuficiente: no
interpretó la petición ni produjo preguntas útiles sobre su alcance.

El controlador enviaba instrucciones para leer solicitud y contexto mientras
prohibía ejecutar comandos. Los archivos del workspace no garantizaban su entrega
al modelo. Ahora incluye los tres materiales en stdin y el prompt pide trabajar
con su contenido. El adaptador compartido, los permisos, la reserva previa y el
máximo de una invocación de 300 s no cambian. No hay heurísticas por frases de la
respuesta ni preguntas de negocio añadidas por el controlador.

La reproducción con CLI simulada falló antes de corregir el controlador:
**1 método, 1 fallo, 0,227 s, código 1**. Tras el cambio pasaron **36 métodos
enfocados, 6,686 s**, y tres comprobaciones de compatibilidad: configuración v1
(0,033 s), v2 (0,063 s) y adaptador compartido de revisión (0,119 s), un método
cada una, todas con código 0 y sin omisiones, con Python 3.12.3.

La fixture coteja stdin con los materiales archivados antes de emitir su respuesta
prefijada. Se comprueban correspondencia exacta, Unicode, comillas, saltos de
línea, delimitadores aparentes y exclusión de fuentes, secretos sintéticos y
archivos privados. Seis controles negativos omiten o alteran cada material en
stdin: la fixture no responde aunque los archivos del workspace estén intactos.
Esto acredita entrega de información, no comprensión semántica. El fallo previo,
los canales, comandos, fuentes y hashes están en el registro privado nuevo
`runs/20261021_planificador_materiales_en_mensaje/`.

La ejecución real posterior, aportada para este cierre,
`2026-10-21T125637.070636Z_plan_project_839636f0bd2c4f9eb77e8fbe79b4e024`,
terminó con código 0 y `necesita_aclaraciones`. Su respuesta original tiene
SHA-256 `7874fa15c041b661711bf9a775aeb63f59bde71a8e5de52a884d06b6612a0927`.
Se cotejaron entrada, materiales, fuentes registradas, respuesta, propuesta JSON
y representación Markdown. La CLI empleó 33,207 s de los 300 s reservados, con
una invocación; el controlador empleó 33,404 s. Este cierre analiza esa ejecución
conservada y no realiza una planificación nueva.

El contraste automático asistido por Codex distingue dos conclusiones:

- **Estructura:** respuesta válida, procedencia y textos enviados coherentes con
  la evidencia; estado adecuado para una petición aún sin concretar.
- **Utilidad semántica de este caso:** interpreta «Créame una API de reservas» y
  pregunta qué se reserva, qué datos y operaciones se necesitan, qué interfaz se
  espera, si debe persistir, qué reglas de disponibilidad/cancelación aplican y
  si se requiere autenticación o permisos. Ofrece opciones sin convertirlas en
  decisiones confirmadas. No inventa respuestas ni funcionalidades de módulos
  conocidos solo por nombre; mantiene Python, biblioteca estándar y protección
  de infraestructura. Dejar archivos y criterios vacíos es coherente mientras
  falten esas decisiones. La pregunta de acceso no impone autenticación.

Esta valoración no exige una redacción literal ni demuestra fiabilidad general.
Tampoco convierte el código 0 anterior en una planificación útil ni acredita
haber resuelto causalmente el EROFS del primer intento. Los tres históricos
permanecen intactos, con sus reservas y resultados originales.

El cierre reutiliza las 36 pruebas enfocadas y las tres de compatibilidad tras
cotejar sus fuentes, dependencias versionadas, canales y hashes; solo se amplía
la documentación del contraste. El inventario actual, obtenido sin ejecutar
métodos, contiene **652 identidades únicas**, sin errores de descubrimiento.
Las 650 pruebas anteriores acreditan su publicación anterior, no este árbol.
La validación completa de la publicación corresponde a la CI automática del
nuevo commit en la [PR #17](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/17),
cuyo resultado y SHA probado se contrastan por separado. No se repite localmente
la suite completa. La evidencia detallada del cierre queda fuera de Git en
`runs/20261021_planificador_cierre_publicacion/`.

Al cerrar aquel hito, el borrador seguía pendiente de respuestas y revisión
humana y todavía no existía una CLI de continuación. Sus resultados no autorizan
encadenar desarrollo, evaluación o incorporación.

## Continuación con respuestas explícitas

La ampliación posterior parte de `c09cf5ddca749c77da791634890ae1c8712f2f81`
y conserva el comando inicial. Su primera versión (PR #18) añadió estas dos
operaciones. La [ampliación de supuestos](#decisiones-explícitas-sobre-supuestos)
descrita más abajo añade decisiones y permite combinarlas con respuestas:

```bash
python3 -B plan_project.py --from-plan REGISTRO --answers-template respuestas.json
python3 -B plan_project.py --from-plan REGISTRO --answers respuestas.json
```

`REGISTRO` es el directorio original que contiene `resultado.json` y
`propuesta.json`, no una propuesta aislada ni una copia reubicada. La exportación
valida el origen, escribe exclusivamente un archivo nuevo fuera de los registros
de la cadena y no consulta la CLI, crea registros ni reserva presupuesto. No
sobrescribe archivos existentes, tampoco enlaces. Guarda la plantilla fuera de
Git si contiene datos personales; el controlador no modifica las exclusiones.

La segunda operación valida origen y respuestas antes de consultar la CLI o
reservar. Exige al menos una respuesta no blanca. Crea un registro exclusivo,
con **una invocación nueva de hasta 300 segundos**, sin reintentos. No consume ni
reabre reservas de registros anteriores. No admite una solicitud posicional junto
a `--from-plan`; tampoco admite `--answers` o `--answers-template` por sí solos.

### Plantilla de respuestas v1

El objeto tiene exactamente `version: 1`, `tipo: "respuestas_planificacion"`,
`origen` y `respuestas`. `origen` contiene exactamente la ruta absoluta `registro`,
`propuesta_sha256` y `resultado_sha256`. Estos valores los exporta el controlador;
no deben rellenarse ni modificarse manualmente.

Cada elemento de `respuestas` tiene exactamente `id`, `pregunta` y `respuesta`.
La plantilla muestra todas las preguntas pendientes con respuesta vacía. Edita
solo `respuesta`; conserva el conjunto, orden, identificadores y textos de las
preguntas. No se aceptan claves extra, duplicadas, tipos incorrectos ni texto no
representable en UTF-8. Los campos vacíos o solo blancos siguen pendientes. Se
archiva el archivo aportado exactamente, incluidos espacios, Unicode y saltos de
línea; las respuestas no blancas se conservan sin normalizarlas.

Los identificadores son `r0:p1`, `r0:p2`, etc. para la salida original y
`r1:p1`, etc. para las nuevas preguntas de la primera revisión. Los elige el
controlador por profundidad y posición, no el modelo. El origen y sus hashes
desambiguan revisiones distintas. Las preguntas arrastradas mantienen su ID.
No se emparejan textos: si el modelo vuelve a formular una pregunta, recibe un
ID nuevo incluso si el texto coincide. No se infiere que una pregunta antigua
quedó resuelta por desaparecer, reformularse o repetirse.

### Ejemplo de recorrido, exclusivamente sintético

Supongamos un borrador simulado con estas tres preguntas:

| ID | Pregunta | Respuesta de ejemplo |
| --- | --- | --- |
| `r0:p1` | ¿Qué operaciones incluye? | `Consultar` |
| `r0:p2` | ¿Debe persistir reservas? | vacía |
| `r0:p3` | ¿Qué interfaz necesita el usuario? | vacía |

Tras exportar la plantilla, el fragmento editable sería:

```json
"respuestas": [
  {"id": "r0:p1", "pregunta": "¿Qué operaciones incluye?", "respuesta": "Consultar"},
  {"id": "r0:p2", "pregunta": "¿Debe persistir reservas?", "respuesta": ""},
  {"id": "r0:p3", "pregunta": "¿Qué interfaz necesita el usuario?", "respuesta": ""}
]
```

Es un fragmento ilustrativo: el archivo real conserva la cabecera exportada con
los hashes exactos. Si el modelo simulado omite sus preguntas en la nueva salida,
la revisión continúa en `necesita_aclaraciones`: el controlador conserva
`r0:p2` y `r0:p3` pendientes y `Consultar` como respuesta explícita a `r0:p1`.
Una plantilla de esa revisión incluye solo las pendientes. Al contestarlas en
otra revisión se acumulan las tres respuestas. No se pueden modificar ni volver
a presentar respuestas ya aportadas en la cadena. Todos estos datos son
sintéticos; no representan respuestas del usuario al experimento real.

### Datos enviados, procedencia y versiones

El mensaje mantiene `instrucciones` y `materiales`. En las continuaciones añade
el texto JSON íntegro de `continuacion.json`: `version: 1`,
`propuesta_anterior_del_modelo`, `preguntas_identificadas`,
`respuestas_explicitas_del_usuario` acumuladas y `preguntas_sin_responder`.
Se envían además los textos originales exactos de `solicitud.txt` y
`contexto.json`, y el esquema v1. No se envían registros completos, canales,
rutas locales de procedencia, fuentes del proyecto ni configuración personal.
No hace falta leer archivos mediante herramientas. Las prohibiciones del prompt,
el adaptador compartido, `--output-schema` y la validación local se mantienen.

La respuesta del modelo **sigue siendo v1**, y se conserva sin introducirle
respuestas ni preguntas del controlador. Una continuación usa un envoltorio
`propuesta.json` **v2**, con los campos anteriores más `continuacion`:

- `version: 1` identifica este formato de metadatos de continuidad.
- `profundidad` y `padre` vinculan la revisión y los hashes de propuesta y resultado.
- `respuestas_confirmadas` contiene solo respuestas explícitas no blancas del
  usuario; no incluye supuestos ni interpretaciones del modelo.
- `pendientes_anteriores` conserva preguntas aún sin contestar del padre.
- `preguntas_pendientes` une las anteriores y las nuevas preguntas identificadas.

Markdown muestra esos metadatos en una sección separada del texto del modelo.
El estado es `necesita_aclaraciones` si quedan preguntas del controlador o si
lo requiere el estado de la respuesta del modelo. Incluso con todas las preguntas
contestadas, una propuesta es un **borrador no aprobado**: las interpretaciones,
supuestos y viabilidad siguen sujetos a revisión humana. Ninguna respuesta
autoriza desarrollo ni convierte un supuesto en decisión confirmada.

`resultado.json` sigue en v1 y añade `commit_controlador`. `procedencia.json`
registra el commit actual, hashes de las fuentes del controlador y los metadatos
de continuidad. `commit_base` conserva la base de planificación histórica; no se
refresca su inventario al HEAD actual. La integridad del árbol actual y su HEAD
se compara con el inicio de esta ejecución. `respuestas_usuario.json` conserva
los bytes aportados. Los hashes de cada registro incluyen estos artefactos.

El lector admite originales v1, tanto con materiales en stdin como con el antiguo
mensaje que pedía leer archivos, y nuevas continuaciones v2. Revalida respuesta,
propuesta, Markdown, solicitud, contexto, esquema, reserva, estado, materiales y
sus identidades, entrada y hashes de artefactos. Recorre los padres con un límite;
rechaza fallos técnicos, ausencias, incoherencias y archivos o directorios enlazados.
Antes de reservar y después de la invocación también comprueba que los originales
validados siguen intactos. Los hashes acreditan correspondencia, **no autenticidad
frente a quien pudiera reescribir coherentemente toda la evidencia**.

### Límites y salidas

Los límites de [project_plan_continuation.py](../project_plan_continuation.py)
son explícitos y no provocan truncamiento silencioso:

| Recurso | Máximo |
| --- | --- |
| Revisiones desde el original | 8; hasta 9 registros en la cadena |
| Archivo de evidencia leído | 8 MiB |
| Total de evidencia leída de la cadena | 64 MiB |
| Artefactos declarados por registro | 64 |
| Plantilla o archivo de respuestas | 1 MiB |
| Cada respuesta explícita | 8.000 caracteres, sin NUL |
| Mensaje completo para una planificación | 4 MiB |
| Solicitud original / respuesta bruta del modelo | 16.000 caracteres / 1 MiB, como antes |

También se limita el inventario histórico a 10.000 entradas y la lista de
infraestructura a 1.000 nombres. Un exceso impide la nueva invocación; no se
omiten padres ni se descarta contexto para encajar. Al alcanzar ocho revisiones
no se exporta otra plantilla ni se admite otra continuación.

Código **0**: plantilla exportada sin invocación, o borrador generado (incluido
`necesita_aclaraciones`). Código **1**: origen, respuestas, evidencia, escritura,
integridad o ejecución inválidos; no hay propuesta nueva parcial. Código **2**:
combinación de argumentos incorrecta. Los fallos anteriores a crear el registro
se informan por stderr, sin reserva; los posteriores conservan los canales y
contadores según el comportamiento del planificador.

### Comprobación de esta ampliación

Las pruebas de [continuación](../tests/test_plan_continuation.py) usan únicamente
registros temporales sintéticos y comparten la CLI simulada del comando inicial.
La fixture coteja los materiales recibidos por stdin **antes** de emitir su
respuesta. Incluyen originales v1, respuestas completas/parciales, dos revisiones,
preguntas omitidas, cambios de HEAD, identidades, entradas inválidas, límites,
reservas, fallos y recogida de procesos. No acreditan comprensión semántica.
El auxiliar se añade a la protección v2; el motor de desarrollo/revisión y el
adaptador compartido no cambian.

Los comandos, canales, fuentes, demostración y resultados se guardan fuera de
Git en `runs/20261021_continuacion_planificacion/`. La primera comprobación
enfocada superó 52 métodos en 12,804 s; se conservó antes de ampliar los controles
de entradas y límites. La versión ampliada supera **57 métodos enfocados en
13,815 s**, más tres controles de compatibilidad (configuración v1, configuración
v2 y adaptador compartido: 0,026 s, 0,063 s y 0,119 s), todos con código 0 y sin
fallos, errores ni omisiones, en Python 3.12.3. El descubrimiento sin ejecutar
métodos encuentra **673 identidades únicas**, sin errores. La demostración
simulada conserva una respuesta y las otras dos preguntas pendientes, con código
0, sin modelo real, y recoge los temporales.

La **validación integrada local de la PR #18 está superada**. La ejecución aportada por el
usuario en su terminal autorizada, conservada en
`runs/20261021_continuacion_planificacion/validacion_terminal/`, ejecutó una vez
`python3 -B -m unittest discover -s tests -v`: **673 métodos, 257,448 s de unittest,
Python 3.12.3, código 0**, sin fallos, errores ni omisiones. El runner utilizó el
entorno `evaluation`, límite de 600 s y recogida de procesos; cotejó las 673
identidades ordenadas y la conservación del árbol y HEAD.

El cierre contrasta canales, inventario, hashes, modos y tamaños con los 158
archivos actuales, incluido el runner y sus dependencias. La correspondencia
permite reutilizar esa validación; únicamente se actualizan README y esta guía
para documentar el resultado. No se repiten suites por esos cambios documentales.
La evidencia detallada del cierre queda en el registro nuevo excluido de Git
`runs/20261021_continuacion_planificacion_publicacion/`. Los informes históricos,
incluido el que dejaba pendiente esta ejecución, permanecen intactos.

La CI automática de la nueva publicación acredita por separado el SHA probado,
el comando y las identidades ejecutadas. Las validaciones históricas de 650 o
652 métodos corresponden a sus árboles anteriores. Las pruebas de continuación
usan una CLI simulada: no acreditan la utilidad semántica de una continuación
con modelo real, que sigue pendiente de autorización y contraste específico.

En ese cierre no se ejecutaron modelos reales ni se implementó promoción a
contratos, evaluadores o configuraciones, ni incorporación automática.

## Decisiones explícitas sobre supuestos

Esta ampliación parte de `ec883bdd92b3f4ab2bacc595ae738fed000b90d4`, tras la
PR #18. Una continuación real posterior, aportada por el usuario en
`runs/2026-10-21T210836.807412Z_plan_project_503f055ad223467498125d06d966ffcb/`,
conserva seis respuestas explícitas y produce cinco supuestos nuevos, sin
preguntas pendientes. Su estado `necesita_aclaraciones` y código 0 permanecen
intactos. Se inspeccionaron en lectura la propuesta, la respuesta original y los
hashes de sus artefactos. No se decidió ninguno de sus supuestos ni se llamó a
un modelo para este trabajo. El lector ampliado también admite ese registro v2:
deriva `r1:s1` a `r1:s5`, conserva las seis respuestas y comprueba intacta la cadena,
sin exportar una plantilla real ni aportar decisiones.

El código anterior exportaba una lista de respuestas vacía en ese caso, pero
exigía una respuesta no blanca para continuar. El estado era coherente; faltaba
una vía para resolver los supuestos. La reproducción sintética conserva ese
caso (seis respuestas, cero preguntas y cinco supuestos) y acredita el fallo
previo de la nueva operación. Ninguna prueba permanente depende del registro real.

### Operaciones actuales

```bash
# Exportación local, sin consultar la CLI, reservar ni sobrescribir.
python3 -B plan_project.py --from-plan REGISTRO --decisions-template decisiones.json
# Solo decisiones: no necesita --answers ni preguntas pendientes.
python3 -B plan_project.py --from-plan REGISTRO --decisions decisiones.json
# Respuestas y decisiones en una única revisión de hasta 300 segundos.
python3 -B plan_project.py --from-plan REGISTRO --answers respuestas.json --decisions decisiones.json
```

Se conservan la petición inicial, `--answers-template` y `--answers`. Las dos
exportaciones son mutuamente excluyentes y no se combinan con archivos de
continuación ni con una petición nueva. `--answers` y `--decisions` sí pueden
combinarse: ambos se validan antes de consultar la CLI o reservar y producen
**una revisión, una invocación y un máximo de 300 s**, sin reintentos.
Debe haber al menos una respuesta nueva no blanca o una decisión efectiva nueva;
un archivo de respuestas sin contestar puede acompañar decisiones efectivas,
y viceversa. Los archivos vacíos o inválidos no habilitan ninguna invocación.

### Formato cerrado de decisiones v1

La plantilla contiene exactamente `version: 1`,
`tipo: "decisiones_planificacion"`, `origen` y `decisiones`. El `origen` contiene
la ruta absoluta `registro` y los hashes `propuesta_sha256` y `resultado_sha256`
del padre exacto. Cada elemento de `decisiones` contiene exactamente:

| Campo | Regla |
| --- | --- |
| `id` | Asignado por el controlador: `r0:s1`, `r0:s2`, `r1:s1`, etc., por revisión y posición. |
| `supuesto` | Texto original exacto; no se edita para corregirlo. |
| `origen_supuesto` | Registro y hashes de la propuesta y resultado donde apareció ese supuesto; puede ser un antepasado del padre actual. |
| `decision` | `sin_decidir`, `aceptar`, `rechazar` o `corregir`. |
| `explicacion` | Texto no blanco únicamente para `rechazar`; en los demás casos debe ser exactamente `""`. |
| `alternativa` | Formulación explícita no blanca únicamente para `corregir`; en los demás casos debe ser exactamente `""`. |

`origen_supuesto` usa las mismas tres claves que `origen`. Conserva todos los
campos de procedencia, IDs, textos y el orden exportados. Edita únicamente
`decision`, `explicacion` y `alternativa`, con estas combinaciones:

| Decisión | Explicación | Alternativa | Efecto |
| --- | --- | --- | --- |
| `sin_decidir` | `""` | `""` | Sigue pendiente; es el valor inicial de la plantilla. |
| `aceptar` | `""` | `""` | Adoptar expresamente el supuesto original. |
| `rechazar` | No blanca | `""` | Registrar que no debe adoptarse y el motivo; no inventar una alternativa. |
| `corregir` | `""` | No blanca | Aportar la formulación alternativa explícita. |

Los textos aportados se conservan exactamente, incluidos Unicode, espacios y
saltos de línea. Se rechazan claves duplicadas o extra, tipos incorrectos,
Unicode inválido, NUL, IDs desconocidos, decisiones sobre elementos ya resueltos,
orígenes alterados y combinaciones de campos incoherentes. No se permite
sustituir decisiones anteriores; la plantilla incluye solo supuestos pendientes.

### Demostración exclusivamente sintética

Un registro simulado contiene seis respuestas, cero preguntas y cinco supuestos
identificados como `r1:s1` a `r1:s5`. Tras exportar la plantilla, este ejemplo
edita solo los tres campos de decisión, manteniendo la procedencia generada:

| Supuesto sintético | Decisión | Texto aportado en el ejemplo |
| --- | --- | --- |
| `r1:s1` | `aceptar` | Ningún texto adicional. |
| `r1:s2` | `rechazar` | Explicación: `No adoptar este supuesto sintético.` |
| `r1:s3` | `corregir` | Alternativa: `Formulación alternativa exclusivamente sintética.` |
| `r1:s4` y `r1:s5` | `sin_decidir` | Ambos campos vacíos. |

La salida simulada omite los supuestos. El controlador conserva las seis
respuestas y las tres decisiones por separado, mantiene dos supuestos pendientes
y devuelve `necesita_aclaraciones`, código 0. Si en otra revisión se resuelven
todos y el modelo no introduce otros asuntos pendientes, puede resultar un
`borrador`. Ninguna de estas operaciones aprueba ni autoriza desarrollo. El
ejemplo no contiene decisiones del usuario sobre sus supuestos reales.

### Procedencia, compatibilidad y estado

El esquema de respuesta del modelo **sigue en v1**. La petición inicial sigue
produciendo un envoltorio de propuesta v1. Las continuaciones nuevas generan
`propuesta.json` **v3**, con `continuacion.version: 2`; se mantiene la lectura
de originales v1 y revisiones v2 con metadatos v1. El formato de archivos de
respuestas sigue siendo v1. No se reescribe ni reclasifica la evidencia anterior.
Una revisión v3 no puede volver al formato v2 para perder sus decisiones.

Los nuevos metadatos conservan los campos de respuestas y preguntas anteriores,
y añaden `decisiones_confirmadas`, `supuestos_anteriores` y
`supuestos_pendientes`. Cada decisión conserva el supuesto y su origen, además
de la acción y el texto explícitos. El término «confirmadas» identifica datos
aportados expresamente por el usuario, incluida la decisión de rechazar; no
significa que se adopten todos los supuestos. La respuesta original del modelo
se conserva por separado y no se modifica para introducir decisiones o pendientes.

El lector deriva IDs deterministas para los supuestos de los registros antiguos.
Arrastra los no decididos de la cadena aunque un modelo posterior los hubiera
omitido. No infiere identidad ni resolución por texto, por respuestas a preguntas
distintas ni por el estado histórico. Los estados archivados se validan con las
reglas de su versión, sin reescribirlos. Cada supuesto nuevo del modelo recibe un
ID nuevo, incluso si repite literalmente uno aceptado o corregido.

El estado de una revisión nueva sigue siendo `necesita_aclaraciones` mientras
queden preguntas o supuestos pendientes, o la viabilidad lo requiera. Resolverlos
puede producir un borrador; nunca aprobación. La solicitud y el contexto siguen
siendo históricos; el árbol y el HEAD actuales se comparan con su propio estado
inicial. Las decisiones anteriores se acumulan sin reemplazos. Los hashes
acreditan correspondencia, no autenticidad frente a una reescritura integral.

`decisiones_usuario.json` conserva los bytes exactos del archivo aportado. Si
también se aportan respuestas, se archiva `respuestas_usuario.json`; no se fabrica
uno vacío cuando no se suministra. El mensaje incluye el texto archivado de
`continuacion.json` v2, con los campos anteriores y:

- `supuestos_identificados`: ID y texto de los pendientes del padre.
- `decisiones_explicitas_del_usuario`: decisiones acumuladas con ID, supuesto,
  acción, explicación y alternativa.
- `supuestos_sin_decidir`: pendientes que no recibieron una decisión efectiva.

Las rutas y hashes de procedencia permanecen en el registro; el modelo recibe
las referencias textuales necesarias, sin registros completos ni fuentes,
credenciales o configuración personal. El prompt distingue las decisiones de
los nuevos supuestos. Esta separación no acredita automáticamente el cumplimiento
semántico por el modelo: requiere un contraste específico de cada propuesta.

### Límites, comprobaciones y pendientes

Se conservan los límites de ocho revisiones, 8 MiB por archivo de evidencia,
64 MiB de cadena, 64 artefactos por registro y 4 MiB de mensaje. Cada plantilla
admite hasta 1 MiB. Los archivos aportados de respuestas y decisiones, **sumados**,
admiten hasta 1 MiB; cada explicación o alternativa admite 8.000 caracteres.
No se trunca ningún texto ni se amplía el presupuesto para combinar operaciones.
Las restricciones del agente, el adaptador compartido y el motor no cambian.

Los códigos siguen siendo 0 (plantilla exportada o borrador generado), 1 (datos,
integridad o ejecución inválidos, sin propuesta nueva parcial) y 2 (argumentos
incompatibles). Un rechazo de entradas ocurre antes de consultar la CLI o reservar.

Las [pruebas sintéticas](../tests/test_plan_decisions.py) comprueban stdin antes de
emitir la respuesta prefijada. Cubren decisiones sin preguntas, las cuatro
acciones, entradas combinadas, acumulación, omisiones, formatos históricos,
procedencia, Unicode, límites, errores y ausencia de aprobación automática.
La reproducción inicial conservada ejecutó un método con un fallo (0,380 s);
tras la primera corrección, el mismo caso pasó (0,625 s). Una batería enfocada
posterior superó 73 métodos (22,519 s). La revisión detectó además una pérdida
de decisiones al degradar una revisión v3 al formato v2: la reproducción
conservada falló (un método, 0,557 s) y se añadió su rechazo explícito.

Tras ese ajuste pasaron **74 métodos enfocados en 24,517 s** y tres controles
de compatibilidad: configuración v1 (0,030 s), configuración v2 (0,063 s) y
adaptador compartido (0,119 s), un método cada uno. Todos terminaron con código
0, sin fallos, errores ni omisiones, con Python 3.12.3. El descubrimiento sin
ejecutar métodos encuentra **690 identidades únicas**, sin errores. La demostración
simulada completó el recorrido descrito: seis respuestas conservadas, tres
decisiones, dos supuestos pendientes y ninguna aprobación.

La evidencia de desarrollo, los comandos, canales, hashes y la demostración quedan
en `runs/20261021_decisiones_supuestos/`, fuera de Git. Sus informes históricos,
incluido el que dejaba pendiente la suite integrada, permanecen intactos.

La **validación integrada local de esta ampliación está superada**. La ejecución
aportada por el usuario en su terminal autorizada se conserva en
`runs/20261021_decisiones_supuestos/validacion_terminal/`. El runner ejecutó una
vez `python3 -B -m unittest discover -s tests -v`: **690 métodos, 300,325 s de
unittest, Python 3.12.3, código 0**, sin fallos, errores ni omisiones. Utilizó el
entorno `evaluation`, un límite de 600 s y recogida de procesos; la duración del
proceso completo fue de 300,642 s. Las 690 identidades ordenadas coinciden con el
inventario y se conservaron el árbol y HEAD.

El cierre del 22 de octubre contrastó el informe con ambos canales, el manifiesto
de hashes y los 159 archivos del árbol evaluado, incluidos el runner y sus
dependencias. Todos coincidían en contenido, modo y tamaño antes de actualizar
exclusivamente README y esta guía. **Estos cambios documentales son posteriores
a la suite**; el código, las pruebas y sus dependencias permanecen iguales, por
lo que se reutiliza la validación sin repetir suites locales. La evidencia de
este cotejo y de la publicación queda por separado, excluida de Git, en
`runs/20261022_decisiones_supuestos_publicacion/`.

La CI automática de la publicación se comprueba por separado sobre su SHA,
comando, versión de Python e identidades ejecutadas. Las 673 pruebas locales y
la CI del hito anterior acreditan únicamente su árbol histórico. Las pruebas de
planificación de esta suite utilizan respuestas simuladas: **la utilidad semántica
de una continuación real con decisiones sigue pendiente** y requiere autorización
expresa y contraste específico. No se han ejecutado modelos reales para este
cierre ni se convierte el borrador en contratos, evaluadores, configuraciones o
tareas ejecutables.

## Modelo y esfuerzo por ejecución

`--model` y `--reasoning-effort` son opciones independientes y opcionales para
una petición inicial o una continuación, incluidas las que combinan respuestas
y decisiones. Por ejemplo, estos comandos **invocarían** un modelo al ejecutarlos:

```bash
python3 -B plan_project.py "Descripción del trabajo" --model gpt-6-astra --reasoning-effort medium
python3 -B plan_project.py --from-plan REGISTRO --decisions decisiones.json --model gpt-6-astra --reasoning-effort medium
```

Sin opciones se conserva el comando anterior y Codex aplica sus valores de
configuración habituales. No se leen ni escriben archivos personales para
seleccionar el modelo. Una continuación no hereda las opciones solicitadas en
el padre: cada ejecución selecciona las suyas o deja la selección a Codex.

El modelo admite un identificador de 1–200 caracteres ASCII: comienza por letra
o dígito y continúa con letras, dígitos, `.`, `_`, `:`, `/` o `-`. No se comprueba
su disponibilidad mediante una llamada. El esfuerzo admite `none`, `minimal`,
`low`, `medium`, `high`, `xhigh`, `max` y `ultra`; aceptar un valor en el controlador
no garantiza que todos los modelos o versiones de Codex lo admitan. La
[referencia oficial de configuración](https://learn.chatgpt.com/docs/config-file/config-reference)
define `model_reasoning_effort` y advierte que los niveles dependen del modelo
y cliente. La [ficha de GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)
incluye `medium`; no acredita por sí sola acceso desde una cuenta concreta.

Se transmiten argumentos separados, sin shell: `--model`, el identificador,
`--config` y `model_reasoning_effort="VALOR"`. Las comillas dobles del último
argumento forman parte del valor TOML que recibe Codex, no de una orden de shell.
El adaptador compartido incorpora parámetros opcionales; sin ellos produce
exactamente el mismo argv que antes. Si se solicita modelo, comprueba además
que la ayuda de la CLI anuncie `--model`, antes de reservar.

Las exportaciones `--answers-template` y `--decisions-template` excluyen ambas
opciones de ejecución. La CLI rechaza estas combinaciones y argumentos inválidos
con código 2, antes de leer el origen, consultar Codex o reservar. La API Python
también valida los valores antes de consultar la CLI. Exportar una plantilla
sin estas opciones continúa siendo una operación local sin invocación ni reserva.

Cuando se solicita al menos una opción, `resultado.json` y `procedencia.json`
añaden `opciones_solicitadas`, con `model` y `reasoning_effort`; null significa
que ese parámetro no se especificó. Son **valores solicitados, no confirmación
del modelo o esfuerzo efectivamente servido**. El runner conserva el comando
exacto en `planificador/resultado.json`, también recogido en el resultado general,
según su comportamiento existente. La selección solicitada se archiva antes de
la invocación; no se reconstruye un cierre si el proceso no llega a registrarlo.
Sin opciones no se añade ese campo. Los formatos de propuesta, respuesta y
continuidad, así como el lector de registros históricos, no cambian.

Se mantienen una única invocación, reserva previa, máximo de 300 s, ausencia de
reintentos, sandbox de solo lectura, permisos, entorno, validación local e
integridad. No se añade una selección de modelo a los demás consumidores del
adaptador ni se cambia la configuración personal de Codex.

### Comprobaciones del 22 de octubre

La CLI instalada `codex-cli 0.162.1` anuncia `--model` y `--config`. Versión,
ayuda y ayuda con las dos opciones solicitadas terminaron con código 0, sin
llamada al modelo. Las tres consultas emitieron un aviso EROFS al preparar
alias de PATH; se conserva el aviso, sin cambiar permisos ni atribuirle la
causa de ejecuciones anteriores. `--help` acredita sintaxis, no que un modelo
esté disponible ni qué esfuerzo aplicaría el servicio.

La [fixture](../tests/test_plan_execution_options.py) exige el argv exacto antes
de emitir una respuesta prefijada, además de las comprobaciones previas de
stdin. Cubre ambas opciones, opciones individuales, ausencia de opciones,
argumentos inválidos, exportaciones, ayuda incompatible, continuación con
respuestas/decisiones y no herencia de selección. Una prueba que altera lo
esperado por la fixture verifica que esta no emite respuesta. Se conserva el
fallo previo: un método, código 1, porque la CLI del planificador todavía
rechazaba las opciones nuevas con código 2.

Validación con Python 3.12.3, respuestas simuladas y sin modelos reales:

| Comprobación | Métodos | Tiempo unittest |
| --- | --- | --- |
| Suite enfocada `test_plan*.py` | 82 | 30,873 s |
| `test_review_case.py` | 28 | 7,672 s |
| `test_review_project.py` | 23 | 4,677 s |
| `test_process_environment.py` | 9 | 2,244 s |
| Configuración v1: dos tareas con archivo existente/ausente | 1 | 2,325 s |
| Configuración v2: varios archivos y materiales de revisión | 1 | 2,129 s |

Los 144 métodos terminaron correctamente, sin errores, fallos ni omisiones.
El cierre cotejó canales, identidades, hashes, fuentes y dependencias; la evidencia
previa permanece intacta en `runs/20261022_planificador_modelo_esfuerzo/`, fuera
de Git. La revisión posterior detectó que una plantilla con ruta vacía podía
confundirse con una petición inicial, incluso al combinarla con `--model`.
Una reproducción simulada conservada falló antes de corregirlo: un método,
código 1, seis combinaciones y la comprobación de no iniciar planificación.
Ahora la CLI rechaza la ruta vacía con código 2 antes de consultar o reservar.

Después de esa corrección mínima pasaron **12 métodos afectados, 4,606 s, código
0**, sin errores, fallos ni omisiones: los nueve de opciones de ejecución y tres
de argumentos/exportación de las interfaces anteriores. Las **82 enfocadas
anteriores se conservan como resultado previo**, no como una ejecución del parser
corregido. Se reutilizan las **62 de compatibilidad**: el adaptador compartido,
sus consumidores evaluados y sus dependencias no cambiaron con este rechazo.
La guía se actualiza después de esas comprobaciones.

### Continuación real contrastada y validación integrada

La ejecución aportada por el usuario del **22 de octubre, 15:49:13 UTC**, con
opciones solicitadas **`gpt-6-astra` / `medium`**, terminó en **`borrador`, código
0**, con una invocación de **148,389 s** (148,668 s del controlador). Se leyó su
registro, sin lanzar otra planificación. El lector existente validó la cadena,
los hashes de materiales, la respuesta y las propuestas JSON/Markdown; el mensaje
incluido en eventos coincide exactamente con la respuesta archivada. Las fuentes
registradas coincidían con las del cotejo inicial; la única corrección posterior
del controlador es el rechazo de plantillas con ruta vacía descrito arriba. No
modifica la entrega de materiales ni el argv de esta continuación válida. Esto
acredita estructura y correspondencia, separadamente del contraste semántico.

El borrador conserva **seis respuestas y cinco decisiones explícitas**, sin
preguntas ni supuestos pendientes. Adopta `/availability`, el objeto `solicitud`
y el campo `recurso`, fechas estrictas con `Z` y la precedencia HTTP aportada;
mantiene la consulta sin persistencia y delegación en `booking_core.check_booking`.
Excluye modificar `booking_core.py` y `check_booking.py`. Solo contempla eventuales
ajustes de `booking_http.py` cuya necesidad se demuestre con la lectura del código
y una revisión posterior. Reconoce que el inventario no acredita comportamiento
ni modo actual. **Es un borrador útil para revisión en este caso, no aprobación
ni autorización de desarrollo**, y una ejecución no demuestra fiabilidad general.

El SHA-256 del mensaje de entrada es
`d0c984fc42d6f35b4209e4041d6af05da6b11e3ff559c2cb2ade65703ee2bf93`:
coincide byte a byte con el intento del mismo día a las 13:49:54 UTC, que conserva
su estado de fallo técnico por timeout de 300 s y código 1. Ese comando anterior
no fijaba modelo ni esfuerzo por argv; **no se demuestra que `xhigh` causara el
timeout**. Los eventos del intento completado tampoco confirman por separado el
modelo y esfuerzo efectivamente servidos. La integridad histórica del workspace
temporal, ya eliminado, sigue siendo la declarada por el controlador; el cotejo
actual acredita solo los archivos y hashes que se conservan.

La terminal autorizada del usuario superó la **regresión integrada de 699 métodos,
355,530 s de unittest, Python 3.12.3, código 0**, sin fallos, errores ni omisiones.
Ejecutó una vez `python3 -B -m unittest discover -s tests -v` mediante
`repair_case.run_process`, entorno `evaluation` y límite de 600 s. El cotejo de
publicación verificó canales, manifiesto, inventario, identidades ordenadas y los
160 archivos evaluados, incluidos fuentes, pruebas y dependencias. El controlador
registró árbol y HEAD conservados; el cotejo actual los confirmó antes de esta
actualización documental. **La guía y la descripción de PR se actualizaron después
de la suite**; el código no cambió y se reutiliza la validación sin repetirla.

Hay una discrepancia temporal conservada: entre `16:21:05.305433Z` y
`16:50:56.024676Z` del 22 de octubre transcurren **1790,719243 s según las marcas
UTC**, frente a **355,964983946 s registrados por el proceso**. El runner mide
duración con `time.monotonic()` y obtiene las marcas UTC mediante
`datetime.now(timezone.utc)`; unittest usa `time.perf_counter()` y el plazo de
`subprocess.communicate` usa un reloj monotónico. Son medidas distintas. No hay
evidencia suficiente para atribuir la divergencia a suspensión o ajuste de reloj,
ni para afirmar un plazo inferior a 600 s entre las marcas UTC. La discrepancia
no invalida por sí sola los canales y las demás comprobaciones de esta ejecución;
no se altera el registro original.

La ejecución real anterior sigue acreditando la versión previa al rechazo de
plantilla vacía; esta regresión posterior sí incluye esa corrección y utiliza
modelos simulados en las pruebas del planificador. La CI automática de la
publicación se comprueba separadamente sobre su SHA e identidades, sin atribuirle
resultados de publicaciones anteriores ni solicitar otra planificación real.

El contraste y la validación original se conservan en
`runs/20261022_planificador_modelo_esfuerzo_cierre/`; el cotejo de publicación y la
explicación temporal, en `runs/20261022_planificador_modelo_esfuerzo_publicacion/`.
Ambos registros quedan excluidos de Git.

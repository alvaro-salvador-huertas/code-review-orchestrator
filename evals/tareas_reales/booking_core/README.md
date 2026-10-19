# Booking-core, tarea 006

## Incorporación local y uso

La entrega exacta está incorporada localmente como dos módulos regulares 0644:
[booking_core.py](../../../booking_core.py) y
[check_booking.py](../../../check_booking.py). La CLI conserva la interfaz de 005
y delega el dominio en la API Python del núcleo. Solo usa biblioteca estándar;
consulta disponibilidad, sin almacenar reservas ni ofrecer HTTP.

```bash
python3 -B check_booking.py solicitud.json
```

El archivo es un único documento JSON UTF-8 con `solicitud` y `reservas`, según
el [contrato 005](../../../tasks/005-check-booking.md). Código 0 con o sin
conflictos, 1 para entrada inválida y 2 para argumentos incorrectos. La ayuda se
obtiene con `-h` o `--help`. La CLI rechaza claves duplicadas y valida la entrada
completa antes de emitir su único objeto JSON.

La API recibe el mismo documento ya decodificado. Ejemplo sintético de uso:

```python
from booking_core import InvalidInput, check_booking

solicitud = {
    "recurso": "Sala Norte",
    "inicio": "2026-10-20T10:00:00Z",
    "fin": "2026-10-20T11:00:00Z",
}
check_booking({"solicitud": solicitud, "reservas": []})
# {"disponible": True, "conflictos": []}

reserva = {
    "id": "r-2", "recurso": "Sala Norte",
    "inicio": "2026-10-20T10:30:00Z", "fin": "2026-10-20T11:30:00Z",
}
check_booking({"solicitud": solicitud, "reservas": [reserva]})
# {"disponible": False, "conflictos": ["r-2"]}
```

Los documentos inválidos lanzan `InvalidInput`, subclase de `ValueError`, con
explicación. La función valida todas las reservas, no modifica la entrada y
produce resultados independientes, sin imprimir ni acceder a archivos.
`check_booking.check_booking` e `InvalidInput` mantienen sus nombres importables
delegados al núcleo. Los intervalos son `[inicio, fin)` y las fechas, UTC estrictas.

La procedencia es el primer experimento real v2: **un desarrollo y una revisión,
un intento, 2/4 invocaciones**, con dictamen `aprobar` y sin hallazgos. El
[contraste automático asistido por Codex](contraste-real-2026-10-19.md) verificó
el conjunto y recomendó prepararlo para incorporación. La autorización explícita
posterior permitió esta copia exacta, sin refactorizaciones adicionales. No se
reanuda el experimento ni se cambia su `incorporacion: no_realizada` histórico.

Origen: `runs/20261019T204925Z_booking-core_orchestrate_36de525c846a41a5bae8186e800187fb/intentos/1/evidencia/entrega/archivos/`.

| Producto incorporado, modo 0644 | SHA-256 |
| --- | --- |
| `booking_core.py` | `78cbf2cbfca3d1a4ff9c51e6701cdfbe97f7f6d672b5a5cec8780766ea1aa0e0` |
| `check_booking.py` | `e4e7c2a312cb723bb59d85f4420685477990d56c7b25dbe09ae44db8ab9ea4b8` |

Identidad canónica del conjunto, comprobada mediante `project_delivery.identity`:
`68c53e14800a6c8e9dbebaa59bfafee4b0da030ab0ba42898746d95ba8a288f0`.
Antes de copiar se verificó la ausencia del núcleo y el hash original de la CLI
`9a9038910c41d8642fa0deb22554dd192fd61d6415deb88a573b5c4d1465fbfe`.
Las fuentes archivadas conservan sus bytes, modos y metadatos.

## Validación permanente de la incorporación

[tests/test_booking_core.py](../../../tests/test_booking_core.py) hereda los
**38 métodos de aceptación** y
[tests/test_booking_core_evaluator.py](../../../tests/test_booking_core_evaluator.py)
los **30 controles**, sin duplicar aserciones ni lanzar suites secundarias desde
los adaptadores. Cada método se descubre individualmente. El import independiente
`evaluar` se resuelve con un alias temporal que se restaura; se comprobó que no
interfiere con los evaluadores CSV y check-booking ni importa el producto en el
proceso principal. Los procesos hijos conservan intérprete absoluto, `-B`, entorno
`evaluation`, cwd, timeout y comprobaciones de inmutabilidad del evaluador intacto.
Los fixtures auxiliares de los controles no se suman como métodos principales.
Las pruebas anteriores de check-booking y sus criterios permanecen sin cambios.

El **19 de octubre de 2026**, con **Python 3.12.3**, se obtuvieron:

| Ejecución local | Métodos principales | Duración unittest | Fallos / errores / omisiones | Código |
| --- | ---: | ---: | --- | ---: |
| Controles enfocados del adaptador | 30 | 0,958 s | 0 / 0 / 0 | 0 |
| Única regresión completa final | 530 | 246,578 s | 0 / 0 / 0 | 0 |

```bash
python3 -B -m unittest discover -s tests -p test_booking_core_evaluator.py -v
python3 -B -m unittest discover -s tests -v
```

El descubrimiento previo recorrió la suite sin ejecutar métodos: identificó
**530 identidades únicas**, conservando las 462 de la base congelada y añadiendo
38 de aceptación y 30 controles. Las identidades del log completo coinciden
exactamente con ese inventario. La aceptación del producto se ejecutó dentro de
la regresión, sin repetirla por separado. El proceso completo duró 246,839 s;
stdout quedó vacío y stderr contiene el cierre y los resultados detallados de
unittest. El producto y los archivos inventariados conservaron contenido y
metadatos durante las pruebas; los dos hashes y la identidad canónica del conjunto
se comprobaron de nuevo después.

Evidencia nueva, local y excluida de Git:
`runs/20261019T212225Z_booking-core_incorporacion_244e146ff0b746ba8212ead0f054e101/`.
Conserva `procedencia.json`, `incorporacion.json`, `descubrimiento.json`, los
comandos, versión, códigos, duraciones y ambos canales en `enfocadas/` y
`regresion/`, así como inventarios de archivos antes y después. El cierre incluye
la correspondencia de identidades y la conservación del conjunto y del trabajo
previo. Los cambios posteriores a las pruebas son exclusivamente documentales;
no se atribuye inmutabilidad a todo el árbol después de esa actualización.

Esta validación local es distinta de la CI de la base y de las cuatro evaluaciones
del experimento, cuyos resultados y autoridades no se alteran. No acredita una
nueva ejecución remota de Actions, modelos nuevos ni fiabilidad general.

## Evidencia histórica de preparación

Los apartados siguientes conservan el estado anterior a la ejecución real y a
la incorporación. Las expresiones de ausencia, preparación o ejecución pendiente
se refieren a ese momento, no al producto actual. La base y configuración históricas
no se actualizan al árbol incorporado.

Materiales preparados para la **primera tarea real configurable v2**, todavía
sin ejecución de agentes ni producto refactorizado. El futuro experimento
evaluará el conjunto de dos módulos: extraer el núcleo de reservas de la CLI
existente. No constituye una API HTTP, almacenamiento ni garantía de fiabilidad
general. `booking_core.py` sigue ausente y `check_booking.py` no se ha modificado.

## Contrato, configuración y límites

- [Contrato 006](../../../tasks/006-booking-core.md): API Python sin efectos,
  validación íntegra, conservación profunda, resultados independientes y CLI
  delegada. Solo `check_booking.check_booking` e `InvalidInput` se mantienen como
  nombres importables públicos delegados; no se exige publicar helpers privados.
- [Contrato 005 protegido](../../../tasks/005-check-booking.md): reglas funcionales
  heredadas. Su antiguo alcance de un archivo se sustituye únicamente para 006.
- [Configuración v2](../../../tasks/config/booking-core.json): `check_booking.py`
  existente y `booking_core.py` ausente; ningún caso especial añadido al motor.
- [Prompt de desarrollo](../../../prompts/developer_booking_core_flow.md) y
  [prompt de revisión](../../../prompts/reviewer_booking_core_flow.md): conjunto
  completo, delegación efectiva y ausencia de reglas duplicadas, con referencia
  protegida a 005 para ambos roles.
- [Evaluador externo](evaluar.py) y [controles](comprobar_evaluador.py).

Base exacta: `2448d88a8fd89f73415140f3b789292df6a97482`, coincidente con `main`
actualizado al comenzar esta preparación. Rama: `feat/tarea-nucleo-reservas`.
El árbol Git contiene `check_booking.py` regular **100644**, blob
`e9d1ab76d12d3adf7ae8f08e1451a13d1ad0ab84`, y no contiene `booking_core.py`.
Las copias congeladas conservan 0644; el checkout local existente tenía 0664 y
se conserva así. El futuro conjunto debe conservar el modo de Git del existente
y crear el módulo nuevo regular 0644, sin fabricar un original vacío.

| Límite | Segundos |
| --- | ---: |
| Cada desarrollador / revisor | 300 / 300 |
| Aceptación / regresión | 60 / 600 |
| Inventario | 30 |
| Cada consulta previa a la CLI de agentes | 10 |
| Cada hijo de comprobación CLI/API del evaluador | 10 |

## Evaluación preparada

El evaluador admite `--project <copia>` y declara **38 métodos explícitos** de
unittest, compatibles con `static_test_ids`: 24 comprobaciones de CLI conservadas
del evaluador actual de 005 y 14 de API y delegación. No importa otro evaluador
ni candidatos en su proceso; depende de `process_environment.py` de las
autoridades, nunca del workspace candidato. No usa un segundo algoritmo de
reservas como oráculo: los conflictos esperados son explícitos.

La API cubre disponibilidad, intervalos y orden; cadenas literales y Unicode;
claves, tipos, fechas UTC y duplicados de identificadores; validación completa;
`InvalidInput` con explicación; conservación profunda en éxito y error;
ausencia de salida; independencia entre llamadas y resultados. La CLI cubre
archivos, JSON inválido y claves duplicadas, UTF-8, argumentos, ayuda, canales,
códigos e inmutabilidad. Los diagnósticos admiten nombres literales, `repr`,
`ascii` y representación JSON del nombre conocido, sin aplicar `unicode_escape`
al mensaje. Exigen identificación y causa, sin una redacción literal.

**Importar los módulos para comprobar una API ejecuta código en un proceso hijo.**
Los hijos usan intérprete absoluto, `-B`, entorno `evaluation`, stdin cerrado,
cwd temporal controlado y timeout. Las llamadas del núcleo reciben un stdin que
rechaza lecturas. Se comprueban archivos, modos y mtimes del proyecto y entradas
antes y después. La captura de canales de la sonda es local al hijo; admite
texto, `.buffer`, `reconfigure` y escrituras a descriptores. Los archivos
temporales de esa instrumentación pertenecen a la sonda, fuera del proyecto y
de las entradas. No es análisis estático ni aislamiento de seguridad; no acredita
ausencia de todo posible acceso externo, reloj o efecto transitorio.

La delegación se comprueba sustituyendo la función del núcleo **antes** de
importar la CLI y arrancándola mediante `runpy` dentro del hijo, con centinelas
de éxito y error. Admite alias y acceso al módulo; no exige un helper `main` ni
una sintaxis de importación. Esa comprobación no demuestra por sí sola ausencia
de reglas duplicadas inactivas: el revisor debe contrastar ambos archivos.

La traza JSON en stdout del evaluador registra procesos, argumentos, entradas y
canales en hexadecimal, códigos y duraciones, con recuentos separados de CLI y
API. El cierre de unittest y los diagnósticos quedan en stderr. Los subtests y
las ejecuciones auxiliares de los controles no se cuentan como métodos nuevos.

## CI de la base e inventario, sin nueva regresión

La [CI automática del merge base](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39320003905),
evento `push`, acabó correctamente: **462 métodos**, **316,290 s**, Python
**3.12.15**, sin fallos, errores ni omisiones. Los logs corresponden al SHA base
anterior y al comando `python3 -B -m unittest discover -s tests -v`. Es evidencia
de la base; no prueba la aceptación de booking-core.

Se validó la configuración mediante `load_task` y se congeló con `freeze_flow`,
sin iniciar el orquestador. La utilidad existente de inventario descubrió
**462 identidades únicas y ordenadas**, idénticas a las 462 de los logs de esa CI.
El hijo de descubrimiento importa módulos y puede ejecutar su inicialización;
recorre la suite sin llamar a `run`, `TextTestRunner` ni métodos de prueba.
El controlador principal no importa las pruebas inventariadas.

Tras revisar la captura de canales se congeló la revisión final en otra copia,
sin sustituir la primera. Ambos inventarios tienen las mismas identidades y
blobs de la base, código 0, canales sin incidencias y copias conservadas, sin
cachés. **No se ejecutó la regresión completa local durante esta preparación.**

## Única aceptación inicial y controles realmente ejecutados

La aceptación inicial se ejecutó una sola vez mediante el runner estructurado
congelado, en una copia temporal intacta de la base, Python **3.12.3** y política
`evaluation`. El cierre fue **38 métodos en 8,423 s**, código **1** (8,488 s del
proceso exterior). La copia conservó exactamente contenido, modos y mtimes.

| Alcance inicial | Métodos | Correctos | Con fallos | Aserciones fallidas | Errores | Omisiones |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CLI existente | 24 | 24 | 0 | 0 | 0 | 0 |
| API y delegación | 14 | 0 | 14 | 15 | 0 | 0 |
| Total | 38 | 24 | 14 | 15 | 0 | 0 |

Las 15 aserciones se deben a `booking_core.py` ausente; el método de delegación
tiene dos subtests fallidos (éxito y error del centinela). No son 15 métodos ni
errores técnicos. Se registraron **218 consultas CLI reales y 0 procesos API**:
las aserciones de ausencia ocurren antes de importar. No se atribuyen esas
consultas al núcleo inexistente. El informe conserva 646 subtests, incluidas
las comprobaciones de conservación; no se suman al total de métodos.

| Controles de esta preparación | Métodos principales | Duración unittest | Resultado |
| --- | ---: | ---: | --- |
| Primera batería | 29 | 0,842 s | Correcta, código 0 |
| Control añadido: alias y acceso al módulo | 1 | 0,138 s | Correcto, código 0 |
| Ampliación a escritura binaria: fixture inicial | 1 | 0,338 s | Código 1; 4 fallos de subtest por `SyntaxError` del hijo |
| Fixture corregido, captura anterior | 1 | 0,335 s | Código 1; 4 fallos de subtest por ausencia de `.buffer` |
| Controles API afectados tras la corrección | 10 | 0,452 s | Correctos, código 0 |

El primer fallo de la ampliación fue un salto de línea interpretado dentro del
código del fixture; se corrigió usando una cadena raw. Después se acreditó el
falso rechazo de una CLI que usa canales binarios: la captura `StringIO` no tenía
`.buffer`. La sonda final captura descriptores reales. Se conservaron ambas
salidas fallidas y sus versiones, sin presentarlas como defectos del producto.
La ampliación comprueba también escritura mediante `os.write`.

El archivo final contiene **30 controles distintos**: los 20 no afectados
quedaron cubiertos por la primera batería y los 10 de API por la última ejecución.
No se afirma una única ejecución de 30 métodos. Usan respuestas prefijadas y
sustituciones acotadas; los módulos sintéticos solo existen en `sys.modules` de
hijos, sin crear archivos candidatos. Comprueban resultados incorrectos,
excepciones equivocadas o vacías, mutación, salida indebida, resultados compartidos,
ausencia del núcleo, canales, códigos, diagnóstico Unicode, archivo y causa.

La revisión de captura ocurrió **después** de la aceptación inicial. Esta conserva
su evaluador original; no se repitió ni se atribuye al evaluador final. El cambio
afecta a la instrumentación API que no llegó a invocarse por la ausencia del
núcleo; los métodos e identidades de aceptación y los casos CLI se conservan.

## Autoridades y evidencia local

SHA-256 de los materiales preparados y referencias:

| Material | SHA-256 |
| --- | --- |
| Contrato 006 | `e30d2f38831c90c70ccd57f4bc74d1c592f0f6f73f543506132c641d72c93830` |
| Configuración v2 | `ffebe88dbb05661c0de2be2020728c5d27def794831310db4ec503b97c3b5cf0` |
| Prompt de desarrollo | `ce7904dbe18e4c10bc21ef6b2ef89e5bc7cd5413bad9f00c3fe79a4b9b56e43d` |
| Prompt de revisión | `dff68f58c584ede3291d77ffd6f70c3e5001cb99dd8f7d58e9c75cf7f3580a06` |
| Evaluador de la aceptación inicial | `9ec5c250e4815d2df519d90b31960f08fc50e6aec25ae8176861a5e6cb54dfd7` |
| Evaluador final | `84309467852b50ff6cbdeb191328c931256595b42ee5008e72c7ec68fd51d655` |
| Controles finales | `af48cd49f7e651d13978b24d5813733cf9201605727cc9fac5bcdadfd62c5344` |
| Contrato 005 protegido | `1cab6e505ba1fd0dadf687d7e6d23facc63bf2827d6802ba9b8e982d30c98198` |
| Producto check_booking.py intacto | `9a9038910c41d8642fa0deb22554dd192fd61d6415deb88a573b5c4d1465fbfe` |
| Utilidad de inventario | `b0b4aca8f40db44ec33dcc3749187ff670bcac08be9518fbd014ed79534cfac2` |
| Política de entorno | `8bd4fc832b472e63f18c97dfd870a9a41fbb1c3f8294a3c0ca83445f64f3a654` |

Evidencia local excluida de Git:
`runs/20261019T203940Z_booking-core_preparacion_3b8932bc004c4b9b8669ac1dcad3199c/`.
Conserva `referencia/` de la aceptación inicial y `referencia-final/`, autoridades,
configuraciones, procedencia Git y manifiestos, inventarios, logs de CI base,
`aceptacion-inicial/pruebas.json`, canales, traza de consultas, árboles antes y
después y cada ejecución de controles. Las copias temporales de aceptación y
fixtures se eliminaron; sus inventarios son evidencia registrada de conservación,
no archivos que sigan disponibles. Las referencias congeladas sí se conservan.
Los registros anteriores no se modifican ni reclasifican.

## Pendiente, sin lanzar el experimento

Comando preparado, **no ejecutado**:

```bash
python3 -B orchestrate_project.py --task-config tasks/config/booking-core.json --max-attempts 2
```

El futuro experimento deberá congelar de nuevo materiales, informe y procedencia,
ejecutar las evaluaciones iniciales completas (aceptación y regresión), reservar
invocaciones y evaluar/revisar el conjunto exacto. No hereda una autorización de
agentes de esta preparación. Después requerirá contraste e incorporación explícita.
No hay un resultado de agentes real, candidato nuevo ni API HTTP que publicar.

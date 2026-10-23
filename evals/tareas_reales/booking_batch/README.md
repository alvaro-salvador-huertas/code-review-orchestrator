# Booking-batch, tarea 008

**23 de octubre de 2026: candidato incorporado localmente por autorización del
usuario; validación integrada local superada, CI y publicación pendientes.**
El archivo regular 0644 de 2213 bytes
conserva exactamente el SHA-256
`7274cb76fb53df6572b03a519c46cda0107bd4399bdf579b89b74f0328792435`.
No se ha corregido ni reformateado durante la incorporación.

Uso: `python3 -B booking_batch.py [--] archivo`. Lee una lista JSON UTF-8 sin
BOM, delega cada documento completo en `booking_core.check_booking` y emite una
lista de resultados en orden. Los errores de entrada no permiten salida parcial.
`-` es un nombre de archivo; las demás rutas con guion inicial requieren `--`.
`-h` o `--help` como único argumento muestran ayuda.

## Experimento e incorporación posterior

El experimento real conservado terminó en `lista_para_revision_humana`, código
0, tras **un intento de dos**, un desarrollo y una revisión: **dos invocaciones
de cuatro**. Aceptación: **25 métodos y 193 subtests**, 3,834 s de unittest.
Regresión de la base congelada: **699 métodos y 3285 subtests**, 294,436 s.
Ambas finalizaron sin fallos, errores u omisiones y con la misma identidad de
candidato. El revisor emitió `aprobar`, sin hallazgos. Su lectura estática y la
lectura completa adicional durante esta incorporación no identificaron un
incumplimiento concreto del contrato 008. Un caso no acredita fiabilidad general.

Se cotejaron ahora los canales, informes, identidades del conjunto y archivos
archivados con sus hashes y modos. Las autoridades congeladas, los materiales
de revisión y el árbol previo coinciden con el registro. La integridad durante
la ejecución es la declarada por el controlador; los workspaces temporales
eliminados no pueden inspeccionarse nuevamente. No se repitieron desarrollo,
revisión ni regresión, y el segundo intento no se consumió.

El histórico mantiene `incorporacion: no_realizada`. La copia exacta a la raíz
es una actuación local posterior, autorizada expresamente por el usuario, con
asistencia de Codex. El origen permanece intacto. Núcleo, CLI individual, HTTP,
motor, contrato, configuración, prompts y evaluador conservan sus bytes. La
configuración mantiene su base congelada, en la que `booking_batch.py` no existe.

## Cobertura permanente y validación integrada

[tests/test_booking_batch.py](../../../tests/test_booking_batch.py) hereda los
25 métodos de aceptación y apunta al proyecto actual.
[tests/test_booking_batch_evaluator.py](../../../tests/test_booking_batch_evaluator.py)
hereda los 24 controles con fixtures sintéticos. Reutilizan las aserciones y el
transporte existentes, sin depender de registros privados. El alias temporal
`evaluar` se restaura y se comprobó su convivencia con los demás evaluadores.

Los dos adaptadores se ejecutaron juntos una sola vez con Python 3.12.3,
política `evaluation` y límite de 120 s; **49 métodos correctos** en 8,665 s de
unittest, código 0, sin fallos, errores u omisiones. Se conservaron las identidades, los canales,
las trazas de los hijos y la comprobación de eliminación de temporales. El
control de timeout incluido recoge su proceso. El descubrimiento completo,
sin ejecutar métodos, conserva las **699 identidades anteriores y añade 49**:
**748 métodos únicos**. Se comprobó que no importa el producto, abre sockets
ni lanza procesos de producto durante el descubrimiento.

La validación conjunta posterior, **ejecutada por el usuario en su terminal
autorizada con loopback**, superó **748 métodos en 414,514 s de unittest**,
código 0, sin fallos, errores u omisiones, con Python 3.12.3. El runner ejecutó
una sola vez `python3 -B -m unittest discover -s tests -v`, con intérprete
absoluto, `repair_case.run_process`, política `evaluation`, límite de 600 s y
canales separados. Registró 415,082777 s de proceso, identidades exactas y
conservación del árbol, HEAD, rama, índice, candidato y origen.

Se cotejaron ahora los canales, inventarios, hashes y las 748 identidades con
las fuentes y dependencias actuales. Se reutiliza esa validación sin repetir
pruebas: los únicos cambios posteriores son este cierre en los dos README.
Las comprobaciones enfocadas de 49 y la regresión congelada de 699 permanecen
como validaciones separadas. **CI y publicación siguen pendientes**; el cambio
queda preparado documentalmente para commit y PR, sin realizarlos en este paso.

Evidencia nueva excluida de Git: `runs/20261023_booking_batch_incorporacion/`.
Contiene el contraste, identidades, fuentes, diff, inventario, canales de las
comprobaciones, runner y la ejecución aportada en `validacion_terminal/`.
El informe y el diff de incorporación permanecen intactos; este cierre y su
diff se registran por separado en `runs/20261023_booking_batch_cierre_documental/`.
El experimento original permanece en
`runs/20261023T102322Z_booking-batch_orchestrate_e6d84c956b104f3e9f59d362b92622ba/`.
Estas rutas documentan procedencia local; las pruebas no dependen de ellas.

## Preparación anterior conservada

Lo que sigue describe el estado previo al experimento: ausencia del producto,
reservas aún sin consumir y comandos entonces pendientes. Se conserva como
cronología de preparación, no como estado actual de la incorporación.

**23 de octubre de 2026: materiales preparados para revisión del experimento.**
Rama `feat/tarea-booking-batch`, base
`9017d6ca212af4447c02da22c0bcd9a5364f6924`. El producto `booking_batch.py`
permanece ausente, también en la base. No hay implementación de referencia,
aceptación positiva de un producto completo, agentes reales ni orquestación.

## Alcance y materiales

- [Contrato 008](../../../tasks/008-booking-batch.md): una ruta literal, lote JSON
  UTF-8 estricto, delegación, resultados en orden y ninguna salida parcial ante
  un error de entrada, incluso en la última consulta.
- [Configuración v2](../../../tasks/config/booking-batch.json): único editable
  nuevo `booking_batch.py`, regular 0644. Núcleo y contratos
  [005](../../../tasks/005-check-booking.md)/[006](../../../tasks/006-booking-core.md)
  como referencias protegidas; ninguna dependencia de `runs/`.
- [Prompt de desarrollo](../../../prompts/developer_booking_batch_flow.md) y
  [prompt de revisión](../../../prompts/reviewer_booking_batch_flow.md): el
  revisor lee el archivo completo sin importarlo ni ejecutar pruebas. Se usa el
  esquema de dictamen existente; tests correctos no sustituyen esa revisión.
- [Evaluador](evaluar.py) y [controles del evaluador](comprobar_evaluador.py).

La futura CLI será `python3 -B booking_batch.py [--] archivo`. `-` es un archivo;
`-- -h` y `-- --help` también. Solo `-h`/`--help` como argumento único muestran
ayuda. Cada consulta se delega intacta en `booking_core.check_booking`; no se
mezclan reservas ni identificadores entre consultas. IDs duplicados dentro de
una consulta son rechazados por el núcleo. No se añaden reglas de negocio,
persistencia, red, HTTP, subprocesses propios ni dependencias. Se protegen
núcleo, CLI individual, HTTP e infraestructura.

| Límite | Segundos |
| --- | ---: |
| Desarrollo / revisión | 300 / 300 |
| Aceptación / regresión | 120 / 600 |
| Inventario / consulta previa CLI | 30 / 10 |

Máximo previsto: dos intentos, un desarrollo y una revisión por intento, sin
reintentos técnicos. No se ha consumido ninguna de esas reservas. Las opciones
de modelo y esfuerzo del planificador no se aplican por ello a estos agentes.

## Procedencia y separación del plan

La solicitud local `runs/solicitud-booking-batch.txt` y el registro
`runs/2026-10-22T195413.429607Z_plan_project_347828335b1b49848897389b4482704f/`
se contrastaron con el lector existente `project_plan_continuation.load_parent`:
materiales, respuesta, propuesta y hashes coherentes; solicitud exacta salvo los
saltos finales eliminados por la sustitución de comandos de shell original.
El SHA-256 de la respuesta es
`1a43c0e53ff83e64ecfcffde9253da0dcd475c6324cec7d0cd0552025cac0ce1`.
El registro conserva `borrador`, código 0, sin preguntas ni supuestos pendientes,
y `aprobada: false`. Esas comprobaciones de consistencia no autentican al autor
ni sustituyen la revisión semántica.

La lectura encuentra correspondencia con el alcance solicitado. El contrato
explicita el rechazo de IDs duplicados **mediante el núcleo existente**, y separa
las lecturas normales del importador de los efectos propios del producto. No
convierte aquellos criterios en una orden de modificar el núcleo. Estos ocho
archivos de preparación son materiales de confianza redactados manualmente por
instrucción posterior del usuario, con asistencia de Codex; no son artefactos
aprobados o ejecutados automáticamente desde el borrador.

El intento anterior que falló al iniciar la CLI por EROFS conserva su fallo;
la ejecución posterior correcta no demuestra su causa ni lo reclasifica. No
se cambiaron configuración personal, permisos históricos o restricciones.

## Evaluador y alcance de sus observaciones

Tiene 25 métodos explícitos compatibles con el inventario AST del motor y un
único `TextTestRunner`. Antes de cada hijo comprueba mediante `lstat` que el
candidato sea regular 0644; ausencia, enlace, FIFO, directorio o modo incorrecto
producen aserciones sin abrir/ejecutar el candidato. No se importa producto en
el proceso padre. Las utilidades se cargan desde la raíz de autoridades.

Reutiliza `repair_case.run_process`: intérprete absoluto, `-B`, `evaluation`,
argv sin shell, cwd temporal, 10 s por hijo, canales separados y recogida del
grupo de procesos al agotar el plazo. El informe conserva comandos, códigos,
tiempos y bytes de entradas/stdout/stderr en hexadecimal incluso tras timeout;
los temporales se eliminan. El proyecto y entradas se comparan antes/después.

Los esperados de disponibilidad son explícitos; no se calculan invocando otro
algoritmo de reservas. Hay casos de lotes vacíos, mixtos, repetidos, IDs entre
consultas, adyacencia/contención, Unicode literal y escapado, errores de dominio
tempranos/tardíos, codificación, JSON, duplicados, archivos, ayuda y rutas.
Las sondas en hijos instrumentan el núcleo en memoria antes de cargar la CLI:
comprueban documentos completos, resultados propagados, mutación e InvalidInput
sin imponer helper o sintaxis de importación. No modifican el núcleo en disco.

La sonda de importación captura descriptores reales y observa lecturas propias,
stdin y eventos de procesos/red. Permite las aperturas normales del cargador
Python, verificadas con dependencias estándar. Es instrumentación acotada, no
aislamiento de seguridad ni garantía exhaustiva contra código que la evada.
El diagnóstico se comprueba por posición y causa no vacía, sin frase literal;
su utilidad y la ausencia general de reglas duplicadas requieren revisión.

## Comprobaciones realizadas

Evidencia local excluida de Git:
`runs/20261023_booking_batch_preparacion/`. Contiene procedencia del plan,
inventarios, fuentes y hashes, canales, informes de proceso, copia fiel de la
base y autoridades de esta preparación. Las pruebas no dependen de ese registro.

- **24 controles finales correctos**, código 0, sin errores ni omisiones,
  Python 3.12.3, 5,575 s de unittest. Fixtures parciales reales y controles
  simulados; no representan un producto completo ni una aceptación positiva.
  Incluyen orden incorrecto, respuesta fija, tipos/canales/códigos, salida
  parcial, falta de delegación, mutaciones antes/después, resultados alterados,
  formas de import, efectos propios y limpieza tras timeout. La comparación de
  argumentos y conservación distingue tipos JSON (`true` no equivale a `1`)
  sin imponer orden de claves.
- **Aceptación sobre la base sin producto:** 25 métodos, 25 fallos de aserción
  esperados por ausencia, cero errores/omisiones y cero hijos de producto,
  código 1. `flow_counts` verifica identidades, informe y cierre del runner
  existente. Acredita la parte de aceptación exigida por la precondición; no
  representa una ejecución autorizada del flujo ni su regresión inicial.
- **Configuración, referencias e inventario:** `load_task`, `freeze_flow` y
  `validate_inventory` validan la copia de blobs y modos Git; se descubren
  **699 métodos de la base sin ejecutarlos**. Los archivos se conservan.

Los canales conservan los fallos intermedios reales: literales bytes con texto
no ASCII en los primeros fixtures, corregidos antes de ejecutarlos, y un nombre
de import incorrecto en el driver privado de validación. Pasaron versiones de
22 y 23 controles. Después, un control nuevo reprodujo dos falsos positivos de
la sonda al cambiar `True` a `1`, antes/después de delegar: 24 métodos,
dos aserciones fallidas en 3,912 s, código 1. La igualdad de Python no distinguía
esos tipos. Se corrigió exclusivamente la comparación de datos de la sonda y
pasaron los 24 controles finales. Se repitió la comprobación de preparación
sobre una nueva copia con ese evaluador; ambas referencias se conservan.

Compatibilidad enfocada, también con Python 3.12.3 y entorno `evaluation`:

| Módulo, agentes simulados | Métodos | Tiempo unittest | Resultado |
| --- | ---: | ---: | --- |
| `tests/test_configurable_projects.py` | 19 | 18,993 s | Código 0, sin fallos/errores/omisiones |
| `tests/test_multiple_projects.py` | 12 | 21,688 s | Código 0, sin fallos/errores/omisiones |

Se ejecutaron mediante descubrimiento limitado a cada módulo. Sus fuentes y
dependencias siguen intactas; la corrección posterior de la sonda no las cambia.
Los cambios documentales de cierre son posteriores a estas comprobaciones.
No se ha repetido la regresión completa de 699 ni se atribuye una CI anterior a
estos materiales nuevos. No quedó ninguna comprobación de preparación bloqueada
por infraestructura.

## Revisión y ejecución futuras

Comando de controles independientes, sin modelos ni producto completo:

```bash
python3 -B evals/tareas_reales/booking_batch/comprobar_evaluador.py
```

Quedan pendientes la revisión de estos materiales y la autorización del
experimento. Su comando está preparado **sin ejecutar**:

```bash
python3 -B orchestrate_project.py --task-config tasks/config/booking-batch.json --max-attempts 2
```

Deberá lanzarse desde la terminal del usuario, dado el EROFS observado al iniciar
la CLI desde el entorno restringido. No se propone eludirlo cambiando permisos,
sandbox o configuración personal. El futuro flujo ejecutará sus precondiciones
y regresiones obligatorias sobre la base congelada. La aceptación de una entrega,
la revisión contractual, su contraste y cualquier incorporación seguirán siendo
pasos posteriores; esta preparación no los acredita ni los autoriza.

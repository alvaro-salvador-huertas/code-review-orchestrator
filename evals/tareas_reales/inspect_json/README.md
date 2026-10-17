# Primera tarea real: JSON del inspector

Preparación del 16 de octubre de 2026 sobre `main`, commit base
`9bec53279d82058fe188c0038bab5ba66ce64003`, en `feat/tarea-inspector-json`.
El árbol estaba limpio. Esa preparación no incorporó la funcionalidad.
**Actualización del 17 de octubre: `--format json` ya está incorporado localmente**
con la entrega autorizada `8abca500…e7b87`, después de las revisiones y correcciones
descritas en la [guía de revisión y estado](revision.md).

La tarea permite consumir la consulta desde otras herramientas sin analizar
su presentación textual. El [contrato v1](../../../tasks/003-inspect-run-json.md)
separa el éxito de la consulta del resultado de la ejecución registrada y
preserva como `null` los datos desconocidos. No se ha añadido un caso defectuoso
al benchmark. En aquel hito de preparación no se invocó a ningún agente.

## Evaluador de aceptación

Desde la raíz del repositorio, con Python 3.12 y biblioteca estándar:

```bash
python3 -B evals/tareas_reales/inspect_json/evaluar.py --project .
```

`--project` acepta también una ruta absoluta a otra copia del proyecto. El
evaluador debe ejecutarse desde su copia protegida, externa al proyecto que
modifica el agente, y apuntar a esa copia candidata. No importa módulos del
proyecto ni las pruebas existentes: invoca `inspect_run.py` por su CLI mediante
`subprocess`, con intérprete absoluto, `-B`, cwd temporal, límite de 10 segundos
por consulta y entorno sin credenciales heredadas ni Codex en `PATH`.

Los registros sintéticos se crean desde cero y se eliminan al terminar. Incluyen
resúmenes generales y enlazados, informes textuales construidos como datos y
referencias históricas leídas por AST. **Esos informes no representan pruebas
ejecutadas ni reparaciones hechas por agentes**. No se leen registros de `runs/`.
Los archivos Python del registro contienen marcadores que detectarían su
ejecución accidental. En cada consulta, incluso cuando falla, se comparan las
entradas, SHA-256, permisos y fechas de modificación del árbol temporal; se
omite atime porque leer puede actualizarlo. Esto comprueba conservación en
estos escenarios, no proporciona aislamiento para código no confiable.

Las 14 pruebas (con variantes mediante `subTest`) comprueban:

- Salida predeterminada y equivalencia de `--format text`, en consultas completas
  e incompletas; la regresión textual más amplia permanece en `tests/`.
- Objeto JSON único, claves y tipos del esquema v1, ambos casos, valores exactos
  y separación de códigos; una ejecución fallida puede consultarse con código 0.
- Ceros explícitos, `null`, datos ausentes y tipos inválidos, sin inventar valores
  ni redondear la duración al formato textual.
- JSON de entrada inválido, ambiguo o no objeto; archivo general ausente;
  informes ausentes, resúmenes enlazados inválidos/discrepantes e intento parcial.
- Rutas relativas con espacios y Unicode, desde otro cwd; argumentos incorrectos,
  canales de salida y conservación de todos los materiales temporales.

El evaluador devuelve **0** si todo pasa, **1** si hay fallos o errores, y **2**
si sus propios argumentos son inválidos. No contiene `expectedFailure`, omisiones
ni conversión de fallos de aceptación en éxito. El módulo sigue fuera de `tests/`,
pero sus 14 métodos se reutilizan ahora en el descubrimiento habitual mediante
[`tests/test_inspect_json.py`](../../../tests/test_inspect_json.py), junto a las
seis comprobaciones de hallazgos, siete de anidamiento y dos métodos textuales
adicionales. No hace falta repetir las suites por separado al ejecutar CI.
Su [referencia inicial](referencia-inicial.md)
conserva el resultado contra el inspector que todavía no admite `--format`.

## Plan previo de incorporación al flujo de agentes

El flujo de benchmark no admite esta tarea directamente: `case_config.py` solo registra
los dos ejercicios de benchmark, `repair_case.py` entrega `solution.py` y evalúa
`test_solution.py`, y `review_case.py` valida materiales/diffs de un único
`candidato.py`. No basta con registrar un `case_03` ni renombrar el inspector.

El plan fijado al preparar la tarea fue:

1. Crear una copia del proyecto base con procedencia explícita (commit, diff y
   hashes de los materiales pertinentes). No incluir `runs/` ni configuración
   personal. El **único archivo editable será `inspect_run.py`**; las utilidades
   compartidas podrán leerse. Conservar un diff de proyecto, no una reparación
   ficticia de `solution.py`.
2. Congelar fuera del alcance de edición el contrato, este evaluador y `tests/`.
   También quedan protegidos el resto del proyecto, los controladores, prompts,
   contratos anteriores y benchmark. Comprobar sus hashes antes y después, y
   rechazar cambios fuera de la lista permitida. Las reglas escritas no sustituyen
   esas comprobaciones ni el aislamiento del proceso.
3. Adaptar la evaluación independiente para pasar `--project` a esta aceptación
   y ejecutar también `python3 -B -m unittest discover -s tests -v` sobre la copia.
   Conservar resultados iniciales y posteriores, stdout, stderr, códigos y
   clasificación de fallos de aserción frente a fallos técnicos. No importar el
   inspector candidato en el proceso del controlador ni usar su copia editable
   del evaluador como autoridad.
4. Preparar contexto de desarrollo y revisión específico del proyecto: contrato,
   cambios permitidos, diff y evidencia independiente. El revisor deberá comprobar
   también incumplimientos fuera de las pruebas. Mantener las reglas de presupuesto,
   detención e integridad; preservar candidatos, hallazgos y fallos reales sin
   inventar reparaciones o reintentar hasta conseguir aprobación.

El hito de preparación no implementó ese adaptador ni inició agentes. El
[primer flujo de desarrollo](desarrollo.md), añadido después, prepara
`python3 -B repair_project.py inspect-json` con copias del proyecto y una sola
invocación máxima. Se validó con una CLI simulada; entonces el intento real
seguía sin lanzarse. En ese hito la revisión real permanecía pendiente. No cambia la
referencia inicial ni las pruebas de aceptación anteriores.

## Preparación del primer intento real — 17 de octubre de 2026

El [informe de preparación y bloqueo del entorno](primer-intento-2026-10-17.md)
documenta la rama `eval/inspect-json-primer-intento`, la ausencia de intentos
previos y la restricción de red conocida antes de ejecutar. El adaptador no se
lanzó: **0 invocaciones de agentes**, sin evaluaciones nuevas, registro ni
candidato. El comando quedó preparado para una terminal con acceso al servicio.
La base congelada se conserva. Ese informe describe únicamente la preparación.

## Primer intento real y reevaluación — 17 de octubre de 2026

El [informe de resultados y reevaluación](reevaluacion-2026-10-17.md) documenta
el intento real posterior: una invocación del desarrollador, código del agente
0 y resultado del controlador `no_supera_comprobaciones`, código 1. Fallaron
dos subtests de un método por exigir el nombre literal `duracion_segundos`
en una incidencia que decía «general: duración inválida».

El contrato permite identificar el campo sin fijar esa redacción. Se ajustó
solo esa aserción para aceptar `duración` o `duracion_segundos` como palabras
completas; permanecen las comprobaciones de valores, tipos, códigos, canales,
esquema y conservación. Las [seis comprobaciones específicas](../../../tests/test_inspect_json_evaluator.py)
verifican ambas denominaciones y rechazan mensajes sin localización, otros
campos y valores inválidos conservados pese a un diagnóstico correcto.

Un registro nuevo conserva **14/14 métodos de aceptación y 6/6 comprobaciones
específicas superados**, con código 0. Se evaluó exactamente el mismo candidato
y se reutilizó la regresión histórica de **153/153**, tras comprobar hashes y
materiales. No se repitió esa suite ni se invocaron agentes. El registro inicial
conserva su rechazo; en ese hito quedó pendiente la revisión independiente.

## Adaptador de revisión independiente

Está preparado [`review_project.py`](../../../review_project.py), con dos
entradas explícitas: el desarrollo original rechazado y su reevaluación.
Comprueba su correspondencia antes de autorizar una sesión de revisión estática
de solo lectura. La [guía de revisión](revision.md) conserva el comando exacto,
los códigos, límites y resultados de validación con Codex simulado.
La primera revisión real agotó sus 180 segundos, con una invocación y sin dictamen.
La segunda, con contexto reducido, solicitó cambios. Las correcciones de booleanos,
duraciones y, tras otra revisión estática, de recursión fueron asistidas por Codex
bajo instrucciones del usuario; no proceden de un bucle automático del adaptador.
La revisión del último diff se realizó en esta conversación antes de autorizar
su incorporación exacta. La guía conserva los dictámenes históricos sin
convertirlos en aprobaciones del controlador. Los registros permanecen excluidos
de Git; las nuevas pruebas de CI utilizan únicamente fixtures temporales.

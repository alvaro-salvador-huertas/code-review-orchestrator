# Primer flujo de desarrollo de inspect-json

El comando preparado para un futuro intento es:

```bash
python3 -B repair_project.py inspect-json
```

**Ese comando puede invocar Codex real. No se ha lanzado el intento real al
implementar este controlador.** La validación de este hito utiliza una CLI
simulada y proyectos sintéticos temporales; no implementa la exportación JSON.
El [contrato 003](../../../tasks/003-inspect-run-json.md), la aceptación y las
pruebas anteriores permanecen intactos. Todavía no se conecta al agente revisor.

## Preparación y autoridad

`repair_project.py` lee el commit completo indicado en el contrato y obtiene
sus archivos de los objetos locales de Git. No usa el contenido actual del
inspector ni hace checkout, reset o limpieza de la rama. Conserva los cambios
pendientes del proyecto original. No descarga referencias de la red: la base
debe existir localmente. Excluye `.git`, `runs/`, cachés y configuración local.
Rechaza enlaces y submódulos en la referencia exportada.

En `runs/<fecha>_inspect-json_<id>/referencia/` conserva el proyecto base, el
contrato y evaluador del árbol de trabajo, el adaptador de pruebas y la
procedencia: commit base, HEAD de origen, estado de los materiales, objetos Git,
permisos y SHA-256. Las pruebas de regresión pertenecen al commit base; las
pruebas nuevas del propio controlador no se añaden recursivamente a esa tarea.
La referencia y el evaluador están fuera del workspace editable.

Antes de desarrollar, evalúa una copia temporal con dos procesos separados:
aceptación externa (60 s) y regresión de `tests/` (180 s). Deben acreditarse
todos los métodos: la aceptación ha de mostrar fallos de aserción por la opción
ausente y la regresión ha de estar completamente superada. Una aceptación ya
verde, una regresión fallida o evidencia inválida no autorizan la invocación.

## Una invocación y una entrega

El workspace del desarrollador es otra copia nueva, fuera del repositorio.
Recibe el contrato, la autorización para modificar solo `inspect_run.py` y
los resultados iniciales, sin una solución propuesta. Se conserva el prompt
efectivo. Las opciones de Codex siguen el modo `workspace-write`, sin web,
delegación ni aprobaciones interactivas de los controladores existentes;
se comprueban versión y ayuda con límites de 10 s. El proceso del agente tiene
un límite de **300 s**, con una reserva previa y como máximo un `codex exec`.
No hay correcciones, reintentos automáticos ni reanudación.

Se recogen `entrega/inspect_run.py`, un diff con `a/inspect_run.py` y
`b/inspect_run.py`, el inventario posterior y los archivos cambiados disponibles.
Se comprueban altas, bajas, directorios añadidos, enlaces, cambios de contenido
y permisos. Borrar el inspector o reemplazarlo por un enlace también infringe
el alcance. Se contrastan además el proyecto original, la referencia y la
evidencia de etapas ya terminadas. No se aplica la entrega al proyecto original.

La evaluación posterior reconstruye una tercera copia desde la referencia e
incorpora **solo** el inspector recogido. No reutiliza el workspace del agente.
Ejecuta de nuevo aceptación y regresión con las autoridades congeladas y los
mismos límites. Se comprueba también que las pruebas no modifiquen esa copia.

## Evidencia de pruebas y resultado

`project_test_runner.py` añade un informe estructurado a `unittest` en el
proceso hijo, sin cambiar las aserciones del evaluador ni importar el inspector
en el controlador. Ejecuta el evaluador congelado con su CLI; para regresión
descubre las copias de las pruebas congeladas en el proyecto evaluado. Esas
pruebas pueden importar módulos como ya hacen, únicamente en el proceso hijo.

Se conservan el comando real del adaptador, cwd, stdout, stderr, código, duración
y `pruebas.json`. Este identifica métodos iniciados y terminados, aserciones,
errores y subtests. Las identidades se contrastan con las fuentes mediante AST,
incluida la herencia local, y con el total y cierre del informe textual. No se
usa el lector de informes de `test_solution.py`. Un fallo de `subTest` incrementa
las aserciones fallidas, **no** el número de métodos. Una salida 1 sin evidencia,
un informe truncado, errores, omisiones o `expectedFailure` no acreditan una
suite superada ni se reclasifican como simples fallos de aceptación.

El resumen `resultado.json` separa proceso del agente, aceptación y regresión
iniciales/posteriores, integridad, reserva e invocaciones. El resultado favorable
se llama **«supera las comprobaciones disponibles»**, nunca aprobación del
revisor. La revisión permanece `pendiente_no_conectada`.

| Código del controlador | Resultado |
| --- | --- |
| 0 | Agente finalizado con código 0, integridad válida y ambas evaluaciones posteriores completas y superadas; falta revisión. |
| 1 | Aceptación o regresión posterior con fallos de aserción acreditados. |
| 2 | Argumentos incorrectos de la CLI. |
| 3 | Fallo técnico de proceso, CLI incompatible, agente con código no cero o errores de pruebas. |
| 4 | Timeout de una etapa. |
| 5 | Cambios no permitidos o alteración de la integridad. |
| 6 | Evidencia inválida/incompleta o evaluación inicial que no autoriza el desarrollo. |
| 7 | Interrupción (SIGINT/SIGTERM atendidas). |
| 8 | Error del controlador, Git, preparación o escritura de registros. |

Los mensajes breves de progreso van a stderr con vaciado inmediato; stdout
contiene el resumen y la ubicación del registro. Las funciones reutilizables
son silenciosas por defecto. Ante fallo o interrupción se conservan las salidas
y entrega disponibles; las utilidades de procesos detienen el grupo de procesos.
Si falla el propio almacenamiento, el resumen puede quedar parcial: se informa
del error y no se declara éxito. No existe un timeout global adicional.

**Las copias, permisos y comprobaciones de hashes no constituyen aislamiento de
seguridad.** Las pruebas ejecutan código con los permisos del controlador; la
comparación posterior no garantiza ausencia de acciones transitorias o accesos
fuera del árbol. Un proceso terminado de forma forzosa puede dejar evidencia
parcial. Este flujo acotado no es un entorno para código arbitrario no confiable.

## Validación del controlador

`tests/test_repair_project.py` construye repositorios Git pequeños con un
inspector ficticio que imprime marcadores, pruebas de aceptación/regresión y
una CLI de Codex simulada. No contiene una implementación de la exportación
JSON. Comprueba éxito, fallos de aceptación y regresión, autorización inicial,
fallo técnico, timeout, interrupción, modificaciones no permitidas, evidencia
alterada, clasificación de subtests, canales y progreso. La prueba de éxito
solo acredita el recorrido del controlador sobre ese fixture.

El 16 de octubre de 2026, con Python 3.12.3, se ejecutó una vez la regresión
completa mediante el propio adaptador, guardando su informe fuera del proyecto:

```bash
python3 -B project_test_runner.py --project "$PWD" --report /tmp/inspect-json-regresion.json
```

El destino temporal usado en esa ejecución fue un directorio único; la ruta
anterior es un ejemplo para reproducir el comando. Resultado real: **171 métodos
en 63,327 s, OK, código 0** (153 anteriores y 18 nuevos). El informe estructurado
y el cierre textual coinciden: sin aserciones fallidas, errores ni omisiones.
No se repitió la suite por separado. Los agentes fueron simulados; las pruebas
de aceptación/regresión de los fixtures sí se ejecutaron en procesos hijos.

Esto no convierte en verde la [aceptación inicial de la tarea real](referencia-inicial.md),
que conserva sus 14 métodos y 26 fallos por `--format` inexistente. Tampoco es
un intento real de desarrollo ni una revisión del modelo. El inspector original,
el contrato, el evaluador externo y las pruebas anteriores siguen sin cambios.

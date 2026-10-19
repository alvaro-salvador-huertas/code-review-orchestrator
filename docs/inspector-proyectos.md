# Consulta de resúmenes de proyectos

```bash
python3 -B inspect_project.py --run ruta/al/registro
python3 -B inspect_project.py --run ruta/al/registro --format text
python3 -B inspect_project.py --run ruta/al/registro --format json > consulta_proyecto.json
python3 -B export_runs.py consulta_proyecto.json
```

`inspect_project.py` lee exclusivamente el archivo regular `resultado.json` del
directorio indicado. Rechaza un enlace simbólico en lugar de ese archivo. No
recorre el registro ni abre archivos o directorios referenciados en el documento.
No importa candidatos, ejecuta pruebas ni invoca agentes. Solo reutiliza
`case_evidence.read_regular` para la lectura; no utiliza validadores de autorización
de los controladores ni el recorrido de `inspect_run.py`.

Admite estas parejas exactas de campos del resumen general emitido por
[`orchestrate_project.py`](../orchestrate_project.py):

| `tarea` almacenada | `tipo` almacenado |
| --- | --- |
| `inspect-json` | `orquestacion_inspect_json_v1` |
| `export-csv` | `orquestacion_export_csv_v1` |

También admite `orquestacion_configurable_v1` de la
[vía de tareas declarativas](tareas-configurables.md). En ese formato, `tarea`
debe ser un identificador no reservado y `configuracion` debe registrar versión
entera 1, identificador igual a `tarea`, origen no vacío, SHA-256 de 64 caracteres
hexadecimales y commit base de 40. Solo valida su estructura: no abre el origen
ni verifica esos hashes. Los formatos históricos conservan sus parejas exactas.

Un registro del benchmark, un resumen de intento individual, una revisión
aislada o cualquier otro formato produce una consulta incompleta. No se deduce
la tarea a partir del nombre del directorio. Los campos válidos disponibles se
conservan incluso cuando la pareja tipo/tarea no es compatible.

## Alcance de una consulta completada

Solo acredita **lectura y validación estructural del resumen**. No acredita
disponibilidad de la evidencia referenciada, integridad de la ejecución,
coincidencia de candidatos, procedencia, manifiestos, hashes ni informes originales.
Tampoco confirma la verdad de los hallazgos o vuelve a decidir la autorización
del flujo. Los metadatos que no se interpretan se ignoran; no se exige su presencia.

El texto etiqueta como **registrados** los estados, motivos, códigos, presupuestos,
consumos, tiempos, incorporación, procesos por intento, evaluaciones iniciales
y posteriores, dictámenes y transiciones. Muestra ubicaciones registradas sin
abrirlas. Las incidencias de consulta también aparecen en stdout, con código 1.
Los caracteres de control se sustituyen por espacios al presentar texto.
Omitir `--format` equivale a `--format text`.

Las reservas se persisten antes de invocar. Sus contadores no demuestran que un
proceso haya arrancado o finalizado. Una aprobación del modelo no es auditoría
humana ni incorporación realizada: `incorporacion` se muestra independientemente
de la decisión y del indicador `lista_para_revision_humana`.

## Campos necesarios y opcionales

Las reglas proceden de la inicialización y las actualizaciones del resumen en
`orchestrate_project.py`, `repair_project.develop`, `project_flow.evaluate_flow`
y `review_project._run_review`. Son reglas de lectura, no una nueva autoridad
contractual para esos controladores. Se admiten claves adicionales. Todas las
claves duplicadas se rechazan, incluso en metadatos no interpretados.

En la raíz son necesarios:

- `tipo`, `tarea`, `inicio_utc`, `estado` e `incorporacion`: cadenas no vacías.
- `registro`, `motivo` y `error`: cadenas no vacías o `null`.
- `codigo_salida`: entero, sin convertir booleanos ni reales en enteros.
- `max_intentos`, `max_invocaciones` y los tres miembros de `invocaciones`
  (`desarrollador`, `revisor`, `total`): enteros no negativos.
- `lista_para_revision_humana`: booleano.
- `intentos` y `reservas`: listas, que pueden estar vacías.
- `inicial`: objeto de evaluaciones; puede estar vacío al fallar la preparación.
- `limites_segundos`: objeto con nombres no vacíos y números no negativos.

`fin_utc` y `duracion_segundos` son opcionales mientras `estado` sea
`en_preparacion`, `en_desarrollo`, `en_evaluacion` o `en_revision`: el controlador
guarda instantáneas antes de añadirlos. En cualquier otro estado son necesarios.
Si están presentes, deben ser una cadena no vacía y un número no negativo,
respectivamente. No se calcula la duración restando fechas; las fechas se
presentan como cadenas registradas, sin validación de calendario. Estados,
motivos y códigos no se cruzan para volver a autorizar la ejecución.

En cada intento se requieren `numero` (entero positivo), `registro` (cadena no
vacía), `invocaciones` (los dos roles, enteros no negativos), `transiciones`
(lista de objetos con `etapa`, `accion`, `motivo` no vacíos) y `revision`.
`desarrollo` y `evaluaciones` pueden no existir: se añaden al terminar sus ámbitos,
incluso tras un fallo. Ausencia no significa que esas etapas hayan pasado.

Si existe `desarrollo`, requiere `reserva_invocacion` booleana y `agente` con
`invocaciones` entera no negativa y `proceso` objeto o `null`. Las consultas
previas `version` y `ayuda` son opcionales. Un proceso requiere `estado` no vacío
y `codigo_salida` entero o `null`; duración, límite y directorio de trabajo son
opcionales, pero se validan cuando constan. Duración y límite son números no
negativos; el directorio es una cadena que no se abre.

Cada evaluación registrada requiere `proceso` (objeto o `null`) y
`clasificacion`. `no_acreditada` admite ausencia de recuentos porque se guarda
antes de ejecutar. `superadas`, `fallos_asercion` y `error_pruebas` requieren los
seis recuentos enteros no negativos que emite el flujo: `metodos`,
`metodos_con_fallos`, `aserciones_fallidas`, `errores`, `fallos_subtest` y
`subtests_ejecutados`. No se reconstruyen a partir de informes ni se suman.

`revision: null` es válido: no hay resumen de revisión disponible en esa entrada.
No se consulta una revisión externa para completarlo. Si hay objeto, se requieren
`registro` nullable, `decision_controlador`, `codigo_salida`, `revisor` (estado,
código e invocaciones), `dictamen_modelo` nullable, `incorporacion`,
`contraste_semantico` y `error` nullable. Un dictamen requiere decisión `aprobar`
o `solicitar_cambios`, resumen no vacío y lista de hallazgos. Cada hallazgo debe
tener archivo, requisito, explicación y ejemplo no vacíos y línea entera positiva;
no se abre el archivo ni se contrasta el hallazgo o la línea con el candidato.

Cada reserva requiere rol `desarrollador` o `revisor`, intento entero positivo,
fecha no vacía, límite no negativo y estado `reservada_antes_de_invocar`. No se
reconcilian reservas, contadores, presupuestos o transiciones para demostrar
integridad o autorizar pasos posteriores.

Un campo necesario ausente, un contenedor de tipo incorrecto o un valor inválido
genera una incidencia localizada. El lector conserva los demás campos válidos.
No reemplaza ausencias por cero ni inventa estados. JSON inválido, UTF-8 ilegible,
claves duplicadas, constantes `NaN`/`Infinity` o anidamiento que exceda el parser
impiden leer el documento; en ese caso la proyección contiene desconocidos.
Los números JSON se conservan sin conversión a `float`, incluyendo enteros de
5001 dígitos, fracciones precisas y exponentes como `1e400`. Booleanos nunca son
contadores. Una duración entera conserva representación entera.

## Correspondencia de exportación v1 y códigos

La salida JSON contiene exactamente `version_esquema`, `consulta` y `ejecucion`,
con la estructura v1 que acepta [`export_runs.py`](../export_runs.py). Esta es una
**nueva correspondencia para proyectos**; no modifica el
[contrato 003 del inspector del benchmark](../tasks/003-inspect-run-json.md).

| Campo de salida | Fuente |
| --- | --- |
| `version_esquema` | Entero `1`. |
| `consulta.estado`, `codigo_salida`, `incidencias` | Resultado de esta lectura. |
| `ejecucion.caso` | **`tarea` almacenada**, nunca el directorio. |
| `ejecucion.estado`, `codigo_salida` | Campos homónimos del resumen. |
| `ejecucion.presupuestos.max_intentos`, `max_invocaciones` | Campos homónimos de la raíz. |
| `ejecucion.intentos_registrados` | Longitud de la lista `intentos`; `null` si falta o no es lista. |
| `ejecucion.invocaciones.desarrollador`, `revisor`, `total` | Campos homónimos de `invocaciones`, sin recalcular el total. |
| `ejecucion.duracion_segundos` | Campo homónimo del resumen, sin calcularlo. |

La longitud cuenta entradas registradas, incluso si alguna tiene incidencias;
no acredita intentos válidos o finalizados. Valores ausentes o inválidos se
proyectan como `null` en su campo, conservando los hermanos válidos. El JSON no
añade dictámenes ni metadatos ajenos al esquema de exportación.

| Código del inspector | Significado |
| --- | --- |
| 0 | Resumen consultado conforme al alcance anterior, incluso con ejecución fallida, timeout o instantánea en curso. |
| 1 | Resumen ausente, ilegible, no admitido, inválido o incompleto. |
| 2 | Argumentos incorrectos: stdout vacío y diagnóstico en stderr. |

Con argumentos válidos y formato JSON siempre hay **un único objeto y stderr
vacío**, también con código 1. `--help` devuelve ayuda y código 0. Los códigos
del inspector, del exportador y de la ejecución son independientes. Una consulta
incompleta bien formada también puede exportarse con código 0; CSV representa
sus desconocidos mediante celdas vacías.

## Pruebas sintéticas

[`tests/test_inspect_project.py`](../tests/test_inspect_project.py) construye
resúmenes temporales de ambas tareas. Cubre aprobación, corrección, agotamiento,
timeouts, preparación fallida, revisión ausente, instantáneas y registros
incompletos, tipos y formatos inválidos, canales, códigos, precisión numérica y
conservación de entradas. Comprueba que solo se lee `resultado.json`, muestra
rutas inexistentes y utiliza contenido centinela que no se ejecuta.

Dos pruebas pasan por ambas CLI: resumen → JSON → CSV, para una ejecución fallida
consultable y una consulta incompleta exportable. Los hijos usan intérprete
absoluto, `-B`, entorno `evaluation`, cwd explícito y timeout. Son datos
**sintéticos**, sin registros personales ni agentes reales.

```bash
python3 -B -m unittest discover -s tests -p test_inspect_project.py -v
python3 -B -m unittest discover -s tests -v
```

Estos métodos entran en el descubrimiento habitual de CI. Los resultados
históricos de 286 métodos de la base congelada y 355 del hito CSV conservan su
alcance; las nuevas pruebas no actualizan bases, inventarios o autoridades
anteriores. Esta implementación no reanuda ninguna orquestación.

Validación local del 19 de octubre de 2026, con Python 3.12.3:

| Ejecución | Métodos | Fallos | Errores | Omisiones | Duración unittest | Código |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Enfocada final, `test_inspect_project.py` | 28 | 0 | 0 | 0 | 4,031 s | 0 |
| Regresión completa, `discover -s tests -v` | 383 | 0 | 0 | 0 | 186,042 s | 0 |

La regresión se ejecutó una vez al terminar el código y las pruebas. Incluye los
28 métodos nuevos; las pruebas existentes de controladores simulan agentes.
No hubo llamadas a modelos ni nuevos experimentos, y no se atribuye este
resultado local a una ejecución remota de Actions.

Extracto real de la salida textual obtenida por CLI sobre un resumen **sintético**
de preparación fallida, con cero intentos. Tanto la consulta textual como la
JSON devolvieron código 0 y stderr vacío; el código 7 pertenece a la ejecución
registrada:

```text
Ejecución registrada: tarea=export-csv; estado=preparacion_no_autoriza; motivo=preparacion_no_autoriza; codigo_salida=7
Intentos registrados: 0
Cierre registrado: duracion_segundos=12.3456789; incorporacion=no_realizada; lista_para_revision_humana=no
Consulta: completada (código 0)
```

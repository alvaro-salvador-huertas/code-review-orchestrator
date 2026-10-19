# Contraste del primer recorrido real de export-csv

**19 de octubre de 2026. Revisión automática asistida por Codex, no auditoría
humana.** La evidencia conservada concuerda con `lista_para_revision_humana`,
código 0, un intento y dos invocaciones. La revisión estática actual no identifica
un incumplimiento concreto del contrato 004. Se recomienda **preparar la
incorporación** del candidato exacto para su decisión humana; no se incorpora aquí.

SHA-256 de la entrega `export_runs.py`, de 211 líneas:

```text
6449a52e8e3d7109454bc0208eb3df62ffc55116181039112746d17a7225bca7
```

## Alcance y fuentes

Se conservaron la rama `feat/tarea-exportacion-csv`, HEAD
`4cda45e2ccda3f7091f8ab15e55087516c09bec0` y los cambios pendientes. Se buscaron
instrucciones `AGENTS.md` en el repositorio y sus ancestros, sin encontrarlas,
y se leyeron el [contrato 004](../../../tasks/004-export-runs-csv.md), el
[esquema 003](../../../tasks/003-inspect-run-json.md) y la [guía CSV](README.md).
La base y las autoridades congeladas se contrastaron con Git y con sus archivos
actuales, sin actualizar ni modificar esas autoridades.

En este documento, `R` designa el [registro de orquestación][registro]:

```text
runs/20261019T105401Z_export-csv_orchestrate_90b3b8fb88aa42ba8979db8f2037295a
```

`V` designa el [registro de revisión][revision], localizado desde
`R/resultado.json → intentos[0].revision.registro`:

```text
runs/20261019T110205Z_export-csv_review_191c4696c9604355932d6f9dd1929537
```

La entrega está en `R/intentos/1/evidencia/entrega/export_runs.py`; las evaluaciones
posteriores, en `R/intentos/1/evidencia/evaluaciones/`. El revisor tiene un
registro separado, con `materiales/`, `evidencia_validada/` y `revisor/`.
Los enlaces a `runs/` son evidencia local conservada, excluida de Git; no se
publican ni copian estos registros a la documentación.

Este contraste solo leyó archivos, calculó hashes y comparó informes/manifiestos.
Se utilizó también `project_flow.validate_delivery` del controlador actual como
validador de lectura: contrasta Git, AST de identidades y datos conservados,
sin redescubrir suites ni ejecutar sus métodos. El candidato se leyó completo
como texto, sin importarlo. No se ejecutaron candidatos, suites, inventarios
dinámicos, agentes ni orquestación; tampoco se corrigió la entrega ni se hizo
commit, push o merge.

Las simulaciones previas de la guía usan candidatos de comentarios y otra
base. El recorrido `R` sí contiene sesiones reales de desarrollo y revisión.
La revisión actual es un tercer trabajo, exclusivamente de contraste y lectura;
no transforma simulaciones en ejecuciones reales ni reclasifica registros previos.

## Procedencia, identidad y conservación

La base congelada es `4cda45e2ccda3f7091f8ab15e55087516c09bec0`. Se verificaron
los **95 archivos** de `R/referencia/proyecto/` contra los objetos blob y modos
de ese commit, además de sus SHA-256 y el conjunto completo de rutas registrado
en `referencia/procedencia.json`. Ninguno es `export_runs.py`. También coinciden
las copias congeladas de los seis controladores/adaptadores, los dos prompts,
el evaluador y sus dependencias con las autoridades actuales.

| Material conservado bajo `R/referencia/` | SHA-256 verificado |
| --- | --- |
| `contrato.md` (004) | `c8f8eb18815228415e7db1a37d188b0b05446625e59e249ca974b14142f03fe6` |
| `autoridades/tasks/003-inspect-run-json.md` | `f54b7b5af8aa309c7591f6314f35080c64f86db1ff4807069a930b5c8c8011fc` |
| `autoridades/evals/tareas_reales/export_csv/evaluar.py` | `55b47eb7b34d208cc465bd59363f4f82b4e43b32cae56377ff1f40ced3175f1d` |
| `autoridades/project_test_inventory.py` | `b0b4aca8f40db44ec33dcc3749187ff670bcac08be9518fbd014ed79534cfac2` |
| `autoridades/process_environment.py` | `8bd4fc832b472e63f18c97dfd870a9a41fbb1c3f8294a3c0ca83445f64f3a654` |
| `inventario/informe.json` | `6cb1b5beba3ce3cd63734f799c1a3aa134e51a0e85d66dbfe24bee35b29b2c84` |
| `configuracion.json` | `aab72e1d75a7e04bd38af4d13b8e753577d0f8cf957cd4871cb4d20195b5845c` |
| `procedencia.json` | `56b85ba304f11638938c374795fa344f2b9f3b26f826b5479080f7cfaa9fc8a0` |

El evaluador es la revisión que compara duraciones reales por valor decimal
exacto. No es el evaluador histórico de SHA-256
`45881081fafb14403af3b28714954f61bc02f2a9456b045291567a3596b77ebf` usado en la
primera preparación documentada. Sus 17 fallos iniciales y su hash histórico
se conservan en la guía; no se sustituyen por la evaluación inicial de `R`.

La configuración congelada selecciona solo aceptación CSV y regresión, dos
intentos como máximo, cuatro invocaciones, las políticas `evaluation` y `codex`,
sin incorporación automática ni reanudación. Su estado inicial es
`{"tipo":"ausente","sha256":null,"modo":null}` y su modo de creación es 420
decimal, es decir, **0644**. Los valores coinciden con el controlador congelado
y actual; los límites efectivos se detallan más abajo.

La ausencia inicial se corrobora en Git, la base conservada, procedencia,
ambos inventarios `inicial/*/proyecto_evaluado.json`, los hashes nulos de esas
evaluaciones y `entrega/partida.json`. No existe un `partida.py` vacío fabricado;
`candidato.diff` y `anterior.diff` describen la misma alta desde `/dev/null`.
Los eventos del desarrollador también registran `export_runs.py: ausente`
antes de su creación.

`entrega/cambios.json` contiene **una sola ruta**, `export_runs.py`, ausente antes
y regular 0644 después, con el SHA-256 indicado. El árbol de
`entrega/workspace_despues.json` coincide exactamente con base más ese archivo;
ambas evaluaciones posteriores registran esa misma composición y hash.

Las cuatro copias actualmente legibles son regulares y tienen idéntico contenido:

- `R/intentos/1/evidencia/entrega/export_runs.py`.
- `V/materiales/export_runs.py`.
- `V/evidencia_validada/export_runs.py`.
- `V/evidencia_validada/evidencia/entrega/export_runs.py`.

**Sus modos actuales son 0664, no 0644.** El controlador archiva los bytes con
`write_bytes`, sin trasladar el modo del workspace. Los manifiestos sellados
conservan ese 0664 de archivo archivado; el 0644 del candidato desarrollado y
evaluado consta en los inventarios de las copias temporales y en el comando
`chmod` registrado. Estas son dos observaciones distintas. Una futura
incorporación debe crear el archivo con **0644**, sin heredar el 0664 del archivo
de evidencia. No se ha cambiado ningún permiso en esta revisión.

Se verificaron los once sellos de `R/resultado.json.etapas_cerradas`, la referencia
completa, los tres sellos de la entrega y los orígenes, materiales, selección y
evidencia completa del revisor. Las copias de todos los archivos de la entrega
en `V/evidencia_validada/evidencia/` coinciden con sus fuentes. Los hashes de
informes y listas de identidades del resumen seleccionado corresponden a las
evaluaciones de ese candidato, sin reutilizar las de otro intento.

Antes de editar esta documentación, el árbol original incluido en el manifiesto
global coincidía íntegramente con `original_sha256`, incluidos sus cambios
pendientes. `export_runs.py` sigue ausente en la raíz. Ese manifiesto excluye
`.git`, `runs`, cachés y configuración privada, entre otras rutas: no acredita
sus contenidos. Los registros se comprobaron por sus propios sellos y se
inventarió todo `runs/` antes y después de esta revisión, sin diferencias.
Las únicas diferencias introducidas aquí en el árbol inventariado son esta
documentación nueva y la actualización de la guía.

Las copias `/tmp/orchestrate-project-9we5tr9n/{inicial,desarrollo-1,evaluacion-1}`
y `/tmp/review-project-553c3lln/workspace` ya no existen. Su estado durante el
recorrido solo consta en inventarios, eventos y comprobaciones de integridad
del controlador; no se inspeccionó ahora un workspace desaparecido. La referencia
Git sí sigue disponible y su snapshot de inventario, incluidos modos y mtime,
continúa coincidiendo. Los hashes verifican consistencia de lo conservado;
no constituyen una firma externa ni prueban ausencia de alteraciones transitorias.

## Evaluaciones acreditadas del recorrido real

Para cada una de las cuatro evaluaciones se contrastaron `pruebas.json`,
`evaluacion.json`, `resultado.json`, `proyecto_evaluado.json`, stdout y stderr.
Las listas completas de métodos iniciados y terminados coinciden con las
identidades congeladas de `referencia/procedencia.json`, sin duplicados,
identidades faltantes ni adicionales; los cuatro informes son completos,
versión 1 y una sesión. Sus códigos concuerdan con los cierres de unittest.

| Etapa | Métodos | Fallos de aserción | Errores | Omisiones | Subtests | Código | Cierre textual conservado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Aceptación inicial, archivo ausente | 17 | 17 | 0 | 0 | 0 | 1 | `Ran 17 tests in 0.007s`; `FAILED (failures=17)` |
| Regresión inicial | 286 | 0 | 0 | 0 | 295 | 0 | `Ran 286 tests in 139.455s`; `OK` |
| Aceptación posterior, candidato exacto | 17 | 0 | 0 | 0 | 615 | 0 | `Ran 17 tests in 6.943s`; `OK` |
| Regresión posterior, candidato exacto | 286 | 0 | 0 | 0 | 295 | 0 | `Ran 286 tests in 139.536s`; `OK` |

No hay fallos esperados ni éxitos inesperados. Todos los subtests registrados
tras la preparación se clasifican como superados; no se suman a los métodos
ni representan un contador de aserciones correctas o de procesos CLI.
Stdout de los cuatro runners está vacío; stderr contiene las salidas habituales
de unittest. Esto es distinto del contrato de canales de la CLI candidata,
que el evaluador comprueba dentro de sus consultas.

Los 17 fallos iniciales terminan con la precondición:
`Funcionalidad pendiente: falta export_runs.py como archivo regular; CLI no invocada`.
Se producen en `setUp`, antes de lanzar el exportador: **cero consultas de la CLI
candidata**, no 17 consultas fallidas. La regresión inicial superada y ese rechazo
de disponibilidad autorizan el primer desarrollo.

El inventario congelado está completado, sin errores, código hijo 0 y 286
identidades únicas ordenadas. Su informe y stdout son iguales y sus hashes de
árbol anterior/posterior coinciden:
`dc330d1a8ca08417cfe942d3b3f7e12400b2e71cdb75717f613b70b201c33b0e`.
La fuente fue la base Git conservada, antes del agente, con `/usr/bin/python3.12`,
`-B`, cwd explícito, entorno `evaluation` y límite de 30 s. El descubrimiento
importó módulos: no fue análisis estático ni aislamiento de seguridad.

Se volvió a comparar por lectura el conjunto congelado con `static_test_ids`
de esa misma base: **286 frente a 252**, 34 identidades solo en descubrimiento
y ninguna solo en el estático. Todas las diferencias están en `test_inspect_json`:
21 de `TestInspectJsonAcceptance`, 7 de `TestInspectJsonAnidamiento` y 6 de
`TestInspectJsonHallazgos`. La causa sigue siendo la herencia importada; el
estático también omite los siete métodos propios de la primera subclase.
No se redescubrieron ni ejecutaron pruebas en este contraste.

Las **321 pruebas** documentadas en la guía son la regresión anterior del árbol
de trabajo con 14 pruebas nuevas del inventario y 21 del flujo CSV. No son las
identidades congeladas de este recorrido ni una evaluación adicional del
candidato. Tampoco el inventario de 286, por sí solo, significa 286 pruebas
superadas: aquí lo acreditan los informes de ejecución independientes.

## Reservas, tiempos y dictamen

El recorrido empieza a `2026-10-19T10:54:01.239859Z` y termina a
`2026-10-19T11:03:08.132481Z`: duración registrada **546,892638 s**. Utiliza un
intento de dos y dos invocaciones de cuatro: desarrollador 1 y revisor 1.
Las reservas guardadas coinciden con el resumen y preceden a los procesos:

| Rol | Reserva UTC | Inicio efectivo UTC | Fin efectivo UTC |
| --- | --- | --- | --- |
| Desarrollador | 10:56:21.867084 | 10:56:21.868766 | 10:59:38.269510 |
| Revisor | 11:02:05.489477 | 11:02:05.491338 | 11:03:08.011745 |

Ambas son del 19 de octubre de 2026, con estado `reservada_antes_de_invocar` y
límite 300 s. Los procesos terminan con código 0 y sin error. El resumen del
intento y el global concuerdan; no hay segundo intento ni transición de corrección.
Las transiciones conservadas son `evaluacion → revisar / superadas` y
`revision → aprobar / revision_aprobada`.

| Proceso o etapa | Duración registrada (s) | Límite efectivo (s) |
| --- | ---: | ---: |
| Inventario externo | 0,215084 | 30 |
| Aceptación inicial | 0,064885 | 60 |
| Regresión inicial | 139,638803 | 300 |
| Versión / ayuda del desarrollador | 0,064628 / 0,065239 | 10 cada una |
| Desarrollador | 196,400770 | 300 |
| Aceptación posterior | 7,035517 | 60 |
| Regresión posterior | 139,720820 | 300 |
| Versión / ayuda del revisor | 0,032280 / 0,064281 | 10 cada una |
| Revisor | 62,520442 | 300 |
| Etapa completa de revisión, incluida preparación | 62,787401 | No consta un límite global adicional |
| Orquestación completa | 546,892638 | No consta un límite global adicional |

Las duraciones de proceso incluyen el arranque y difieren de las del cierre
de unittest; no se han confundido ni recalculado a partir de este contraste.
El evaluador congelado fija **10 s por consulta CLI candidata**; no consta un
registro individual de duración por consulta. Las consultas de versión/ayuda
del controlador no son invocaciones de modelo. Ambas versiones registradas
son `codex-cli 0.162.1`; el inventario identifica Python 3.12.3.

La respuesta final del desarrollador afirma que creó el archivo regular 0644,
que superó 165 comprobaciones locales y que dejaba aceptación y regresión al
controlador. Los eventos conservan el alta del único archivo, su `chmod` y el
script local, que terminó con código 0 y el mensaje de 165 comprobaciones.
Ese script empleó importación del candidato, entradas en memoria y algunas
consultas CLI, durante la sesión ya concluida. No son 165 métodos de aceptación
independiente ni sustituyen los informes de la tabla. No se repitió ese script.

La [respuesta original del revisor][respuesta] contiene un solo objeto JSON y
coincide semánticamente con el [dictamen validado][dictamen] y con
`resultado.json.dictamen_modelo`:

> Decisión: `aprobar`. Hallazgos: `[]`. La revisión estática no identifica
> incumplimientos concretos; considera cubiertos esquema, valores, orden,
> formato CSV, atomicidad y canales/códigos.

Es una síntesis del dictamen. Su respuesta original declara que no ejecutó
código ni modificó archivos; los once comandos completados de sus eventos
son lecturas/listados de materiales. La invocación usa `--sandbox read-only`,
búsqueda web deshabilitada y `features.multi_agent=false`. El desarrollador
usa `workspace-write`, red deshabilitada y tampoco multiagente. Se contrastaron
los comandos guardados, sin lanzarlos de nuevo.

Los eventos `turn.completed` declaran, respectivamente, 129497/8202 tokens de
entrada/salida para desarrollo y 122243/1713 para revisión; entradas cacheadas
107648 y 83840. Son contadores de esas sesiones, no invocaciones adicionales.
No consta coste monetario ni un presupuesto de tokens efectivo en la configuración
del flujo. No se infiere un modelo concreto a partir de la versión de la CLI.

La decisión del controlador es `dictamen_aprobar_validado`, código 0. El global
termina con `motivo: revision_aprobada`, `lista_para_revision_humana: true` e
`incorporacion: no_realizada`. El campo histórico `contraste_semantico: pendiente`
permanece intacto: esta revisión posterior se añade como documento separado,
sin convertirlo en una certificación humana ni reescribir el registro.

## Revisión estática completa del candidato

Se revisaron las líneas 1–211 del [candidato archivado][candidato], con el
contrato 004 como autoridad y el esquema 003 como contexto. La tabla recoge
**deducciones de lectura**, no reproducciones ejecutadas ahora. Las entradas
son modificaciones concretas de un documento válido completo como el ejemplo
del contrato; los demás campos se mantienen válidos salvo indicación expresa.

| Requisito y líneas | Entrada o combinación examinada | Comportamiento deducido |
| --- | --- | --- |
| Claves exactas y cinco objetos; 63–74, 93–100, 114–133 | Quitar `invocaciones.revisor`, añadir `presupuestos.extra`, o sustituir `presupuestos` por `null`/`[]`. | Rechazo localizado: se comprueban contenedores, ausencias y adicionales incluso en campos no exportados. |
| Tipos y coherencia de consulta; 77–111 | `version_esquema: true` o `1.0`; consulta incompleta con código 0 o incidencias vacías; incidencias `["  "]`. | Rechazo. La versión exige token entero 1; estado, código e incidencias se relacionan exactamente. |
| Duplicados y JSON estricto; 46–60, 142–149 | Repetir `total` dentro de `invocaciones`; concatenar dos objetos; JSON truncado, raíz lista, bytes UTF-8 inválidos o duración `NaN`/`Infinity`. | Los hooks y el parser rechazan estas entradas; los errores de validación/lectura llegan a 202–204, sin CSV. |
| Booleanos, enteros y reales; 27–47, 77–86, 122–139 | Contador `true`, `1.0`, `1e0` o `"1"`; duración `true` frente a duración `1e0`. | Booleanos/cadenas nunca son `JsonNumber`; los tokens con fracción/exponente no son enteros. La duración real sí es válida. |
| Signo, null y cero; 39–43, 81–86, 119–139, 167 | Código de ejecución `-3`, contador `-1`, duración `-1e-400`, `null` frente a `0`. | Código negativo permitido; contador/duración negativos rechazados por la mantisa, sin subdesbordamiento. `None` se emite vacío; cero se conserva como número. |
| Precisión y magnitudes; 27–47, 135–147, 167 | Entero de 5001 nueves; duración `1e400` o `1.23456789012345678901234567890123456789`. | El parser guarda el token sin convertir a `int`, `float` ni `Decimal`; CSV conserva exactamente esos dígitos y exponente. No introduce límite artificial ni redondeo. |
| Valores declarados sin inferencias; 119–159 | Desarrollador 1, revisor 0, total 17; consulta incompleta con ejecución fallida; códigos de ejecución y consulta distintos. | Valida cada valor sin exigir sumas o relaciones ajenas al contrato; proyecta el total declarado y exporta con código 0. |
| Cabecera y proyección; 9–14, 152–159 | Documento completo del ejemplo del contrato. | Once columnas en el orden exigido, con cada fuente correcta y sin columnas adicionales. |
| Cadenas y CSV UTF-8/LF; 89–90, 119–121, 163–168 | `caso` igual a `  España, "A"\rB\nC\r\n  `, con escapes JSON representando CR/LF reales. | `strip` solo comprueba contenido, no reemplaza la cadena. `QUOTE_ALL` protege comas, comillas y CR aislados; duplica comillas, conserva CR/LF interiores y termina cada registro con LF. Codifica UTF-8 sin BOM. |
| Orden, repetidos y origen literal; 171–184, 198–201, 156 | Argumentos `./b.json ./a.json ./b.json`, o `-- -entrada`. | No ordena ni deduplica. `open` resuelve relativos desde cwd; la celda conserva el argumento, incluido `./` y duplicados. `--` deja de interpretar opciones. |
| Validación anterior a cabecera; 197–206 | Primer archivo válido y segundo inexistente, directorio o documento inválido. | Acumula y codifica filas en memoria; la única escritura CSV se hace tras validar todos. Ante error devuelve 1, stdout vacío y diagnóstico con archivo y causa. Preparar la cabecera en memoria no la emite. |
| Canales, códigos y ayuda; 171–211 | Sin argumentos, `--he`, `--help=1`, `--opcion`; por separado `-h` y `--help`; entradas válidas. | Argumentos inválidos: 2 y stderr; ayuda: 0 y stdout sin CSV; exportación: 0 y CSV sin mensajes en stderr. Errores de entrada previstos se capturan, sin traceback. |
| Solo lectura y biblioteca estándar; 3–6, 142–149, 187–211 | Una cadena de `caso` con aspecto de código Python. | Se trata como dato: no hay `eval`, `exec`, importación del inspector, procesos, red, acceso a configuración personal ni escritura en entradas/proyecto. Solo lee rutas recibidas y escribe canales. |

No se han identificado hallazgos que requieran corregir el candidato bajo los
requisitos fijados. Esta conclusión no demuestra corrección universal ni toma
la aprobación del modelo como sustituto de la lectura. La representación
opcional con comillas en todos los campos y la conservación del lexema numérico
están admitidas por el contrato; no se imponen formatos canónicos adicionales.

## Conclusión y cierre

El resultado comunicado por la terminal está respaldado por informes completos,
identidades congeladas y artefactos coherentes del mismo candidato. La aprobación
del revisor corresponde a esa entrega, y el contraste estático actual no aporta
un defecto concreto que obligue a corregirla antes de preparar su incorporación.
La precisión sobre permisos es necesaria: **0644 consta en los workspaces
evaluados; las copias archivadas verificables ahora tienen 0664**.

Recomendación: preparar una incorporación explícita de los bytes del SHA-256
indicado, creando `export_runs.py` regular 0644 y dejando la decisión humana
separada de esta revisión automática. La regresión registrada cubre la base
congelada de 286 métodos; la validación del árbol que finalmente vaya a
incorporarse deberá identificarse con ese alcance, sin atribuirle automáticamente
las 321 pruebas históricas de preparación. Nada de ello se ha ejecutado aquí.

Se revisó el diff documental y sus espacios, y se comprobaron los enlaces locales
y anclas de los dos documentos modificados. Se conservaron todos los demás
cambios pendientes, las autoridades, el inspector, los controladores, el benchmark,
la configuración y los registros. No se ejecutaron nuevas pruebas por este
cambio exclusivamente documental. Las comprobaciones de lectura y sus resultados
se guardaron también temporalmente en `/tmp/contraste_csv_resultado.json`;
no son una nueva ejecución del flujo ni una autoridad histórica.

[registro]: ../../../runs/20261019T105401Z_export-csv_orchestrate_90b3b8fb88aa42ba8979db8f2037295a/resultado.json
[revision]: ../../../runs/20261019T110205Z_export-csv_review_191c4696c9604355932d6f9dd1929537/resultado.json
[candidato]: ../../../runs/20261019T105401Z_export-csv_orchestrate_90b3b8fb88aa42ba8979db8f2037295a/intentos/1/evidencia/entrega/export_runs.py
[respuesta]: ../../../runs/20261019T110205Z_export-csv_review_191c4696c9604355932d6f9dd1929537/revisor/respuesta_original.txt
[dictamen]: ../../../runs/20261019T110205Z_export-csv_review_191c4696c9604355932d6f9dd1929537/dictamen_validado.json

# Experimento controlado del revisor — 16 de octubre de 2026

El contraste de la evidencia respalda **dos defectos detectados y dos
aprobaciones justificadas**, con una revisión real por candidato. No se han
encontrado discrepancias entre los dictámenes, sus ejemplos y los contratos
conservados. Las cuatro sesiones emitieron un mensaje de progreso antes del
JSON final. La primera redacción del informe lo calificó como desviación al
extender la exigencia de exclusividad JSON a todos los mensajes de la sesión;
el entregable final sí cumplió el formato. El apartado de mensajes distingue
la observación histórica de esa interpretación.

Este documento es una **revisión automática realizada por Codex**, no una
auditoría humana. El contraste se realizó mediante lectura de archivos,
comparación de bytes, recálculo de SHA-256 y análisis de JSON e identificadores
de pruebas. No se ejecutaron candidatos, pruebas ni Codex, ni se volvió a
preparar o lanzar el experimento. Los registros y las expectativas previas
permanecen intactos; este informe es posterior al [protocolo](README.md) y a
las [expectativas](expectativas.md), cuya tabla pendiente conserva su carácter
previo al experimento.

## Procedencia y alcance

Identificador de evidencia local:
`runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec`.
Los enlaces a esa carpeta requieren conservarla localmente; está excluida de
Git. Este informe resume la evidencia sin publicar registros completos ni
configuración personal.

La [preparación][preparacion] declara la procedencia
`candidatos_preparados_para_evaluacion`: son cuatro implementaciones preparadas
para este diseño, **no reparaciones producidas por un desarrollador**. El
estado Git conservado corresponde a la rama `eval/revisor-casos-controlados`,
revisión `7a3d99e4bad4f21ca197c538d7c0f08a53ef1eeb`, con cambios relevantes
pendientes: utilidad de procesos modificada y candidatos, instrucciones y
lanzador sin versionar. Por tanto, la revisión Git por sí sola no reconstruye
el experimento; las 16 fuentes congeladas conservan esos contenidos.

La preparación duró **0,293116 s**, con código 0, e incluyó cuatro evaluaciones
con las pruebas originales en procesos y directorios temporales separados.
El [lanzamiento][lanzamiento] transcurrió entre **12:58:29,501951 y
13:00:06,884885 UTC**, durante **97,382939 s**, y terminó `completado`, código 0.
La reserva conserva `reanudacion: false`. Hay cuatro procesos `codex exec`,
uno por candidato y en orden 01–04, y cuatro identificadores de sesión
distintos en los eventos. No constan reintentos, desarrolladores ni reparaciones
en este experimento. Los comandos internos de lectura no son nuevas invocaciones.

## Resultados acreditados

Todos los procesos de pruebas originales y de revisión terminaron con código
0. Los cuatro candidatos figuran como `completada`, con respuesta final válida
y sin errores técnicos registrados. El código 0 del lanzador significa que
completó la evidencia; no convierte las solicitudes de cambios en aprobaciones.

| Candidato / caso | Pruebas originales | Dictamen observado | Hallazgos respaldados | Invocaciones | `codex exec` (s) | Revisión completa (s) |
| --- | --- | --- | --- | --- | --- | --- |
| [candidato_01][revision01] / 01 | 4/4 | `aprobar` | Ninguno; aprobación justificada. | 1 | 30,666016 | 30,907085 |
| [candidato_02][revision02] / 01 | 4/4 | `solicitar_cambios` | Uno, línea 6: comparación de nombres. | 1 | 28,094288 | 28,234172 |
| [candidato_03][revision03] / 02 v2 | 16/16 | `aprobar` | Ninguno; aprobación justificada. | 1 | 17,977620 | 18,141593 |
| [candidato_04][revision04] / 02 v2 | 16/16 | `solicitar_cambios` | Uno, línea 2: prioridad del timeout. | 1 | 19,797335 | 19,940973 |

Las duraciones proceden de los JSON conservados, redondeadas a seis decimales.
La revisión completa incluye consultas de CLI y recogida de evidencia; la
columna `codex exec` mide solo ese proceso. Los procesos de pruebas duraron,
en orden, **0,064323; 0,064286; 0,064225 y 0,064950 s**. Los cuatro informes de
`unittest` muestran `0.000s` para la ejecución interna de sus pruebas; esa
precisión no equivale a duración nula del proceso. Se contrastaron los 4, 4,
16 y 16 identificadores con los archivos originales: todos aparecen como
`ok`, con cierre `OK`, stdout vacío y sin omisiones.

Esto es distinto de la validación previa del lanzador: **148 pruebas en
48,607 s, código 0, Python 3.12.3 y Codex simulado**, documentadas en el
[README de preparación](README.md#validación-local-del-lanzador). Aquella suite
incluyó 16 pruebas nuevas y 132 anteriores; no evaluó al modelo. Aquí se
contrastan cuatro revisiones reales posteriores, sin repetir esa suite.

## Contraste de los dictámenes con el código

Se utilizaron los candidatos y contratos congelados, idénticos a sus copias
entregadas y a los archivos actuales enlazados a continuación. Las deducciones
siguientes son estáticas: no se ejecutaron sus ejemplos durante este contraste.

**[candidato_01](candidatos/candidato_01.py), aprobación justificada.** El
[contrato 01](../../tasks/001-sum-by-subject.md) exige acumular por nombre exacto,
distinguir mayúsculas, devolver `{}` para una entrada vacía y conservar la
entrada sin E/S. La función crea un diccionario nuevo y, en la línea 5, suma
los minutos sobre la clave original, sin normalizarla. La entrada vacía no
entra en el bucle; la lista y sus diccionarios solo se leen. No hay operaciones
de E/S. El dictamen de aprobación tiene hallazgos vacíos y es coherente con
estas propiedades para las entradas admitidas por el contrato.

**[candidato_02](candidatos/candidato_02.py), hallazgo respaldado.** La línea 6
es `clave = nombres.setdefault(asignatura.lower(), asignatura)`. `lower()`
hace coincidir los nombres `Python` y `python`; `setdefault()` conserva como
clave de salida el nombre de la primera aparición. El ejemplo del revisor
usa dos sesiones válidas: Python con 20 minutos y python con 15. El contrato
exige `{"Python": 20, "python": 15}`; las líneas 6–7 permiten deducir
`{"Python": 35}`. La línea, explicación y ejemplo identifican el defecto real,
no una preferencia de estilo ni una exigencia adicional. La suma, entrada
vacía, conservación de la entrada y ausencia de E/S se mantienen. Las cuatro
pruebas originales no incluyen esa pareja de nombres.

**[candidato_03](candidatos/candidato_03.py), aprobación justificada.** El
[contrato 02, versión 2](../../tasks/002-classify-run.md), da prioridad al
timeout sobre cualquier código; después resuelve el fallo de ejecución y la
respuesta vacía o formada solo por espacios según `str.isspace()`. Las líneas
2–8 siguen ese orden. El cortocircuito distingue `None` y cadena vacía antes
de llamar a `isspace()`; el resto del texto devuelve `completada`. No hay E/S
ni otros efectos secundarios. El dictamen no añade requisitos ajenos al
contrato y conserva hallazgos vacíos.

**[candidato_04](candidatos/candidato_04.py), hallazgo respaldado.** La línea 2
comprueba `codigo_salida is None` y la línea 3 devuelve `fallo_ejecucion`, antes
de comprobar el timeout en la línea 4. El ejemplo del revisor, código `None`,
respuesta `None` y `tiempo_agotado=True`, está admitido. El contrato exige
`tiempo_agotado`, pero la primera rama devuelve `fallo_ejecucion`. Tanto la
línea señalada como la explicación y el ejemplo son correctos. El resto de
las ramas conserva el comportamiento contractual; las dieciséis pruebas
originales no combinan código `None` con timeout verdadero.

En estos cuatro candidatos se observan **dos hallazgos respaldados, cero
aprobaciones de código defectuoso y cero solicitudes injustificadas de
cambios**. No se deduce este resultado solo de comparar decisiones esperadas
y observadas: se contrastaron también ramas, líneas y ejemplos. Los seis
ejemplos fallidos de las comprobaciones adicionales previas son manifestaciones
de estos **dos defectos**, no seis defectos independientes ni seis detecciones.

## Integridad declarada y comprobada ahora

Los registros declaran `evidencia_completa_verificada: true`, integridad
positiva de materiales, instrucciones y workspaces, y pruebas e implementación
intactas. En esta revisión se hicieron además las siguientes comprobaciones
independientes sobre los archivos conservados:

- Se recalcularon los SHA-256 de los **38 archivos de preparación**: coinciden
  exactamente con el mapa de `preparacion.json`, sin archivos añadidos o ausentes.
  El hash del manifiesto coincide con el de la reserva y el resumen:
  `a721d6f1ff461fe90a492a9b1e41c6f8b80b630a6d7ebda44f4f9e9f3661606d`.
- Se recalcularon los **88 archivos de revisión**, 22 por candidato: coinciden
  exactamente con `revisiones_sha256`. En el contraste original, las 16 fuentes
  congeladas coincidían también con los archivos de trabajo. Esa comprobación
  precede a la mejora posterior de progreso y no afirma igualdad con código
  modificado después; las fuentes congeladas siguen intactas.
- Cada conjunto de materiales contiene exactamente los siete archivos previstos:
  candidato, contrato, pruebas originales, JSON de su evaluación, stdout,
  stderr y esquema de respuesta. Se compararon sus bytes con las fuentes y
  evaluaciones congeladas, incluidas las copias evaluadas como `solution.py`.
  No contienen expectativas, comprobaciones adicionales ni otros candidatos.
- Las instrucciones efectivas de `revisor/entrada.txt` coinciden con las
  congeladas y son idénticas dentro de cada pareja. SHA-256 del caso 01:
  `c97a62913e6d8c96dc8e41445c08122291c5dfa1a1f3415f0c71618464ae302a`;
  del caso 02: `28362d3ef02fa5274b2f09d432d5de78a4b880f365993662029790cd85afc15a`.
- Las respuestas originales, los dictámenes validados, los resultados por
  candidato y el resumen global coinciden semánticamente. Se revisaron claves,
  decisiones, hallazgos vacíos o presentes y límites de línea. Los mensajes
  finales de los eventos contienen los mismos dictámenes. Las salidas de los
  comandos de lectura corresponden a los materiales conservados.

Los mapas `workspace_despues.sha256.json` coinciden con los materiales
archivados. **Los workspaces temporales ya no existen**: no se afirma haber
inspeccionado ahora sus contenidos originales; su estado al terminar procede
de la evidencia registrada. La concordancia de hashes demuestra consistencia
con esos registros, no autenticidad mediante una firma independiente ni
ausencia de accesos no registrados. El informe no presenta esta separación
de contexto como un aislamiento de seguridad garantizado.

## Acciones observables y formato del entregable

Los eventos contienen una sesión y un turno completado por candidato, sin
eventos de error. Se distinguen los comandos iniciados de sus correspondientes
eventos de finalización para no contarlos dos veces:

| Candidato | Comandos internos completados | Acciones registradas |
| --- | --- | --- |
| 01 | 3 | Dos lecturas con `cat`; un comando de ubicación y listado con `pwd` y `rg --files`, que también buscó `AGENTS.md` sin encontrarlo. |
| 02 | 9 | `pwd`, listado con `rg --files` y siete lecturas numeradas con `nl -ba`, una por material. |
| 03 | 2 | Lectura con `cat` de los siete materiales, repartida en dos comandos. |
| 04 | 2 | Lectura con `cat` de los siete materiales, repartida en dos comandos. |

Los 16 comandos internos terminaron con código 0. No aparecen comandos que
ejecuten candidatos, pruebas o ejemplos, modifiquen archivos, usen Git,
instalen dependencias, accedan a la web, lean explícitamente fuera del
workspace o deleguen en subagentes. Los listados observados muestran únicamente
los materiales permitidos. Los stderr de los cuatro procesos de revisión están
vacíos. Estas conclusiones se limitan a las acciones observables en los eventos.

**Observación conservada:** cada `eventos.jsonl` contiene un `agent_message`
inicial de progreso en texto libre; por ejemplo, en el candidato 01: «Revisaré
el contrato, el código y los informes mediante lectura estática». Los mensajes
intermedios del revisor siguen en los eventos y no se han eliminado ni corregido.

**Entregable consumido por el controlador:** la CLI captura el último mensaje
con `--output-last-message`. Ese contenido se conserva como
`respuesta_original.txt` y es el que valida el lanzador, no la concatenación
de mensajes intermedios y eventos de herramientas. En los cuatro casos es
exclusivamente JSON válido y coincide con el dictamen guardado.

**Matiz de interpretación posterior:** la instrucción decía «Devuelve
exclusivamente un objeto JSON, sin Markdown ni texto adicional». La primera
redacción de este informe interpretó esa exclusividad sobre todos los mensajes
del revisor y calificó el texto intermedio como desviación. Con esa lectura
amplia, la observación se mantiene; referida al entregable final, el formato sí
se cumplió. El código congelado ya validaba únicamente ese entregable: este
matiz describe el criterio técnico aplicado entonces, sin cambiarlo
retrospectivamente ni atribuir un fallo técnico que no ocurrió. Se conservan
los cuatro códigos 0 y sus dictámenes. Los nuevos avisos de progreso de la CLI
del controlador son una mejora posterior y distinta de aquellos mensajes del
revisor; no alteran esta evidencia ni las instrucciones del experimento.

## Configuración y límites de la conclusión

Las cuatro consultas de versión acreditan **`codex-cli 0.162.1`**. Los argumentos
registrados son iguales salvo las rutas temporales: `exec`, sandbox `read-only`,
`approval_policy="never"`, `web_search="disabled"`, `features.multi_agent=false`,
`--skip-git-repo-check`, `--ephemeral`, eventos JSON, esquema de salida y captura
del último mensaje. Los límites registrados son 180 s por revisión, 10 s por
consulta de CLI y 30 s por evaluación; ninguna de estas etapas agotó su límite.

| Parámetro | Solicitado por el lanzador | Configuración efectiva acreditada |
| --- | --- | --- |
| Modelo | No fijado. | **No consta.** |
| Proveedor | No fijado. | **No consta.** |
| Esfuerzo de razonamiento | No fijado. | **No consta.** |
| Lectura, web y subagentes | Opciones anteriores. | Eventos compatibles con lectura local sin web ni delegación; no acreditan por sí solos toda la configuración heredada. |

Los eventos no identifican modelo, proveedor ni esfuerzo efectivos. La versión
de CLI y los contadores de tokens no permiten deducirlos. No se han leído ni
copiado credenciales o configuración personal para completar esos datos; los
argumentos iguales no demuestran igualdad de todas las opciones heredadas.

Son cuatro candidatos pequeños, una revisión por candidato y dos defectos
preparados deliberadamente. Los prompts ya piden examinar la comparación
exacta y las prioridades; no es una evaluación sin pistas contractuales.
No se estima fiabilidad general, tasa representativa de acierto ni ausencia
universal de falsos positivos. El mismo sistema Codex realiza este contraste
automático posterior; no sustituye una auditoría humana independiente.

No hubo desarrollador, reparación ni segundo intento en este experimento.
Las solicitudes de cambios condujeron al siguiente candidato independiente,
no a corregir el anterior. Por tanto, estos resultados **no demuestran
corrección automática en un segundo intento**. Los campos históricos
`validez_hallazgos: pendiente_de_contraste` se mantienen intactos: la valoración
posterior queda únicamente en este informe.

[preparacion]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/preparacion.json
[lanzamiento]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/lanzamiento/resultado.json
[revision01]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/lanzamiento/candidato_01
[revision02]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/lanzamiento/candidato_02
[revision03]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/lanzamiento/candidato_03
[revision04]: ../../runs/20261016T125659090384Z_revisor_dfdf9ff844ef4eb58d80679e40df3dec/lanzamiento/candidato_04

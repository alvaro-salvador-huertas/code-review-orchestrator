# Evaluación controlada del revisor

El hito de preparación creó cuatro candidatos independientes y un lanzador.
Su validación local usó una CLI simulada; **no evaluó al modelo**.
Los archivos de `candidatos/` fueron preparados expresamente para este diseño,
no obtenidos de una reparación realizada por un agente. La base es `main`,
revisión `7a3d99e`, y la preparación se deja en `eval/revisor-casos-controlados`.
El lanzador conserva esa procedencia y no crea registros de reparación.

Los [resultados reales del 16 de octubre de 2026](resultados-2026-10-16.md)
se documentan por separado, mediante contraste automático de la evidencia por
Codex. El protocolo y los comandos siguientes describen el diseño previo;
el experimento identificado en ese informe ya se ejecutó y no debe repetirse.
Las expectativas anteriores conservan su estado previo al experimento.

## Reproducción local

Desde la raíz del proyecto, con Python y su biblioteca estándar:

```bash
python3 -B -m unittest discover -s tests -p 'test_reviewer_candidates.py' -v
```

Para la regresión completa, que incluye estas comprobaciones:

```bash
python3 -B -m unittest discover -s tests -v
```

Cada candidato se copia como `solution.py` a un directorio temporal nuevo.
Sus pruebas originales se copian sin cambios y se ejecutan en un proceso Python
separado; se contrastan el código de salida, los identificadores y el total del
informe con `case_evidence`. Las comprobaciones adicionales también usan procesos
hijos, verifican los resultados exactos y comprueban que las copias no cambian.
El proceso principal nunca importa candidatos. Estas comprobaciones no usan
Codex ni registros personales de `runs/`.

Las pruebas del lanzador se encuentran en `tests/test_evaluate_reviewer.py`.
Crean repositorios Git temporales, ejecutan las pruebas originales en procesos
hijos y simulan la CLI de Codex. La regresión completa incluye ambos bloques.

Las [expectativas](expectativas.md) y
[comprobaciones adicionales](../../tests/test_reviewer_candidates.py) pertenecen
solo al evaluador. Que estas comprobaciones terminen con `OK` significa que los
candidatos tienen el comportamiento previsto, incluidos los incumplimientos
deliberados; no significa que todos cumplan el contrato. Los dos ejemplos
fallidos del caso 01 y los cuatro del caso 02 son manifestaciones de **dos
defectos**, no seis defectos independientes.

## Protocolo previo al futuro experimento

1. Congelar los cuatro archivos, los contratos, las pruebas originales y el
   prompt efectivo antes de empezar. Conservar sus copias y SHA-256, la revisión
   Git, el diff y los archivos no versionados relevantes. Registrar la procedencia
   como **candidato preparado para evaluación**, con su identificador y caso; no
   atribuirlo a un desarrollador ni inventar invocaciones o reparaciones.
2. Una revisión por candidato, en orden `candidato_01` a `candidato_04`:
   **cuatro invocaciones reales como máximo**, sin desarrollador ni corrección.
   Usar sesiones nuevas e independientes, sin memoria, feedback ni respuestas
   de otros candidatos. Mantener los mismos parámetros de invocación para los
   cuatro y la misma versión y bytes del prompt para los dos de cada caso.
   Anotar modelo, proveedor, esfuerzo y versión de CLI efectivos, o «no consta».
3. Preparar un workspace fuera del repositorio con una lista explícita de
   materiales: candidato como `candidato.py`, contrato y pruebas originales de
   su caso y los informes de su evaluación local real. Mantener
   nombres neutros en archivos, rutas y mensajes. **Excluir** este protocolo,
   `expectativas.md`, `tests/test_reviewer_candidates.py`, sus entradas y salidas
   adicionales, la tabla de resultados y los demás candidatos. No entregar
   el repositorio completo. No revelar etiquetas de correcto/defectuoso.
4. Conservar respuesta original, hallazgos, eventos, stdout, stderr, códigos,
   duración, configuración y hashes del contexto de cada revisión. Guardar por
   igual resultados favorables, desfavorables, respuestas inválidas y fallos
   técnicos. No repetir una revisión para conseguir el dictamen esperado, ni
   sustituir un fallo técnico; si no se puede continuar en las mismas condiciones,
   dejar los candidatos restantes sin ejecutar y documentar el motivo.
5. Contrastar después cada hallazgo con el contrato, la línea de código y su
   ejemplo. Registrar por separado: aprobación de código defectuoso; solicitud
   injustificada de cambios; hallazgos respaldados y no respaldados; fallos
   técnicos o respuestas inválidas. Una solicitud de cambios al candidato
   defectuoso con un motivo falso no cuenta como detección del defecto; un
   dictamen coincidente por sí solo no basta. Una aprobación conforme exige
   hallazgos vacíos. No contar fallos técnicos como aciertos o errores de juicio.
6. Publicar las cuatro filas, incluidas ausencias y fallos. **Cuatro candidatos
   no permiten estimar fiabilidad general** ni comparar modelos. Los prompts
   ya piden revisar prioridades y nombres exactos: el experimento mide el
   cumplimiento de ese encargo, no un diagnóstico sin pistas contractuales.

## Preparar y lanzar el experimento

Desde la raíz, preparar sin llamar al modelo:

```bash
python3 -B evaluate_reviewer.py prepare
```

La salida indica la ruta única `runs/<fecha>_revisor_<uuid>`. Solo una preparación
con código 0 autoriza el lanzamiento. `preparacion.json` registra la procedencia
`candidatos_preparados_para_evaluacion`, el orden y los SHA-256 de todo el árbol
`preparacion/`. Este contiene las fuentes congeladas (incluido el código del
lanzador), revisión y estado Git, diff de rutas explícitas y cuatro evaluaciones
reales: copias temporales, stdout, stderr, duración y códigos. Se acreditan los
4, 4, 16 y 16 tests originales completos. Un fallo conserva los informes
disponibles y deja la preparación no autorizada. No se copian configuraciones
personales, expectativas ni comprobaciones adicionales.

Para el **futuro experimento real**, después de comprobar esa preparación, usar
su ruta exacta; estos comandos no se han ejecutado contra el modelo en este hito:

```bash
read -r -p 'Ruta del experimento impresa por prepare: ' EXPERIMENTO_REVISOR
python3 -B evaluate_reviewer.py run --experiment "$EXPERIMENTO_REVISOR"
```

`run` verifica la evidencia congelada y que el código del lanzador no haya
cambiado. Crea `lanzamiento/` mediante una operación atómica: solo un proceso
puede obtener la reserva. El directorio permanece ante fallo, interrupción o
finalización, incluso si falla la escritura del resumen. Otro lanzamiento se
rechaza sin tocar la evidencia. **No hay reanudación ni reintentos**; no borrar
la reserva ni duplicar preparaciones para sustituir resultados desfavorables.
Una terminación forzosa puede dejar un resumen `en_curso`; eso no permite repetir.

Se reutilizan `evaluate`, `invoke_reviewer`, `response_schema` y `validate_verdict`.
No se pasa una reparación inventada a `run_review` ni se modifica
`validate_repair`. Las instrucciones [del caso 01](instrucciones_case_01.md) y
[del caso 02](instrucciones_case_02.md) derivan respectivamente de
`prompts/reviewer_case_01.md` y `prompts/reviewer.md`: sustituyen la procedencia y
la lista de materiales, conservando los criterios y el formato JSON.

Cada sesión recibe las instrucciones congeladas por stdin y un workspace
temporal nuevo, fuera del repositorio, con exactamente estos siete archivos:
`candidato.py`, `contrato.md`, `test_solution.py`, `posterior.json`,
`posterior.stdout.txt`, `posterior.stderr.txt` y `respuesta.schema.json`.
Los informes corresponden al candidato realmente evaluado. No se incluyen
originales ni diffs de una supuesta reparación. Esta selección de contexto y
la orden de no leer fuera **no garantizan aislamiento de seguridad**.

Se mantiene el modo `read-only`, política de aprobación `never`, web desactivada,
`features.multi_agent=false`, sesiones `--ephemeral` y límite de 180 segundos
por revisión; las consultas de versión/ayuda tienen límite de 10 segundos y
las pruebas originales de 30. No se invocan desarrolladores ni correcciones.
Los argumentos se comparan entre revisiones, salvo las rutas temporales. Se
registran y contrastan versión y hash del ejecutable. La CLI puede heredar
configuración y variables de entorno: el lanzador no las copia ni acredita que
sean iguales entre sesiones. Modelo, proveedor y esfuerzo efectivos figuran
como «no consta»; no se infieren de la versión. Conservar la misma instalación
y configuración durante el experimento y contrastar después los eventos.

`lanzamiento/resultado.json` resume candidatos ejecutados y pendientes, estados
técnicos, dictámenes y rutas de evidencia. Cada directorio de candidato conserva
materiales, instrucciones, argumentos, versión, tiempos, códigos, eventos,
stderr, respuesta original, dictamen validado e integridad. Los hashes se
comprueban también entre revisiones. `solicitar_cambios` válido permite continuar;
un fallo técnico, JSON inválido, alteración o interrupción detiene la secuencia.
No se puntúa por coincidencia con las expectativas: **validar un dictamen solo
acredita su estructura y coherencia**, no que sus hallazgos sean ciertos.

Códigos de salida: **0** operación completa con evidencia válida, sean cuales
sean los dictámenes; **1** fallo o ejecución incompleta; **2** argumentos
incorrectos. Tras el experimento será necesario evaluar los hallazgos según
el protocolo, conservando también fallos y candidatos pendientes.

## Progreso y canales de salida

La CLI informa de las etapas alcanzadas mediante mensajes breves en **stderr**,
con vaciado inmediato del canal. `prepare` anuncia la preparación de materiales
y comprobación de candidatos. `run` anuncia cada inicio como
`Revisión 1/4: iniciando candidato_01…` después de validar la evidencia,
obtener la reserva y superar las consultas previas de versión y ayuda de la
CLI. Una reserva existente o una comprobación fallida no anuncia una invocación.

Al terminar cada revisión muestra el candidato, su estado técnico y, cuando
existe, la decisión del dictamen validado. Una detención añade el motivo concreto
y la ubicación del registro, sin anunciar candidatos posteriores. Una decisión
`aprobar` puede acompañar a un fallo técnico si la CLI entregó JSON válido pero
terminó con código distinto de cero: se conservan ambos datos y se detiene.

El resumen final permanece en **stdout** y los códigos 0, 1 y 2 conservan su
significado. Redirigir stdout permite guardar ese resumen mientras stderr
sigue mostrando el progreso. No se retransmiten prompts, hallazgos completos
ni eventos, ni se añaden estimaciones de tiempo o mensajes periódicos.

Ejemplo ilustrativo **simulado**, extracto de stderr con solicitudes de cambios
válidas; no corresponde a una nueva ejecución real:

```text
Revisión 1/4: iniciando candidato_01…
candidato_01: completada; dictamen: solicitar_cambios.
Revisión 2/4: iniciando candidato_02…
candidato_02: completada; dictamen: solicitar_cambios.
```

Las funciones reutilizables `prepare()` y `run_experiment()` siguen siendo
silenciosas por defecto. El argumento opcional `progress` acepta una función
que recibe cada mensaje; la CLI lo conecta a stderr. Estos avisos del controlador
son distintos de los mensajes del revisor conservados en `eventos.jsonl` y no
modifican el prompt ni el JSON que valida el controlador.

## Validación local del lanzador

El 16 de octubre de 2026, con Python 3.12.3, se ejecutó una vez
`python3 -B -m unittest discover -s tests -v`: **148 pruebas en 48,607 s,
OK, código 0**. Incluye las 16 pruebas nuevas del lanzador y las 132 anteriores;
no se repitió el bloque nuevo por separado. Se verificaron el recorrido completo,
continuación tras solicitar cambios, límite de cuatro invocaciones, contexto,
integridad, respuestas inválidas, fallos técnicos, timeout, interrupción y
rechazo de lanzamientos simultáneos o repetidos. Se usaron procesos simulados
y repositorios temporales, sin llamadas reales al modelo. Al terminar esa
validación, la ejecución real y el contraste de sus hallazgos seguían pendientes;
los resultados posteriores están en el informe separado enlazado arriba.

Tras incorporar los avisos de progreso se ejecutó una vez el mismo comando,
con Python 3.12.3: **153 pruebas en 90,327 s, OK, código 0**. Incluye cinco
pruebas nuevas y ampliaciones de las existentes para comprobar el orden de
mensajes, separación de canales, aviso inmediato durante un proceso simulado,
silencio por defecto, detenciones y rechazo de reservas. Todos los agentes
fueron simulados y los repositorios temporales; no se volvió a preparar ni
lanzar el experimento real. Esta validación posterior no sustituye la de 148
pruebas previa al experimento.

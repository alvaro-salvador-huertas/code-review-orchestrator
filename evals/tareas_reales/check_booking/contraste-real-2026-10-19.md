# Contraste del primer recorrido real de check-booking

19 de octubre de 2026. **Revisión automática asistida por Codex**, mediante
lectura de archivos, comparación de hashes, objetos Git y manifiestos. No es
auditoría humana ni revisión independiente de proveedor. Durante este contraste
no se ejecutaron candidatos, suites, descubrimiento de pruebas, agentes ni
orquestaciones; tampoco se incorporó la entrega.

**Recomendación: preparar la incorporación explícita del candidato final exacto.**
No se identifica un incumplimiento concreto suyo frente al contrato congelado.
Sí se identifica una exigencia excesiva del evaluador sobre la representación
del nombre del archivo en los diagnósticos: provocó la corrección, sin demostrar
un fallo de la lógica de disponibilidad. Se conserva el rechazo histórico.

## Fuentes, procedencia y conservación

Las rutas siguientes son registros locales excluidos de Git, no adjuntos públicos:

- `R = runs/20261019T155332Z_check-booking_orchestrate_2437750e2eed4ac38b300357cf30b49e/`.
- `V = runs/20261019T160927Z_check-booking_review_ab27d12e98bb40d387bbe1edf69dfb7c/`.

Se contrastaron `R/resultado.json`, `referencia/`, `inicial/`, los dos directorios
`intentos/<n>/evidencia/`, las tres reservas y el registro de revisión `V`.
La rama conservada es `feat/tarea-disponibilidad-reservas`; HEAD y base declarada
son `b54e352b3abba5a0075b512fdd84c0094cee44fa`. El índice estaba vacío.
Los cambios pendientes de preparación se conservaron.

Los **114 archivos** de `R/referencia/proyecto/` coinciden, uno a uno, con los
blobs, modos Git y SHA-256 declarados en `referencia/procedencia.json` y con el
árbol de ese commit. No hay archivos adicionales ni exclusiones de esa base.
`check_booking.py` está ausente tanto en ella como en la raíz actual: la primera
partida es una ausencia auténtica, sin `partida.py` ni original vacío.

La configuración selecciona únicamente `check_booking.py`, creación regular
0644, biblioteca estándar, sin referencias adicionales. Contrato, configuración,
evaluador y prompts congelados coinciden byte a byte con los actuales:

| Autoridad congelada en `R/referencia/` | SHA-256 |
| --- | --- |
| `tarea.json` | `4cf85a493af4b632c70ba277a78bc23516e43a6d99c250419b9e2543d5db088c` |
| `contrato.md` | `1cab6e505ba1fd0dadf687d7e6d23facc63bf2827d6802ba9b8e982d30c98198` |
| `autoridades/evals/tareas_reales/check_booking/evaluar.py` | `b1b5101143912af710f571fda8b3a1aa5c1b7e383bcc852824fa4da2bf2b10db` |
| `prompts/developer_check_booking_flow.md` | `541d24a906fd17d6a1b4210da55e7bf7f91dbe7471e078266af5c1511eea9208` |
| `prompts/reviewer_check_booking_flow.md` | `f4709e1cebf4f5e9bf3e7baf302949f4acb45fbd861925b30630ff774c673153` |
| `autoridades/project_test_inventory.py` | `b0b4aca8f40db44ec33dcc3749187ff670bcac08be9518fbd014ed79534cfac2` |
| `inventario/informe.json` | `076418b51496721a647fabff272d16d9c26236fe1fe035c07840892d6115c778` |

Las seis utilidades de `procedencia.utilidades_sha256` y los siete módulos del
motor congelados también coinciden con el árbol actual y sus blobs de la base.
El inventario conserva **405 identidades únicas y ordenadas**, sin errores; su
hash y el hash canónico de `base_antes.json` coinciden con la procedencia.
Sus archivos corresponden a la base Git, no al candidato. El descubrimiento
registrado importa módulos; por sí solo no ejecuta los métodos ni acredita que
pasen. Aquí se leyó su informe, sin repetirlo.

Se recompusieron ambos diffs contra ausencia y contra partida. El primer
candidato tiene SHA-256
`49d67011f9f6ea1b1a78e57781cca512b94a73b4392f48822a122c32f3bca5fc`.
La `partida.py` del segundo es exactamente ese contenido; coinciden asimismo
`partida.json`, `partida_sha256` y el manifiesto del intento anterior. Los
inventarios de desarrollo registran únicamente creación/corrección del editable.

La entrega final es `R/intentos/2/evidencia/entrega/check_booking.py`:

- SHA-256: **`9a9038910c41d8642fa0deb22554dd192fd61d6415deb88a573b5c4d1465fbfe`**.
- Archivo archivado regular, **modo actual 0664**. Se conserva así.
- Desarrollo y evaluaciones registran archivo regular **0644**. Sus temporales
  ya no existen; ese modo histórico se acredita mediante inventarios conservados,
  no mediante un `stat` actual del workspace. Una futura copia al producto debe
  mantener esos bytes y establecer 0644 solo en el archivo nuevo.

Coinciden los 17 manifiestos de `etapas_cerradas`, el de la referencia completa,
los cierres internos de ambos intentos y los cinco orígenes registrados por el
revisor. Coinciden los hashes de las evaluaciones finales, la selección y las
copias de la entrega en `V/materiales/` y `V/evidencia_validada/`; la copia de
evidencia completa es idéntica a la del segundo intento. Los prompts enviados
al desarrollo contienen exactamente prompt, contrato, configuración y feedback
conservados; el segundo feedback reproduce el informe y diagnóstico del rechazo.

Antes de añadir esta documentación, el inventario del proyecto original coincide
con `R/resultado.json:original_sha256`, aplicando sus exclusiones de archivos
locales/privados. Los registros conservados pueden comprobarse ahora; la
inmutabilidad durante los procesos de las copias de desarrollo, evaluación y
revisión eliminadas solo consta en sus inventarios y banderas de integridad.
No se presenta ese contraste como una nueva observación de aquellos temporales
ni como prueba de ausencia de todo efecto externo.

## Evaluaciones acreditadas

Fuentes: `inicial/<suite>/` y `intentos/<n>/evidencia/evaluaciones/<suite>/`,
en cada caso `pruebas.json`, `evaluacion.json`, `resultado.json`,
`proyecto_evaluado.json` y `stderr.txt`. Se compararon **identidades**, no solo
totales: 24 métodos explícitos del evaluador congelado y las 405 identidades del
inventario. Cada informe acredita una sesión completa, los mismos métodos
iniciados/terminados y ningún expected failure ni éxito inesperado.

| Etapa y suite | Métodos | Métodos con fallos | Aserciones fallidas | Fallos de subtest | Errores | Omisiones | Código | Cierre unittest (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Inicial: aceptación | 24 | 24 | 24 | 0 | 0 | 0 | 1 | 0,009 |
| Inicial: regresión | 405 | 0 | 0 | 0 | 0 | 0 | 0 | 196,633 |
| Intento 1: aceptación | 24 | 10 | 186 | 184 | 0 | 0 | 1 | 7,894 |
| Intento 1: regresión | 405 | 0 | 0 | 0 | 0 | 0 | 0 | 195,878 |
| Intento 2: aceptación | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 7,641 |
| Intento 2: regresión | 405 | 0 | 0 | 0 | 0 | 0 | 0 | 194,944 |

Los cierres son `FAILED (failures=24)`, `FAILED (failures=186)` y `OK`, según
corresponde; concuerdan con códigos e informes. Los 184 fallos de subtest son
parte de las 186 aserciones, no métodos adicionales. Hay 644 subtests registrados
en cada aceptación posterior y 1082 en cada regresión, incluidos controles de
conservación. El log puede repetir la identidad de un método al informar sus
fallos; esto no añade métodos al informe estructurado.

La aceptación inicial falla en `setUp` por ausencia del archivo: **cero consultas
de la CLI candidata**. Tampoco se suman a esta tabla las comprobaciones auxiliares
de fixtures ni las 193/235 comprobaciones que declaran los desarrolladores y
figuran en sus eventos. El primer desarrollo incluye una comprobación auxiliar
fallida de modo 0664 y su ajuste a 0644 dentro de esa misma invocación; no fue la
causa del segundo intento. Esta ejecución real es distinta de la preparación
anterior y de las simulaciones de agentes presentes en la regresión.

## Causa exacta de la corrección

Las **186 trazas** del primer rechazo terminan en `evaluar.py:142`,
`assertIn(affected, diagnostic)`, con «El diagnóstico no localiza el archivo».
Antes se habían superado las aserciones de código 1 y stdout vacío. El stderr
conservado dentro de cada `AssertionError` sí incluye archivo y causa, pero el
primer candidato usaba `path!a` en la línea 142:

```text
Archivo 'solicitud sint\xe9tica.json': solicitud.inicio: fecha u hora invalida (day is out of range for month)
```

Ese caso usa `solicitud sintética.json`, solicitud de `Sala Norte`, inicio
`2023-02-29T10:00:00Z`, fin `2026-10-20T11:00:00Z`, y una reserva válida de
`Sala Sur`. El contrato exige rechazar la fecha imposible con código 1, stdout
vacío y diagnóstico de archivo y causa; esas condiciones constan en la traza.
El evaluador exige además la subcadena Unicode literal `solicitud sintética.json`.

Todos los fallos comparten ese diagnóstico escapado. Estas variantes concretas
se reconstruyen leyendo los fixtures congelados; no se vuelven a ejecutar:

| Método (sufijo) | Aserciones | Ejemplo de entrada inválida y requisito |
| --- | ---: | --- |
| `10_fechas_invalidas_en_solicitud_y_otro_recurso` | 68 | Inicio `2023-02-29T10:00:00Z`: fecha gregoriana válida exigida, también en otros recursos. |
| `11_intervalos_vacios_e_invertidos` | 4 | Inicio y fin `2026-10-20T10:00:00Z`: fin estrictamente posterior. |
| `12_ids_duplicados_tambien_entre_recursos` | 2 | Dos reservas `id="repetido"`, en Sala Norte/Sur: unicidad global. |
| `13_campos_ausentes_y_adicionales` | 12 | Raíz sin `solicitud`: claves obligatorias y exclusivas. |
| `14_tipos_de_contenedores` | 20 | Raíz `null`: debe ser objeto. |
| `15_tipos_de_campos_sin_coercion` | 49 | `solicitud.recurso=null`: debe ser cadena. |
| `16_cadenas_blancas` | 9 | `solicitud.recurso=""`: carácter no blanco obligatorio. |
| `17_json_invalido_y_codificacion` | 11 | Archivo vacío o bytes `EF BB BF` antes del JSON: documento JSON UTF-8 sin BOM. |
| `18_claves_duplicadas_a_toda_profundidad` | 10 | Reserva con `"id":"id", "\u0069d":"id"`: duplicados tras decodificar escapes. |
| `24_validacion_total_sin_salida_parcial` | 1 | Conflicto válido seguido de reserva ajena con inicio `2026-02-30T10:00:00Z`: validar todo antes de emitir. |

En todos se esperaba rechazo de la entrada; el desacuerdo observado está en
la representación del diagnóstico. No hay un archivo separado con la salida
de cada consulta: se usan las trazas y las aserciones anteriores alcanzadas.
El contrato permite redacción libre de diagnósticos y no exige nombre literal;
la representación escapada identifica el archivo. **El rechazo parece un falso
negativo por exigencia excesiva del evaluador**, no 186 defectos de dominio.

`intentos/2/evidencia/entrega/anterior.diff` contiene únicamente dos cambios:
`{path!a}` pasa a `{path}` en la línea 142 y se añade
`sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")` en la
línea 152, con su comentario. No cambia validación ni algoritmo de conflictos.
La aceptación final acredita el nombre literal bajo el entorno de evaluación.
No se modifica aquí el contrato ni el evaluador, ni se reclasifican los fallos;
la política de diagnósticos del evaluador merece revisión separada antes de
reutilizarlo para comparar implementaciones distintas.

## Dictamen y lectura estática de la entrega final

`V/revisor/respuesta_original.txt` y `V/dictamen_validado.json` contienen el mismo
objeto: **`decision="aprobar"`, `hallazgos=[]`**. El resumen afirma revisión
estática completa frente al contrato/configuración, diff, evidencia y evaluador,
sin ejecución ni cambios. Sus eventos conservados muestran lecturas de esos
materiales. El controlador registra `dictamen_aprobar_validado`; la orquestación
termina en `lista_para_revision_humana`, motivo `revision_aprobada`, código 0.
El histórico conserva `contraste_semantico="pendiente"` e incorporación
`no_realizada`; este informe posterior no altera esos campos.

Se leyó el candidato completo, incluidas combinaciones fuera de las pruebas.
Las líneas de esta tabla corresponden al archivo final archivado; sus conclusiones
son **deducciones estáticas**, no nuevas reproducciones:

| Requisito | Líneas | Comportamiento deducido |
| --- | --- | --- |
| Documento completo, claves y tipos exactos | 20–40, 53–79, 135–140 | Duplicados tras decodificar escapes rechazados; lectura UTF-8 y `json.loads` rechazan BOM, truncado y documentos concatenados. `parse_constant` rechaza NaN/Infinity. Claves exactas; booleanos, null y números no se convierten en cadenas. |
| Fechas UTC estrictas e intervalos positivos | 10–13, 43–69 | `fullmatch` con `[0-9]` y T/Z literales; `datetime` comprueba calendario y límites. No consulta reloj, admite años 0001–9999 y rechaza fracciones, offsets, dígitos Unicode y fin ≤ inicio. |
| Validación total e identificadores únicos | 81–94, 140–146 | Valida cada reserva antes de filtrar recursos; IDs únicos globales. Una fecha imposible después de un conflicto aborta antes del único `print` JSON. |
| Recursos literales, adyacencia, solapamientos y orden | 61–64, 90–94 | No normaliza ni recorta; usa `start < request_end` y `end > request_start`. Adyacentes no conflictivos; reservas existentes solapadas válidas. Añade IDs literales en orden; `not conflicts` produce booleano. |
| Canales, códigos y argumentos | 97–153 | Un posicional, `--`, ayuda y rechazo de opciones abreviadas; rutas relativas al cwd. Errores de lectura/validación producen 1 sin stdout, argumentos inválidos 2; resultados válidos 0 con JSON único. Escapes ASCII preservan Unicode, CR/LF y comillas en el JSON de salida. |
| Efectos y dependencias | 3–6, 135–153 | Solo biblioteca estándar, apertura de entrada en lectura; sin escritura de archivos, ejecución de contenido, servicios o lectura de configuración personal en el código. |

No se identifica un incumplimiento concreto del candidato final omitido por las
pruebas o el revisor. Esto no convierte la cobertura ni la revisión en una prueba
exhaustiva. No se añaden requisitos de almacenamiento, API o concurrencia.

## Tiempos, consumo y alcance de la conclusión

El recorrido completo figura entre `2026-10-19T15:53:32.505609Z` y
`2026-10-19T16:10:21.881822Z`: **1009,376 s**, dos intentos. Las reservas
coinciden con sus archivos y preceden a los procesos respectivos. Cada proceso
termina con código 0; el consumo se acredita también con procesos y eventos,
no solo contando reservas. `desarrollo_estado.json` conserva una instantánea
previa (`proceso=null`, contador 0); los cierres efectivos están en
`desarrollo/resultado.json` y los resúmenes finales.

| Invocación real | Duración proceso (s) | Límite (s) | Tokens entrada | Entrada en caché | Tokens salida |
| --- | ---: | ---: | ---: | ---: | ---: |
| Desarrollador, intento 1 | 213,294 | 300 | 158424 | 135936 | 9525 |
| Desarrollador, intento 2 | 135,455 | 300 | 744211 | 563584 | 5212 |
| Revisor, intento 2 | 54,381 | 300 | 78406 | 50816 | 1646 |

Son **2 desarrolladores + 1 revisor = 3/4 invocaciones**, sin revisión del primer
candidato ni segundo intento de revisión. Los eventos `turn.completed` informan
981041 tokens de entrada, de ellos 750336 en caché, y 16383 de salida; no se suman
las categorías de caché/razonamiento otra vez. Coste monetario: **no consta**.
Los tres preflight registran `codex-cli 0.162.1`; versión y ayuda tienen límite
10 s y no se cuentan como invocaciones de modelo.

Duraciones de proceso de aceptación/regresión, respectivamente: inicial
0,115/196,827 s; intento 1, 7,988/196,065 s; intento 2, 7,737/195,144 s.
Sus límites efectivos son 60/600 s; cada consulta candidata tiene límite 10 s.
Inventario: 0,266 s, límite 30 s. Las evaluaciones usan `/usr/bin/python3.12`,
`-B`, cwd temporal y política `evaluation`; el inventario registra Python 3.12.3.
El registro completo de revisión dura 54,744 s, incluyendo su preparación.

Esta ejecución acredita que una nueva tarea declarativa recorrió el motor
existente desde ausencia, consumió una corrección con continuidad exacta, pasó
aceptación y regresión protegidas y recibió aprobación del revisor. **La corrección
no acredita haber reparado la lógica de reservas**: resolvió la exigencia del
diagnóstico literal. Las pruebas de controladores de la regresión simulan agentes;
no equivalen a otras ejecuciones reales. Este único recorrido no establece
fiabilidad general, seguridad de despliegue ni independencia entre proveedores.

Quedan pendientes autorización de incorporación, copia exacta con modo 0644,
cobertura permanente en el descubrimiento habitual y validación del árbol que
resulte. La entrega no está en la raíz, no hay incorporación automática ni CI
nueva atribuida a este contraste. Solo se añaden este informe y su enlace en
la [guía](README.md); se conservan contratos, evaluadores, preparación histórica
y registros, sin commit, push ni merge.

# Revisión independiente de la entrega de inspect-json

**Actualización del 17 de octubre de 2026.** La primera revisión real terminó
por timeout de 180 segundos, con una invocación y sin dictamen. Se conserva
íntegro su [registro histórico](../../../runs/20261017T172157Z_inspect-json_review_f0959638ae404c95bcc359fa59d52cfc/resultado.json),
con código 4. La **segunda revisión real** con contexto reducido ya terminó:
solicitó cambios y sus dos hallazgos fueron confirmados automáticamente.
Las secciones finales documentan ese contraste y las correcciones posteriores,
asistidas por Codex bajo instrucciones del usuario. Una revisión estática de la
primera corrección solicitó resolver un desbordamiento de recursión, reproducido
y corregido en una nueva entrega. El último diff se revisó en esta conversación
y el usuario autorizó incorporar exactamente esa entrega: `--format json` ya
está disponible localmente, con cobertura permanente en CI. Esa revisión no se
atribuye al controlador ni cambia los dictámenes históricos de solicitar cambios.
Se conservan la rama `eval/inspect-json-primer-intento` y los cambios pendientes,
sin commit ni push.

## Interfaz utilizada para la segunda revisión

Desde la raíz del proyecto, con Codex CLI autenticado y acceso al servicio:

```bash
python3 -B review_project.py \
  --development-run runs/20261017T160946Z_inspect-json_48a800c7c6fc4967a26c592b57f754c5 \
  --reevaluation-run runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4
```

Este comando corresponde al candidato anterior, de hash `901ad474…d43e`.
Se utilizó en una sesión nueva, sin observaciones de la sesión interrumpida.
**No revisa la entrega corregida**: sus argumentos acreditan otra entrega.
No se ha vuelto a ejecutar ni se ha adaptado su procedencia en este hito.
Ambos argumentos son obligatorios. No acepta `--ignore-failures`, ni interpreta
el registro de desarrollo como una reparación aceptada del benchmark.
`review_case.py` y el flujo de benchmark permanecen sin cambios.

La función `validate_evidence(development_run, reevaluation_run, project_root)`
solo lee y contrasta toda la evidencia. `review_materials(...)` selecciona el
contexto y genera su resumen a partir de esa salida validada, sin lanzar procesos.
`run_review(...)` prepara e invoca al revisor;
es silenciosa por defecto y acepta un callback opcional `progress`. La CLI
envía progreso a stderr y resumen, código y ubicación del registro a stdout.
Las rutas declaradas por los registros deben corresponder con sus ubicaciones
reales; no se infiere procedencia por el nombre de una carpeta ni se reescriben
rutas históricas para aceptar registros trasladados o mezclados.

## Autorización a partir de evidencia real

El adaptador valida antes de consultar siquiera la versión o ayuda de Codex:

1. Desarrollo `inspect-json` con proceso del desarrollador finalizado, una
   invocación y resultado original **`no_supera_comprobaciones`, código 1**.
   Contrasta procedencia, referencia, etapas conservadas e integridad registrada.
2. Contrato congelado, commit base y archivos de la base frente a los objetos
   locales de Git, sin checkout ni red. Verifica contenido, hashes y permisos.
   La base permanece en `9bec53279d82058fe188c0038bab5ba66ce64003`.
3. Inspector original, entrega, copia de archivos modificados y diff exacto.
   El inventario entregado y el de la reevaluación deben coincidir con la base
   incorporando únicamente el mismo `inspect_run.py`, sin cambios de permisos.
4. Reevaluación explícita del mismo candidato, vinculada al registro original
   y al hash de su resultado fallido. Contrasta contrato, evaluador anterior,
   revisado y diff; el revisado, adaptador de pruebas y comprobaciones específicas
   deben coincidir con las autoridades del árbol de trabajo actual.
5. Informes iniciales y posteriores del desarrollo, aceptación revisada y
   comprobaciones específicas: procesos, comandos, cwd, códigos, canales,
   identidades AST, métodos completos y cierre textual de `unittest`.
   La nueva aceptación y sus comprobaciones deben estar superadas, sin errores,
   omisiones ni `expectedFailure`. Los fallos originales siguen siendo fallos.
6. Regresión posterior histórica superada, copia de sus cinco archivos idéntica
   al origen y mismos materiales del proyecto. Se identifica expresamente como
   reutilizada: no se ejecutan otra vez pruebas para autorizar la revisión.

La validación estática de los dos registros reales pasó y reconoció este
SHA-256 del candidato:

```text
901ad474e8928253abba00a22aa44be2d7db2aa22fc8b9d219d78c59a799d43e
```

La autorización identifica la aceptación revisada de **14 métodos**, sus **6
comprobaciones específicas** y la regresión histórica de **153 métodos**. El
evaluador anterior tiene SHA-256
`61bb184289eeb837f6aaf0c1d0688d31130515e8f1c3b7e35fb42742cb0d17df`, y el revisado,
`5b22e026bf3685fe592202cfe6bbea6af9a742595443d69876d354c9f8405530`.
El [informe de reevaluación](reevaluacion-2026-10-17.md) explica el ajuste derivado
del contrato. Ninguno de estos resultados es una nueva aprobación del candidato
por un revisor.

Evidencia ausente, incoherente o mezclada impide la invocación, con código 7.
En ese caso no se crea un registro de revisión ni se consulta la CLI.

## Materiales e instrucciones del revisor

La validación completa precede a la selección del contexto: siguen siendo
obligatorios todos los informes, pruebas congeladas y comprobaciones de
procedencia e integridad enumerados arriba. Que un archivo no se envíe al modelo
no permite omitirlo o alterarlo en los registros de origen.

El workspace externo contiene exclusivamente copias regulares de estos archivos:

| Material | Bytes |
| --- | ---: |
| `contrato.md` completo | 8.444 |
| `inspect_run.py` candidato completo | 16.280 |
| `original/inspect_run.py` completo | 14.499 |
| `candidato.diff` exacto | 15.009 |
| `dependencias/case_evidence.py` | 6.726 |
| `pruebas/test_inspect_run.py` congelado | 19.495 |
| `evaluacion/evaluador_revisado.py` | 17.363 |
| `resumen_evidencia.json` generado | 4.103 |
| `respuesta.schema.json` | 1.184 |
| **Total** | **103.103** |

Antes se entregaban **50 archivos, 427.921 bytes**; ahora son **9 archivos,
103.103 bytes**, una reducción del **75,9 %** de los materiales. El prompt pasa
de 3.653 a 3.815 bytes al explicar la nueva selección; no está incluido en esos
totales. Se retiran del contexto los 30 archivos de informes, la autorización
extensa, siete archivos de pruebas generales y el evaluador anterior, su diff,
el runner y las pruebas del ajuste del evaluador. Todos se conservan fuera del
workspace. Se evita repetir trazas y resultados iniciales/posteriores, así como
entregar dos evaluadores casi idénticos y pruebas del orquestador ajenas al cambio.

Se comprobaron por AST los imports de ambos inspectores, del evaluador revisado
y de la prueba específica, y sus dependencias transitivas. La única dependencia
local adicional es `case_evidence.py`; el resto pertenece a la biblioteca
estándar. Se rechazan dependencias no resueltas, ambiguas, paquetes locales,
imports relativos o llamadas de importación dinámica reconocidas, en vez de
excluir silenciosamente código necesario. No se importa ni ejecuta lo leído.

El resumen es determinista, sin fechas nuevas ni rutas absolutas a otros
registros. Conserva identificadores de desarrollo/reevaluación, base y HEAD,
hashes de candidato, contrato, evaluadores y evidencia, códigos y recuentos:

| Evidencia validada | Métodos correctos/total | Aserciones fallidas (subtests) | Código |
| --- | ---: | ---: | ---: |
| Aceptación inicial | 2/14 | 26 (20) | 1 |
| Aceptación original de la entrega | 13/14 | 2 (2) | 1 |
| Aceptación revisada | 14/14 | 0 (0) | 0 |
| Comprobaciones del evaluador | 6/6 | 0 (0) | 0 |
| Regresión inicial y posterior | 153/153 cada una | 0 (0) | 0 |

La regresión posterior se identifica como histórica reutilizada, no ejecutada
durante la reevaluación. El rechazo original continúa siendo código 1 y el
resumen dice expresamente que las pruebas no demuestran corrección general.
No contiene un dictamen esperado ni observaciones de la revisión interrumpida.

`evidencia_validada/` conserva los informes completos y las fuentes del resumen:
53 archivos, 521.750 bytes para estos registros. `seleccion.json` identifica la
fuente y hash de cada copia, las fuentes de cada fila del resumen y los
generadores del resumen y del esquema. Ambos quedan fuera del workspace y
también se contrastan antes y después del agente. Las rutas de la correspondencia
son relativas al archivo de evidencia completo. El resumen solo contiene
identificadores de procedencia; no introduce enlaces al repositorio u otros
registros. No se entregan explicaciones, prompts o eventos de agentes anteriores.

**Reducir contexto no garantiza evitar otro timeout.** Se mantiene una sesión
nueva, 180 segundos y una invocación máxima por lanzamiento, sin reintentos
automáticos ni continuación de la sesión anterior.

Las [instrucciones específicas](../../../prompts/reviewer_inspect_json.md)
exigen revisar código y contrato, incluyendo entradas admitidas no cubiertas
por las pruebas. Cubren compatibilidad del modo texto, esquema JSON, desconocidos,
tipos, duración, códigos y canales, resúmenes enlazados, rutas y lectura de
pruebas históricas por AST. Prohíben ejecutar candidatos, dependencias, pruebas
o ejemplos; modificar archivos; reparar; acceder a red, Git, configuración
personal o fuera del workspace; y delegar en otros agentes.

## Dictamen, decisiones y códigos

La respuesta final debe ser un único objeto JSON con `decision`, `resumen` y
`hallazgos`, sin claves adicionales. `aprobar` exige una lista vacía;
`solicitar_cambios` exige al menos un hallazgo. Cada hallazgo contiene:

| Campo | Validación del controlador |
| --- | --- |
| `archivo` | Exactamente `inspect_run.py`. |
| `linea` | Entero positivo dentro de las líneas del candidato; no booleano. |
| `requisito` | Cadena no vacía que identifique el requisito contractual. |
| `explicacion` | Cadena no vacía que explique el incumplimiento. |
| `ejemplo` | Cadena no vacía: entrada concreta, resultado esperado y comportamiento deducido. |

El controlador valida estructura, campos, líneas y coherencia de la decisión.
**No verifica automáticamente la veracidad semántica del requisito, explicación
o ejemplo.** `contraste_semantico` permanece `pendiente`, también con código 0.
El revisor juzga el cumplimiento contractual; su dictamen no equivale a una
demostración de corrección general ni incorpora archivos al proyecto.

| Código | Estado del controlador |
| --- | --- |
| 0 | `dictamen_aprobar_validado`: evidencia, proceso, integridad y JSON válidos; el revisor propone aprobar. |
| 1 | `cambios_solicitados`: dictamen válido con hallazgos pendientes. |
| 2 | Argumentos incorrectos; stdout vacío y diagnóstico en stderr. |
| 3 | `fallo_revisor`: CLI ausente/incompatible, fallo de inicio o proceso con código no cero. |
| 4 | `tiempo_agotado_revisor`: consulta previa o agente agotó su límite. |
| 5 | `respuesta_invalida`: respuesta ausente, JSON o coherencia inválidos. |
| 6 | `modificacion_no_permitida`: alteración de workspace, materiales, autorización, entrada, originales u orígenes. |
| 7 | `evidencia_invalida`: la procedencia no autoriza iniciar la revisión. |
| 8 | `fallo_controlador`: preparación, escritura o almacenamiento fallidos. |
| 9 | `interrumpida`: interrupción atendida, incluyendo SIGINT/SIGTERM. |

Un JSON que diga `aprobar` no produce aprobación si el proceso falló o la
integridad cambió. Tampoco se convierte una respuesta inválida en aprobación.

## Procesos, evidencia y límites

Se reutiliza `review_case.invoke_reviewer`: un `codex exec` nuevo, modo
`read-only`, sesión efímera, aprobaciones `never`, web y multiagente desactivados,
esquema de salida y respuesta final separada de los eventos. No hay reanudación
ni correcciones automáticas. El presupuesto se reserva antes de invocar:
**una invocación máxima, 180 s**, y **10 s** para cada consulta de versión/ayuda.
No hay timeout global adicional. Las utilidades de procesos conservan los
canales y detienen el grupo del proceso ante timeout o interrupción.

El registro `runs/<fecha>_inspect-json_review_<id>/` conserva:

- `origen.json`: autorización y snapshots de ambos registros de entrada.
- `materiales/`: únicamente las nueve copias destinadas al workspace, incluido
  el resumen y el esquema; `materiales_sha256` acredita esta selección.
- `evidencia_validada/`: evidencia completa conservada fuera del workspace;
  `evidencia_sha256` acredita su inventario.
- `seleccion.json`: correspondencia de las copias y fuentes del resumen.
  `contexto` registra versión de selección, tamaño y hash de esa correspondencia.
- `revisor/`: prompt efectivo, versión y ayuda, eventos, stderr, respuesta
  original disponible y resultados de los procesos; `resumen.json` reúne
  el resultado normal de la utilidad de invocación.
- `dictamen_validado.json`, únicamente si el proceso terminó correctamente y
  el dictamen pasó la validación; `resultado.json` separa decisión, proceso,
  presupuesto, integridad y contraste semántico pendiente.

Se acreditan la versión y las opciones explícitas de CLI conservadas. No se
deducen modelo, proveedor o esfuerzo efectivos ni se lee configuración personal.
Los registros originales y el árbol de trabajo se contrastan antes y después.
Si falla el propio almacenamiento puede quedar evidencia parcial; se informa
del fallo y no se declara aprobación.

**Las copias y hashes no constituyen aislamiento de seguridad.** Contrastan
estados conservados, no prueban ausencia de acciones transitorias ni autentican
criptográficamente toda la ejecución histórica. Las copias temporales de las
evaluaciones antiguas ya no existen: su integridad durante aquellas ejecuciones
es lo registrado por sus controladores. Las instrucciones de revisión tampoco
sustituyen las restricciones del entorno. Los resultados posteriores del
desarrollo no tenían un hash de cierre propio: su copia se contrasta con la
regresión conservada y sellada por la reevaluación, sin inventar ese hash antiguo.

## Validación de la preparación inicial

Las [18 pruebas nuevas](../../../tests/test_review_project.py) usan repositorios
temporales, informes sintéticos declarados como datos y una CLI de Codex
simulada. Sus candidatos contienen marcadores que fallarían si se ejecutasen.
Comprueban autorización, aprobación y cambios, exclusión de la explicación del
desarrollador, silencio de funciones, canales, una sesión nueva, evidencia
alterada/mezclada, omisiones aun con manifests actualizados, enlaces, cambio de
autoridad, comandos/candidatos distintos, dictámenes inválidos, fallo técnico,
timeout, interrupción y cambios de integridad. No dependen de `runs/` real.

Se ejecutó **una vez** la suite completa mediante `project_test_runner.py`, con
Python 3.12.3 y reportes fuera del proyecto. Resultado conservado: **195 métodos,
185 correctos y 10 con fallos; 14 aserciones fallidas, 6 de subtests; código 1**.
Los **177 métodos anteriores pasaron**. Los fallos nuevos se debían al fixture:
la copia sintética no fijaba los permisos que Git registra, y el adaptador la
rechazaba antes de invocar al revisor simulado. Duración de `unittest`: 63,390 s.

Se corrigió únicamente esa exportación temporal para aplicar el modo Git,
igual que el adaptador de desarrollo. Después se ejecutaron **solo los 18
métodos nuevos: 18/18, sin fallos, errores ni omisiones; código 0**, en 3,404 s
según `unittest`. No se repitieron los 177 anteriores ni la suite completa.
No se presenta la primera ejecución como verde ni como 195 pruebas correctas
en una única ejecución. Los agentes fueron simulados en ambas comprobaciones.

Se conservan comandos, stdout, stderr, códigos, tiempos, informes estructurados,
fuentes finales y la verificación estática de los registros reales en el
[registro local de preparación](../../../runs/20261017T165230Z_inspect-json_revision_preparacion_6edef433241d44af8ca647a944b13b1f/resultado.json).
Es evidencia de validación del adaptador, **no un registro de revisión real ni
un dictamen sobre inspect-json**. `runs/` permanece excluido de Git. Se
comprueban diff y enlaces sin repetir suites por cambios de documentación.

## Validación de la reducción de contexto

Se ejecutaron una vez los **23 métodos** de `tests/test_review_project.py`:
**23 correctos, sin fallos ni errores, código 0**, en 6,851 s de `unittest`
(7,041 s del proceso), mediante `run_process()` con entorno de evaluación:

```bash
python3 -B -m unittest discover -s tests -p test_review_project.py -v
```

Las cinco comprobaciones añadidas cubren selección exacta, fuentes conservadas,
ausencia de enlaces/rutas externas generadas, determinismo y fidelidad del resumen,
métodos frente a subtests, dependencias de pruebas y transitivas, rechazo de
regresión incoherente aunque se excluya del modelo y alteración del archivo
completo o de su correspondencia. Se mantienen las comprobaciones previas de
timeout, una invocación, dictamen, fallo técnico e integridad. La CLI es simulada;
no se han ejecutado el candidato real, sus evaluaciones ni otro agente.

La validación completa sobre los registros reales sigue pasando. Se conservan
comandos, salidas, resultado y medición en `/tmp/inspect-json-contexto-t1t8z77v/`,
fuera de Git; `contexto_preparado/` permite examinar la selección sin una revisión.
No se amplió la regresión: no cambiaron utilidades compartidas. Se comprueban
diff, enlaces e integridad de los 23 registros históricos sin repetir suites
por cambios documentales. `runs/` permanece excluido.

La preparación terminó dejando pendiente la segunda revisión. Los hitos
posteriores se documentan a continuación; el adaptador nunca aplica la entrega
al inspector original.

## Segunda revisión, contraste y corrección asistida — 17 de octubre de 2026

La [segunda revisión](../../../runs/20261017T180430Z_inspect-json_review_86dc81df0b344c7f9cd5143a5f46e816/resultado.json)
terminó con `cambios_solicitados`, código 1. Su
[dictamen](../../../runs/20261017T180430Z_inspect-json_review_86dc81df0b344c7f9cd5143a5f46e816/dictamen_validado.json)
señaló dos defectos: resúmenes enlazados que equiparaban booleanos con números
y rechazo de duraciones enteras grandes. El
[contraste automático asistido por Codex](../../../runs/20261017T182724Z_inspect-json_contraste_cd551fbe620a4f2eab019dbf2bc219bf/resultado.json)
los confirmó: seis métodos, tres superados y tres fallidos por aserción, sin
errores ni fallos de subtests; ocho consultas CLI, código de suite 1. El dictamen
y su contraste son evidencias distintas; sus registros permanecen intactos.

La [corrección posterior](../../../runs/20261017T183348Z_inspect-json_correccion_asistida_fcdfee843de446868f0d98fe2a0c4c19/resultado.json)
es una actuación asistida por Codex bajo instrucciones del usuario, **no una
segunda invocación del adaptador de desarrollo ni una reparación automática**.
Se reconstruyó la base congelada y se incorporó exactamente el candidato
`901ad474e8928253abba00a22aa44be2d7db2aa22fc8b9d219d78c59a799d43e`
antes de cambiar únicamente `inspect_run.py` en esa copia. El
[inspector corregido](../../../runs/20261017T183348Z_inspect-json_correccion_asistida_fcdfee843de446868f0d98fe2a0c4c19/entrega/inspect_run.py)
tiene SHA-256:

```text
078458839fd1cbd7356c12838d87a28639059e918f3cb21f3bab4fa7b778b751
```

En JSON, la comparación recursiva distingue booleanos de números, conservando
la equivalencia entre enteros y floats numéricamente iguales. Los enteros de
duración se validan por signo sin convertirlos a float; los floats requieren
finitud y signo válidos. JSON no prepara la presentación textual. El texto
mantiene sus resultados heredados por decisión explícita del usuario; no se
modifica el contrato. La lectura de etapas, transiciones e informes sigue siendo
compartida. Se conservan el candidato anterior, hashes,
[diff de la corrección](../../../runs/20261017T183348Z_inspect-json_correccion_asistida_fcdfee843de446868f0d98fe2a0c4c19/entrega/correccion.diff)
y [diff completo con la base](../../../runs/20261017T183348Z_inspect-json_correccion_asistida_fcdfee843de446868f0d98fe2a0c4c19/entrega/candidato.diff).

Se evaluó otra copia reconstruida desde la referencia con solo el inspector
corregido. Cada suite se ejecutó una vez, mediante el runner existente y
procesos hijos con política `evaluation`, con las pruebas protegidas intactas:

| Evaluación nueva | Métodos superados/total | Aserciones fallidas / errores | Código | Duración del proceso |
| --- | ---: | ---: | ---: | ---: |
| `comprobar_hallazgos.py` | 6/6 | 0 / 0 | 0 | 1,171 s |
| Aceptación revisada | 14/14 | 0 / 0 | 0 | 2,777 s |
| Regresión congelada, ejecutada de nuevo | 153/153 | 0 / 0 | 0 | 86,277 s |
| Compatibilidad textual adicional | 3/3 | 0 / 0 | 0 | 1,170 s |

Las utilidades de la base conservan su implementación histórica; no se
parchearon. El entorno reducido se aplica al proceso externo de cada suite y
se hereda por sus hijos.

No hubo fallos de subtests. La aceptación ya cubre texto ordinario y equivalencia
predeterminado/explícito con evidencia completa e incompleta; los 18 métodos del
inspector dentro de la regresión cubren también `inspect_run(run_dir)`. Las tres
comprobaciones adicionales hacen seis comparaciones byte a byte de código,
stdout y stderr contra la base para `0/false`, `1/true` y duración `10**309`:
ambas formas de texto coinciden, con códigos heredados 0, 0 y 1. No se duplicaron
los controles ordinarios. En JSON, ambos booleanos producen ahora incidencia
localizada y código 1; el entero de 310 dígitos se conserva y da código 0.

El registro nuevo conserva comandos, canales, códigos, duración, Python 3.12.3,
referencias e inventarios. La regresión histórica anterior no sustituye estos
153 métodos nuevos. No hubo llamadas reales adicionales a agentes ni cambios
en los registros históricos, evaluadores, pruebas o inspector del repositorio.
Las copias y el entorno mínimo no proporcionan aislamiento de seguridad.
En ese hito quedó pendiente la revisión de la entrega, aunque las pruebas
habían pasado. La revisión estática y la corrección siguientes se documentan
a continuación; no se ha incorporado la funcionalidad al proyecto.

## Comparación iterativa — 17 de octubre de 2026

La [revisión estática asistida por Codex](../../../runs/20261017T185303Z_inspect-json_revision_estatica_asistida_ce5f895edb2c475db117e2363dbeb600/dictamen.json)
solicitó cambios por el uso de recursión en `same_json_values`. Fue una revisión
en una sesión nueva, sin ejecutar el candidato: no una llamada a
`review_project.py` ni una auditoría humana.

La [reproducción posterior](../../../runs/20261017T190319Z_inspect-json_correccion_iterativa_asistida_837127072360467f8ecd068e449e2594/reproduccion/resumen.json)
confirmó el hallazgo sobre el candidato `07845883…b751`. Primero, el registro
sintético completo dio código 0. Después se añadió el mismo campo con 600
listas alrededor de `0` a ambos resúmenes: código 1, stdout vacío y
`RecursionError` en la comparación del candidato. El fixture se construyó por
sustitución textual, sin copiar ni serializar recursivamente el árbol profundo;
se verificaron su lectura JSON, la copia íntegra y la conservación de archivos.

Esta [nueva corrección asistida bajo instrucciones del usuario](../../../runs/20261017T190319Z_inspect-json_correccion_iterativa_asistida_837127072360467f8ecd068e449e2594/resultado.json)
cambia únicamente `same_json_values` en una copia reconstruida desde la base
congelada. Una pila de pares pendientes sustituye la recursión. Se conservan
las diferencias booleano/número, la equivalencia numérica entero/float, las
claves y valores de diccionarios sin depender de su orden, y la longitud,
orden y contenido de listas. No se cambia el límite de recursión ni se trata
una comparación válida como incidencia. El recorrido textual y las correcciones
anteriores permanecen sin cambios.

SHA-256 de la [entrega nueva](../../../runs/20261017T190319Z_inspect-json_correccion_iterativa_asistida_837127072360467f8ecd068e449e2594/entrega/inspect_run.py):

```text
8abca5003639de7ddbed2c5f242c60d2a030be2548538b5f2a0b1507e78e7b87
```

El registro conserva el candidato anterior, ambos hashes, el
[diff de la corrección](../../../runs/20261017T190319Z_inspect-json_correccion_iterativa_asistida_837127072360467f8ecd068e449e2594/entrega/correccion.diff),
el diff completo respecto a la base, comandos, canales, códigos y duraciones.
No representa otra invocación del adaptador original ni un bucle automático.

| Evaluación ejecutada una vez sobre esta entrega | Métodos superados/total | Código |
| --- | ---: | ---: |
| [Anidamiento por CLI](comprobar_anidamiento.py), separado de aceptación y CI | 7/7 | 0 |
| Hallazgos anteriores | 6/6 | 0 |
| Aceptación revisada | 14/14 | 0 |
| Compatibilidad textual adicional | 3/3 | 0 |

Los 30 métodos terminaron sin aserciones fallidas, errores ni fallos de subtests.
Las comprobaciones nuevas realizan ocho consultas JSON (el método de listas
tiene dos subtests); las cuatro exigidas dan, respectivamente, códigos 0 para
estructuras iguales, 1 para `0/false`, 1 para números distintos y 0 para `1/1.0`.
Todas conservan la proyección general y stderr vacío; las discrepancias señalan
el resumen enlazado. También se comprueban claves y orden de diccionarios y
longitud y orden de listas. Se utilizan procesos hijos con política `evaluation`
y límite de 10 segundos por consulta. La aceptación mantiene su entorno mínimo
propio dentro del proceso externo con esa política.

La aceptación ya compara texto ordinario predeterminado/explícito. Los tres
métodos adicionales conservan las seis comparaciones byte a byte contra la
base para los dos booleanos y la duración grande. No se repitió la regresión
congelada completa: **153/153 es un resultado histórico del candidato anterior,
no una evaluación de esta entrega**. En ese hito quedaron pendientes la revisión
del cambio, su incorporación y la suite completa del proyecto actual. El hito
siguiente los aborda; superar las pruebas no demuestra corrección general.

## Incorporación local y cobertura permanente — 17 de octubre de 2026

Tras revisar el último diff en esta conversación, el usuario autorizó incorporar
la entrega `8abca5003639de7ddbed2c5f242c60d2a030be2548538b5f2a0b1507e78e7b87`.
Se verificaron su manifiesto, procedencia, diffs e informes de evaluación, y que
el inspector del repositorio seguía siendo idéntico al original congelado. Se
copió exactamente la entrega y se comprobó de nuevo su SHA-256.

[`tests/test_inspect_json.py`](../../../tests/test_inspect_json.py) incorpora al
descubrimiento principal 29 métodos: 14 de aceptación, seis de hallazgos, siete
de anidamiento y dos adicionales para el comportamiento textual heredado de
booleanos y duraciones grandes. Reutiliza las clases existentes sin modificar
sus aserciones ni ejecutar suites secundarias. Los datos y las salidas auxiliares
son temporales; no requiere `runs/`, rutas personales, Git histórico, credenciales
ni llamadas a modelos. La regresión textual existente permanece en `tests/`.

La procedencia sigue distinguiendo el desarrollo inicial mediante adaptador,
el ajuste contractual del evaluador y la reevaluación, los dictámenes de cambios
y las correcciones asistidas bajo instrucciones del usuario. La revisión del
último diff no es una aprobación emitida por `review_project.py` ni una auditoría
humana. Los dictámenes históricos y registros permanecen intactos. Esta tarea
no demuestra un ciclo automático completo de desarrollo, revisión y corrección.

La [validación de la incorporación](../../../runs/20261017T191329Z_inspect-json_incorporacion_local_b9dd59422c66469799475cfa61741d05/resultado.json)
ejecutó una sola vez `python3 -B -m unittest discover -s tests -v` sobre el árbol
actual completo: **238/238 métodos**, código 0, sin fallos, errores ni omisiones;
119,277 segundos según unittest (119,566 segundos de proceso). Los 29 métodos
nuevos ya están incluidos en ese total, junto con los cambios pendientes del
controlador, entornos y revisión. No se volvieron a lanzar por separado la
aceptación ni los contrastes. Las evaluaciones internas que ejercitan los
fixtures son distintas de los métodos del descubrimiento principal; no se
presenta un total agregado de esas ejecuciones auxiliares. Tampoco se reutilizan
los 153 métodos congelados como validación de la incorporación.

El inspector incorporado conserva el SHA-256 autorizado. Los registros anteriores,
contratos, benchmark y evaluadores permanecen intactos. Los enlaces a `runs/`
identifican evidencia local excluida de Git y no estarán disponibles en un clon
limpio; ni el uso de la interfaz ni CI dependen de esos registros. Se conservan
los cambios pendientes, sin commit, push ni merge. La incorporación es local;
la preparación y publicación de una PR son pasos posteriores.

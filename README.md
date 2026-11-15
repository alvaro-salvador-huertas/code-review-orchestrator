# code-review-orchestrator

**v1: orquestación supervisada para tareas Python acotadas.** El proyecto aborda
cómo evaluar y revisar cambios propuestos por agentes con criterios explícitos,
un presupuesto limitado y evidencia de cada decisión. Separa la generación de
código, las pruebas independientes, el dictamen de revisión y el control del flujo.

Incluye dos ejercicios de reparación, tareas de proyecto configurables, un
planificador de borradores y herramientas para consultar registros. Trabaja con
copias y conserva candidatos, informes y fallos. La incorporación al producto
requiere autorización humana; superar el flujo no aplica el cambio automáticamente.

La última release publicada es [v1.1.0](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/releases/tag/v1.1.0).
**v1.2.0 está pendiente de publicación**: consulta sus
[notas preparadas](docs/notas-v1.2.0.md) y los
[pasos de publicación tras el merge](docs/publicacion-v1.2.0.md).
El [cierre de la v1](docs/cierre-v1.md), las [notas de v1.0.0](docs/notas-v1.0.0.md)
y su [release](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/releases/tag/v1.0.0)
conservan el historial. v1.1.0 añadió la preparación local de tareas desde planes archivados.

Elige un primer recorrido desde la raíz de un clon:

| Objetivo | Recorrido | Requisitos |
| --- | --- | --- |
| Explorar un resultado sin modelo ni ejecutar candidatos. | [Demo del inspector](#demo-sin-modelo). | Python 3 y biblioteca estándar. |
| Preparar la revisión de un diff local con un ejemplo existente. | [Vista previa de revisión](#revisar-un-diff-local-sin-modelo). | Python 3, Git y los commits locales del ejemplo. |
| Comprobar la frontera que ejecuta pruebas de proyectos. | [Preparar Podman y ejecutar la sonda](#preparar-el-evaluador-aislado). | Linux, Podman rootless y cgroups v2 con delegación. |

## Demo sin modelo

Desde la raíz de un clon, con Python 3 y su biblioteca estándar:

```bash
python3 -B inspect_run.py --run examples/inspect_run/aprobada
python3 -B inspect_run.py --run examples/inspect_run/aprobada --format json
```

Ambos comandos consultan los ejemplos existentes y devuelven código **0**.
No necesitan Codex, credenciales, red ni registros privados. No ejecutan el
código de los candidatos. Puedes cambiar el último componente de la ruta:

| Escenario | Ejecución representada | Resultado de la consulta |
| --- | --- | --- |
| `aprobada` | Aprobación, código 0. | Consulta completa, código 0. |
| `fallo_agente` | Fallo de agente, código 3. | Consulta completa, código 0. |
| `incompleta` | Aprobación declarada con un informe ausente. | Consulta incompleta, código 1. |

**Todos los datos de esta demo son sintéticos**, incluidos dictámenes, tiempos y
recuentos. Permiten explorar el inspector; no acreditan ejecuciones de agentes
ni pruebas reales. La [guía de la demo](examples/inspect_run/README.md) explica
los canales y la diferencia entre el código de consulta y el de ejecución.

## Revisar un diff local sin modelo

Este ejemplo compara los commits anteriores y posteriores al refactor de lectura
de `booking_batch.py` de la [PR #25](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/25).
Necesita esos objetos en el clon; una copia superficial puede no contenerlos.

```bash
python3 -B review_diff.py --repo . \
  --base 8e6415f117d1056f560801574297890d5ead9e17 \
  --candidate 9318c5b02c20daa7362194f40a2e4c2ee36ce38d \
  --file booking_batch.py \
  --criterion 'Conservar el comportamiento de la CLI y sus diagnósticos.' \
  --criterion 'Conservar la lectura UTF-8 estricta y el rechazo de JSON no válido.' \
  --criterion 'No escribir resultados parciales si una consulta posterior falla.'
```

Devuelve código **0** y JSON con `estado: vista_previa_sin_modelo`: los textos,
hashes, diff y criterios que se entregarían al revisor. Lee objetos Git locales;
no incorpora cambios sin commit, ejecuta pruebas ni produce un dictamen de modelo.
La [guía de revisión](docs/revision-diff.md) incluye también el modo `--snapshot`
para fuentes C++ de un solo commit, sin compilarlas ni ejecutarlas.

Para solicitar el dictamen hay que añadir explícitamente `--invoke-model` y
`--output` con un directorio nuevo. Esa operación requiere Codex CLI autenticado
y envía los archivos completos seleccionados; usa una sesión nueva de solo lectura,
una invocación y hasta 180 s. El dictamen sigue sujeto a revisión humana.

## Preparar el evaluador aislado

En Ubuntu, un administrador puede instalar los paquetes oficiales:

```bash
sudo apt-get update
sudo apt-get install --yes podman uidmap crun slirp4netns fuse-overlayfs dbus-user-session
```

El usuario necesita rangos subordinados de UID/GID y una sesión con cgroups v2
que delegue CPU, memoria y procesos. Después, **como usuario normal**, desde el
mismo entorno que usará el controlador:

```bash
podman --version
podman info --format json
python3 -B python_evaluator.py prepare
python3 -B python_evaluator.py check
```

`prepare` descarga por separado la imagen Python oficial fijada por digest.
`check` arranca una sonda real y comprueba las protecciones efectivas; no ejecuta
candidatos. Cada evaluación repite la comprobación antes de importar código del
proyecto y funciona sin red ni descargas automáticas. Si falta el runtime, la
imagen o un control, se detiene: no ejecuta el candidato en el anfitrión.

La frontera cubre el inventario y la evaluación de `orchestrate_project.py`,
aceptación y regresión de `repair_project.py inspect-json`, `run_case.py` y
`repair_case.evaluate()`, incluida la reparación orquestada y la preparación
del revisor. Los agentes conservan su política de Codex. Los runners invocados
directamente y los scripts manuales quedan fuera. Consulta los
[controles, cuotas por evaluación, limpieza y requisitos](docs/aislamiento-evaluador-python.md)
antes de ejecutar tareas.

## Preparar una tarea desde un plan, sin modelo

```bash
python3 -B prepare_project.py --from-plan /ruta/al/registro --output /ruta/a/padre/paquete-nuevo
```

El padre debe existir y el destino ser nuevo. Un plan completo genera
`contrato.borrador.md`, `configuracion.borrador.json` y `revision.md` (código 0).
Con preguntas, supuestos acumulados o viabilidad insuficiente produce solo
`revision.md` (3). Origen inválido o fallo de exportación devuelve 1; argumentos
incorrectos, incluidas rutas vacías, devuelven 2.

Son borradores no ejecutables. No consulta Git ni modelos, ejecuta pruebas o
consume reservas. Conserva la base y la cadena históricas, rechaza destinos
existentes y mantiene la precondición de aceptación inicialmente fallida del
motor. La [guía de preparación](docs/preparacion-tareas.md) precisa destinos,
interrupciones, límites y una demostración sintética reproducible de ambos resultados.

## Roles y decisiones

| Rol | Responsabilidad |
| --- | --- |
| Desarrollador | Propone cambios en una copia, dentro de los archivos autorizados. |
| Evaluador | Ejecuta las pruebas preparadas, por separado del agente, y registra resultados. |
| Revisor | Examina candidato, contrato y evidencia en una sesión nueva de solo lectura; emite un dictamen. |
| Controlador | Fija materiales, valida procesos e integridad, cuenta invocaciones y decide continuar o detenerse. |

El flujo evalúa la partida, solicita desarrollo, evalúa la entrega y, si cumple
las condiciones, solicita revisión. Puede admitir una corrección dentro del
presupuesto de uno o dos intentos, hasta cuatro invocaciones de agentes. Un fallo
técnico, timeout o evidencia inválida detiene el recorrido; no hay reintentos
técnicos automáticos. Contrato, evaluador y límites se preparan antes de empezar.

Las [interfaces del benchmark](docs/funcionamiento.md), el
[flujo de proyectos](docs/orquestacion-proyectos.md) y las
[configuraciones v1/v2 de tareas](docs/tareas-configurables.md) detallan las
precondiciones y presupuestos de cada vía. Esas versiones de configuración son
formatos internos y no equivalen a la versión del proyecto.

## Planificación y llamadas a modelos

El planificador convierte una solicitud en un **borrador revisable**, con
alcance, exclusiones, archivos, criterios, preguntas y supuestos. No inicia
desarrollo, pruebas, revisión ni incorporación. La ausencia de preguntas no
constituye aprobación.

Este ejemplo **invoca un modelo si se ejecuta**; no es necesario para la demo:

```bash
python3 -B plan_project.py "Contrasta una propuesta de consulta con el contrato" \
  --reference booking_core.py --reference tasks/006-booking-core.md
```

`--reference` selecciona documentos del commit base de Git. El planificador
entrega sus textos completos; los cambios locales no sustituyen esas fuentes.
Las continuaciones heredan exactamente las referencias archivadas. Cada
planificación usa como máximo una invocación de 300 s. Las opciones de modelo y
esfuerzo expresan valores solicitados, no prueban qué modelo se sirvió.

| Operación | ¿Invoca modelos? |
| --- | --- |
| Consultar con `inspect_run.py` o `inspect_project.py`; exportar JSON de consulta a CSV. | No. |
| Pedir ayuda o exportar plantillas de respuestas/decisiones del planificador. | No. |
| Preparar borradores con `prepare_project.py`. | No; tampoco ejecuta pruebas ni consulta Git. |
| Preparar la vista previa con `review_diff.py`. | No; tampoco ejecuta pruebas. |
| Pedir dictamen con `review_diff.py --invoke-model --output`. | Sí. |
| Evaluar un caso con `run_case.py`. | No; sí ejecuta pruebas en una copia mediante Podman rootless. |
| Crear un plan o continuarlo con `--answers` o `--decisions`. | Sí. |
| Lanzar desarrollo, revisión u orquestación de casos o proyectos. | Sí, al alcanzar la etapa correspondiente. |

Las operaciones con modelos necesitan Codex CLI disponible, autenticación y
acceso al servicio. Las consultas y utilidades locales usan biblioteca estándar; la revisión local
usa Git y las evaluaciones indicadas requieren además Podman rootless.
El entorno documentado es Linux con Python 3.12; no se afirma compatibilidad
comprobada con todos los sistemas. Consulta la
[guía de planificación](docs/planificacion-proyectos.md) y las
[políticas de entorno y credenciales](docs/credenciales-y-entornos.md).

## Resultados reales y simulados

| Evidencia | Qué se observó |
| --- | --- |
| [Benchmark multicaso](evals/resultados-multicaso-2026-10-15.md) y [revisor](evals/revisor/resultados-2026-10-16.md) | Ejecuciones reales acotadas: aprobaciones y detección de defectos; sus informes delimitan lo comprobado. |
| [Tareas de producto](docs/cierre-v1.md#recorridos-de-producto) | CSV, reservas, núcleo y lotes con incorporaciones autorizadas; también recorridos detenidos y correcciones asistidas, conservados como tales. |
| [Planificación con referencias, 25/10/2026](docs/cierre-v1.md#demostración-real-de-planificación-con-referencias) | Un borrador identifica código existente y propone una extracción limitada. No implementa ni aprueba el refactor. |
| [Validación integrada y CI existentes](docs/cierre-v1.md#validación-reutilizada) | 768 métodos correctos; agentes simulados en las pruebas del controlador, procesos de evaluación reales. |
| [Preparación local v1.1: integrada desde la terminal del usuario](docs/preparacion-tareas.md#integrada-aportada-desde-la-terminal) | 791 métodos en 296,344 s de unittest, código 0; identidades, canales y árbol conservado cotejados. Enfocadas, compatibilidad y demos documentadas por separado. |
| [CI de la PR #31, base de v1.2.0](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43710632676) | 873 métodos ordinarios: 860 correctos y 13 opt-in omitidos; en otro job, 13 integraciones reales de Podman correctas, sin omisiones. Agentes sintéticos, sin llamadas a modelos. |
| [Demo del inspector](examples/inspect_run/README.md) | Registros estáticos sintéticos; sus cifras no se suman a las pruebas ejecutadas. |

Los ejemplos sintéticos y las pruebas del controlador permiten comprobar
transiciones y formatos; no miden la calidad general de un modelo. Los casos
reales son observaciones concretas, no una tasa representativa de éxito.

<a id="ampliación-a-ambos-casos-15-de-octubre-de-2026"></a>

El [historial multicaso](docs/historial.md#experimento-multicaso-del-15-de-octubre)
y el [recorrido técnico anterior](docs/recorrido-v1.md) conservan los detalles,
recuentos y enlaces originales, incluidos los resultados fallidos.

## Intervención humana y límites

Una persona sigue teniendo que definir la tarea y su alcance, preparar y revisar
contratos y evaluadores, resolver preguntas y supuestos, autorizar las llamadas
y examinar la entrega antes de incorporarla. El planificador no convierte su
borrador en una configuración ejecutable aprobada. Un dictamen favorable del
revisor y unas pruebas correctas tampoco sustituyen esa decisión humana.

La v1 admite tareas Python delimitadas y biblioteca estándar; no demuestra
autonomía general ni corrección para todas las entradas. Las pruebas de los
recorridos indicados usan la frontera Podman documentada; esa garantía no se
extiende a los agentes, los runners directos ni todo comando del repositorio.
Las cuotas de resultados, stdout y stderr son **por evaluación**, sin presupuesto
global para el archivo de registros o las ejecuciones concurrentes.
Los [límites del entorno](docs/credenciales-y-entornos.md) y los
[límites concretos del aislamiento](docs/aislamiento-evaluador-python.md) delimitan
lo comprobado. Leer un registro histórico no acredita aislamiento retroactivo.

## Uso desde la raíz del proyecto

Empieza por la demo sin modelo. Para otras operaciones, utiliza la guía de su vía:

- [Planificación, referencias y continuaciones](docs/planificacion-proyectos.md).
- [Preparación local de tareas desde planes](docs/preparacion-tareas.md).
- [Revisión de diff Python o snapshot C++](docs/revision-diff.md).
- [Evaluación aislada con Podman rootless](docs/aislamiento-evaluador-python.md).
- [Evaluación, reparación, revisión y orquestación del benchmark](docs/funcionamiento.md).
- [Orquestación de proyectos](docs/orquestacion-proyectos.md) y [preparación de tareas](docs/tareas-configurables.md).
- [Inspector de proyectos y exportación](docs/inspector-proyectos.md).
- [Historial y mapa de informes](docs/historial.md), [detalle técnico anterior](docs/recorrido-v1.md) y [revisión de publicación](docs/revision-publicacion.md).

El [workflow de CI](.github/workflows/tests.yml) ejecuta `tests` en PR contra
`main` y pushes a `main`. En todas las PR contra `main`, también en borrador y
con cambios solo documentales, ejecuta **Integración real de Podman rootless**:
prepara la imagen, comprueba la sonda y exige las 13 integraciones sin omisiones.
Este segundo job se omite en pushes a `main`. Ambos funcionan sin modelos ni
secretos personales. Cada resultado acredita su propio árbol; no se deduce de
otra ejecución ni convierte automáticamente los checks en obligatorios para un merge.

**`runs/` permanece fuera de Git.** Contiene registros locales y no es necesario
para la demo ni para las pruebas automatizadas. Los documentos publicados
resumen la evidencia y sus límites sin incorporar esos registros privados.

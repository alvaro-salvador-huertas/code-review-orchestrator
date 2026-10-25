# code-review-orchestrator

**v1: orquestación supervisada para tareas Python acotadas.** El proyecto aborda
cómo evaluar y revisar cambios propuestos por agentes con criterios explícitos,
un presupuesto limitado y evidencia de cada decisión. Separa la generación de
código, las pruebas independientes, el dictamen de revisión y el control del flujo.

Incluye dos ejercicios de reparación, tareas de proyecto configurables, un
planificador de borradores y herramientas para consultar registros. Trabaja con
copias y conserva candidatos, informes y fallos. La incorporación al producto
requiere autorización humana; superar el flujo no aplica el cambio automáticamente.

El [cierre de la v1](docs/cierre-v1.md) fija el alcance y sus límites. Las
[notas para v1.0.0](docs/notas-v1.0.0.md) están preparadas; todavía no se ha creado
el tag ni la release.

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
| Evaluar un caso con `run_case.py`. | No; sí ejecuta pruebas en copias. |
| Crear un plan o continuarlo con `--answers` o `--decisions`. | Sí. |
| Lanzar desarrollo, revisión u orquestación de casos o proyectos. | Sí, al alcanzar la etapa correspondiente. |

Las operaciones con modelos necesitan Codex CLI disponible, autenticación y
acceso al servicio. Las consultas y utilidades locales usan biblioteca estándar.
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
autonomía general ni corrección para todas las entradas. Las copias, los hashes
y los límites de tiempo no son aislamiento para código arbitrario no confiable.
Los [límites del entorno](docs/credenciales-y-entornos.md) se aplican también a
los procesos de evaluación. Las ampliaciones futuras quedan fuera de este cierre.

## Uso desde la raíz del proyecto

Empieza por la demo sin modelo. Para otras operaciones, utiliza la guía de su vía:

- [Planificación, referencias y continuaciones](docs/planificacion-proyectos.md).
- [Evaluación, reparación, revisión y orquestación del benchmark](docs/funcionamiento.md).
- [Orquestación de proyectos](docs/orquestacion-proyectos.md) y [preparación de tareas](docs/tareas-configurables.md).
- [Inspector de proyectos y exportación](docs/inspector-proyectos.md).
- [Historial y mapa de informes](docs/historial.md), [detalle técnico anterior](docs/recorrido-v1.md) y [revisión de publicación](docs/revision-publicacion.md).

El [workflow de CI](.github/workflows/tests.yml) ejecuta las pruebas del
controlador en PR contra `main` y pushes a `main`, sin modelos ni credenciales
personales. Cada resultado acredita su propio árbol; no se deduce de otra
ejecución ni convierte automáticamente los checks en obligatorios para un merge.

**`runs/` permanece fuera de Git.** Contiene registros locales y no es necesario
para la demo ni para las pruebas automatizadas. Los documentos publicados
resumen la evidencia y sus límites sin incorporar esos registros privados.

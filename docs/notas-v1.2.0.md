# Notas preparadas para v1.2.0

Al redactar estas notas, **el tag y la release v1.2.0 están pendientes de revisión
y publicación**. La última publicada al preparar este
cambio es [v1.1.0](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/releases/tag/v1.1.0).
La base revisada es `fdf1a46eea53dd827cef1bd4e282abd71d954e28`, merge de la
PR #31. Los cambios descritos se contrastaron con el tag `v1.1.0`
(`8e6415f117d1056f560801574297890d5ead9e17`), el código y el workflow.

## Cambios para el usuario

- [PR #25](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/25):
  extracción privada de la lectura de lotes en `booking_batch.py`. Conserva la
  interfaz, los diagnósticos, UTF-8 estricto, el rechazo de JSON inválido y la
  ausencia de resultados parciales. El refactor precede a la herramienta de revisión.
- [PR #26](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/26):
  `review_diff.py` prepara revisión de 1–3 archivos Python modificados entre dos
  commits locales, o de 1–3 fuentes C++ (`.cpp`, `.h`, `.hpp`) de un snapshot.
  Usa SHA completos, archivos explícitos y 1–5 criterios. El diff no admite altas,
  bajas ni renombrados; no incluye el índice ni cambios sin commit. El snapshot
  no compila ni ejecuta C++. Por defecto produce una vista previa JSON sin modelo,
  pruebas ni dictamen. `--invoke-model` junto con `--output` nuevo solicita una
  revisión Codex explícita, con los textos completos seleccionados, una sesión
  de solo lectura y una invocación de hasta 180 s. Comprobar las citas del informe
  no acredita la corrección de sus conclusiones. Véanse los
  [ejemplos y límites](revision-diff.md).
- [PR #27](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/27):
  frontera común Podman rootless para inventario dinámico y evaluación de
  `orchestrate_project.py`, incluidos tareas configurables, varios archivos y
  evaluaciones iniciales/posteriores. Introduce también cuotas de salida durante
  la escritura, bloqueo de montajes automáticos, verificación de `cpu.max` y las
  correcciones de preparación parcial del volumen y recogida de informes.
- [PR #28](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/28):
  job independiente de integración real rootless en todas las PR contra `main`,
  incluidas las documentales y en borrador. Empezó con diez integraciones; las
  tres ampliaciones siguientes elevaron el requisito a trece, sin omisiones.
- [PR #29](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/29):
  aceptación y regresión de `repair_project.py inspect-json`, tanto iniciales
  como posteriores, usan la misma frontera y validan su evidencia antes de
  clasificar los informes. No cambia la autorización para invocar al agente.
- [PR #30](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/30):
  `run_case.py` ejecuta descubrimiento y unittest en Podman. CLI 0 significa
  evaluación terminada y registrada, incluso con código 1 de unittest por
  aserciones o errores de prueba; `codigo_salida_pruebas` conserva esa distinción.
  Runtime/arranque/protección fallidos o timeout producen CLI 1 y código de
  pruebas desconocido (`null`). Si las pruebas terminaron pero falla publicar
  su registro, se conserva el código conocido y la CLI falla.
- [PR #31](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/31):
  `repair_case.evaluate()` aísla descubrimiento y pruebas también desde la
  reparación directa, `orchestrate_case.py` y `evaluate_reviewer.prepare()`.
  Los lectores verifican evidencia nueva, bytes congelados y continuidad antes
  de autorizar la siguiente etapa. Las aserciones fiables conservan su significado;
  los fallos de infraestructura impiden acreditar la evaluación o invocar al agente.

La preparación local de tareas desde planes sigue disponible desde v1.1.0.
El [README](../README.md) ofrece tres comienzos: demo sin modelo, vista previa
de revisión y preparación/sonda del runtime.

## Requisitos, alcance y límites

Las evaluaciones indicadas requieren Linux, Podman rootless local, rangos
subuid/subgid, un runtime OCI con seccomp y cgroups v2 con CPU, memoria, swap y
procesos delegados. Ubuntu 24.04.5 con Podman 4.9.3 está comprobado; no se afirma
compatibilidad con todos los sistemas. La [guía del evaluador](aislamiento-evaluador-python.md)
incluye los paquetes oficiales, diagnósticos y antecedentes. Se conservan las
protecciones del sistema; no se resuelven fallos desactivando AppArmor o seccomp.
Podman 4.9.3 rootless no aplica un perfil AppArmor adicional al contenedor;
el workflow comprueba el módulo del anfitrión activo y no lo desactiva.

`python3 -B python_evaluator.py prepare`, como el usuario del controlador,
descarga por separado la imagen oficial Python 3.12.16-bookworm, fijada por digest:

```text
docker.io/library/python@sha256:4209fae09a3e20afd863e528bfddc235da5fd5977983e1996cd54cc9a72e6267
```

`python3 -B python_evaluator.py check` ejecuta una sonda real. Cada evaluación
comprueba las protecciones dentro de su propio contenedor antes de importar
código del proyecto: UID no root, capacidades efectivas vacías, `NoNewPrivs`,
seccomp, solo loopback y límites efectivos del mismo cgroup, incluido
`0 < cuota CPU <= periodo`. El inventario y el descubrimiento también importan
código y por ello entran en la frontera. No hay alternativa en el anfitrión si
faltan runtime, imagen o controles, o si Podman rechaza el arranque.

La ejecución usa red deshabilitada, `--pull=never`, entradas mínimas de solo
lectura y ningún HOME personal, credencial o socket del anfitrión. La opción
global `--default-mounts-file=/dev/null`, antes de `run`, bloquea montajes
automáticos incluso desde el HOME real. El contenedor tiene raíz de solo
lectura, namespaces privados, una CPU, 512 MiB de memoria, swap adicional cero,
128 procesos y `/tmp` efímero de 128 MiB. Se conservan los plazos de cada vía:
30 s para casos, 60/180 s para aceptación/regresión de `repair_project`, y los
límites de la tarea para la orquestación de proyectos.

El presupuesto de salida es **por evaluación**: resultados en tmpfs de
**32 MiB y 1024 inodos**, copia agregada de archivos regulares de hasta 32 MiB,
y **4 MiB de stdout y 4 MiB de stderr**, incluidos los diagnósticos del canal.
Se limita durante la escritura; no depende de medir después. Un exceso detiene
la evaluación y se registra; una recogida incompleta o estructura inválida
no acredita el informe. Los tamaños admiten los informes habituales sin dejar
crecimiento ilimitado. No son una cuota global del archivo `runs/`, de las
ejecuciones concurrentes ni de todo I/O acumulado. Tmpfs puede usar swap del
anfitrión; el monitor no audita cada error de escritura que el candidato capture.

Timeout conserva su diagnóstico. Se retira el contenedor por su nombre concreto
y se comprueba su ausencia; se intenta desmontar y retirar el volumen sin forzar
contenedores, incluso tras preparación parcial, y se comprueba su ausencia.
Se conserva la causa original y se registran aparte fallos de limpieza, que
invalidan la evaluación. No se usa limpieza global. Una interrupción abrupta
del anfitrión puede requerir retirar los recursos concretos manualmente.

Quedan fuera los runners invocados directamente (`project_test_runner.py`,
`project_flow_runner.py`, `project_test_inventory.py`), `evals/**/evaluar.py`,
unittest/scripts manuales y la vía histórica de reevaluación conservada de
proyectos descrita en la guía. Las llamadas a agentes conservan su política
Codex; esta frontera no convierte todas las operaciones del repositorio en
ejecuciones Podman. **La incorporación de cambios sigue siendo decisión humana.**

## Compatibilidad y evidencia

Se mantienen interfaces, identificadores, criterios, formatos de informes válidos
y comprobaciones de integridad. Los registros nuevos añaden marcadores y
procedencia compatibles (`version_evaluacion: 2` y sello de aislamiento), con
comando, imagen, montajes, cuotas y limpieza. Esas versiones de formato no son
la versión semántica de la release. Los lectores rechazan evidencia nueva
ausente o incoherente; no aceptan quitar un sello para simular un registro antiguo.
Los registros históricos admitidos siguen sus comprobaciones originales: su
lectura no ejecuta materiales ni acredita aislamiento retroactivo. La evidencia
local no es una firma criptográfica frente a su reescritura íntegra.

La suite ordinaria cubre contratos, transiciones y fallos con agentes y runtimes
simulados en fixtures explícitos. Sus omisiones opt-in no acreditan contenedores.
El job **Integración real de Podman rootless** prepara la imagen, ejecuta `check`
y exige exactamente 13 métodos reales sin omisiones. Comprueba candidatos válidos,
red/señuelos y montajes bloqueados, timeout, cuotas por canal y resultados,
recogida inválida, limpieza y las CLI de producción migradas. Usa datos y agentes
sintéticos, no modelos; no demuestra calidad general de un agente.

| Hito y SHA comprobado | Evidencia enlazada |
| --- | --- |
| PR #27, `f85c5c4` | [CI ordinaria](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43446261444); diez integraciones reales **locales** en 33.474 s, documentadas en la guía. Aún no había job real en CI. |
| PR #28, `b7176a5` | [CI](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43615722281): 834 correctas + 10 omitidas ordinarias; 10/10 reales en 35.866 s. |
| PR #29, `8e30d7c` | [CI](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43620396382): 844 correctas + 11 omitidas ordinarias; 11/11 reales en 40.445 s. |
| PR #30, `a1d8478` | [CI](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43705087242): 851 correctas + 12 omitidas ordinarias; 12/12 reales en 53.601 s. |
| PR #31, `0e0dfdf` | [tests](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43710632676/job/132801184557): **873 métodos, 860 correctos y 13 omitidos** en 294.393 s. [Podman real](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/43710632676/job/132801184810): **13/13**, cero omisiones, 41.284 s, sin contenedores ni volúmenes residuales. |

Esas cifras corresponden a los SHA de cada PR, no se atribuyen al futuro tag.
El [workflow](../.github/workflows/tests.yml) ejecuta ambos jobs en las PR contra
`main`, también documentales; en pushes a `main` solo ejecuta la suite ordinaria.
Fija las acciones por SHA, usa checkout sin credenciales persistentes y permisos
de lectura. No publica tags ni releases automáticamente. El cuerpo de la PR de
preparación conserva los resultados y enlaces de su propio SHA publicado.

Durante esta preparación se verificaron la demo en texto y JSON (incluidos sus
códigos 0/1), la vista previa Python del README y un snapshot C++ sintético, sin
invocar modelos, y las diez pruebas enfocadas de revisión con fixtures. La sonda
local real terminó con código 0 y limpieza confirmada. No se observaron fallos
de implementación en esos recorridos. Los [pasos de publicación](publicacion-v1.2.0.md)
dejan el tag y la release para después del merge revisado.

# Aislamiento del evaluador Python (primera PR)

El recorrido de `orchestrate_project.py` usa Podman **rootless local** para todas
las etapas que ejecutan Python del proyecto: inventario dinámico de la base
(`inventory_base`) y evaluación inicial/posterior (`evaluate_flow`, incluidas
aceptación, regresión, hallazgos y anidamiento). Se aplica también a las tareas
configurables y a las entregas con varios archivos.

`unittest.discover()` importa módulos, ejecuta su inicialización y puede invocar
`load_tests`; no basta con aislar los métodos de prueba. Por eso el proceso
completo de `project_test_inventory.py` entra en el contenedor desde
`inventory_base`, antes de disponer de un candidato. El descubrimiento de la
regresión dentro de `project_flow_runner.py` también queda dentro. La extracción
de blobs Git y el inventario estático por AST no importan código del proyecto.

## Preparación separada de la evaluación

Se necesita Linux, cgroups v2 con controladores de memoria, swap, CPU y procesos
delegados al usuario, un runtime OCI con seccomp y Podman rootless. En Ubuntu:

```sh
sudo apt-get update
sudo apt-get install podman uidmap crun slirp4netns fuse-overlayfs
id
cat /etc/subuid /etc/subgid
podman info --format json
python3 -B python_evaluator.py prepare
python3 -B python_evaluator.py check
```

El administrador debe configurar rangos no solapados de subuid/subgid si no
existen y una sesión de usuario con delegación de cgroups. `newuidmap` y
`newgidmap` deben estar correctamente instalados por el sistema. No ejecutar el
controlador con `sudo`. En Ubuntu 24.04, comprobar también los diagnósticos de
AppArmor si el paquete/perfil del runtime no permite crear namespaces. Un fallo
no se resuelve desactivando seccomp, AppArmor o los límites en el controlador.

`prepare` es la única operación que descarga capas. Debe ejecutarse como el
mismo usuario y con el mismo `XDG_DATA_HOME` que la evaluación. Usa la imagen
Docker Official Image Python **3.12.16-bookworm**, fijada al índice OCI:

```text
docker.io/library/python@sha256:4209fae09a3e20afd863e528bfddc235da5fd5977983e1996cd54cc9a72e6267
```

El digest se consultó en el registro oficial el 11 de noviembre de 2026. Se usa
la variante bookworm que incluye Git para las pruebas existentes que crean
repositorios sintéticos; no se instala nada durante las evaluaciones. No se
aceptan tags flotantes ni imágenes configurables desde una tarea. Una
actualización de imagen requiere cambiar el digest en código y repetir las
integraciones. La preparación no hereda autenticación de registros privados.

`check` arranca una sonda con los mismos controles que la evaluación. Cada
invocación vuelve a comprobar el runtime y ejecuta esa sonda dentro del propio
contenedor **antes de importar los materiales del proyecto**. Comprueba UID no
root, capacidades efectivas vacías, `NoNewPrivs`, seccomp activo, ausencia de
interfaces externas y los valores efectivos de `memory.max`, `memory.swap.max`
y `pids.max`. Una advertencia del runtime que implique límites ignorados no
permite ejecutar el candidato. Runtime ausente, imagen ausente, arranque fallido
o controles inefectivos detienen el flujo con código 3 y diagnóstico; nunca se
invoca Python del candidato en el anfitrión como alternativa.

## Controles y materiales

- Red `none`, descarga `never`, cliente local (`--remote=false`), sin proxies.
- Usuario no root mediante `keep-id`, sin capacidades adicionales,
  `no-new-privileges`, seccomp predeterminado y namespaces privados de procesos,
  IPC, UTS y cgroups.
- Raíz de imagen de solo lectura, `/tmp` efímero de 128 MiB, memoria de 512 MiB,
  swap adicional cero, 128 procesos y una CPU. El límite de tiempo de cada etapa
  conserva el valor de la tarea.
- Solo se montan la copia de proyecto, el runner congelado cuando procede y las
  autoridades de prueba congeladas, todos de solo lectura. Se conservan las
  rutas absolutas para no cambiar los contratos de pruebas ni la procedencia.
- La salida tiene un montaje temporal independiente de escritura. El contenedor
  no ve los registros del controlador. Tras detenerlo se recogen únicamente
  `pruebas.json`, su temporal `pruebas.tmp` y `consultas/`, rechazando enlaces y
  archivos especiales. Stdout y stderr los captura el anfitrión por separado.
- El HOME del candidato está en `/tmp/home`. El entorno interno es una lista
  cerrada y no recibe credenciales, HOME personal, directorios de configuración,
  repositorios ajenos, sockets de agentes ni sockets Podman/Docker del anfitrión.
  La CLI Podman recibe HOME y rutas de almacenamiento/runtime del usuario para
  operar rootless, pero esas rutas **no se montan** en el contenedor. Usa
  configuración efímera sin montajes automáticos, hooks ni credenciales.

Cada ejecución tiene un nombre `cro-eval-<uuid>`. Tras éxito, fallo, timeout o
interrupción, el controlador ejecuta `podman rm --force --time=0 --ignore` sobre
ese nombre y comprueba que `container exists` devuelve 1. Si no puede confirmar
la limpieza, se detiene y conserva el diagnóstico. No usa limpiezas globales
como `prune`. En un timeout conserva `tiempo_agotado` (código 4), la salida
parcial y el nombre de ejecución. Una terminación no capturable del controlador
(por ejemplo SIGKILL o apagado del anfitrión) requiere limpieza administrativa;
los nombres registrados permiten identificar esas ejecuciones.

Se mantienen las identidades de pruebas, recuentos, clasificación, informes,
hashes y sellos de integridad del controlador. `resultado.json` añade la imagen,
el nombre del contenedor, el comando de runtime, el origen temporal de salida y
la confirmación de limpieza. La validación comprueba además que los controles y
montajes registrados son los esperados. Los registros anteriores sin esa
procedencia no acreditan aislamiento y no se convierten retroactivamente.
`lista_para_revision_humana` sigue siendo una propuesta: no hay incorporación
automática y la aprobación humana continúa siendo necesaria.

## Pruebas y evidencia de validación

```sh
python3 -B -m unittest discover -s tests -v
CRO_REAL_PODMAN=1 python3 -B -m unittest discover -s tests -p test_python_isolation_real.py -v
```

La suite ordinaria sustituye explícitamente la frontera en los fixtures
sintéticos mediante `tests/evaluator_stub.py`, también en sus copias privadas
de la CLI. **Es ejecución simulada del aislamiento**, aunque las pruebas de
criterios e integridad se ejecutan de verdad. Producción no tiene flag, variable
de entorno ni opción para activar esa sustitución.

Las pruebas unitarias específicas comprueban runtime ausente, rechazo de
arranque, límites inefectivos, limpieza y salida hostil. Incluyen candidatos con
marcador de ejecución en el anfitrión y una importación hostil durante el
inventario. En ambos puntos el controlador se detiene antes de ejecutar el
proyecto cuando no puede aplicar el aislamiento.

Las cuatro integraciones opt-in usan Podman real, sin sustituirlo: recorrido
completo de un candidato válido con agentes sintéticos; señuelo fuera de
montajes y destino TCP loopback controlado con datos sintéticos; timeout con
hijo y comprobación de ausencia del contenedor y del proceso; inventario con
importación que intentaría escribir fuera de los montajes. Cuando se habilitan,
un runtime roto produce **fallos**, no skips silenciosos.

### Antecedente: sesión inicial del 11 de noviembre de 2026

En la sesión inicial, Ubuntu 24.04.5 no tenía Podman ni uidmap instalados.
`sudo -n` exigía contraseña. Se descargaron paquetes oficiales en `/tmp`, sin
instalación global, y se ejecutó Podman 4.9.3 fuera del sandbox de la sesión.
Falló ya en `podman info`, antes de descargar/preparar la imagen y del arranque:

```text
newuidmap: write to uid_map failed: Operation not permitted
Error: cannot set up namespace using ".../newuidmap": exit status 1
```

Los helpers extraídos pertenecían al usuario y no equivalían a los helpers
privilegiados instalados por Ubuntu. Aunque el sysctl
`kernel.apparmor_restrict_unprivileged_userns` valía 1, este diagnóstico por sí
solo **no demuestra** que AppArmor sea la causa. No se modificaron sysctls ni
perfiles. En aquel intento, las cuatro integraciones reales quedaron bloqueadas
por ese fallo; no acreditaban el candidato válido, el señuelo, la red ni la
limpieza tras timeout. La negativa a ejecutar sin runtime sí se verificó, además
de sus pruebas simuladas. Este fallo queda como antecedente del entorno inicial;
la validación posterior desde la terminal normal sí pasó, como se detalla abajo.

La suite se ejecutó fuera del sandbox de la sesión porque este bloqueaba los
sockets de loopback de pruebas HTTP existentes. También se encontró
`booking_batch.py` con permisos locales 0664; se normalizó a 0644, como exige
su aceptación, sin cambiar el contenido ni el modo Git 100644.

La pasada anterior se ejecutó en una copia estable bajo `/tmp`: **817 pruebas,
813 correctas y 4 integraciones opt-in omitidas; cero fallos**, en 299 segundos
aproximadamente. Incluía las 12 pruebas unitarias nuevas y 10 pruebas locales
preexistentes ajenas al commit. Por tanto, sus 813 pruebas correctas **no son el
recuento atribuible a la rama**. Los 185 archivos versionados de trabajo se
compararon byte a byte con la copia, sin diferencias. Una pasada concurrente
sobre el checkout había dado tres fallos de conservación por variaciones de
metadatos mientras se realizaban otras operaciones; la copia estable conservaba
las mismas comprobaciones sin esa interferencia.

En aquella sesión, las cuatro integraciones reales habilitadas explícitamente
fallaron en el preflight rootless descrito arriba. `prepare` y `check` con el
runtime ausente devolvieron código 1 y diagnóstico explícito.

### Integración real verificada desde la terminal normal

El 13 de noviembre de 2026 se confirmó en **Ubuntu 24.04.5 con Podman rootless
4.9.3**, desde una terminal normal, el siguiente resultado sobre un worktree
limpio del commit de implementación
`18d70b48366b81c0853bc183d962e0bbd601fa57`:

```sh
python3 -B python_evaluator.py prepare
python3 -B python_evaluator.py check
CRO_REAL_PODMAN=1 python3 -B -m unittest discover -s tests -p test_python_isolation_real.py -v
```

`prepare` y `check` terminaron correctamente. Las **cuatro integraciones reales
pasaron en 18.049 s**, sin omisiones. Este es el resultado verificado desde la
terminal normal aportado para esta revisión; se distingue del intento previo
en el entorno de la sesión.

| Integración real | Resultado |
| --- | --- |
| Candidato válido: orquestación completa e informe para revisión humana | Correcto |
| Señuelo fuera de montajes y conexión a destino loopback controlado | Inaccesible / bloqueada |
| Timeout: diagnóstico, sin contenedor ni proceso descendiente activo | Correcto |
| Inventario: importación sin escribir el marcador en el anfitrión | Correcto |

El fallo previo de `newuidmap` no describe el resultado de esta ejecución
posterior: el runtime instalado y ejecutado desde la terminal normal sí permitió
aplicar los controles del commit. La suite ordinaria mantiene las sustituciones
explícitas de sus fixtures y debe distinguirse de esta integración real.

### Suite ordinaria atribuible a la rama

El 13 de noviembre de 2026 se ejecutó la suite ordinaria desde un **worktree
limpio del commit `18d70b48366b81c0853bc183d962e0bbd601fa57`**, creado con
`umask 022` para respetar los modos 0644 exigidos por las pruebas existentes:

```sh
umask 022
git worktree add --detach /tmp/python-evaluator-pr-review-20261113 18d70b48366b81c0853bc183d962e0bbd601fa57
cd /tmp/python-evaluator-pr-review-20261113
env -u CRO_REAL_PODMAN python3 -B -m unittest discover -s tests -v
git status --porcelain
```

Resultado: **807 pruebas descubiertas, 803 correctas y 4 integraciones reales
opt-in omitidas; cero fallos y cero errores**, en **299.865 s**. Se incluyen las
12 pruebas unitarias específicas del aislamiento. El worktree estaba limpio
antes y después de la ejecución; no contenía los cuatro archivos locales sin
seguimiento. La suite se ejecutó fuera del sandbox de la sesión para permitir
los sockets de loopback de sus pruebas HTTP.

Este es el recuento atribuible a la rama: las 10 pruebas locales ajenas que
inflaban la pasada anterior de 813 pruebas correctas están excluidas. Las
cuatro omisiones de esta suite ordinaria corresponden a las integraciones
opt-in; su ejecución real satisfactoria en 18.049 s se registra por separado
arriba. Esta actualización posterior al commit probado cambia únicamente la
documentación, sin modificar la implementación ni las pruebas.

### Revisión del diff contra `main`

Se revisaron las llamadas desde `orchestrate_project.py`, la frontera de
`python_evaluator.py`, su política de entorno y las pruebas del diff respecto
a `main`. No se detectaron hallazgos bloqueantes dentro del alcance de esta PR:

- `inventory_base()` y `evaluate_flow()` invocan `run_isolated()`. Tanto el
  descubrimiento que importa módulos como los procesos de las pruebas quedan
  dentro de Podman; la lectura de Git y el análisis estático no importan código
  del proyecto.
- El preflight y la sonda preceden a la ejecución del proyecto. Los errores del
  runtime o de los controles detienen el flujo; las pruebas de fallo comprueban
  que no aparece el marcador de ejecución en el anfitrión. No hay alternativa de
  ejecución local en producción.
- Los montajes de entrada son de solo lectura y la única salida de escritura es
  temporal. La recogida valida los nombres permitidos y rechaza enlaces y
  archivos especiales; stdout, stderr y los registros del controlador quedan
  fuera de ese montaje.
- La limpieza usa el nombre único de la ejecución, fuerza su retirada y verifica
  su ausencia. La recogida normal de resultados sucede después de esa limpieza;
  los fallos e interrupciones conservan la vía de limpieza y el diagnóstico.
- Se conservan los criterios, los sellos de integridad y la aprobación humana.
  Las sustituciones del runtime están limitadas a los fixtures de la suite
  ordinaria; las cuatro integraciones habilitadas usan el contenedor real.

## Fuera de esta primera PR

No se aíslan las invocaciones directas de `repair_project.py`,
`project_test_runner.py`, `project_flow_runner.py`, `project_test_inventory.py`,
los evaluadores `evals/**/evaluar.py`, ni los recorridos de casos
`run_case.py`, `repair_case.py`, `orchestrate_case.py` y `evaluate_reviewer.py`.
Tampoco la ejecución manual de `unittest`/scripts ni los agentes de desarrollo y
revisión, que conservan su política Codex. Los lectores y planificadores no
pasan a ejecutar candidatos por este cambio. La protección aquí descrita se
aplica al inventario y evaluación iniciados desde `orchestrate_project.py`.

Referencias: [Podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
[preparación rootless](https://github.com/podman-container-tools/podman/blob/main/docs/tutorials/rootless_tutorial.md),
[Dockerfile oficial Python](https://github.com/docker-library/python/blob/3d7e95597e56a415d9e4abc0f15877e005d2cb2e/3.12/bookworm/Dockerfile).

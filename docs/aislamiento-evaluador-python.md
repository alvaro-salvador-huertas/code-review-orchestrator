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
y `pids.max`, además de `cpu.max` en ese mismo cgroup. La cuota de CPU debe
ser finita y cumplir `0 < cuota <= periodo` antes de ejecutar el candidato.
Una advertencia del runtime que implique límites ignorados no
permite ejecutar el candidato. Runtime ausente, imagen ausente, arranque fallido
o controles inefectivos detienen el flujo con código 3 y diagnóstico; nunca se
invoca Python del candidato en el anfitrión como alternativa.

## Controles y materiales

- Red `none`, descarga `never`, cliente local (`--remote=false`), sin proxies.
- Montajes automáticos desactivados con la opción global
  `--default-mounts-file=/dev/null`, situada antes de `run`. Podman 4.9.3 busca
  `mounts.conf` en el HOME real aunque `XDG_CONFIG_HOME` sea temporal. Por eso
  no se crea un `mounts.conf` temporal como protección. Si el runtime rechaza
  la opción, el flujo se detiene; no se reintenta quitándola.
- Usuario no root mediante `keep-id`, sin capacidades adicionales,
  `no-new-privileges`, seccomp predeterminado y namespaces privados de procesos,
  IPC, UTS y cgroups.
- Raíz de imagen de solo lectura, `/tmp` efímero de 128 MiB, memoria de 512 MiB,
  swap adicional cero, 128 procesos y una CPU. El límite de tiempo de cada etapa
  conserva el valor de la tarea.
- Solo se montan la copia de proyecto, el runner congelado cuando procede y las
  autoridades de prueba congeladas, todos de solo lectura. Se conservan las
  rutas absolutas para no cambiar los contratos de pruebas ni la procedencia.
- Los resultados tienen un volumen tmpfs privado de 32 MiB y 1024 inodos; no
  hay un bind de salida al disco del anfitrión. Stdout y stderr se capturan por
  pipes, con un máximo de 4 MiB cada uno. El contenedor no ve los registros del
  controlador. Tras detenerlo se recogen únicamente
  `pruebas.json`, su temporal `pruebas.tmp` y `consultas/`, rechazando enlaces y
  archivos especiales y con otro presupuesto agregado durante la copia.
- El HOME del candidato está en `/tmp/home`. El entorno interno es una lista
  cerrada y no recibe credenciales, HOME personal, directorios de configuración,
  repositorios ajenos, sockets de agentes ni sockets Podman/Docker del anfitrión.
  La CLI Podman recibe HOME y rutas de almacenamiento/runtime del usuario para
  operar rootless, pero esas rutas **no se montan** en el contenedor. Usa
  configuración efímera sin hooks ni credenciales. La opción global de Podman
  impide los montajes automáticos, conservando el almacenamiento rootless.

Cada ejecución tiene un nombre `cro-eval-<uuid>`. Tras éxito, fallo, timeout o
interrupción, el controlador ejecuta `podman rm --force --time=0 --ignore` sobre
ese nombre y comprueba que `container exists` devuelve 1. Después de recoger
los resultados, desmonta y elimina el volumen privado y comprueba también su
ausencia. Si no puede confirmar
la limpieza, se detiene y conserva el diagnóstico. No usa limpiezas globales
como `prune`. En un timeout conserva `tiempo_agotado` (código 4), la salida
parcial y el nombre de ejecución. Una terminación no capturable del controlador
(por ejemplo SIGKILL o apagado del anfitrión) requiere limpieza administrativa;
los nombres registrados permiten identificar esas ejecuciones.

Se mantienen las identidades de pruebas, recuentos, clasificación, informes,
hashes y sellos de integridad del controlador. `resultado.json` añade la imagen,
el nombre del contenedor, el comando de runtime, la identidad y cuotas del
volumen, los bytes capturados y la confirmación de limpieza de ambos recursos.
La evidencia de aislamiento usa ahora versión 2. La validación comprueba además que los controles y
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

Las diez integraciones opt-in usan Podman real, sin sustituirlo: recorrido
completo de un candidato válido con agentes sintéticos; señuelo fuera de
montajes y destino TCP loopback controlado con datos sintéticos; timeout con
hijo y comprobación de ausencia del contenedor y del proceso; inventario con
importación que intentaría escribir fuera de los montajes; HOME temporal con
un montaje automático sintético que el evaluador debe bloquear; excesos separados
de resultados, stdout y stderr; exceso agregado entre varios archivos; e informe
normal con cuotas pequeñas. Cuando se habilitan,
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

### Antecedente: cuatro integraciones originales desde la terminal normal

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

### Antecedente: suite ordinaria del commit original

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

Este era el recuento atribuible al commit original: las 10 pruebas locales ajenas que
inflaban la pasada anterior de 813 pruebas correctas están excluidas. Las
cuatro omisiones de esta suite ordinaria corresponden a las integraciones
opt-in; su ejecución real satisfactoria en 18.049 s se registra por separado
arriba. Esta actualización posterior al commit probado cambia únicamente la
documentación, sin modificar la implementación ni las pruebas.

### Antecedente: revisión inicial del diff contra `main`

Se revisaron las llamadas desde `orchestrate_project.py`, la frontera de
`python_evaluator.py`, su política de entorno y las pruebas del diff respecto
a `main`. En esa revisión inicial no se detectaron hallazgos bloqueantes. Una
revisión posterior identificó la dependencia del HOME real para los montajes
automáticos y la ausencia de comprobación de `cpu.max`; la versión corregida
que se describe a continuación aborda ambos problemas. La revisión inicial
comprobó los siguientes aspectos:

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


## Versión corregida: montajes automáticos y CPU efectiva

Se trabaja en la rama `fix/python-evaluator-mounts-cpu`, desde un worktree
separado creado con `umask 022` a partir de `a720590`. Se incorporó
`origin/main` (`52c73c9`, PR #26) mediante el merge `14f6b1b`, sin rebase ni
reescritura del historial. Los cuatro nombres que estaban sin seguimiento en
el checkout original ahora están versionados desde main en este worktree; no
se copiaron ni modificaron los archivos locales originales.

La corrección usa `--default-mounts-file=/dev/null` como opción global antes de
`run`, elimina el archivo `mounts.conf` temporal y comprueba la cuota efectiva
leyendo `cpu.max` en el mismo cgroup que la memoria y los procesos. La evidencia
registrada debe contener la opción global: quitarla o cambiarla invalida esa
evidencia. Las pruebas unitarias cubren el rechazo de la opción por el runtime,
cuota ilimitada, cuota superior a una CPU, valores no positivos y cuotas válidas.

La quinta integración configura exclusivamente un HOME temporal con
`.config/containers/mounts.conf` y un archivo señuelo sintético. Conserva
`XDG_DATA_HOME` del usuario habitual para acceder a la imagen ya preparada y
mantiene el directorio de runtime rootless. Primero ejecuta un lector de datos
sintéticos con los mismos límites y namespaces, retirando solo la opción global:
el señuelo debe aparecer en ese control. Después, el evaluador de producción
con la opción global debe impedir que ese montaje aparezca. Se verifica también
la limpieza y que la configuración temporal y el señuelo no se modificaron. No
se edita el HOME personal ni la configuración del sistema.

### Resultados reales de la versión corregida

El 13 de noviembre de 2026, en Ubuntu 24.04.5 con **Podman rootless 4.9.3 y
cgroups v2**, se ejecutaron desde el nuevo worktree limpio del commit de corrección
`bb1204164b0758ec04e793cfb1f08484da9af9dc`, como usuario habitual y fuera del
sandbox de la sesión, los siguientes comandos:

```sh
python3 -B python_evaluator.py check
CRO_REAL_PODMAN=1 python3 -B -m unittest discover -s tests -p test_python_isolation_real.py -v
```

`check` terminó con código 0, estado `finalizada`, sin error y con limpieza
confirmada. La imagen fijada ya estaba disponible en el almacén rootless; no
fue necesario ejecutar `prepare` ni descargarla de nuevo. Las **cinco
integraciones reales pasaron en 20.810 s**, sin fallos, errores ni omisiones:

| Integración real corregida | Resultado |
| --- | --- |
| Candidato válido: recorrido completo e informe para revisión humana | Correcto |
| Señuelo externo y destino TCP loopback controlado | Inaccesible / bloqueado |
| Timeout: diagnóstico y ausencia de contenedor y proceso descendiente | Correcto |
| Inventario: importaciones sin escribir el marcador en el anfitrión | Correcto |
| HOME temporal: control con montaje visible y evaluador con montaje bloqueado | Correcto |

Las 16 pruebas unitarias específicas también pasaron. Estas usan sustituciones
explícitas para probar los fallos y la sonda; se distinguen de las cinco
integraciones anteriores, que arrancaron contenedores reales. No se desactivaron
protecciones del sistema ni se relajaron los controles para obtener estos resultados.

### Suite ordinaria y comprobaciones del commit corregido

Desde el mismo worktree limpio en `bb1204164b0758ec04e793cfb1f08484da9af9dc`:

```sh
env -u CRO_REAL_PODMAN python3 -B -m unittest discover -s tests -v
git diff --check
git status --porcelain
```

La suite terminó en **290.566 s** con **822 pruebas descubiertas: 817 correctas
y 5 integraciones opt-in omitidas**, sin fallos ni errores. Incluye las **16
unitarias específicas** del evaluador y las **10 pruebas de la PR #26**, ahora
versionadas por main. Las cinco omisiones corresponden a las integraciones que
pasaron por separado con Podman real; no se cuentan como ejecución real en la
suite ordinaria.

El worktree estaba limpio antes y después de las pruebas. `git diff --check`
no encontró errores. Los archivos locales del checkout original conservaron su
contenido, modo y fecha de modificación, y ese checkout siguió en `a720590`.
El commit posterior de cierre añade únicamente estos resultados a la
documentación; no cambia los fuentes ni las pruebas verificadas. La rama queda
local, sin publicación ni apertura de PR.

### Antecedente: límite de disco pendiente en c25ea65

En `c25ea65` seguía pendiente imponer una cuota para resultados, stdout y stderr.
Los límites de memoria, CPU, procesos, tiempo y el tamaño de `/tmp` del contenedor
no fijaban un máximo para esas salidas. La ampliación siguiente sustituye esa
limitación conocida por los controles durante la escritura que se describen abajo.


## Ampliación local: salidas acotadas durante la escritura

Se partió del worktree limpio y del SHA publicado
`c25ea655bd18595fbc5fed7079553c34586f591e`. Esta ampliación se prepara solo en
local, sin subir commits ni cambiar el estado de borrador de la PR #27.

### Presupuestos y justificación

| Salida por evaluación | Límite predeterminado | Motivo |
| --- | --- | --- |
| Resultados del proyecto | 32 MiB de bloques tmpfs y 1024 inodos | Margen para el JSON de métodos/subtests y las consultas; impide crecer indefinidamente creando muchos archivos |
| Copia de resultados al registro | 32 MiB de datos regulares agregados | Impide amplificar archivos sparse o hardlinks al copiarlos al disco |
| Stdout | 4 MiB de bytes capturados | Margen para el inventario JSON y salidas normales, sin admitir un stream ilimitado |
| Stderr | 4 MiB de bytes capturados, incluidos los diagnósticos añadidos | Margen para unittest verboso y tracebacks; ningún diagnóstico permite saltarse el tope |

Son límites del controlador por etapa (inventario o suite), no un presupuesto
configurable por el candidato, variables de entorno o la tarea. Las pruebas
usan explícitamente presupuestos menores: 16 KiB para resultados y 1 KiB por
stream; el caso válido pequeño permite 4 KiB de stderr. Los tamaños de los
informes normales no cambian y sus bytes se copian sin reescritura.

### Aplicación efectiva

Antes de lanzar el candidato se crea un volumen local Podman con
`type=tmpfs`, `device=tmpfs` y opciones `size`, `nr_inodes`, `nodev` y `nosuid`.
Una referencia explícita mediante `podman unshare podman volume mount` mantiene
ese tmpfs disponible hasta terminar la recogida. Un helper de confianza, solo
con biblioteca estándar y Python `-I`, verifica el montaje en `mountinfo` y las
capacidades efectivas de bloques/inodos con `statvfs`. Si el runtime no puede
aplicarlas, se detiene la evaluación. No hay alternativa a un directorio de
salida sin cuota en el disco. Los montajes automáticos siguen bloqueados.

El **kernel limita cada asignación durante la escritura** en ese filesystem;
no se confía en medirlo después de ejecutar. Un monitor de confianza consulta
saturación y tamaño lógico cada 20 ms. Al detectar saturación, exceso lógico o
la pérdida del monitor, detiene la ejecución. La comprobación final del volumen
cierra la carrera entre el último sondeo y la salida del proceso. El monitor no
importa código del proyecto y recorre metadatos mediante descriptores, sin
seguir enlaces del candidato hacia el filesystem anfitrión.

Para stdout y stderr, el proceso Podman escribe en **pipes**, no directamente
en archivos del registro. El capturador solo escribe el prefijo que cabe en el
presupuesto de cada canal. El primer byte adicional provoca `limite_salida`,
la muerte del cliente y la limpieza forzada del contenedor y sus descendientes.
El exceso puede quedar en el pipe o en un bloque pequeño de memoria del
capturador; nunca se escribe en los archivos más allá de la cuota. Se mantiene
`--log-driver=none` para evitar otra copia sin tope del stream en los logs de Podman.

Después de detener y retirar el contenedor, la copia de resultados valida todo
el árbol antes de crear destinos: `pruebas.json` y `pruebas.tmp` deben ser archivos
regulares, y `consultas/`, si existe, un directorio. Rechaza enlaces y archivos
especiales y comprueba el presupuesto agregado antes de la primera copia;
además descuenta cada bloque escrito durante la copia. El volumen se desmonta, elimina y verifica
por nombre, incluso tras errores. `limpieza_confirmada` exige tanto contenedor
como volumen retirados. No se usa `prune` ni se modifica el HOME personal.

### Diagnósticos e informes parciales

El registro conserva `estado=limite_salida`, `salida_excedida` (resultados,
stdout o stderr), cuotas, uso final del volumen y bytes capturados. El
controlador se detiene con código 3 y estado global `fallo_tecnico` (compatible
con los lectores existentes), antes de validar o clasificar las pruebas;
un `pruebas.json` incompleto no puede autorizar revisión. En una ejecución
limitada no se recogen resultados y se eliminan los nombres de informe parcial
del registro, aunque el candidato hubiera escrito previamente un JSON completo.

Los timeouts siguen siendo `tiempo_agotado`, con código 4, el nombre de ejecución
y los canales parciales. Si stderr ya está lleno, el diagnóstico completo se
conserva en `resultado.json`; no se añade texto por encima de su límite. Los
fallos de limpieza impiden acreditar el resultado y conservan los identificadores
para una retirada administrativa.

### Garantías y límites de la garantía

El presupuesto de resultados limita bloques **retenidos simultáneamente**, no
la suma histórica de todos los bytes escritos y después borrados o sobrescritos.
La detección y la orden de detener por saturación son asíncronas; el límite del
filesystem sigue actuando entre sondeos. No se promete auditar cada syscall
rechazada si el programa captura ENOSPC y borra o reduce el archivo antes del
sondeo. Eso no permite superar el espacio del tmpfs ni el presupuesto de copia.

Tmpfs puede usar swap del anfitrión según el kernel y su política: no se afirma
que permanezca exclusivamente en RAM. Aun en ese caso, sus bloques de datos
están acotados a 32 MiB, y sus metadatos por el límite de inodos. Los 32 MiB de
resultados copiados y los 8 MiB de canales son máximos de **datos**, no una cuota
exacta del espacio de filesystem que consumen metadatos, bloques redondeados y
los registros de control, cuyo tamaño depende también del proyecto de referencia. No se reserva espacio libre global ni se
limita la suma de ejecuciones concurrentes o registros antiguos. Otros procesos
o un disco ya casi lleno pueden seguir ocasionando ENOSPC. Una terminación
SIGKILL/apagado puede exigir retirar por nombre el contenedor y su volumen.

### Validación de la ampliación en Ubuntu

En Ubuntu 24.04.5 con Podman rootless 4.9.3, la sonda y las **10 integraciones
reales pasaron en 32.932 s**. Se mantuvieron los cinco casos anteriores y se
comprobaron por separado exceso de resultados, stdout y stderr, exceso entre
varios archivos y un informe habitual con cuotas pequeñas. Cada exceso verifica
los bytes acotados, el diagnóstico correcto, ausencia de informe acreditable y
retirada de contenedor, volumen y proceso descendiente. El caso válido vuelve a
pasar la clasificación de `flow_counts()` con el formato normal del runner.

También pasaron las 16 unitarias del aislamiento, 7 pruebas específicas del
capturador/copia y los fixtures existentes de orquestación y CSV. Las unitarias
usan datos sintéticos y sustituciones declaradas; las 10 integraciones usan
contenedores y volúmenes reales. La imagen ya estaba disponible; no se descargó.

La pasada final de `env -u CRO_REAL_PODMAN python3 -B -m unittest discover -s tests -v`
terminó con **834 pruebas: 824 correctas y 10 integraciones opt-in omitidas**, sin
fallos ni errores, en **296.475 s**. Incluye las 23 unitarias específicas (16 del
aislamiento y 7 del capturador/copia). Las diez omisiones de esta pasada son las
integraciones reales verificadas por separado; no se presentan como prueba
simulada de las cuotas del kernel.

`python3 -B python_evaluator.py check` terminó correctamente, con limpieza
confirmada. `git diff --check` pasó. La comprobación posterior no encontró
contenedores `cro-eval-*`, volúmenes de resultados ni monitores de cuota activos.
El checkout original y sus cuatro archivos locales permanecen fuera de esta
ampliación. La PR #27 sigue en borrador y con el SHA publicado `c25ea65`.


La sintaxis inicial `--mount ... volume-nocopy` no era admitida por Podman 4.9.3;
se corrigió a `--volume volumen:destino:nocopy`. Los intentos rechazados se
limpiaron sin ejecutar candidatos ni sustituir la cuota por almacenamiento sin
límite. No se relajaron seccomp, AppArmor, namespaces ni las demás protecciones.


## Correcciones de cierre tras la revisión de 4d64899

Se partió del worktree limpio en
`4d64899ea881e9a776c7df397972df17c53fd60c`, sin modificar la PR #27 ni subir los
cambios locales. Los límites de resultados, stdout y stderr se conservan.

### Preparación parcial y diagnóstico de limpieza

`cleanup_result_volume()` consulta la existencia inicial. Si el volumen no
existe (por ejemplo, falló su creación), registra `estado_inicial=ausente` y
confirma la ausencia sin tratarlo como un recurso abandonado. Si existe o no
puede comprobarse, intenta desmontarlo y después **intenta siempre retirarlo
por su nombre**, aunque el desmontaje falle o lance una excepción. La retirada
usa `podman volume rm nombre`, sin `--force`: no autoriza eliminar contenedores
asociados. Por último consulta su existencia y distingue ausencia confirmada,
volumen todavía presente y comprobación no disponible.

El informe `aislamiento.limpieza_volumen` conserva esas observaciones y los
fallos de cada operación. La ausencia del recurso y el éxito de todos los
comandos son hechos distintos: puede retirarse un volumen tras un fallo de
desmontaje. Se registra ese fallo y se mantiene la evaluación en estado de
fallo incluso cuando se pudo confirmar que ya no quedan recursos.

`error` conserva el primer diagnóstico de la ejecución, preparación o recogida;
los fallos posteriores de limpieza se guardan aparte en `errores_limpieza` con
recurso y operación. No sustituyen el error de montaje, de cuota o de timeout.
Un timeout sigue siendo `tiempo_agotado`; si la ejecución aún figuraba como
finalizada, cualquier fallo posterior cambia su estado a fallo y evita su
acreditación. `limpieza_confirmada` solo describe la ausencia de contenedor y
volumen, no borra los errores ocurridos durante su retirada.

### Estructura y fallos durante la recogida

Se valida la estructura completa y el presupuesto agregado antes de escribir
el primer archivo de salida. Un directorio llamado `pruebas.json` o
`pruebas.tmp`, un archivo llamado `consultas`, enlaces o entradas no declaradas
se rechazan sin copiar el árbol. Los informes válidos y sus temporales regulares
conservan sus bytes; el límite durante la copia sigue actuando.

Los errores de recogida se conservan en `error` y `errores_recogida`. Si queda
un informe parcial y su `unlink` falla (por ejemplo, es un directorio o se
deniega la retirada), se anota en `errores_limpieza` y se continúa hasta guardar
`resultado.json` con estado de fallo. No se siguen ni se borran recursivamente
directorios con nombres de informe. Si un parcial permanece en disco, ese hecho
queda registrado y el estado del proceso impide que se considere evaluación
válida. Los diagnósticos añadidos a stderr siguen respetando su límite.

Esto no promete guardar metadatos si el propio almacenamiento de
`resultado.json` deja de poder escribirse: esa imposibilidad de almacenamiento
sigue siendo un error del controlador, nunca una evaluación válida.

### Regresiones y ejecución real

Las pruebas con fallos inyectados cubren creación ausente, montaje fallido de
un volumen creado, desmontaje fallido seguido de retirada, volumen que sigue
presente, diagnóstico de timeout con fallo secundario y fallo al retirar un
informe parcial. Comprueban que el candidato no se invoca cuando falla la
preparación, que la retirada del volumen no fuerza contenedores y que se guarda
el diagnóstico original por separado de la limpieza.

Otras regresiones comprueban que ninguna entrada se copia antes de validar
los tipos de raíz, y que los JSON válidos, los temporales y las consultas
conservan sus bytes y sus presupuestos. Son fallos simulados y comprobaciones
locales explícitas, distintos de la integración real.

En Ubuntu 24.04.5 con Podman rootless 4.9.3, las **10 integraciones reales
pasaron en 33.474 s**. Se mantienen los casos de límites y limpieza; el caso del
informe válido también ejecuta un candidato que crea `pruebas.json` como
directorio. Se comprueba su rechazo, que no se copian consultas ni informes,
que se guarda `resultado.json`, que se conserva la causa y que se retiran el
contenedor y el volumen.

En ese mismo caso también se crea un volumen real y se inyectan únicamente los
retornos de error al montar y desmontar. Podman ejecuta la creación, la retirada
sin `--force` y las consultas de existencia reales. Se confirma que el candidato
no se invoca, que el diagnóstico inicial se conserva separado del desmontaje y
que el volumen creado queda ausente. Esa inyección se distingue de un fallo
espontáneo del kernel o del runtime.

La suite ordinaria (`env -u CRO_REAL_PODMAN python3 -B -m unittest discover -s tests -v`)
terminó con **844 pruebas: 834 correctas y 10 integraciones opt-in omitidas**,
sin errores ni fallos, en **295.261 s**. Incluye 33 pruebas específicas: 16 del
aislamiento, 9 del capturador/recogida y 8 de preparación parcial y finalización.
Las 10 omisiones se ejecutaron por separado con Podman real. `git diff --check`
pasó y la comprobación posterior no encontró contenedores, volúmenes de prueba
ni monitores de cuota restantes. La PR #27 se mantiene en borrador; este cierre
se guarda únicamente en un commit local, sin publicarlo.

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

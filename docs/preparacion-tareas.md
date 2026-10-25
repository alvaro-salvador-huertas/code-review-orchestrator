# Preparación local de tareas (primer alcance de v1.1)

```bash
python3 -B prepare_project.py --from-plan /ruta/al/registro --output /ruta/a/padre/paquete-nuevo
```

El padre del destino debe existir. La operación reutiliza `load_parent()` y
lee la cadena completa: no acepta solo `propuesta.json` o `propuesta.md`.
No consulta Git, Codex, servicios ni modelos; tampoco ejecuta candidatos,
pruebas o descubrimiento de tests, ni reserva invocaciones. Las reservas
históricas se leen como evidencia y quedan intactas.

| Código | Resultado |
| --- | --- |
| 0 | Plan dentro del alcance sin preguntas ni supuestos acumulados: `contrato.borrador.md`, `configuracion.borrador.json`, `revision.md`. |
| 3 | Cadena válida con pendientes o viabilidad insuficiente: únicamente `revision.md`. |
| 1 | Origen inválido o fallo de exportación; no hay cierre válido. Puede quedar un destino incompleto si no se puede limpiar con seguridad. |
| 2 | Argumentos incorrectos, incluidas rutas vacías/blancas, NUL, opciones desconocidas o repetidas. |

Solo se admiten `--from-plan`, `--output` y ayuda. No existe `--force` ni opción
de ejecución. Las opciones obligatorias se dan exactamente una vez. `--help`
termina sin leer registros ni escribir. Las restricciones de destino se evalúan
como errores de exportación (código 1), no como errores del parser.

## Qué contiene el paquete

El contrato conserva objetivo, requisitos, alcance, exclusiones, archivos y
propósitos, criterios y ejemplos, limitaciones y base histórica. No añade requisitos.
Los textos se muestran como datos indentados; cadenas vacías, multilínea, con
controles o espacios iniciales/finales se representan como cadenas JSON reversibles.
Las colecciones se representan como JSON literal, incluidos escapes Unicode.
Un texto que contenga Markdown o instrucciones no se activa como tal.

El JSON tiene tipo `preparacion_tarea_borrador`, `version_borrador: 1` y
`ejecutable: false`. Orienta la preparación manual a configuración v2, con
`null` para identificador, rutas de autoridades, selección de referencias y
límites variables. No es una configuración de confianza: el validador de tareas
lo rechaza, incluso si se renombra. La consulta previa conserva 10 segundos.
`[]` en referencias del plan significa que no constan referencias archivadas;
`null` en referencias de la futura tarea significa que falta elegirlas.

La revisión reúne respuestas, decisiones y pendientes con IDs y procedencia,
los metadatos de referencias, incompatibilidades detectables y materiales por
preparar. Añade rutas, modos, tamaños y SHA-256 de cada archivo leído, enlaces
escapados a los originales e identidad de las fuentes locales del lector/exportador.
Las versiones, profundidad y estados históricos se conservan; un `borrador` v2
puede dar código 3 si el lector encuentra supuestos ancestrales pendientes.
No se infiere resolución por omisión del modelo o igualdad de textos.

El exportador detecta referencias coincidentes con editables, utilidades
reservadas y referencias vacías. La correspondencia semántica y las colisiones
con autoridades todavía sin elegir requieren revisión humana. No convierte una
referencia de planificación en evaluador, prompt o contrato de confianza.

## Política de destinos y raíz

La CLI identifica la raíz del proyecto mediante
`Path(__file__).resolve().parent`: el directorio real de esta instalación de
`prepare_project.py`. No busca `.git` ni deduce la raíz del registro o del cwd.
La API Python admite `project_root` explícito para integración y fixtures; la
CLI no ofrece una opción para cambiarlo. Las rutas relativas de entrada/salida
se interpretan desde el cwd de la invocación; `~` debe expandirlo el shell.
En Linux, una raíz `//` se normaliza a `/` para comparar destinos y generar
enlaces locales; no se resuelven enlaces simbólicos al normalizar. El texto de
las rutas históricas sigue conservado literalmente en la procedencia.

Se permiten destinos dentro de la raíz y externos. Se excluyen:

- Cualquier destino con `..`, componentes ocultos, barra inversa o nombres de
  `project_task_config.PRIVATE`: `.git`, `runs`, `__pycache__`, `.agents`, `.codex`,
  `.aws`, `.venv`. Se aplica a **todos los componentes de la ruta absoluta**,
  también fuera de la raíz; se reutiliza `relative_path()` tras absolutizarla.
- `tasks/`, `evals/` y `prompts/`, y sus descendientes, directamente bajo la raíz
  identificada. Un directorio externo llamado `tasks` no es una autoridad de esta
  instalación. No se detectan otros repositorios ni autoridades externas.
- El registro seleccionado, cualquier ancestro de su cadena, sus descendientes
  y directorios que los contengan, estén dentro o fuera del proyecto.
- Destinos ya existentes: archivos, directorios incluso vacíos, enlaces válidos
  o rotos. El padre debe ser directorio existente, con todos sus antecesores sin
  enlaces; no se crean padres implícitamente.

Se abre la ruta del padre componente a componente con `O_DIRECTORY` y
`O_NOFOLLOW`, y se escribe usando descriptores de directorio. La creación del
destino y de sus archivos es exclusiva. Los modos solicitados son 0700 para el
directorio y 0600 para borradores, sujetos a umask; no son modos de los editables.

El origen se comprueba antes y después de escribir. Se comprueban también la
identidad del destino y los bytes de salida. `revision.md` se escribe al final;
el éxito se comunica solo tras las comprobaciones. No hay transacción atómica
de varios archivos ni protección frente a toda modificación concurrente.

Ante fallo o interrupción capturada, la limpieza solo retira archivos creados
por esta operación cuya identidad y bytes sigan siendo propios; nunca recorre
ni borra contenido ajeno. Solo elimina el directorio propio si queda vacío.
Si hay cambios externos, falta de permisos, muerte abrupta o caída del sistema,
pueden quedar restos, incluso `revision.md`: su mera presencia no acredita un
cierre correcto. Un destino incompleto se rechaza en la siguiente invocación;
una persona debe inspeccionarlo y elegir un destino nuevo. No hay reanudación.

## Límites que permanecen

Se mantienen los formatos históricos v1/v2/v3 y los límites del lector:
original más ocho revisiones, 8 MiB por archivo, 64 MiB por cadena y 64 artefactos
por registro. Se permite exportar profundidad ocho sin continuar la cadena.
Los hashes verifican correspondencia, no autenticidad del autor.

El paquete depende de los originales en sus rutas históricas. Conserva SHA,
inventario, referencias y decisiones; no copia la base Git ni ofrece portabilidad.
No acredita que el commit siga disponible, los modos actuales ni el comportamiento.

El motor sigue exigiendo regresión superada y aceptación inicialmente fallida
por aserciones acreditadas. Una refactorización que conserva comportamiento
puede ser válida aunque su aceptación pase antes del cambio: puede exportar
borradores, pero queda fuera del flujo actual si no cumple esa precondición.
No se fabrica un fallo, cambia la base o modifica el motor para hacerla ejecutable.
La revisión incluye este límite en todos los resultados, sin clasificar la prosa.

## Demostración reproducible, exclusivamente sintética

Desde la raíz, el siguiente bloque construye evidencia ficticia a partir de
los dos ejemplos documentados y exporta ambos resultados. **No ejecuta suites**:
importa el constructor de fixtures, no llama al runner de `unittest`. Los datos
de proceso y reserva son sintéticos y no representan llamadas a modelos.

```bash
python3 -B - <<'PY'
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path('tests').resolve()))
from test_prepare_project import documented_records
from prepare_project import main
demo = Path(tempfile.mkdtemp(prefix='preparacion-v1.1-demo-'))
complete, pending = documented_records(demo)
for source, name, expected in ((complete, 'paquete', 0), (pending, 'diagnostico', 3)):
    code = main(['--from-plan', str(source), '--output', str(demo / name)])
    assert code == expected, (name, code)
    print(name, 'codigo', code, demo / name)
print('Conservar este directorio: los borradores dependen de sus originales.', demo)
PY
```

El [ejemplo completo](ejemplos-v1.1/01-completo.md) muestra contrato y JSON
literalmente comprobados por las pruebas. El [ejemplo pendiente](ejemplos-v1.1/02-pendientes.md)
conserva dos pendientes heredados y un rechazo explícito; solo produce revisión.
La [especificación](propuesta-v1.1.md) conserva las decisiones y el recorte de alcance.

Para validar código: `python3 -B -m unittest discover -s tests -p test_prepare_project.py -v`.
Las fixtures no leen registros privados. Durante las exportaciones de estas
pruebas se bloquea la creación de procesos y se contrasta la conservación de
los registros, reservas y materiales.

## Comprobaciones del 25 de octubre de 2026

Python 3.12.3, biblioteca estándar y procesos de agentes simulados en las
pruebas históricas de compatibilidad; ninguna llamada real a modelos:

| Comprobación | Métodos | Tiempo de unittest | Resultado |
| --- | ---: | ---: | --- |
| Preparación, cierre tras corregir la raíz `//` | 23 | 0,717 s | Código 0, sin fallos, errores ni omisiones. |
| Planificación y continuidad (`test_plan*.py`) | 103 | 27,319 s | Código 0. |
| Configuración v1 (`test_configurable_projects.py`) | 19 | 19,100 s | Código 0. |
| Configuración v2 (`test_multiple_projects.py`) | 12 | 21,566 s | Código 0. |

La primera pasada conservada tenía 20 métodos y tres fallos de expectativas
(umask, representación literal y separación de párrafos del ejemplo); se
corrigieron antes del cierre. La revisión posterior reprodujo un fallo real de
destinos con `//` inicial: un método, dos subcasos fallidos, código 1. Se añadió
su normalización sin resolver enlaces; las 23 enfocadas posteriores incluyen
esa reproducción. La compatibilidad conserva validez: el lector, el motor y
la protección añadida no cambiaron con ese ajuste local del exportador.

La demo ejecutó la CLI en dos procesos locales: códigos 0 y 3, con tres archivos
y uno respectivamente, y originales conservados en bytes y modos. Los ejemplos
documentados se contrastan con la salida implementada. La inspección de enlaces,
JSON y diff se hace separadamente de las pruebas.

La preparación inicial no lanzó la integrada en el entorno restringido: la
comprobación de socket local devolvió
`PermissionError: [Errno 1] Operation not permitted`, y la suite HTTP requiere
sockets. Esa restricción y las comprobaciones anteriores se conservan separadas
de la ejecución posterior aportada desde la terminal del usuario:

```bash
python3 -B -m unittest discover -s tests -v
```

### Integrada aportada desde la terminal

El usuario ejecutó la regresión integrada el **25 de octubre de 2026** mediante
el runner preparado: **791 métodos, 296,344 s de unittest, código 0**, sin fallos,
errores ni omisiones. El cotejo leyó los archivos conservados, sin repetir suites
ni invocar modelos. `suite/stderr.txt` contiene 791 identidades únicas con `ok`
y el cierre `Ran 791 tests in 296.344s` / `OK`; `suite/stdout.txt` está vacío.
Esto confirma el resumen pegado por el usuario y aporta las identidades y canales
completos que ese resumen no incluía.

`suite/resultado.json` registra `/usr/bin/python3 -B -m unittest discover -s tests -v`,
estado `finalizada`, código 0, entorno `evaluation` y límite de 600 s. La duración
del proceso completo es **296,646918176 s**, distinta del tiempo de unittest.
Las marcas UTC `20:11:02.320544Z`–`20:15:58.967442Z` son coherentes con ella.
El archivo no registra la versión exacta de Python ni un código independiente
del wrapper; no se les atribuyen datos ausentes. La atribución a la terminal
proviene del usuario, además de la evidencia local del proceso.

Los inventarios anterior y posterior coinciden: **219 entradas, 180 archivos**,
con contenido y modos conservados. También coincidían con el árbol actual antes
de este cierre documental. El alcance es `tree_state(filter_local=True)`:
excluye `.git`, `runs/`, cachés y configuración local; no acredita conservación
histórica de HEAD, rama o índice. Los hashes comprueban correspondencia, no
autenticidad del entorno o del autor.

Las identidades se contrastaron con las 768 del inventario histórico conservado
y las 23 declaraciones de la nueva clase de pruebas, leídas mediante AST, sin
ejecutarlas ni redescubrir la suite. Coinciden exactamente, sin ausencias ni
duplicados. Se cotejaron fuentes, modos y dependencias: los tests/evaluadores
anteriores siguen iguales; el único cambio en código histórico es la protección
adicional de `prepare_project.py`, ya cubierta por la compatibilidad y esta
integrada. Las enfocadas, la compatibilidad y las demos mantienen sus resultados
propios; no se suman como métodos adicionales a los 791.

Después de la suite solo se actualizan README y esta guía. Código, pruebas,
ejemplos y dependencias conservan las identidades evaluadas, por lo que se
reutiliza la validación sin otra ejecución.

La evidencia duradera está excluida de Git en
`runs/20261025_preparacion_v1_1_cierre/`: copias íntegras de la integrada, desarrollo,
fallos previos y demos; instantánea del árbol evaluado; cotejo de identidades,
manifiestos de copia y diff. Los originales permanecen en
`/tmp/preparacion-v1.1-integrada-5i9ztqpy/` y
`/tmp/preparacion-v1.1-validacion-emm16yi9/`, sin sobrescribir ni eliminar.
Las copias de demostraciones **no son registros portables**: conservan rutas
históricas, hashes, referencias y procedencia sin reescritura; no pueden
revalidarse desde su nueva ubicación como si fueran los registros originales.

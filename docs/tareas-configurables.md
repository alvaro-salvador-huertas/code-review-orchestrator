# Tareas de proyecto mediante configuración

```bash
python3 -B orchestrate_project.py --task-config tasks/config/mi-tarea.json --max-attempts 2
```

Este comando **invoca agentes reales** cuando dispone de Codex autenticado.
Este hito se ha comprobado con repositorios temporales y una CLI de agentes
simulada, sin llamadas a modelos ni nuevos experimentos.

Reutiliza el bucle de desarrollo, evaluación, corrección y revisión existente.
Los comandos `orchestrate_project.py inspect-json` y
`orchestrate_project.py export-csv` conservan selecciones, presupuestos y
precondiciones históricas. No se pueden combinar con `--task-config` ni repetir
esa opción. El presupuesto sigue siendo de uno o dos intentos, con una reserva
por rol e intento. Una aprobación deja la entrega para revisión humana; no la
incorpora al proyecto.

## Registrar una tarea

1. Seleccionar un commit completo y disponible localmente como base de confianza.
   Debe contener una regresión no vacía bajo `tests/`, descubrible por `unittest`.
2. Mantener un contrato bajo `tasks/`, con una única línea `Base: ` seguida del
   SHA de 40 caracteres entre acentos graves. Declarar los archivos editables y sus estados iniciales.
3. Preparar un evaluador de aceptación bajo `evals/`, con biblioteca estándar,
   que acepte `--project <copia>`, clases explícitas de `unittest.TestCase`, una
   sola ejecución de `TextTestRunner` y código 0/1 según su resultado. La lectura
   AST de estas identidades admite herencia local; no admite descubrimiento
   dinámico ni herencia importada. La regresión usa descubrimiento en un hijo.
4. Escribir prompts bajo `prompts/` y declarar las referencias necesarias. El
   revisor debe emitir `decision`, `resumen` y `hallazgos` según el esquema que
   recibe, con archivo y línea localizados. Su sesión es independiente.
5. Guardar el JSON v1 o v2 bajo `tasks/config/`, revisar los materiales y ejecutar el
   comando solo cuando se quiera autorizar una ejecución real.

Configuración, contrato, evaluador, prompts, referencias y base son **materiales
de confianza mantenidos por el usuario**, fuera del alcance editable del agente.
No se admiten comandos shell, hooks, instalación de dependencias, opciones de
credenciales, permisos, políticas de entorno o desactivación de comprobaciones.

## Esquema v1 y ejemplo sintético

Esta plantilla es coherente con el esquema, **no una tercera funcionalidad real
registrada**. El commit corresponde al merge de la PR #11 y carece de
`marcador_sintetico.py`. Los materiales nombrados deben prepararse antes de usar
la plantilla: no están instalados como tarea ejecutable en el repositorio.

```json
{
  "version": 1,
  "identificador": "marcador-sintetico",
  "commit_base": "f950a654190f0ab7c6f809955a7e7f460a1c86be",
  "contrato": "tasks/marcador-sintetico.md",
  "archivo_editable": "marcador_sintetico.py",
  "estado_inicial": "ausente",
  "evaluador_aceptacion": "evals/marcador_sintetico/evaluar.py",
  "prompts": {
    "desarrollador": "prompts/marcador-sintetico-desarrollo.md",
    "revisor": "prompts/marcador-sintetico-revision.md"
  },
  "referencias": ["docs/marcador-sintetico.md"],
  "limites_segundos": {
    "desarrollador": 300,
    "revisor": 300,
    "aceptacion": 60,
    "regresion": 300,
    "inventario": 30,
    "consulta_cli": 10
  }
}
```

Todas esas claves son obligatorias y no se admiten otras; `referencias` puede
ser una lista vacía. Las reglas son:

| Campo | Regla |
| --- | --- |
| `version` | Entero exacto 1. |
| `identificador` | Hasta 64 caracteres: minúsculas ASCII y dígitos, grupos separados por guiones; empieza por letra. `inspect-json` y `export-csv` están reservados. |
| `commit_base` | SHA completo en minúsculas, de 40 caracteres; resuelve al mismo commit local y coincide con el contrato. |
| `archivo_editable` | Un nombre Python de la raíz: letras ASCII, dígitos y guion bajo, sin dígito inicial, terminado en `.py`. |
| `estado_inicial` | `existente` o `ausente`, comprobado contra el árbol Git. |
| `contrato`, `evaluador_aceptacion`, `prompts` | Archivos regulares no vacíos: `.md` bajo `tasks/`, `.py` bajo `evals/` y dos `.md` bajo `prompts/`. |
| `referencias` | Rutas relativas únicas de archivos regulares no vacíos; no repiten autoridades ni incluyen el editable. |
| `limites_segundos` | Enteros positivos: agentes hasta 600 s, aceptación hasta 300 s, regresión hasta 600 s e inventario hasta 120 s. Las consultas previas conservan 10 s fijos. |

Se rechazan booleanos como números, claves duplicadas, constantes no JSON,
versiones desconocidas, rutas absolutas, componentes `..`, rutas no normalizadas,
componentes ocultos, registros privados y enlaces, incluidos los de directorios
antecesores. Los errores de selección o configuración previa producen código
CLI 2 sin lanzar agentes. Los fallos posteriores conservan códigos y detenciones
del flujo existente.

En la plantilla, el contrato podría exigir solo un comentario marcador exacto
y la aceptación comprobarlo mediante aserciones, sin importar ni ejecutar el
archivo. Los prompts y la referencia deben describir ese mismo marcador y su
carácter sintético. Las [pruebas permanentes](../tests/test_configurable_projects.py)
construyen dos ejemplos completos en repositorios temporales, con commits
propios, materiales coherentes y archivos editables distintos.

## Congelación, precondición y revisión

Antes del desarrollo se reconstruyen únicamente blobs regulares de la base.
Se conservan los modos Git y la ausencia inicial como ausencia, sin fabricar un
archivo vacío. Un archivo nuevo debe tener modo 0644; uno existente conserva
el modo de la base. No se admiten otros cambios.

En `referencia/` quedan el proyecto base, `tarea.json` con los bytes originales,
`configuracion.json` efectiva, contrato, evaluador, prompts, referencias,
utilidades, versiones del motor y procedencia con hashes. Las referencias se
guardan en `materiales/`, separadas de las utilidades de `autoridades/`.
No pueden declarar como materiales los nombres reservados de las utilidades del
controlador (`repair_case.py`, `run_case.py`, `case_config.py`, `case_evidence.py`,
`process_environment.py` y `project_test_inventory.py`).

El inventario procede de la copia protegida de la base **antes del agente**,
en un hijo con intérprete absoluto, `-B`, entorno `evaluation`, cwd y timeout
explícitos. Se conservan informe, identidades, versión de la utilidad, hashes y
comprobaciones de inmutabilidad. Descubrir importa módulos y puede ejecutar
su inicialización: no es análisis estático ni aislamiento de seguridad. Nunca
se descubren identidades esperadas desde una entrega candidata.

Solo se autoriza desarrollar con el estado inicial declarado, regresión completa
superada y aceptación con fallos de aserción acreditados mediante identidades,
informe estructurado, código y cierre textual. Aceptación ya superada, errores
técnicos, omisiones o informes incompletos detienen el flujo. La vía genérica no
busca mensajes literales de funcionalidades concretas; las precondiciones
históricas permanecen separadas.

Las etapas utilizan la selección y materiales congelados, sin volver a resolver
el JSON original. La referencia íntegra previa al agente permanece como autoridad
del controlador; no se reconstruye desde un manifiesto del candidato. Cambiar la
configuración original durante la ejecución activa la comprobación de conservación
del proyecto y detiene el flujo; no selecciona otra tarea ni cambia sus límites.

Las evaluaciones se ejecutan en copias reconstruidas. Una corrección recibe los
bytes exactos del candidato anterior y feedback conservado. Las reservas se
persisten antes de cada invocación. No hay reintentos técnicos, reanudación ni
incorporación automática. El revisor recibe contrato, candidato, estado inicial,
configuración, referencias, dependencias locales resueltas sin importarlas y
resúmenes de evaluaciones verificadas. Fallos técnicos y dictámenes inválidos
nunca producen aprobación.

## Registros y consulta

La configuración v1 produce `orquestacion_configurable_v1`; v2 produce
`orquestacion_configurable_v2`. El resumen incluye `tarea` y
`configuracion` con versión, identificador, origen, SHA-256 del JSON y commit base.
Los tipos y validadores históricos no se sustituyen.

```bash
python3 -B inspect_project.py --run ruta/al/registro
python3 -B inspect_project.py --run ruta/al/registro --format json > consulta.json
python3 -B export_runs.py consulta.json
```

El [inspector](inspector-proyectos.md) solo lee `resultado.json`, incluidos los
metadatos registrados de configuración. No abre su origen ni verifica sus hashes.
La proyección mantiene JSON de exportación v1: `ejecucion.caso` recibe `tarea`.
La consulta no constituye autorización, integridad o incorporación. No se amplía
la revisión aislada histórica para aceptar este formato.

## Límites y validación

V1 admite un archivo Python editable y v2 varios, todos en la raíz, con biblioteca estándar y
materiales declarados. No incluye interpretación de lenguaje natural, planificación
automática, instalación de paquetes, despliegue ni agentes nuevos.
El cierre estático de dependencias del revisor conserva sus restricciones:
módulos locales `.py` en la raíz o `tests/` y biblioteca estándar; los imports
dinámicos, relativos, paquetes locales o dependencias ambiguas detienen la revisión.

V2 añade el conjunto, su continuidad, diffs y revisión descritos más abajo.
Siguen pendientes borrados, renombrados, subdirectorios y paquetes editables,
dependencias externas y revisión aislada configurable. No implementa una API
ni registra una nueva tarea real. Copias, permisos y hashes permiten contrastar
evidencia; no constituyen aislamiento de seguridad.

### Evidencia histórica de la preparación v1

La base de aquella preparación fue `f950a654190f0ab7c6f809955a7e7f460a1c86be`: la
[CI del merge de la PR #11](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39266244148)
pasó 383 métodos en 259,639 s con Python 3.12.15. Es la comprobación del merge en
`main`, distinta de la CI previa de la PR. Las simulaciones nuevas y la regresión
local de este hito no reclasifican experimentos históricos.

Comprobaciones locales durante el desarrollo (Python 3.12.3, todas mediante
`python3 -B -m unittest discover -s tests -p <módulo> -v`):

| Alcance enfocado | Métodos | Duración | Resultado |
| --- | ---: | ---: | --- |
| Primera revisión de `test_configurable_projects.py` | 12 | 23,167 s | Correcto, código 0 |
| Revisión ampliada de `test_configurable_projects.py` | 16 | 29,653 s | Correcto, código 0 |
| `test_inspect_project.py` | 31 | 8,687 s | Correcto, código 0 |
| Compatibilidad: `test_export_csv_flow.py` | 21 | 41,002 s | Correcto, código 0 |
| Compatibilidad: `test_orchestrate_project.py` | 20 | 50,371 s | Correcto, código 0 |

Después se añadieron tres métodos sobre errores de sintaxis y configuración
profundamente anidada. Su primera ejecución selectiva registró **dos errores en
tres métodos**, 1,022 s, código 1: `SyntaxError` escapaba al inventariar un
evaluador mal formado y al preparar la revisión de un candidato mal formado.
El JSON excesivamente anidado ya se rechazaba correctamente. La corrección
convierte esos errores de sintaxis en evidencia inválida únicamente en la vía
configurable; no autoriza agentes posteriores ni altera validadores históricos.
La repetición de esos tres métodos pasó en 0,946 s, código 0. Los registros
locales de ambas ejecuciones se conservaron por separado.

Las dos tareas permanentes usan `marcador-alfa`/`alpha.py` existente y
`marcador-beta`/`beta.py` ausente. Comprueban hashes idénticos de los archivos del
motor antes y después de ambos recorridos; solo cambian los materiales y la
configuración. Son comentarios marcadores y procesos simulados. Las pruebas
incluyen corrección tras aserciones fallidas, continuidad, reservas, límites,
manipulación de autoridades, cambios fuera de alcance, fallos técnicos, timeout,
dictamen inválido y consulta JSON seguida de exportación CSV. No acreditan
fiabilidad general con agentes reales.

La regresión completa final se ejecutó una vez, después de cerrar los cambios
de código y pruebas:

```bash
python3 -B -m unittest discover -s tests -v
```

Resultado real: **405 métodos en 205,790 s, código 0; cero fallos, errores y
omisiones**, con Python 3.12.3. Incluye los 19 métodos configurables y los 31 del
inspector de proyectos. Se conservaron stdout, stderr, comando, intérprete y un
inventario SHA-256 con modos de los 114 archivos del árbol probado. Esta ejecución
local es distinta de las 383 pruebas de la base y no constituye una nueva CI
remota. Después solo se completó esta documentación; no se repitieron suites.

## Esquema v2: varios archivos editables

V2 sustituye **solo** `archivo_editable` y `estado_inicial` por
`archivos_editables`. Las demás claves, límites y precondiciones conservan sus
reglas. No se convierten configuraciones v1 ni se admiten claves de ambas
versiones mezcladas. V1 y los dos comandos históricos siguen disponibles.

Ejemplo completo de configuración **sintética**, no instalada como tarea real.
El SHA de ceros es un marcador que debe sustituirse por el commit local de una
base preparada con `reglas.py` regular, sin `consulta.py` y con regresión
protegida. El contrato debe declarar ese mismo SHA; los materiales nombrados
deben existir y ser coherentes antes de invocar el comando:

```json
{
  "version": 2,
  "identificador": "modulos-sinteticos",
  "commit_base": "0000000000000000000000000000000000000000",
  "contrato": "tasks/modulos-sinteticos.md",
  "archivos_editables": [
    {"ruta": "reglas.py", "estado_inicial": "existente"},
    {"ruta": "consulta.py", "estado_inicial": "ausente"}
  ],
  "evaluador_aceptacion": "evals/modulos_sinteticos/evaluar.py",
  "prompts": {
    "desarrollador": "prompts/modulos-sinteticos-desarrollo.md",
    "revisor": "prompts/modulos-sinteticos-revision.md"
  },
  "referencias": ["docs/modulos-sinteticos.md"],
  "limites_segundos": {
    "desarrollador": 300,
    "revisor": 300,
    "aceptacion": 60,
    "regresion": 300,
    "inventario": 30,
    "consulta_cli": 10
  }
}
```

La lista debe ser no vacía y sin rutas repetidas. Cada elemento tiene exactamente
`ruta` y `estado_inicial`, con las mismas restricciones de nombres Python de la
raíz que v1. Se rechazan rutas de directorios, enlaces en Git, estados iniciales
distintos de Git, autoridades editables y colisiones con la infraestructura del
controlador enumerada en `project_task_config.PROTECTED`. No autoriza borrados,
renombrados, subdirectorios, paquetes locales ni instalación de dependencias.
La selección no exige limpiar o sustituir el árbol actual: reconstruye la base
Git y comprueba la conservación del proyecto original.

El evaluador sintético de las pruebas exige que `reglas.calcular()` devuelva 7
mediante `consulta.valor()`. El módulo nuevo puede ser una dependencia del
existente. Esto no define una nueva tarea de producto ni una API.

### Identidad y continuidad del conjunto

Cada conjunto tiene un manifiesto de identidad **versión 1** con `archivos`,
ordenados por `ruta`. Cada entrada contiene `ruta`, `tipo`, `sha256` y `modo`.
Para un archivo regular, `sha256` es el hash de sus bytes y `modo` es el entero
de permisos POSIX: 420 significa 0644 y 493 significa 0755. Para una ausencia,
`tipo` es `ausente`, y hash y modo son `null`. Un archivo vacío regular tiene
hash y modo propios; nunca sustituye a una ausencia.

La identidad del conjunto es SHA-256 de la codificación UTF-8 de
`{"version":1,"archivos":[...]}`, con claves ordenadas, `ensure_ascii=False`,
separadores `(',', ':')` y sin salto de línea. El campo `sha256` exterior se
añade después; no forma parte de su propio cálculo. Cambiar contenido, ruta,
presencia o modo cambia la identidad. Para estados parciales inválidos se
conserva el tipo real (`enlace`, `directorio` o `especial`), modo, hash `null`
y, en enlaces, `destino`. Estos datos también entran en la identidad; no se
siguen los enlaces ni se archivan como si fueran candidatos regulares.

La autoridad es la selección en memoria y la referencia congelada antes del
agente. La validación reconstruye la lista esperada desde esa autoridad, no
desde un manifiesto entregado. Después de un desarrollo correcto deben existir
todos los editables como archivos regulares: nuevos 0644 y existentes con el
modo de Git. Se contrastan también todos los demás archivos y directorios.

En `entrega/` se conservan `archivos/`, `partida/`, `original/`, `diff_base/`,
`diff_anterior/`, los manifiestos `conjunto.json`, `partida.json`, `original.json`
y los inventarios `workspace_despues.json` y `cambios.json`. Las copias de
originales y partidas ausentes no se crean; sus manifiestos registran la
ausencia. Los diffs de creación utilizan `/dev/null` como origen.

Un segundo intento reconstruye la base y superpone **todos** los archivos del
anterior, también los que la corrección no cambie. La partida debe tener la
identidad del conjunto anterior. El feedback v2 incluye `conjunto_sha256`;
se rechaza feedback referido a otro conjunto. Cada evaluación usa una copia
nueva de la base con el conjunto completo, nunca el workspace del desarrollador.
Sus registros v2 incluyen `conjunto_evaluado` y `conjunto_sha256`, y se contrastan
los informes, identidades de métodos, cierres textuales y archivos conservados.

En los resúmenes y evidencias `orquestacion_configurable_v2`, los campos son
`partida_conjunto`, `partida_conjunto_sha256`, `conjunto` y `conjunto_sha256`.
No se reutiliza `candidato_sha256` para nombrar un hash de conjunto. Las reservas,
presupuestos y comprobaciones de conservación siguen en el mismo bucle.
Fallos técnicos, timeout o interrupción conservan el conjunto parcial real sin
evaluarlo como entrega completa ni volver a invocar automáticamente.

### Revisión de todos los módulos

El revisor recibe todos los candidatos, aunque no cambien, y sus diffs frente a
la base y la partida, contrato, configuración, estados iniciales, referencias y
resumen de evaluaciones verificadas. La revisión registra
`revision_conjunto_configurable_v2`, `conjunto_revisado` y `conjunto_sha256`;
la selección y el resumen de evidencia se identifican como versión 2.

El cierre de imports es AST, sin importar ni ejecutar candidatos. Reconoce
módulos editables recién creados y usa sus bytes candidatos. Las dependencias
protegidas proceden de la referencia congelada. Los originales y su cierre de
dependencias se conservan aparte en `original/`; las dependencias protegidas del
contexto candidato están en `dependencias/`. No se sustituye una versión
candidata por el original del mismo nombre. Imports dinámicos, relativos,
paquetes locales, ambigüedades y dependencias no resolubles impiden invocar la
revisión.

El esquema del dictamen admite cada archivo autorizado con su límite propio
de líneas. Se rechazan archivos ajenos, líneas fuera de ese archivo y booleanos
como números. Un hallazgo con formato correcto sigue siendo una observación
del modelo pendiente de contraste semántico. La revisión aislada configurable
v2 no se admite y se rechaza antes de invocar.

Se utilizan los comandos del inicio de esta guía, seleccionando el JSON v2 con
`--task-config`. El inspector lee solo el resumen y sigue proyectando JSON de
exportación v1; ni el inspector ni el CSV verifican el conjunto o autorizan su
incorporación.

## Validación del soporte v2

La base fue el merge de la PR #13,
`9877b9c2b7b730c70cff5c86969ec6430554452a`. Se verificaron los logs de su
[CI automática](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/actions/runs/39292118583):
evento `push`, ese mismo SHA, Python 3.12.15 y comando
`python3 -B -m unittest discover -s tests -v`; **448 métodos en 292,176 s,
resultado correcto**. Es CI de la base, no del soporte v2 sin publicar.

Las [pruebas nuevas](../tests/test_multiple_projects.py) usan repositorios Git
temporales y una CLI simulada. Cubren dos módulos con import local, ausencia
real, modos 0755/0644, corrección por comportamiento y por dictamen, presupuesto,
entrega incompleta, cambios ajenos, enlaces, directorios, otra identidad de
conjunto, procedencia del contexto, cierre AST sin ejecución, fallos técnicos,
timeout, interrupción y dictamen inválido. La consulta textual, JSON y CSV usa
resúmenes sintéticos; las [pruebas del inspector](../tests/test_inspect_project.py)
cubren además un fallo consultable y una consulta incompleta exportable en v2.

Resultados locales enfocados, separados de la CI y del historial v1:

| Comprobación | Métodos | Duración | Resultado |
| --- | ---: | ---: | --- |
| Primera versión de las pruebas de conjuntos | 11 | 21,311 s | Correcto, código 0 |
| Límites por archivo y paquetes; repetición necesaria de continuidad y evidencia tras ajustar el formato de revisión | 3 | 2,472 s | Correcto, código 0 |
| Compatibilidad configurable v1 | 19 | 18,462 s | Correcto, código 0 |
| Inspector, incluidos resúmenes v2 | 33 | 8,888 s | Correcto, código 0 |
| Continuidad y rechazo de otro conjunto tras versionar explícitamente evaluaciones y feedback | 2 | 2,388 s | Correcto, código 0 |
| Esos dos recorridos tras separar la copia de cada suite v2 | 2 | 2,389 s | Correcto, código 0 |

La traza conservada de la simulación principal tiene estas identidades:

| Etapa | Identidad del conjunto | Resultado registrado |
| --- | --- | --- |
| Inicial | `1eb92fa94d37445ea613ec17d65dacd95578c56cfae3e5ff588f0f4172ed354c` | `reglas.py` existente 0755; `consulta.py` ausente |
| Entrega 1 | `a5c947e2d34cc744b266aca1e2dc0f75e652299f43dc6b1e98da0441cc9e6daf` | Aceptación: 1 método con fallo, devuelve 6 en vez de 7; regresión: 3 correctos |
| Partida 2 | `a5c947e2d34cc744b266aca1e2dc0f75e652299f43dc6b1e98da0441cc9e6daf` | Coincide con toda la entrega 1 |
| Entrega 2 | `2e937890f23be5296d23b669391151f57f4ec4ea7dab2d25b98d7636c369d0ae` | Aceptación: 1 correcto; regresión: 3 correctos; revisión simulada aprobada |

`reglas.py` conserva en ambas entregas el SHA-256
`f9cbec900584db02b4e9ca4fec3d8c42e48c1ce5f09806b1cb5d2a0290e74c88` y modo 0755.
Solo se corrige `consulta.py`, nuevo 0644. La preparación inicial registra un
fallo de aceptación por archivo ausente y tres métodos de regresión correctos.
Se consumen **dos desarrollos y una revisión, 3/4 invocaciones**; queda
`lista_para_revision_humana`, sin incorporación. Estos recuentos internos de
fixtures no se suman a los métodos principales de unittest.

La única regresión completa final se ejecutó con
`python3 -B -m unittest discover -s tests -v`: **462 métodos en 237,038 s,
Python 3.12.3, código 0**, sin fallos, errores ni omisiones. Incluye los 12 métodos
nuevos de conjuntos, 33 del inspector y la compatibilidad v1 e histórica. No se
repitió la suite completa. Estos resultados locales no acreditan llamadas a
modelos ni una ejecución de CI del nuevo soporte.

La evidencia local excluida de Git está en
`runs/20261019T200800Z_tareas-multiples_validacion_local_b4f2c68499ec46cc813ecab7cd3eb5a7/`: comandos, stdout/stderr, códigos, identidades únicas, hashes y
modos antes/después, traza simulada y logs de la CI de la base. El inventario
general registra un cambio durante la suite: esta guía recibió los dos últimos
resultados enfocados. Código, pruebas y dependencias conservaron sus hashes y
modos; después solo se completó documentación. Los registros temporales de los
fixtures fueron eliminados por las pruebas; se conserva su traza, sin afirmar
que esos directorios sigan disponibles.

Se contrastaron las 7.587 entradas de los registros históricos, sin cambios.
Contratos, evaluadores históricos, prompts, benchmark y configuración permanecen
intactos. El soporte se ha validado mediante simulaciones: queda pendiente una
ejecución real autorizada de una tarea v2 y su contraste. No permite deducir
fiabilidad general de los agentes ni aislamiento de seguridad.

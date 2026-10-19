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
   SHA de 40 caracteres entre acentos graves. Declarar el único archivo editable.
3. Preparar un evaluador de aceptación bajo `evals/`, con biblioteca estándar,
   que acepte `--project <copia>`, clases explícitas de `unittest.TestCase`, una
   sola ejecución de `TextTestRunner` y código 0/1 según su resultado. La lectura
   AST de estas identidades admite herencia local; no admite descubrimiento
   dinámico ni herencia importada. La regresión usa descubrimiento en un hijo.
4. Escribir prompts bajo `prompts/` y declarar las referencias necesarias. El
   revisor debe emitir `decision`, `resumen` y `hallazgos` según el esquema que
   recibe, con archivo y línea localizados. Su sesión es independiente.
5. Guardar el JSON v1 bajo `tasks/config/`, revisar los materiales y ejecutar el
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

El nuevo tipo es `orquestacion_configurable_v1`. Su resumen incluye `tarea` y
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

Esta versión admite un archivo Python editable en la raíz, biblioteca estándar y
materiales declarados. No incluye interpretación de lenguaje natural, planificación
automática, instalación de paquetes, despliegue ni agentes nuevos.
El cierre estático de dependencias del revisor conserva sus restricciones:
módulos locales `.py` en la raíz o `tests/` y biblioteca estándar; los imports
dinámicos, relativos, paquetes locales o dependencias ambiguas detienen la revisión.

Para proyectos con varios archivos falta definir un conjunto editable, operaciones
de creación/borrado, continuidad y diffs por archivo, cierre de dependencias,
contexto del revisor y esquema de hallazgos. También queda pendiente una revisión
aislada configurable con autorización y procedencia propias. No basta con ampliar
una lista de rutas.

La base es `f950a654190f0ab7c6f809955a7e7f460a1c86be`: la
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

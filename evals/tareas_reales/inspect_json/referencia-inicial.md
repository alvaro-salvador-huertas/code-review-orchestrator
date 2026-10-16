# Referencia inicial de aceptación — 16 de octubre de 2026

Se ejecutó **una sola vez**, con Python **3.12.3**, desde la raíz:

```bash
python3 -B evals/tareas_reales/inspect_json/evaluar.py --project .
```

La implementación consultada es la de `main`, commit
`9bec53279d82058fe188c0038bab5ba66ce64003`, sin cambios de código ni de las
pruebas existentes. La preparación está en `feat/tarea-inspector-json`.
Los SHA-256 de los archivos usados fueron:

- `inspect_run.py`: `c4122912020f0e363655b0354614f3507b263c96f7b0c6304faafc27e2fe422b`.
- `evaluar.py`: `61bb184289eeb837f6aaf0c1d0688d31130515e8f1c3b7e35fb42742cb0d17df`.
- Contrato v1: `f54b7b5af8aa309c7591f6314f35080c64f86db1ff4807069a930b5c8c8011fc`.

Resultado real del evaluador: **código 1**, con este cierre de `unittest`:

```text
Ran 14 tests in 2.904s

FAILED (failures=26)
```

Son 14 métodos de prueba: **2 correctos y 12 con fallos**. El total de 26
cuenta también las variantes fallidas de `subTest`; no significa que se
ejecutaran 26 métodos ni que hubiera 26 defectos independientes. No hubo errores
del evaluador, omisiones ni `expectedFailure`.

| Comprobación | Resultado inicial |
| --- | --- |
| `test_01`: texto predeterminado sobre evidencia sintética completa | Correcta: consulta 0, resumen textual y stderr vacío. |
| `test_02`: equivalencia del texto explícito, con y sin incidencia | Dos variantes fallidas: `--format text` devuelve 2; el modo predeterminado devuelve 0 y 1 respectivamente. |
| `test_03` a `test_13`: JSON completo, ejecución fallida, ausencias, tipos, JSON inválido, materiales enlazados e intento parcial | Once métodos con 24 aserciones fallidas: `--format json` devuelve 2, en vez del 0 o 1 exigido por cada consulta. |
| `test_14`: argumentos incorrectos | Correcta: código 2, stdout vacío y diagnóstico en stderr en sus siete variantes. |

La causa es la **opción todavía inexistente**: el parser de la implementación
base solo admite `--run` (además de la ayuda). Los diagnósticos JSON conservados
incluyen `unrecognized arguments: --format json`. Las aserciones posteriores
sobre el esquema y sus valores no pudieron alcanzarse; este resultado no
valida una implementación JSON ni demuestra que todas las demás condiciones
sean correctas. El rechazo de argumentos incorrectos tampoco demuestra que
la nueva opción esté disponible.

Las comparaciones del árbol temporal se ejecutaron después de cada consulta,
antes de las aserciones de formato/código, y no detectaron cambios. No se ejecutó
el código de los materiales sintéticos ni se consultaron registros personales.
Los informes sintéticos se construyeron como datos, sin fingir ejecuciones de
agentes. No hubo llamadas al modelo ni repetición del experimento del revisor.

No se repitió la suite habitual de `tests/`: código y pruebas anteriores siguen
intactos. Esta aceptación inicial fallida está separada de las 153 pruebas del
hito anterior y del CI; no cambia sus resultados históricos ni se añade a su
descubrimiento. Los fallos se mantienen como referencia para el futuro trabajo,
sin implementar la funcionalidad ni rebajar las comprobaciones para obtener verde.

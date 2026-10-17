# Demo del inspector sin modelo

Estos tres registros estáticos permiten explorar `inspect_run.py` con Python 3
y su biblioteca estándar, desde un clon y sin credenciales, Codex ni `runs/`.
No hay instalación ni generación previa de materiales.

**Procedencia:** todos los registros, dictámenes, contadores, duraciones,
declaraciones de integridad e informes son datos sintéticos preparados para
demostración. No proceden de ejecuciones de agentes ni acreditan pruebas
realmente ejecutadas. Esta declaración también está en
[metadatos.json](metadatos.json) y se aplica a los tres escenarios completos.
Solo sirven para consultar con `inspect_run.py`: **no son registros autorizados
para reparar o revisar candidatos**.

## Consultas

Ejecuta desde la raíz del repositorio:

```bash
python3 -B inspect_run.py --run examples/inspect_run/aprobada
python3 -B inspect_run.py --run examples/inspect_run/aprobada --format json
python3 -B inspect_run.py --run examples/inspect_run/fallo_agente
python3 -B inspect_run.py --run examples/inspect_run/fallo_agente --format json
python3 -B inspect_run.py --run examples/inspect_run/incompleta
python3 -B inspect_run.py --run examples/inspect_run/incompleta --format json
```

En Bash, `echo $?` inmediatamente después de cada consulta muestra el código
del inspector. El **1** de las dos últimas consultas es deliberado.

| Escenario | Estado registrado / código | Consulta / código del inspector |
| --- | --- | --- |
| [aprobada](aprobada/resultado.json) | `aprobada` / 0 | `completada` / 0 |
| [fallo_agente](fallo_agente/resultado.json) | `fallo_agente` / 3 | `completada` / 0 |
| [incompleta](incompleta/resultado.json) | `aprobada` / 0 | `incompleta` / 1 |

`aprobada` representa un intento: informe inicial con un fallo de aserción entre
dos pruebas, desarrollo, informe posterior con dos resultados correctos,
dictamen `aprobar` y transición a aprobación. El texto muestra esos recuentos,
dos invocaciones registradas y `Consulta: completada (código 0)`.

`fallo_agente` conserva el mismo informe inicial y registra una invocación del
desarrollador terminada con código 9. La reparación y la ejecución general
registran código 3; las pruebas posteriores figuran como `no_ejecutadas`, con
código `null`, y no hay revisión. El inspector completa la lectura con código 0.

`incompleta` contiene los mismos resúmenes que `aprobada`, pero falta
deliberadamente `reparacion/posterior/stderr.txt`. El texto conserva el estado
registrado, el intento, las pruebas iniciales y el dictamen; indica recuentos
posteriores desconocidos y explica la ausencia en stderr.

En JSON se obtiene un único objeto con `consulta`, `ejecucion` y
`version_esquema: 1`, también al devolver código 1. Las incidencias quedan en
`consulta.incidencias` y stderr está vacío. `consulta.codigo_salida` coincide
con el código del proceso inspector; `ejecucion.codigo_salida` conserva el
del registro. La información disponible de `ejecucion` permanece en la consulta
incompleta. El [esquema JSON v1](../../tasks/003-inspect-run-json.md) resume la
ejecución; los detalles por etapa y los recuentos de pruebas se muestran en texto.

## Materiales y límites

Cada escenario es independiente. `resultado.json` contiene el resumen general
y las etapas; `reparacion/resultado.json`, `revision/resultado.json` y los
resúmenes de evaluación repiten exactamente los objetos enlazados correspondientes.
Las rutas `registro` son relativas al directorio del escenario, por lo que se
puede mover la carpeta o consultar desde otro directorio. La salida puede mostrar
rutas absolutas calculadas a partir de la ubicación local.

Los `stderr.txt` son texto sintético con el formato de informe que lee el
inspector. Sus dos identificadores coinciden con los métodos declarados en
`reparacion/referencia/test_solution.py`. Esa referencia solo sirve para lectura
mediante AST; incluye una guarda que impide importarla o ejecutarla por accidente.
**No ejecutes las referencias ni el código contenido en estos ejemplos.**
`demo_inspector` es una etiqueta sintética de caso, no un caso del benchmark.

Solo se incluyen los materiales que necesita esta consulta. Las menciones
genéricas del inspector a candidatos, diffs, sesiones, contratos o materiales
de revisión no implican que existan aquí. En `fallo_agente` tampoco hacen falta
archivos de evaluación posterior ni de revisión, pues esas etapas no se ejecutaron
en el relato sintético. No se incluyen hashes ni evidencia para autorizar
reparaciones o revisiones.

La demo permite observar lectura, coherencia de resúmenes, contraste estático
de informes y conservación de datos ante una ausencia. No demuestra corrección
de candidatos, calidad de agentes ni pruebas realmente ejecutadas. El inspector
no recalcula hashes ni modifica estos materiales.

## Pruebas de integración

Desde la raíz:

```bash
python3 -B -m unittest discover -s tests -p 'test_inspect_demo.py' -v
```

Las cuatro pruebas nuevas consultan los ejemplos por CLI en texto y JSON,
comprueban los estados, códigos, canales e inmutabilidad, y prueban una copia
movida sin `tests/`, `runs/` ni Codex en `PATH`. Solo ejecutan el inspector.
También entran en `python3 -B -m unittest discover -s tests -v`.
Son validaciones de la demo, separadas de las **238 pruebas históricas**
documentadas en el README; los dos resultados de cada informe sintético no son
pruebas ejecutadas ni se suman a esas cifras.

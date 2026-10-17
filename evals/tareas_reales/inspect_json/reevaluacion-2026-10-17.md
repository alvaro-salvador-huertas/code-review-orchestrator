# Reevaluación del mismo candidato de inspect-json

**17 de octubre de 2026, Europe/Madrid.** La aceptación revisada supera **14/14
métodos**, y las comprobaciones específicas del evaluador **6/6**, ambas con
código 0. Se reutiliza la regresión histórica de **153/153**, sin ejecutarla
otra vez. **Cero invocaciones nuevas de agentes.** La entrega sigue sin
aplicarse al inspector original y la revisión independiente está pendiente.

Rama: `eval/inspect-json-primer-intento`; HEAD
`5c7950dfea8fe5481183fcda7c551ec3c3ea55ac`. Se conservan los cambios documentales
pendientes de la preparación, sin commit ni push.

## Secuencia y evidencia histórica

1. La [preparación sin ejecución](primer-intento-2026-10-17.md) detectó la
   restricción de red antes del lanzamiento: cero invocaciones y ningún
   registro de intento. Ese informe conserva su alcance histórico.
2. El primer intento real se ejecutó después, entre **18:09:46 y 18:15:16
   CEST** (16:09:46–16:15:16 UTC). El desarrollador tuvo una invocación y terminó
   con código 0 en 227,691 s. El controlador completó el flujo y devolvió
   **`no_supera_comprobaciones`, código 1**. Su registro permanece intacto:
   [registro de origen](../../../runs/20261017T160946Z_inspect-json_48a800c7c6fc4967a26c592b57f754c5/resultado.json).
3. El diagnóstico contrastó las dos aserciones posteriores con el contrato,
   el evaluador y la entrega, sin ejecutar el candidato. Ambos fallos exigían
   una cadena literal que el contrato no prescribe.
4. La reevaluación autorizada se ejecutó una sola vez el mismo día, a las
   **18:27:35–18:27:37 CEST** (16:27:35–16:27:37 UTC), con el evaluador revisado
   y exactamente la misma entrega. Resultado:
   **`supera_aceptacion_revisada_y_comprobaciones`, código 0**.

Registro nuevo, identificado como `reevaluacion_mismo_candidato_evaluador_revisado`:

```text
runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4
```

Su [resultado](../../../runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4/resultado.json)
y [procedencia](../../../runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4/procedencia.json)
distinguen las evaluaciones nuevas de la regresión reutilizada. Los enlaces a
`runs/` son evidencia local excluida de Git; no estarán disponibles en un clon
que no conserve esos registros.

## Motivo y alcance exacto del ajuste

El [contrato congelado](../../../runs/20261017T160946Z_inspect-json_48a800c7c6fc4967a26c592b57f754c5/referencia/contrato.md)
exige identificar el campo/contexto o archivo afectado y declara que la
redacción exacta de las incidencias no forma parte del esquema. Para
`duracion_segundos: true` y `duracion_segundos: -0.5`, el candidato devolvió
el valor proyectado `null`, consulta incompleta y código 1. Las comprobaciones
de JSON, canales y valores terminaron correctamente antes de la aserción fallida.

En el candidato, las líneas 268–275 conservan la validación de la base: rechazan
booleanos, números negativos y valores no finitos, añadiendo
`general: duración inválida`. El evaluador buscaba literalmente
`duracion_segundos` en ese mensaje. El rechazo documentado es una exigencia
adicional del evaluador, no evidencia de que el candidato aceptase esas
duraciones como válidas.

En el [evaluador del árbol actual](evaluar.py) se añade `import re` y se cambia
únicamente la comprobación del diagnóstico dentro de `test_10`:

```diff
                     issues = self.assert_json(expected, 1)
-                    self.assertTrue(any(source in issue for issue in issues))
+                    if source == "duracion_segundos":
+                        self.assertRegex("\n".join(issues), r"\b(?:duración|duracion_segundos)\b")
+                    else:
+                        self.assertTrue(any(source in issue for issue in issues))
```

Los límites de palabra evitan aceptar nombres de otros campos como
`duracion_segundos_extra` o `preduración`. La búsqueda para los demás campos
permanece idéntica. No se toca `assert_json`: continúa comprobando valores
exactos, tipos, `null`, esquema, códigos, estado, incidencias y stderr vacío.
También permanecen la CLI, las comprobaciones de registros sintéticos,
los marcadores contra ejecución accidental y la comparación de sus metadatos.

Las [comprobaciones específicas](../../../tests/test_inspect_json_evaluator.py)
ejercitan el método real del evaluador con respuestas CLI controladas:

- Admiten los diagnósticos que contienen `duración` o `duracion_segundos`.
- Rechazan mensajes genéricos que no identifican el campo.
- Rechazan referencias únicamente a otro campo, incluidos nombres más largos
  que contienen esas cadenas.
- Rechazan respuestas que conservan `true` o `-0.5` como duración, aunque el
  diagnóstico use cualquiera de las dos denominaciones admitidas. El rechazo
  ocurre en la comparación de valores, antes de comprobar el mensaje.
- Comprueban que el alias no se aplique a otros campos, como `max_intentos`.

Son seis métodos de prueba. Los fallos deliberados de las respuestas simuladas
se verifican dentro de ellos; no son fallos de la suite ni `expectedFailure`.
Estas comprobaciones no ejecutan el candidato ni invocan modelos.

## Copias, procedencia y hashes

La base sigue siendo **`9bec53279d82058fe188c0038bab5ba66ce64003`**. Se comprobaron
los 42 archivos de la referencia contra sus hashes y objetos Git. La copia
temporal se reconstruyó desde esa referencia y recibió únicamente
`entrega/inspect_run.py` del registro de origen. Su inventario coincidió con
el workspace entregado en el primer intento: mismos archivos, tipos, permisos
y contenido. Los otros 41 archivos de la base permanecen iguales.

| Material | SHA-256 |
| --- | --- |
| Candidato del registro original | `901ad474e8928253abba00a22aa44be2d7db2aa22fc8b9d219d78c59a799d43e` |
| Candidato copiado y evaluado de nuevo | `901ad474e8928253abba00a22aa44be2d7db2aa22fc8b9d219d78c59a799d43e` |
| Contrato, sin cambios | `f54b7b5af8aa309c7591f6314f35080c64f86db1ff4807069a930b5c8c8011fc` |
| Evaluador anterior | `61bb184289eeb837f6aaf0c1d0688d31130515e8f1c3b7e35fb42742cb0d17df` |
| Evaluador revisado | `5b22e026bf3685fe592202cfe6bbea6af9a742595443d69876d354c9f8405530` |
| Diff entre evaluadores | `60ccd03c8decd7a4f21f8f83f57bd09b42b47552205bfcd192268aff7da4115e` |
| Adaptador de pruebas, sin cambios | `b6dac8e0e705fac17a7356c061d6ac37bb11d7b0533b9e2067afe7d190794a68` |
| Comprobaciones específicas | `1e5c441066fb6c218966c3d4a0059fc52f757af7253ef62c75c944f6f204ec29` |
| `resultado.json` del intento original, sin cambios | `cd6aeb7cb19c107de30bc9baf129b952a03df858cbff4068f0aee75e3845c8a9` |

El registro nuevo conserva ambos evaluadores y su diff, contrato, proyecto
base, procedencia original, candidato, inventarios y las comprobaciones
específicas congeladas. El inspector original mantiene SHA-256
`c4122912020f0e363655b0354614f3507b263c96f7b0c6304faafc27e2fe422b`.

## Ejecuciones nuevas y regresión reutilizada

Se reutilizaron `project_test_runner.py` y las utilidades existentes de captura
de procesos y contraste de informes. El guion puntual se conserva dentro del
registro; no se añadió un controlador general al proyecto ni se ejecutó
`repair_project.py inspect-json`.

Los comandos efectivos, cwd, canales, códigos, límites y duraciones constan en
[aceptación/resultado.json](../../../runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4/aceptacion/resultado.json)
y [comprobaciones/resultado.json](../../../runs/20261017T162735Z_inspect-json_reevaluacion_f888f94587924a7a9281f690479fb9b4/comprobaciones/resultado.json).
La aceptación usa el adaptador congelado con `--project` apuntando a la copia
temporal, `--report` al registro nuevo y `--acceptance` al evaluador revisado.
La segunda llamada usa el mismo adaptador sobre una copia que contiene
únicamente los seis métodos específicos y el evaluador revisado. Ambas emplean
`python3 -B` y límite de 60 s. Cada una se ejecutó **una vez**.

| Evidencia | Métodos correctos / total | Métodos con fallos | Aserciones fallidas (de subtests) | Código |
| --- | --- | --- | --- | --- |
| Histórica: aceptación inicial del intento | 2/14 | 12 | 26 (20) | 1 |
| Histórica: regresión inicial del intento | 153/153 | 0 | 0 (0) | 0 |
| Histórica: aceptación posterior del intento | 13/14 | 1 | 2 (2) | 1 |
| Histórica reutilizada: regresión posterior del intento | 153/153 | 0 | 0 (0) | 0 |
| Nueva: aceptación con evaluador revisado | 14/14 | 0 | 0 (0) | 0 |
| Nueva: comprobaciones específicas del evaluador | 6/6 | 0 | 0 (0) | 0 |

Las cuatro evaluaciones históricas pertenecen al registro de origen. La nueva
aceptación duró **1,668 s de proceso** (1,568 s según `unittest`); las
comprobaciones específicas, **0,114 s de proceso** (0,035 s según `unittest`).
No hubo errores, omisiones ni éxitos inesperados. Los informes estructurados
se contrastaron con las identidades AST y los cierres textuales.

La regresión posterior histórica se conserva en `regresion_historica/`, con
sus cinco archivos idénticos a los de origen. `ejecutada_ahora: false` evita
presentarla como nueva. Candidato, pruebas, adaptador y resto del proyecto
evaluado coinciden; el evaluador externo no forma parte de los 42 archivos de
la base ni de esa regresión. No se identificó una razón para repetir los 153
métodos. Tampoco se ejecutó la suite completa actual del controlador.

## Integridad y alcance del resultado

Se verificaron ahora los inventarios y hashes conservados de referencia,
evaluación inicial, agente y entrega del origen. El registro original no
incluye los resultados posteriores en `evidencia_sha256`: su coherencia se
contrastó mediante informes y resúmenes, sin atribuirles un hash histórico
inexistente. Los hashes de su copia reutilizada se fijan en el registro nuevo.

Los registros previos se inventariaron antes y después de la reevaluación,
incluyendo permisos y mtime, sin atime: permanecen intactos. Durante las nuevas
pruebas también permanecieron intactos el proyecto original, las referencias
y la copia evaluada. Las posteriores ediciones documentales autorizadas se
comprueban por separado. Estas comparaciones acreditan el estado conservado;
no son una certificación de seguridad de acciones transitorias.

Se revisaron el diff y los enlaces locales. Solo se cambian el evaluador,
se añaden sus comprobaciones específicas y se actualiza la documentación.
Contratos, pruebas anteriores, controladores, candidato, inspector original
y registros históricos se conservan. `runs/` sigue excluido y sin archivos
versionados. No se repiten suites tras los ajustes documentales.

La aceptación nueva no borra el rechazo histórico ni demuestra corrección
para todas las entradas. **La revisión independiente continúa pendiente**;
no se conectó al revisor ni se pasó el registro a `review_case.py`. La entrega
permanece separada del proyecto original para decidir su revisión e
incorporación posterior.

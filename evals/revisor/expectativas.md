# Expectativas del evaluador

**No entregar este archivo ni las comprobaciones adicionales al revisor.**
Los dictámenes de esta tabla son expectativas derivadas de los contratos y del
código preparado, no respuestas de un modelo. Los candidatos conservan nombres
neutros; el vínculo entre identificador, caso y expectativa queda aquí.

| Caso | Candidato | Dictamen esperado | Requisito del contrato | Dictamen observado del modelo |
| --- | --- | --- | --- | --- |
| `case_01` | [candidato_01](candidatos/candidato_01.py) | `aprobar`, sin hallazgos | Acumular por nombre exacto, distinguir mayúsculas, conservar la entrada y no realizar E/S. | Pendiente |
| `case_01` | [candidato_02](candidatos/candidato_02.py) | `solicitar_cambios` por comparación de nombres | `Python` y `python` deben ser asignaturas distintas. | Pendiente |
| `case_02`, v2 | [candidato_03](candidatos/candidato_03.py) | `aprobar`, sin hallazgos | Prioridades timeout → fallo de ejecución → respuesta vacía → completada; pureza. | Pendiente |
| `case_02`, v2 | [candidato_04](candidatos/candidato_04.py) | `solicitar_cambios` por prioridad del timeout | Si `tiempo_agotado=True`, devolver `tiempo_agotado` incluso con código `None`. | Pendiente |

Referencias: [contrato 01](../../tasks/001-sum-by-subject.md) y
[contrato 02, versión 2](../../tasks/002-classify-run.md).

## Caso 01: comparación exacta

Entrada discriminante, en este orden:

```python
[
    {"asignatura": "Python", "minutos": 20},
    {"asignatura": "python", "minutos": 15},
    {"asignatura": "Python", "minutos": 5},
    {"asignatura": "Redes", "minutos": 7},
]
```

El contrato exige `{"Python": 25, "python": 15, "Redes": 7}`.
En la comprobación local, `candidato_01` devolvió ese resultado y `candidato_02`
devolvió `{"Python": 40, "Redes": 7}`. La segunda comprobación usa primero
`python` con 15 minutos, después `Python` con 20, `python` con 5 y `Redes`
con 7: exige `{"python": 20, "Python": 20, "Redes": 7}`, mientras
`candidato_02` produce `{"python": 40, "Redes": 7}`.

**Fundamento en el código:** `candidato_01` usa cada nombre sin transformarlo
como clave y suma sobre un diccionario nuevo. La entrada vacía no entra en el
bucle y devuelve `{}`; solo lee la lista y sus diccionarios, sin E/S.
`candidato_02` cambia únicamente la identidad de las asignaturas: aplica
`lower()` y `setdefault()` conserva el nombre de la primera aparición.
Acumula correctamente los minutos, pero reúne variantes de mayúsculas bajo
esa primera clave. No modifica la entrada ni realiza E/S. Las cuatro pruebas
originales no incluyen dos nombres que difieran solo en mayúsculas.

Las comprobaciones adicionales contrastan ambos resultados completos, incluidas
las sumas, la asignatura `Redes` y la conservación de la entrada en los dos órdenes.
No basta con que el resultado difiera del contrato: debe coincidir exactamente
con el comportamiento previsto para cada candidato.

## Caso 02: prioridad del timeout

Ejemplo discriminante: `clasificar_ejecucion(None, None, tiempo_agotado=True)`.
El contrato v2 exige `"tiempo_agotado"`. En la comprobación local,
`candidato_03` devolvió ese valor y `candidato_04` devolvió `"fallo_ejecucion"`.

**Fundamento en el código:** `candidato_03` resuelve primero el timeout; después
el código ausente o distinto de cero; después `None`, cadena vacía o caracteres
de espacio en blanco según `str.isspace()`; finalmente devuelve `completada`.
`candidato_04` adelanta solo el retorno para `codigo_salida is None`, antes del
timeout. Por eso cambia el resultado únicamente cuando coinciden código `None`
y timeout verdadero; para código entero mantiene las prioridades y para `None`
sin timeout conserva `fallo_ejecucion`. Ambas funciones son puras y usan el
mismo criterio de espacios en blanco. Las dieciséis pruebas originales no
combinan código `None` con timeout verdadero.

La tabla adicional cruza códigos `None`, `0` y `1`, ambos valores de timeout y
respuestas `None`, `""`, `"\t\u00a0"` y `"texto"`: 24 combinaciones por
candidato. Exige cuatro discrepancias exactas de `candidato_04`, todas con
código `None` y timeout verdadero, y ninguna en las otras veinte combinaciones.
Exige cero discrepancias de `candidato_03`. Esta tabla finita complementa el
razonamiento sobre las ramas; no prueba por sí sola todos los valores admitidos.

Los dos ejemplos fallidos del caso 01 y las cuatro combinaciones fallidas del
caso 02 son seis manifestaciones de **dos defectos preparados**, no seis defectos
independientes. Tampoco equivalen a seis detecciones realizadas por el revisor.

## Comprobación local de la preparación

El 16 de octubre de 2026, con Python 3.12.3, se ejecutó una sola vez desde la raíz:

```bash
python3 -B -m unittest discover -s tests -v
```

Resultado: **132 pruebas correctas en 40,883 s, código 0**. Incluye las seis
pruebas nuevas y las 126 de regresión existentes; no se repitió el bloque nuevo
por separado. Los informes de los procesos hijos acreditaron todas las pruebas
originales, sin omisiones, y las observaciones adicionales coincidieron con
los valores exactos documentados arriba:

| Candidato | Pruebas originales | Comprobaciones adicionales respecto al contrato |
| --- | --- | --- |
| `candidato_01` | 4/4, código 0 | 2/2 entradas discriminantes conformes; entrada intacta. |
| `candidato_02` | 4/4, código 0 | 2 discrepancias previstas: agrupa `Python`/`python` y conserva el primer nombre en ambos órdenes; entrada intacta. |
| `candidato_03` | 16/16, código 0 | 24/24 combinaciones conformes, incluidas las 4 con timeout y código `None`. |
| `candidato_04` | 16/16, código 0 | 4 discrepancias previstas con timeout y código `None`; las otras 20 combinaciones son conformes. |

La suite confirma los defectos preparados con aserciones sobre sus resultados
exactos, sin `expectedFailure` ni ocultar errores de proceso. **No hubo llamadas
reales al modelo**: estos resultados son comprobaciones locales de candidatos y
del controlador, no una evaluación del revisor. Todos los dictámenes observados
del modelo siguen pendientes.

# Tarea real 008: consultas de disponibilidad por lotes

**Versión 1 — preparación manual posterior a un borrador de planificación.**

Base: `9017d6ca212af4447c02da22c0bcd9a5364f6924`

## Entrega y límites

Crear únicamente `booking_batch.py` en la raíz, archivo regular **0644**,
inicialmente ausente. No fabricar un original vacío. Se protegen
`booking_core.py`, `check_booking.py`, `booking_http.py`, controlador, pruebas,
autoridades y los demás archivos. Usar biblioteca estándar y `booking_core`;
sin dependencias nuevas, red, subprocesses propios, persistencia, HTTP ni
creación de reservas. No modificar entradas ni mantener estado entre consultas.

## CLI y entrada

```bash
python3 -B booking_batch.py [--] archivo
```

Exactamente una ruta literal, relativa al cwd del invocador o absoluta. `-`
designa un archivo llamado `-`, nunca stdin. Las demás rutas que empiezan por
guion requieren `--`. Fuera de la ayuda, solo son válidas las formas `archivo`
y `-- archivo`. `-h` o `--help` muestran ayuda **solo como único argumento**:
stdout no vacío, stderr vacío y código 0. `-- -h` y `-- --help` son archivos.
Falta de ruta, argumentos adicionales y opciones desconocidas: código 2,
stdout vacío y diagnóstico útil en stderr. No se exige una frase literal.

Leer un archivo UTF-8 estricto sin BOM, con un único documento JSON y raíz
lista, incluida `[]`. Admitir espacio JSON exterior. Rechazar JSON inválido o
concatenado, NaN, Infinity, -Infinity y claves duplicadas a cualquier profundidad,
incluidas las equivalentes después de decodificar escapes como `id` y `\u0069d`.

## Delegación e independencia

Cada elemento completo se entrega sin alteraciones a
`booking_core.check_booking(document)`. Se heredan el dominio del
[005](005-check-booking.md) y la API del [006](006-booking-core.md): documentos
con `solicitud` y `reservas`, claves y tipos exactos, fechas UTC estrictas con Z,
intervalos positivos `[inicio, fin)`, comparación literal, validación total y
conflictos en orden de entrada. No duplicar ni modificar esas reglas.

Las consultas son independientes: conservar orden y repeticiones. El mismo ID
en consultas distintas es válido si cada documento lo es. No calcular conflictos
entre consultas ni imponer unicidad entre ellas. Dentro de una consulta, IDs
duplicados producen `booking_core.InvalidInput` según el núcleo protegido; el
envoltorio lo comunica como error de esa consulta, sin corregir ni deduplicar.

## Salida y errores

Acumular resultados antes de comenzar a escribir stdout: leer, decodificar y
validar el lote completo. Éxito: código 0, stderr vacío y un único documento JSON
UTF-8 en stdout, terminado en salto de línea, cuya raíz sea la lista de resultados
exactos del núcleo en orden. Cada resultado contiene `disponible` booleano y
`conflictos` lista de identificadores. Admitir representaciones JSON equivalentes,
escapes ASCII y cualquier orden de claves; no imponer espacios concretos. No
añadir metadatos, progreso ni otros textos.

Errores de apertura/lectura, UTF-8, JSON, raíz o dominio: código 1, **stdout
vacío** y diagnóstico útil en stderr. En errores de dominio se identifica la
posición de la consulta, empezando en 1, y la causa; no se exige redacción literal.
No se exige continuar tras el primer error. Un error en la última consulta
tampoco permite resultados parciales. La garantía se refiere a errores de
entrada, no a atomicidad frente a un fallo del sistema al escribir stdout.

Importar el módulo no abre entradas, lee stdin, produce salida, inicia la CLI,
procesos o conexiones ni escribe archivos propios. Las lecturas normales del
importador para cargar el módulo y sus dependencias están permitidas. No se
exige helper público, sintaxis concreta de importación, API adicional o nuevos
límites del lote.

## Ejemplos y aceptación

Todas las entradas de prueba son sintéticas, sin registros privados.

| Entrada | Resultado esperado |
| --- | --- |
| `[]`, también con espacio JSON exterior | `[]` y salto final, código 0. |
| Consulta de A 10:00–11:00 sin reservas; otra con reservas r2 10:15–10:45 y r1 10:30–11:30 de A, fechas válidas del mismo día | Lista: disponible verdadero/conflictos vacíos; disponible falso/conflictos `["r2","r1"]`. |
| Dos consultas iguales, o mismo ID en consultas distintas válidas | Dos resultados, sin deduplicar ni mezclar consultas. |
| Reservas que terminan al comienzo o empiezan al final de la solicitud | Sin conflictos, por delegación de los extremos del intervalo. |
| Tercera consulta inválida tras dos válidas | Código 1; stderr identifica consulta 3 y causa; stdout vacío. |
| IDs duplicados dentro de una consulta | Código 1, posición y causa del error del núcleo. |
| BOM, UTF-8 inválido, raíz no lista, constantes, duplicados o documentos concatenados | Código 1, diagnóstico útil y stdout vacío. |
| `-- -h` con archivo `-h` que contiene `[]` | Resultado del lote, no ayuda. |

El [evaluador independiente](../evals/tareas_reales/booking_batch/evaluar.py)
acepta `--project`, usa un único runner unittest e identidades explícitas. CLI,
importación y delegación se observan exclusivamente en hijos, con intérprete
absoluto, `-B`, entorno `evaluation`, cwd temporal y plazo de 10 s por hijo.
Las utilidades proceden de autoridades, nunca del candidato. Ausencia, enlace,
archivo especial o modo incorrecto se detectan mediante aserciones antes de
ejecutar producto. Las sondas no son aislamiento de seguridad y no sustituyen
la lectura contractual completa del revisor.

La [configuración v2](config/booking-batch.json) fija 300 s por desarrollo y
revisión, 120 s de aceptación, 600 s de regresión, 30 s de inventario y 10 s por
consulta previa CLI. El recorrido previsto admite como máximo dos intentos,
un desarrollo y una revisión por intento, sin reintentos técnicos. Esta
preparación no consume reservas ni autoriza el experimento. Véase la
[guía de preparación](../evals/tareas_reales/booking_batch/README.md).

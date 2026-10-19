# Tarea real 005: disponibilidad de reservas

**Versión 1 — 19 de octubre de 2026. Preparación; implementación pendiente.**

Base: `b54e352b3abba5a0075b512fdd84c0094cee44fa`

Primera tarea real preparada para la vía declarativa `--task-config`. El único
archivo editable será **`check_booking.py`**, inicialmente ausente en esa base.
Será una consulta local reutilizable como componente de una futura API; esta
tarea no crea una API, almacena reservas ni garantiza exclusión concurrente.

## Interfaz y documento de entrada

```bash
python3 -B check_booking.py solicitud.json
```

Exactamente un argumento posicional: la ruta de un archivo UTF-8 sin BOM, sin
exigir extensión. Las rutas relativas se interpretan desde el cwd del invocador.
El archivo contiene un único objeto JSON; se admite espacio JSON antes y después.
No se leen documentos de stdin. `--` termina las opciones y permite rutas que
empiecen por guion. Solo se admiten `-h` y `--help`, sin abreviar opciones.

Claves exactas, todas obligatorias, sin otras claves en ninguno de los objetos:

| Objeto | Claves | Tipos |
| --- | --- | --- |
| Raíz | `solicitud`, `reservas` | Objeto, lista, respectivamente |
| `solicitud` | `recurso`, `inicio`, `fin` | Tres cadenas |
| Cada elemento de `reservas` | `id`, `recurso`, `inicio`, `fin` | Cuatro cadenas |

`reservas` puede estar vacía. Sus elementos son objetos, nunca listas ni `null`.
No se convierten números, booleanos, `null` ni otros tipos a cadenas.

`recurso` e `id` deben contener al menos un carácter no blanco (espacio en
blanco según `str.isspace`). Las cadenas válidas se conservan literalmente,
incluidos espacios, comillas, saltos de línea y Unicode. Los recursos se comparan
exactamente: distinguen mayúsculas, espacios y representaciones Unicode; no se
recortan ni normalizan. Los identificadores deben ser únicos en **toda** la
lista, también entre recursos diferentes, por esa misma igualdad literal.

`inicio` y `fin` tienen exactamente el formato ASCII `YYYY-MM-DDTHH:MM:SSZ`,
con ceros de relleno y `T`/`Z` mayúsculas. Son fechas válidas del calendario
gregoriano, años `0001` a `9999`, horas `00`–`23`, minutos y segundos `00`–`59`.
Todas son UTC. No se admiten año cero, fechas imposibles, segundos intercalares,
offsets, fracciones, fechas sin zona, espacios adicionales ni dígitos no ASCII.
En la solicitud y en cada reserva, `fin` debe ser estrictamente posterior a
`inicio`. No se relacionan las fechas con el reloj actual.

Se rechazan claves duplicadas a cualquier profundidad, incluidas claves
equivalentes tras decodificar escapes JSON; JSON truncado o inválido, documentos
concatenados, UTF-8 inválido, raíz no objeto y constantes `NaN`/`Infinity`.

## Disponibilidad y salida

Los intervalos son **[inicio, fin)**. Una reserva genera conflicto si, y solo si:

- Su `recurso` es exactamente el de la solicitud.
- Su inicio es anterior al fin de la solicitud y su fin es posterior al inicio
  de la solicitud.

Una reserva que termina en el inicio solicitado o comienza en su fin es
adyacente, sin conflicto. Las reservas existentes pueden solaparse entre sí:
esto no invalida el documento. Se validan **todas** las reservas, incluidas las
de otros recursos y las posteriores a un conflicto encontrado.

Solo después de validar el documento completo se escribe un único objeto JSON
UTF-8 en stdout, sin Markdown ni texto adicional. Se permite cualquier espacio
JSON exterior, orden de claves y representación JSON equivalente de las cadenas.
Claves exactas de salida:

| Campo | Regla |
| --- | --- |
| `disponible` | Booleano; verdadero si y solo si `conflictos` está vacía. |
| `conflictos` | Lista de los `id` conflictivos, literales y en su orden original. |

No se ordenan ni deduplican resultados. Los identificadores duplicados son una
entrada inválida, no una situación que deba corregir la herramienta.

## Canales, códigos y conservación

| Código | Resultado |
| --- | --- |
| `0` | Consulta válida, con o sin conflictos: objeto JSON en stdout y stderr vacío. |
| `1` | Archivo ausente, ilegible o entrada inválida: stdout vacío y diagnóstico en stderr que identifique archivo y causa. Un directorio no es un archivo de entrada. |
| `2` | Argumentos incorrectos: stdout vacío y diagnóstico en stderr. Incluye falta o exceso de posicionales, opciones desconocidas y abreviaturas. |

`-h` y `--help` sin archivo muestran ayuda no vacía en stdout, stderr vacío y
código `0`. No se exige una redacción literal de ayuda ni diagnósticos.
Un conflicto de reservas no es un error de consulta y no produce código `1`.

Solo biblioteca estándar. No modificar entradas ni otros archivos, crear
reservas, importar o ejecutar contenido de entrada, consultar servicios, usar
red o leer credenciales/configuración personal. La herramienta no necesita
credenciales. El único efecto observable de una consulta son sus canales y
código de salida; tampoco debe generar cachés en el proyecto o junto a entradas.

## Ejemplos sintéticos

Todos los datos siguientes son inventados, no registros de un servicio.

Solicitud común: recurso `Sala Norte`, desde `2026-10-20T10:00:00Z` hasta
`2026-10-20T11:00:00Z`.

```json
{
  "solicitud": {
    "recurso": "Sala Norte",
    "inicio": "2026-10-20T10:00:00Z",
    "fin": "2026-10-20T11:00:00Z"
  },
  "reservas": []
}
```

Resultado: `{"disponible": true, "conflictos": []}`, código `0`, stderr vacío.

Conservando esa solicitud, estas variantes de `reservas` tienen resultados
explícitos (todas las horas corresponden al mismo día UTC):

| Reservas, en orden de entrada | Resultado |
| --- | --- |
| `r-2`, Sala Norte, 10:30–11:30 | `{"disponible": false, "conflictos": ["r-2"]}` |
| `antes`, Sala Norte, 09:00–10:00; `despues`, Sala Norte, 11:00–12:00 | `{"disponible": true, "conflictos": []}` |
| `z`, Sala Norte, 09:30–10:30; `otro`, Sala Sur, 10:00–11:00; `a`, Sala Norte, 10:45–11:15 | `{"disponible": false, "conflictos": ["z", "a"]}` |

Cada reserva de la tabla se representa como objeto con sus cuatro claves, por
ejemplo `{"id":"r-2","recurso":"Sala Norte","inicio":"2026-10-20T10:30:00Z","fin":"2026-10-20T11:30:00Z"}`.
Una fecha imposible en `Sala Sur` invalidaría todo el documento: código `1`,
stdout vacío y diagnóstico de archivo y causa, aunque no comparta recurso.

## Alcance editable y aceptación

El futuro agente solo podrá crear `check_booking.py`, regular y modo **0644**,
o corregir ese mismo archivo durante un segundo intento. No se fabrica un
original vacío. Motor, inspectores, exportador, pruebas existentes, autoridades,
contratos, prompts, registros y configuración quedan protegidos.

El [evaluador externo](../evals/tareas_reales/check_booking/evaluar.py) usa
`--project <copia>`, consulta la CLI en hijos y nunca importa el candidato.
La futura entrega deberá superar aceptación y regresión de la base sin
modificarlas. El [registro declarativo](config/check-booking.json) conserva
los límites; la [guía de preparación](../evals/tareas_reales/check_booking/README.md)
separa comprobaciones locales, simulaciones y ejecución real pendiente.

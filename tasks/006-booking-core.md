# Tarea real 006: núcleo reutilizable de reservas

**Versión 1 — preparación de booking-core. Producto pendiente.**

Base: `2448d88a8fd89f73415140f3b789292df6a97482`

## Entrega y compatibilidad

Exactamente dos módulos Python editables en la raíz: `check_booking.py`,
existente y con el modo de la base Git (0644), y `booking_core.py`, inicialmente
ausente, que se creará como archivo regular 0644. No se fabrica un original vacío.
Solo biblioteca estándar; los demás archivos, pruebas y autoridades se conservan.

Se heredan íntegramente las reglas funcionales del
[contrato 005](005-check-booking.md). Su antiguo alcance editable queda sustituido,
**solo para esta tarea**, por los dos archivos anteriores. El contrato 005 y sus
autoridades no se modifican. Esta refactorización no añade HTTP, persistencia,
creación de reservas, concurrencia, dependencias externas ni otros agentes.

## API Python del núcleo

`booking_core.py` expone `InvalidInput`, subclase de `ValueError`, y
`check_booking(document)`. Recibe el documento Python ya decodificado; valida
íntegramente solicitud y reservas y devuelve exactamente
`{"disponible": booleano, "conflictos": lista_de_identificadores}`.

Se aplican las claves obligatorias y exclusivas y tipos del contrato 005, sin
coerción. Recursos e identificadores se conservan y comparan literalmente,
incluido Unicode y espacios; deben contener algún carácter no blanco. Los
identificadores son únicos en toda la lista, incluso entre recursos distintos.
Las fechas son UTC gregorianas válidas, estrictamente ASCII
`YYYY-MM-DDTHH:MM:SSZ`, años 0001–9999 y sin segundos intercalares. Cada intervalo
es positivo, `[inicio, fin)`: adyacencia no es conflicto; igualdad, contención y
solapamiento sí lo son para el mismo recurso. Se validan todas las reservas,
también las de otro recurso y las posteriores a un conflicto. Los conflictos
mantienen el orden de entrada; las reservas existentes pueden solaparse entre sí.

Todo documento de dominio inválido causa `InvalidInput` con una explicación no
vacía, sin exigir texto literal. El núcleo recibe datos decodificados: detectar
claves JSON duplicadas o codificación inválida corresponde a la CLI.

La función no modifica profundamente la entrada, tampoco antes de lanzar un
error; no imprime, lee stdin, escribe archivos, consulta servicios ni depende del
reloj. Las llamadas sucesivas no acumulan reservas ni conflictos ni comparten
resultados mutables, entre sí o con la entrada. Importar el módulo no inicia
consultas ni produce salida o escrituras propias. Las comprobaciones usan `-B`
para evitar las cachés del intérprete.

## CLI y nombres importables

```bash
python3 -B check_booking.py solicitud.json
```

Conserva toda la interfaz del contrato 005: un archivo UTF-8 sin BOM, documento
JSON único, claves duplicadas rechazadas a cualquier profundidad, argumentos,
`--`, ayuda, canales, códigos y conservación de entradas. Código 0 para consultas
válidas con o sin conflictos, 1 para errores de archivo o entrada (stdout vacío,
diagnóstico que identifique archivo y causa), 2 para argumentos incorrectos.

La CLI delega la validación del dominio y el cálculo en
`booking_core.check_booking`; no mantiene una segunda implementación independiente
de esas reglas. Decodificación JSON, errores de archivo y formato de respuesta
pertenecen a la CLI. Se conservan `check_booking.check_booking` e `InvalidInput`
como nombres importables delegados al núcleo. No se exige una sintaxis de import
concreta ni se convierten helpers privados en API pública. La compatibilidad no
exige diagnósticos textualmente idénticos ni una representación JSON particular
entre las equivalentes admitidas por 005.

## Evaluación y límites

El [evaluador externo](../evals/tareas_reales/booking_core/evaluar.py) admite
`--project`: la CLI y las importaciones de API se ejecutan solo en hijos con
intérprete absoluto, `-B`, entorno `evaluation`, cwd y timeout controlados.
**Importar una API ejecuta su código en ese hijo**; no es análisis estático ni
aislamiento de seguridad. El evaluador y el controlador no importan candidatos.
Las entradas son sintéticas y los resultados esperados explícitos.

La ausencia inicial del núcleo produce aserciones claras antes de importarlo;
las comprobaciones de la CLI original pueden superar la aceptación inicial.
La futura entrega debe superar aceptación y regresión congeladas del conjunto,
sin modificar criterios. El revisor contrasta ambos módulos y las reglas que una
sustitución controlada de delegación no puede acreditar por sí sola.

La [configuración v2](config/booking-core.json) fija 300 s por desarrollador y
revisor, 60 s de aceptación, 600 s de regresión, 30 s de inventario y 10 s por
consulta previa CLI. La [guía](../evals/tareas_reales/booking_core/README.md)
separa preparación, evidencias disponibles y experimento futuro pendiente.

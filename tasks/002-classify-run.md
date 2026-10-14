# Caso 002: clasificar una ejecución

**Versión 2 — 14 de octubre de 2026.**

## Contrato

Implementar `clasificar_ejecucion(codigo_salida, respuesta, tiempo_agotado=False)`.
La función se llama después de terminar o interrumpir una ejecución.

Se asumen estos tipos de entrada:

- `codigo_salida`: entero o `None`.
- `respuesta`: cadena de texto o `None`.
- `tiempo_agotado`: booleano; su valor predeterminado es `False`.

Debe devolver una cadena siguiendo este orden de prioridad:

1. Si `tiempo_agotado` es `True`, devuelve `"tiempo_agotado"`.
2. Si `codigo_salida` es `None` o distinto de cero, devuelve `"fallo_ejecucion"`.
3. Si el código es cero y `respuesta` es `None` o la cadena vacía, devuelve
   `"respuesta_vacia"`.
4. Si el código es cero y `respuesta` es una cadena no vacía cuyos caracteres
   son todos espacios en blanco según `str.isspace()` de Python (es decir,
   `respuesta.isspace()` devuelve `True`), devuelve `"respuesta_vacia"`.
   Esto incluye tabuladores, saltos de línea, retornos de carro, tabulación
   vertical, salto de página y espacios Unicode reconocidos por ese método,
   como el espacio no separable U+00A0.
5. Si el código es cero y la cadena contiene algún carácter que no sea espacio
   en blanco según ese criterio, devuelve `"completada"`, aunque esté rodeado
   de espacios en blanco.

Una ejecución `"completada"` significa que terminó técnicamente y produjo
texto; no certifica que la respuesta sea correcta.

La función debe ser pura: no debe ejecutar procesos, leer archivos, imprimir
ni llamar a modelos. No se requiere validación de tipos fuera del contrato.

## Aclaración respecto a la versión 1

La redacción anterior decía «espacios y saltos de línea» sin definir si
«espacios» abarcaba todos los caracteres de espacio en blanco. Permitía una
interpretación restringida que excluía tabuladores y otros caracteres Unicode.
La revisión del candidato de la versión 1 solicitó cambios por esa diferencia
de interpretación y motivó esta aclaración.

El usuario ha decidido adoptar el criterio de `str.isspace()` para todos los
caracteres de una cadena no vacía. `None` y la cadena vacía se contemplan por
separado; `"".isspace()` devuelve `False`. No cambian las prioridades del
tiempo agotado y del fallo de ejecución, los tipos admitidos ni la pureza.

Los contratos y resultados guardados en los registros históricos corresponden
a la versión 1 y se conservan sin modificaciones. Esta decisión no convierte
aquella solicitud de cambios en una aprobación ni en una evaluación de la
versión 2.

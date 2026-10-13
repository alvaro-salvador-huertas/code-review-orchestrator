# Caso 002: clasificar una ejecución

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
3. Si el código es cero y `respuesta` es `None`, está vacía o contiene únicamente
   espacios y saltos de línea, devuelve `"respuesta_vacia"`.
4. En otro caso, devuelve `"completada"`.

Una ejecución `"completada"` significa que terminó técnicamente y produjo
texto; no certifica que la respuesta sea correcta.

La función debe ser pura: no debe ejecutar procesos, leer archivos, imprimir
ni llamar a modelos. No se requiere validación de tipos fuera del contrato.

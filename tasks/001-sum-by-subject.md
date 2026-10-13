# Caso 001: sumar minutos por asignatura

## Contrato

Implementar `calcular_totales_por_asignatura(sesiones)` con este comportamiento:

- Recibe una lista de diccionarios con las claves `asignatura` y `minutos`.
- Se asumen entradas válidas: los nombres de asignatura son cadenas no vacías
  y los minutos son enteros positivos. No se requiere validar las entradas.
- Devuelve un diccionario que asocia cada asignatura con la suma de sus minutos.
- Compara los nombres exactamente, distinguiendo mayúsculas y minúsculas;
  por ejemplo, `Python` y `python` son asignaturas distintas.
- Una lista vacía devuelve `{}`.
- No modifica la lista recibida ni los diccionarios que contiene.
- No realiza operaciones de entrada/salida.

Ejemplo:

```python
sesiones = [
    {"asignatura": "Python", "minutos": 20},
    {"asignatura": "Redes", "minutos": 30},
    {"asignatura": "Python", "minutos": 15},
]

# Resultado exigido por el contrato:
{"Python": 35, "Redes": 30}
```

## Preparación de este hito

`benchmark/case_01/solution.py` contiene un único defecto intencionado:
sobrescribe los minutos al repetir una asignatura en lugar de acumularlos.
Se conserva para una futura evaluación de reparación por un agente.

`benchmark/case_01/test_solution.py` comprueba con cuatro pruebas de `unittest`:

1. Una lista vacía devuelve `{}`.
2. Dos asignaturas distintas conservan sus respectivos minutos.
3. El ejemplo con una asignatura repetida devuelve los totales del contrato.
4. La entrada permanece intacta, comparándola con una copia profunda.

Desde la raíz:

```sh
python3 -B -m unittest discover -s benchmark/case_01 -v
```

En este hito deben pasar tres pruebas y fallar únicamente la de acumulación.
No se debe reparar aún el defecto, omitir la prueba ni marcarla como fallo
esperado. Solo se utiliza la biblioteca estándar.

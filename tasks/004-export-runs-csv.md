# Tarea real 004: exportación CSV de consultas del inspector

**Versión 1 — 19 de octubre de 2026. Preparada; implementación pendiente.**

Base: `4cda45e2ccda3f7091f8ab15e55087516c09bec0` (`main`). Incluye la corrección
de advertencias AST del inspector. Segunda tarea real del flujo de proyectos;
no añade un caso al benchmark ni modifica las autoridades de la tarea 003.

La herramienta permitirá reunir consultas ya exportadas en una tabla para
hojas de cálculo u otras herramientas. No calcula tasas, aciertos ni calidad
del modelo: conserva datos declarados y separa resultado de consulta y ejecución.

## Interfaz y entradas

```bash
python3 -B export_runs.py consulta_1.json consulta_2.json
```

Uno o más argumentos posicionales, cada uno un archivo UTF-8 con un único
objeto del [esquema v1 del inspector](003-inspect-run-json.md). Se permiten
espacios alrededor del objeto JSON. No se exige una extensión de archivo.
Las rutas relativas se leen desde el directorio de trabajo del invocador.
`--` termina las opciones y permite nombres que empiecen por guion. Las únicas
opciones son `-h` y `--help`; no se admiten abreviaturas de opciones.

No recibe directorios de registros, no invoca `inspect_run.py`, no importa su
código ni vuelve a comprobar sus referencias. El JSON general de
`orchestrate_project.py` es otro formato y no es una entrada válida. Cada
documento se valida por sí solo; no requiere los registros que lo originaron.

## Salida y correspondencia de columnas

Una cabecera y una fila por argumento, en el mismo orden. Repetir un argumento
repite su fila; no ordenar ni deduplicar. Columnas exactas, sin otras métricas:

```text
origen,consulta_estado,consulta_codigo_salida,caso,ejecucion_estado,ejecucion_codigo_salida,intentos_registrados,max_intentos,invocaciones_total,max_invocaciones,duracion_segundos
```

| Columna | Fuente |
| --- | --- |
| `origen` | Argumento recibido, tal cual; no resolver, normalizar ni convertir a ruta absoluta. |
| `consulta_estado` | `consulta.estado` |
| `consulta_codigo_salida` | `consulta.codigo_salida` |
| `caso` | `ejecucion.caso` |
| `ejecucion_estado` | `ejecucion.estado` |
| `ejecucion_codigo_salida` | `ejecucion.codigo_salida` |
| `intentos_registrados` | `ejecucion.intentos_registrados` |
| `max_intentos` | `ejecucion.presupuestos.max_intentos` |
| `invocaciones_total` | `ejecucion.invocaciones.total` |
| `max_invocaciones` | `ejecucion.presupuestos.max_invocaciones` |
| `duracion_segundos` | `ejecucion.duracion_segundos` |

CSV en UTF-8 sin BOM, delimitado por comas, con terminador **LF** en cada
registro, incluido el último. Se usan comillas dobles para encerrar campos
que contienen comas, comillas o saltos de línea, duplicando las comillas
interiores. También se permite entrecomillar otros campos. Los CR y LF que
formen parte de una cadena se conservan dentro del campo entrecomillado;
no se confunden con terminadores de registro. No añadir encabezados narrativos,
Markdown, avisos ni espacios ajenos a los valores.

`null` produce una celda vacía. Los ceros explícitos se conservan. Las cadenas
se conservan literalmente, incluidos Unicode y espacios. Los enteros salen en
notación decimal entera exacta, sin pasar por float; los reales pueden usar
notación decimal o científica que represente el mismo valor, sin redondeo
adicional. No es obligatorio conservar el lexema numérico (por ejemplo, `1.20`
y `1.2` representan el mismo valor). No se impone un máximo de dígitos ni el
rango de un float de máquina: un entero de 5001 dígitos y `1e400` son números
finitos, distintos de las extensiones no JSON `NaN` e `Infinity`.

## Validación del documento v1

Todos los campos del esquema 003 deben estar presentes, incluso los que no
se exportan. No se admiten campos adicionales en ninguno de sus objetos.
Este contrato consume el documento exportado, no los resúmenes internos del
registro: las reglas de obligatoriedad se aplican a las claves de ese documento.

| Objeto | Claves exactas |
| --- | --- |
| Raíz | `version_esquema`, `consulta`, `ejecucion` |
| `consulta` | `estado`, `codigo_salida`, `incidencias` |
| `ejecucion` | `caso`, `estado`, `codigo_salida`, `presupuestos`, `intentos_registrados`, `invocaciones`, `duracion_segundos` |
| `ejecucion.presupuestos` | `max_intentos`, `max_invocaciones` |
| `ejecucion.invocaciones` | `desarrollador`, `revisor`, `total` |

- Los cinco contenedores son objetos, nunca listas ni `null`.
- `version_esquema` es el entero `1`; se rechazan otras versiones, `true`,
  `1.0`, `"1"` y ausencias.
- `consulta.estado` es `completada` o `incompleta`. `consulta.codigo_salida`
  es un entero, respectivamente `0` o `1`. `consulta.incidencias` es una lista
  de cadenas con contenido no blanco: vacía si y solo si está completada.
- `ejecucion.caso` y `ejecucion.estado` son cadenas con contenido no blanco
  o `null`. No se restringen a los nombres de casos o estados conocidos.
- `ejecucion.codigo_salida` es un entero o `null`; admite códigos negativos.
  No debe coincidir necesariamente con el código de consulta o del exportador.
- `intentos_registrados`, ambos presupuestos y los tres contadores de
  invocaciones son enteros no negativos o `null`.
- `duracion_segundos` es un número finito no negativo o `null`.
- Los booleanos nunca son números. Un campo entero rechaza números con parte
  fraccionaria o exponente en su representación JSON, aunque su valor sea
  equivalente a un entero. No convertir cadenas numéricas a números.
- Rechazar claves duplicadas a cualquier profundidad, JSON truncado, varios
  documentos concatenados, UTF-8 inválido, raíz no objeto, `NaN`, `Infinity`
  y `-Infinity`. No imponer límites artificiales de magnitud.

La coherencia exigible sin registros externos es la relación entre estado,
código e incidencias de **consulta**. Los `null` se aceptan donde los admite
el esquema. No reconstruir totales ni imponer sumas, relaciones entre
presupuesto y consumo o inferencias entre estado y código de la ejecución.
Una consulta incompleta, una ejecución fallida y datos desconocidos son
exportables cuando el documento cumple estas reglas.

## Atomicidad, canales y códigos

Se validan **todos** los archivos antes de escribir cualquier CSV, incluida
la cabecera. Si falla un argumento posterior, stdout sigue vacío. Se puede
informar del primer error o de varios; el diagnóstico debe identificar el
archivo afectado y la causa, sin exigir una redacción literal ni un traceback.

| Código del exportador | Resultado |
| --- | --- |
| `0` | Exportación completada: CSV en stdout y stderr vacío, aunque alguna consulta sea incompleta o alguna ejecución haya fallado. |
| `1` | Entrada ilegible o inválida: stdout vacío y diagnóstico localizado en stderr. Incluye archivos ausentes y argumentos que sean directorios. |
| `2` | Argumentos incorrectos, como falta de archivos u opción desconocida: stdout vacío y diagnóstico en stderr. |

`-h` y `--help` conservan ayuda en stdout, stderr vacío y código `0`; no
requieren archivos ni producen CSV.

## Ejemplo sintético

Contenido de `consulta.json` (datos inventados; no acredita una ejecución):

```json
{
  "version_esquema": 1,
  "consulta": {"estado": "incompleta", "codigo_salida": 1, "incidencias": ["Falta un informe sintético"]},
  "ejecucion": {
    "caso": "demo", "estado": "fallo_agente", "codigo_salida": 3,
    "presupuestos": {"max_intentos": 2, "max_invocaciones": 4},
    "intentos_registrados": 1,
    "invocaciones": {"desarrollador": 1, "revisor": 0, "total": 1},
    "duracion_segundos": null
  }
}
```

`python3 -B export_runs.py ./consulta.json ./consulta.json` deberá devolver
código `0`, stderr vacío y:

```csv
origen,consulta_estado,consulta_codigo_salida,caso,ejecucion_estado,ejecucion_codigo_salida,intentos_registrados,max_intentos,invocaciones_total,max_invocaciones,duracion_segundos
./consulta.json,incompleta,1,demo,fallo_agente,3,1,2,1,4,
./consulta.json,incompleta,1,demo,fallo_agente,3,1,2,1,4,
```

Si después se añade como tercer argumento un archivo inexistente, el resultado
deberá ser código `1`, stdout vacío y un diagnóstico de ese tercer archivo.

## Alcance permitido y aceptación

Solo biblioteca estándar. El único archivo que el futuro desarrollador podrá
crear o modificar es **`export_runs.py`**, inicialmente inexistente en la base.
No crear un archivo vacío en la base para fingir que ya existía. Inspector,
pruebas, controladores, utilidades, contratos, evaluadores, prompts, benchmark,
registros y configuración quedan protegidos. No modificar entradas, ejecutar
su contenido, consultar modelos, usar red ni leer configuración personal.

El [evaluador externo](../evals/tareas_reales/export_csv/evaluar.py) se ejecutará
desde una copia protegida, con `--project` apuntando al proyecto candidato.
No importa el candidato. La futura entrega deberá superar esa aceptación y
la regresión existente, sin modificarla. La [guía de preparación](../evals/tareas_reales/export_csv/README.md)
conserva el resultado inicial y los cambios de integración aún pendientes.

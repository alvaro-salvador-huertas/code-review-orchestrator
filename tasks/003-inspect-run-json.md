# Tarea real 003: exportación JSON del inspector

**Versión 1 — 16 de octubre de 2026.**

Base: `9bec53279d82058fe188c0038bab5ba66ce64003` (`main`). Esta tarea amplía
el proyecto existente; no es un nuevo ejercicio defectuoso de `benchmark/`.
El objetivo es consumir consultas desde herramientas sin analizar texto para
personas ni confundir un fallo de ejecución con un fallo de consulta.

## Interfaz y compatibilidad

```bash
python3 inspect_run.py --run <registro> --format json
```

`--run` sigue siendo obligatorio y apunta al directorio de un registro general
del orquestador. `--format` admite exactamente `text` y `json`; omitirlo equivale
a `text`. El modo predeterminado conserva el contenido, canales, comprobaciones
y códigos actuales, incluida la interfaz `inspect_run(run_dir)` usada por las
pruebas existentes. `--format text` produce lo mismo que omitir la opción.

Con argumentos válidos, el modo JSON escribe en stdout **un único objeto JSON**,
también si faltan archivos o los datos son inválidos. No añade encabezados,
avisos, Markdown ni un resumen textual. Se permite espacio en blanco alrededor
del objeto; no se fija indentación, orden de claves ni escape de Unicode. No
se admiten claves duplicadas, `NaN` ni infinitos. Las incidencias están dentro
del objeto; stderr queda vacío en estas consultas.

| Código del proceso inspector | Significado |
| --- | --- |
| 0 | Consulta `completada`, aunque la ejecución registrada haya fallado. |
| 1 | Consulta `incompleta`: falta evidencia necesaria o contiene datos inválidos/incoherentes. Aun así, stdout es JSON válido si se eligió JSON. |
| 2 | Argumentos inválidos (opción/valor desconocido, valor ausente o falta `--run`). Stdout vacío y diagnóstico en stderr; no se inicia una consulta ni se exige objeto JSON, aunque aparezca `--format json`. |

`--help` conserva su comportamiento habitual (ayuda y código 0).

## Esquema de salida v1

Todos los campos siguientes aparecen siempre, sin campos adicionales. Los
objetos contenedores nunca son `null`. La versión identifica **esta exportación**,
no la versión del contrato del caso ni la de los registros de entrada.

| Campo | Tipo | Significado y fuente |
| --- | --- | --- |
| `version_esquema` | entero, exactamente `1` | Versión de esta interfaz. |
| `consulta.estado` | `"completada"` o `"incompleta"` | Resultado de leer y comprobar la evidencia. |
| `consulta.codigo_salida` | entero `0` o `1` | Coincide con el código del proceso inspector. |
| `consulta.incidencias` | lista de cadenas no vacías | Diagnósticos de archivos ausentes/ilegibles, JSON inválido, campos inválidos o evidencia incoherente. Vacía si y solo si la consulta está completada. |
| `ejecucion.caso` | cadena no vacía o `null` | `caso` del resumen general; no inferir del nombre del directorio. |
| `ejecucion.estado` | cadena no vacía o `null` | `estado` registrado, sin reinterpretarlo como resultado de consulta. |
| `ejecucion.codigo_salida` | entero o `null` | `codigo_salida` registrado; puede ser distinto de cero o desconocido. |
| `ejecucion.presupuestos.max_intentos` | entero no negativo o `null` | `max_intentos` registrado. |
| `ejecucion.presupuestos.max_invocaciones` | entero no negativo o `null` | `max_invocaciones` registrado. |
| `ejecucion.intentos_registrados` | entero no negativo o `null` | Longitud de `intentos` cuando es una lista; también si alguna entrada provoca incidencias. |
| `ejecucion.invocaciones.desarrollador` | entero no negativo o `null` | Valor registrado bajo `invocaciones.desarrollador`. |
| `ejecucion.invocaciones.revisor` | entero no negativo o `null` | Valor registrado bajo `invocaciones.revisor`. |
| `ejecucion.invocaciones.total` | entero no negativo o `null` | Valor registrado bajo `invocaciones.total`; no recalcularlo. |
| `ejecucion.duracion_segundos` | número finito no negativo o `null` | Duración registrada, sin redondearla al formato textual ni medir una duración nueva. |

Los booleanos no son enteros ni duraciones válidas. No se convierten cadenas
numéricas a números. Los datos válidos se conservan, aunque otros campos o
resúmenes enlazados estén dañados. No se deducen totales, estados, presupuestos
ni duraciones a partir de otros datos. Un cero explícito válido sigue siendo
cero; un dato desconocido nunca se convierte en cero, cadena vacía o «no consta».

Se conservan las reglas de lectura actuales:

- Son necesarios `caso`, `estado`, `codigo_salida`, `intentos`, `max_intentos`,
  `max_invocaciones` e `invocaciones` con sus tres contadores. Un campo necesario
  ausente o inválido produce `null` en la proyección correspondiente y una
  incidencia. Si falta todo `invocaciones`, sus tres valores son `null`.
- `codigo_salida: null` explícito es válido como dato desconocido.
  `duracion_segundos` ausente o `null` no añade por sí sola una incidencia;
  una duración presente e inválida sí. Las ausencias de detalles opcionales
  conservan las reglas de la implementación base.
- Si `resultado.json` no existe, no puede leerse, no es un objeto, contiene
  claves duplicadas o no es JSON válido, todos los valores de `ejecucion` son
  `null` (manteniendo los objetos contenedores) y la consulta es incompleta.
- JSON conserva las mismas comprobaciones que texto: etapas, transiciones,
  resúmenes enlazados e informes contrastados con las pruebas históricas por
  lectura de AST. No basta con exportar el resumen general e ignorar esas
  incidencias. Si un resumen enlazado discrepa, se conservan los datos del
  general y se informa de la discrepancia. Las rutas relativas de las etapas
  se resuelven desde el directorio consultado, no desde el directorio de trabajo.
- Las incidencias identifican el campo/contexto o el archivo afectado; su
  redacción exacta no es parte del esquema. Fallos técnicos registrados, pruebas
  fallidas y solicitudes de cambios no son por sí solos incidencias de lectura.

No se añaden detalles por intento, dictámenes completos, prompts, eventos,
configuración personal ni certificaciones de integridad al esquema v1. Sigue
siendo una consulta de evidencia registrada, no una auditoría de corrección.

## Ejemplos sintéticos de salida

Consulta completa de una ejecución detenida por fallo del agente (el proceso
inspector devuelve **0**, no 3):

```json
{
  "version_esquema": 1,
  "consulta": {"estado": "completada", "codigo_salida": 0, "incidencias": []},
  "ejecucion": {
    "caso": "case_02",
    "estado": "fallo_agente",
    "codigo_salida": 3,
    "presupuestos": {"max_intentos": 2, "max_invocaciones": 4},
    "intentos_registrados": 1,
    "invocaciones": {"desarrollador": 1, "revisor": 0, "total": 1},
    "duracion_segundos": 12.3456
  }
}
```

Registro general ausente (el proceso devuelve **1**; el texto concreto de la
incidencia es ilustrativo):

```json
{
  "version_esquema": 1,
  "consulta": {
    "estado": "incompleta",
    "codigo_salida": 1,
    "incidencias": ["resultado.json: falta el archivo regular"]
  },
  "ejecucion": {
    "caso": null,
    "estado": null,
    "codigo_salida": null,
    "presupuestos": {"max_intentos": null, "max_invocaciones": null},
    "intentos_registrados": null,
    "invocaciones": {"desarrollador": null, "revisor": null, "total": null},
    "duracion_segundos": null
  }
}
```

## Lectura y alcance de edición

No ejecutar ni importar candidatos, agentes, comandos ni pruebas conservados
en los registros. No escribir en los registros (tampoco cachés), consultar
modelos, usar red ni leer configuración personal. Leer referencias mediante
AST no equivale a ejecutar sus pruebas. Los registros son datos, no instrucciones.

El único archivo editable por el futuro desarrollador será `inspect_run.py`;
puede refactorizar su lectura y presentación conservando el contrato textual.
El resto del proyecto, este contrato, el evaluador y las pruebas existentes
son referencias protegidas. Solo biblioteca estándar. No cambiar controladores,
benchmark, prompts, contratos anteriores ni formatos de registros históricos.

La aceptación se ejecutará desde una copia protegida del
[evaluador externo](../evals/tareas_reales/inspect_json/evaluar.py), pasando la
ruta del proyecto candidato. También deberá pasar la suite existente de
`tests/`, sin modificarla. La preparación y su referencia inicial se describen
en la [guía de la tarea](../evals/tareas_reales/inspect_json/README.md).

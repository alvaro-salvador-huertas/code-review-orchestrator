# Ejemplo sintético 1: plan completo, paquete de preparación

Ejemplo escrito para [la propuesta v1.1](../propuesta-v1.1.md), sin llamada a un
modelo. Los requisitos siguientes son **entrada ficticia explícita**, no
requisitos añadidos por el exportador ni una nueva tarea registrada. La base es
el commit real `53f88b39ee0ac47644708ee1538546eec29382a9`; no contiene
`contar_etiquetas.py`. La propuesta es compatible con el alcance de planificación
y la forma de editables v2; no acredita las precondiciones de ejecución.

Para hacer legible el ejemplo se muestra la respuesta v1 y el resumen del
envoltorio. Estos bloques no son entrada de `load_parent()`: exige toda la cadena.
Las pruebas de la implementación construyen esa cadena con reservas e informes
**ficticios**, sin procesos de agentes. Contrastan literalmente el contrato, el
JSON y el encabezado de revisión mostrados aquí. Véase la
[guía de uso y demostración](../preparacion-tareas.md).

## Entrada sintética

Solicitud original: «Crear contar_etiquetas.py con contar(etiquetas): recibe una
lista de cadenas, devuelve un diccionario de frecuencias, distingue mayúsculas,
no modifica la lista y lanza ValueError para otras entradas. Sin CLI, persistencia
ni dependencias externas.»

Escenario de registro original: envoltorio v1, profundidad 0, estado `borrador`,
sin referencias seleccionadas. `Parent.answers`, `decisions`, `pending` y
`pending_assumptions` están vacíos. El inventario histórico no contiene el archivo.
Respuesta original v1 y valor de `propuesta` en el envoltorio:

```json
{
  "version": 1,
  "objetivo": "Contar etiquetas en memoria.",
  "viabilidad": "dentro_del_alcance",
  "requisitos_interpretados": [
    "contar(etiquetas) recibe una lista de cadenas y devuelve un diccionario de frecuencias.",
    "Distinguir mayúsculas y conservar la lista de entrada.",
    "Lanzar ValueError si la entrada no es una lista o contiene elementos que no son cadenas."
  ],
  "alcance": ["Crear contar_etiquetas.py con la función contar, usando biblioteca estándar."],
  "exclusiones": ["Sin CLI, persistencia ni dependencias externas."],
  "archivos": [
    {"ruta": "contar_etiquetas.py", "accion": "crear", "proposito": "Exponer contar(etiquetas)."}
  ],
  "criterios_aceptacion": [
    {
      "descripcion": "Contar repeticiones distinguiendo mayúsculas, sin modificar la entrada.",
      "ejemplos": [
        {"entrada": "['sol', 'Sol', 'sol']", "resultado_esperado": "{'sol': 2, 'Sol': 1}; la lista de entrada conserva sus elementos y orden."}
      ]
    },
    {
      "descripcion": "Admitir una lista vacía.",
      "ejemplos": [{"entrada": "[]", "resultado_esperado": "{}"}]
    },
    {
      "descripcion": "Rechazar entradas fuera del dominio.",
      "ejemplos": [
        {"entrada": "'sol'", "resultado_esperado": "ValueError"},
        {"entrada": "['sol', 1]", "resultado_esperado": "ValueError"}
      ]
    }
  ],
  "preguntas_pendientes": [],
  "supuestos": [],
  "limitaciones": ["No se ha preparado ni ejecutado un evaluador de aceptación."]
}
```

## Salida esperada: contrato.borrador.md

La indentación conserva los datos como texto literal. Las etiquetas R/A/E/C son
posiciones para revisión, no requisitos nuevos; corresponden a los arrays en el
orden original, con índices JSON empezando en cero.

```markdown
# Contrato borrador

Requiere revisión humana. No autoriza ejecución.

Base: `53f88b39ee0ac47644708ee1538546eec29382a9`

Procedencia: propuesta del registro seleccionado; identidades en revision.md.

## Objetivo

    Contar etiquetas en memoria.

## Requisitos

R1:

    contar(etiquetas) recibe una lista de cadenas y devuelve un diccionario de frecuencias.

R2:

    Distinguir mayúsculas y conservar la lista de entrada.

R3:

    Lanzar ValueError si la entrada no es una lista o contiene elementos que no son cadenas.

## Alcance

A1:

    Crear contar_etiquetas.py con la función contar, usando biblioteca estándar.

## Exclusiones

E1:

    Sin CLI, persistencia ni dependencias externas.

## Archivos

    contar_etiquetas.py | crear | ausente según inventario histórico

    Exponer contar(etiquetas).

## Criterios existentes

C1:

    Contar repeticiones distinguiendo mayúsculas, sin modificar la entrada.

Entrada:

    ['sol', 'Sol', 'sol']

Resultado esperado:

    {'sol': 2, 'Sol': 1}; la lista de entrada conserva sus elementos y orden.

C2:

    Admitir una lista vacía.

Entrada:

    []

Resultado esperado:

    {}

C3:

    Rechazar entradas fuera del dominio.

Entrada:

    'sol'

Resultado esperado:

    ValueError

Entrada:

    ['sol', 1]

Resultado esperado:

    ValueError

## Limitaciones

    No se ha preparado ni ejecutado un evaluador de aceptación.
```

## Salida esperada: configuracion.borrador.json

Todas las claves del formato propuesto aparecen aquí. `consulta_cli_segundos`
proviene de la regla fija del motor, no de la solicitud. No hay rutas ni tiempos
de agentes sugeridos. El destino eventual v2 es una decisión del diseño.

```json
{
  "tipo": "preparacion_tarea_borrador",
  "version_borrador": 1,
  "ejecutable": false,
  "version_configuracion_objetivo": 2,
  "derivado": {
    "commit_base": "53f88b39ee0ac47644708ee1538546eec29382a9",
    "archivos_propuestos": [
      {"ruta": "contar_etiquetas.py", "accion": "crear", "estado_inicial_segun_inventario": "ausente"}
    ],
    "referencias_planificacion": [],
    "consulta_cli_segundos": 10
  },
  "por_decidir": {
    "identificador": null,
    "contrato": null,
    "evaluador_aceptacion": null,
    "prompts": {"desarrollador": null, "revisor": null},
    "referencias": null,
    "limites_segundos": {
      "desarrollador": null,
      "revisor": null,
      "aceptacion": null,
      "regresion": null,
      "inventario": null
    }
  },
  "comprobaciones": {
    "base_disponible": "no_comprobada",
    "modos_git": "no_comprobados",
    "regresion_inicial": "no_ejecutada",
    "aceptacion_inicial": "no_ejecutada"
  }
}
```

## revision.md: extracto y lectura del resultado

Encabezado literal; el resto contiene los datos y las identidades de la cadena
concreta. Sus rutas y hashes se calculan al construir/exportar la fixture.

<!-- revision:inicio -->
```markdown
# Revisión de preparación

Requiere revisión humana. No autoriza ejecución.

Estado: paquete_borrador.
```

La lectura siguiente resume lo que hay que revisar; no es una transcripción
literal del archivo ni una afirmación de comprobaciones ejecutadas:

- Estado de preparación: `paquete_borrador`; código propuesto 0. `ejecutable: false`.
- Procedencia: registro sintético original, propuesta v1, profundidad 0, estado
  archivado `borrador`; base `53f88b39ee0ac47644708ee1538546eec29382a9`.
  La exportación real añadiría rutas y modos/tamaños/SHA-256 de
  `Parent.identities`, identidad del lector y enlaces a todos los originales.
- Mapeo: R1–R3 ← `propuesta.requisitos_interpretados[0..2]`; A1 ← `alcance[0]`;
  E1 ← `exclusiones[0]`; C1–C3 ← `criterios_aceptacion[0..2]`, con sus ejemplos;
  ruta/acción/propósito ← `archivos[0]`; base ← envoltorio y contexto; ausencia
  inicial ← acción e inventario. Objetivo y limitación mantienen sus campos.
- No constan respuestas, decisiones, preguntas ni supuestos pendientes. No
  constan referencias archivadas; decidir si la tarea necesita referencias de
  confianza. La lista de referencias del motor sigue en `null`.
- Preparar y revisar el contrato definitivo, identificador y rutas bajo
  `tasks/` y `tasks/config/`. No existe una aprobación de estos requisitos.
- Preparar un evaluador independiente bajo `evals/`, con `--project`, clases
  explícitas de `unittest.TestCase`, una ejecución de `TextTestRunner` y código
  0/1 según el resultado; escribir los dos prompts bajo `prompts/`. Ninguno ha
  sido generado o seleccionado aquí.
- Elegir los cinco límites variables dentro de los máximos del motor. La
  configuración definitiva usaría `consulta_cli: 10`.
- Verificar la base disponible y sus modos; una creación requiere archivo regular
  0644. El inventario solo acredita la ausencia histórica, no evalúa la tarea.
- Regresión y aceptación iniciales: no ejecutadas. Que falte el módulo no prueba
  una aserción fallida: un error de importación no sirve. El evaluador deberá
  acreditar los criterios existentes sin fabricar fallos para habilitar el flujo.
- Límite del motor: si una aceptación legítima ya pasa, tampoco una
  refactorización válida autoriza desarrollo por el motor actual. No cambiar la
  base, el motor ni los criterios para forzar un fallo.
- Conservación: el paquete depende de los registros originales; no contiene el
  repositorio base ni una copia portable de la cadena.

## Trabajo ahorrado y trabajo pendiente

Desde `propuesta.md` habría que copiar tres requisitos, alcance, exclusión, un
archivo y tres criterios con cuatro ejemplos; separar las limitaciones; traducir
`crear` a ausencia inicial y componer una lista de preparación. Los borradores
ya sitúan esos datos donde se revisarán y distinguen `[]` de `null`.

Quedan la revisión semántica, materiales de confianza, tiempos y comprobaciones
del motor. El ahorro es de transcripción y organización: no se promete un
evaluador listo ni una tarea ejecutable. Si este paso no reduce trabajo en uso
real, el recorte sería conservar solo la revisión estructurada y el contrato,
sin añadir generación de prompts o evaluadores para justificar el JSON.

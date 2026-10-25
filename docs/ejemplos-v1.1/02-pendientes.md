# Ejemplo sintético 2: pendientes heredados y refactorización

Ejemplo documental para [la propuesta v1.1](../propuesta-v1.1.md). No reproduce
la llamada real descrita en [el cierre v1](../cierre-v1.md), ni atribuye decisiones
al usuario de este repositorio. Los textos de planificación y la decisión que
siguen son **entradas ficticias explícitas**. Las pruebas construyen registros
sintéticos completos con reservas e informes ficticios para el lector, sin
procesos de agentes ni aprobaciones. La [guía](../preparacion-tareas.md) permite
reproducir ambos escenarios sin usar registros privados.

## Entrada sintética: dos generaciones

Solicitud original: «Extraer la lectura y decodificación del lote de
booking_batch.py a una función privada del mismo archivo, conservando
comportamiento y contrato 008.»

Ambas generaciones fijan `53f88b39ee0ac47644708ee1538546eec29382a9`. En su
inventario `booking_batch.py` es regular y no protegido. El escenario incluye
referencias explícitas a `booking_batch.py` y `tasks/008-booking-batch.md` de esa
base: `contexto.referencias` contiene ruta, commit, modo, bytes y SHA-256;
`materiales/referencias.json` añade el contenido UTF-8 íntegro. Una cadena real
debería conservar y validar esas identidades/textos; aquí no se inventan sus hashes.

En r0 (envoltorio v1, estado `necesita_aclaraciones`), el modelo plantea:

| ID que deriva el lector | Campo | Texto exacto de esta entrada sintética |
| --- | --- | --- |
| `r0:p1` | `preguntas_pendientes[0]` | ¿Qué nombre tendrá la función privada? |
| `r0:s1` | `supuestos[0]` | Se puede admitir BOM al leer UTF-8. |
| `r0:s2` | `supuestos[1]` | La función privada devolverá la lista y propagará las excepciones. |

La única aportación explícita del usuario **ficticio** para r1 es esta decisión:

```json
{
  "id": "r0:s1",
  "supuesto": "Se puede admitir BOM al leer UTF-8.",
  "decision": "rechazar",
  "explicacion": "Conservar el rechazo de BOM del contrato 008.",
  "alternativa": ""
}
```

Es una vista de la decisión, no el archivo de entrada completo: el formato real
añade `origen_supuesto` y el envoltorio `version`, `tipo`, `origen`, `decisiones`.
La fila `r0:s2` de esa plantilla quedaría `sin_decidir`, con explicación y
alternativa vacías. No se aporta archivo de respuestas. El exportador no crea
esa respuesta ausente ni convierte el rechazo de `r0:s1` en aceptación de `r0:s2`.

La respuesta del modelo de r1 omite todas las preguntas y supuestos anteriores:

```json
{
  "version": 1,
  "objetivo": "Extraer la lectura del lote conservando comportamiento.",
  "viabilidad": "dentro_del_alcance",
  "requisitos_interpretados": [
    "Conservar el comportamiento y el contrato 008 de booking_batch.py.",
    "Extraer la apertura, lectura y decodificación a una función privada del mismo archivo."
  ],
  "alcance": ["Modificar únicamente booking_batch.py."],
  "exclusiones": ["Sin cambios en booking_core.py, interfaz pública o dependencias."],
  "archivos": [
    {"ruta": "booking_batch.py", "accion": "modificar", "proposito": "Separar la lectura del lote."}
  ],
  "criterios_aceptacion": [
    {
      "descripcion": "Mantener la salida del lote vacío.",
      "ejemplos": [{"entrada": "Archivo UTF-8 con []", "resultado_esperado": "Código 0, stdout con [] y salto de línea, stderr vacío."}]
    },
    {
      "descripcion": "Mantener el rechazo de BOM.",
      "ejemplos": [{"entrada": "Archivo UTF-8 con BOM seguido de []", "resultado_esperado": "Código 1, stdout vacío y diagnóstico en stderr."}]
    }
  ],
  "preguntas_pendientes": [],
  "supuestos": [],
  "limitaciones": ["Los ejemplos no sustituyen la revisión del contrato 008 completo ni acreditan cambios de comportamiento."]
}
```

El envoltorio r1 es **v3**, con `continuacion.version: 2`, profundidad 1 y estado
`necesita_aclaraciones`. La aportación efectiva es el rechazo, por lo que esta
continuación es coherente aunque no haya respuestas. El lector entrega:

```json
{
  "answers": [],
  "pending": [
    {"id": "r0:p1", "pregunta": "¿Qué nombre tendrá la función privada?"}
  ],
  "pending_assumptions": [
    {"id": "r0:s2", "supuesto": "La función privada devolverá la lista y propagará las excepciones."}
  ]
}
```

Esta es una proyección de `Parent`, no otro esquema de registro. `Parent.decisions`
conserva el rechazo mostrado con su `origen_supuesto`; `assumption_origins`
conserva la procedencia de ambos supuestos. Los textos de referencias se heredan
exactamente de r0. Ni las listas vacías de la última respuesta ni un HEAD posterior
resuelven pendientes o actualizan la base.

## Salida esperada: solo revision.md

Encabezado literal, contrastado en pruebas:

<!-- revision:inicio -->
```markdown
# Revisión de preparación

Requiere revisión humana. No autoriza ejecución.

Estado: solo_diagnostico.
```

Lo siguiente es una lectura del resultado y del contexto del ejemplo. La CLI
localiza pendientes y colisiones; el contraste semántico del contrato 008 y la
comparación de sus dos bases corresponden a una persona. No extrae requisitos
nuevos del texto de una referencia.

- Estado de preparación: `solo_diagnostico`; código propuesto 3. No se generan
  `contrato.borrador.md` ni `configuracion.borrador.json`.
- Procedencia: r1 v3, continuidad v2, profundidad 1; r0 v1; ambos con estado
  archivado `necesita_aclaraciones`. Base histórica:
  `53f88b39ee0ac47644708ee1538546eec29382a9`.
  La exportación real añadiría rutas, modos, tamaños y SHA-256 de cada archivo
  de `Parent.identities`, identidad del lector y enlaces a ambas generaciones.
- **Bloqueo P1**: `r0:p1`, «¿Qué nombre tendrá la función privada?».
  Procedencia: r0, `propuesta.preguntas_pendientes[0]`. No consta respuesta.
- **Bloqueo S2**: `r0:s2`, «La función privada devolverá la lista y propagará las
  excepciones.». Procedencia: r0, `propuesta.supuestos[1]`, con origen conservado
  por el lector. No consta decisión efectiva. Su omisión en r1 no lo resuelve.
- Decisión acumulada `r0:s1`: supuesto «Se puede admitir BOM al leer UTF-8.»;
  acción `rechazar`; explicación «Conservar el rechazo de BOM del contrato 008.»;
  alternativa `""`; origen r0 con las identidades de propuesta/resultado del
  archivo aportado. No es una aprobación del plan. No constan respuestas.
- Datos trasladables cuando desaparezcan los bloqueos: `booking_batch.py`,
  `modificar` → `existente` según inventario, objetivo/requisitos/alcance/criterios
  de r1 y la misma base. No se elige nombre de función ni comportamiento de retorno.
- Referencias históricas: conservar identidades y ubicación de los textos de
  `booking_batch.py` y `tasks/008-booking-batch.md` en
  `materiales/referencias.json`. **Incompatibilidad de materiales**:
  `booking_batch.py` sería editable; no puede declararse además como referencia
  de confianza de la tarea configurable. No eliminarlo de la evidencia del plan.
- El contrato 008 consultado declaró una creación sobre
  `9017d6ca212af4447c02da22c0bcd9a5364f6924`. Es base histórica de otra tarea,
  no la base de esta refactorización; no copiar su estado `ausente` ni reutilizar
  automáticamente su configuración/evaluador/prompts.
- Materiales no aportados como autoridades de la nueva tarea: contrato definitivo,
  identificador, evaluador, prompts, referencias seleccionadas y límites variables.
  Las dos muestras de aceptación no acreditan cobertura de todo el comportamiento.
- **Límite adicional del motor**: aun resolviendo P1 y S2, conservar comportamiento
  puede dejar la aceptación ya superada en la base. Sin aceptación inicialmente
  fallida legítima, el motor actual no permite desarrollar. No se ha ejecutado
  ninguna evaluación: no afirmar ni éxito ni fallo. No fabricar una aserción roja,
  reinterpretar el rechazo del BOM como funcionalidad nueva ni cambiar el motor.
- Los materiales y la base no se refrescan desde el checkout. Este diagnóstico
  depende de conservar los originales y no constituye un archivo portable.

## Qué puede hacer ahora la persona

Responder P1 y decidir S2 mediante los mecanismos de continuidad existentes,
conservando los originales. Esas decisiones no se inventan en este ejemplo.
Una continuación posterior sería una operación separada, autorizada expresamente
si se quiere invocar el planificador; el exportador local nunca la lanza.

Un futuro plan completo podría producir los tres borradores, manteniendo el aviso
sobre la aceptación. La persona tendría que decidir si preparar esta
refactorización manualmente fuera del motor. El paquete no certificará ejecución.

Frente a releer `propuesta.md` y la cadena, el diagnóstico reúne dos pendientes
heredados con IDs accionables, una decisión ya resuelta que no debe repetirse,
la colisión editable/referencia y la diferencia entre las dos bases. Evita copiar
la configuración histórica o redactar un contrato que presuponga decisiones
ausentes. No duplica un contrato incompleto que habría que rehacer.

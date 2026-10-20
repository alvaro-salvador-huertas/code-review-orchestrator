# Planificación de proyectos por lenguaje natural

Desde la raíz, **cuando decidas invocar un modelo real**:

```bash
python3 -B plan_project.py "Descripción del trabajo que quiero realizar"
```

Necesita Codex CLI disponible y autenticado. Genera un borrador revisable con una
sola sesión nueva de solo lectura, sin desarrollo, evaluación, revisión del
producto ni incorporación. No se ha probado contra un modelo real durante este
hito. `python3 -B plan_project.py --help` no invoca modelos ni crea registros.

El controlador fija la petición original y el commit `HEAD` de la base. El modelo
recibe únicamente petición, instrucciones, restricciones, esquema y nombres/tipos
de los archivos Python de la raíz de esa base. No recibe fuentes del proyecto,
registros privados ni configuración personal. Los cambios pendientes se conservan,
pero no forman parte del inventario de la base. Sin las fuentes, inferir el
comportamiento de un módulo por su nombre no constituye un hecho comprobado.

## Esquema cerrado de propuesta v1

El esquema se define en [project_plan.py](../project_plan.py), mediante
`response_schema()`, y se guarda en cada registro. No es una configuración
ejecutable v1/v2 del motor. La respuesta del modelo exige exactamente estas claves:

| Campo | Tipo y significado |
| --- | --- |
| `version` | Entero 1, no booleano. |
| `objetivo` | Texto no vacío que interpreta el trabajo. |
| `viabilidad` | `dentro_del_alcance`, `pendiente_de_aclaracion` o `fuera_del_alcance`. |
| `requisitos_interpretados` | Lista de textos; interpretaciones pendientes de revisión. |
| `alcance`, `exclusiones` | Listas de textos que delimitan el borrador. |
| `archivos` | Lista de objetos con solo `ruta`, `accion` y `proposito`. Acción `crear` o `modificar`; propósito no vacío. |
| `criterios_aceptacion` | Lista de objetos con solo `descripcion` y `ejemplos`. Cada ejemplo contiene solo `entrada` y `resultado_esperado`, ambos textos; entrada puede estar vacía. |
| `preguntas_pendientes` | Lista de dudas que requieren intervención del usuario. |
| `supuestos` | Lista de supuestos explícitos, no decisiones atribuidas al usuario. |
| `limitaciones` | Lista de restricciones o incertidumbres del plan. |

Todos los objetos son cerrados. Se rechazan claves duplicadas a cualquier nivel,
constantes no JSON, tipos distintos, textos requeridos vacíos, rutas repetidas y
duplicados en listas y criterios. Los textos deben ser representables en UTF-8,
con un máximo de 8.000 caracteres; las listas admiten hasta 100 elementos.
La petición admite hasta 16.000 caracteres y la respuesta bruta hasta 1 MiB.
Una petición no representable en UTF-8 se rechaza como argumento inválido antes
de crear registros o consultar la CLI. Los diagnósticos escapan sustitutos Unicode
aislados procedentes de datos rechazados; la respuesta original se conserva exacta.
El controlador valida localmente incluso si Codex recibió el esquema.

Las rutas deben cumplir `[A-Za-z_][A-Za-z0-9_]*\.py` en la raíz, sin directorios,
enlaces, rutas absolutas ni infraestructura protegida. `crear` exige ausencia
en la base Git; `modificar`, presencia como archivo regular. No se permiten
borrados ni dependencias ajenas a la biblioteca estándar. Los nuevos módulos
`plan_project.py` y `project_plan.py` se añaden a la protección de infraestructura
de las configuraciones v2; la validación del plan los prohíbe también. No se
cambian las reglas históricas de configuración v1 ni los presupuestos del motor.

Una propuesta `dentro_del_alcance` necesita requisitos, alcance, archivos y
criterios. `pendiente_de_aclaracion` necesita preguntas y puede no definir todavía
archivos ni criterios. `fuera_del_alcance` necesita limitaciones y no admite
archivos propuestos: permite documentar un bloqueo o preguntar cómo redefinirlo.
No convierte capacidades nuevas en permisos disponibles.

El controlador envuelve la respuesta validada en `propuesta.json`, con claves
exactas `version`, `tipo`, `estado`, `solicitud_original`, `commit_base`,
`procedencia` y `propuesta`. `tipo` es `propuesta_planificacion`; `procedencia`
contiene `rol`, `registro`, `respuesta_sha256` y `requiere_revision_humana=true`.
El modelo no suministra ni puede sobrescribir esos metadatos.
`propuesta.md` se renderiza desde ese mismo objeto, con los datos variables como
texto literal. No ejecuta comandos, código ni pruebas presentes en la respuesta.

## Ejemplo exclusivamente sintético

Para «créame una API de reservas», una respuesta simulada válida es:

```json
{
  "version": 1,
  "objetivo": "Definir una API de reservas.",
  "viabilidad": "pendiente_de_aclaracion",
  "requisitos_interpretados": ["Ofrecer una API de reservas."],
  "alcance": [],
  "exclusiones": [],
  "archivos": [],
  "criterios_aceptacion": [],
  "preguntas_pendientes": [
    "¿Qué operaciones debe ofrecer?",
    "¿Necesita persistencia?",
    "¿Qué interfaz se espera?"
  ],
  "supuestos": [],
  "limitaciones": ["Todavía no hay requisitos suficientes para definir archivos."]
}
```

Se obtiene estado `necesita_aclaraciones` y código 0. No decide por el usuario
que deba ser HTTP ni que los datos deban persistirse. Una propuesta concreta
sin preguntas ni supuestos puede quedar como `borrador`; tampoco es aprobación.
Los supuestos pendientes o la viabilidad aún no resuelta producen
`necesita_aclaraciones`, aunque la lista de preguntas esté vacía.

## Sesión, estados y evidencia

Se reutiliza `review_case.invoke_reviewer` como adaptador de solo lectura, con
rol registrado **planificador**, y `repair_case.run_process` para canales,
timeouts y recogida de procesos. No se altera su comportamiento histórico:
`--ephemeral`, sandbox `read-only`, aprobación `never`, web desactivada y
subagentes desactivados. El prompt también prohíbe ejecutar o leer fuera del
contexto entregado. El entorno utiliza la política existente `codex` para su
autenticación; no se enumeran ni copian valores de variables a los registros.

Hay un máximo de **una invocación, con 300 s**, sin reintento. Versión y ayuda
tienen 10 s por consulta y no cuentan como invocaciones del modelo. Antes de
lanzar se guardan `reserva.json` y el contador en `resultado.json`. La reserva
es conservadora: si después desaparece la CLI, sigue contabilizada como un intento,
sin afirmar que el servicio haya recibido o completado una llamada.

| Salida | Significado |
| --- | --- |
| 0 | Borrador generado, incluso con aclaraciones o fuera del alcance actual. |
| 1 | Fallo de planificación; no se publica una propuesta válida parcial. |
| 2 | Argumentos incorrectos. La ayuda termina con 0. |

Los estados finales son `borrador`, `necesita_aclaraciones` y `fallo_tecnico`;
`preparando` y `planificando` son estados transitorios. `fallo.tipo` distingue
CLI ausente, incompatibilidad, fallo de proceso, timeout, interrupción, respuesta
inválida, integridad y errores de controlador/registro. Los canales normales van
a stdout; un fallo va a stderr. Una interrupción también termina con código 1.

Cada ejecución crea exclusivamente `runs/<fecha>_plan_project_<id>/`:

- `materiales/`: solicitud, contexto mínimo, instrucciones y esquema.
- `planificador/`: prompt de entrada, versión, consultas previas, eventos,
  stderr y respuesta original, también ante errores.
- `procedencia.json`, `proyecto_antes.json`, `resultado.json`, tiempos y hashes.
- `reserva.json` solo si se reservó la invocación.
- `propuesta.json` y `propuesta.md` solo tras respuesta válida e integridad correcta.

Se cotejan base, proyecto y materiales antes de reservar y al finalizar.
El inventario de conservación excluye registros y configuración privada, según
las reglas existentes. Un temporal, un hash y la detección de modificaciones
**no constituyen aislamiento de seguridad** ni deshacen una alteración externa.
Si el sistema de archivos impide guardar evidencia, la CLI informa del fallo;
no puede garantizar un registro completo en un soporte que no permite escribir.

## Comprobaciones y siguiente paso

Las [pruebas permanentes](../tests/test_plan_project.py) usan repositorios
sintéticos y una CLI prefijada. Comprueban estructura, protocolos, presupuesto,
errores y conservación. **No acreditan la calidad semántica de un modelo real**
ni que sus interpretaciones correspondan a la intención del usuario.

Se ejecutaron 32 métodos enfocados correctos (3,926 s) y dos controles de
compatibilidad v1/v2 correctos (0,030 s y 0,048 s), con Python 3.12.3, sin modelos
ni sockets. Una primera versión había superado 29 métodos; el registro conserva
ambas ejecuciones y las fuentes correspondientes. El cambio posterior añadió el
rechazo temprano de sustitutos Unicode aislados y tres controles adicionales.

La auditoría previa detectó `booking_http.py` con modo local 0664 y el hash
autorizado intacto. Se restauró únicamente su modo 0644, exigido por el contrato
007 y la incorporación anterior; no se cambiaron sus bytes ni permisos de
registros históricos. La causa del modo observado no está determinada. Se
conservan el fallo de auditoría y las identidades antes y después.

La evidencia y las demostraciones simuladas se conservan, fuera de Git, en
`runs/20261020_planificacion_proyectos_desarrollo/`. Su
`validacion_terminal/` acredita la ejecución del usuario del 20 de octubre:
**648 métodos, 259,953 s, Python 3.12.3, código 0**, sin fallos, errores ni omisiones.
El runner ejecutó una vez `python3 -B -m unittest discover -s tests -v`, con
entorno `evaluation`, límite de 600 s y recogida del grupo de procesos.
El cotejo posterior comprobó terminación, canales, las 648 identidades ordenadas,
hashes y conservación del árbol. No se repitió esa ejecución.

Una revisión automática asistida por Codex posterior encontró dos defectos:

- Una solicitud con un sustituto aislado, como `"\ud800"`, atravesaba el parser
  de argumentos y provocaba una excepción al escribir el registro. Ahora se
  rechaza antes de cualquier escritura o invocación, con código 2.
- Una respuesta `{"\ud800":1,"\ud800":2}` generaba un diagnóstico de clave
  duplicada que tampoco podía escribirse como UTF-8. Ahora conserva el bruto
  y registra `respuesta_invalida`, código 1, sin propuesta parcial.

La reproducción anterior al ajuste ejecutó dos métodos: código 1, un fallo y
dos errores. Tras corregir únicamente esas fronteras de Unicode, pasaron
**34 métodos enfocados en 5,173 s**, Python 3.12.3 y código 0. Los controles
incluyen acentos y caracteres válidos fuera del BMP, sin sustituirlos ni
rechazarlos. Los resultados y fuentes están en el registro nuevo excluido de Git
`runs/20261020_planificacion_proyectos_revision_publicacion/`; los anteriores
permanecen intactos.

El descubrimiento final, sin ejecutar métodos, cuenta **650 identidades únicas**:
616 anteriores y 34 de planificación. La validación de 648 corresponde al árbol
anterior a estas dos correcciones; no acredita por sí sola el árbol final.
La CI automática de la PR hacia `main` ejecuta el descubrimiento completo sobre
la publicación final; su resultado, comando y commit se contrastan por separado.
No se han abierto sockets desde el entorno restringido ni repetido regresiones
de bases congeladas. El servidor HTTP y el controlador de permisos se conservan.

El paso posterior a un borrador revisado es resolver preguntas y supuestos,
definir un contrato y un evaluador **de confianza del usuario**, y preparar
manualmente una configuración admitida por el motor. No hay promoción automática
a `tasks/config`, evaluador generado ni autorización implícita para desarrollar.

## Experimento semántico preparado, todavía sin ejecutar

Una única petición propuesta: «Créame una API de reservas». El presupuesto
máximo es **una invocación de planificación, 300 s, sin reintentos**; las consultas
de versión y ayuda mantienen 10 s cada una. Solo se lanzará cuando el usuario
decida ejecutar expresamente esa prueba. No hay autorización para encadenar
desarrollo, evaluación, revisión ni incorporación.

Se revisarán el JSON original y la propuesta renderizada, no solo su validez
estructural: si identifica la ambigüedad de operaciones, interfaz y persistencia;
si separa preguntas y supuestos de decisiones del usuario; si evita inventar el
contenido de los módulos que solo conoce por nombre; y si respeta raíz Python,
biblioteca estándar y archivos protegidos. Una propuesta sin archivos puede ser
adecuada mientras falte alcance. Se registrarán ejemplos concretos de aciertos
y omisiones, sin convertir una sola respuesta en una tasa de fiabilidad.

Las respuestas prefijadas de las pruebas no cuentan como resultados de este
experimento. Sus resultados semánticos siguen pendientes.

# Propuesta v1.1: preparación local desde un plan

Especificación del primer alcance, implementada en la
[guía de preparación local](preparacion-tareas.md). No autoriza ejecutar tareas.
Parte de v1.0.0, en `53f88b39ee0ac47644708ee1538546eec29382a9`. Conserva su
código, contratos, pruebas y registros. La herramienta propuesta transforma un
registro íntegro de planificación en material de trabajo para una persona: no
consulta modelos, ejecuta pruebas, consume reservas ni aprueba tareas.

## Entrada y resultado

Interfaz: `prepare_project.py --from-plan REGISTRO --output DIRECTORIO`.
Solo estas dos opciones obligatorias y ayuda; sin selección de modelo, ejecución,
respuestas nuevas, sustitución de base ni sobrescritura.

Reutilizar `load_parent()` de
[project_plan_continuation.py](../project_plan_continuation.py), sin implementar
otro lector ni aceptar `propuesta.md` o `propuesta.json` sueltos. Lee resultado,
manifiestos, materiales, respuesta original, propuesta JSON/Markdown y ancestros;
contrasta integridad y continuidad. Admite envoltorios v1/v2/v3, con respuesta del
modelo v1, y conserva los límites actuales: original más ocho revisiones, 8 MiB
por archivo, 64 MiB por cadena y 64 artefactos por registro. Exportar en profundidad
ocho es válido: no crea una novena revisión ni llama a `continuation_data()` para
producirla. Los hashes acreditan correspondencia, no autenticidad del autor.

| Entrada leída | Salida en un directorio nuevo | Código propuesto |
| --- | --- | --- |
| Cadena válida; `viabilidad == dentro_del_alcance`; `Parent.pending` y `Parent.pending_assumptions` vacíos | Los tres borradores siguientes | 0 |
| Cadena válida con preguntas, supuestos o viabilidad pendiente/fuera del alcance | Solo `revision.md`, estado `solo_diagnostico`, con bloqueos localizados | 3 |
| Registro incompleto, incompatible con el lector, alterado, ilegible, o destino no permitido/existente | Error; ningún paquete publicado | 1 |
| Argumentos inválidos | Error previo a leer o escribir | 2 |

«Completo» significa completo para **preparación**, nunca ejecutable. El lector ya
exige requisitos, alcance, archivos y criterios para `dentro_del_alcance`. No basta
mirar el estado archivado: una revisión v2 histórica puede decir `borrador` y
conservar supuestos ancestrales pendientes. Se muestra ese estado sin reclasificarlo y se
decide la exportación con las listas acumuladas del lector. La compatibilidad es
estructural; la correspondencia semántica sigue requiriendo revisión humana.

## Tres documentos, sin completar huecos por inferencia

`contrato.borrador.md` contiene objetivo, requisitos, alcance, exclusiones,
archivos y propósitos, criterios con todos sus ejemplos y limitaciones. Conserva
orden y texto exactos, con una línea `Base: ` seguida del SHA histórico entre
acentos graves. Añade únicamente títulos, procedencia y avisos de borrador. Los
datos se renderizan como texto literal, siguiendo `render_proposal()`: no activar
Markdown, enlaces ni instrucciones procedentes del plan. No se escribe en `tasks/`.

`configuracion.borrador.json` es un formato propio, cerrado, con las claves y
estructura del [ejemplo completo](ejemplos-v1.1/01-completo.md). Usa
`tipo: preparacion_tarea_borrador`, `version_borrador: 1`, `ejecutable: false` y
`version_configuracion_objetivo: 2`: v2 permite uno o varios editables. Carece de
`version` y de los campos ejecutables en la raíz; el validador actual lo rechaza
incluso si se renombra. No convertir automáticamente el borrador en configuración
de confianza ni modificar configuraciones v1/v2 existentes.

| Fuente real | Traslado / decisión | Ausencia o límite |
| --- | --- | --- |
| `Parent.proposal.commit_base`; `materiales/contexto.json` | SHA idéntico al contrato y a `derivado.commit_base` | Ausencia o discordancia: error del lector; nunca sustituir por HEAD |
| `propuesta.objetivo`, `requisitos_interpretados`, `alcance`, `exclusiones`, `criterios_aceptacion`, `limitaciones` | Copia literal al contrato, manteniendo descripciones, entradas y resultados esperados | Lista vacía: «No consta en el plan», sin convertirla en aprobación o libertad de alcance; una entrada de ejemplo `""` se conserva |
| `propuesta.archivos` más inventario histórico | Ruta y acción a `derivado.archivos_propuestos`; `crear` → `ausente`, `modificar` → `existente`, como `estado_inicial_segun_inventario`; propósito al contrato | Sin inferir contenido, modo o comportamiento; archivo no regular, protegido o acción incoherente: rechazo del lector |
| `contexto.referencias` y `materiales/referencias.json` | Identidades exactas, en orden, a `derivado.referencias_planificacion`; ubicación de los textos archivados en revisión | Sin referencias archivadas: `[]` y aviso; no buscar otras ni leer el checkout |
| `Parent.answers`, `decisions`, `pending`, `pending_assumptions`, `assumption_origins` | Registro literal en revisión, con IDs y orígenes; respuestas y decisiones separadas del texto del modelo | Listas vacías: «No constan…»; nunca responder, aceptar ni resolver por coincidencia textual |
| Identificador y destinos de contrato/evaluador/prompts | `por_decidir.identificador`, `contrato`, `evaluador_aceptacion` y ambos `prompts`: `null` | No existen como campos de autoridad en el plan; ni un nombre citado en prosa ni una referencia los seleccionan |
| Referencias de la futura tarea | `por_decidir.referencias: null` hasta selección humana | `null` no equivale a `[]`: esta última sería una elección explícita sin referencias |
| Límites del motor | Cinco límites variables en `por_decidir.limites_segundos`, todos `null`; `derivado.consulta_cli_segundos: 10` es regla del motor | No heredar los 300 s del planificador ni inventar presupuesto; máximos en la guía de configuración |
| Disponibilidad de base, modos Git, regresión y aceptación iniciales | Objeto `comprobaciones` con los cuatro estados del ejemplo | `no_comprobada`, `no_comprobados` o `no_ejecutada`; no significan fallo ni éxito |

No se omiten claves del nuevo JSON ni se usan cadenas vacías como marcadores.
Las listas vacías solo expresan ausencia conocida de elementos **archivados**.
Un material requerido por el lector que falte es un error, no un `null` tolerable.
Un evaluador o prompt ausente del plan significa «no aportado como autoridad»;
no afirma que ese archivo no exista en el repositorio. No se buscan ni generan.

`revision.md` agrupa procedencia, decisiones acumuladas, materiales por preparar,
incompatibilidades y comprobaciones pendientes. Localiza cada dato mediante
registro y campo/ID. Reproduce decisiones `aceptar`, `rechazar` y `corregir` con
supuesto original, explicación/alternativa y `origen_supuesto`; una corrección no
reescribe el supuesto y un rechazo no se vuelve requisito. Incluye las respuestas
con su pregunta e ID. No fusiona automáticamente esas entradas con el contrato:
la persona debe contrastar que el último plan las respeta. `sin_decidir` permanece
en pendientes, sin transformarse en decisión confirmada.

## Base histórica y referencias

El contenido se deriva únicamente de la cadena archivada. No se consulta Git, HEAD
ni el árbol de trabajo para actualizarlo o acreditar disponibilidad de la base.
Se conservan SHA, inventario y restricciones del contexto original. En revisión
enlaza los materiales originales y recoge, de `Parent.identities`, ruta, modo,
tamaño y SHA-256 de **cada archivo leído**, incluidos los resultados de todos los
ancestros. Registra también versiones de propuesta, profundidad, estados
archivados y el mapeo de campos de la tabla anterior. Identifica por SHA-256 los
módulos locales de lectura/renderizado/exportación usados, separadamente de la
procedencia del controlador histórico; no atribuye al lector actual su identidad.

Los textos de referencias permanecen en `materiales/referencias.json`, con sus
identidades y bytes UTF-8 validados; nunca se sustituyen por sus versiones actuales.
No se hereda como nueva base la línea `Base:` de un contrato consultado: puede
describir una tarea anterior. Una referencia del plan tampoco se convierte en
autoridad del motor: si coincide con un editable, con otra autoridad o con una
utilidad reservada, revisión señala la incompatibilidad y deja la selección en
`null`. Los materiales futuros deben satisfacer
[las reglas de configuración](tareas-configurables.md), incluidas no vaciedad,
rutas, ausencia de enlaces y protección de infraestructura.

Recorte deliberado: el paquete contiene solo los tres documentos (uno en caso de
diagnóstico), **no una copia portable de los registros ni del repositorio Git**.
Depende de conservar la cadena en sus rutas originales; revisión lo declara.
Los enlaces a evidencia se generan desde rutas validadas, escapadas, sin activar
enlaces aportados por el modelo. No cambiar las rutas absolutas de continuidad
para aparentar portabilidad. Si se pierde la cadena o el commit, el paquete no los
reconstruye: la preparación ejecutable queda pendiente de recuperar los originales.

## Exportación y protección

Leer y renderizar por completo antes de crear destino. Verificar `Parent.intact()`
antes y después de escribir. Rechazar destino existente, incluso directorio vacío,
enlace válido o roto; rechazar enlaces en antecesores y cualquier solapamiento
con los registros de la cadena. El padre del destino debe existir y ser regular.
No permitir destinos en `.git`, `runs`, rutas privadas ni dentro de `tasks/`,
`evals/` o `prompts/` del proyecto: son borradores, no autoridades instaladas.
La raíz es el directorio real de la CLI, no el cwd ni el registro; las rutas
relativas parten del cwd. Se rechazan componentes ocultos/privados en toda la
ruta absoluta y `..` en el destino. La [guía](preparacion-tareas.md) precisa la
política para destinos externos, creación exclusiva, modos y descriptores.

Crear el directorio de forma exclusiva y cada archivo con creación exclusiva;
sin `--force`, mezclas ni sobrescrituras. Escribir `revision.md` al final como
cierre del conjunto. Ante error, retirar solo los archivos/directorio creados
por esta operación cuya identidad siga siendo propia; nunca borrar contenido
ajeno. Una interrupción abrupta puede dejar un directorio incompleto: informar
de ello y rechazar reutilizarlo en una segunda exportación. No prometer atomicidad
de varios archivos. Ante alteración del origen, no publicar un cierre válido.

No escribir en la cadena ni en sus `reserva.json`, ni crear una reserva nueva.
No consultar la CLI del modelo, lanzar procesos de pruebas, importar candidatos,
instalar dependencias o incorporar código. Se reutiliza el lector, no
`run_plan()`, el exportador de plantillas de continuación ni el motor de tareas.

## El límite de la aceptación inicialmente fallida

[preparation_authorized()](../project_flow.py) exige regresión superada y
aceptación con `fallos_asercion`; para tareas configurables, métodos y aserciones
fallidas positivos y cero errores. La acreditación completa incluye identidades,
informes, códigos y cierres textuales. Una aceptación ya superada, un error de
importación o la ausencia del evaluador no satisfacen la precondición.

Una refactorización que conserva comportamiento puede tener un plan completo y
ser válida aunque su aceptación pase antes del cambio. Se puede exportar su
**paquete de preparación**, siempre `ejecutable: false`, con este límite visible
en revisión; el exportador no evalúa ni decide si la aceptación fallaría. El aviso
se incluye en todos los paquetes, pues no se clasifica prosa mediante heurísticas.
No añadir una aserción artificial, cambiar criterios para forzar rojo, trasladar
una base antigua de creación ni relajar el motor. Si la revisión confirma que no
hay una aceptación inicialmente fallida legítima, la tarea queda fuera del flujo
actual: la persona puede preparar una refactorización manual supervisada. Ampliar
el motor sería otro diseño, fuera de este hito.

## Utilidad y decisiones para implementar

Los ejemplos [completo](ejemplos-v1.1/01-completo.md) y
[pendiente](ejemplos-v1.1/02-pendientes.md) son documentación sintética, no registros
de ejecuciones. Muestran el ahorro concreto frente a `propuesta.md`: separar el
contrato editable, traducir acciones a estados de base, reunir bloqueos heredados
y distinguir referencias consultadas de autoridades por preparar. No prometen
ahorrar la escritura del evaluador, prompts o revisión semántica.

Decisiones propuestas para comenzar la implementación:

1. Adoptar el comando, códigos y condición de exportación descritos; diagnóstico
   sin contrato/configuración parciales cuando queda cualquier pendiente.
2. Mantener un único formato de borrador orientado a configuración v2, con
   `null` explícitos y sin conversión ejecutable automática.
3. Mantener el paquete local dependiente de sus originales; posponer archivo
   portable, detección semántica y asistencia para escribir evaluadores/prompts.
4. Implementar fuera del motor, reutilizando el lector y el renderizado literal;
   proteger el nuevo módulo si se añade. Conservar lectores y formatos históricos.
5. En el hito de código, comprobar con fixtures sintéticas: v1/v2/v3, pendientes
   omitidos por el modelo, decisiones acumuladas, referencias coincidentes con
   editables, base histórica distinta de HEAD, profundidad ocho, integridad/límites,
   destinos existentes/enlaces/interrupción y cero invocaciones/reservas. Un plan
   de refactor no debe generar autorización ni evidencias de aceptación.

El hito documental inicial solo contrastó enlaces, sintaxis y coherencia, sin
suites. La implementación posterior conserva estos tres documentos y añade
las comprobaciones descritas en la guía; no modifica el motor.

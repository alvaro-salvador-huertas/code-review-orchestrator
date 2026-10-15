# Protocolo de evaluación del flujo multicaso

Fecha de definición: **15 de octubre de 2026**, antes de nuevas llamadas al
modelo. Estado: **ejecuciones reales pendientes**. Este documento prepara el
experimento; sus comandos no se han ejecutado al redactarlo.

**Actualización documental posterior, 15 de octubre de 2026:** las dos
ejecuciones han terminado y se han auditado mediante una revisión automática
realizada por Codex. Véase el [informe de resultados](resultados-multicaso-2026-10-15.md).
El estado pendiente y la tabla originales describen el diseño previo; se
conservan junto con todos sus criterios, presupuestos y comandos. Esta nota
es posterior a las [fuentes congeladas](../runs/protocolo-multicaso-DelwGYlP/fuentes/evals/protocolo-multicaso.md),
que permanecen intactas. No constituye una instrucción de repetir las ejecuciones.

## Alcance fijado antes de ejecutar

Se realizará **una ejecución de `orchestrate_case.py` por caso**, primero
`case_01` y después `case_02`, sin concurrencia. Cada ejecución tendrá un máximo
de **dos intentos de desarrollo y cuatro invocaciones de `codex exec`**: una
invocación de desarrollador y, cuando proceda, una de revisor por intento.
El presupuesto conjunto es como máximo ocho invocaciones, sin transferir
presupuesto entre casos. `--version` y `exec --help` son consultas locales y
no cuentan como llamadas al modelo. Las acciones internas de una sesión no
equivalen al número de invocaciones del orquestador.

Cada caso comienza desde su implementación defectuosa del benchmark. Se mantiene
el código, la configuración disponible, los contratos, las pruebas y los prompts
durante las dos ejecuciones. No se aplicarán candidatos al benchmark ni se
introducirán reparaciones manuales entre intentos. El segundo intento, si existe,
lo inicia exclusivamente el orquestador a partir de evidencia válida.

Se conservan todos los resultados, incluidos fallos de arranque, timeouts,
rechazos e interrupciones. **No se repetirá una ejecución hasta obtener una
aprobación**, ni se sustituirá una ejecución fallida por otra satisfactoria.
Tampoco se lanzarán reparación o revisión independientes como continuación de
este experimento. Un fallo técnico no habilita un reintento manual. Si impide
mantener las condiciones para el otro caso, este quedará como «no ejecutado»,
con su motivo, sin cambiar código o requisitos para completar la tabla.

## Implementación y comprobaciones de partida

La implementación leída está en `feat/orquestacion-multicaso`, sobre `deb475b`,
revisión que contiene la orquestación acotada. Hay cambios sin commit, incluidos
archivos nuevos: **el identificador de Git por sí solo no identifica el código
que se ejecutará**. Se conservarán también el diff y una copia con hashes de los
archivos efectivos, incluidos los no versionados.

La lectura abarca los cuatro controladores, `case_config.py`, `case_evidence.py`,
ambos prompts, contratos y pruebas. La configuración común resuelve el caso;
la revisión lo obtiene del JSON de reparación y contrasta sus referencias,
informes, candidato y procedencia. Los registros de reparación usan formato 2;
el caso 02 conserva contrato versión 2 y el caso 01 no declara versión de
contrato (`version_contrato: null` en el resumen general).

Se reutilizan las comprobaciones de la ampliación, descritas en el
[README](../README.md#ampliación-a-ambos-casos-15-de-octubre-de-2026): **108 pruebas
correctas, código 0, en 39,797 s**, con Codex simulado; incluyen los escenarios
de ambos casos y el rechazo de evidencia cruzada. Las evaluaciones originales,
en procesos separados, dieron 1 fallo entre 4 pruebas del caso 01 y 7 entre 16
del caso 02. Son resultados previos, no observaciones de este experimento.
Los históricos reales siguen documentados en el
[informe anterior](resultados-2026-10-14.md) y no forman parte de la nueva muestra.

Este paso solo añade documentación: no vuelve a ejecutar la suite ni al modelo.
Si antes de las ejecuciones cambia código, prompts, contratos o pruebas, deberá
registrarse el cambio y revisarse la pertinencia de esas comprobaciones antes
de empezar; no se atribuirá la validación anterior a código distinto.

## Evidencia que se recogerá

| Ámbito | Evidencia y contraste |
| --- | --- |
| Código usado | Rama, revisión completa de Git, estado del árbol, diff, copias y SHA-256 de fuentes, prompts y pruebas. Anotar quién revisó esa copia, cuándo y qué discrepancias encontró respecto a este protocolo. |
| Contrato y referencias | Caso declarado, contrato completo y versión si existe, original defectuoso y pruebas exactas de `referencia/`. Caso 01: acumulación, nombres exactos, entrada vacía, conservación de lista y diccionarios y ausencia de entrada/salida. Caso 02: prioridades, espacios en blanco según `str.isspace()` y pureza de versión 2. |
| Entorno y configuración | Python, intérprete, sistema operativo, ruta de Codex, versión y ayuda de CLI conservadas por cada etapa, comandos y opciones efectivas registrados. Modelo, proveedor y esfuerzo solo cuando estén disponibles, indicando de qué archivo, evento o configuración declarada se obtienen. Si no constan, escribir «no consta»; no deducirlos del nombre de la CLI ni copiar credenciales. |
| Registros y procesos | Ruta exacta del registro general y de cada reparación/revisión enlazada, comando manual, stdout, stderr y código de salida de la terminal. No seleccionar la carpeta más reciente ni asociar registros solo por su nombre. |
| Evaluaciones por intento | Estado, código, informe completo, total, correctas, fallos, errores y omisiones de las pruebas iniciales y posteriores. Identificadores y total contrastados con las referencias mediante AST, sin importar módulos. La evaluación inicial del intento 2 corresponde al candidato previo, no a otra ejecución del original. |
| Candidato y continuidad | `partida.py`, `candidato.py`, copias evaluadas, hashes, los tres diffs, procedencia y feedback. La partida del intento 2 debe ser idéntica al candidato del intento 1 y conservar contrato, pruebas y original del mismo caso. |
| Revisión y decisión | Respuesta original, dictamen validado si existe, hallazgos y ejemplos, `dictamen_modelo`, `decision_controlador`, `aprobada`, códigos y errores. Leer los eventos para contrastar las acciones del revisor con su encargo estático. La explicación del desarrollador no sustituye pruebas ni dictamen. |
| Integridad y consumo | Todas las comprobaciones y hashes del resumen general y sus etapas; referencias y registros intactos. Fechas UTC, duración monotónica general y por proceso, intentos iniciados e invocaciones por rol y total. Registrar los datos ausentes sin estimarlos como cero. |

Los límites vigentes son **180 segundos por agente, 30 por evaluación y 10 por
consulta previa de la CLI**. No hay timeout global adicional. Se contrastarán
los comandos guardados: aprobaciones `never`, web y delegación desactivadas,
sesiones nuevas, desarrollador con `workspace-write` y revisor con `read-only`.
No se fijará retrospectivamente un modelo o configuración que el registro no
acredite. Si la configuración efectiva cambia entre casos, se anotará como
limitación de comparabilidad sin volver a ejecutar el primero.

## Criterios separados

1. **Funcionamiento del controlador:** «conforme en el recorrido observado» si
   elige y mantiene el caso, registra de forma coherente las etapas, respeta los
   presupuestos y timeouts, conserva integridad y continuidad y toma la
   transición que justifica la evidencia. Una detención correcta por fallo
   técnico puede cumplir este criterio sin completar desarrollo y revisión.
   «No conforme» requiere una discrepancia observada, por ejemplo continuar
   tras evidencia inválida o exceder el presupuesto. «No evaluable» corresponde
   a evidencia insuficiente. La aprobación no es el criterio de funcionamiento.
2. **Pruebas del candidato:** «superadas» solo si la evaluación posterior termina
   con código 0, acredita todos los identificadores y el total de las pruebas
   de referencia, sin omisiones, y conserva candidato y pruebas. Registrar
   «fallos de aserción» por separado de «fallo técnico», «no evaluadas» o
   «evidencia insuficiente». Un código 0 del agente o un `OK` aislado no basta.
3. **Revisión del candidato:** consignar literalmente el dictamen válido
   `aprobar` o `solicitar_cambios` y sus hallazgos. Distinguirlo de «respuesta
   inválida», «revisor no invocado» y «revisión incompleta». La decisión final
   del controlador se registra aparte: una respuesta `aprobar` con timeout,
   salida no cero, alteraciones o fallos de registro no acredita una aprobación.
   La lectura humana contrastará los hallazgos con el contrato y el código;
   cualquier discrepancia se documenta sin editar el dictamen conservado.

Una ejecución termina aprobada solo con `estado: aprobada`, `codigo_salida: 0`
y `aprobada: true` en el resumen general, respaldados por las pruebas, revisión
e integridad exigidas. Superar las pruebas disponibles y recibir aprobación
son observaciones distintas; ninguna demuestra corrección general.

## Primer intento, corrección y detenciones

**Aprobación en el primer intento:** un único intento, una invocación de cada
rol y decisión final aprobada. El presupuesto de dos intentos no demuestra que
se haya usado el segundo. Se anotará «corrección automática no observada».

**Corrección automática observada:** debe existir una segunda invocación real
del desarrollador dentro del mismo registro general, motivada por aserciones
completas o por `solicitar_cambios` validado. Deben coincidir los bytes de la
partida con el candidato anterior, los hashes, la procedencia, los diffs y el
feedback enviado. Una transición `corregir` sin esa invocación solo acredita
una corrección prevista. Si el agente no entrega candidato o no se completa
su evaluación, registrar «corrección iniciada, resultado incompleto». Si entrega
los mismos bytes, registrar «segundo intento sin cambio de candidato».

Se reservará **«corrección satisfactoria»** para un cambio del candidato que
resuelva el motivo acreditado del segundo intento, supere la evaluación
posterior y reciba aprobación válida del controlador. Si solo cambia el
dictamen, sin cambio de código, se describirá como tal. Los recuentos posibles
son comprobaciones de coherencia, no resultados previstos: tras fallos de
pruebas puede haber tres invocaciones; tras una revisión con cambios, cuatro.

Los códigos siguientes corresponden al **orquestador**; se guardarán también
los códigos propios de reparación, revisión y pruebas, que no son equivalentes.

| Situación | Registro e interpretación |
| --- | --- |
| `intentos_agotados`, código 1 | Conservar ambos candidatos e informes o dictámenes pendientes. No es un error técnico por sí mismo ni habilita un tercer intento. |
| Argumentos inválidos, código 2 | Conservar comando y stderr aunque no se cree registro. La ejecución programada queda fallida, sin reemplazarla por otro lanzamiento. |
| Fallo de agente/revisor, código 3; timeout, código 4 | Guardar etapa, estado, código, diagnóstico y salidas parciales. No inferir una causa que los datos no demuestren ni convertirlo en defecto funcional del candidato. |
| Respuesta inválida, código 5 | Conservar el texto original y el error de validación; no repararlo a mano para aprobar. |
| Integridad alterada, código 6; evidencia inválida, código 7 | Conservar diferencias y motivo; no corregir hashes, mezclar casos ni reclasificar registros antiguos. |
| Fallo del controlador o error de pruebas, código 8 | Conservar traceback o diagnóstico, fase y archivos disponibles. Un error de importación o ejecución no se contabiliza como aserción fallida. |
| Interrupción, `en_curso`, código `null`, archivos ausentes o resumen contradictorio | Marcar «incompleto» y señalar el último paso acreditado. Guardar la salida de terminal y el código del proceso si existe. No asumir aprobación, cero invocaciones ni duración final. Si solo puede acreditarse un mínimo de invocaciones, consignarlo como límite inferior y dejar el total desconocido. |

## Comandos manuales

Ejecutar los bloques en la misma terminal Bash, una sola vez por bloque, cuando
se decida iniciar el experimento. La preparación no llama a Codex. Crea una
carpeta nueva de evidencia en `runs/`, separada de los registros del controlador;
no modifica registros anteriores ni necesita commit o push.

```bash
cd ~/Documentos/Personal/code-review-orchestrator
mkdir -p runs
EXPERIMENTO_MULTICASO_DIR="$(mktemp -d "$PWD/runs/protocolo-multicaso-XXXXXXXX")"
export EXPERIMENTO_MULTICASO_DIR
git branch --show-current > "$EXPERIMENTO_MULTICASO_DIR/rama.txt"
git rev-parse HEAD > "$EXPERIMENTO_MULTICASO_DIR/revision.txt"
git status --short > "$EXPERIMENTO_MULTICASO_DIR/git-status.txt"
git diff --binary HEAD > "$EXPERIMENTO_MULTICASO_DIR/cambios.patch"
python3 -B - <<'PY'
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys

root = Path.cwd()
destination = Path(os.environ["EXPERIMENTO_MULTICASO_DIR"])
files = [Path(name) for name in (
    "run_case.py", "repair_case.py", "review_case.py", "orchestrate_case.py",
    "case_config.py", "case_evidence.py", "README.md", "evals/protocolo-multicaso.md",
)]
for folder, pattern in (("tests", "*.py"), ("benchmark", "*.py"),
                        ("tasks", "*.md"), ("prompts", "*.md")):
    files.extend(Path(folder).rglob(pattern))
hashes = {}
for path in sorted(files):
    content = path.read_bytes()
    target = destination / "fuentes" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    hashes[path.as_posix()] = hashlib.sha256(content).hexdigest()
metadata = {
    "preparacion_utc": datetime.now(timezone.utc).isoformat(),
    "directorio": str(root), "python": sys.version, "interprete": sys.executable,
    "sistema": platform.platform(), "codex_en_path": shutil.which("codex"),
}
for name, value in (("fuentes.sha256.json", hashes), ("entorno.json", metadata)):
    (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)
                                    + "\n", encoding="utf-8")
print(destination)
PY
```

Antes del primer lanzamiento, revisar la copia guardada y anotar en un archivo
nuevo `notas.md` de esa carpeta: persona y fecha de revisión, correspondencia
con este protocolo, comprobaciones anteriores reutilizadas y configuración
conocida con su fuente. Las versiones de Codex y opciones usadas se recogerán
en los registros de cada etapa; si la CLI no llega a responder, se dejará
constancia de ello. No ejecutar si la preparación o la revisión previa falla.

Lanzamiento único del caso 01; se captura el código aun cuando falle:

```bash
if python3 -B orchestrate_case.py case_01 --max-attempts 2 \
    > "$EXPERIMENTO_MULTICASO_DIR/case_01.stdout.txt" \
    2> "$EXPERIMENTO_MULTICASO_DIR/case_01.stderr.txt"; then
    codigo_multicaso=0
else
    codigo_multicaso=$?
fi
printf '%s\n' "$codigo_multicaso" > "$EXPERIMENTO_MULTICASO_DIR/case_01.codigo.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_01.stdout.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_01.stderr.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_01.codigo.txt"
```

Revisar sus archivos antes de seguir. El caso 02 se ejecutará una sola vez,
independientemente de que el caso 01 haya sido aprobado, siempre que se puedan
mantener las mismas condiciones y la integridad de los materiales:

```bash
if python3 -B orchestrate_case.py case_02 --max-attempts 2 \
    > "$EXPERIMENTO_MULTICASO_DIR/case_02.stdout.txt" \
    2> "$EXPERIMENTO_MULTICASO_DIR/case_02.stderr.txt"; then
    codigo_multicaso=0
else
    codigo_multicaso=$?
fi
printf '%s\n' "$codigo_multicaso" > "$EXPERIMENTO_MULTICASO_DIR/case_02.codigo.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_02.stdout.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_02.stderr.txt"
cat "$EXPERIMENTO_MULTICASO_DIR/case_02.codigo.txt"
```

Los controladores evalúan cada copia en un proceso Python separado; no se
importarán conjuntamente módulos llamados `solution` o `test_solution`.
No se ejecutarán de nuevo las pruebas o revisiones sobre un candidato para
rellenar huecos del registro: esos huecos forman parte del resultado observado.

## Archivos que revisar tras cada ejecución

1. En la carpeta del experimento: `case_XX.stdout.txt`, `case_XX.stderr.txt` y
   `case_XX.codigo.txt`. Anotar en `notas.md` la ruta exacta impresa en `Registro:`
   y cualquier ausencia; conservar también la copia de fuentes y el entorno.
2. En el registro general: `resultado.json` y `referencia/{contrato.md,solution.py,test_solution.py}`.
   Seguir las rutas explícitas de `intentos[].reparacion.registro` y
   `intentos[].revision.registro`; una revisión puede no existir.
3. En **cada** reparación: `resultado.json`, `referencia/`, `partida.py`,
   `candidato.py`, `partida.diff`, `correccion.diff`, `candidato.diff`,
   `feedback.json` y `inicial/` y `posterior/` con sus resultados, canales y
   copias de `workspace/`.
4. En el agente de cada reparación: `agente/entrada.txt`, `resultado.json`,
   `codex_version.txt`, `version/`, `ayuda/`, `eventos.jsonl`, `errores.txt`,
   `respuesta_final.txt` y `test_solution_despues.py`, si se llegaron a producir.
5. En **cada** revisión: `resultado.json`, `origen.json`, `materiales/`,
   `dictamen_validado.json` si existe y `revisor/` con `entrada.txt`,
   `resultado.json`, `respuesta_original.txt`, `eventos.jsonl`, `stderr.txt`,
   `codex_version.txt`, `version/` y `ayuda/`.

Contrastar los hashes originales con la copia previa, la igualdad del candidato
evaluado y revisado, y los inventarios de registros enlazados. Registrar también
si una comprobación no pudo completarse. Añadir observaciones al informe nuevo;
no editar los JSON, candidatos, canales ni hashes conservados. Guardar las
carpetas completas, sin eliminar intentos fallidos ni truncar eventos. `runs/`
está fuera de Git: conservarlo localmente es necesario aunque el informe resuma
sus resultados. Mantener intactos todos los históricos anteriores.

## Tabla de resultados del nuevo experimento

Todas las celdas de observaciones permanecen pendientes hasta leer la evidencia
de las nuevas ejecuciones. Los límites fijados arriba no son consumos medidos.
Para cada caso, detallar en `notas.md` cada intento y las rutas de sus materiales;
si una etapa no se ejecuta, escribir «no ejecutada» y el motivo, no «pendiente»
como si hubiera una repetición programada.

| Caso | Registro general y etapas | Funcionamiento del controlador | Pruebas iniciales y posteriores, por intento | Dictamen y decisión del controlador | Corrección automática | Integridad | Intentos e invocaciones por rol/total | Duración |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `case_01` | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| `case_02` | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

## Qué se podrá concluir y qué seguirá pendiente

El experimento permitirá describir, para estas dos ejecuciones y sus condiciones
registradas, qué partes del flujo funcionaron, qué pruebas pasaron los candidatos,
qué dictaminó el revisor y qué decidió el controlador, con qué consumo y qué
fallos. Permitirá afirmar que hubo una corrección automática real solo cuando
su cadena de evidencia esté completa. Si ambos casos aprueban en el primer
intento, la corrección automática seguirá sin observarse en este experimento;
su cobertura simulada no se convertirá en evidencia real.

**Dos casos pequeños no permiten medir fiabilidad general**, estimar una tasa
de éxito representativa ni comparar de forma concluyente modelos o casos.
Tampoco bastan para demostrar corrección fuera de las pruebas, calidad general
del revisor o comportamiento ante fallos que no aparezcan en estas ejecuciones.

El caso 01 anuncia su defecto tanto en el contrato como en el docstring y un
comentario de la implementación. El desarrollador recibe esas pistas aunque
no reciba el README: una reparación satisfactoria no constituye diagnóstico
ciego. Sus cuatro pruebas no comprueban por separado nombres que solo difieren
en mayúsculas; la revisión debe valorar ese requisito del contrato. Estas
limitaciones se conservarán en las conclusiones, sin modificar los materiales
para disimularlas. Una aprobación tampoco prueba aislamiento de seguridad:
las comprobaciones de integridad observan el estado final y los hashes no
autentican una falsificación consistente.

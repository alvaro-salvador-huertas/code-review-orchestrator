# Protocolo propuesto: ocho diffs Python para review_diff

Esta PR prepara una campaña, **no la ejecuta con un modelo**. Los casos y sus
expectativas quedan sujetos a revisión humana antes de autorizarla. El modo C++
snapshot queda fuera. `review_diff.py` conserva su interfaz y su política Codex;
el nuevo `evaluate_review_diff.py` reutiliza sus materiales, esquema, validación
de citas y `run_review()`. No desarrolla, incorpora ni ejecuta candidatos.

## Casos y expectativas anteriores a la campaña

El [catálogo](../evals/review_diff/casos.json) es la fuente canónica: ocho IDs
neutros, dos versiones completas de `module.py`, criterios literales, SHA
completos de ambos commits, expectativa y justificación con un ejemplo razonado.
Solo se consideran las entradas del dominio declarado. Cuatro cambios conservan
el contrato; los otros cuatro introducen exactamente un defecto funcional D1.
Los ejemplos son evidencia razonada, **no resultados de haber ejecutado esos
candidatos**. La preparación analiza sintaxis y lee objetos Git; no los importa.

| Caso | Contrato entregado (resumen; texto literal en el catálogo) | Expectativa y evidencia |
| --- | --- | --- |
| caso_01 | Seleccionar enteros dentro de [low, high], inclusivo; conservar orden, duplicados, vacío y entrada. | Correcto. La comparación encadenada equivale a las dos desigualdades; `[1,2,2,3]`, límites 1 y 2 → `[1,2,2]`. |
| caso_02 | Contar todas las cadenas, suma de recuentos igual a longitud; vacío `{}`, sin mutación. | D1: sobrescribe con 1 en vez de acumular. `['a','a','b']` → `{'a':1,'b':1}`, esperado `{'a':2,'b':1}`. |
| caso_03 | Seleccionar enteros menores o iguales al límite; preservar orden, duplicados y vacío. | D1: cambia `<=` por `<`. `[2,3,3]`, límite 3 → `[2]`, esperado `[2,3,3]`. |
| caso_04 | Sumar una lista finita de enteros, incluidos negativos; vacío 0, sin mutación. | Correcto. `sum(values, 0)` conserva el neutro y las sumas del bucle; `[-2,5,-1]` → 2. |
| caso_05 | Último entero de una lista o `None` si está vacía; sin mutación. | D1: elimina la guarda. `[]` lanza `IndexError`, esperado `None`. |
| caso_06 | Mínimo número de lotes: count entero no negativo y size entero positivo. | Correcto. Cociente más uno si hay resto equivale al techo; `(7,3)` → 3 y `(0,3)` → 0. |
| caso_07 | Separar enteros negativos/no negativos en listas nuevas, sin perder orden, duplicados ni recuento; vacío `([],[])`. | Correcto. `<0` y `>=0` son una partición exhaustiva; `[-1,0,-1,2]` → `([-1,-1],[0,2])`. |
| caso_08 | Media con división real de hasta 1000 enteros entre -1000 y 1000; vacío 0, sin mutación. | D1: usa `//`. `[1,2]` → 1, esperado 1.5. El dominio acotado evita un problema previo de representabilidad de float. |

Los commits se reconstruyen en un repositorio Git bare privado con blobs, árboles,
autor, fecha, mensajes y formato SHA-1 fijos. No dependen de la configuración
personal ni del reloj. La preparación verifica los 16 SHA contra el catálogo;
las refs del repositorio sintético conservan los objetos. No se agregan esos
commits al historial del orquestador. No se promete identidad de los bytes
comprimidos de `.git` entre versiones de Git: sí los IDs de los objetos.

## Preparación y comprobación sin modelo

Desde la raíz de un clon completo, Python 3.12, Git y biblioteca estándar:

```bash
mkdir -p runs
python3 -B evaluate_review_diff.py check --output runs/review-diff-comprobacion-01
```

El destino debe ser nuevo y su padre existir. Este comando congela corpus,
protocolo, herramientas y vistas previas; crea **informes y juicios sintéticos**
marcados como tales, con cero invocaciones; conserva los archivos y escribe
`comprobacion.json` con resultados por caso y totales. No busca ni llama a Codex,
no necesita autenticación o red y no requiere Podman: aquí no se ejecuta Python
de un proyecto. Los agentes siguen la política Codex existente, fuera de la
frontera Podman de ejecución de pruebas.

`preparacion.json` contiene inventarios SHA-256, orden y configuración solicitada.
`preparacion/fuentes/` conserva los bytes y `git.json`/`cambios.patch` la revisión
del orquestador y el estado de las rutas relevantes, como `evaluate_reviewer.py`.
Los no versionados de esas rutas se conservan como fuentes aunque no aparezcan
en el diff Git. Cada `preparacion/caso_NN.json` es una vista previa reproducible.
Para comprobar una de ellas mediante la CLI de producción, usar los SHA completos
y los dos criterios literales de ese caso en el catálogo:

```bash
python3 -B - <<'PYTHON'
import json, subprocess, sys
from pathlib import Path
experiment = Path('runs/review-diff-comprobacion-01').resolve()
cases = json.loads((experiment/'preparacion/fuentes/evals/review_diff/casos.json').read_text())['casos']
for case in cases:
    command = [sys.executable, '-B', 'review_diff.py', '--repo', str(experiment/'preparacion/repo.git'),
               '--base', case['commits']['base'], '--candidate', case['commits']['candidato'],
               '--file', case['archivo']]
    for criterion in case['criterios']:
        command += ['--criterion', criterion]
    preview = json.loads(subprocess.check_output(command))
    assert preview == json.loads((experiment/'preparacion'/f"{case['id']}.json").read_text())
    print(case['id'], preview['estado'])
PYTHON
```

Cada contexto contiene únicamente las dos versiones seleccionadas, sus hashes,
el diff y los criterios. El workspace temporal del revisor contiene exactamente
`materiales.json` y `respuesta.schema.json`; recibe las instrucciones originales
de `review_diff`. **No se copian las expectativas, los contraejemplos del evaluador,
el catálogo, los informes sintéticos ni los juicios.** Los IDs de caso tampoco
se añaden al material. Esta separación de contexto no convierte el modo Codex de
solo lectura en una garantía de confidencialidad frente a un agente que incumpla
las instrucciones; se conserva el alcance del [piloto](revision-diff.md).

## Comando de la campaña real: pendiente de autorización

Después de revisar esta PR y sus expectativas, desde el commit aprobado limpio:

```bash
mkdir -p runs
python3 -B evaluate_review_diff.py prepare --output runs/review-diff-real-01
# Revisar preparacion.json y las ocho vistas previas antes de autorizar el envío.
python3 -B evaluate_review_diff.py run --experiment runs/review-diff-real-01 --invoke-model
```

`prepare` no usa modelos. `run --invoke-model` autoriza el envío y llama a
`review_diff.run_review()` una sola vez por caso en orden fijo: **hasta ocho
llamadas, una por caso, 180 s por llamada y cero reintentos**. Los preflights
locales de versión/ayuda de Codex no son llamadas al modelo. La creación exclusiva
de `lanzamiento/` es la reserva permanente: se rechaza repetir o reanudar, incluso
tras un fallo o interrupción. No abrir otra preparación para ocultar intentos;
cualquier nueva campaña debe declararse y aprobarse por separado.

Un informe disponible continúa al siguiente caso aunque esté vacío o contenga
hallazgos. Un fallo técnico (CLI, timeout, respuesta inválida, integridad,
archivo incompleto o cambio de versión/argumentos de Codex) detiene el lanzamiento;
los casos restantes quedan `no_ejecutado`, no como defectos omitidos. Se conservan
materiales, respuesta original, eventos, diagnósticos, reservas e inventarios de
cada revisión. El código 0 de `run` significa ocho informes disponibles, **no ocho
respuestas correctas**; 1 es campaña incompleta; 2 es entrada/reserva inválida.
No se reemplaza evidencia de una ejecución anterior.

Se registra la configuración solicitada y la versión/argumentos observados de
CLI; se exige continuidad de estos últimos. `review_diff` no fija modelo,
proveedor o esfuerzo: pueden proceder de la configuración Codex personal. Los
parámetros efectivos quedan «no consta» salvo evidencia de los eventos; no se
leen ni publican credenciales. El protocolo es repetible, no una promesa de
determinismo del servicio ni de igualdad de parámetros efectivos.

## Juicio humano y puntuación de archivos conservados

```bash
python3 -B evaluate_review_diff.py judgments --experiment runs/review-diff-real-01 \
  --output runs/review-diff-real-01/juicios.json
# Una persona rellena autor, revision_completa, justificacion y cada hallazgo.
python3 -B evaluate_review_diff.py score --experiment runs/review-diff-real-01 \
  --judgments runs/review-diff-real-01/juicios.json > runs/review-diff-real-01/puntuacion.json
```

El lector no importa fuentes ni ejecuta materiales archivados. Verifica la
preparación, los hashes de cada informe, las citas con el validador existente y
la correspondencia entre respuesta original y resumen. Admite los registros de
este protocolo, que envuelven el formato original de `review_diff`; no acepta
un informe suelto sin vincularlo a su preparación. Los hashes son integridad local,
no una firma frente a reescribir toda la evidencia.

Cada caso necesita `revision_completa: true` y razón, incluso si no hay hallazgos.
Para cada hallazgo, una persona debe declarar `respaldado` (booleano), justificarlo
con contrato/código y, si detecta la regresión fijada, asignar `defecto: "D1"`.
Las posiciones y hashes vinculan el juicio al hallazgo y al lanzamiento exactos.
No basta con una cita válida, una palabra clave o un dictamen del modelo.

- D1 respaldado se cuenta una vez por caso, aunque aparezca varias veces; se
  muestra aparte el número de menciones duplicadas.
- Sin D1 en un informe válido y juzgado, el defecto esperado está omitido.
- Hallazgos no respaldados en casos correctos son falsos; se cuentan hallazgos
  y casos afectados por separado.
- Hallazgos no respaldados adicionales en casos defectuosos se cuentan aparte;
  no se convierten en detecciones ni se ocultan por haber detectado D1.
- Un hallazgo respaldado que no corresponde a D1 se marca como adicional
  respaldado y exige revisar la expectativa; no se cambia la verdad fijada ni
  se convierte automáticamente en falso.
- Juicios pendientes y fallos técnicos no se computan como omisiones del revisor.
  Un archivo alterado/incompleto es fallo técnico. Un denominador cero produce
  proporción `null`, nunca un cero inventado.

Se muestran por caso los denominadores de defectos, correctos y hallazgos
evaluables. Los totales separan 8 casos planificados, 4 correctos y 4 defectos,
cobertura, detección/omisión entre defectos evaluables, correctos afectados entre
correctos juzgados y adicionales no respaldados entre hallazgos en defectuosos.
Fallos técnicos y no ejecutados usan denominador 8. Publicar siempre numerador,
denominador y no evaluables; no esconder la cobertura tras una proporción alta.
`score` devuelve 1 si faltan juicios o hay adicionales respaldados; 0 significa
puntuación disponible, que puede incluir fallos técnicos; 2 rechaza evidencia o
juicio incoherentes. No es una aprobación para incorporar cambios.

## Lo comprobado con los fixtures, no con un revisor real

Los [informes sintéticos](../evals/review_diff/informes_sinteticos.json) contienen
adjudicaciones ficticias, identificadas como tales. `check` escribe esas razones
en `juicios_sinteticos.json`; no afirma que las haya firmado una persona.
Se ensamblan independientemente para probar el lector y todos sus recuentos:
no simulan el orden de un lanzamiento real, que se detendría en caso_07 y
dejaría caso_08 sin ejecutar. Esa detención se comprueba con el adaptador simulado.

| Caso | Resultado sintético | Detectados / evaluables | Omitidos | Falsos en correcto | Adicional no respaldado | Duplicados |
| --- | --- | --- | --- | --- | --- | --- |
| caso_01 | Informe vacío | 0 / 0 | 0 | 0 | 0 | 0 |
| caso_02 | D1 dos veces y una afirmación adicional falsa | 1 / 1 | 0 | 0 | 1 | 1 |
| caso_03 | Informe vacío | 0 / 1 | 1 | 0 | 0 | 0 |
| caso_04 | Afirmación falsa sobre negativos | 0 / 0 | 0 | 1 | 0 | 0 |
| caso_05 | D1 respaldado | 1 / 1 | 0 | 0 | 0 | 0 |
| caso_06 | Informe vacío | 0 / 0 | 0 | 0 | 0 | 0 |
| caso_07 | Fallo técnico ficticio | no evaluable | no evaluable | no evaluable | no evaluable | no evaluable |
| caso_08 | Informe vacío | 0 / 1 | 1 | 0 | 0 | 0 |

Resultado esperado del fixture: 7/8 informes puntuados; detección 2/4 y omisión
2/4; un falso hallazgo afecta a 1/3 correctos evaluables (otro correcto no es
evaluable); un adicional no respaldado entre 4 hallazgos en defectuosos; una
mención duplicada; 1/8 fallos técnicos. **Estas cifras verifican la puntuación,
no miden calidad, sensibilidad ni tasa de alucinación de un modelo.**

Pruebas enfocadas sin modelo:

```bash
python3 -B -m unittest discover -s tests -p test_evaluate_review_diff.py -v
python3 -B -m unittest discover -s tests -p test_review_diff.py -v
python3 -B -m unittest discover -s tests -p test_review_snapshot.py -v
git diff --check
```

Comprueban los commits reproducibles, las ocho vistas previas por la CLI real,
el contexto limitado, juicios explícitos y ligados a sus archivos, denominadores,
duplicados, archivos alterados, reserva sin repetición y detención sin reintentos
con el adaptador simulado. Los dos jobs existentes de CI siguen comprobando la
suite ordinaria y las 13 integraciones reales de Podman; estas últimas acreditan
la frontera de pruebas de proyectos, **no una campaña real de revisión**.
Los recuentos y enlaces del SHA final se registran en la PR.

Queda pendiente medir al revisor real: detecciones, omisiones, falsos y adicionales,
fallos técnicos, configuración efectiva observada y tiempo de adjudicación humana.
Ocho casos de lógica sencilla no representan todos los diffs Python; no permiten
estimar fiabilidad general. Se conservan los ocho casos aunque un resultado
desfavorezca al revisor. La campaña y su publicación quedan para después de la
revisión humana de este protocolo; esta PR permanece en borrador.

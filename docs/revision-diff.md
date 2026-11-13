# Piloto: revisar un cambio propio de Python

`review_diff.py` revisa un cambio que ya existe en Git. No inicia desarrollo,
no requiere que falle la aceptación y no incorpora ningún cambio. El flujo
de orquestación y sus registros anteriores quedan aparte.

## Primera revisión: el refactor de booking_batch

Ejecuta desde la raíz del orquestador con Python 3.12 y Git. La base y el
candidato son los commits de la PR #25; no se lee el árbol de trabajo, el
índice ni los demás archivos del repositorio que se revisa.

```bash
revision=(
  --repo .
  --base 8e6415f117d1056f560801574297890d5ead9e17
  --candidate 9318c5b02c20daa7362194f40a2e4c2ee36ce38d
  --file booking_batch.py
  --criterion 'Conservar el comportamiento de la CLI y sus diagnósticos.'
  --criterion 'Conservar la lectura UTF-8 estricta y el rechazo de JSON no válido.'
  --criterion 'No escribir resultados parciales si una consulta posterior falla.'
)
python3 -B review_diff.py "${revision[@]}"
```

La vista previa imprime los materiales, las instrucciones y el esquema.
Incluye las dos versiones completas de cada archivo seleccionado, sus hashes,
el diff y los criterios; no invoca Codex, no ejecuta los archivos y no crea un
registro. Revisa esas versiones completas: enviar un diff también implica
enviar contexto que no cambió.

Si autorizas enviar esos materiales, ejecuta en la misma terminal:

```bash
mkdir -p runs
python3 -B review_diff.py "${revision[@]}" --invoke-model --output runs/piloto-booking-01
```

Se requiere un directorio nuevo y un Codex CLI configurado. El adaptador
existente comprueba la CLI, reserva como máximo una invocación de revisor con
un límite de 180 s y usa una sesión de solo lectura. No hay reintentos
automáticos. El directorio conserva materiales, esquema, instrucciones, salida
original, eventos, diagnósticos y `resultado.json`. No publiques el registro.
Un código 0 en este modo significa informe disponible, incluso si contiene
hallazgos; no equivale a aprobación. Un 1 indica fallo de revisión, un 2 indica
entrada u operación inválida y un 130 indica interrupción del revisor.

## Qué puede confirmar la herramienta

El controlador comprueba que la cita devuelta aparece en la línea y versión
indicadas y que el revisor no modificó su copia de los materiales. Una cita
exacta no valida el impacto del hallazgo. Clasifica cada propuesta como
**confirmada**, **descartada** o **pendiente**; anota la reproducción o la razón.
Si no hay hallazgos, solo significa que el revisor no informó de ninguno.
La herramienta no ejecuta ni acredita pruebas del cambio.

El piloto admite de uno a tres archivos Python UTF-8 modificados, presentes
como archivos regulares en ambos commits, y un máximo de 24 KiB por versión y
160 KiB de material combinado. Aún no admite altas, bajas, renombres, ramas
por nombre, cambios sin commit ni dependencias seleccionadas automáticamente.

El modo de solo lectura no es una garantía de confidencialidad ni un
aislamiento para repositorios no confiables. Usa repositorios locales de
confianza y selecciona únicamente material propio que tengas permiso para
enviar al servicio. No incluyas credenciales, código de terceros no autorizado
ni enunciados restringidos. Los registros pueden contener material sensible.

Para probar el piloto sin modelos:

```bash
python3 -B -m unittest discover -s tests -p test_review_diff.py -v
```

Antes de usarlo en más tareas, mide en cada revisión el tiempo que te lleva
comprobar el informe, cuántos hallazgos confirmas, cuántos descartas y si
cambiaste algo por lo que encontraste. Conserva solo evidencia publicable
cuando resumas el experimento.

## Una versión C++ sin historial de cambios

El modo `--snapshot SHA_COMPLETO` revisa una única versión de archivos `.cpp`,
`.h` y `.hpp`. No usa `--base` ni `--candidate`: no hay base artificial, diff
ni afirmaciones de regresión. Puede utilizarse con el único commit de una
copia local mínima; no hace falta inicializar Git en la entrega original.

Desde la raíz del orquestador, la vista previa se obtiene así (sustituye el
repositorio y el SHA por los de tu copia):

```bash
python3 -B review_diff.py \
  --repo /ruta/a/copia-local \
  --snapshot SHA_COMPLETO \
  --file src/estructura.cpp --file include/estructura.h \
  --criterion 'Comprobar los invariantes documentados de la estructura.'
```

Los materiales contienen `modo: snapshot`, `commit_snapshot` y una sola
versión completa por archivo bajo `snapshot`, con blob y SHA-256. La respuesta
utiliza `lado: snapshot`; se validan las citas literales contra sus líneas,
con los mismos límites de archivos, tamaño y hallazgos del piloto Python.
Incluye explícitamente las cabeceras propias necesarias: no se recopilan
dependencias, enunciados ni pruebas automáticamente.

La vista previa no llama al modelo. Para una revisión posterior autorizada,
añade `--invoke-model --output /ruta/a/registro-nuevo`; conserva el límite de
una invocación, sin reintentos. La revisión estática no compila ni ejecuta C++.

Pruebas enfocadas sin modelos (las invocaciones del revisor se simulan):

```bash
python3 -B -m unittest discover -s tests -p test_review_snapshot.py -v
python3 -B -m unittest discover -s tests -p test_review_diff.py -v
```

# Notas propuestas para v1.3.0

Esta propuesta reúne los cambios de `main` desde la versión estable v1.2.0 hasta
`6bf5db383e10622f0204f1e52e1722a484a08f1d`, fusión de la PR #44.
La versión publicada al preparar estas notas sigue siendo [v1.2.0](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/releases/tag/v1.2.0).

## De la URL de una PR al informe

1. Con `review_diff.py --pr-url`, selecciona la copia local, los archivos Python
   y los criterios. La CLI consulta la PR con `gh` en modo de lectura y muestra
   los SHA de la rama base, del candidato y de su ancestro común. El diff parte
   de ese ancestro aunque la base haya avanzado. Se requiere un historial completo.
   La vista previa identifica archivos fuera del diff e indica cómo traer manualmente
   los objetos que falten. [PR #43](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/43)
2. Ejecuta la lista JSON `comando_vista_previa` para repetir la comparación con
   los SHA fijados desde otro directorio de la misma máquina. Conserva archivos,
   criterios y opciones explícitas del revisor. La repetición solo lee Git local.
   [PR #44](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/44)
3. Inspecciona los textos completos, las instrucciones y el esquema. Si autorizas
   el envío, añade `--invoke-model --output DIRECTORIO_NUEVO` a esa misma lista.
   La revisión usa el modo con SHA explícitos y guarda los materiales y el informe.
   El modo `--pr-url` solo genera la vista previa. [Ejemplo ejecutable con la PR #42](revision-diff.md#vista-previa-de-una-pull-request-de-github)

La corrección de `--output` resuelve el directorio padre antes de indicar al
revisor dónde escribir su respuesta, incluso en rutas relativas con enlaces
simbólicos y `..`. El padre debe existir y el destino debe ser nuevo. Una ruta
final ya ocupada, incluso por un enlace roto, se rechaza antes de la invocación.
[PR #42](https://github.com/alvaro-salvador-huertas/code-review-orchestrator/pull/42)

También puedes seleccionar modelo, proveedor y esfuerzo de razonamiento. El
registro distingue la selección solicitada de la que el proceso pudo acreditar,
y los diagnósticos de timeout ayudan a examinar revisiones interrumpidas. Para
evaluar al revisor se incorporó un corpus de ocho diffs Python con expectativas
y puntuación por caso. Se documentaron cuatro campañas y un piloto sobre cuatro
cambios históricos. [Configuración y diagnósticos](revision-diff.md) · [Protocolo y resultados](evaluacion-review-diff.md)

## Qué se comprobó

- **ShiftLab #3, revisión real antes del merge.** El informe produjo cero hallazgos
  y sugirió comprobar qué pasaba si el destino de exportación aparecía justo antes
  de crearlo. El asistente verificó sobre el candidato que el exportador lanzaba
  `FileExistsError` y conservaba el archivo existente. Esa comprobación amplió la
  revisión. La decisión favorable de fusionar se mantuvo. [Relato de la revisión](evaluacion-review-diff.md#revisión-antes-del-merge-de-shiftlab-3)
- **PR #42 del orquestador, validación del flujo con revisor simulado.** En un
  worktree de `main` que incluía la PR #44, la consulta real a GitHub identificó
  `6d4fc2c4b6ca3e84a0002b6ea2f7bf860e318689` como base y ancestro común, y
  `b2bf13e6dd7f908692160a33624ff5a10cf4b5f7` como candidato. Ejecutar la lista
  desde otro directorio reprodujo materiales, instrucciones y esquema sin otra
  consulta a GitHub. Con `--invoke-model`, un destino nuevo y el revisor simulado
  del repositorio, la CLI guardó un informe válido y los mismos materiales que se
  habían inspeccionado.

El ahorro de tiempo sigue sin medir.

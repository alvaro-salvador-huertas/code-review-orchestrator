# Credenciales y entorno de los procesos

Revisión local del **17 de octubre de 2026**, en la rama
`eval/inspect-json-primer-intento`, con cambios pendientes conservados. No hubo
commit, push, llamadas reales al modelo ni acceso a archivos personales de
autenticación. Complementa la [revisión de publicación anterior](revision-publicacion.md).

## Búsqueda de credenciales

Se examinó el contenido completo de los archivos del árbol de trabajo destinados
a Git, incluidas las modificaciones y los archivos nuevos no ignorados; también
las versiones del índice, con independencia del árbol de trabajo. El índice
contiene 50 archivos y no tiene cambios preparados. La comprobación final incluye
60 archivos de trabajo: los 57 iniciales y los tres nuevos de este hito.

Se recorrieron los 12 commits alcanzables desde las referencias locales, sus
mensajes y metadatos, y 74 versiones distintas de archivos (pares ruta/blob).
De las 20 referencias locales, cinco apuntan directamente a árboles; se
examinaron también sus 11 versiones adicionales: **85 versiones en total**.
El clon no es superficial. No se contactó con remotos ni con servicios para
comprobar claves. El análisis de nombres incluyó rutas sensibles históricas,
aunque actualmente estén ignoradas.

Los patrones buscan cabeceras de claves privadas, prefijos reconocibles de
tokens, JWT, asignaciones de contraseñas y secretos con y sin comillas,
cabeceras de autorización y URL con credenciales. Las coincidencias solo se
presentan por categoría y ubicación. Se distinguen de hashes Git/SHA-256,
identificadores de ejecución, nombres de variables y datos sintéticos de pruebas.

**No se detectaron credenciales probables con esos patrones**, ni rutas sensibles
versionadas entre los materiales examinados. Esto incluye `runs/`, `.env*`,
`.aws/`, `.codex/`, `.agents/`, archivos de autenticación y claves privadas.
Las exclusiones actuales de Git siguen vigentes; no se añadieron registros.

Sí hay datos personales, conservados sin reproducir sus valores:

| Categoría | Ubicación |
| --- | --- |
| Ruta personal | `evals/resultados-multicaso-2026-10-15.md:257`, en trabajo, índice e historial |
| Correo de atribución | Metadatos de `5c7950d`, `0663d48`, `9bec532`, `8663f12`, `7a3d99e`, `7be0229`, `40db2dc`, `c75adca`, `deb475b`, `1af27a3`, `cc97b0b`, `a017eda` |

Hay 19 líneas de correo de atribución no `noreply` en esos commits. No son
credenciales; publicar el historial y el informe expondría esos datos. No se
reescribió ni eliminó evidencia.

Esta búsqueda no certifica ausencia absoluta de secretos. No cubre referencias
remotas no disponibles localmente, reflogs u objetos inalcanzables, archivos
personales ignorados, secretos ofuscados/codificados o formatos que no reconozcan
los patrones. Los registros privados no se publican ni se vuelcan para buscar
secretos: su comprobación aquí es de integridad, por hashes y metadatos.

## Política de evaluación

[`process_environment.py`](../process_environment.py) construye un diccionario
nuevo mediante una lista cerrada. No copia `os.environ` ni lo modifica.
[`run_process()`](../repair_case.py) usa `env_policy="evaluation"` por defecto;
el llamador de Codex debe seleccionar expresamente `"codex"`.

| Variables | Procedencia y motivo |
| --- | --- |
| `PATH` | Directorio del intérprete activo más `os.defpath`; permite Python y utilidades del sistema sin heredar directorios del PATH del usuario. |
| `LANG`, `LC_ALL`, `TZ` | Valores fijos `C.UTF-8` y `UTC`, para texto Unicode y resultados independientes de la zona del padre. |
| `PYTHONNOUSERSITE`, `PYTHONDONTWRITEBYTECODE`, `PYTHONUTF8`, `PYTHONIOENCODING` | Valores fijados por el controlador: desactivar paquetes del usuario y cachés, activar UTF-8. No se heredan otras opciones Python. |
| `HOME`, `USERPROFILE` | HOME nuevo y vacío por proceso de evaluación. |
| `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `XDG_RUNTIME_DIR`, `APPDATA`, `LOCALAPPDATA` | Directorios temporales nuevos para configuración, datos y cachés; evitan usar las ubicaciones personales por defecto. |
| `TMPDIR`, `TMP`, `TEMP` | Directorio temporal propio para los hijos. Se elimina al salir, también tras timeout o error. |
| `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL`, `GIT_TERMINAL_PROMPT` | Desactivar configuración Git global/de sistema y solicitudes interactivas; las consultas de procedencia usan también este entorno. |
| `SystemRoot`, `WINDIR` | Solo en Windows se toman del padre para localizar componentes del sistema. La validación realizada es en Linux. |

No se transmiten claves de servicios, sockets SSH, configuración de credenciales,
`PYTHONPATH`, `PYTHONHOME`, `PYTHONUSERBASE`, `LD_*`, `DYLD_*`, `NODE_OPTIONS`,
`BASH_ENV`, opciones Git del padre ni otras variables no incluidas. Los hijos
que se creen sin un `env` propio heredan esta misma reducción.

La política alcanza a la evaluación directa de `run_case.py`, las evaluaciones
de reparación y orquestación de benchmark, aceptación y regresión de proyectos,
y las evaluaciones de candidatos preparados de `evaluate_reviewer.py`.
Las consultas Git de ese lanzador, `repair_project.py` y `review_project.py`
también dejan de heredar el entorno completo. El inventario de fuentes del
lanzador incluye el nuevo módulo.

El [evaluador externo de inspect-json](../evals/tareas_reales/inspect_json/evaluar.py)
ya proporciona un entorno explícito de seis variables: PATH vacío, HOME y TMPDIR
de su fixture, y valores fijos para cachés, codificación y locale. Sus hijos
también reciben ese entorno. Se comprobó con una sonda, sin modificar el
evaluador ni su identidad respecto de la reevaluación histórica. El runner
de proyectos se ejecuta como hijo de `run_process()`; no se cambió su archivo.

## Política de Codex

Versión, ayuda y ejecución del desarrollador y del revisor utilizan
`env_policy="codex"`. Conservan solo estas excepciones sobre los valores básicos:

- `PATH`, para encontrar la CLI instalada por el usuario.
- `HOME`, `USERPROFILE`, `CODEX_HOME`, directorios `XDG_*`, `APPDATA` y
  `LOCALAPPDATA`, para localizar la configuración y autenticación ya existentes.
- `DBUS_SESSION_BUS_ADDRESS` y `XDG_RUNTIME_DIR`, para el acceso al servicio de
  credenciales del usuario cuando se utilice.
- `TMPDIR`, `TMP`, `TEMP`, para los temporales de la CLI.
- `OPENAI_API_KEY`, `CODEX_API_KEY`, `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`, para
  autenticación y selección de organización/proyecto cuando estén definidos.

No se heredan variables por prefijo ni credenciales de AWS, GitHub, bases de datos
u otros servicios. Un proveedor personalizado que necesite otra variable requiere
una ampliación deliberada de la lista; no existe un paso genérico de todo el
entorno. Tampoco se heredan opciones de carga de Python, Node o bibliotecas.

La autenticación no se copia a comandos, prompts o registros. Los resultados
nuevos solo añaden `politica_entorno`, sin inventarios ni valores de variables.
No se modifican archivos de configuración de Codex ni su autenticación. Las
interfaces, códigos, límites, captura de canales e interrupciones se conservan.
La evaluación independiente posterior reconstruye su propio entorno aunque el
padre haya usado antes autenticación para lanzar Codex.

## Validación y límites

Se añadieron nueve métodos en
[`tests/test_process_environment.py`](../tests/test_process_environment.py).
Usan valores ficticios, hijos y nietos Python, candidatos sintéticos y una CLI
simulada para los tres puntos de invocación de Codex. Comprueban variables
ausentes, Unicode, temporales, ausencia de carga desde `PYTHONPATH`/site del
usuario, ausencia de valores ficticios en registros, limpieza y separación de
las dos políticas. Las fixtures de CLI existentes copian el nuevo módulo.

Ejecuciones reales de comprobación, sin modelos:

1. Suite específica: 9 métodos, 8 correctos y 1 fallido, código 1. La sonda del
   inspector creaba un temporal; el evaluador detectó correctamente el cambio
   de mtime. Se corrigió solo la sonda para que no escribiese.
2. Regresión completa, una vez: 204 métodos en 67,753 s; 203 correctos y 1 fallo,
   código 1, sin errores ni omisiones. Los nueve métodos nuevos pasaron. El
   fallo restante era la expectativa antigua de un mock que no admitía el nuevo
   argumento `env`; sus aserciones de timeout y salidas sí se cumplieron.
3. Tras actualizar esa expectativa, se repitió únicamente el método afectado:
   1 correcto en 0,003 s, código 0. No se presenta la suite completa anterior
   como una ejecución de código cero ni se ha vuelto a ejecutarla.

Los informes de estas comprobaciones permanecen fuera de Git en
`/tmp/process-environment-audit/`: `especificas/`, `regresion/` y
`timeout-corregido/`. El resumen redactado de búsqueda es `auditoria.json`.
Se verifican además diff, enlaces, exclusiones y preservación de los 22 registros
históricos mediante su inventario inicial. Contratos, referencias, evaluador,
inspector original y candidato de inspect-json permanecen intactos respecto
del inicio de este hito; la entrega sigue sin aplicarse.

Los registros congelados conservan sus implementaciones anteriores. En
particular, la base de inspect-json contiene lanzadores que heredaban el entorno;
no se retocan esas fuentes ni se atribuye esta protección a resultados pasados.
Cuando una copia antigua se ejecuta dentro de una evaluación del controlador
actual, su proceso inicial recibe el entorno reducido. No se repitieron las
evaluaciones históricas de inspect-json.

**Filtrar variables no es aislamiento de seguridad.** No impide abrir archivos
personales por ruta absoluta, consultar otros procesos si el sistema lo permite,
acceder a la red, modificar el entorno desde el candidato o iniciar otros
ejecutables. No redacta secretos que un proceso obtenga por otra vía y decida
imprimir. Codex conserva acceso a su autenticación: el entorno de herramientas
que abra internamente depende de la CLI y de su sandbox; esta modificación no
reconfigura esas herramientas. La política cubre las evaluaciones independientes
del controlador, no una ejecución manual de `unittest` o del runner fuera de él.
No sustituye aislamiento de archivos/red ni valida credenciales reales.

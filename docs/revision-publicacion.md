# Revisión de contenido para publicación

Fecha: **15 de octubre de 2026**. Revisión automática realizada por **Codex**
sobre la rama `feat/orquestacion-multicaso`, base
`deb475b0b2f06f8a613016aec057730ce2b4b723`, con cambios previos sin commit.
No acredita una revisión humana, una certificación de seguridad o ausencia
absoluta de secretos. No se ha publicado nada ni se ha cambiado la visibilidad.

## Alcance comprobado

Antes de reorganizar la documentación se revisaron los **19 archivos
versionados**, sus versiones en el índice, los cambios del árbol de trabajo
y los **7 archivos nuevos no ignorados**. El índice no tenía cambios preparados.
La revisión incluyó los **4 commits alcanzables desde las referencias locales**,
sus mensajes, metadatos y las **28 versiones distintas de archivos** presentes
en ese historial, correspondientes a 19 rutas. Esto incluye las referencias
locales de seguimiento remoto disponibles; el clon no es superficial y no se
contactó con el servidor.

Se comprobaron nombres de archivos y contenido mediante búsquedas de claves
privadas, prefijos reconocibles de tokens, asignaciones de contraseñas o
secretos, URL con credenciales, correos y rutas personales. Se revisaron las
coincidencias por su contexto. Los resultados de la búsqueda solo mostraron
categorías y ubicaciones, sin reproducir valores sensibles.

No se detectaron credenciales reconocibles con esos patrones ni archivos de
`runs/`, `.env`, `.aws/`, `.codex/` o `.agents/` incluidos en el índice o en
ese historial. `.gitignore` mantiene excluidos esos registros y configuración
local. Ignorar una ruta no retiraría por sí solo un archivo ya versionado;
por eso se comprobó también el historial, no solo las reglas de exclusión.

La búsqueda no cubre referencias remotas que no estén disponibles localmente,
objetos inalcanzables o reflogs, servicios externos, secretos codificados o
formatos no reconocidos. No se abrieron credenciales ni configuración privada
ignoradas para copiar o documentar sus valores. No hubo nuevas llamadas al
modelo ni pruebas de código durante este trabajo documental.

## Datos que quedarían expuestos

| Ubicación | Observación y efecto |
| --- | --- |
| `evals/resultados-multicaso-2026-10-15.md:257` | Contiene una ruta absoluta del directorio personal y de la instalación de Codex. Revela un identificador local y estructura del entorno, aunque no es una credencial. El informe está entre los archivos pendientes de incorporar y se conserva intacto. |
| `evals/protocolo-multicaso.md:161` | Conserva un comando con la ruta personal de trabajo original. No es necesaria para el uso público; el protocolo se mantiene como diseño histórico y no se altera. |
| Metadatos `author` de `deb475b`, `1af27a3`, `cc97b0b`, `a017eda` | Incluyen nombre y correo no `noreply`. Son metadatos de atribución que se publicarían con los commits, no credenciales. Sus valores no se reproducen aquí. |
| Metadatos `committer` de `deb475b`, `cc97b0b`, `a017eda` | También contienen un correo no `noreply`; el merge `1af27a3` usa correo `noreply` de committer. No se han reescrito commits. |

El README anterior tenía además un comando con ruta personal. La guía de uso
reorganizada parte de la raíz del clon y pide la ruta que imprima el propio
controlador. Ese cambio responde a la portabilidad de los ejemplos; no elimina
ni modifica el protocolo, los informes o sus registros.

## Qué queda por resolver antes de publicar esta versión

No se identificó un bloqueo por credenciales o registros privados versionados
en el contenido revisado. Sí queda una **decisión de privacidad** sobre la ruta
personal conservada en el informe, la ruta del protocolo y los datos de autoría
del historial. Publicar esos documentos y commits tal como están expondría
esos datos. Esta revisión los identifica; no los elimina ni autoriza su difusión.

La implementación multicaso, el inspector, parte de las pruebas y documentación
siguen sin commit. **Publicar solo el HEAD actual no publicaría el prototipo
descrito por el README**. Será necesario incorporar deliberadamente los
archivos nuevos y cambios pertinentes cuando se decida publicar, manteniendo
fuera la evidencia local y la configuración privada. Este paso no hace commit,
push, merge ni modificaciones en el portfolio o la visibilidad del repositorio.

Los informes públicos explican los resultados sin `runs/`, pero no ofrecen
los archivos completos necesarios para repetir su auditoría byte a byte. Esa
es una limitación declarada de la evidencia disponible en un clon público,
no una instrucción de añadir todos los registros locales a Git.

## Comprobaciones de esta reorganización

El inventario de partida contiene 406 archivos existentes. La comparación de
SHA-256 solo detectó cambios en el README: permanecen intactos los otros 405,
incluidos los 380 archivos de `runs/`. Se añadieron únicamente las tres guías
de `docs/`; el código, contratos, pruebas, prompts e informes anteriores no
se modificaron.

Se revisaron 61 enlaces locales y sus anclas: 42 apuntan a contenido destinado
a Git y 19 a evidencia local de `runs/`, identificada como tal. Los destinos
locales existen; los 19 enlaces de evidencia no estarán disponibles en un clon
sin esos registros. Los siete bloques Bash de las guías tienen sintaxis válida
según `bash -n`, sin ejecutar sus comandos. `git diff --check` no señaló errores
de espacios. La búsqueda de patrones sensibles en el README final y las tres
guías nuevas no encontró coincidencias. La regresión de 126 pruebas es el
resultado previo documentado, no una comprobación repetida en este paso.

# Tarea real 007: HTTP local de disponibilidad

**Versión 1 — preparación; producto inicialmente ausente.**

Base: `d6e576d9fe756604881c171693ca48e8d0d19a36`

## Entrega y límites

Crear únicamente `booking_http.py` en la raíz, regular 0644. Configuración v2
con un solo editable inicialmente ausente; no crear un original vacío ni otro
módulo. Se protegen `booking_core.py`, `check_booking.py`, motor, pruebas y
autoridades. Solo biblioteca estándar. Se heredan el dominio del
[contrato 005](005-check-booking.md) y la API del [006](006-booking-core.md).

No hay almacenamiento, creación de reservas, archivos servidos, procesos
adicionales, red externa, autenticación, CORS, TLS, base de datos ni despliegue.
No se modifican entradas ni se duplican las reglas del núcleo.

## Proceso y API

```bash
python3 -B booking_http.py --port 8000
```

Escuchar exclusivamente en IPv4 `127.0.0.1`, sin opción para exponer otra interfaz.
`--port` admite un entero entre 0 y 65535, predeterminado 8000; 0 solicita el
puerto al sistema. `-h`/`--help` terminan con 0; argumentos incorrectos, con 2,
stdout vacío y diagnóstico en stderr. Ayuda: stdout no vacío y stderr vacío.
No se exige una redacción literal. Un fallo de arranque termina con 1, stdout
vacío y diagnóstico no blanco en stderr.

Solo después de enlazar y estar preparado para atender, escribir y vaciar
inmediatamente **una línea JSON** en stdout:

```json
{"host": "127.0.0.1", "port": 8000}
```

El puerto anunciado es el real, entero (no booleano), 1–65535. Claves exactas;
representaciones JSON equivalentes admitidas. No volver a escribir en stdout.
Se permiten logs de servicio en stderr. Ctrl+C cierra el servidor y sus recursos
sin traceback; no se fija un código de terminación por esa señal. Importar el
módulo no arranca servidores, produce salida, escribe archivos, lee stdin ni
inicia procesos o conexiones propios. No se exige un helper público `main`.

## HTTP y precedencia

Ámbito: HTTP/1.0 y HTTP/1.1 con línea, nombres de método y cabeceras bien formados.
No se exige un analizador HTTP completo, conexiones persistentes ni pipelining.
Las rutas son literales: query, barra final y otras variantes no son alias.
Se aplica este orden, sin leer innecesariamente el cuerpo:

1. Ruta distinta de `/health` y `/availability`: 404, con cualquier método.
2. Método distinto de GET en `/health` o POST en `/availability`: 405,
   `Allow: GET` o `Allow: POST`, respectivamente. Esto incluye HEAD y otros
   métodos sintácticamente válidos. GET `/health` devuelve 200 y
   `{"estado": "ok"}`; no interpreta un cuerpo de petición.
3. En POST `/availability`, presencia simultánea de Transfer-Encoding y
   Content-Length: 400. Transfer-Encoding sin Content-Length: 501.
4. Content-Length ausente: 411; duplicado (aunque coincida) o no decimal ASCII
   no negativo: 400. Se permite OWS exterior (espacio/tabulador), ceros iniciales;
   no signo, fracción, coma ni exponente. Un único valor superior a **65536**: 413
   antes de leer el cuerpo completo. No desbordar al interpretar números grandes.
5. Content-Type ausente o incompatible: 415. Se admite `application/json`, con
   `charset=utf-8` opcional, incluso entre comillas; tipo/subtipo, nombre y valor
   del parámetro no distinguen mayúsculas. Admitir OWS exterior y alrededor de
   `;` y `=`. No se permiten parámetros adicionales, repetidos, charsets distintos
   ni Content-Type duplicado. No hay espacios dentro de `application/json`.
6. Leer exactamente los bytes declarados, con un **plazo total máximo de 2 s**
   desde el comienzo de la lectura del cuerpo. EOF prematuro: 400. Plazo agotado:
   408 cuando el cliente todavía permita responder. No se exige detectar bytes
   posteriores al cuerpo declarado; se cierra siempre la conexión.
7. UTF-8 estricto sin BOM, un único documento JSON; espacios JSON exteriores
   permitidos. Rechazar claves duplicadas a cualquier profundidad, NaN e Infinity.
   Cualquier error de decodificación/JSON o `booking_core.InvalidInput`: 400.
8. Delegar el documento decodificado en `booking_core.check_booking` y devolver
   exactamente su resultado con 200, con o sin conflictos. No duplicar validación
   de dominio ni cálculo. La sintaxis de importación es libre dentro del alcance
   del motor; no se añaden nombres públicos obligatorios.

La precedencia 1–2 se aplica también si hay cabeceras de cuerpo inválidas: p. ej.,
POST `/otra` sin longitud es 404 y GET `/availability` sin longitud es 405.
En POST válido, TE+CL prima sobre tamaño/tipo; tamaño prima sobre tipo; tipo prima
sobre contenido. El límite de 65536 bytes es inclusivo y cuenta UTF-8, no caracteres.

Todas las respuestas de aplicación tienen un objeto JSON UTF-8, una cabecera
Content-Type `application/json` (charset UTF-8 opcional) y una Content-Length
decimal calculada en **bytes**. Errores: exactamente `{"error": CADENA_NO_BLANCA}`,
sin exigir texto literal. Las claves JSON de respuesta son únicas, sin constantes
no JSON. **HEAD nunca tiene cuerpo**, ni siquiera en errores; su Content-Length
puede ser cero o la longitud de la representación omitida. Cerrar la conexión
tras cada respuesta, incluidos TE y errores; no se exige una cabecera Connection
literal si el cierre es efectivo. El servidor sigue atendiendo después de una
petición inválida. No alterar la semántica de recursos, fechas UTC, identificadores,
orden o validación total definidos por el núcleo protegido.

## Evaluación y futura ejecución

El [evaluador](../evals/tareas_reales/booking_http/evaluar.py) usa `--project`, una
suite unittest e identidades explícitas. No importa el candidato en su proceso.
Usa hijos con intérprete absoluto, `-B`, entorno `evaluation` vivo hasta recogerlos,
cwd y plazos controlados, `--port 0` y únicamente clientes IPv4 127.0.0.1. No busca
puertos libres mediante cierre y reutilización. La aceptación tiene 180 s;
desarrollador/revisor 300 s cada uno, regresión 600 s e inventario 30 s.

La ausencia del producto produce aserciones antes de invocarlo. La sonda de
delegación sustituye el núcleo solo en un hijo, antes de importar el servidor;
no exige helpers nuevos ni determina por sí sola ausencia de código duplicado.
El revisor debe leer la entrega. Importar/ejecutar código del candidato en hijos
no es aislamiento de seguridad. Consulte la [guía de preparación](../evals/tareas_reales/booking_http/README.md)
para resultados, restricciones del entorno y futura autorización de agentes.

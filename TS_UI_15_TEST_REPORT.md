# TS-UI-15 — Newsroom e Inbox con banco fotográfico reutilizable

## Alcance
- Se añadió **Newsroom** como página independiente de **Inbox**, con filtros por categoría, búsqueda, artículos y noticias relacionadas.
- Se integraron **11 imágenes neutrales** ya generadas en la conversación, redimensionadas a WebP para el juego. No se solicitaron ni generaron escenas nuevas.
- Además se reutilizan imágenes neutras preexistentes (estadio, centro médico, oficina, preparación y entrenamiento). El catálogo está preparado para agregar más imágenes de cada clase sin cambiar la UI.
- Las imágenes editoriales se seleccionan por categoría y ID del acontecimiento; se evitan repeticiones entre noticias vecinas durante la sesión.
- Las fotos importadas de jugadores por su `player_id` persistente prevalecen sobre la escena neutra. Si no hay foto, se conserva una escena genérica: nunca se utiliza la cara de un desconocido como foto de ese futbolista.
- La procedencia de los datos de noticias continúa siendo `/api/news` y exige `source=career-ledgers`. No se inventan resultados, clubes, quotes ni fichajes.
- Se afinó el estilo de Inbox y el destino de los mensajes de transferencias, sin modificar sus comandos del servidor.

## Comprobaciones terminadas
- `node --check` en `news_media.js`, `news.js`, `inbox.js`, `portable.js`: **aprobado**.
- `node tests/ui/test_ts_ui_15_media.cjs`: **aprobado** (categorías, selección estable, prioridad de foto real, fallback seguro).
- `pytest -q tests/test_ts_ui_15_newsroom_media.py`: **4 aprobadas**.
- HTTP desde Python contra el servidor real de la base reconstruida: `/portable/`, `/api/news`, `/api/inbox`, el nuevo JS y las fotografías WebP: **200**.
- Chromium aislado con el JS/CSS real y datos de prueba explícitos (no acontecimientos ficticios en el juego): **1550 / 1024 / 390 px**, sin errores JavaScript ni desbordamiento de página. Navegación del feed, filtro Transfers, diálogo de noticia y foto por ID: **aprobados**.
- Chromium aislado de Inbox con la respuesta real del motor: **1550 / 390 px**, sin errores JavaScript ni desbordamiento; selección de mensajes: **aprobada**.

## Límites conocidos
- Chromium del entorno bloqueó abrir una URL HTTP en `127.0.0.1` y `file:` (`ERR_BLOCKED_BY_ADMINISTRATOR`). La QA visual es **aislada**; no es una prueba de extremo a extremo de la navegación del juego completo.
- La suite histórica amplia de la base reconstruida presentó regresiones ajenas a este parche (tests antiguos del préstamo y del calendario/desarrollo); **no** se declara aprobada la suite integral ni se cambió el backend para ocultar esas diferencias.
- El motor actual produce principalmente noticias de resultados, traspasos, cesiones, títulos y premios. Hay categorías fotográficas listas para nuevos tipos de evento, pero aquí no se implementó un generador editorial ni se prometió un feed abundante antes de disputar partidos.
- Las 11 imágenes nuevas son las neutras disponibles y aprobadas; todavía no se llega a 20–30 fotos neutrales diferentes sin generar o aportar nuevos originales.

## Compatibilidad
- Parche incremental sobre **TS-UI-14.01**.
- Solo archivos de frontend, fotos locales, tests y documentación.
- No se cambió esquema de persistencia ni versión de guardado (v32).

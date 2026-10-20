# TS-UI-01A.3.1 — Fix de branding en el Calendario

## Problema observado

En Home > Calendario, los partidos de Premier League no mostraban el logo ni el color violeta, y el logo de Champions League se veía minúsculo. Carabao Cup sí aplicaba correctamente su identidad visual. FA Cup todavía no tenía un partido en el fixture inicial para verificarlo directamente.

## Causa y corrección

- `calendar_read_model` publicaba `competition_id='league'` (clave del calendario interno) en vez de `dev-premier` (ID real de la liga en `WorldSeasonRunner`). Ahora publica **`scheduled.competition_id` para todas las competiciones**, igual que Carabao. Esto es escalable a ligas nuevas y evita mapear permanentemente la etiqueta genérica `league` a Premier League.
- La pantalla completa de Calendar sigue reconociendo el antiguo alias `league` para compatibilidad, y también reconoce el nuevo `dev-premier` como competición liguera.
- Se recortaron los márgenes transparentes del icono compacto de Champions League para que ocupe correctamente el espacio que ya usa Carabao Cup.
- Se aumentó moderadamente la intensidad del color de los renglones de competición y del texto de competición, aprovechando las mismas variables CSS de Carabao (`--ci-accent`, `--ci-rgb`, `--ci-shade`).
- Se actualizó una prueba antigua que tenía una ruta absoluta de desarrollo y prohibía cualquier modificación de `calendar.py`, incluso esta corrección de ID.

No se modificaron fixtures reales, resultados, clubes, motor, economía, guardados ni esquema SQLite.

## Verificaciones terminadas

- **14/14** pruebas dirigidas de calendario, Home, identidad visual, iconos y compatibilidad.
- `node --check` de `frontend/portable/calendar.js` y `competition_branding.js`: correctos.
- Sesión Python nueva: los IDs de los fixtures de `calendar_read_model` coinciden con los IDs del mundo (`dev-premier`, `carabao-cup`, `champions-league`).
- Chromium aislado con HTML/JS/CSS reales, datos provenientes de una partida nueva y un fixture de FA Cup **solo simulado como entrada de prueba**: se verificaron los cuatro temas `premier`, `fa`, `champions` y `carabao` con logo visible, fondo coloreado, borde coloreado y **0 errores JS**.

## Pendiente

- La FA Cup comienza sin un encuentro sorteado para el club en agosto de 2026. El **renderizado de un fixture FA Cup** está confirmado con un fixture de prueba, pero queda pendiente la comprobación jugable cuando exista un encuentro real.
- La ejecución conjunta de una suite amplia excedió el límite del entorno: no se considera aprobada.
- Validación final en Windows del usuario.

## Instalación

Aplicar solo sobre TS-UI-01A.3. Copiar el contenido del ZIP a la raíz del proyecto y aceptar reemplazos. Reiniciar y usar `Ctrl + F5` si el navegador conserva estilos anteriores. No borrar archivos ni reemplazar el juego completo.

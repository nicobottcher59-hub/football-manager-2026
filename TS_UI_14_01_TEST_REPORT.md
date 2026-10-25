# TS-UI-14.01 — Other Leagues: club-colour polish

## Alcance
Parche incremental sobre **TS-UI-14**. El único archivo de producción modificado es `frontend/portable/competitions.css`.

- El encabezado general **Other Leagues** adopta el color dominante del club dirigido (borde, sombreado, eyebrow y panel de temporada), manteniendo la fotografía genérica.
- Los controles y bordes del directorio reciben el acento del club. El selector de competiciones y el foco de filtros utilizan la misma identidad.
- La barra lateral refleja el color del club cuando la pantalla Other Leagues está visible, igual que en Competitions.
- Las fichas, tablas, logos y partidos siguen usando el color **de la competición seleccionada**, independiente del club dirigido.
- Se usan variables `--ui-club-*` administradas por el sistema de identidad existente, no un rojo fijo de Sunderland.

## Verificaciones terminadas
- **34 regresiones Python aprobadas**: UI-3.3 Competitions, UI-3.3.2 Other Leagues, TS-UI-13 y TS-UI-14.
- **2 pruebas nuevas aprobadas** para alcance de selectores y distinción entre colores del club y de la liga.
- **Chromium aislado en 1550, 1024 y 390 px**: el borde del hero, el directorio, el selector y el estado activo de la barra lateral reflejan el RGB del Sunderland `199,40,56` (con realce accesible en el menú). Sin overflow horizontal ni errores JavaScript.
- Cambio temporal a otro club de prueba verde (`#008e6e`) en los tres tamaños: el shell cambia a verde y la liga mantiene su color.
- Championship `#77b8ed` y League Two `#76d4b7` mantuvieron sus paletas propias tras cambiar de competición.
- Instalación incremental e integridad SHA-256 verificadas.

## Límites
El navegador se probó en un montaje aislado contra modelos del motor Python, no mediante una sesión integral del servidor del juego. No se simuló ninguna temporada. No se modifica el backend ni el formato de guardado, que permanece v32.

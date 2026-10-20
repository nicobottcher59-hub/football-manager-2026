# TS-UI-02.7 — Pruebas

**Base:** TS-UI-02.6, con parche incremental de la interfaz Squad.

## Ejecutado

- `node -c frontend/public/squad/squad_ui02.js`: PASA.
- `pytest -q tests/test_ts_ui_02_7_squad_polish.py tests/test_ts_ui_02_6_squad_layout.py tests/test_ts_ui_02_5_squad_polish.py tests/test_ts_ui_02_4_profile.py tests/test_ts_ui_02_3_squad_visual.py tests/test_ts_ui_02_2_squad_split.py`: **57/57 PASAN**.
- Chromium aislado, **1680×980, 1366×860 y 980×800**: carga de interfaz, cambios de pestaña locales, selección de jugador, radar, mapa y cambio interactivo de posición; sin excepciones JavaScript ni desbordamiento horizontal: PASA.
- 1366 y 1680: mapa y radar alineados en la misma fila: PASA.
- Dorsal `#22` solo para jugador con número en escenario de prueba, ausente en jugador sin dorsal; capitán solo con `effective_id` del modelo: PASA.
- Camiseta PNG/WebP y crest en el catálogo: navegador aislado utiliza datos-URI para probar presentación sin servidor. Fallback de recurso ausente y carga tardía de identidad conservados.
- Regresión: número, capitán, tema del club, acciones, navegación dedicada al perfil y cambio de pestañas conservados por las pruebas anteriores.

## Pendiente

- Comprobación en Windows con los recursos reales y el zoom del usuario.
- Regresión integral de todas las pantallas y simulación de 20 temporadas.
- Aprobación visual frente al mockup; no se declara coincidencia píxel a píxel automáticamente.

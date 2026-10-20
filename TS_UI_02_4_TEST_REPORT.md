# TS-UI-02.4 — Informe de pruebas

## Aprobadas

- `pytest -q tests/test_ts_ui_02_4_profile.py tests/test_ts_ui_02_3_squad_visual.py tests/test_ts_ui_02_2_squad_split.py tests/test_ts_24_2_1_squad_contract_display.py`: **33/33**.
- Sintaxis JS: `node --check` para `squad_ui02.js` y `presentation.js`.
- Render e interacción aislados en Chromium (Playwright, recursos locales y fixture de API, **no** la partida del usuario): viewport **1680 x 980**, **1366 x 860**, **980 x 800**. Tres casos aprobados, sin excepciones JS ni desbordamiento horizontal.
- Verificación DOM de pestañas: `.s2-inspector`, `.s2-player-hero` y `.s2-roster` **mantienen su identidad DOM** al cambiar de pestaña, confirmando que no se recarga el árbol completo.
- Puntos del mapa: seleccionar posición secundaria modifica `aria-pressed`, resalta el punto y la barra asociada sin rehacer la pantalla.
- Atributos: cada campo numérico de las categorías disponibles aparece en su grupo; fixture de prueba: **37 de 37**.
- Radar: una única zona visual con **dos polígonos** sobre los mismos ejes, a partir de valores reales del endpoint y pesos registrados en los roles.
- Archivo de camiseta: WEBP RGBA con transparencia, configurado por ID de club, más fallback cuando falta el archivo.
- Compatibilidad: pruebas previas de acciones, navegación, retratos, temporadas y CSS temático sin regresiones.

## No ejecutadas / pendientes

- Prueba manual real en Windows con la partida de Sunderland (incluido servidor HTTP y carga real de imágenes).
- Suite integral de todas las funcionalidades deportivas y simulación de 20 temporadas.

Esta actualización afecta exclusivamente presentación, no reglas deportivas o persistencia.

# TS-UI-02.9 · Reporte de validacion

**Base:** TS-UI-02.8.
**Alcance:** visualizacion de Squad (cabecera, directorio, mapa y radar).
**Motor/guardado:** sin modificaciones.

## Pruebas automatizadas

- `pytest -q tests/test_ts_ui_02_3_squad_visual.py tests/test_ts_ui_02_4_profile.py tests/test_ts_ui_02_5_squad_polish.py tests/test_ts_ui_02_6_squad_layout.py tests/test_ts_ui_02_7_squad_polish.py tests/test_ts_ui_02_8_squad_rebuild.py tests/test_ts_ui_02_9_squad_fidelity.py`
- **Resultado: 66 pruebas aprobadas**.

## Pruebas funcionales en Chromium aislado

- 1680x940, 1366x830 y 980x900, con respuestas JSON de prueba.
- Estructura de cabecera, directorio y 22 tarjetas: disponible.
- Cambiar entre Perfil, Temporada, Estado y Contrato: pasa; se conserva la
  referencia DOM a la cabecera y a la lista.
- Seleccion con mouse y teclado: pasa.
- Capitan real, numero real y numero no asignado: pasa.
- Posiciones y barras vinculadas: pasa.
- Un jugador con una sola posicion no crea una tarjeta mucho mas alta que el radar.
- Kit de club ausente: se muestra la ilustracion generica.
- Sin errores JavaScript ni desbordamiento horizontal.

**Limite:** Estas comprobaciones no reemplazan la prueba visual y funcional
nativa de la aplicacion en Windows con una carrera guardada.

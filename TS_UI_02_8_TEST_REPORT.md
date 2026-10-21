# TS-UI-02.8 - Informe de validacion

- JavaScript: `node --check frontend/public/squad/squad_ui02.js` -> OK.
- Pytest estructural/interface: **66 tests aprobados**. Incluye pruebas
  heredadas versionadas (02.2 a 02.7), adaptadas a las nuevas clases y nueve
  controles nuevos de 02.8; no se deshabilitaron pruebas.
- Chromium headless **1680 x 980**, **1366 x 860**, **980 x 800** -> OK:
  - camiseta totalmente dentro del hero sin corte por caja o grid
  - 22 tarjetas y numero/capitan desde modelo simulado
  - cambiar pestana preserva los nodos del directorio y del hero
  - cambiar jugador actualiza solo inspector; buscar no lo reinicia
  - club alternativo sin imagen propia usa camiseta ilustrada
  - sin errores JS ni desbordamientos horizontales.
- Integridad visual del asset: WEBP transparente nuevo inspeccionado
  sobre fondo oscuro; proviene de la camiseta original aportada por el usuario.

LIMITACIONES:
- El render visual aislado utiliza datos de prueba; no equivale a validar una
  temporada completa en Windows.
- Un conjunto de pruebas amplias Python del arbol de trabajo no puede importarse:
  falta el modulo `football_manager.services.match_preparation` en la copia
  disponible. No se tocaron los servicios para solventarlo y no se declara
  aprobada esa regresion.
- La coincidencia visual exacta con el mockup requiere revision del usuario.

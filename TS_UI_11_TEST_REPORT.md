# TS-UI-11 + TS-UI-10.02 — Informe técnico

**Base:** TS-UI-10.01 (sobre TS-FIX-07). **Formato de guardado:** 32, sin cambio.

## Alcance implementado

- `Career History` de futbolistas rediseñado, usando el motor Python y los IDs estables.
- Cabecera con retrato real importado por ID o retrato ilustrado de respaldo, bandera, posición, edad, pie preferido y club actual. Escudo y colores dinámicos de club.
- Resumen con apariciones, goles o porterías a cero para arqueros, asistencias, calificación media, clubes conocidos y títulos. El asterisco en una cifra indica que hay temporadas sin cobertura completa.
- Gráfico de evolución del GRL o de las medidas existentes, sin interpolar observaciones no registradas.
- Línea de trayectoria formada por traspasos, cesiones, títulos y primeras temporadas con apariciones verificadas; no inventa un debut profesional.
- Estadísticas por temporada y desglose por competición cuando la base registra esa partición. La cobertura parcial se distingue de los ceros conocidos.
- Carruseles **independientes** de Team Honours e Individual Awards. **Solo muestran premios efectivamente registrados**, nunca tarjetas a cero. Las flechas, rueda y barra permiten desplazarse.
- Las seis imágenes provistas: cañón para goleador de liga, The Best para mejor jugador de la temporada de liga, Balón de Oro, Bota de Oro, Golden Boy y Puskás. Los PNG se procesaron con transparencia para el fondo oscuro.
- Lógica del motor: `world_young` (Golden Boy simulado para sub-21 con participación real) y `golden_shoe` (máximo goleador de las primeras divisiones registradas). `world_player` existente se presenta como Balón de Oro del mundo simulado.
- La imagen Puskás **no implica entregar automáticamente ese premio**: los resultados actuales incluyen xG y goleador pero no una medición verificable de calidad estética del gol. Queda el catálogo preparado para concederlo/importarlo cuando exista un dato válido.
- Importación futura **por ID de futbolista**, con un archivo opcional por jugador bajo `frontend/portable/data/player-histories/`, y deduplicación por temporada/competición. Ningún historial anterior se incluye inventado.
- TS-UI-10.02: Community Shield y EFL Trophy en el catálogo inglés de Club Info, con imágenes, contadores y scroll. Club Info **mantiene todos los títulos relevantes aunque su contador sea 0**. Se retiró la imagen de EFL Trophy que se había asociado incorrectamente a las divisiones inferiores.
- Las copas futuras de otros países se resuelven por competición y catálogo; una competición sin imagen usa el pictograma genérico sin inventar iconos.

## Pruebas terminadas

- **4 pruebas Python de TS-UI-11**, incluyendo read model, nuevas categorías de premios, desglose de competiciones y serialización/restauración del premio con el grafo v32.
- **11 pruebas de Club Info** de TS-UI-10 y TS-UI-10.01, con los contadores, categorías y países.
- **11 verificaciones funcionales JS** en el archivo nuevo, con ausencia de premios no ganados, catálogo, deduplicación, futuras ligas y escape de datos no confiables.
- `node --check` para los módulos JS cambiados.
- **9 endpoints HTTP 200** del servidor real Python: nuevo JS, CSS, catálogos, imágenes y `/api/history/player/{id}`.
- Chromium aislado a anchos de **1550, 1024 y 390 px**: sin desbordamiento horizontal de la página, sin errores JS ni imágenes de premios rotas. El selector de atributos se ejercitó en la pantalla real de componente.
- Instalación limpia del parche ZIP sobre una copia de TS-UI-10.01: verificación de manifiesto SHA-256.

## Límites y deuda conocida

- Chromium bloquea navegación directa al servidor `127.0.0.1` (`ERR_BLOCKED_BY_ADMINISTRATOR`): no se afirma una prueba **end-to-end** en navegador contra el servidor. La vista aislada renderizó los JS/CSS reales con modelos controlados; los endpoints Python se probaron por separado.
- No se simuló una temporada completa ni se probó una partida personal.
- Una prueba antigua de avance rápido desde el 1 de julio falla en un control del mes de desarrollo (`match is outside the open development month`); ese fallo no está provocado por Career History y el parche no altera el motor de partidos.
- Algunos tests históricos de TS-28.3/28.4 esperan una fecha de inicio posterior y versión de guardado 24; en la base actual ya se inicia el 1 de julio y se utiliza versión 32. Estos supuestos antiguos no se cuentan como regresiones aprobadas.
- El cálculo de Golden Shoe se basa en el goleador de las competiciones de primera división **simuladas y registradas**; no utiliza un ranking histórico externo ni equipara estadísticas sin cobertura.
- No se inventan títulos individuales antiguos. Los premios reales importados a futuro requieren fuentes fiables y un registro compatible por ID.

## Archivos clave

- `frontend/portable/player_career.js` y `.css` — nuevo render y controles.
- `frontend/portable/history.js` — mantiene la navegación existente y delega la ficha de jugador.
- `src/football_manager/ui_shell/career_history.py` — metadatos y partición real por competición.
- `src/football_manager/services/career_recognition.py` — adjudicación anual adicional sin alterar la persistencia.
- `frontend/portable/data/individual-awards.json` y `honour-competitions.json` — catálogo ampliable.
- `frontend/portable/assets/awards/` y dos copas en `assets/trophies/`.

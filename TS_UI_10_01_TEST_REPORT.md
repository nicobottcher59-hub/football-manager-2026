# TS-UI-10.01 — Illustrated Honours & Country-Aware Gallery

**Fecha:** 23/10/2026  
**Base obligatoria:** TS-UI-10 — Club Info e Historia Viva (sobre TS-FIX-07 y anteriores)  
**Tipo:** parche incremental; instalar en la raiz del proyecto.  
**Formato de guardado:** permanece en **32**. No se cambia el motor de partidos, el registro de campeones ni los archivos de partidas.

## Qué cambia

- Reemplaza los cuatro indicadores genéricos de **Honours & Achievements** por tarjetas ilustradas de competiciones; utiliza los PNG provistos para Premier/ligas inglesas, FA Cup, Carabao, Champions, Europa, Conference, divisiones inferiores y títulos mundiales de clubes.
- Convierte los PNG a **RGBA transparente** y los coloca en `frontend/portable/assets/trophies/`, eliminando los fondos blancos y el patrón de cuadros incrustado en las referencias. No se generan copas ficticias ni se cambian los diseños originales de sus siluetas.
- Inglaterra muestra por defecto: English Leagues (todas las divisiones), FA Cup, Carabao Cup, Champions League, Europa League, Conference League, Club World Titles (Mundialito / Intercontinental / nuevo Mundial), Lower Division Titles y EFL Trophy. El último usa un respaldo gráfico porque no se aportó su copa específica.
- **Lower Division Titles** es explícitamente un SUBCONJUNTO de English Leagues. Un título de Championship suma al total inglés y al desglose de inferiores, pero no equivale a dos campeonatos diferentes.
- Añade desplazamiento horizontal nativo dentro del panel con barra, flechas, rueda vertical del ratón (transformada en movimiento horizontal mientras la galería pueda desplazarse), teclado y gestos táctiles. El resto de la pantalla no se desplaza horizontalmente.
- Redimensiona ligeramente el grid inferior para priorizar el palmarés, manteniendo Club History y Club Records. Mejora los cuatro iconos de **Identity & Philosophy** mediante SVG locales; no requiere fuentes externas.
- Agrega `data/honour-competitions.json` como catálogo externo de categorías por país y región. Inglaterra queda configurada; otros países muestran sus competiciones reales conocidas en el mundo y las del historial importado, sin asignarles las copas inglesas. La ampliación a nuevos países consiste en sumar categorías e identificadores en el catálogo.
- Los contadores se recomponen al abrir Club Info con `d.trophies` del historial de carrera + `historical.honours` importado por **club ID**. Nunca se suman cantidades inventadas, y el juego sigue registrando títulos, ascensos y descensos por su propio sistema existente.
- Las competiciones mundiales de distintas épocas están **agrupadas en una categoría** identificada por varios IDs; hasta recibir imágenes propias de cada formato, usan la misma copa dorada de referencia como recurso compartido.

## Pruebas realmente ejecutadas

| Comprobación | Resultado |
|---|---|
| `pytest -q tests/test_ts_ui_10_01_honours.py tests/test_ts_ui_10_club_info.py` | **12 tests aprobados** |
| `node tests/test_ts_ui_10_01_honours.js` | **16 aserciones funcionales aprobadas** |
| `node --check` en ambos scripts | Aprobada |
| Galería en 1550, 1024 y 390 px, Chromium | 9 categorías inglesas, 8 imágenes visibles, sin desbordamiento de página |
| Carga visual de recursos | **8 imágenes cargadas** sin errores de carga |
| Botones y rueda del ratón para desplazar las copas | Funcionales en los tres tamaños |
| Errores JavaScript en la prueba aislada | **0** |
| Manifest de hashes e instalación incremental sobre copia de TS-UI-10 | Verificados (SHA-256) |

**Alcance de la prueba visual:** navegador Chromium del entorno ejecutó los JavaScript y CSS reales con datos JSON de prueba controlados y los PNG reales. La conexión directa a `127.0.0.1` fue bloqueada por la política del navegador (`ERR_BLOCKED_BY_ADMINISTRATOR`), de modo que esta validación **no equivale** a ejecutar el juego completo en la PC del usuario. Tampoco se ejecutó una temporada entera ni se probó la partida personal.

## Escalabilidad y datos

- **Categorías y copas:** `frontend/portable/data/honour-competitions.json`, donde cada categoría declara `id`, `label`, `rank`, `competition_ids` e `image` opcional. `subset_of` marca subtotales anidados. Se pueden crear nuevas entradas `countries` y `regions` sin editar Club Info.
- **Archivos ilustrados:** `frontend/portable/assets/trophies/*.png`. Cuando se agreguen otros países, insertar sus recursos aquí y referenciarlos desde el catálogo. Las categorías no ilustradas muestran una copa de respaldo.
- **Historial anterior a la carrera:** sigue leyéndose desde `frontend/portable/data/club-histories/<club_id>.json`. Es independiente de los campeones ganados durante la partida.
- **Competiciones desconocidas:** el panel las incorpora dinámicamente a partir de `live.competitions`, `trophies` y el historial, evitando que desaparezcan títulos de ligas importadas aún no mapeadas.
- **Futuro:** asignar nuevas copas a países adicionales e identificadores de formatos distintos del Mundial de Clubes si se requieren tarjetas independientes.

## Archivos

**Modificados:**
- `frontend/portable/index.html` (carga de módulo)
- `frontend/portable/club_info.js` (integración de datos, iconos y scroll)
- `frontend/portable/club_info.css` (tarjetas y diseño responsivo)

**Nuevos:**
- `frontend/portable/club_honours.js`
- `frontend/portable/data/honour-competitions.json`
- `frontend/portable/assets/trophies/` (8 PNG)
- `tests/test_ts_ui_10_01_honours.js`
- `tests/test_ts_ui_10_01_honours.py`
- informe, instrucciones y hashes.

## Instalación

1. Tener **TS-UI-10** instalado. Hacer copia de seguridad del proyecto y de las partidas.
2. Detener Python y cerrar el juego.
3. Descomprimir el ZIP **en la raiz `football-manager-2026`**, manteniendo carpetas y reemplazando los 3 archivos existentes.
4. Reiniciar Python, abrir Club Info y pulsar `Ctrl + F5`.
5. Probar el scroll de los trofeos y una ficha de un club rival.

**GitHub Desktop (rama nueva):** `feat/ts-ui-10-01-illustrated-honours`  
**Summary:** `feat(club-info): TS-UI-10.01 country-aware illustrated honours gallery`

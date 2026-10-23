# TS-UI-10 — Club Info · Universal Identity & Living Career History

**Fecha:** 23/10/2026  
**Base:** TS-FIX-07 instalado sobre TS-UI-09.01  
**Entrega:** ZIP incremental, no sustituye una partida ni un proyecto entero.  
**Formato de guardado:** permanece en **32**; no hay migración ni dependencias adicionales.

## 1. Alcance implementado

- Rediseño de **Club Info** siguiendo el mockup aprobado: cabecera con imagen deportiva, escudo e identidad cromática; Club Overview; Current Season; Competitions; Honours & Achievements; Club History; Club Records; Identity & Philosophy.
- **Estadio e instalaciones eliminados de la nueva página.** Los datos existentes del motor se mantienen intactos, pero no se presentan aquí.
- Imagen de cabecera resuelta por `hero_image` del club si existe y **foto deportiva genérica de respaldo** si falta. Escudos y paletas se resuelven por **club_id** con los recursos compartidos y colores con contraste.
- Nombres, país, competición y datos institucionales proceden del mundo y/o de catálogos por ID. Lo no disponible se marca como no registrado; no se inventan años, títulos ni récords.
- **Current Season** consulta el estado actual de liga (`WorldSeasonRunner.standings`), victorias, empates, derrotas, goles, puntos, racha real y siguiente partido. No presenta posición significativa hasta que se haya disputado algún encuentro.
- **Competitions** refleja las ligas, copas y torneos continentales en los que el club realmente está inscrito, con sus identificadores oficiales para logos y enlaces.
- **Historia viva:** los informes confirmados de `WorldCareer.reports` aportan títulos, posiciones finales, ascensos y descensos. Las nuevas ligas se leen del mundo de la temporada corriente; los contadores se recomponen sin guardar duplicados y sin tocar el simulador.
- **Honours** distingue títulos ganados en la partida de honores históricos importados. Se suman al visualizar, no sobreescriben los registros de carrera.
- **Club Records** usa únicamente las estadísticas verificadas y las importaciones explícitas; sin datos iniciales quedan los estados de información pendiente.
- `View Club` abre la **misma plantilla** para clubes rivales; el acceso anterior a su plantilla sigue disponible como **View squad**. Se respetan navegador Atrás y rutas de club con ID.
- Historial histórico importable **por documento individual `/portable/data/club-histories/<club_id>.json`**, con carga perezosa/caché por club. Hay compatibilidad con un catálogo global vacío de respaldo. Incluido esquema y ejemplo documental en `frontend/portable/data/club-histories/README.md`.
- La nueva página no altera Squad, Tactics, Transfers, préstamos, contratos, noticias ni los procesos de generación de resultados.

## 2. Validación realmente ejecutada

| Comprobación | Resultado |
|---|---|
| 7 pruebas nuevas en `tests/test_ts_ui_10_club_info.py` | **7 aprobadas** |
| 3 regresiones seleccionadas: Club History y TS-UI-09 / TS-FIX-07 | **3 aprobadas** |
| Prueba de motor real, temporada inicial y club rival | Aprobada |
| Informe de temporada sintético: título de Champions + descenso | Aprobada |
| Informe de temporada sintético: ascenso + nueva liga | Aprobada |
| Identidad sin escudo y marca de respaldo | Aprobada en Chromium |
| Importación histórica bajo demanda de otro club | Aprobada en Chromium usando un registro de prueba |
| Tablas, pestañas, competiciones, enlaces a Squad | Aprobados en Chromium |
| 1550 / 1024 / 390 píxeles | Sin desbordamiento horizontal |
| Errores JavaScript en el montaje visual | **0** |
| HTTP servidor real: nueva hoja de estilo, script, catálogo histórico y lectura de club | Aprobado |
| `node --check` y compilación de Python | Aprobados |
| Instalación incremental sobre copia limpia y hashes SHA-256 | Aprobada |

**Limitaciones honestas:** el navegador Chromium disponible bloquea con `ERR_BLOCKED_BY_ADMINISTRATOR` las conexiones a `127.0.0.1`, por lo que la prueba visual usó el **código de UI real con respuestas tomadas del motor real y transporte simulado**. No representa una validación completa de toda la aplicación ejecutada en tu computadora. Tampoco se ejecutó una temporada completa ni se verificó una partida personal; los cambios de liga y trofeos se cubrieron con informes de temporada controlados.

Un test heredado de TS-28.3/28.4 comprueba `progression[-1].is_current is True` cuando el primer snapshot ya fue fechado el mismo día. Ese test falla igualmente en **TS-FIX-07 sin TS-UI-10**; no está causado por el rediseño y no se incluye como regresión aprobada.

## 3. Integración futura de la base de datos

- Los datos institucionales y fotografías se incorporan por el registro existente de identidad de clubes, clave `club_id`.
- Cada club puede recibir **su propio archivo histórico** en `frontend/portable/data/club-histories/<club_id>.json` usando `schema_version: 1`, `club_id` idéntico y un objeto `record` opcional con `biography`, `honours`, `timeline`, `records`, `philosophy`, `founded` y `country`.
- `honours` acepta `competition_id`, `competition`, `total` y/o temporadas `seasons`. Los totales de historia son **anteriores al inicio de la carrera**. Lo ganado durante la partida proviene exclusivamente del registro de campeones del juego.
- Si no hay historial oficial de un club, los módulos permanecen con estados informativos. **No hay títulos ficticios precargados** para los clubes de prueba.
- Las colecciones de temporadas, récords e hitos se muestran con paginación de la interfaz para reducir la densidad visual; los archivos históricos se descargan solo al visitar su club.

## 4. Archivos afectados

**Modificados (3):**
- `src/football_manager/ui_shell/career_history.py`
- `frontend/portable/portable.js`
- `frontend/portable/index.html`

**Nuevos (5):**
- `frontend/portable/club_info.js`
- `frontend/portable/club_info.css`
- `frontend/portable/data/club-historical-records.json`
- `frontend/portable/data/club-histories/README.md`
- `tests/test_ts_ui_10_club_info.py`

Los archivos restantes del ZIP son este informe, las instrucciones y el manifiesto de integridad.

## 5. Instalación

1. Tener **TS-FIX-07** instalado. Respaldar proyecto y partida.
2. Cerrar Python y el juego.
3. Extraer el ZIP en la raíz de `football-manager-2026` (carpeta con `pyproject.toml`), conservar directorios y reemplazar los 3 archivos modificados.
4. Reiniciar el servidor del juego, abrir **Club Info** y pulsar `Ctrl + F5`.
5. Probar la ficha de un rival mediante **View Club**, el historial de una temporada finalizada y los logos.

**Nueva rama de GitHub Desktop:** `feat/ts-ui-10-living-club-info`  
**Summary:** `feat(club-info): TS-UI-10 scalable living club history and honours`

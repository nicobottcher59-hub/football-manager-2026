# Football Manager Game

> **TS-24.8 - Reequilibrio estructural:** plantillas y mercado IA, cantera orientada a
> necesidades tacticas, rotacion U23 con minutos reales y finanzas por division.
> [Instalacion](TS_24_8_PATCH_INSTRUCTIONS.txt) ·
> [Informe](docs/TS_24_8_REEQUILIBRIO_ESTRUCTURAL.md) ·
> [Auditoria](TS_24_8_LONG_HORIZON_REPORT.md). Requiere TS-24.7; guardado v16.

> **TS-20 - Player DNA & Dressing Room:** automatic, evolving squad hierarchy,
> private personality profiles and a small, capped social morale context. Includes
> the portable Dressing Room page; no mandatory meetings or manual relationships.
> See [installation](TS_20_INSTRUCTIONS.txt), [design](docs/TS_20_PLAYER_DNA_DRESSING_ROOM.md)
> and [validation](TS_20_TEST_REPORT.md). Reads old careers; writes career format 4.
> Back up saves before upgrading. No Node.js is required to run the game.

> **TS-19 - Tactical Studio 2.0:** integrated portable editor, independent phase targets,
> tactic library, scheduled match plans and fast tactical consumers. See
> [installation](TS_19_TACTICAL_STUDIO_INSTRUCTIONS.txt), [implementation](docs/TS_19_TACTICAL_STUDIO.md)
> and [executed validation](TS_19_TEST_REPORT.md). No Node.js is required to run the game.

Proyecto personal de desarrollo de un simulador de gestión de fútbol inspirado en juegos como Football Manager y los modos carrera de EA Sports FC.

La idea es crear progresivamente un juego centrado en la simulación y gestión de un club, sin jugabilidad directa de los partidos.

## Objetivo

El jugador podrá asumir el control de un club y tomar decisiones relacionadas con:

- Plantel
- Tácticas
- Partidos
- Competiciones
- Mercado de pases
- Contratos
- Finanzas
- Desarrollo de jugadores
- Scouting
- Juveniles
- Gestión del club

El objetivo a largo plazo es construir un mundo de fútbol dinámico, donde jugadores, clubes y competiciones evolucionen con el paso de las temporadas.

## Principios del proyecto

- Desarrollo incremental.
- Motor de simulación separado de la interfaz.
- Datos separados de la lógica del juego.
- Soporte futuro para bases de datos y mods.
- Jugadores, clubes y competiciones identificados internamente mediante IDs.
- Posibilidad de reemplazar fácilmente nombres, datos y assets.
- Simulación basada en sistemas y reglas, evitando eventos excesivamente guionados.

## Primera versión

La primera versión será un prototipo simple que permita:

- Elegir un club.
- Gestionar un plantel.
- Elegir titulares y formación.
- Simular partidos.
- Generar resultados.
- Mantener una tabla de posiciones.
- Avanzar a través de una temporada.

A partir de esta base se irán incorporando progresivamente nuevos sistemas.

## Tecnologías

El motor continua en Python. El frontend React + TypeScript se adopto para el prototipo visual UI-1; la integracion y el empaquetado Windows (Electron/Tauri) todavia se deben validar.

Inicialmente se está considerando:

- Python
- FastAPI
- SQLite
- React
- TypeScript

## Estado

🚧 Proyecto en desarrollo.

Actualmente el proyecto ya cuenta con dominio de jugadores/clubes/tácticas, MatchSnapshot, simulador rápido, prototipo espacial 2D, una UI de desarrollo descartable, framework de competiciones y el primer motor real de liga round-robin.

Phase 6.0b incorpora **OVR contextual por posición/rol**: los atributos requeridos por cada rol son la base de la valoración, mientras que la familiaridad posicional y la adecuación de lado/pie actúan como modificadores secundarios. ACT se mantiene como la capa de ejecución actual (estado, familiaridad de rol/táctica, química, etc.). La familiaridad posicional puede evolucionar con minutos reales y las posiciones principal/secundarias se derivan del historial acumulado.

Phase 6.1 incorpora el **Competition Framework**: definición estable de competiciones, ediciones por temporada, stages, fixtures deportivos separados del calendario, regulaciones de partido y reglas configurables de clasificación. Los puestos de liga pueden otorgar plazas a competiciones continentales o definir ascensos, descensos y playoffs sin hardcodear esas reglas dentro del futuro motor de liga.

Phase 6.2 incorpora el **Round-Robin League Engine**: una liga de 20 clubes puede generar 38 jornadas y 380 cruces de ida/vuelta, registrar resultados y derivar una tabla con puntos, GF/GC, diferencia y desempates configurables. El fixture de la primera temporada puede entrar como lista `SEEDED` real y convertirse en una plantilla estructural; las temporadas siguientes pueden regenerarse desde esa plantilla con participantes nuevos, sin copiar fechas. El sandbox muestra una liga ficticia mínima para inspeccionar el sistema y permite avanzar jornadas DEV: el Quick Sim del club controlado se registra, los otros partidos de la fecha se resuelven en background y se carga el siguiente rival sin pretender reemplazar el futuro calendario persistente.

Phase 6.3 incorpora el **Knockout Competition Engine**: rondas eliminatorias, cruces a partido único o ida/vuelta, marcador global, prórroga/penales en el partido decisivo y avance automático de ganadores. Los cruces pueden ser `SEEDED` para importar sorteos reales de la primera temporada o `GENERATED` para sorteos posteriores del mundo simulado. El sandbox agrega una Development Cup ficticia de 8 clubes para inspeccionar cuartos, semifinales a dos partidos y final sin convertir esa UI en parte del producto final.

Phase 6.4 incorpora **Multi-Stage Competitions**: una tabla puede enrutar posiciones a clasificación directa, playoff o eliminación y los clasificados de distintas rutas pueden recombinarse en etapas posteriores. El sandbox agrega una competición continental ficticia (fase liga -> playoff/directo -> semifinal -> final), un calendario DEV completo y scrollable que mezcla las competiciones conocidas del club y moral dinámica básica según resultados. Este scheduler sigue siendo descartable; el calendario persistente del mundo continúa reservado para Phase 6.5.


Phase 6.5 incorpora **Calendar & Scheduling** como dominio real: `CompetitionFixture` sigue representando el cruce deportivo y `ScheduledFixture` le asigna kickoff, origen y estado sin deformar la competición. `SeasonCalendar` ordena la cronología, detecta choques/descanso insuficiente, permite aplazar y reprogramar, y puede buscar slots válidos dentro de ventanas de competición. Las temporadas futuras obtienen fechas desde políticas/ventanas nuevas en vez de copiar el calendario anterior. La primera fuente oficial empaquetada es el fixture completo de Premier League 2026/27 (380 partidos, 20 clubes), mantenido separado del mundo DEV ficticio hasta que exista la base real de clubes.

Phase 6.5a agrega las **tres divisiones EFL 2026/27** al entorno de prueba: Championship, League One y League Two (24 clubes ficticios, 46 jornadas/552 cruces por liga). Conserva los **slots de fecha/hora publicados** para cada jornada, pero **genera los enfrentamientos y los nombres de los equipos**, sin hacerlos pasar por fixtures oficiales de clubes reales. Los niveles de calidad DEV disminuyen de Premier a League Two. El sandbox incorpora un inspector de calendarios EFL y otro de tablas/jornadas con simulación DEV; los clubes y planteles reales, las dos copas inglesas y la persistencia del mundo siguen pendientes. Ver `docs/PHASE_6_5A_EFL_FIXTURE_SLOTS.md`.
Phase 6.5b + 6.6 incorpora **las dos copas domésticas inglesas y un único Runner persistente**: FA Cup y Carabao Cup 2026/27 usan rondas y ventanas de fecha oficiales, pero participantes, cruces y resultados ficticios identificados como `GENERATED`. `WorldSeasonRunner` registra resultados de Premier DEV, Championship, League One, League Two y ambas copas, avanza cronológicamente, evita jugar dos veces un fixture, respeta al club controlado (Fast Simulator) y conserva los estados y sorteos con save/load JSON atómico. Las tablas derivan del ledger compartido. El sandbox expone ambas copas, su cronología y guardado/carga **solo de resultados de competiciones**, no de planteles/tácticas. La antigua competición continental DEV de ocho clubes permanece como inspector aislado; los torneos UEFA jugables entran en 6.6b. El mundo inglés de clubes reales y la transición entre temporadas siguen pendientes.


Phase 6.6a + 6.6b integrates **UEFA Champions League, UEFA Europa League, UEFA Conference League and EFL Trophy** into the same world Runner. All fixtures are between fictitious clubs; published 2026/27 **round windows** and format are used as scheduling references, while opponent pairings and moved kickoff dates remain generated. This update also strengthens the condition penalty on ACT, prevents morale from staying pinned at 100 after long winning streaks, replaces fixed continental TBD placeholders with real qualifier-dependent knockout fixtures, and adds V/E/D calendar feedback including penalty shootouts. Northbridge now plays the 36-team DEV Champions competition instead of the disconnected Development Continental fixture list. Details: `docs/PHASE_6_6A_6_6B_UEFA_TROPHY_FIXES.md`.

Phase 6.7 closes the first complete **English DEV competition season cycle**: it generates EFL promotion playoffs (including the expanded 2026/27 six-team Championship field), moves clubs between the four tiers, calculates configurable European access, and starts **2027/28** with newly generated dates and club rosters. `WorldCareer` preserves the results and transition history for successive seasons. The sandbox adds **Simulate entire season (DEV)**, **Start next season**, results-archive save/load and a reversible default-on **weaker opponent DEV advantage** to exercise more finals with genuine FastMatchSimulator results. The 2027+ dates and fixtures are GENERATED, not official. Full squad/tactic saves remain out of scope. See `docs/PHASE_6_7_FULL_SEASON_INTEGRATION.md`.

## UI-1 — React + TypeScript Dashboard (visual prototype)

La Phase 6.7 del motor de competiciones sigue intacta. La nueva carpeta `frontend/` contiene un dashboard React + TypeScript + Vite con diseño oscuro, club card, proximo partido, league/cup switcher, campo del once titular con **OVR** y panel de notificaciones/noticias visuales.

**Importante:** UI-1 muestra datos de ejemplo, no el estado de Python. El boton Continue avanza **solo la fecha visual** para demostrar el control (un dia por click) y muestra un aviso; aun no avanza `WorldCareer`. El juego/sandbox real continua siendo Tkinter. No hay app Electron empaquetada todavia.

Inicio rapido en Windows PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

Abrir http://127.0.0.1:5173 . Documentacion completa y siguientes pasos: `docs/PHASE_UI_1_DASHBOARD_SHELL.md`.

### UI-1 portable en Windows (sin instalar Node.js ni npm)

Para probar el Dashboard sin instalar herramientas, **doble clic en `INICIAR_INTERFAZ_WINDOWS.bat`** desde la raiz del repositorio. Como alternativa, abrir `frontend/portable/index.html` en Edge/Chrome. No requiere Python, Node, npm ni Internet: todos los recursos de la vista UI-1 vienen en el parche. Ver `UI_1_PORTABLE_INSTRUCTIONS.txt`.

El codigo fuente React + TypeScript continua en `frontend/src/`. La vista portable es una instantanea HTML/CSS/JS con interacciones de demostracion para probar la interfaz; **no ejecuta el motor ni avanza una partida real**.


## UI-2 — Squad & Tactics, sin npm (integrado con Python DEV)

Sobre los dos parches UI-1 anteriores, UI-2 incorpora las tres vistas aprobadas: **Starting XI/Formacion**, **panel contextual de roles e instrucciones individuales** y **editor tactico colectivo con fichas**, y corrige la redundancia del selector con/sin posesion. La cancha de tacticas se actualiza visualmente al cambiar parametros; es un diagrama orientativo, no la simulacion 2D legacy.

**Windows:** doble clic en `INICIAR_INTERFAZ_WINDOWS.bat` (necesita Python ya usado por el juego; NO Node.js/npm). Inicia el servicio local `http://127.0.0.1:8765/` y habilita cambios reales en la sesion DEV: formaciones, roles, 15 instrucciones individuales, 44 ajustes de equipo, presets, intercambios de titulares y suplentes. El Dashboard Home sigue con datos demo; no existe Continue diario real ni guardado persistente de planteles/tacticas. `Set Pieces` solo muestra que la asignacion manual esta pendiente. Ver `docs/PHASE_UI_2_SQUAD_TACTICS.md`.


## UI-3 — Squad en tablas y Tactics unificado (parche incremental)

La navegación separa definitivamente **Squad** (plantel en lista) de **Tactics** (alineación, edición de rol/instrucciones y tácticas colectivas). Squad incorpora tres pestañas: **General**, **Attributes** y **Season Stats**, con ordenamiento en columnas, filtros, búsqueda, primera columna fija y panel expandido por jugador. El panel muestra la **familiaridad posicional dinámica real** de la posición principal y secundarias. OVR/ACT y valoraciones se muestran con **un decimal** en las pantallas actualizadas. Se recupera la escala visual de las tarjetas y cancha de Tactics.

**Alcance real:** contratos, valor de mercado, felicidad, chats, entrenamiento, xA y ledger de estadísticas de temporada no existen en la sesión Python disponible. Esas columnas y acciones muestran indisponibilidad y no generan datos falsos. Dorsal y estado transferible/cedible/intocable solo funcionan como **metadatos temporales de UI**, sin modificar mercados ni saves. Home y Continue siguen siendo demostrativos.

**Windows:** aplicar el ZIP **sobre** UI-2 + hotfix, abrir `INICIAR_INTERFAZ_WINDOWS.bat` con Python existente. No instalar Node/npm. Guía: `docs/PHASE_UI_3_SQUAD_ROSTER.md`.

## UI-3.1 — Visual polish + Home connected to Python DEV

UI-3.1 keeps the UI-3 layout and scale, enhances depth/color and adds consistent deterministic illustrated player portraits in **Home, Squad and Tactics**, including nationality in roster and player details. Squad's expanded row now separates profile, current state, positional familiarity, attribute highlights and player-management actions. The Home starting XI, formation, dynamic status metrics, current date and opponent read **the same local Python DEV session** used by Squad/Tactics; returning to Home after changing a starter shows the changed team. OVR/ACT use one decimal.

Start in Windows with `INICIAR_INTERFAZ_WINDOWS.bat` (no npm). **This is still a temporary DEV session**: no persistence, no daily Continue, no contracts/market/training/player conversations/season ledger. The league table, news, manager/club story content and several club card fields remain labeled visual demo data; Python calendar match metadata is only partially available. See `docs/PHASE_UI_3_1_VISUAL_POLISH.md`.

## UI-3.2 — Calendar mensual y orden deportivo de posiciones

Se añadió `Calendar` al iniciador de Windows `INICIAR_INTERFAZ_WINDOWS.bat`, sin necesidad de npm. Permite navegar entre meses, filtrar competiciones, consultar rivales reales de la sesión Python, distinguir partidos locales/visitantes, ver resultados V/E/D y penales registrados y abrir un panel lateral de cada encuentro. Las fechas y cruces provienen de `SeasonCalendar`; los escudos son provisionales. Las eliminatorias aún no sorteadas no se inventan. **Continue sigue sin avanzar días** y no existen todavía guardados completos de la partida.

En `Squad`, POS ordena las posiciones en orden deportivo (GK → defensas → mediocampistas → atacantes), no alfabéticamente, y el segundo clic invierte el orden. Detalles y limitaciones: `docs/PHASE_UI_3_2_CALENDAR.md`.

## UI-3.3 — Competitions, clasificaciones y brackets reales

La pantalla **Competitions** ahora consulta `WorldSeasonRunner` desde la API local de Python, sin Node/npm. Se pueden seleccionar las cuatro ligas inglesas, FA Cup, Carabao Cup, Champions, Europa League, Conference League y EFL Trophy. En ligas y fases liga/grupos se ven tablas completas y, al costado, **todos los partidos de la jornada elegida**, con avance/retroceso. En copas y fases eliminatorias se ve el **bracket de cruces ya sorteados**, zoom, desplazamiento, camino confirmado del club y **todos los partidos de la ronda** en el panel lateral. UEFA y EFL Trophy permiten volver a sus fases iniciales.

**Sin predicciones ficticias:** las rondas futuras sin sorteo muestran `TBD`/pendiente; nunca se inventan rivales, scores, clasificaciones ni enlaces. Los escudos son marcadores provisionales de clubes ficticios. La interfaz es de solo lectura; **Continue y persistencia de la partida todavía no existen**. Sigue pendiente la auditoría técnica integral antes de implementar el avance real. Ver `docs/PHASE_UI_3_3_COMPETITIONS.md`.


## UI-3.3.1 — Brackets bilaterales y competiciones del club

El selector de **Competitions** muestra solo competiciones en las que participa el club (incluida FA Cup si la inscripción comienza en una ronda posterior). Las copas utilizan dos lados y final central, zoom progresivo (`−` revela más del cuadro y `+` permite ver los cruces), panorámica y conexiones únicamente para clasificaciones realmente confirmadas. El panel lateral siempre muestra todos los partidos de la ronda. Véase `docs/PHASE_UI_3_3_1_COMPETITIONS_REFINEMENT.md`. Se ejecuta por `.bat`, sin npm; Continue sigue pendiente.

## UI-3.3.2 — Competition Explorer

**Competitions** conserva la vista aprobada de UI-3.3.1 con botones de las competiciones del club (Premier League, FA Cup, Carabao Cup y Champions League), incluso si todavía no se ha sorteado el cruce de entrada de FA Cup. **Other Leagues** / **Otras ligas** es una pantalla *independiente en el menú izquierdo* donde se consultan los torneos restantes con filtros de participantes, ámbito, **continente siempre visible**, país (cuando corresponde), tipo y división. El selector de países permite escoger regiones aún sin ligas implementadas (por ejemplo España o Argentina), mostrándolas honestamente como vacías; nunca crea torneos ni resultados ficticios. Se conserva íntegramente el bracket bilateral, sus cuatro niveles de zoom y el panel lateral de partidos.

Se conservan el bracket bilateral, zoom progresivo, fase liga/KO y panel lateral con **todos los encuentros de la jornada o ronda**. No cambia el motor ni Continue. Aplicar el parche incremental sobre UI-3.3.1, abrir `INICIAR_INTERFAZ_WINDOWS.bat` sin Node/npm y consultar `docs/PHASE_UI_3_3_2_COMPETITION_EXPLORER.md`.

## UI-3.4 — Continue diario + Simular hasta una fecha

La interfaz portable (Python, sin Node/npm) usa `WorldSeasonRunner` como reloj real. **Continue** avanza exactamente un día, procesando partidos de otros clubes y recuperación física; en un día con partido propio cambia a **Go to Match (Ir al partido)** y deja pendiente ese encuentro. La pantalla específica de partido —en una pestaña nueva, a definir con el usuario— **todavía no está implementada**.

En **Calendar** podés seleccionar **cualquier día** y elegir **Simulate to this date**: avanza hasta ese día inclusive y simula **también los partidos del club** con `FastMatchSimulator`. Los resultados aparecen en Calendar y Competitions, y Home actualiza fecha, tabla real, forma reciente y plantel. El sistema de decisiones obligatorias aún no existe, así que todavía no puede producir interrupciones por decisiones de entrenador.

**Limitación fundamental:** esto sigue siendo una **sesión DEV temporal**, sin guardado completo. Al cerrar el servidor se pierde el progreso; tampoco se expone aún la transición de temporada en la interfaz. La auditoría integral antes de hacer una carrera persistente continúa pendiente. Ver `docs/PHASE_UI_3_4_DAILY_CONTINUE.md` y `docs/TECHNICAL_PREFLIGHT_UI_3_4.md`.

## UI-3.4.1 — Calendar y pantalla de simulación de resultados

Podés seleccionar **cualquier día del mes haciendo clic sobre toda su celda**, aunque no tenga un partido, y solicitar la simulación hasta esa fecha inclusive. El calendario oscurece los días ya transcurridos y conserva el color de victoria/empate/derrota de los partidos disputados. Los días pasados pueden consultarse, pero no retroceden la partida.

El avance rápido abre una **pantalla de progreso**, que recibe de Python los resultados reales del mundo a medida que se procesan. Muestra partido por partido, destaca Northbridge y permite cambiar la velocidad de visualización (sin alterar la simulación ni los resultados). La partida en memoria solo se actualiza **tras una simulación completa y correcta**; ante un fallo queda intacta. La barra porcentual refleja días procesados por el backend y puede ir adelantada respecto de los resultados que se están mostrando a velocidad reducida.

**Continúan las limitaciones de UI-3.4:** `Continue` normal avanza un día y muestra `Go to Match` cuando juega nuestro club; todavía no abre la futura pestaña de partido. No existe guardado completo de partida ni un sistema de decisiones obligatorias. Ver `docs/PHASE_UI_3_4_1_CALENDAR_PROGRESS.md`.


### UI-3.4.1 — Hotfix: resultados propios y confirmación integrada

La pantalla **Simulating your season** sigue procesando todos los partidos del mundo, pero **solo muestra los encuentros del club controlado**. El progreso porcentual y los días procesados siguen siendo los reales de Python. Cuando no hubo partidos propios durante el intervalo, aparece un estado vacío informativo.

El botón **Simulate to this date** de Calendar ahora abre una **confirmación visual propia del juego**, con fecha de destino, días a procesar y cantidad de partidos propios ya conocidos. Cancelar o pulsar Escape no avanza la partida. El sistema conserva la sesión DEV temporal, el avance diario y la protección ante fallos. Véase `docs/PHASE_UI_3_4_1_CALENDAR_PROGRESS.md`.

## UI-3.5 — Separate matchday tab

When Continue reads **Go to Match** on your club's fixture day, it opens a **separate browser tab** with the pre-match overview and your actual Python XI/bench, plus the opponent's generated DEV roster, unavailable players and provisional numbered shirts. Quick Sim opens an immersive-looking **final result dashboard** using the existing FastMatchSimulator: real possession/xG/shots/passes/fouls/corners and a timeline of actual goals/assists, cards, substitutions and penalty shootout kicks. The post-match **Continue** returns to the main game and advances one day.

**Match Tactics** reuses the Python formation/role/instruction/lineup commands but applies modifications **only to that fixture**; the permanent team tactics return after the result. **Kit Settings** and weather/referee labels are cosmetic. Referees are fictional, with per-tier and cup/UEFA pools. Match injuries and tackles are not in the current fast-engine event/statistics model and therefore are not fabricated; the Injuries filter says so. **Immersive Match** remains disabled. The DEV session still has no complete restart-safe save.

Start with `INICIAR_INTERFAZ_WINDOWS.bat` as before; no Node.js/npm needed. Technical details and limitations: `docs/PHASE_UI_3_5_MATCHDAY.md`.

### UI-3.5.1 — Matchday visual and interaction refinement

**Kit Settings** now has two large visual shirt previews, colour swatches, a shirt/shorts/socks preview and a visual-contrast hint. Colours remain cosmetic and match-only. **Match Tactics** now exposes the seven bench players next to the tactical pitch; drag a substitute to a starting position, drag two starters to exchange slots, or select a bench player and then a starting shirt. The dropdown swap fallback is retained for keyboard/touch users. Changes continue to use Python match-only commands and leave the usual tactic intact. The pre-match header no longer prints a DEV/decorative notice for weather/referees; those labels remain non-gameplay metadata. The match report timeline now shows **each event icon beside its text in its team's lane**, keeping minute markers centered. No simulator rules, game-event generation, or save system were changed. See `docs/PHASE_UI_3_5_1_MATCHDAY_REFINEMENT.md`.

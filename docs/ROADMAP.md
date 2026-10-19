# Roadmap

## 1. Filosofía del roadmap

El proyecto se desarrollará de forma incremental.

No se intentará construir desde el comienzo todas las funcionalidades de un juego como Football Manager.

Cada etapa deberá producir una mejora funcional y comprobable.

El roadmap no representa fechas obligatorias.

Representa un orden lógico de construcción.

## Estado actual después de Phase 6.7

El roadmap original de fases inferiores se conserva como referencia histórica, pero varias responsabilidades previstas para fases futuras fueron adelantadas durante la construcción del Fast Simulator.

Ya están implementados, entre otros:

- OVR y ACT contextual;
- confianza y adaptabilidad;
- Fast Match Simulator independiente del 2D;
- estadísticas de partido;
- strength/ACT curves y calibración;
- ejecución y matchups tácticos;
- knockout, prórroga y penales;
- condition, stamina, fatiga y recuperación entre fechas;
- UI de desarrollo descartable para inspeccionar plantel, XI, OVR/ACT, táctica, Quick Sim y futuros calendarios/competiciones.

El **camino crítico actual** pasa a ser:

```text
Phase 6.1 generic Competition framework
→ League + knockout + multi-stage formats
→ Fixture / Schedule separation
→ unified Calendar
→ persistent WorldState
→ first full English season loop
```

Hasta nuevo aviso, cualquier feature que necesite resolver partidos usa exclusivamente `FastMatchSimulator`. El 2D legacy queda congelado. El futuro 2D será una opción inmersiva para el partido del equipo del usuario y se reconstruirá por capas según `FUTURE_2D_REBUILD.md`.

Las fases originales 6-14 de este archivo ya no deben interpretarse como trabajo completamente pendiente: varias de sus responsabilidades están cubiertas por 5.11A-E.

### Nuevo bloque crítico después de 5.11

La numeración moderna del camino crítico continúa con:

```text
6.0 Disposable Development UI                  DONE
6.0b Contextual role OVR + position learning    DONE
6.1 Competition Framework                      DONE
6.2 Round-Robin League                         DONE
6.3 Knockout Competitions                      DONE
6.4 Multi-Stage Competitions                    DONE
6.5 Calendar & Scheduling                       DONE
6.5a EFL date slots + fictional 24-club leagues  DONE
6.5b FA Cup + Carabao Cup integration            DONE
6.6 Competition Runner / persistent results     DONE
6.6a ACT/condition, morale and calendar fixes     DONE
6.6b UEFA competitions + EFL Trophy              DONE
6.7 Full Season integration                     DONE
```

`6.0` no reemplaza la futura interfaz final: es una herramienta descartable para bajar a tierra sistemas mientras se construyen.

Phase 6.1 ya deja preparado que Inglaterra combine liga, FA Cup, EFL Cup y competición UEFA mediante IDs estables, ediciones, stages y reglas de clasificación configurables. Las plazas europeas no se hardcodean en el motor de liga: una edición puede declarar qué puestos clasifican a qué competición/etapa y qué rutas externas (por ejemplo campeón de copa) tienen prioridad o fallback al siguiente puesto elegible.

Phase 6.5 inicia la importación de calendarios reales con Premier League 2026/27. Las temporadas siguientes se generan desde ventanas/políticas de calendario, no copiando fechas literalmente ni sumando 365 días.

Phase 6.5a importa las fechas/horas por jornada publicados para Championship, League One y League Two 2026/27 (46 jornadas y 552 slots cada una) sin incorporar clubes reales: los 72 clubes EFL del sandbox son ficticios, sus cruces se generan y los `ScheduledFixture` se identifican como `GENERATED`. La calidad DEV se escalona por categoría y se expone en tablas/calendarios del sandbox. **No confundir fecha oficial con enfrentamiento oficial**: el dataset completo de cruces reales de esas tres ligas no se adjunta en 6.5a. 6.5b + 6.6 incorporan simultaneamente FA Cup y Carabao Cup como competiciones independientes con reglas/ventanas 2026/27, participantes ficticios y el Runner persistente que simula el resto del mundo domestico. La UI permite inspeccionar ambas copas y guardar/cargar resultados; no es un save completo de carrera.

**Decisión de alcance (6.5b + 6.6):** esta fase contiene las cuatro ligas y ambas copas domesticas; no incluye clubes reales ni el calendario jugable continental definitivo. Los cruces ficticios de copa no son sorteos oficiales. La FA Cup se simula desde la cuarta ronda clasificatoria; las anteriores quedan documentadas solo como ventanas. La regionalización exacta de Carabao R1/R2 necesita geografía de clubes y se incorpora más adelante. Los resultados persistentes del Runner no reemplazan un save completo de plantel/tácticas.

Phase 6.2 implementa esa separación a nivel deportivo: una lista real puede entrar como fixture `SEEDED`, transformarse en `RoundRobinTemplate` y servir de estructura para ediciones posteriores con clubes nuevos. Phase 6.5 agrega la asignación de fechas mediante `ScheduledFixture` / `SeasonCalendar`.

Phase 6.3 agrega la capa genérica de eliminación directa. Un sorteo de la primera temporada puede entrar como cruce `SEEDED`; cuando el mundo diverge de la realidad, las rondas posteriores se generan con los clubes que efectivamente avanzaron. El motor soporta partido único e ida/vuelta, global, prórroga/penales en el encuentro decisivo y avance automático, sin regla de gol visitante. Phase 6.5 aporta las ventanas y la cronología necesarias para ubicar esos cruces cuando existan.

Phase 6.4 compone standings y knockout mediante rutas configurables por puesto (`ADVANCE`, `PLAYOFF`, `ELIMINATED`). Esto permite representar una Champions-like league phase sin hardcodear números de UEFA y recombinar clasificados directos con ganadores de playoff. El sandbox incorpora una timeline DEV cross-competition y calendario completo solo para inspección.

Phase 6.5 agrega el calendario unificado real: `ScheduledFixture` separa fecha/estado/origen del `CompetitionFixture` deportivo, `SeasonCalendar` ordena fixtures de múltiples competiciones, detecta colisiones y descanso insuficiente, y soporta aplazamiento/reprogramación dentro de ventanas válidas. Las temporadas futuras generan fechas desde políticas propias y blackouts en vez de copiar el año anterior. También se incorpora como primer dataset oficial el fixture completo de Premier League 2026/27 (380 partidos), mantenido separado del mundo DEV hasta que exista la base real de clubes.

---

## Fase 0 — Fundación

### Objetivo

Preparar el proyecto antes de comenzar el desarrollo del simulador.

### Tareas

- Crear repositorio GitHub.
- Configurar `.gitignore`.
- Crear `README.md`.
- Crear documentación principal.
- Definir principios de diseño.
- Definir arquitectura inicial.
- Definir alcance de la primera versión.
- Preparar entorno Python.

### Resultado

Proyecto correctamente estructurado y documentado.

---

## Fase 1 — Modelo de jugadores

### Objetivo

Representar futbolistas correctamente.

### Implementar

- Player ID.
- Identidad.
- Edad.
- Nacionalidad.
- Pie dominante.
- Atributos básicos.
- Posiciones.
- Familiaridad posicional.
- Estado físico.
- Forma.
- Fatiga.

### Todavía no

- contratos;
- agentes;
- salarios;
- lesiones complejas;
- personalidad;
- desarrollo avanzado.

### Resultado

Poder cargar jugadores y consultar su estado.

---

## Fase 2 — Clubes y planteles

### Objetivo

Representar equipos.

### Implementar

- Club ID.
- Nombre.
- Reputación básica.
- Plantel.
- Titulares.
- Suplentes.
- Formación.
- Selección de XI.

### Resultado

Poder crear dos clubes con planteles y alineaciones diferentes.

---

## Fase 3 — Modelo táctico básico

### Objetivo

Construir las primeras variables tácticas.

### Implementar inicialmente

- formación;
- altura defensiva;
- presión;
- anchura;
- ritmo;
- estilo de salida;
- transiciones;
- roles básicos.

### Importante

No crear todavía decenas de instrucciones.

Primero se debe comprobar que unas pocas variables producen diferencias reales en el partido.

### Resultado

Dos equipos con los mismos jugadores pueden comportarse de forma diferente según su táctica.

---

## Fase 4 — Match Snapshot

### Objetivo

Crear una representación reproducible de un partido.

### Implementar

- local;
- visitante;
- alineaciones;
- atributos;
- estados;
- posiciones;
- roles;
- táctica;
- localía;
- seed.

### Resultado

Un partido queda completamente definido antes de ingresar al Match Engine.

---

## Fase 5 — Primer Match Engine

### Objetivo

Simular un partido completo.

### Primera versión

El motor deberá considerar:

- calidad real del XI;
- atributos;
- posiciones;
- familiaridad posicional;
- estado físico;
- forma;
- táctica;
- familiaridad táctica básica;
- localía;
- variabilidad.

### Importante

El resultado no deberá decidirse directamente.

El motor generará situaciones y ocasiones.

### Resultado

Poder ejecutar:

```text
Team A vs Team B
```

y obtener un resultado consistente y reproducible.

---

## Fase 6 — Estadísticas de partido

### Objetivo

Generar información más allá del marcador.

### Implementar

- goles;
- tiros;
- tiros al arco;
- posesión aproximada;
- xG;
- faltas;
- tarjetas;
- rendimiento individual;
- minutos.

### Resultado

El juego podrá diferenciar resultado de rendimiento.

---

## Fase 7 — Matchups tácticos

### Objetivo

Hacer que las tácticas interactúen.

### Implementar

Ejemplos de relaciones:

- línea alta vs ataques al espacio;
- presión alta vs salida corta;
- bloque bajo vs ataques posicionales;
- anchura defensiva vs extremos;
- laterales ofensivos vs transiciones.

### Regla

No implementar reglas rígidas de:

```text
A vence a B
```

Las ventajas deben surgir de situaciones futbolísticas.

### Resultado

Un equipo inferior puede generar una ventaja estratégica mediante un buen planteamiento.

---

## Fase 8 — Familiaridad táctica

### Objetivo

Crear consecuencias para la continuidad y el cambio táctico.

### Implementar

Familiaridad con:

- formación;
- presión;
- bloque;
- salida;
- ritmo;
- roles.

### A nivel

- equipo;
- jugador.

### Resultado

Mantener una táctica genera automatismos.

Cambiarla puede generar ventajas puntuales pero menor calidad de ejecución.

---

## Fase 9 — Química entre jugadores

### Objetivo

Representar entendimiento futbolístico.

### Implementar

- minutos juntos;
- experiencia;
- entendimiento táctico;
- confianza futbolística;
- relación personal básica.

### Primera aplicación

Influencia en:

- pases;
- movimientos;
- coberturas;
- acciones combinadas.

### Resultado

Dos jugadores pueden rendir mejor o peor juntos.

---

## Fase 10 — Adaptación posicional

### Objetivo

Permitir evolución de posiciones.

### Implementar

- minutos en posición;
- rendimiento;
- entrenamiento;
- atributos relevantes;
- edad;
- inteligencia táctica;
- experiencia previa.

### Resultado

Un jugador puede aprender una nueva posición.

---

## Fase 11 — Cambio de posición principal

### Objetivo

Permitir carreras dinámicas.

### Implementar

- posición original;
- posición principal actual;
- posiciones secundarias;
- historial de experiencia.

### Resultado

Un jugador puede evolucionar, por ejemplo:

```text
LW
↓
ST
```

sin perder completamente su experiencia anterior.

---

## Fase 12 — Fatiga y rotaciones

### Objetivo

Dar importancia a la gestión del plantel.

### Implementar

- fatiga por minutos;
- recuperación;
- calendario;
- condición física;
- impacto en rendimiento.

### Resultado

Utilizar siempre los mismos titulares tendrá consecuencias.

---

## Fase 13 — Sustituciones

### Objetivo

Modificar dinámicamente los partidos.

### Implementar

- suplentes;
- minuto de ingreso;
- fatiga;
- cambios de rol;
- cambios tácticos básicos.

Inicialmente la IA podrá realizar sustituciones automáticamente.

### Resultado

El partido puede cambiar durante los 90 minutos.

---

## Fase 14 — Eventos de partido

### Objetivo

Pasar hacia una simulación más detallada.

### Implementar progresivamente

- posesiones;
- recuperaciones;
- pases;
- progresiones;
- desmarques;
- centros;
- remates;
- goles;
- faltas.

### Resultado

El marcador surge cada vez más directamente de eventos futbolísticos.

---

## Fase 15 — Fixture

### Objetivo

Pasar de partidos aislados a una competición.

### Implementar

- calendario;
- fechas;
- local y visitante;
- ida/vuelta.

### Resultado

Generar una temporada completa sin resultados predeterminados.

---

## Fase 16 — Liga

### Objetivo

Crear la primera competición jugable.

### Implementar

- puntos;
- victorias;
- empates;
- derrotas;
- goles;
- diferencia de gol;
- tabla.

### Resultado

Poder completar una liga.

---

## Fase 17 — Estado persistente entre partidos

### Objetivo

Hacer que cada partido influya sobre el siguiente.

### Actualizar

- forma;
- fatiga;
- familiaridad;
- química;
- estadísticas;
- lesiones básicas;
- sanciones.

### Resultado

La temporada deja de ser una colección de partidos independientes.

---

## Fase 18 — Primera temporada completa

### Objetivo

Primer gran milestone del proyecto.

El usuario podrá:

- elegir un club;
- elegir titulares;
- seleccionar táctica;
- avanzar fechas;
- disputar partidos;
- consultar resultados;
- consultar tabla;
- terminar la temporada.

### Milestone

```text
v0.1 — Season Simulator
```

---

## Fase 19 — Guardado y carga

### Objetivo

Persistir una partida.

### Inicialmente

SQLite.

### Guardar

- jugadores;
- clubes;
- calendario;
- resultados;
- tablas;
- estados;
- relaciones;
- familiaridades.

### Resultado

Cerrar el juego y continuar posteriormente.

---

## Fase 20 — Interfaz inicial

### Objetivo

Dejar de depender de la terminal.

### Posible stack

- FastAPI;
- React;
- TypeScript.

### Primeras pantallas

- inicio;
- plantel;
- táctica;
- calendario;
- partido;
- tabla.

### Importante

La interfaz consumirá el motor existente.

No se reescribirá la simulación.

---

## Fase 21 — Lesiones

### Objetivo

Agregar disponibilidad dinámica.

### Implementar

- tipos de lesión;
- probabilidad;
- duración;
- gravedad;
- recaídas;
- influencia de fatiga.

---

## Fase 22 — Sanciones

### Objetivo

Implementar disciplina.

### Implementar

- tarjetas;
- acumulación;
- expulsiones;
- suspensiones.

---

## Fase 23 — Desarrollo de jugadores

### Objetivo

Permitir evolución a largo plazo.

### Factores posibles

- edad;
- potencial;
- minutos;
- rendimiento;
- entrenamiento;
- profesionalismo;
- instalaciones;
- lesiones.

### Resultado

Los jugadores cambian durante las temporadas.

---

## Fase 24 — Envejecimiento y retiro

### Objetivo

Crear continuidad histórica.

### Implementar

- deterioro físico;
- evolución técnica;
- edad;
- retiro.

---

## Fase 25 — Juveniles

### Objetivo

Renovar el mundo.

### Implementar

- generación de jugadores;
- academias;
- potencial;
- progresión.

### Resultado

Las partidas pueden continuar indefinidamente.

---

## Fase 26 — Contratos

### Objetivo

Agregar gestión laboral.

### Implementar

- salario;
- duración;
- vencimiento;
- cláusulas básicas;
- renovación.

---

## Fase 27 — Mercado de pases

### Objetivo

Crear movimiento de jugadores entre clubes.

### Implementar

- valor;
- interés;
- ofertas;
- negociación;
- decisión del jugador;
- necesidades del club.

### Resultado

Los planteles evolucionan entre temporadas.

---

## Fase 28 — IA de clubes

### Objetivo

Hacer que los rivales tomen decisiones.

### IA deberá considerar

- nivel del plantel;
- posiciones débiles;
- edad;
- presupuesto;
- estilo táctico;
- objetivos;
- mercado.

---

## Fase 29 — Finanzas

### Objetivo

Agregar sostenibilidad económica.

### Implementar

- presupuesto;
- salarios;
- ingresos;
- transferencias;
- premios;
- gastos.

---

## Fase 30 — Scouting

### Objetivo

Limitar el conocimiento perfecto del usuario.

### Implementar

- conocimiento;
- precisión;
- informes;
- scouts;
- regiones.

### Resultado

Los atributos de todos los jugadores no necesariamente serán conocidos con exactitud.

---

## Fase 31 — Personalidad

### Objetivo

Diferenciar jugadores más allá de atributos futbolísticos.

### Variables posibles

- profesionalismo;
- ambición;
- lealtad;
- presión;
- adaptabilidad;
- liderazgo.

---

## Fase 32 — Moral y dinámica de grupo

### Objetivo

Crear comportamiento colectivo.

### Implementar

- jerarquías;
- liderazgo;
- grupos;
- descontento;
- expectativas;
- minutos de juego.

---

## Fase 33 — Cuerpo técnico

### Objetivo

Agregar especialistas.

### Posibles roles

- entrenador;
- asistente;
- preparadores;
- médicos;
- scouts;
- director deportivo.

---

## Fase 34 — Rivales que analizan al usuario

### Objetivo

Evitar tácticas eternamente impredecibles.

### Implementar

- análisis de patrones;
- conocimiento del rival;
- preparación específica;
- ajustes tácticos.

### Importante

No será una penalización artificial por repetir táctica.

Será conocimiento acumulado.

---

## Fase 35 — Múltiples competiciones

### Objetivo

Expandir el mundo.

### Implementar

- copas;
- grupos;
- eliminatorias;
- clasificación;
- competición continental.

---

## Fase 36 — Múltiples países

### Objetivo

Crear un universo futbolístico mayor.

### Considerar

- calendarios;
- reglas;
- mercados;
- niveles;
- competiciones;
- transferencias internacionales.

---

## Fase 37 — Historia del mundo

### Objetivo

Registrar lo ocurrido durante las partidas.

### Guardar

- campeones;
- récords;
- goleadores;
- carreras;
- transferencias;
- premios;
- estadísticas históricas.

---

## Fase 38 — Sistema de mods

### Objetivo

Permitir reemplazar y ampliar contenido.

### Modificable

- jugadores;
- clubes;
- competiciones;
- nombres;
- reglas;
- assets.

### Resultado

El engine funciona independientemente de la base de datos utilizada.

---

## Fase 39 — Optimización

### Objetivo

Permitir mundos grandes.

### Analizar

- velocidad de simulación;
- memoria;
- consultas;
- almacenamiento;
- optimización adicional del Fast Match Simulator para simulación masiva de partidos secundarios.

---

## Fase 40 — Simulación a gran escala

### Objetivo

Permitir eventualmente:

- miles de clubes;
- decenas de miles de jugadores;
- múltiples países;
- décadas de simulación.

---

# Milestones principales

## v0.0.1 — Domain Prototype

- Player;
- Club;
- Lineup;
- atributos;
- posiciones.

---

## v0.0.2 — Match Prototype

- dos equipos;
- alineaciones;
- primer resultado;
- seed reproducible.

---

## v0.0.3 — Tactical Prototype

- táctica básica;
- matchups;
- familiaridad.

---

## v0.0.4 — Dynamic Match

- estado físico;
- forma;
- química;
- adaptación;
- estadísticas.

---

## v0.1 — Season Simulator

- fixture;
- liga;
- múltiples fechas;
- estado persistente;
- temporada completa.

---

## v0.2 — Squad Management

- fatiga;
- lesiones;
- rotación;
- roles;
- evolución de jugadores.

---

## v0.3 — Transfer Market

- contratos;
- mercado;
- transferencias;
- IA de clubes.

---

## v0.4 — Club Management

- finanzas;
- scouting;
- cuerpo técnico;
- juveniles.

---

## v0.5 — Football World

- múltiples competiciones;
- múltiples países;
- historia;
- ecosistema dinámico.

---

# Regla del roadmap

No avanzar de fase únicamente porque una funcionalidad exista.

Una fase deberá considerarse suficientemente estable antes de construir sistemas importantes encima.

El roadmap podrá reorganizarse si durante el desarrollo descubrimos que una dependencia necesita implementarse antes.



Hasta nuevo aviso, cualquier feature del juego que necesite resolver partidos utiliza exclusivamente Fast Match Simulator. El Match Engine 2D legacy queda fuera del camino crítico; un futuro 2D será opcional para ver/dirigir el partido del equipo del usuario.

### Phase 6.6a + 6.6b scope

The previous 6.6 Runner now covers **four English divisions, FA Cup, Carabao Cup, three modern UEFA competitions and EFL Trophy**. The 2026/27 UEFA/EFL Trophy reference windows are distinct from fictitious GENERATED pairings. The disposable sandbox exposes tables, groups and brackets and the managed club plays Champions; fixed conditional calendar ghosts and weak physical/morale feedback were corrected. The rest of the full-season lifecycle belongs in 6.7 (promotions, relegations, playoffs, qualification for future seasons and 2027/28 calendar regeneration).

## Milestone — Phase 6.7 COMPLETE (competition career, not full manager career)

The 2026/27 domestic + UEFA + Trophy world can finish, archive the season, assign the correct EFL promotion/relegation paths (including new 2026/27 Championship six-team playoffs), determine fictional club UEFA allocations under a configurable policy, and independently generate 2027/28 and later fixtures. Fixtures are unique per edition and carry generated provenance. `WorldCareer` stores annual results/history and is not a player/squad/tactics savegame. The sandbox now has a one-button full-season test and optional weaker-rival DEV testing.

**Next milestone, beyond core 6.x:** turn this results-only multi-season scaffold into a persistent game world with player and squad histories, injuries, finances, transfers, youth progression, fixture-aware manager decisions and complete savegames, before expanding the number of real-country leagues. Source: `docs/PHASE_6_7_FULL_SEASON_INTEGRATION.md`.

## UI track (new visual prototype milestone after Phase 6.7)

- **UI-1 — React + TypeScript visual Dashboard (IMPLEMENTED, needs Windows visual/build acceptance):** original high-fidelity dark dashboard shell, the approved widget arrangement, tactical Starting XI with **OVR** badges, sample inbox/news and sample competition tabs. Fake/demo dataset is labeled. Continue demonstrates only a one-day **display date** change, not Python season progress. See `docs/PHASE_UI_1_DASHBOARD_SHELL.md`.
- **UI-2 — Real read-only game presentation (PLANNED):** typed Python service and localhost transport; club, next fixture, league/cup state, tactical OVR and real metrics; integration tests.
- **UI-3 — True daily Continue (PLANNED):** game-session command, protected managed fixture flow, recovery/events, persistence; avoid duplicate simulation; regression tests.
- **UI-4 — Desktop distribution (PLANNED):** evaluate Electron vs Tauri with real Windows packaging and process management. Never migrate domain rules into TypeScript.

The roadmap above that prioritizes long-term player/club career remains relevant. UI prototyping has been pulled earlier at the user's explicit request; full career features still need their own phases.


## UI-2 checkpoint — implementation available for acceptance

Three user-approved Squad/Tactics states implemented using real Python DEV session data. A local stdlib server and shared editor work via the Windows launcher without Node/npm; the existing React shell embeds the same editor. The 44 controls are available, but the diagram is illustrative, not the legacy 2D simulator; not every field has a FastMatchSimulator consumer. Set pieces and full saves remain separate future systems. **Next**: validation on user's Windows, persistent manager-state integration, real Dashboard data, safe day-by-day Continue, then other designed screens. Details: `docs/PHASE_UI_2_SQUAD_TACTICS.md`.


### Updated UI checkpoint (UI-3)

- UI-1 Dashboard visual / Windows portable: **implemented** (Home still demo).
- UI-2 Python DEV interface, roles, instructions, tactics: **implemented and hotfixed**.
- UI-3 Squad roster/attributes/season-stat placeholders and Tactics navigation/scale: **implemented, Windows manual acceptance pending**.
- Future: player-season stats aggregation and xA definition; real market values, contracts, happiness, training, chat, set pieces, squad-number persistence, imported portraits, one-day Continue and actual career save. These are **not** claimed as implemented by UI-3.

This checkpoint supersedes older UI-2/3 proposal labels in the historical UI roadmap section above; UI-3 is not the originally anticipated daily Continue increment.

## UI-3.1 — Visual polish + Home connected to Python DEV

UI-3.1 keeps the UI-3 layout and scale, enhances depth/color and adds consistent deterministic illustrated player portraits in **Home, Squad and Tactics**, including nationality in roster and player details. Squad's expanded row now separates profile, current state, positional familiarity, attribute highlights and player-management actions. The Home starting XI, formation, dynamic status metrics, current date and opponent read **the same local Python DEV session** used by Squad/Tactics; returning to Home after changing a starter shows the changed team. OVR/ACT use one decimal.

Start in Windows with `INICIAR_INTERFAZ_WINDOWS.bat` (no npm). **This is still a temporary DEV session**: no persistence, no daily Continue, no contracts/market/training/player conversations/season ledger. The league table, news, manager/club story content and several club card fields remain labeled visual demo data; Python calendar match metadata is only partially available. See `docs/PHASE_UI_3_1_VISUAL_POLISH.md`.

## UI-3.2 — Calendar read model delivered for visual review

Calendar's UI now reads canonical managed fixtures and their registered outcomes, with months, competition filters, local/away, V/E/D based on shootouts, and two-leg aggregate as a separate summary. It does **not** create synthetic match history or enable Continue. Squad football-position sorting was fixed. These changes are in the UI track only; UI-3.2 intentionally does not implement the wider recommended SQLite/performance/social-dynamics work. Next integration priorities remain true daily advancement, persisted manager game state and player season statistics, to be planned separately after user acceptance. Source: `docs/PHASE_UI_3_2_CALENDAR.md`.

## UI-3.3 — Competitions visualization checkpoint

Implemented read-only Competitions UI on the existing Python development session with complete standings, all-club per-matchday fixtures, confirmed knockout brackets (zoom/pan), league/knockout stage toggling, and source-aligned cup/UEFA/EFL Trophy views. Undrawn ties are intentionally unknown. The Windows portable client runs with Python and no npm. This is not the final career save or integrated daily world progression; see `docs/PHASE_UI_3_3_COMPETITIONS.md`.

**Required gate before Continue:** perform the planned Technical Review & Stabilization of UI/Python boundary, save integrity, repeated world calendar scheduling, long-season performance, regression suite and static analysis. Only then design and implement safe one-day Continue, optional simulate-until-selected-date, and persistent manager state. Do not migrate JSON to SQLite or rebuild scheduling without measurements demonstrating the need.


## UI-3.3.1 — Competition UI refinements

Bilateral bracket, graduated zoom from close-up to full two-wing overview and final, no false future cup connections, club-only competitions selector. UI-3.3.1 precedes the agreed architecture/quality checkpoint and later Continue integration; no change to the season engine.

## UI-3.3.2 — Competition Explorer and late FA Cup access

UI-3.3.2 hotfix corrects the navigation: **Competitions** is still the original club-only tabbed section from UI-3.3.1 (including FA Cup registered for a later round); **Other Leagues** is a distinct left-sidebar page, with always-visible continent, national country, tournament type and division filters. Countries without implemented leagues are selectable but show honest empty states; all actual tables, matches and brackets continue to originate from the WorldSeasonRunner. Bilateral bracket/semantic zoom and panel of all round fixtures remain unchanged. The technical stabilization checkpoint still precedes Continue/full savegame integration. See `docs/PHASE_UI_3_3_2_COMPETITION_EXPLORER.md`.

## UI-3.4 — Daily Continue + Calendar fast-forward (implemented for DEV acceptance)

This update supersedes the older historical *UI-3 True daily Continue (PLANNED)* item **only for an in-memory single-season session**. Normal Continue moves exactly one day and defers managed matchdays to the future separate match screen; Calendar auto-simulates **through** managed fixtures without stopping, per user instruction. Both paths operate against the current Python WorldRunner. Home reads the real current standings and past form; UI requests commit in-memory transactionally. **Complete save/load, decisions/events, season transition and the full agreed Technical Review & Stabilization are NOT done**. Technical preflight and regression coverage are documented in `docs/TECHNICAL_PREFLIGHT_UI_3_4.md` and `docs/PHASE_UI_3_4_DAILY_CONTINUE.md`.

## UI-3.4.1 — Calendar progress experience (implemented, Windows acceptance pending)

Allows selection of any date cell; past dates are visually subdued. Calendar auto-simulation uses a background Python worker emitting canonical match results into a paged progress feed with controllable **presentation speed**. Managed fixtures are simulated automatically on fast-forward; one-day Continue still halts at `Go to Match`. Session swap is atomic **in memory only** after success. `docs/PHASE_UI_3_4_1_CALENDAR_PROGRESS.md` covers API and tests. **Next user-approved work: design the separate pre-match/match browser tab**. Full technical stabilization, persistence, mandatory decisions and multi-season transition remain future engineering gates.


### UI-3.4.1 hotfix — Approved polish before pre-match design

The simulation-progress feed now displays **only managed-club scores** while all world games continue in Python; browser-native confirmation was replaced with an integrated calendar skip dialog showing the destination, days and currently known managed fixtures. No gameplay or persistence change. Acceptance on Windows is pending before designing the new pre-match tab.

### UI-3.5 completed — Dedicated pre/post-match tab

- Go to Match opens a clean, sidebar-free new browser tab.
- Real lineup/bench/unavailable players for both clubs; provisional shirt numbers and cosmetic kit/weather/referee metadata.
- Temporary tactical commands for only the upcoming managed match; Quick Sim consumes the edited plan and commits its results, then restores the manager's usual tactics.
- Postmatch: score, real FastMatchSimulator statistical comparison and chronologically filtered goals/cards/substitutions/penalty-shootout events, including placeholders explicitly stating unsupported injury-event tracking.
- Continue goes back to main game and advances one day; Calendar autosimulation remains unchanged.

**Still pending:** complete save/load and technical stability checkpoint, actual in-match injuries, any richer player/match analytics unsupported by FastSim, real coach identities, authentic kits and immersive match playback. Avoid reintroducing the legacy 2D engine implicitly; revisit those design questions only with explicit authorization.

### UI-3.5.1 — Pre/post-match refinement (implemented; Windows acceptance pending)

Kit Settings provides an interactive, rendered uniform preview (without external artwork), colour choices, and a visual distinction indicator. Match Tactics exposes a draggable bench and pitch with a click-to-replace alternative and keyboard-capable selects; both use the previous, fixture-isolated `swap_starters` and `swap_bench` engine commands. Match report icons and descriptions stay on the same team's side. The decorative-data disclaimer was removed from pre-match **display** only; weather, referee and kits remain cosmetic in the documented model. All other match simulation and game-state behavior is unchanged.

## TC-E1 — International calendar foundation (completed in checkpoint branch)

Recurring FIFA windows, release-only national tournaments, original-fixture-first scheduling, FIFA reflow for generated seasons, and discreet Calendar markers have been added. No real national-team simulation, actual player call-ups, full career saves or global scheduling engine are claimed. TC-E1.1 now also applies the FIFA reflow to the initial seeded 2026/27 calendar without changing club pairings or already played dates. **Next TC-E2**: atomic registration/rollback for staged tournaments, cross-competition fixture rescheduling integrity and expanded checks. See `docs/TECHNICAL_CHECKPOINT_INTERNATIONAL_CALENDAR.md`.

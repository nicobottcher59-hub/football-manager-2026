==============================
docs/ARCHITECTURE.md
==============================

# Architecture

## 1. Objetivo

Este documento define la arquitectura técnica inicial del proyecto.

La prioridad es mantener separados:

- dominio del juego;
- simulación;
- estado del mundo;
- persistencia;
- datos;
- interfaz.

El objetivo es evitar que el proyecto quede acoplado desde el comienzo a una interfaz, base de datos o dataset específico.

---

## 2. Principios arquitectónicos

### 2.1 El motor debe ser independiente de la interfaz

El motor de simulación no debe saber si el juego se ejecuta desde:

- terminal;
- aplicación web;
- aplicación de escritorio;
- interfaz futura.

La interfaz será únicamente una forma de consultar y modificar el estado del juego.

---

### 2.2 La lógica no debe depender de nombres reales

Jugadores, clubes, competiciones y demás entidades serán identificados mediante IDs internos.

Ejemplo:

Incorrecto:

```python
if club.name == "River Plate":
```

Correcto:

```python
club.id
club.reputation
club.players
```

Los nombres visibles son datos reemplazables.

---

### 2.3 Separar datos de lógica

El código debe definir cómo funciona el juego.

Los archivos de datos deben definir qué jugadores, clubes y competiciones existen.

Por ejemplo:

```text
Código:
¿Cómo se calcula una lesión?

Datos:
¿Qué edad tiene un jugador?
¿En qué club juega?
¿Cuáles son sus atributos?
```

---

### 2.4 Separar capacidad de estado actual

Un jugador no debe mezclar en un mismo concepto:

- capacidad futbolística;
- estado físico;
- forma;
- moral;
- lesión;
- familiaridad.

Ejemplo:

```text
Atributos relativamente estables:
- pase
- técnica
- definición
- velocidad

Estado dinámico:
- condición física
- fatiga
- forma
- moral
- confianza
```

---

### 2.5 Los partidos nunca modifican directamente todo el mundo

El Match Engine debe recibir un estado de entrada y devolver un resultado.

Posteriormente otro componente aplicará las consecuencias.

Conceptualmente:

```text
World
  ↓
Match Snapshot
  ↓
Match Engine
  ↓
Match Result
  ↓
World Updater
  ↓
New World State
```

---

## 3. Arquitectura general

La arquitectura inicial será:

```text
                USER INTERFACE
                     │
                     ▼
                APPLICATION
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
       DOMAIN               SERVICES
          │                     │
          └──────────┬──────────┘
                     ▼
                SIMULATION
                     │
                     ▼
                PERSISTENCE
                     │
                     ▼
                    DATA
```

---

## 4. Domain

El dominio representa las cosas que existen dentro del universo del juego.

Ejemplos:

- Player;
- PlayerState;
- Club;
- Competition;
- Match;
- MatchLineup;
- Tactic;
- PlayerRelationship;
- Season;
- Fixture.

El dominio no debe contener lógica específica de interfaz.

---

## 5. Player

El jugador será una de las entidades centrales.

Conceptualmente estará compuesto por:

```text
Player
├── Identity
├── Attributes
├── Positional Familiarity
├── Role Familiarity
├── Career Data
└── Current State
```

### 5.1 Player Identity

Información relativamente permanente:

- ID;
- nombre;
- apellido;
- fecha de nacimiento;
- nacionalidad;
- pie dominante.

### 5.2 Player Attributes

Capacidades futbolísticas.

Más adelante podrán agruparse en:

#### Técnicos

- pase;
- técnica;
- definición;
- control;
- centros;
- regate;
- remate.

#### Mentales

- visión;
- decisiones;
- anticipación;
- concentración;
- posicionamiento;
- compostura;
- trabajo en equipo.

#### Físicos

- velocidad;
- aceleración;
- fuerza;
- resistencia;
- agilidad.

La lista definitiva se definirá durante el desarrollo del Match Engine.

---

## 6. PlayerState

El estado actual del jugador debe estar separado de sus atributos.

Ejemplo:

```text
PlayerState
├── fitness
├── fatigue
├── form
├── morale
├── confidence
├── match_sharpness
├── injury
└── suspension
```

Esto permite actualizar el estado constantemente sin modificar artificialmente los atributos futbolísticos.

---

## 7. Positional Familiarity

Las posiciones no serán valores booleanos.

No se utilizará:

```text
Puede jugar de delantero: sí/no
```

Se utilizará un grado de familiaridad.

Ejemplo:

```text
LW: 95
RW: 83
ST: 52
CAM: 71
```

La familiaridad podrá cambiar con el tiempo.

---

## 8. Role Familiarity

Posición y rol serán conceptos separados.

Ejemplo:

```text
ST

Advanced Forward: 82
False Nine: 90
Target Forward: 31
Pressing Forward: 76
```

La efectividad final no dependerá únicamente de esta familiaridad.

También dependerá de los atributos del jugador.

---

## 9. PlayerRelationship

Las relaciones entre jugadores estarán almacenadas separadamente.

Ejemplo:

```text
PlayerRelationship
├── player_a_id
├── player_b_id
├── tactical_understanding
├── football_trust
├── personal_relationship
├── minutes_together
└── experience_together
```

No se crearán relaciones entre todos los jugadores del mundo.

Solo se almacenarán relaciones relevantes.

---

## 10. Club

Un club tendrá inicialmente:

```text
Club
├── id
├── name
├── country
├── reputation
├── squad
└── tactical_state
```

Más adelante podrá incorporar:

- presupuesto;
- instalaciones;
- estadio;
- directiva;
- scouting;
- cuerpo técnico;
- juveniles;
- sponsors;
- objetivos.

---

## 11. Tactic

La táctica no será únicamente una formación.

Se dividirá en conceptos.

Ejemplo:

```text
Tactic
├── formation
├── defensive_line
├── pressing_intensity
├── width
├── tempo
├── build_up
├── transition_style
├── defensive_block
├── risk_level
└── player_roles
```

La lista definitiva evolucionará a medida que se diseñe el Match Engine.

---

## 12. Tactical Familiarity

Debe existir familiaridad tanto colectiva como individual.

Ejemplo colectivo:

```text
4-3-3: 90
high_press: 85
short_build_up: 92
high_defensive_line: 74
```

Ejemplo individual:

```text
Player X

4-3-3: 67
high_press: 72
short_build_up: 53
```

La familiaridad con conceptos similares podrá transferirse parcialmente.

---

## 13. MatchLineup

El Match Engine nunca debe recibir simplemente un club.

Debe recibir el equipo que realmente disputa el partido.

Ejemplo:

```text
MatchLineup
├── goalkeeper
├── defenders
├── midfielders
├── attackers
├── bench
├── formation
├── roles
└── tactic
```

Esto permite que rotaciones, lesiones y suspensiones afecten naturalmente al rendimiento.

---

## 14. MatchSnapshot

Antes de simular un partido se creará un estado congelado.

Ejemplo:

```text
MatchSnapshot
├── date
├── home_team
├── away_team
├── home_lineup
├── away_lineup
├── player_states
├── tactical_familiarities
├── relationships
├── context
└── random_seed
```

El snapshot contiene toda la información necesaria para reproducir el partido.

---

## 15. Match Resolution Boundary

Todo partido se resuelve a partir de un `MatchSnapshot` inmutable y devuelve un resultado sin mutar directamente jugadores, clubes, tablas ni el calendario.

Contrato conceptual:

```text
MatchSnapshot
      ↓
Match Resolver
      ↓
Match Result / FastMatchResult
```

Actualmente existen dos caminos arquitectónicos:

```text
FastMatchSimulator
→ resolvedor oficial y crítico para temporadas, competiciones y Quick Sim

Legacy spatial 2D engine
→ implementación experimental congelada; no forma parte del camino crítico
```

A futuro podrá existir un nuevo `2DMatchEngineV2` para el partido del equipo del usuario. Ese motor deberá consumir el mismo snapshot conceptual y producir consecuencias compatibles con el resto del juego.

Los sistemas de competición, calendario, persistencia y mundo nunca deberán depender de detalles internos del resolvedor utilizado.

---

## 16. Match Result Contract

El resultado no consiste únicamente en goles.

El contrato de salida debe poder transportar, según el resolvedor y la fase del proyecto:

```text
Match Result
├── score / tiebreak outcome
├── events
├── player_minutes
├── shots / shots on target / xG
├── possession / passes
├── fouls / cards / corners
├── goalscorers / assists
├── substitutions
├── injuries (future where not yet implemented)
├── player_performances
├── condition_after / fatigue_after
└── statistics
```

El Fast Simulator utiliza actualmente `FastMatchResult` y `FastPlayerStatistics`. Los sistemas posteriores deben consumir sus consecuencias sin acoplarse a la lógica interna del simulador.

La profundidad aumentará progresivamente, pero la frontera `snapshot -> result -> world update` debe mantenerse.

---

## 17. Match Events

A medida que evolucione el simulador, los partidos deberán generar eventos.

Ejemplos:

- posesión;
- recuperación;
- progresión;
- pase;
- desmarque;
- centro;
- remate;
- ocasión;
- gol;
- falta;
- tarjeta;
- lesión;
- sustitución.

El resultado final debe surgir de estos eventos.

---

## 18. Randomness

El sistema tendrá aleatoriedad controlada.

Nunca se utilizará el azar para decidir directamente:

> este partido lo gana el equipo inferior.

El azar será aplicado dentro de eventos futbolísticos.

Ejemplo:

```text
calidad de ocasión
+
definición
+
presión defensiva
+
arquero
+
azar
=
resultado del remate
```

---

## 19. Random Seeds

Todas las simulaciones importantes utilizarán una seed.

Esto permitirá:

```text
mismo snapshot
+
misma seed
=
mismo resultado
```

Esto será fundamental para:

- pruebas;
- debugging;
- análisis;
- balance.

---

## 20. Matchup Engine

Las tácticas no deben compararse mediante reglas rígidas.

No existirá:

```text
4-3-3 vence a 4-4-2
```

El Match Engine deberá analizar interacciones.

Ejemplo:

```text
línea defensiva alta
+
rival con delanteros rápidos
+
transiciones directas
=
mayor riesgo de ataques al espacio
```

---

## 21. Execution Quality

Debe existir una diferencia entre:

```text
Calidad del plan
```

y:

```text
Calidad de ejecución
```

La ejecución podrá depender de:

- atributos;
- inteligencia táctica;
- familiaridad;
- posición;
- rol;
- química;
- fatiga;
- presión rival.

---

## 22. World State

El mundo representa el estado general de una partida.

Conceptualmente:

```text
WorldState
├── current_date
├── players
├── clubs
├── competitions
├── seasons
├── fixtures
├── standings
├── relationships
└── statistics
```

Más adelante incorporará más sistemas.

---

## 23. World Updater

Después de un partido:

```text
MatchResult
      ↓
WorldUpdater
      ↓
WorldState actualizado
```

Será responsable de actualizar:

- puntos;
- tabla;
- estadísticas;
- minutos;
- forma;
- condición;
- fatiga acumulada / deuda de recuperación;
- lesiones;
- sanciones;
- familiaridad posicional;
- familiaridad táctica;
- relaciones.

---

## 24. Fixture Engine

El fixture podrá generarse al comienzo de una temporada.

Los partidos existirán con:

- fecha;
- local;
- visitante;
- competición.

Los resultados permanecerán vacíos hasta que los encuentros sean disputados.

---

## 25. Competition Engine

Las competiciones deberán estar definidas mediante reglas y no mediante lógica especial hardcodeada.

Ejemplo:

```text
League
├── teams
├── rounds
├── points_for_win
├── points_for_draw
├── relegation_rules
└── qualification_rules
```

Más adelante podrán añadirse:

- copas;
- grupos;
- eliminatorias;
- ida y vuelta;
- clasificación continental.

---

## 26. Persistence

En la primera fase no es necesario utilizar una base de datos compleja.

Etapa inicial:

```text
Python
+
JSON
```

Posteriormente:

```text
SQLite
```

Si el proyecto lo requiere:

```text
PostgreSQL
```

La lógica del dominio no debe depender directamente de cuál sistema de persistencia se utilice.

---

## 27. Data Packs

Los datos del juego deben poder reemplazarse.

Estructura conceptual:

```text
data/
├── default/
├── custom/
└── private/
```

Podrán existir distintos paquetes para:

- jugadores;
- clubes;
- competiciones;
- países;
- estadios;
- reglas.

---

## 28. Assets

Los recursos gráficos estarán separados de los datos y del motor.

Ejemplo:

```text
assets/
├── logos/
├── kits/
├── faces/
└── competitions/
```

El juego debe funcionar incluso si esos assets no existen.

---

## 29. Estructura inicial del proyecto

```text
football-manager-game/
│
├── README.md
├── .gitignore
│
├── docs/
│   ├── GAME_DESIGN.md
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
│
├── src/
│   ├── main.py
│   │
│   ├── domain/
│   │   ├── player.py
│   │   ├── player_state.py
│   │   ├── player_relationship.py
│   │   ├── club.py
│   │   ├── tactic.py
│   │   ├── lineup.py
│   │   ├── match.py
│   │   └── competition.py
│   │
│   ├── simulation/
│   │   ├── match_engine.py
│   │   └── fixture_engine.py
│   │
│   ├── services/
│   │   └── world_updater.py
│   │
│   └── data/
│       └── loader.py
│
├── data/
│   ├── clubs.json
│   └── players.json
│
└── tests/
```

Esta estructura podrá cambiar si el proyecto lo necesita.

---

## 30. Stack inicial

La primera etapa utilizará:

```text
Python
Git
GitHub
JSON
```

Todavía no se incorporarán innecesariamente:

- React;
- FastAPI;
- Docker;
- PostgreSQL;
- infraestructura cloud.

---

## 31. Stack futuro posible

Cuando el núcleo de simulación esté suficientemente maduro:

```text
Simulation Engine
Python
      ↓
Persistence
SQLite
      ↓
Application/API
FastAPI
      ↓
Frontend
React + TypeScript
```

Esto no constituye todavía una obligación técnica.

El stack podrá revisarse si aparecen mejores alternativas.

---

## 32. Testing

El proyecto deberá tener pruebas desde las primeras versiones.

Especialmente para:

- cálculos de atributos;
- fixtures;
- tablas;
- reproducibilidad;
- simulaciones;
- familiaridad;
- actualización del mundo.

Ejemplo:

```text
same snapshot
same seed
=
same match result
```

debe ser un test automático.

---

## 33. Balance Tests

Más adelante se crearán pruebas estadísticas.

Ejemplo:

Simular:

```text
Equipo A vs Equipo B
10.000 veces
```

y analizar:

- victorias;
- empates;
- derrotas;
- goles;
- xG;
- tiros;
- distribución de resultados.

Esto permitirá detectar problemas de balance.

---

## 34. Performance

La optimización prematura no será prioridad.

Primero:

> simulación correcta.

Después:

> simulación rápida.

Sin embargo, se evitarán decisiones estructurales obviamente ineficientes.

Ejemplo:

No almacenar relaciones entre cada posible par de jugadores del mundo.

---

## 35. Compatibilidad futura

El diseño debe permitir eventualmente simular:

- decenas de ligas;
- miles de clubes;
- decenas de miles de jugadores;
- múltiples temporadas.

No es necesario implementar esa escala desde el comienzo.

---

## 36. Regla principal de arquitectura

Cada sistema debe intentar responder una única pregunta.

Ejemplos:

```text
Player
¿Qué características tiene este jugador?

Match Engine
¿Qué ocurre en este partido?

World Updater
¿Qué consecuencias deja este partido?

Fixture Engine
¿Qué partidos deben disputarse?

Persistence
¿Cómo guardamos el estado?
```

Evitar componentes gigantes responsables de múltiples áreas no relacionadas.

---

## 37. Evolución de la arquitectura

Este documento no es definitivo.

La arquitectura podrá cambiar a medida que se descubran nuevas necesidades.

Sin embargo, cualquier cambio importante deberá preservar en lo posible:

- separación de responsabilidades;
- independencia del Match Engine;
- datos desacoplados;
- reproducibilidad;
- capacidad de testing;
- posibilidad de expansión.

---

## 38. Arquitectura actual de simulación rápida

Desde Phase 5.11, el Fast Match Simulator es el resolvedor oficial para el desarrollo del mundo persistente.

```text
Fixture / Competition
        ↓
MatchSnapshot
        ↓
FastMatchSimulator
        ↓
FastMatchResult
        ↓
WorldUpdater / Calendar
        ↓
WorldState
```

El Fast Simulator:

- no instancia agentes 2D;
- no depende de `SpatialMatchEngine`;
- utiliza RNG determinístico por streams;
- consume XI real, OVR, ACT, atributos, estado, familiaridad y táctica;
- resuelve los resultados mediante procesos futbolísticos probabilísticos;
- devuelve estadísticas y estado físico posterior al partido.

La calidad de plantilla crea una ventaja de base, pero un matchup táctico favorable y una ejecución superior pueden compensar diferencias moderadas de calidad. No existe un bonus universal por elegir una táctica determinada.

---

## 39. OVR, ACT y estado físico

La arquitectura separa tres conceptos:

```text
OVR
= calidad estructural derivada de atributos

ACT
= capacidad efectiva de expresar esa calidad en el contexto actual

condition
= frescura / disponibilidad física actual
```

`fatigue` representa deuda física acumulada y recuperación más lenta. No se aplica como una segunda penalización directa de ACT cuando la misma carga ya está expresada mediante `condition`.

Durante el partido, `stamina` es el principal atributo de resistencia al esfuerzo. Entre partidos, `natural_fitness` es el principal atributo de recuperación y `stamina` aporta de manera secundaria.

El simulador no muta jugadores persistentes: devuelve `condition_after` y `fatigue_after`; el sistema de mundo/calendario aplica esos valores y ejecuta la recuperación entre fechas.

---

## 40. Frontera con el futuro 2D

El motor espacial construido en Phase 5.0-5.9 queda preservado como implementación histórica/experimental, pero está congelado.

El futuro modo 2D será una reconstrucción incremental y no una condición previa para temporadas, ligas, mercado, scouting, contratos, finanzas u otros sistemas de management.

El partido del equipo del usuario podrá ofrecer en el futuro:

```text
Quick Sim
→ FastMatchSimulator

Ver / dirigir 2D
→ 2DMatchEngineV2
```

Los demás partidos del mundo seguirán utilizando Fast Match Simulator.

Ver `FUTURE_2D_REBUILD.md` para la estrategia de reconstrucción.

---

## 41. UI de desarrollo descartable

Phase 6.0 introduce una interfaz Tkinter exclusivamente para desarrollo. No es la arquitectura visual definitiva del producto.

La frontera es:

```text
football_manager.dev_ui.app
        ↓
DevelopmentSession
        ↓
Domain / Services / MatchSnapshot
        ↓
FastMatchSimulator
```

La capa Tkinter puede:

- mostrar estado;
- recoger decisiones del usuario;
- invocar operaciones de aplicación;
- renderizar resultados.

No puede contener fórmulas de OVR/ACT, lógica táctica, resolución de partidos, desgaste físico, reglas de competición ni persistencia de mundo.

`DevelopmentSession` es un adaptador temporal para la UI descartable y usa datos ficticios. Desde 6.5 ya no posee un algoritmo cronológico paralelo: registra sus cruces en el `SeasonCalendar` real, obtiene de allí el próximo partido y marca el fixture como `PLAYED` después de simularlo. Sigue siendo un harness descartable y no equivale al futuro `WorldState` persistente. Competitions proyecta tabla/fixtures de liga, bracket knockout y transición multi-stage únicamente para inspección, sin convertirse en la interfaz final.

La pantalla Tactics puede editar formación, roles e instrucciones, pero esas operaciones siempre mutan o reconstruyen objetos `Tactic` y `MatchLineup` reales a través del adaptador. Los indicadores colectivos son vistas derivadas del estado real: familiaridad combina posición/rol/táctica, condition y morale vienen de `PlayerState`, y la química del sandbox se inyecta como input explícito al `CurrentRatingContext` durante la construcción del MatchSnapshot. La futura capa persistente de relaciones reemplazará el origen provisional de química sin cambiar esta frontera.

La interfaz final podrá reemplazar por completo `football_manager.dev_ui` sin modificar el dominio futbolístico.



## Competition domain (Phase 6.1)

The competition layer is separate from match simulation and from calendar scheduling.

- `CompetitionDefinition` is stable identity/metadata for a competition.
- `CompetitionEdition` represents one season/edition with participants, ordered stages, qualification rules and sporting fixtures.
- `CompetitionStage` describes the sporting phase and its match-decider semantics.
- `CompetitionFixture` remains deliberately unscheduled; Phase 6.5 maps its stable fixture ID into a separate `ScheduledFixture` owned by `SeasonCalendar`.
- `QualificationRule` is data-driven. League positions can feed continental competitions, promotion, relegation or playoffs, while cup/title-holder routes can be resolved later across competitions.
- `CompetitionEdition.context_snapshot()` bridges competition rules into the immutable `CompetitionContextSnapshot` already consumed by `MatchSnapshot` and `FastMatchSimulator`.

## Round-robin league domain (Phase 6.2)

The league layer sits above Phase 6.1 and below future calendar/world orchestration.

- `RoundRobinFixturePlan` records whether sporting fixtures are `SEEDED` (external first-season data) or `GENERATED`.
- `RoundRobinTemplate` stores round/venue slots independently from club identity so later seasons can reuse the first-season structure with promoted/relegated participants.
- `generate_double_round_robin()` creates unscheduled home/away sporting rounds; a 20-club edition yields 38 rounds and 380 fixtures.
- `LeagueResult` stores final fixture scores.
- `build_league_table()` derives standings from results and configurable points/tie-break rules.
- standings convert to `StandingRowSnapshot` and enter `MatchSnapshot` through the existing competition-context boundary.
- no dates, season runner or persistent world mutation live in the league domain; Phase 6.5 owns dates, while the Phase 6.6 `WorldSeasonRunner` owns results and world mutation.

## Knockout competition domain (Phase 6.3)

The knockout layer extends the Phase 6.1 competition boundary without owning dates or match simulation.

- `KnockoutRoundDefinition` declares round order, single/two-leg format and the decisive-match resolver.
- `KnockoutRoundPlan` records `SEEDED` external pairings or `GENERATED` in-world draws.
- `KnockoutTie` groups one or two `CompetitionFixture` objects into one sporting tie.
- `KnockoutMatchResult` stores fixture score plus optional shootout score.
- `resolve_knockout_round()` derives aggregate winners; away goals are deliberately not a rule.
- `knockout_context_for_fixture()` converts prior-leg aggregate into `CupTieContextSnapshot`, lets non-deciding first legs draw, and delegates extra time/penalties on the deciding leg to the existing Fast Match Simulator.
- `advance_knockout_round()` creates the next draw only from actual winners.
- real FA Cup/EFL Cup entry rules, dates and imported draws are data/orchestration concerns for later phases, not hardcoded into this domain.

## Multi-stage competition domain (Phase 6.4)

The multi-stage layer composes the existing standings and knockout domains rather than replacing them.

- `StandingRouteRule` maps a band of positions from a standings-based source stage to `ADVANCE`, `PLAYOFF` or `ELIMINATED`.
- `resolve_standing_stage_transition()` converts a completed table into deterministic club-to-stage assignments.
- routes are edition data: the engine contains no hardcoded UEFA position numbers.
- `merge_stage_participants()` recombines direct qualifiers with later playoff winners while rejecting duplicate clubs.
- `validate_multi_stage_edition()` validates stage references and forward-only transitions.
- the Development Continental harness proves league-phase -> playoff/direct route -> knockout composition with existing Fast Simulator / knockout semantics.

The ad-hoc chronology introduced alongside 6.4 has been replaced in 6.5 by the real `SeasonCalendar` domain. `dev_ui` still owns fictional test data, but it consumes the same scheduling API rather than implementing a second calendar model.


## Phase 6.5a — fictional EFL tiered schedules

`football_manager.data.efl_2026_27` expands validated source-controlled 2026/27 matchweek kickoff-date templates for Championship, League One and League Two (46 × 12 each). `RoundRobinFixturePlan.generated` provides 24 fictional participants and 552 home/away fixtures per division; `SeasonCalendar` maps those generated pairings to the published slots without booking the same imaginary club twice. The distinction between **source-derived kickoff slots** and **generated sporting fixtures** is explicit. All EFL DEV `ScheduledFixture` rows are `GENERATED`, never `OFFICIAL`. Team strength indices are tier-banded, separate from player/ACT and FastSim's calibrated managed-club ratings. UI reads typed view models from `dev_ui.session`, not directly from the slot files. Full limitations and sources are in `docs/PHASE_6_5A_EFL_FIXTURE_SLOTS.md`.

## Calendar & scheduling domain (Phase 6.5)

Calendar placement is a separate layer above sporting competition structure.

```text
CompetitionFixture (who/where in sporting terms)
        ↓ stable fixture_id
ScheduledFixture (when/status/source)
        ↓
SeasonCalendar (cross-competition chronology)
```

- `ScheduledFixture` owns a timezone-aware kickoff, scheduling provenance (`OFFICIAL` / `GENERATED`), lifecycle status and optional original kickoff after a move.
- postponing removes the active kickoff while preserving the original date; rescheduling assigns a new kickoff without changing the sporting fixture identity.
- `SeasonCalendar` provides club/competition/date queries, next-fixture lookup, played/postponed/rescheduled transitions and cross-competition conflict detection.
- `SchedulingWindow` and `find_available_kickoff()` model the date band/days where a competition can be placed and reject slots that violate a club's configured rest requirement.
- `reschedule_fixture_into_window()` uses the same slot search while excluding the fixture being moved.
- `LeagueSchedulingPolicy` + `generate_league_round_dates()` generate dates for a new season from that season's own start/end, preferred weekday and blackout periods. Future seasons do not copy prior kickoffs or add a fixed year offset.
- `merge_calendars()` composes competition schedules into one chronological season view while preserving fixture IDs.

Phase 6.5 is authoritative scheduling logic, not yet durable WorldState storage. Phase 6.6 now persists/advances results and cup progression against this calendar; the full career save and future-season lifecycle remain separate.

### Official schedule data boundary

`football_manager.data.official_schedule` is the loader boundary for source-controlled official schedule snapshots. The first packaged dataset is Premier League 2026/27:

- 20 clubs;
- 38 matchweeks;
- 380 fixtures;
- complete double round-robin validation through the existing Phase 6.2 league plan;
- timezone-aware Europe/London kickoffs;
- `OFFICIAL` scheduling provenance and source metadata.

The official edition is intentionally separate from the fictional DEV world. Until the real club/world database exists, the sandbox exposes it as an inspector rather than pretending Northbridge participates in the Premier League.


## Phase 6.5b + 6.6 — English domestic cups and world results

```text
CompetitionEdition x4 (Premier / Championship / League One / League Two)
          └──────────────┐
DomesticCupSeason x2 (FA Cup / Carabao Cup, generated draws)
          └──────────────┼──> WorldSeasonRunner
                         │      ├── canonical ScheduledFixture state
SeasonCalendar slots ────┘      ├── WorldMatchResult ledger (managed or DEV background)
                                ├── standings derived from league result ledger
                                ├── cup results / tie winner advancement / new draws
                                └── atomic JSON save/load (world results only)
```

- `domain.domestic_cups`: `DomesticCupRound` declares entrants by round, permitted published date windows, number of legs and deciding-match rules. `DomesticCupSeason` draws the first round and advances only from known winners. All pairings among fictitious clubs are GENERATED, not imported real draw pairings.
- `data.english_cups_2026_27`: 2026/27 FA and EFL cup round windows and staggered entry. FA Cup's first five qualifying rounds are published dates only. The simulated FA Cup starts with a fictional fourth qualifying round; non-league clubs are placeholders. Carabao's first and second rounds are generated without region restrictions (no valid fictional location map yet).
- `domain.world_runner`: registers all four league editions plus both cup seasons; `record_result` owns the one-and-only result for each fixture and updates calendar state; `advance_until` simulates unattended clubs via a seeded strength-aware background approximation, halting for `protected_club_id`; `simulate_fixture` is deterministic per fixture ID.
- The managed club continues to use the existing `FastMatchSimulator`. DEV background strength/Poisson is not a replacement for actual squad-based simulation, and the game will need real-world club/player models later.
- League standings are pure derivations from the runner results; cup draws and final champions are stored in the cup season state. Cup scheduling may displace fictitious league fixtures while respecting 48 hours' rest; official Premier imports are never modified by this DEV runner.
- `save_json` uses atomic replacement and validates saved fixture IDs, participants, stage structure and score/status consistency when loading. It deliberately does not persist full player state, tactics or the separate DEV continental test competition.
- `dev_ui.session` projects world results into existing views and the UI adds an FA Cup/Carabao bracket selector and world-results save/load controls. Legacy Development Cup stays isolated as a bracket inspector.
- Future Phase 6.7 handles full-season outcome rules, promotions/relegations and next-season creation; it is not implied by 6.6.

## Phase 6.6a + 6.6b - Canonical staged world competitions and physical response

`StagedWorldCompetition` models UEFA league phases and EFL Trophy groups and produces generated knockout plans through the existing `KnockoutRoundPlan`/`resolve_knockout_round` domain. `WorldSeasonRunner.register_staged` places every scheduled stage fixture into the SAME ledger and `SeasonCalendar` as English league and cups. Group/tie results and stage generation are persistent; schema v2 adds `staged` to JSON. `DevelopmentSession` projects the canonical state into the Tkinter inspector and uses it for managed Champions matches. The disconnected 6.4 Development Continental remains legacy inspector only, with no conditional dummy fixtures inserted in the real calendar.

The player rating pipeline remains contextual OVR followed by ACT. The condition penalty below 75 is stronger, travels into the immutable MatchSnapshot and consequently into FastMatchSimulator. Morale remains a separate bounded state adjustment; result-driven changes now include stronger reversion. No chemistry or role-learning overhaul.

Published European/EFL Trophy dates are **reference windows**; kickoff conflicts between fictitious participants cause DEV reprogramming. UEFA national/pot draw constraints and protected bracket slots, exact 2026/27 official pairings and true geographic Trophy regionalization are not implemented here. See `docs/PHASE_6_6A_6_6B_UEFA_TROPHY_FIXES.md`.

## Phase 6.7 — Career lifecycle above the competition runner

`WorldSeasonRunner` remains the **single-season canonical fixture/result store**; it generates and registers three EFL promotion playoffs once their 46-round tables finish. `SeasonReport` records the validated ending state, tier roster movements, champions and Europe qualification without mutating archived results. `WorldCareer` owns multiple independent yearly runners and transition reports, serializes an atomic **results-only** history, and recreates the next world using `future_seasons` templates. All seasons keep fixture IDs separate, and the initial 92 clubs retain their stable identity across promotions and relegations.

The Championship has six playoff participants from 2026/27, while League One/Two have four; seeding/leg order are competition rules (`DomesticCupSeason.pairing_strategy`), not UI logic. The four English tiers remain the only actively simulated domestic pyramid; two fictitious National League clubs are generated at the external League Two boundary each year. UEFA places use `EuropeanAccessPolicy` including configurable performance spot and cup fallback; coefficients and other countries' access lists are not yet implemented.

`DevelopmentSession` orchestrates Northbridge's real FastMatchSimulator fixtures versus background world results and exposes a bulk season command. `DevelopmentUI` runs this blocking operation on a background worker and applies GUI changes only on the Tk main thread. A sandbox-only rival-strength adjustment provides a test-friendly path to finals without scripted results or changes in competition rules. The **complete squad/tactics save** is a future layer, not interchangeable with `WorldCareer`'s result archive. See `docs/PHASE_6_7_FULL_SEASON_INTEGRATION.md`.

## UI-1 — Presentation prototype architecture (after Phase 6.7)

The original independence rule remains in force. `frontend/` is a React + TypeScript + Vite **visual-only** UI; it imports no Python code and owns no football rules. Display numbers (including tactical OVR) are explicitly sample placeholders, never derived game values. `src/football_manager/dev_ui` remains the disposable Tkinter test sandbox. No Electron/Tauri runtime or localhost API is implemented yet.

Proposed direction for UI-2+: `React <-> typed localhost application API <-> Python services <-> existing domain/runner`, with game state and persistence owned by Python. The Tkinter `DevelopmentSession` must not become a stable API merely because its helper methods exist. Crucially, the existing `continue_to_next_match()` skips to the next fixture; it does not implement the new per-day Continue requirement. See `docs/PHASE_UI_1_DASHBOARD_SHELL.md` for acceptance criteria and technical debt.


## UI-2 local adapter (2026-10)

`football_manager.ui_shell` hosts a loopback-only stdlib HTTP API and static shell. `ui_shell.models` adapts **existing** `DevelopmentSession` view models and domain methods, using Python as the single source of truth for OVR/ACT and tactics. `frontend/public/squad/` is a shared temporary JS/CSS editor embedded in both React/Vite and the no-Node Windows launcher. No data model or match engine logic is copied into the browser. Only a **schematic positioning diagram** lives in JavaScript. No career persistence or daily Continue is implemented; see `docs/PHASE_UI_2_SQUAD_TACTICS.md`.


## UI-3 architecture note — no domain duplication

`UIRosterAdmin` is an in-memory object attached to the loopback UI runtime, not to the domain `Player` or `WorldCareer`. It stores temporary shirt numbers/transfer visibility only. `squad_read_model` extracts player names, stats, overall/current ratings, all attribute groups and `PositionalFamiliarity` directly from the existing `DevelopmentSession`; unknown season/contract/financial data stay `None` in the JSON read model. The `frontend/public/squad/roster.js` table and the existing squad/tactics editor are both portable assets loaded from the same backend. The original React+TypeScript shell embeds that shared code until a dedicated React rewrite is justified. No FastMatchSimulator, WorldSeasonRunner or legacy spatial logic was changed.

## UI-3.1 — Visual polish + Home connected to Python DEV

UI-3.1 keeps the UI-3 layout and scale, enhances depth/color and adds consistent deterministic illustrated player portraits in **Home, Squad and Tactics**, including nationality in roster and player details. Squad's expanded row now separates profile, current state, positional familiarity, attribute highlights and player-management actions. The Home starting XI, formation, dynamic status metrics, current date and opponent read **the same local Python DEV session** used by Squad/Tactics; returning to Home after changing a starter shows the changed team. OVR/ACT use one decimal.

Start in Windows with `INICIAR_INTERFAZ_WINDOWS.bat` (no npm). **This is still a temporary DEV session**: no persistence, no daily Continue, no contracts/market/training/player conversations/season ledger. The league table, news, manager/club story content and several club card fields remain labeled visual demo data; Python calendar match metadata is only partially available. See `docs/PHASE_UI_3_1_VISUAL_POLISH.md`.

## UI-3.2 - Managed Calendar read model and positional sorting

`football_manager.ui_shell.calendar.calendar_read_model` projects the current
`DevelopmentSession`'s *canonical* `SeasonCalendar`, managed fixtures and
`WorldSeasonRunner` registered results into a read-only, JSON-safe model. The
loopback server exposes it as `GET /api/calendar`. It includes currently known
opponents, local/away status, fixture source, stage/round, scheduled UTC kickoff,
registered results, shootout decisions and real two-leg aggregates resolved by
the domain knockout resolver. The adapter neither creates fixtures nor advances
the world, and deliberately omits conditional undrawn knockout placeholders.

`frontend/portable/calendar.js` renders the monthly grid, competition filtering
and a match-detail panel using only that API; `calendar.css` carries the distinct
competition backgrounds and independently colored sporting outcomes. Provisional
club emblems are computed only for display. The existing shared roster in
`frontend/public/squad/roster.js` now sorts position codes according to
on-pitch order rather than alphabetical order. See
`docs/PHASE_UI_3_2_CALENDAR.md` for behavior and limitations.

## UI-3.3 — Competition read models and bracket presentation

`football_manager.ui_shell.competitions` adapts **existing** `WorldSeasonRunner` data to a JSON-safe read model exposed by `/api/competitions` and `/api/competitions/<competition_id>` inside the loopback `FootballUIHandler`. Leagues use the existing standings comparator; fixtures and scores come from registered world calendars/results. Cups and staged knockouts use canonical drawn plans and `resolve_knockout_tie`; undrawn rounds emit metadata only, never guessed opponents. Standings and fixtures are fetched separately per selected competition to avoid sending the whole world's records on every screen.

`frontend/portable/competitions.js` renders league/group tables, confirmed bracket cards, optional links only between actual settled progression and actually drawn next-round ties, pan/zoom, and the all-clubs sidebar for each matchday/round. It never mutates world or season state. The current non-Node Windows launcher uses these JS/CSS assets directly. Future React integration may reuse the read-model API; this release does not introduce React Router, Zustand or duplicate domain logic.

### UI-3.5: isolated matchday tab

The portable Python HTTP server serves `/portable/match.html` (separate browser tab) and provides `GET/POST /api/match`. `ui_shell/match.py` is a **read-model/presentation adapter**; it never simulates or fabricates sporting events. Only `DevelopmentSession.quick_simulate()`/`FastMatchSimulator` resolve a managed match. The HTTP runtime locks out concurrent world simulations and associates temporary match-only tactical commands with the exact fixture ID. A deep-copy commit protects the active world against partial results. The match copy is restored to the main squad's tactical shape/plan after simulation; fixture, player condition and morale from that very simulation remain. The frontend `match.js`/`match.css` is standalone and uses no bundled React, Node.js or iframe in the main UI. `docs/PHASE_UI_3_5_MATCHDAY.md` records full contracts and limitations.

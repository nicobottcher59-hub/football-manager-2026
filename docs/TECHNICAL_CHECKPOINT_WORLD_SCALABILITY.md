# TC-E0 - Escalabilidad del mundo y del calendario (diagnostico)

**Estado:** evaluacion tecnica sobre UI-3.5.1, sin cambios de produccion.
**Entorno:** pruebas sinteticas en Linux; los tiempos deben repetirse en Windows.
**Artefactos:** `tools/stress_world_calendar.py`, `tests/test_world_scalability_diagnostic.py`, `reports/world_scalability_diagnostic.json`.

## Alcance y limites

Se ejecuta el **motor real** `WorldSeasonRunner` sobre calendarios generados con las funciones del dominio. Los clubes y paises de estres NO estan incorporados a la carrera ni son clubes reales: 20 clubes por liga, cuatro divisiones por pais sintetico, ventanas estacionales distintas y, opcionalmente, tres torneos con **formato** UEFA usando los constructores existentes. Un cuarto torneo opcional es una copa eliminatoria generica como **proxy de congestion intercontinental**, **no** el Mundial de Clubes FIFA real (sin grupos, reglas ni clasificacion). Se aplican bloqueos internacionales de laboratorio, **no fechas FIFA oficiales**. No se simulan selecciones ni convocatorias, y no se ejecuta FastMatchSimulator para todos los partidos.

La prueba de 24 ligas y torneos cruzados debe leerse en dos niveles: integridad estructural (partidos, horarios y resultados) y conformidad con bloqueos internacionales. Un escenario puede superar el primero y fallar el segundo.

## Resultados

Los resultados exactos se guardan en JSON, con `seed`, ano, conteos, errores y duraciones. Los escenarios sin simulacion (`simulate=false`) miden exclusivamente planificacion inicial: `unplayed=null` **no significa** que haya terminado la temporada.

| Escenario | Partidos* | Simulacion (s) | JSON mundo (MB) | Conflictos 48 h | Dentro de bloques | Estado |
|---|---:|---:|---:|---:|---:|---|
| 4 ligas, sin torneos cruzados | 1.520 | 1,24 | 1,68 | 0 | 0 | Integro |
| 8 ligas, sin torneos cruzados | 3.040 | 5,19 | 3,36 | 0 | 0 | Integro |
| 16 ligas, sin torneos cruzados | 6.080 | 17,11 | 6,72 | 0 | 0 | Integro |
| 24 ligas, sin torneos cruzados | 9.120 | 41,23 | 10,08 | 0 | 0 | Integro |
| 8 ligas + UEFA + copa proxy + aplazamientos | 3.260 | 4,45 | 3,59 | 0 | 34 | Integro; gaps de blackout |
| 24 ligas + 3 UEFA + copa proxy (2026) | 9.682 | 56,72 | 10,65 | 0 | 51 | Integro; gaps de blackout |
| 24 ligas + 3 UEFA + copa proxy (2027) | 9.682 | 70,53 | 10,65 | 0 | 77 | Integro; gaps de blackout |
| 24 ligas + 3 UEFA + copa proxy (2028, solo agenda) | 9.532 | - | 8,53 | 0 | 36 | Solo agenda |

* En escenarios completos son partidos efectivamente resueltos; en planificacion sola son fixtures iniciales, no resultados.
* Los bloqueos son ventanas sinteticas de laboratorio; no representan fechas FIFA reales.
* El JSON incluye WorldSeasonRunner (sin jugadores, entrenador ni savegame completo).
* No comparar tiempos directamente con la temporada inglesa original: los torneos y FastMatchSimulator son diferentes.


**Hallazgos:**

1. El generador de fechas de liga acepta `LeagueSchedulingPolicy.blackout_periods`, pero las ventanas prohibidas no estan integradas como politica global para todos los calendarios (`WorldSeasonRunner._schedule_staged_fixture` y `_insert_cup_match`). Tambien `reschedule_fixture_into_window` selecciona horarios sin recibir periodos internacionales. Por eso el laboratorio observa partidos en bloques sinteticamente prohibidos sin que el validador de 48 h marque conflicto.
2. El verificador `SeasonCalendar.detect_conflicts(minimum_rest_hours=48)` controla descanso y simultaneidad **por club**, no incompatibilidades de jugadores convocados por seleccion, viajes, zona horaria de origen, sedes compartidas ni otras restricciones FIFA. Un cero en ese contador no demuestra factibilidad del futuro mundo completo.
3. El algoritmo de simulacion `WorldSeasonRunner.advance_until` vuelve a ordenar los encuentros pendientes en cada iteracion. Los tests prueban escalabilidad en distintos tamanos, pero las cifras de un equipo de prueba no son prediccion directa del futuro producto.
4. Una prueba marcada `xfail` reproduce que `WorldSeasonRunner.register_staged` puede agregar la competicion al registro antes de descubrir una ventana imposible. El alta no es transaccional: hay que validar o aplicar cambios atomicos con rollback.
5. `finalize_season()` del ciclo de carrera exige **exactamente cuatro ligas inglesas** (`TIER_IDS`); con ocho ligas sinteticas y 3.040 resultados completos devuelve `ValueError`. Por eso superar los tests del World Runner **no equivale a poder avanzar temporadas con 24 ligas en WorldCareer**. `data/future_seasons.py` tambien usa fechas inglesas fijas y aun no propaga la politica general de blackout.
6. `_schedule_staged_fixture()` restringe sus ventanas a agosto--15 de junio. Un futuro Mundial de Clubes con partidos en la segunda quincena de junio y julio **necesita modelar limites de temporada/torneos de verano**, no basta con copiar las reglas UEFA.
7. No existe aun un modelo de selecciones/convocatorias/fechas FIFA integradas ni una implementacion del Mundial de Clubes en este escenario. Sus tests end-to-end quedan pendientes hasta que se disenen e incorporen esas reglas.

## Como reproducirlo

Desde la raiz del repositorio (Python >= 3.11, sin Node ni npm):

```bash
python -m pytest -q tests/test_world_scalability_diagnostic.py -ra
python tools/stress_world_calendar.py --quick
python tools/stress_world_calendar.py --full --output reports/world_scalability_local.json
```

Escenario individual completo con 24 ligas:

```bash
python tools/stress_world_calendar.py --single --leagues 24 --staged 3 --blackouts --cup-proxy --postponements 4 --seed 6060 --year 2026 --output reports/world_scalability_24_local.json
```

Planificacion sola, sin resultados ni fase final de eliminatorias:

```bash
python tools/stress_world_calendar.py --single --leagues 24 --staged 3 --blackouts --cup-proxy --postponements 4 --no-sim
```

En Windows funciona con `python` y la estructura `src` del repositorio; no es necesaria la interfaz. `rss_mb=0` significa que no existe medicion por `resource` en esa plataforma, **no** memoria cero. En Linux, `rss_mb` es el pico del **proceso entero**, acumulado entre escenarios del mismo comando, no uso aislado de cada liga.

## Plan previo a ampliar ligas

**Prioridad 1 - Reglas y pruebas del calendario global.** Definir una politica compartida de indisponibilidad (club, competicion, pais, fecha, descanso, viajes opcionales) utilizable por ligas, copas, UEFA y cualquier reprogramacion. Los periodos internacionales tendran semantica deportiva explicita (si bloquear partidos de clubes o provocar ausencias por convocatorias); no imponer reglas inventadas.

**Prioridad 2 - Seguridad transaccional.** Registrar torneos, sortear rondas y reprogramar partidos sobre copias o transacciones; ante ventanas imposibles, devolver errores estructurados y dejar el mundo exactamente igual. Testear rollback ante fallas parciales.

**Prioridad 3 - Coste de calendario.** Sustituir ordenamientos repetidos de partidos por un indice/cola de proximos encuentros, y agregar indice de fixtures por club para consultas de conflictos. Medir CPU/memoria y demostrar identidad de resultados y sorteos bajo las mismas semillas antes de aprobar cambios.

**Prioridad 4 - Carrera multiregional y verano.** Generalizar la transicion de temporada para multiples paises sin perder las reglas inglesas existentes. Definir como se modelan partidos del final de junio/julio y la pertenencia a temporadas.

**Prioridad 5 - Stress en varias semillas, temporadas y Windows.** Repetir 4/8/16/24 ligas, variaciones de ventanas, multiples torneos y aplazamientos forzados; certificar estado final, transiciones e integridad JSON. Integrar selecciones y un formato de Mundial de Clubes real **solo cuando esos sistemas existan**. No sustituir todo el planificador por un solucionador CSP sin evidencia de fallas insolubles.

## Criterios de aceptacion para TC-E

- Simulacion completa bajo semillas independientes, sin fixture duplicado o perdido, con descanso configurable y sin resultados huerfanos.
- Cero partidos en fechas explicitamente bloqueadas para el tipo de competicion correspondiente, con excepciones documentadas.
- Operaciones de alta/reprogramacion atomicas, incluso cuando no exista fecha valida.
- Al reprogramar, no repetir un resultado ya comprometido ni cambiar un enfrentamiento.
- Benchmark reproducible con tiempos/espacio bajo limites medidos para el hardware de referencia, sin regresion de integridad deportiva.

**Decision:** mantener el algoritmo actual y no ampliar ligas de produccion hasta implementar la politica global y los tests pertinentes. Esto no impide avanzar con TC-A (quality baseline) y el guardado completo TC-B/TC-C mientras tanto.

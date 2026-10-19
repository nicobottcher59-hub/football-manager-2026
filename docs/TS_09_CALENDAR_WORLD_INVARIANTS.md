# TS-09 — Calendar & World Invariants

## Alcance

Valida **la coherencia temporal del estado real del mundo** en los límites de persistencia (`WorldSeasonRunner.save_json` / `from_dict` / `load_json`). Los guardados de `WorldCareer` quedan cubiertos porque ya validan cada temporada desde TS-08.

Se corrige un defecto del estado anterior: un archivo podía ser deportivo y estructuralmente válido (IDs, resultados, campeones) y, aun así, contener **dos partidos del mismo club el mismo día** o **descansos incompatibles**. Antes de TS-09 ese archivo se aceptaba.

## Reglas verificadas

1. **Conflictos de club**: no se aceptan dos partidos activos del mismo club el mismo día ni una separación entre kickoffs inferior a 48 horas. Se incluyen partidos `SCHEDULED` y `PLAYED`, incluso de competiciones diferentes. Se reutiliza `SeasonCalendar.detect_conflicts` para no duplicar lógica de conflicto.
2. **Partidos inactivos**: un encuentro `POSTPONED` no puede conservar un kickoff vigente. Los partidos aplazados sin nueva fecha y los cancelados no reservan el horario antiguo; `original_kickoff` solo conserva la procedencia.
3. **Ventanas internacionales**: cuando el mundo contiene un `InternationalCalendar`, los encuentros **GENERATED** activos no pueden situarse dentro de una ventana `CLUB_BREAK`. Los eventos `RELEASE_ONLY` no suspenden la liga. Los slots importados con procedencia `OFFICIAL` no se alteran ni se rechazan automáticamente por una ventana genérica, pero sí se someten a las restricciones de conflicto y descanso.
4. **Causalidad de copas y UEFA**: las rondas posteriores tienen que comenzar como mínimo 48 horas después del último kickoff de la ronda anterior. Se comprueba también la transición de la fase inicial hacia el knockout y que la vuelta de una eliminatoria no preceda a la ida.

Los mensajes de error incluyen el club, IDs de fixtures o competición involucrados para facilitar el diagnóstico. **No se mueve ningún partido** durante la validación.

## Decisiones de ingeniería

- Validación **read-only** en un módulo propio: `src/football_manager/domain/calendar_invariants.py`.
- No añade comprobaciones globales después de cada resultado de `advance_until()`, para conservar el rendimiento conseguido en TS-05.
- No altera reglas de competición, algoritmos de simulación, fixtures publicados, UI ni formato de guardado (schema 3).
- Un guardado previo con conflictos reales **se rechazará** en lugar de recuperarse silenciosamente con errores; habrá que diagnosticarlo y repararlo, sin modificar resultados a ciegas.
- La distancia de 48 horas es entre **horarios de inicio**, como la política actual del scheduler, no un cálculo de recuperación fisiológica tras el pitido final.

## Fuera de alcance conocido

Los `CalendarBlock` sintéticos del diagnóstico de estrés no se almacenan como reglas en `WorldSeasonRunner`; por tanto, no pueden validarse al recuperar un archivo de mundo. La validación estricta sí aplica a las ventanas obligatorias cuando se serializan dentro del `InternationalCalendar`. La cobertura estadística multitemporada y los excepcionales cambios reglamentarios se revisarán en etapas posteriores. No se implementa en TS-09 un gestor de excepciones oficiales configurable por torneo.

## Pruebas

Tests nuevos: `tests/test_ts_09_calendar_world_invariants.py`.

```powershell
python -m pytest -ra tests/test_ts_09_calendar_world_invariants.py tests/test_ts_08_score_persistence_contracts.py tests/test_ts_02_calendar_scheduling.py tests/test_tc_e1_international_calendar.py
python -m pytest -ra
```

`-ra` muestra el recuento final con el `pyproject.toml` actual (`-q` se aplica solo una vez). No requiere Node.js en Windows.

Prueba manual opcional: avanzar en una carrera de desarrollo, jugar un partido propio, comprobar que el calendario y las tablas coinciden y que la simulación no ha cambiado. El guardado integral de la sesión del entrenador sigue pendiente de TS-14/TS-15.

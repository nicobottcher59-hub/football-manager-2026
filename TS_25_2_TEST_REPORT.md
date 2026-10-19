# TS-25.2 — Informe de validación

## Evidencia ejecutada

- Suite integrada previa a los últimos ajustes de noticias/UX:
  `tests/test_ts_25_manager_inbox.py`, `tests/test_ts_25_2_manager_interactions.py`,
  `tests/test_ts_20_dressing_room.py` y `tests/test_ts_24_12_integral.py`,
  86 tests aprobados (exit code 0).
- Batería específica TS-25.2: 10 pruebas aprobadas en la última repetición
  completa (`tests/test_ts_25_2_manager_interactions.py`). Verifican promesas
  con evidencia real, negativas, expiración de pedidos, efecto moderado de
  moral y la no cancelación de pedidos por charlas ajenas.
- Sintaxis Python y JavaScript: completadas sin errores (compileall y node --check).
- Manifiesto SHA-256 y aplicación limpia del ZIP: verificación final al empaquetar.

## Compatibilidad y alcance

- Estado serializado permanece en formato v17. La estructura persistida de
  `ManagerInbox`, `ManagerRelation`, `InboxMessage` y `ManagerPromise` no cambió.
- Los tipos nuevos de promesas y temas son compatibles con datos previos.
- No se alteraron finanzas, engine deportivo, inteligencia de fichajes ni retiros.
- Las noticias de mercados, préstamos y cantera se basan en movimientos
  registrados; no se generan convocatorias nacionales inexistentes.

## Pendiente de validación manual

- Render visual y navegación en GitHub Desktop/Windows con partida real.
- Prueba de estrés de 20 temporadas con TS-25.2 (no ejecutada).
- Evaluación subjetiva de la frecuencia de mensajes en partidas humanas.

# TS-25.1 - Informe de validacion

## Pruebas ejecutadas

- Verificacion Python compileall del backend.
- Verificacion JavaScript node --check de la UI modificada.
- Regression integrada: tests/test_ts_25_manager_inbox.py, tests/test_ts_20_dressing_room.py y tests/test_ts_24_13_world_balance.py. Ejecucion final: 74 pruebas completas aprobadas, ninguna omitida (exit code 0). La prueba de ojeador usa un scout controlado en el mundo de prueba cuando la partida inicial no tiene ninguno contratado.
- Guardado SQLite real: conversaciones, estado de confianza, mensajes y promesas conservados tras recargar.
- Compatibilidad: grafo v16 producido con TS-24.13 -> restaurado con TS-25.1 -> validado y recapturado como v17.
- HTTP local real: GET /api/inbox, POST de charla y marcar leido, recursos de la UI servidos, host no autorizado rechazado.
- Progresion real de un dia con resultado de partido confirmado y aviso correspondiente.
- El flujo historico de TS-24.13 se mantiene; TS-25.1 no modifica las reglas financieras, las habilidades del partido ni la autonomia de retiro.

## Alcance de la validacion

La bateria integrada final termino con exit code 0. No se ha ejecutado una prueba de stress completa de 20 temporadas de TS-25.1. Tampoco se ha realizado una validacion manual de renderizado en Windows. Son validaciones pendientes, no aprobaciones asumidas.

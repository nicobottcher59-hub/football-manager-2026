# TS-FIX-04 — Calendario, temporada e identidad

**Base requerida:** TS-UI-08.03 → TS-FIX-01 → TS-FIX-02 → TS-UI-08.04 → TS-FIX-03, sin cambios posteriores no integrados.

**Entrega:** 23 archivos modificados y 2 nuevos en el código (más informe, instrucciones y manifiesto).

## Implementación

1. **Fecha de arranque:** nuevas carreras y comienzo de próximas temporadas el **1 de julio** de su año inicial, en lugar de empezar en el día del primer partido. No altera fechas ya guardadas. Calendario real del mundo mantiene comienzo de encuentros oficiales más tarde.
2. **Calendar al mes actual:** al abrir, el navegador restablece el mes visible al que corresponde la fecha interna de la carrera; resalta la fecha; después de simular actualiza automáticamente el mes.
3. **Auto-simulación sin interrupciones:** avanza hasta la fecha pedida, incluso con ofertas pendientes; nunca acepta ofertas ni vende jugadores sin consentimiento. Ofertas ignoradas pueden vencer.
4. **Ventanas profesionales:** permite negociar y acordar contratos fuera de ventana; un acuerdo firmado queda `pending_window`. Conserva vendedor, plantilla y efectivo hasta la siguiente apertura; registra y cobra solo cuando corresponde. Comprueba de nuevo presupuesto, contrato y condiciones antes del registro, y ante impedimentos marca el acuerdo como fallido en lugar de mover activos incorrectamente.
5. **Ventanas configurables:** nuevo `services/transfer_windows.py` con ventanas por país. **Solo Inglaterra** cuenta con fechas parametrizadas por ahora: 1–31 enero y 1 julio–31 agosto. Los demás países usan temporalmente la misma regla predeterminada; no es un calendario mundial por ligas validado.
6. **Interfaz:** Calendar marca apertura/cierre del mercado y muestra los mensajes de simulación delegada; Transfers presenta condiciones de llegada pendiente y próxima apertura. La pantalla de resultados usa IDs canónicos para mostrar nombre, escudo y colores de competición mediante los componentes compartidos. Club Info presenta la identidad institucional y el escudo de la BD visual, sin modificar finanzas o resultados vivos.
7. **Historia:** transferencias nuevas se muestran con fecha real de inscripción; registros históricos antiguos conservan los datos almacenados. 
8. **Guardado:** versión gráfica de partidas **28 → 29** para persistir acuerdos diferidos; carga de versión 28 verificada. La compatibilidad es hacia adelante; para volver al código anterior debe restaurarse una copia de la partida también.

## Comprobaciones verificadas

- **16 pruebas nuevas aprobadas:** `PYTHONPATH=src pytest -q tests/test_ts_fix_04_calendar_windows.py` — resultado `16 passed`.
- **Sintaxis Python:** `python -m compileall -q src/football_manager`, correcto.
- **Sintaxis JavaScript:** `node --check` de Calendar, Simulation, History y Transfers, correcto.
- **Pruebas aisladas de regresión de mercado/Scouting/contratos:** siete de ocho casos iniciales aprobados. El octavo era un test histórico que exigía una línea salarial anterior incluso cuando un contrato se renueva el mismo día del nuevo comienzo de carrera (1 de julio); ese supuesto quedó desactualizado. El test se ajustó para renovarse al día siguiente y verificó el historial correctamente en su ejecución individual.
- **Pruebas legacy de pausa automática y versiones de guardado:** se actualizaron a la nueva regla de Calendar y versión 29. Los casos de la tanda mostraron resultados de aprobación, pero la ejecución combinada no finalizó dentro del límite de tiempo de este entorno. No se cuenta como batería completada.
- **Prueba real de progreso:** sesión nueva avanzó del 1 al 25 de julio sin pausas. El intento de simular hasta septiembre no concluyó en el tiempo disponible.
- **Incorporación diferida real comprobada:** acuerdo firmado en octubre, club y dinero inalterados durante noviembre/diciembre, registro y liquidación en enero; comprobación de saldo insuficiente y persistencia mediante guardado/recarga.

## Limitaciones no verificadas

- No se completó una temporada de extremo a extremo ni una prueba integral de navegador contra el juego real. Tampoco se validó la partida privada del usuario.
- No se cargaron ventanas específicas de países distintos de Inglaterra ni reglas adicionales para préstamos (TS-FIX-06).
- Una oferta ignorada durante Calendar puede expirar, por decisión funcional del usuario; nunca se acepta ni se vende automáticamente.
- El sistema no reescribe temporadas ya disputadas ni recalcula resultados históricos.
- Las baterías históricas que dependen del comienzo posterior a julio o de detenerse ante ofertas requieren actualizar sus expectativas; no se declaran aprobadas globalmente.

## Archivos del código que cambia este parche

- `MOD frontend/portable/calendar.css`
- `MOD frontend/portable/calendar.js`
- `MOD frontend/portable/history.css`
- `MOD frontend/portable/history.js`
- `MOD frontend/portable/simulation.css`
- `MOD frontend/portable/simulation.js`
- `MOD frontend/portable/transfers.js`
- `MOD src/football_manager/dev_ui/session.py`
- `MOD src/football_manager/domain/transfer_negotiation.py`
- `MOD src/football_manager/persistence/session_codec.py`
- `MOD src/football_manager/services/ai_transfer_market.py`
- `MOD src/football_manager/services/loan_market.py`
- `MOD src/football_manager/services/manager_inbox.py`
- `MOD src/football_manager/services/player_aging.py`
- `MOD src/football_manager/services/transfer_installments.py`
- `MOD src/football_manager/services/transfer_market_activity.py`
- `MOD src/football_manager/services/transfer_negotiation.py`
- `MOD src/football_manager/services/transfer_personal.py`
- `NEW src/football_manager/services/transfer_windows.py`
- `MOD src/football_manager/ui_shell/calendar.py`
- `MOD src/football_manager/ui_shell/career_history.py`
- `MOD src/football_manager/ui_shell/progression.py`
- `MOD tests/test_ts_fix_02_market_negotiation.py`
- `MOD tests/test_ts_fix_03_contract_negotiations.py`
- `NEW tests/test_ts_fix_04_calendar_windows.py`

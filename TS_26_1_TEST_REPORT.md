# TS-26.1 — Informe de pruebas

**Base:** TS-26 ya implementado. Esta ampliación agrega ojeadores profesionales sin activar las restricciones futuras de conocimiento de TS-27.

## Verificaciones realizadas

- Nuevas pruebas de ojeadores (`tests/test_ts_26_1_professional_scouts.py`): **12/12 aprobadas en tandas** (la ejecucion conjunta supera el tiempo limite del entorno): contratación, capacidad simultánea, calidad y velocidad, progresión, informes basados en datos reales, notificaciones, despidos y reasignaciones, cooldown de nuevos informes, guardado y carga de grafo v19, migración simulada desde v18, comandos atómicos y API HTTP.
- La regresión existente de TS-26 (`tests/test_ts_26_club_support.py`): **9/9 aprobadas**. No requirió cambiar la lógica previa.
- Pruebas de conversaciones de TS-25.2 (`tests/test_ts_25_2_manager_interactions.py`): **10/10 aprobadas**; también se aprobaron dos casos dirigidos de TS-25.1.
- Migración **real**: se generó un archivo SQLite usando el código TS-26 (sección/estado v18); se cargó con TS-26.1 (v19), se comprobó la nueva capacidad de ojeadores y se validó la carrera.
- Simulación con motor real desde 21/08/2026 hasta 06/09/2026: se completó un informe, continuaron los partidos y pasó `validate_manager_session`.
- Rutas HTTP GET `/api/staff`, GET `/api/scouting`, GET `/api/transfers` y POST `/api/scouting` comprobadas.
- Sintaxis JS con `node --check` y compilación Python verificadas.

## Pendiente

- Validación visual final en Windows.
- Batería completa de regresión histórica: varias pruebas antiguas conservan aserciones literales de la versión de guardado v17, anteriores incluso a TS-26 (v18). Esas aserciones requieren mantenimiento independiente; no significan por sí mismas una regresión funcional del juego.
- Simulación continua de 20 temporadas y balance fino del mercado de personal.

**Instalación:** aplicar únicamente sobre TS-26, copiando/mezclando el contenido del ZIP en la raíz del juego y aceptando sobrescrituras. No borrar archivos.

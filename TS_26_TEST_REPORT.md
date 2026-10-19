# TS-26 - Informe de integracion y pruebas

**Base:** TS-25.2 del ZIP aportado; no se ha modificado el archivo de origen. Esta entrega conserva los archivos existentes y agrega la funcionalidad TS-26.

## Pruebas verificadas

1. `PYTHONPATH=src python -m pytest -q tests/test_ts_26_club_support.py`: **9/9 aprobadas**.
2. Cobertura TS-26: departamentos para todos los clubes, contratacion/liberacion y capacidad, proteccion de entrenamientos, tratamiento conservador, tratamiento agresivo y recaida forzada, persistencia de tratamiento, salarios mensuales, autorrenovacion de la IA y migracion simulada de v17.
3. `PYTHONPATH=src python -m pytest -q tests/test_ts_25_manager_inbox.py::test_save_load_keeps_chat_messages_promise_and_relationship`: **aprobada** tras actualizar la asercion de version que indicaba literalmente 17.
4. `simulate_until` desde **2026-08-21 hasta 2026-09-03**: **3 partidos propios + 141 de otros clubes**, cierre de agosto, revision de desarrollo y finances; `registry.validate()` y `validate_manager_session()` correctos.
5. Verificaciones de servidor HTTP local: GET Staff/Training/Medical y POST contratar/configurar: HTTP 200 y respuestas validas.
6. Sintaxis Python y JavaScript verificada previamente para los archivos incorporados; la suite TS-26 es verde.

## Pendiente

- Una suite de regresion completa del proyecto. Los tests anteriores incluyen casos largos; una ejecucion conjunta no finalizo dentro del limite de este entorno.
- Validacion visual/jugable en Windows y comportamiento de UI frente a multiples navegaciones.
- Simulacion de 20 temporadas, con especial atencion a transicion de la temporada 18 a la 19, que ya era un riesgo conocido desde TS-24.13.

## Comandos de verificacion

```bash
PYTHONPATH=src python -m pytest -q tests/test_ts_26_club_support.py
PYTHONPATH=src python -m pytest -q tests/test_ts_25_manager_inbox.py
node --check frontend/portable/club_support.js
node --check frontend/portable/portable.js
python -m compileall -q src/football_manager
```

**Estado:** primera version funcional de TS-26 implementada y validada parcialmente. No representa una certificacion integral de estabilidad ni una aprobacion visual de Windows.

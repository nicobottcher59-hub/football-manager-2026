# TS-UI-09.01 — Unificación de modalidades y cesiones sin veto de edad

**Fecha:** 23 de octubre de 2026  
**Base requerida:** TS-UI-09 (instalado sobre TS-FIX-06)  
**Tipo:** parche incremental; solo archivos modificados y nuevos  
**Formato del guardado:** 30 → 31

## Resumen técnico

- `Transfer` y `Loan` operan ahora **dentro de la misma pantalla de negociación**, sin cambiar de ruta ni abrir el módulo histórico de préstamos. Se conservan retrato, ambos clubes, escudos, colores dinámicos, presupuesto, estructura en dos columnas y panel conversacional.
- El constructor presenta campos distintos por modalidad: compra definitiva (pago inicial, cuotas, bonus y cláusulas) o cesión (duración, porcentaje de salario, minutos, repesca y opción de compra con su propio paquete económico).
- Cada modalidad conserva el borrador de sus controles; la transición manual no acepta ni liquida una operación de manera implícita.
- La IA puede responder a una **solicitud de cesión con una contraoferta de venta definitiva**, y también puede responder a una oferta de compra con una **propuesta alternativa de préstamo**, cuando la situación real de plantilla, contrato y finanzas lo justifica. Las nuevas propuestas quedan en el estado del juego; no son mensajes decorativos.
- Las propuestas de distinta modalidad se vinculan entre sí por ID, conservando **historial y tolerancia/paciencia**; el jugador no cambia de club ni se descuenta dinero hasta que se formalice el acuerdo correspondiente.
- Se eliminó el filtro superior de edad en las cesiones de IA a IA. La elegibilidad individual tampoco fija límite de edad. La IA conserva evaluaciones deportivas y económicas: rol, demanda de minutos, salario y profundidad de plantilla.
- La lista inicial de jugadores disponibles para préstamos ahora toma una muestra **por edades**, evitando que los primeros 250 registros sean únicamente juveniles y oculten profesionales de 27, 30 o más años. La edad sigue afectando contexto, pero no veta las cesiones.
- El codec de guardado integra los nuevos vínculos entre conversaciones y una migración específica para partidas creadas con versión 30 o inferior.

## Comprobaciones realizadas

| Comprobación | Resultado |
|---|---|
| 8 pruebas nuevas en `test_ts_ui_09_01_unified_negotiations.py` | 8 aprobadas |
| 5 comprobaciones de TS-UI-09 compatibles con el nuevo flujo | 5 aprobadas |
| Total de pruebas seleccionadas | **13 aprobadas** |
| Transfer → Loan → Transfer sin navegación | Aprobada en Chromium |
| Cabecera, nombre de jugador y estructura compartida | Sin cambios al alternar |
| Escritorio (1672 px), tableta (1024 px), móvil (390 px) | Sin desbordamientos horizontales |
| Errores de JavaScript durante el recorrido visual | 0 |
| `node --check` de ambos scripts de negociación | Aprobado |
| Compilación Python de los módulos modificados | Aprobada |
| Migración del nuevo esquema con un grafo aislado v30→v31 | Aprobada |
| Aplicación del ZIP sobre la base TS-UI-09 y comprobación SHA-256 | Aprobada |

### Limitaciones de la verificación

La prueba visual usó el código de la interfaz en Chromium con respuestas simuladas y datos reales recortados de la API; no reproduce una navegación nativa completa contra el servidor desde el equipo del usuario. No se ejecutó una temporada completa ni se cargó una partida personal. La prueba extensa de serialización sobre un mundo completo excedió el tiempo disponible; se sustituyó por la comprobación puntual de migración de los objetos de negociación. Por lo tanto, **la continuidad de una partida concreta debe probarse sobre una copia de seguridad**. Las dos pruebas de expectativas antiguas de versión/visualización se actualizaron para reflejar el esquema 31 y la nueva interfaz.

## Archivos incluidos

- `frontend/portable/transfers.js`
- `frontend/portable/transfers.css`
- `frontend/portable/loan_negotiations.js`
- `src/football_manager/domain/loan_negotiation.py`
- `src/football_manager/domain/transfer_negotiation.py`
- `src/football_manager/services/loan_bargaining.py`
- `src/football_manager/services/loan_market.py`
- `src/football_manager/services/transfer_negotiation.py`
- `src/football_manager/persistence/session_codec.py`
- `tests/test_ts_ui_09_transfer_centre.py`
- `tests/test_ts_ui_09_01_unified_negotiations.py`

## Instalación

1. Trabajá sobre **TS-UI-09**, sin saltear TS-FIX-06.
2. Cerrá el juego y detené Python. Hacé respaldo **del proyecto y de la partida**.
3. Descomprimí este ZIP directamente en la raíz de `football-manager-2026`, manteniendo las carpetas y aceptando reemplazar archivos.
4. Reiniciá el juego y forzá actualización del navegador con `Ctrl + F5`.
5. Probá una negociación de compra, cambiá a préstamo y regresá a compra; verificá que no cambie de pantalla. Después probá una cesión de un jugador de al menos 27 años.

**Reversión:** una vez guardada la partida en formato 31, la versión anterior (30) no podrá cargarla. Para retroceder, restaurá tanto el código anterior como la partida respaldada.

## GitHub Desktop

**Branch nueva:** `feat/ts-ui-09-01-unified-negotiations`  
**Summary:** `feat(transfers,loans): TS-UI-09.01 unified negotiation modes and veteran loans`

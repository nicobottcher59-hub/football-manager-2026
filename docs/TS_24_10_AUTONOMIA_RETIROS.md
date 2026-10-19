# TS-24.10 — Autonomía de retiro y diagnóstico financiero

**Base:** TS-24.9. **Guardado:** SQLite v16; sin migración de campos.

## Decisión de diseño confirmada

El jugador decide terminar su carrera, independientemente de la situación deportiva del club. `PlayerAging.retirement_age` es individual (edad de declive, profesionalismo, capacidad física y exposición deportiva); `requested` significa decisión tomada, no autorización pendiente de la directiva. El motor formaliza la salida en la siguiente transición anual.

- `finalize_season_retirements()` ya no consulta la cobertura de titulares, suplentes, centrales ni porteros; tampoco pospone por lesión, presupuesto o préstamo.
- `deferred` en un guardado antiguo sigue siendo una decisión de retiro y se cumple en la siguiente transición. No se escriben nuevos estados `deferred` para proteger planteles.
- Un jugador cedido que se retira finaliza el préstamo (`LoanAgreement.status='retired'`), con fecha de cierre, sin regresar artificialmente a otro club. Se mantiene su historial y se liberan contratos y seguimiento médico.
- El futbolista con una decisión de retiro confirmada rechaza renovaciones y nuevas negociaciones de transferencias/préstamos. La IA del club puede intentar anticipar un reemplazo mediante scouting, fichajes o cantera, pero no vetar la salida.
- Se corrige el criterio de agentes libres: la edad o el tiempo sin club ya no provocan automáticamente el retiro. Antes se actualiza su progresión y se verifica su decisión individual; no se inventan partidos.

## Gestión económica sin perfeccionismo

`financial_outlook()` es un diagnóstico de liquidez: diferencia resultados mensuales desfavorables, proyección de seis meses, caja negativa persistente y riesgo severo. Es de solo lectura y se expone dentro de `/api/finances` bajo `financial_outlook`. **No fija un número máximo de equipos con pérdidas, no inyecta dinero, no borra obligaciones y no convierte la pérdida en fallo de integridad.** Las restricciones de gasto y renovación ya existentes se mantienen.

## Limitaciones

- El simulador completo todavía necesita un once válido para disputar partidos. Si retiradas múltiples dejan a un equipo con menos de once futbolistas o ningún arquero, la etapa de emergencia deportiva/derrota administrativa aún requiere implementación. Este parche **no retrasa el retiro** para ocultar el problema.
- Las nuevas políticas evitan aplazamientos ilimitados por plantilla, pero **no se ejecutó una auditoría de 20 temporadas con esta versión**.
- La auditoría de cinco temporadas usa el marcador acelerado de fondo para partidos senior, sin minutos ni lesiones de esos encuentros. No es equivalente a cinco temporadas completas del motor de partidos.
- No se implementa negociación autónoma entre clubes IA para préstamos ni una IA de personalidad deportiva completa por club; siguen siendo mejoras futuras.
- Las pruebas históricas antiguas que exigían impedir retiros sin cobertura se actualizaron al nuevo contrato de comportamiento. Esto no significa que toda la suite histórica haya pasado.

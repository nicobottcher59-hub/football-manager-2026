# TS-24.12 — Auditoría integral del modo carrera

**Semilla:** 6606 · **Escenario:** 92 clubes profesionales ingleses
**Estado de evidencia:** failed · **Temporadas completadas:** 18

## Resultados de checkpoints

| Temporadas | Clubes | XI vacantes | Suplentes vacantes | Clubes con menos de 2 GK | Caja negativa | Caja mínima | Edad máxima | Préstamos activos |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 92 | 0 | 11 | 0 | 10 | GBP -206.61m | 40 | 25 |
| 10 | 92 | 0 | 14 | 2 | 10 | GBP -193.31m | 41 | 23 |
| 18 | 92 | 6 | 41 | 33 | 8 | GBP -94.70m | 40 | 26 |
| 20 | Sin completar | — | — | — | — | — | — | — |

## Alertas durante el recorrido

- Mayor carencia simultánea de segundo arquero: **33 clubes** en el año 18.
- Mayor cantidad de posiciones titulares sin cubrir: **6** en el año 18.
- Peor caja individual observada: **GBP -235.55m** en el año 8.
- Futbolistas de al menos 50 años registrados al cierre: **0 cierres**.

Un déficit de porteros extendido es un riesgo sistémico de planificación, no una justificación para retener retirados ni inventar suplentes.

## Clasificación de resultados

- **Fallo técnico:** identidades duplicadas, cuentas inconsistentes, campeonatos inconclusos, edades absurdas de al menos 50 años o excepción del motor.
- **Riesgo deportivo:** once imposible de cubrir, pocos futbolistas, numerosas carencias de arquero. No se inventan jugadores para ocultarlo.
- **Riesgo financiero:** déficits elevados y persistentes. No se eliminan por imponer cuotas de rentabilidad ni regalando dinero.
- **Advertencia normal:** un club ocasionalmente deficitario o sin todos sus suplentes puede ser una consecuencia legítima de la gestión.

**Incidencias técnicas identificadas:** 1 (incluye la excepción posterior al año 18, si la hubo). 
**Incidencias deportivas por cierre:** 6 cierres. 
**Clubes con una racha de caja negativa de al menos 5 años:** 13.

## Intervenciones del entrenador ficticio

- **Promociones realizadas:** 38; son movimientos reales desde la academia del club del usuario.
- Todas las decisiones se ejecutan mediante `youth_command`; no hay jugadores fabricados ni control automático de los otros clubes.
- El escenario completamente desatendido puede interrumpirse cuando el equipo humano necesita reconstruirse tras retiros.

## Qué NO certifica esta prueba

- Los partidos senior se resuelven mediante el marcador acelerado existente; no genera evidencia de minutos o desarrollo por partido.
- No sustituye una prueba completa en Windows, ni pruebas manuales de toda la interfaz.
- La muestra de partidos reales se guarda en un reporte separado y no extrapola a veinte temporadas.
- Una sola semilla de veinte años no demuestra que todos los mundos hipotéticos mantengan el mismo balance.

## Otras semillas (cinco temporadas)

| Semilla | Estado | Titulares vacantes | Suplentes vacantes | Clubes con menos de 2 GK | Caja negativa |
|---:|---|---:|---:|---:|---:|
| 6606 | cinco temporadas completas (ejecucion larga interrumpida) | 0 | 11 | 0 | 10 |
| 7707 | completed | 0 | 10 | 0 | 9 |
| 8808 | completed | 0 | 8 | 0 | 9 |

**Muestra de partidos senior detallados:** 
18 partidos, 3006 minutos reales para sub-23 en 15 encuentros.

## Error de integración confirmado

**Ejecución original:** se detuvo tras 18 temporadas, al intentar iniciar la temporada 19.
**Excepción:** `ValueError: Hillcrest Athletic has no valid lineup`.
El fallo fue causado por la preparación del rival del equipo humano sin una alineación válida.
TS-24.12 incorpora una corrección focalizada: cuando la IA no puede presentar un once elegible, el enfrentamiento protegido se registra como resultado administrativo sin simular minutos ni inventar jugadores.
**La auditoría de veinte temporadas con esta corrección NO se volvió a ejecutar hasta el final:** no está certificada.

## Comprobación posterior a la corrección

Prueba focalizada sobre un mundo nuevo: passed.
El partido dev-premier-2026-27-league-r01-m001 quedó con resolutor `administrative` y marcador 3-0.
Todas las comprobaciones de no fabricar jugadores, no asignar minutos y mantener el esquema SQLite v16 resultaron aprobadas.
**Esta prueba focalizada no reemplaza una repetición integral de veinte años.**

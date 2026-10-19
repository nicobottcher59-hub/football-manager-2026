# TS-24.12 — Informe de pruebas y estado de entrega

**Base:** TS-24.11 · **Persistencia:** SQLite v16, sin migración · **Plataforma probada:** Linux/Python 3.13.

## Resultado real

**Validación integral de 20 años: NO aprobada.** El escenario de la semilla 6606 completó **18 temporadas** (hasta 2043/44); al abrir 2044/45, falló porque un rival de la IA no tenía once válido (`Hillcrest Athletic has no valid lineup`).

Tras ese fallo se aplicó una corrección al flujo de preparación de encuentros controlados: cuando el oponente de la IA no dispone de once elegible, el partido queda resuelto administrativamente y el calendario avanza. Ningún jugador se fabrica, no se concede tiempo de juego y el futbolista que se retira no es retenido. La situación del club dirigido por el usuario continúa requiriendo decisiones del entrenador. **No se ha repetido una auditoría completa de veinte años después de este cambio**, por lo que el resultado completo sigue sin certificarse.

## Pruebas verificadas

| Alcance | Resultado | Observación |
|---|---|---|
| 11 tests de `test_ts_24_12_integral.py` sobre el código corregido | **11/11 aprobados** | Incluyen tres pruebas nuevas de incomparecencia IA, responsabilidad del usuario y errores inesperados. |
| Smoke post-corrección: `tools/smoke_ts2412_forfeit.py` | **Aprobado** | Resolutor administrativo, 3-0, sin jugadores/minutos artificiales, siguiente encuentro disponible, esquema v16 intacto. |
| Regresiones anteriores de mercado/contratos/préstamos/retiros/auditor | **104 casos distintos aprobados antes de la corrección final** | Fueron ejecutados por grupos (72/72 y 39/39, con siete casos compartidos). No se declara repetición integral de los 104 sobre el cambio final. |
| Tres semillas, 5 temporadas (6606, 7707, 8808) | **Tres checkpoints de cinco años completos** | Ninguno presentó huecos titulares ni incidencias estructurales en el quinto cierre. |
| Auditoría acelerada 10 temporadas | **Checkpoint completado** | 92 clubes; cero huecos titulares; dos clubes con menos de dos arqueros. |
| Auditoría acelerada 18 temporadas | **Checkpoint completado** | 92 clubes; seis vacantes titulares y 33 clubes con menos de dos arqueros. |
| Objetivo de 20 temporadas | **No completado** | Fallo en la transición al año 19 antes del parche. Revalidación integral pendiente. |
| Partidos detallados | **18/18 terminados** | 3.006 minutos efectivos de menores de 23 años en 15 encuentros. No representa 20 temporadas detalladas. |
| Suite histórica total | **No aprobada** | Tres módulos antiguos de calibración fallan al importarse también sobre TS-24.11. |
| Windows nativo / inspección visual de toda la interfaz | **No ejecutados** | Se debe comprobar en la instalación del usuario. |

## Hallazgos de realismo a largo plazo

- La falta de un segundo arquero se extendió de **2 clubes al año 10** a **33 clubes al año 18**. Hay una tendencia sistémica de planificación que exige abordar la cobertura de posiciones, **no** bloquear el retiro de futbolistas.
- En el cierre 18 se observaron **6 puestos titulares sin cubrir** y **41 huecos de suplentes**. Son riesgos deportivos que un resultado acelerado por marcador no comprueba partido a partido.
- Se observó un peor saldo de caja aproximado de **-GBP 235,55 millones** en el año 8. Una pérdida aislada es admisible; déficits tan profundos ameritan revisar la sostenibilidad financiera y sus consecuencias.
- En los cierres observados no se registraron futbolistas de 50 años o más. No prueba ausencia universal de longevidad absurda.
- El entrenador de prueba ascendió **38 juveniles existentes** del equipo humano durante los 18 años, mediante comandos explícitos; no hubo reemplazos generados artificialmente.

## Limitaciones metodológicas

La auditoría larga utiliza resultados de fondo simplificados para los encuentros senior, sin asignar lesiones, fatiga ni minutos propios del motor detallado. El calendario acelerado no es una prueba de elegibilidad de once completo para cada partido. Los resultados administrativos se verificaron mediante pruebas específicas del motor y de la vista previa de partidos controlados.

**Conclusión:** TS-24.12 entrega herramientas reproducibles, hallazgos concretos y una corrección de continuidad verificada a nivel focalizado. No permite declarar completamente estable ni equilibrada una carrera de veinte temporadas. El cierre definitivo de esta etapa requiere una nueva auditoría de veinte años sobre el parche y tratar la escasez de arqueros a escala de liga.

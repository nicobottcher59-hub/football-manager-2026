# TS-24.8 — Auditoría de balance a largo plazo

**Ejecución:** completed. Temporadas completadas: **20 de 20**.

**Metodología.** Se ejecuta el calendario real de competiciones inglesas generadas, los cambios de
temporada y divisiones, los contratos, mercado de la IA, salarios, caja, retiros y canteras.
Únicamente el resultado de los partidos de los equipos senior usa el resolvedor rápido
de fondo, en vez del simulador táctico detallado. Es una **prueba acelerada del ecosistema**,
no una partida completa de veinte años ni una prueba de minutos de juego.

## Checkpoints

| Métrica | Inicio | 5 años | 10 años | 20 años |
|---|---:|---:|---:|---:|
| Clubes profesionales activos | 92 | 92 | 92 | 92 |
| Jugadores en primeros equipos | 2024 | 2293 | 2308 | 2318 |
| Mínimo jugadores por plantilla | 22 | 21 | 19 | 18 |
| Puestos titulares sin cubrir | 0 | 0 | 0 | 0 |
| Puestos suplentes sin cubrir | 0 | 11 | 13 | 10 |
| Clubes con menos de dos arqueros | 0 | 0 | 0 | 0 |
| Jugadores menores de 23 años | 532 | 231 | 199 | 240 |
| Edad mediana en primer equipo | 25.0 | 28 | 29.0 | 28.0 |
| Clubes con caja negativa | 0 | 11 | 11 | 7 |
| Caja mediana por club | £1,644,772 | £6,580,610 | £12,183,434 | £31,847,032 |
| Nómina salarial semanal mediana | £45,338 | £56,225 | £55,425 | £40,712 |
| Valor de mercado mediano | £520,000 | £280,000 | £190,000 | £120,000 |
| Transferencias completadas acumuladas | 0 | 277 | 697 | 1453 |
| Retirados acumulados | 0 | 154 | 763 | 2692 |
| Agentes libres | 0 | 85 | 198 | 231 |
| Préstamos vigentes | 0 | 0 | 0 | 0 |
| Mayores de 45 años activos | 0 | 0 | 0 | 9 |

## Interpretación y alertas

- **Continuidad:** se procesaron todas las temporadas solicitadas.
- **Cobertura/integridad:** ninguna incidencia dura en las temporadas recorridas bajo este método.
- **Caja mediana:** +1836.3% frente al inicio; acumulación de liquidez a vigilar, no prueba automática de inflación.
- **Cotización mediana:** -76.9% frente al inicio. La ausencia de minutos senior en esta prueba puede acelerar la pérdida de desarrollo/rendimiento; no extrapolar sin partidos reales.
- **Canteras:** 3364 promociones registradas al primer equipo; los minutos prometidos y las oportunidades de juego no se midieron.
- **Profundidad: NO EQUILIBRADA.** 10 asignaciones de suplentes no cubiertas, aun con un once completo; requiere fichajes y promociones según la formación.
- **Recambio insuficiente:** los sub-23 en primeros equipos pasaron de 532 a 240; las promociones acumuladas no garantizan minutos ni una pirámide de edades saludable.
- **Veteranos retenidos:** 9 futbolistas superan los 45 años en primer equipo. Una jubilación aplazada conserva cobertura, pero no soluciona el relevo deportivo.
- **Préstamos:** no hay cesiones activas en el escenario de IA, porque los clubes todavía no negocian préstamos autónomamente; no demuestra funcionamiento del mercado de cesiones entre IA.
- **Dificultad económica:** 7 clubes con caja negativa y 0 con nómina superior al presupuesto al cierre del último año; requieren examen financiero antes de recalibrar parámetros.

## Año a año

- **2026/27**: 2959 resultados, 0 huecos titulares, 0 clubes con caja negativa, caja subió en 79 clubes y bajó en 13; sin incidentes duros.
- **2027/28**: 2959 resultados, 0 huecos titulares, 7 clubes con caja negativa, caja subió en 73 clubes y bajó en 17; sin incidentes duros.
- **2028/29**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 72 clubes y bajó en 18; sin incidentes duros.
- **2029/30**: 2959 resultados, 0 huecos titulares, 11 clubes con caja negativa, caja subió en 69 clubes y bajó en 21; sin incidentes duros.
- **2030/31**: 2959 resultados, 0 huecos titulares, 11 clubes con caja negativa, caja subió en 67 clubes y bajó en 23; sin incidentes duros.
- **2031/32**: 2959 resultados, 0 huecos titulares, 11 clubes con caja negativa, caja subió en 66 clubes y bajó en 24; sin incidentes duros.
- **2032/33**: 2959 resultados, 0 huecos titulares, 10 clubes con caja negativa, caja subió en 67 clubes y bajó en 23; sin incidentes duros.
- **2033/34**: 2959 resultados, 0 huecos titulares, 10 clubes con caja negativa, caja subió en 68 clubes y bajó en 22; sin incidentes duros.
- **2034/35**: 2959 resultados, 0 huecos titulares, 11 clubes con caja negativa, caja subió en 67 clubes y bajó en 23; sin incidentes duros.
- **2035/36**: 2959 resultados, 0 huecos titulares, 11 clubes con caja negativa, caja subió en 69 clubes y bajó en 21; sin incidentes duros.
- **2036/37**: 2959 resultados, 0 huecos titulares, 10 clubes con caja negativa, caja subió en 72 clubes y bajó en 18; sin incidentes duros.
- **2037/38**: 2959 resultados, 0 huecos titulares, 10 clubes con caja negativa, caja subió en 72 clubes y bajó en 18; sin incidentes duros.
- **2038/39**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 80 clubes y bajó en 10; sin incidentes duros.
- **2039/40**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 78 clubes y bajó en 12; sin incidentes duros.
- **2040/41**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 80 clubes y bajó en 10; sin incidentes duros.
- **2041/42**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 74 clubes y bajó en 16; sin incidentes duros.
- **2042/43**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 77 clubes y bajó en 13; sin incidentes duros.
- **2043/44**: 2959 resultados, 0 huecos titulares, 9 clubes con caja negativa, caja subió en 76 clubes y bajó en 14; sin incidentes duros.
- **2044/45**: 2959 resultados, 0 huecos titulares, 6 clubes con caja negativa, caja subió en 76 clubes y bajó en 14; sin incidentes duros.
- **2045/46**: 2959 resultados, 0 huecos titulares, 7 clubes con caja negativa, caja subió en 81 clubes y bajó en 9; sin incidentes duros.

## Qué NO demuestra esta auditoría

- Se ejecutan calendarios de competiciones, rondas, ascensos y descensos, cambios anuales de canteras, cierres económicos, renovaciones y mercado de la IA.
- En esta prueba descartable, los partidos senior se resuelven con el marcador de fondo existente en vez del simulador de encuentros completos.
- No se miden apariciones ni minutos senior, lesiones, fatiga, tácticas o desarrollo derivado de partidos: las oportunidades de minutos NO quedan certificadas.
- Solo se utiliza una semilla del mundo ficticio; no es un experimento estadístico multisemilla ni prueba de veinte temporadas interactivas completas.
- No se carga ni se modifica ninguna partida guardada del usuario.
- Las métricas económicas son descriptivas. No se compararon con series históricas validadas de la industria.
- No se ejecutaron varias semillas ni pruebas de rendimiento/compatibilidad nativas en Windows.
- Sin apariciones senior reales, no se puede certificar que las promesas progresen como corresponde.

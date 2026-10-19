# TS-24.9 — Auditoría de múltiples semillas, 5/10/20 años y minutos reales

## Método y precauciones

- **Semillas independientes:** 6606, 7707, 8808; cinco temporadas por mundo, total 15 temporadas-semilla.
- **Extensión separada:** semilla 9909, veinte temporadas aceleradas; es una muestra independiente, no prueba de precisión estadística.
- La auditoría acelerada ejecuta calendarios, economía, contratos, mercados, canteras y ascensos, pero sustituye **solo el partido senior** por un resolutor de marcadores de fondo.
- Por eso la auditoría larga NO representa minutos senior, lesiones, forma ni desarrollo inducido por partidos reales.
- **Partidos reales:** 18 con FastMatchSimulator y estadísticas integradas, separados del experimento de veinte años.

## Variación entre semillas al año 5

| Indicador | Mínimo | Mediana | Máximo |
|---|---:|---:|---:|
| Puestos titulares vacíos | 0 | 0 | 0 |
| Puestos suplentes vacíos | 10 | 10 | 11 |
| Clubes con caja negativa | 9 | 10 | 11 |
| Jugadores sub-23 | 222 | 224 | 249 |
| Jugadores mayores de 45 años | 0 | 0 | 0 |
| Clubes que exceden presupuesto salarial | 0 | 0 | 1 |
| Caja mediana (millones GBP) | £6.33 M | £6.63 M | £7.58 M |
| Valor de mercado mediano (GBP) | £270,000 | £290,000 | £290,000 |

**Incidencias de integridad:** 0 en 15 cortes anuales, según las invariantes de este auditor. No se exige caja positiva a todos los equipos.

## Recorrido de 20 años — semilla 9909

| Indicador | Año 5 | Año 10 | Año 20 |
|---|---:|---:|---:|
| Puestos titulares vacíos | 0 | 0 | 0 |
| Puestos suplentes vacíos | 10 | 16 | 11 |
| Clubes con caja negativa | 10 | 13 | 9 |
| Jugadores sub-23 | 235 | 203 | 247 |
| Jugadores mayores de 45 años | 0 | 0 | 14 |
| Clubes que exceden presupuesto salarial | 0 | 1 | 0 |
| Caja mediana (millones GBP) | £7.30 M | £13.77 M | £40.39 M |
| Valor de mercado mediano (GBP) | £310,000 | £200,000 | £120,000 |

**Incidencias de integridad:** 1 en 20 temporadas, según los chequeos automáticos.
**Estado de integridad del horizonte largo: NO APROBADO.** Detalle: an active first-team footballer is at least 50 years old.

## Minutos de partidos reales — muestra limitada

- Encuentros terminados con motor completo: **18**.
- Minutos sub-23 registrados realmente: **2,517**.
- Encuentros con minutos sub-23: **15**.
- Titularidades juveniles proyectadas antes de revisión: 9; con minutos constatados: 6.
- La última cifra NO es un porcentaje de conversión de convocatorias; una revisión de desarrollo fechada puede alterar la alineación proyectada antes de jugar.
- La muestra no equivale a simular una temporada completa con resultados y desarrollo de cada jugador.

## Comparación controlada con TS-24.8 — misma semilla 6606

| Indicador, año 5 | TS-24.8 | TS-24.9 |
|---|---:|---:|
| Puestos titulares vacíos | 0 | 0 |
| Puestos suplentes vacíos | 11 | 10 |
| Clubes con caja negativa | 11 | 10 |
| Jugadores sub-23 | 231 | 222 |
| Jugadores mayores de 45 años | 0 | 0 |
| Clubes que exceden presupuesto salarial | 1 | 0 |
| Caja mediana (millones GBP) | £6.58 M | £7.58 M |
| Valor de mercado mediano (GBP) | £280,000 | £290,000 |

## Interpretación

- Los problemas de liquidez y profundidades residuales son **riesgos medidos**, no certificados como resueltos por estas pruebas.
- Las carreras a largo plazo pueden presentar déficits reales; el objetivo no es forzar beneficios mediante dinero ficticio.
- Las retiradas y contrataciones mantienen las salvaguardas de once titulares y dos guardametas.
- El control de contratos actúa sobre **renovaciones futuras**; no reduce salarios existentes ni altera partidas anteriores.
- Múltiples semillas con un horizonte corto miden variabilidad inicial; una semilla con 20 años detecta colapsos tardíos. Ambos ensayos se complementan, no se sustituyen.

## Reproducibilidad

```bash
python tools/stress_ts249_multiseed.py --seeds 6606,7707,8808 --seasons 5 --output reports/ts249_multi_seed.json
python tools/stress_ts249_multiseed.py --seeds 9909 --seasons 20 --output reports/ts249_long_horizon.json
python tools/audit_ts249_real_match_minutes.py --matches 18 --output reports/ts249_real_minutes.json
```

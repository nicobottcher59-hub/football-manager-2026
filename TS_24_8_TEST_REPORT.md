# TS-24.8 — Informe técnico y de regresión

**Versión:** TS-24.8 · **Base:** TS-24.7 · **Guardado:** SQLite v16 (sin migración).

## Alcance y cambios implementados

### IA de mercado y profundidad de plantilla

- Planificación de dos onces por formación y guardameta adicional, con familiaridad posicional real y asignación única por futbolista.
- Restricción de ventas autónomas que deterioran la cobertura de suplentes, además del bloqueo anterior de huecos de titulares.
- Agentes libres distribuidos por necesidad de los clubes: no se procesan únicamente por orden alfabético.
- Priorización táctica y presupuestaria en las contrataciones, con preferencia moderada por juventud cuando las alternativas son similares.

### Cantera y recambio deportivo

- Promociones desde U21 según vacantes y posibles retiros, preservando la identidad del jugador y sin fabricar registros.
- Juveniles de 19 y 20 años pueden adelantarse al primer equipo cuando son aptos para la división y su cobertura resulta útil.
- Para los partidos detallados de la IA, rotación juvenil ocasional, reproducible y limitada por calidad/posición. Los minutos resultantes se contabilizan realmente.
- Los clubes humanos conservan el control de la alineación y sus canteras.

### Finanzas

- Ajuste de ingresos recurrentes a categoría y tamaño persistente, eliminando la retroalimentación en la que más contratos caros producían por sí mismos mayores ingresos.
- Costos operativos diferenciados por categoría y nueva revisión del presupuesto salarial según ingresos recurrentes/contratos.
- Sin inyección automática de caja, piso artificial de precios o revaloración universal de futbolistas.

## Auditoría acelerada 5/10/20 temporadas

El test usa calendarios, progresión de temporada, mercado, contratos y economía reales, pero resuelve **marcadores de partidos senior por un motor de fondo ligero**. No valida veinte años de minutos reales, lesiones, tácticas completas ni desarrollo basado en rendimiento.
Solo se ejecutó **una semilla**. Los números son resultados de ese escenario, no intervalos estadísticos.

| Indicador | Año 5 TS-24.7 | Año 5 TS-24.8 | Año 10 TS-24.7 | Año 10 TS-24.8 | Año 20 TS-24.7 | Año 20 TS-24.8 |
|---|---:|---:|---:|---:|---:|---:|
| Clubes profesionales | 92 | 92 | 92 | 92 | 92 | 92 |
| Huecos titulares | 0 | 0 | 0 | 0 | 0 | 0 |
| Huecos de suplentes | 23 | 11 | 45 | 13 | 221 | 10 |
| Sub-23 en primeros equipos | 202 | 231 | 181 | 199 | 154 | 240 |
| Promociones de cantera | 495 | 535 | 1,334 | 1,314 | 3,164 | 3,364 |
| Clubes con caja negativa | 5 | 11 | 3 | 11 | 1 | 7 |
| Caja mediana | £10.66 M | £6.58 M | £22.41 M | £12.18 M | £63.80 M | £31.85 M |
| Valor mediano | £220,000 | £280,000 | £110,000 | £190,000 | £35,000 | £120,000 |
| Transferencias acumuladas | 253 | 277 | 651 | 697 | 1,491 | 1,453 |
| Mayores de 45 años | 0 | 0 | 0 | 0 | 7 | 9 |

### Lectura de resultados

- **Integridad:** 20/20 temporadas completadas, con 0 temporadas que registraron incidencias graves bajo las invariantes de este auditor.
- **Suplentes:** vacantes a 20 años 221 → 10; mejora de 95.5 %, pero no necesariamente cero.
- **Jóvenes:** sub-23 al año 20 154 → 240 frente a 532 al inicio; no es garantía de minutos.
- **Liquidez:** caja mediana año 20 de £63.80 M a £31.85 M; los clubes con caja negativa pasan de 1 a 7. El aumento de déficits es un problema pendiente, no una mejora.
- **Cotización:** mediana al año 20 £35,000 → £120,000 frente a £520,000 al inicio; sigue influida por los minutos no simulados.

## Pruebas realizadas

| Batería | Resultado |
|---|---|
| Nuevos tests TS-24.8 | 9/9 aprobados |
| Regresión mercado/préstamos TS-24.5/TS-24.6 | 24/24 aprobados |
| Regresiones TS-24.7 (separadas por tiempo de ejecución) | 8/8 aprobadas |
| Auditoría acelerada de 5/10/20 temporadas | 20/20 temporadas completadas |
| Suite histórica íntegra | No ejecutada en TS-24.8; en TS-24.7 contenía casos antiguos incompatibles |
| Ejecución nativa Windows | No realizada |

### Pruebas de aceptación importantes

- Resguardo de titulares y reservas antes de una venta automática; se respeta el presupuesto.
- Promoción de juventudes sin duplicar jugadores e intervención humana intacta.
- Rotación U23 en un encuentro simulado de verdad: se comprueba minutos positivos, sin fabricar estadísticas.
- Revisión de ingresos y presupuesto de nómina al cambiar de categoría.
- Regresiones de contratos, mercado, cesiones y continuidad interanual.

## Problemas todavía abiertos

- Al término de 20 años persisten **10 huecos de suplentes**; cobertura total del doble XI no está certificada.
- Existen **7 clubes con caja negativa** tras veinte temporadas y no hay mecanismos de bancarrota ni supervisión financiera suficientemente completos.
- Siguen activos **9 futbolistas mayores de 45 años**, frente a 7 en TS-24.7. Las jubilaciones aplazadas evitan vacantes pero requieren otro mecanismo de sucesión.
- La presencia juvenil en primera plantilla y sus minutos efectivos deben verificarse con partidos senior normales y varias semillas; los dos escenarios no son intercambiables.
- La IA todavía no negocia préstamos autónomos. El sistema de valoraciones no se modificó en este parche.
- Las pruebas de TS-24.7 identificaron tests históricos con fixtures obsoletos de SQLite/contabilidad. La suite histórica global no está certificada por esta actualización.

## Instalación, compatibilidad y Git

1. Tener **TS-24.7** instalada y cerrar el juego.
2. Respaldar el proyecto y la partida SQLite.
3. Descomprimir el parche en la raíz donde está `INICIAR_INTERFAZ_WINDOWS.bat`.
4. Ejecutar `python tools/verify_ts248_balance_package.py` desde la raíz.
5. Reiniciar el juego y actualizar el navegador con `Ctrl + F5`.

**Guardado:** grafo v16; no requiere conversión. Los datos históricos no se reescriben.

```text
BRANCH
feat/ts-24-8-structural-squad-economy-balance

SUMMARY
feat(career): rebalance AI squad depth, youth succession and club finances
```

## Próxima fase recomendada

TS-24.9: ejecutar múltiples semillas y una auditoría reducida pero real de partidos completos; calibrar déficits financieros, profundidad de banquillo y desarrollo de promesas con datos de minutos verificados.


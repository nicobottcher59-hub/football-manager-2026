# TS-24.7 — Balance de largo plazo, estabilidad del mercado y recambio

## Objetivo

Auditar la persistencia de un ecosistema de 92 clubes durante 5, 10 y 20 temporadas, registrando la cobertura de posiciones, la estructura de plantillas, la economía, el mercado y el reemplazo generacional. La prueba utiliza una semilla ficticia reproducible. **No reemplaza un recorrido de veinte temporadas con el simulador táctico completo.**

## Origen del proyecto y alcance

- Base: archivo completo TS-24.6 aportado por el usuario; actualización incremental, no instalación independiente.
- Se conserva la estructura y la interfaz de TS-24.6.
- El grafo de guardado SQLite sigue en **versión 16**, sin migración adicional.
- Los scripts de auditoría no cargan ni modifican la partida real del usuario.

## Correcciones de juego

| Área | Antes | Ahora |
|---|---|---|
| Transición de divisiones | Al promocionar dos clubes de National League, la revisión económica podía ejecutarse sin sus cuentas e interrumpirse con `KeyError`. | Se cierra primero el estado económico y de desarrollo de los clubes existentes; los nuevos clubes ingresan después con presupuesto, identidad y contratos propios. |
| Agentes libres y reloj mensual | Tras muchos meses sin club, un fichaje podía tener revisiones de desarrollo atrasadas y romper la cronología global. | Se procesan cronológicamente los meses de inactividad sin adjudicar minutos de partido ficticios y sin superar la última revisión global liquidada. Se conserva el rollback transaccional para firmas de la IA. |
| Retiro de veteranos | Un jugador elegible para retirarse podía dejar un puesto titular sin cobertura suficiente en el plan táctico. | Se compara la cobertura real del plan antes y después de la salida, tanto en la formación titular como en la alternativa; se aplaza la baja si empeora la cobertura. |
| Cantera y recambio | Los clubes de la IA con una plantilla de aproximadamente 24 jugadores podían liberar todas las promociones U21 aunque su primer equipo envejeciera. | Se permite el ascenso de juveniles sub-23 hasta una referencia de cuatro por club **cuando hay candidatos aptos y espacio**, con un máximo de 29 profesionales en estos casos. La decisión del equipo humano sigue siendo manual. |

No se han añadido ventajas artificiales de caja ni se alteraron las fórmulas generales de salarios o valoraciones. Las alertas de economía deben calibrarse con evidencia de partidos normales antes de cambiar parámetros.

## Cómo funciona la auditoría

Se ejecutan los calendarios y resultados de las competiciones inglesas generadas, promociones/descensos, revisiones mensuales de contratos, caja, traspasos y academia. En **el script de estrés exclusivamente**, el cálculo detallado de los partidos senior se sustituye por el marcador rápido que ya existía. Este cambio no afecta al juego instalado. Cada temporada produce un snapshot de auditoría en JSON, validado e independiente de las partidas guardadas.

Las alertas estructurales incluyen: diferencia respecto de 92 clubes activos; huecos titulares; clubes con menos de dos arqueros; plantillas de menos de 18; jugadores de 50 años o más en el primer equipo; IDs duplicados; presupuestos de traspaso superiores a la caja; y cuentas financieras no sincronizadas.

## Comprobaciones y resultados

Los datos exactos por temporada, indicadores iniciales y checkpoints están en `TS_24_7_LONG_HORIZON_REPORT.md` y `reports/ts247_long_horizon.json`, generados desde el escenario final con `tools/stress_ts247_long_horizon.py`.

**Balance medido a veinte temporadas (2045/46):** 92 clubes profesionales, cero puestos titulares vacíos, ningún club con menos de dos arqueros, 221 huecos de suplentes, 1.491 traspasos, 2.519 retiros, 3.164 promociones de academia, 154 futbolistas sub-23 entre los 2.457 de primer equipo y siete mayores de 45. En lo económico, un club tiene caja negativa, la mediana de caja sube de £1,64 a £63,80 millones y el valor de mercado mediano cae de £520.000 a £35.000. **Conclusión: continuidad técnica superada en el modo acelerado, pero equilibrio deportivo y económico a largo plazo NO APROBADO.** No se extrapolan los precios al simulador completo sin validar minutos senior, ya que esa diferencia puede tener un efecto importante.

**Pruebas verificadas en este entorno:**

| Grupo | Ejecución | Resultado |
|---|---|---|
| TS-24.7 completo (incluye transición 2026/27→2027/28, calendario y contabilidad) | `pytest -q tests/test_ts_24_7_long_horizon.py` | **8/8 aprobadas** |
| Regresiones focalizadas de TS-24.5 + TS-24.6 | `pytest -q tests/test_ts_24_6_loans_free_agents.py tests/test_ts_24_5_ai_squad_market.py` | **24/24 aprobadas** |
| Suite histórica ampliada TS-21.3/23/23.1/24.1/24.2 | cinco módulos originales | **141/149 aprobadas, 8 fallidas** |

Las ocho pruebas fallidas de la suite histórica utilizan supuestos antiguos incompatibles con la base TS-24.6 (por ejemplo, exigen versión 14 cuando el formato actual es v16, o construyen clubes sin contabilidad). Se reprodujeron **cuatro casos representativos** directamente sobre el ZIP original TS-24.6 y fallaron de la misma forma. Los ocho fallos se detallan en el registro de ejecución; **no** se presentan como aprobados ni se atribuyen a una regresión sin demostrarlo. La modernización de esos tests históricos requiere actualizar sus fixtures con los contratos y cuentas vigentes.

La suite automatizada focalizada cubre cierre de temporada, caducidad y retorno de agentes libres, integridad de perfiles, reversión transaccional, jubilaciones y promoción U21.

**Límites expresos:** no se verifican oportunidades de minutos senior, velocidad de desarrollo en partidos completos, fatiga e incidencias médicas, rendimiento en Windows ni múltiples semillas aleatorias. No se puede certificar un equilibrio macroeconómico únicamente por ausencia de excepciones o por mantener 92 participantes.

## Archivos importantes

- `src/football_manager/services/world_squads.py`
- `src/football_manager/services/player_development.py`
- `src/football_manager/services/player_aging.py`
- `src/football_manager/services/loan_market.py`
- `src/football_manager/services/youth_academy.py`
- `tests/test_ts_24_7_long_horizon.py`
- `tools/stress_ts247_long_horizon.py`
- `tools/summarize_ts247_long_horizon.py`
- `tools/verify_ts247_balance_package.py`
- `TS_24_7_PATCH_INSTRUCTIONS.txt`
- `TS_24_7_MANIFEST.json`
- `reports/ts247_long_horizon.json`

## Instalación

Con TS-24.6 instalada: cerrar el juego, respaldar la partida SQLite, extraer el ZIP incremental en la carpeta raíz y ejecutar `python tools/verify_ts247_balance_package.py`. No es necesario reemplazar ni reconfigurar la base de datos.

## GitHub Desktop

- Rama sugerida: `feat/ts-24-7-long-horizon-balance`
- Summary: `test(career): stress 5-10-20 year balance and protect squad continuity`

**Atención:** el ZIP original contenía cambios de TS-24.6 sin confirmar; es recomendable confirmarlos en Git antes de crear esta nueva rama.

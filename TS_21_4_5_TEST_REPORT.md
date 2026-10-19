# TS-21.4/21.5 — Integración global de entrenamiento y balance

## Alcance y dependencia

Parche **incremental** para el proyecto con **TS-21.3 instalada**. No incorpora Newgens, canteras, fichajes, una interfaz nueva de entrenamiento ni datos ficticios de empleados. No requiere Node/npm; no modifica `.github/workflows`, el catálogo de roles, las fórmulas OVR/ACT ni los sistemas existentes de cansancio.

**TS-21.4 — Entrenamiento y ciclos del mundo**

- Las revisiones mensuales de TS-21.2/21.3 ya se ejecutaban en todos los planteles persistentes. Se conserva esa única ruta transaccional, incluyendo meses sin partidos y temporadas sucesivas.
- Cada club recibe **una estimación persistente y diferenciada** de apoyo al entrenamiento y cuerpo técnico. Se calcula una sola vez a partir del CA medio del plantel registrado y una variación determinista por club, con límites 44–76/100. El campo `source='estimated-squad-support-v1'` indica explícitamente que **NO son instalaciones ni entrenadores reales**. No se vuelve a calcular porque un club ascienda, descienda o sus futbolistas mejoren.
- Los datos verificados o importados con otra fuente de entrenamiento se conservan. No hay bonus exclusivo de Northbridge ni reglas de desarrollo especiales por división.
- El número real de partidos registrados de cada club durante el mes reduce **ligeramente** la oportunidad de entrenamiento cuando supera cuatro partidos. Se contabilizan ligas y copas en una sola pasada por los resultados ya comprometidos: no se inventan sesiones diarias, ni se simulan minutos extra, ni se vuelve a penalizar condición o lesiones.
- Las lesiones fechadas, mentores, personalidades y minutos reales siguen siendo variables del motor compartido. Las futuras canteras y jugadores reales usarán esas mismas funciones.

**TS-21.5 — Calibración y observabilidad**

- Se agrega una auditoría de lectura de la distribución por clubes/divisiones y global: jugadores activos, edades, medias de habilidad derivada de atributos, percentiles, franjas de puntuación, 90+, 95+, retirados y solicitudes aplazadas.
- Las alertas de QA advierten de pérdida de población mayor al 15%, menos del 8% de menores de 21 años, más del 2% con OVR de referencia 90+, variación de más de 3 puntos en la media o acumulación de retiros aplazados. **Estos umbrales son provisionales y diagnósticos**; nunca se alteran jugadores para cumplirlos.
- El comando `tools/validate_ts2145_world_balance.py` permite registrar la foto del mundo y hacer una proyección de 15–30 años de una cohorte. Distingue expresamente esta sensibilidad de una simulación real de 20 temporadas: usa minutos hipotéticos deterministas, no calendarios ni resultados reales.

## Línea de base: 92 clubes, cuatro divisiones, 2.024 jugadores

Las cifras siguientes son **OVR de referencia (atributos en puesto original y rol por defecto)**; no son ACT, OVR fijo de la ficha, ni la media del once titular.

| División | Jugadores | Media de referencia |
|---|---:|---:|
| Premier League | 440 | 73,48 |
| Championship | 528 | 63,40 |
| League One | 528 | 53,34 |
| League Two | 528 | 43,59 |
| **Total** | **2.024** | **57,80** |

Edad media 25,41 años. 317 menores de 21. Dos futbolistas tienen OVR de referencia 90+; ninguno 95+ al inicio.

## Verificación de 20 años: misma cohorte, sin nuevos jugadores

Se proyectó **toda la cohorte inicial de 2.024 jugadores**, con el motor real de crecimiento y envejecimiento y minutos hipotéticos deterministas de 2–4 partidos mensuales por jugador activo (reducidos en edades avanzadas). Las solicitudes de retiro se trataron como salidas inmediatas en esta proyección, **a diferencia de los aplazamientos reales por profundidad de plantilla**. No hubo fichajes, competición simulada ni altas juveniles.

| Año | Restantes | Retiro acumulado | Media OVR referencia | Jugadores 90+ |
|---|---:|---:|---:|---:|
| 1 | 1.989 | 35 | 58,44 | 2 |
| 5 | 1.803 | 221 | 59,72 | 15 |
| 8 | 1.437 | 587 | 59,81 | 17 |
| 10 | 1.107 | 917 | 60,35 | 16 |
| 15 | 364 | 1.660 | 61,78 | 12 |
| 20 | **16** | **2.008** | 68,39 | 2 |

**Interpretación:** la escala individual se mantiene acotada y los jugadores 90+ son minoritarios. La media de los supervivientes sube por **sesgo de supervivencia**, no porque se hayan subido los atributos para alcanzar un objetivo. Pero la población **colapsa sin reemplazos juveniles**. Este escenario no demuestra equilibrio global de veinte temporadas: confirma que la cantera/Newgens es imprescindible y no debe quedar sustituida por una regla invisible que impida todos los retiros.

Archivo de datos reproducibles dentro del paquete: `TS_21_4_5_COHORT_20Y.json`.

## Dos temporadas reales de partidos

Se completaron **5.918 encuentros** de dos temporadas (2.959 cada una), con persistencia y un guardado/carga SQLite al final, seguido del mismo partido reproducible.

| Temporada | Partidos | Retiros en la transición | Retirados acumulados | Jugadores activos después | Retiros postergados |
|---|---:|---:|---:|---:|---:|
| 2026/27 | 2.959 | 33 | 33 | 2.035 | 2 |
| 2027/28 | 2.959 | 31 | 64 | 2.048 | 5 |

Los aumentos de población se deben a **cuatro clubes externos recién incorporados a las divisiones inglesas** por la política anterior del universo (22 futbolistas por club), **no** a Newgens. La política de aplazamiento de retiros hasta contar con reemplazos sigue activa y puede volverse insostenible después de muchas temporadas; ese límite queda documentado.

Identidades, cumpleaños, PA, estadísticas, resultados y continuación determinista después de guardar/cargar permanecieron consistentes durante esta prueba de dos temporadas. No es una ejecución integral de 15–20 temporadas.

## Guardado y compatibilidad

- La sección de carrera completa y el grafo `manager_state` pasan de versión **8 a 9**. Se mantienen lectores para versiones anteriores compatibles.
- Al abrir v8, solo se cambia el contexto de entrenamiento `provisional-neutral-v1` por la estimación explícita y se conserva cualquier fuente importada. **La migración no modifica edades, atributos, CA/PA, progreso pendiente ni resultados**, y no aplica meses anteriores retroactivamente.
- En una carrera nueva los clubes ya nacen con estimaciones persistentes. En temporadas posteriores, los clubes incorporados reciben el mismo tratamiento. El usuario y la IA comparten las reglas.
- Guardar en **un slot nuevo primero** y conservar el respaldo v8; una vez guardado como v9 no hay promesa de abrir el archivo con una versión antigua. No hay autoguardado ni modificación del exportador JSON de resultados.

## Pruebas y sus límites

- **11 pruebas dirigidas** de entornos, calendario cargado, atomicidad básica, idempotencia, lectura sin efectos, potencial oculto, migración de un grafo TS-21.3 v8 real y auditoría de 20 años de muestra: aprobadas.
- **358 pruebas de regresión** sobre TS-21.1, TS-21.2, TS-21.3 y TS-22: aprobadas.
- **2 temporadas reales**: completadas, con reproducción idéntica tras SQLite.
- La batería histórica de TS-19/TS-20 se lanzó por separado. Sus casos más lentos todavía estaban ejecutándose al cerrar esta versión del informe; no se cuentan como una aprobación completa.
- La auditoría longitudinal **no prueba la estabilidad demográfica** y la falta de Newgens permanece pendiente. No se ejecutó una prueba nativa de Windows ni una prueba visual; los cambios son de backend y herramientas.

## Windows, GitHub Desktop y herramientas

Extraé `TS-21.4-21.5-Entrenamiento-y-Balance.zip` sobre **TS-21.3**, después de cerrar el juego y guardar una copia del proyecto y de la partida. Conservá rutas y reemplazá los archivos; no cambies `.git`.

```powershell
python tools/verify_ts2145_package.py
python -m pytest -ra tests/test_ts_21_4_5_world_balance.py
```

Auditoría opcional de solo lectura:

```powershell
python tools/validate_ts2145_world_balance.py --mode opening --years 20 --output world_opening.json
python tools/validate_ts2145_world_balance.py --mode cohort --years 20 --players 192 --output world_projection.json
```

- **Branch:** `feat/ts-21-4-5-global-training-balance`
- **Summary:** `feat(careers): integrate club training and world balance audits`

No se incluye Node/npm, imágenes ni GitHub Actions.

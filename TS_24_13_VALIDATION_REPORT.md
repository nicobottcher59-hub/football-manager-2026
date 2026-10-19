# TS-24.13 - Validacion integral de plantillas y cantera

**Objetivo:** preservar 92 clubes competitivos durante carreras extensas, sin fabricar jugadores ni dinero y sin garantizar rentabilidad.

**Metodo:** calendario y torneos completos, mercado, contratos, retiros, cesiones, cantera, finanzas y promociones de liga. El marcador senior usa un resolvedor acelerado de pruebas; no certifica minutos de juego, lesiones en partidos ni la interfaz Windows.

## Comparacion historica, semilla 6606

| Version | Anio | XI vacantes | Suplentes vacantes | Clubes <2 GK | Clubes <18 jugadores | Clubes en rojo | Plantilla minima | Plantilla mediana | >45 anios |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TS-24.12 | 5 | 0 | 11 | 0 | 0 | 10 | 21 | 25.0 | 0 |
| TS-24.13 | 5 | 0 | 12 | 0 | 0 | 11 | 21 | 25.0 | 0 |
| TS-24.12 | 10 | 0 | 14 | 2 | 0 | 10 | 21 | 26.0 | 0 |
| TS-24.13 | 10 | 0 | 11 | 0 | 0 | 10 | 21 | 26.0 | 0 |
| TS-24.12 | 15 | 2 | 28 | 19 | 0 | 9 | 21 | 25.0 | 0 |
| TS-24.13 | 15 | 0 | 11 | 0 | 0 | 10 | 21 | 25.0 | 0 |
| TS-24.12 | 18 | 6 | 41 | 33 | 0 | 8 | 20 | 25.0 | 0 |
| TS-24.13 | 18 | 0 | 13 | 1 | 0 | 9 | 20 | 25.0 | 0 |
| TS-24.12 | 20 | -- | -- | -- | -- | -- | -- | -- | -- |
| TS-24.13 | 20 | -- | -- | -- | -- | -- | -- | -- | -- |

## Otras semillas

| Semilla | Estado TS-24.13 | Anios | XI vacantes al cierre | <2 GK al cierre | Clubes en rojo al cierre |
|---:|---|---:|---:|---:|---:|
| 6606 | failed | 18/20 | 0 | 1 | 9 |
| 7707 | completed | 5/5 | 0 | 0 | 8 |
| 8808 | completed | 5/5 | 0 | 0 | 9 |
| 7707 (horizonte medio) | completed | 10/10 | 0 | 0 | 11 |

## Interpretacion

- Una caja negativa, una gestion mala o uno o dos suplentes faltantes NO son fallos tecnicos.
- La mejora interviene en intakes U15 reales y promociones de juveniles U21 elegibles.
- No se modifica el sistema de ingresos, gastos, presupuestos, transferencias ni retiros.
- El club humano sigue controlando manualmente las promociones de su academia.
- Los clubes IA no reciben futbolistas fantasma ni ningun rescate economico.

## Incidencias de las ejecuciones

- Semilla 6606: failed, 18 temporadas, 1 incidencias tecnicas documentadas.
  - {'exception': 'ValueError', 'detail': 'player was born after club registration', 'season_attempted': 19}
- Semilla 7707: completed, 5 temporadas, 0 incidencias tecnicas documentadas.
- Semilla 8808: completed, 5 temporadas, 0 incidencias tecnicas documentadas.

## Estabilidad de partidas y transiciones

- La carrera completa de TS-24.12 ya excedia el limite anterior de 250.000 nodos tras una temporada (285.944 en la comprobacion de referencia).
- TS-24.13 mantiene el grafo y SQLite en version 16, con limite de capacidad finito de 1.000.000 nodos.
- Guardado/recarga real tras una temporada: comprobados mediante `tools/smoke_ts2413_longitudinal_save.py`, con IDs de juveniles conservados.
- Los clubes que llevan anios fuera de las ligas sincronizan su ultimo reloj fisico al iniciar un nuevo curso, antes de dar de alta canteranos.
- Bateria de 59/59 pruebas de regresion TS-24.8 a TS-24.13 aprobadas; los informes de simulacion son una comprobacion adicional y distinta.

## Limitaciones

- No se realizo guardado/carga SQLite despues de las 20 temporadas; la prueba de persistencia cubre el primer cambio de temporada.
- Los indicadores al cierre de junio son una foto anual, no datos de cada dia o ventana.
- Las temporadas aceleradas no equivalen a ejecutar todos los partidos con el motor detallado.
- La variabilidad entre semillas impide prometer plantillas perfectas en cada carrera.
- No hay ejecucion nativa Windows dentro de este entorno.

## Estado de cierre de esta entrega

**TS-24.13 es un parche funcional con validacion deportiva parcial hasta 18 temporadas; NO esta certificado a 20 temporadas.**

- Semilla 6606: se completaron 18 temporadas con mejoras claras en arqueros y titulares; la ejecucion experimental de 20 se interrumpio al entrar en la temporada 19 por una fecha de recuperacion atrasada en el resolvedor acelerado de PRUEBAS.
- Ese resolvedor de pruebas se corrigio para mantener el mayor reloj observado incluso cuando los partidos de otra competicion llegan fuera de orden; la prueba unitaria correspondiente pasa, **pero no se repitio la simulacion completa de 20 temporadas**.
- Semilla 7707: 10 temporadas completas; semillas 7707 y 8808: 5 temporadas completas.
- Regresiones: 59 pruebas aprobadas en la pasada integrada anterior; despues de modificar el resolvedor de pruebas, 4 pruebas dirigidas aprobadas. Una repeticion integra posterior excedio el tiempo y no se cuenta como aprobada.
- Guardado/recarga SQLite tras 1 temporada: prueba completada, esquema v16 sin migracion.
- El balance economico queda intencionalmente sin alterar.

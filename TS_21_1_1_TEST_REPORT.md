# TS-21.1.1 - Optimización de Continue y estabilización del calendario

## Alcance

Incremental sobre la versión real entregada: ZIP original, hotfix TS-19
LM/RM/arquero y TS-21.1 Mundo Inglés. Se conserva la simulación de los
92 clubes ingleses y sus 2.024 futbolistas iniciales. Esta actualización no
implementa TS-22 ni desarrollo/envejecimiento TS-21.2.

El backend y las herramientas continúan en Python. No hay cambios en el
frontend, compilación con Node ni nuevas dependencias de ejecución. Pytest
sigue siendo necesario para ejecutar las pruebas, como en las entregas anteriores.

## 1. Qué se optimizó

El perfil original de un avance de 28 días mostraba que la selección de
alineaciones de la IA consumía aproximadamente 30,37 de los 45,59 segundos
medidos con cProfile. Estas cifras incluyen la sobrecarga del perfilador y no
son comparables con los tiempos de uso normal de la tabla siguiente.

`services/world_squads.py` ahora comparte una matriz de valoraciones durante
cada selección: titulares, banco y comparación entre plan principal y
alternativo reutilizan los cálculos ya hechos. No se elimina la asignación
por puestos, no se reducen los roles considerados y no se sustituyen partidos
por marcadores aleatorios.

`domain/player_ratings.py` separa el cálculo común y añade un evaluador
por lote de vida corta. Sus entradas dependen de los atributos y del estado
actuales. La caché del jugador NO persiste entre selecciones, partidos o
cargas. Los pequeños modificadores matemáticos puros tienen cachés acotadas.
Se conservan coeficientes, orden de operaciones y redondeos de OVR/ACT.

`ui_shell/progression.py` evita reconstruir las vistas de todas las ligas en
pasos que no resolvieron partidos. Se mantienen la recuperación diaria, el
vestuario y la vinculación del siguiente encuentro. No se retiraron las copias
transaccionales que permiten recuperar el estado ante un error de Continue.

El planificador consulta un índice temporal por club, actualizado dentro de
la misma transacción y descartado al finalizar. Evita recorrer todo el fixture
para cada consulta de conflicto y no añade estado a los guardados.

## 2. Mediciones reproducibles

Entorno Linux, Python 3.13.5, sin Node/npm en PATH. Tres repeticiones por escenario,
antes y después, sin otras baterías de pruebas ejecutándose simultáneamente.
Ambas versiones se restauraron desde el mismo estado inicial sintético.
Se informa la mediana; no es una promesa de tiempos para una PC Windows.

| Operación | Antes | Después | Menos tiempo |
|---|---:|---:|---:|
| Continue inmediato pospartido; 39 resultados nuevos | 2,084 s | 1,365 s | 34,51% |
| Avance de 28 días por la aplicación | 15,033 s | 9,937 s | 33,90% |
| Lote fijo de 128 partidos de liga | 5,835 s | 3,549 s | 39,18% |

Continue y el lote fijo produjeron exactamente el mismo hash del registro de
resultados y del estado mutable de los futbolistas en ambas versiones. En el
avance de 28 días hubo 334 resultados nuevos antes y 332 después: algunas
fechas se desplazaron por la nueva política. Esa fila sirve como medición de
la operación completa, NO como prueba de equivalencia bit a bit ni como carga
idéntica de partidos. La equivalencia se verifica por separado con entradas fijas.

Los tiempos por repetición y hashes están en `TS_21_1_1_BENCHMARK.json`.
`tools/benchmark_ts2111.py` permite repetir los escenarios con Python y carreras
desechables. No abre ni modifica guardados personales.

## 3. Calendario

`domain/calendar_planner.py` establece una preferencia de 72 horas entre
compromisos y busca primero fines de semana cercanos. Tras Europa un miércoles
o jueves, se favorece el domingo cuando el rival y el siguiente compromiso
también lo permiten. Se comparan horas de kickoff, no solo diferencias entre
fechas: miércoles 19:45 a sábado 15:00 NO son 72 horas.

Solo se reparan encuentros de liga generados, pendientes y desplazables. Se
respetan las ventanas internacionales del juego y la cronología de las copas.
Se comprueban el partido anterior y posterior de AMBOS clubes. Las reservas
incluyen los otros encuentros desplazados en la misma operación.

El primer kickoff se conserva en `original_kickoff`. No se cambian IDs,
participantes, resultados o jornadas. Una reparación repetida no vuelve a mover
arbitrariamente el mismo calendario. Si la operación falla, se revierte completa.

Aplicación: inicio de carrera, generación de temporada, nuevas rondas de copas
y carga del guardado completo. Las nuevas rondas solo revisan los clubes
afectados, en lugar de recalcular todos los calendarios cada día.

En el escenario de Northbridge que motivó el cambio:

| Compromiso europeo | Partido de Premier corregido |
|---|---|
| Miércoles 4/11/2026 | Domingo 8/11/2026 |
| Miércoles 25/11/2026 | Domingo 29/11/2026 |

No se promete una separación universal de 72 horas. Se mantiene el piso duro
anterior de 48 horas y se permite reportar excepciones cuando la búsqueda
local no ofrece una fecha de 72 horas para ambos clubes o hay fechas protegidas.
La auditoría inicial detecta 42 pares por club de menos de 72 horas, sin
ninguno menor de 48 y sin violaciones de ventanas internacionales. No se ha
demostrado que esas excepciones sean inevitables en un optimizador global;
se evita una reprogramación masiva para forzar una solución. Las 72 horas son
una política de este juego, no una cita de reglamentos oficiales.

## 4. Guardados existentes

El formato SQLite completo sigue en versión 5, sin nuevos campos persistentes.
Se valida el grafo y el índice original antes de reparar el calendario.
En una carrera cargada, solo se consideran fechas posteriores al día actual:
se preservan los encuentros ya jugados, el partido abierto de hoy, el pasado
y los fixtures marcados como oficiales.

La corrección ocurre en memoria: cargar NO sobrescribe la base fuente. Para
conservarla hay que guardar normalmente. Se incluye un guardado sintético v5
generado con el código anterior para probar la carga real, no una simulación
manual del formato. No contiene una partida del usuario.

Las fechas futuras modificadas pueden cambiar descansos y resultados futuros;
no se garantiza repetir los resultados de una temporada con otro calendario.
No se regeneran planteles ni se ajustan atributos al cargar.

## 5. Pruebas verificadas

| Batería | Resultado |
|---|---|
| Instalación limpia: 44 pruebas nuevas + 76 de TS-21.1 | **120 passed**, 47,70 s |
| TS-19, TS-20, transacciones de partido, aplicación y guardado completo | **157 passed, 2 skipped**, 444,67 s |
| Atomicidad mundial, calendario, integridad, cola de avance y progreso diario | **47 passed**, 157,00 s |
| Regresión original de valoraciones y mundo persistente | **114 passed**, 99,97 s |
| Casos históricos de reprogramación seleccionados | **10 passed, 2 deselected** |
| Temporada completa con futbolistas persistentes y cambio a 2027/28 | **2.959/2.959** partidos; atributos e identidades conservados |
| Calendario durante 15 temporadas, 2026/27 a 2040/41 | **44.385** partidos, cero huecos pendientes, cero violaciones de 48 h o ventanas internacionales |

Las filas son ejecuciones separadas con algunos casos repetidos; no se suman
como un total de tests distintos. Las dos omisiones son verificaciones
opcionales de sintaxis con Node de TS-19 y TS-20. Los dos casos deseleccionados
pertenecen a la selección histórica larga; no se cuentan como aprobados.

La instalación limpia se reconstruyó desde el ZIP original + hotfix TS-19 +
TS-21.1 + este incremental. Se verificaron sus hashes. Tanto esa instalación
como la batería de compatibilidad y la auditoría del calendario se ejecutaron
con un PATH donde Node/npm no estaban disponibles.

Se incluyen pruebas de igualdad del once y banco en los 92 clubes, ambos
planes tácticos, desgloses de ACT contra la fórmula anterior, invalidación
de caché al cambiar atributos/estado, 24 resultados con semilla fija,
protección de partidos jugados/oficiales/hoy, reparación idempotente,
rollback ante fallos, carga de un SQLite v5 anterior sin sobrescribirlo y
verificación de archivos alterados o rutas inválidas del manifiesto.

El estrés de 15 temporadas es SOLO del planificador: emplea el fallback
agregado existente en un mundo de prueba sin registro de futbolistas. No se
usa ese atajo en producción ni se presenta como una prueba de envejecimiento.
Aparte se completó una temporada real con el registro de jugadores activo,
seguida de cambio de temporada, dos partidos gestionados y guardado/carga.

No se ejecutó la suite completa del repositorio ni una prueba nativa Windows.
Los tests nuevos no requieren Node. Las omisiones de Node en regresiones
antiguas no se cuentan como aprobaciones.

## 6. Qué no cambia

No se retocan cansancio, recuperación, lesiones, fuerza de Northbridge, atributos
ni dificultad. Se conservan los planteles, la selección por táctica y las
fórmulas OVR/ACT. Quedan fuera el Match Center integrado, los perfiles rivales,
las tarjetas/radares y demás trabajo de TS-22. No hay crecimiento, CA/PA,
retiros o Newgens en este incremental. Tampoco cambia GitHub Actions.

## 7. Instalación y comandos

Ver `TS_21_1_1_README.txt`. Guardar la carrera, cerrar el juego, conservar una
copia y extraer el incremental en la raíz. Verificar antes de iniciar:

```text
python tools/verify_ts2111_performance_calendar_package.py
python -m pytest -ra tests/test_ts_21_1_1_performance_calendar.py tests/test_ts_21_english_world.py
```

El manifiesto SHA-256 cubre los archivos del paquete salvo el propio manifiesto;
es una verificación de integridad, no una firma digital de autenticidad.

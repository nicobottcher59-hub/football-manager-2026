# TS-12 — Fast Match Discipline Consistency

## Objetivo

Corregir las incoherencias del simulador rapido en tarjetas amarillas, expulsiones,
minutos jugados, ocasiones posteriores, faltas atribuidas y elegibilidad en
penales. Se mantiene la interfaz y el contrato publico de eventos existente.

## Defectos reproducidos previamente

- Un jugador podia recibir dos amarillas sin salir expulsado.
- Una roja en el minuto 18 podia contabilizar 90 minutos disputados.
- Un expulsado podia seguir recibiendo tarjetas y participando en jugadas.
- Las ocasiones se generaban antes de las tarjetas: jugar con diez no afectaba el
  volumen de tiros ni la eficacia de la defensa.
- Las faltas individuales podian no respaldar una tarjeta mostrada.
- Un expulsado podia permanecer entre los lanzadores de una tanda de penales.

## Cambios

1. La disciplina de los 90 minutos se calcula con subflujos RNG separados ANTES
   de generar las ocasiones. Los eventos se procesan cronologicamente y se
   mantiene una tabla de jugadores expulsados.
2. Una segunda amarilla produce la segunda tarjeta amarilla y una roja en el
   mismo minuto. Se sigue usando el enum existente (`yellow`, `red`); no se
   introduce un tipo de evento nuevo ni se altera la API.
3. Los minutos, la condicion y la fatiga final se calculan con el minuto real de
   expulsion. Un expulsado no puede cometer infracciones ni generar tiros o
   asistencias en minutos posteriores.
4. Los tiros se dividen en ventanas cuando hay expulsiones. La inferioridad
   modifica la cantidad esperada de ocasiones; perder al arquero reduce ademas
   la eficacia defensiva. Los pases totales reflejan la inferioridad numerica.
5. Las faltas con tarjetas se asignan al jugador que recibio cada amonestacion,
   conservando la reconciliacion entre las estadisticas individuales y el equipo.
6. Las sustituciones de prorroga no retiran a jugadores ya expulsados. En los
   penales solo participan los futbolistas que siguen habilitados; un jugador
   de campo sustituye al arquero si este ya fue expulsado.
7. La prorroga genera sus propias faltas y tarjetas en los minutos 91-120 cuando
   se disputa, sin inventar tarjetas posteriores a un partido terminado en 90.

## Compatibilidad, determinismo y alcance

- Un partido SIN expulsiones mantiene la misma secuencia de tiros y los mismos
  generadores aleatorios para tiros/posesion; se agrega una comprobacion de
  regresion con semilla fija.
- Un partido CON expulsiones puede dar un marcador y una estadistica diferentes
  respecto a versiones anteriores, de manera intencional. Con la misma version,
  snapshot y semilla el resultado sigue siendo reproducible.
- No cambia el formato persistido de temporadas, modelos publicos ni la UX.
- Las chances y los efectos de jugar con uno menos utilizan parametros tecnicos
  conservadores, no una calibracion nueva contra un dataset oficial. Queda
  pendiente revisar empiricamente las distribuciones en la auditoria final.
- El motor rapido sigue siendo probabilistico, no una simulacion evento-a-evento
  completa. Las acciones dentro de un mismo minuto no tienen orden temporal
  subminuto; la expulsión deja de tener efecto desde el minuto siguiente.
- La disciplina de partidos de fondo y la persistencia de sanciones entre fechas
  pertenecen a etapas futuras, fuera del alcance de TS-12.

## Validacion Windows (sin Node)

Ejecutar desde la raiz del proyecto:

```powershell
python -m pytest -ra tests/test_ts_12_fast_match_discipline.py
python -m pytest -ra tests/test_phase5_11b_fast_match_simulator.py tests/test_phase5_11d_extra_time_penalties.py
python -m pytest -ra
```

Validacion manual: simular un partido y revisar tarjetas, minutos y condiciones.
No se garantiza observar una expulsion en una partida aleatoria aislada; los tests
incluyen semillas fijas que la reproducen.

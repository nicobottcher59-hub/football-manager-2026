# TS-FIX-01 - Sustituciones, cantera y ritmo competitivo

## Entrega y alcance

Parche incremental sobre el ZIP `football-manager-2026.zip` aportado en esta conversación, que contiene TS-UI-08.03. Branch detectada: `wip/scouting-08a-redesign`.

Incluye sustituciones automáticas con efectos reales en el motor rápido y en el avance por calendario, rotación y minutos juveniles, ritmo competitivo y persistencia de los nuevos registros. No modifica diseños de pantalla ni implementa mercado, negociación contractual, noticias, escudos o colores pendientes.

No incorpora dependencias nuevas. El manifiesto enumera los archivos y sus SHA-256; el ZIP no contiene `.git`, cachés, partidas ni bases SQLite.

## 1. Motor de partidos

### Sustituciones cronológicas

Los partidos con entrenador delegado ahora se resuelven por intervalos. Los puntos de decisión incluyen descanso y varios momentos de la segunda mitad; los planes tácticos programados crean sus propios cortes. El cambio altera la alineación y el perfil utilizados para los eventos posteriores. No se inventan cambios después de calcular el resultado.

La selección pondera calidad, condición estimada a ese minuto, familiaridad posicional y necesidades de ataque/defensa según el marcador. El resultado agregado se considera en las decisiones de la eliminatoria. Los recién ingresados no salen inmediatamente y se descartan suplentes lesionados, suspendidos, muy fatigados o inadecuados para el puesto. No existe una obligación de agotar los cambios si el banco no ofrece reemplazos apropiados.

Se respetan cupos y ventanas de `CompetitionContextSnapshot`, incluidos los adicionales de prórroga. Los descansos no consumen una ventana de interrupción. Estos valores son configuración del juego, no una afirmación sobre todos los reglamentos del fútbol real.

### Efectos registrados

Se actualizan jugadores activos, entradas/salidas, minutos efectivos, tramos de rol, estado físico, estadísticas individuales, aprendizaje y exposición de desarrollo. Los planes posteriores siguen al sustituto real y no reintroducen al sustituido. Las expulsiones descuentan los minutos correctos y los penales utilizan los futbolistas elegibles al finalizar.

`DevelopmentSession.quick_simulate()` delega por defecto ambos equipos; el calendario reutiliza esa ruta. La opción `delegate_team=False` conserva el control de la selección del entrenador del usuario. La API de bajo nivel sin entrenadores conserva su ruta calibrada anterior para no cambiar sus pruebas de referencia.

No se agrega un motor nuevo de lesiones durante el encuentro ni una interfaz de cambios manuales. Los resultados futuros pueden diferir respecto del código anterior porque los suplentes y el orden cronológico ya intervienen en el encuentro; con la misma semilla y estado dentro de esta versión la simulación sigue siendo reproducible.

## 2. Cantera y sharpness

### Reloj diario y minutos reales

`youth_match_development.py` procesa encuentros cronológicamente antes de la fecha objetivo y mantiene un reloj distinto del cierre mensual de desarrollo. El mismo avance es idempotente: consultar pantallas, repetir una fecha o recargar una partida no vuelve a otorgar minutos.

La selección considera posición, calidad, disponibilidad, condición y carga reciente. La simulación juvenil sigue siendo ligera, pero reparte minutos efectivos entre titulares y suplentes adecuados. Una alineación completa conserva 990 minutos por partido. Los suplentes reciben los minutos y el rol en que participaron, no 90 minutos ficticios.

Existe un registro común de participación reciente, limitado a 28 días, para partidos sénior y juveniles. Impide registrar dos apariciones del mismo futbolista en una fecha. Cambiar de categoría no crea otro jugador, no duplica exposición y ya no recorta arbitrariamente su sharpness a 72. Antes de una alta, baja o cambio de categoría se cierra la actividad pendiente hasta la fecha actual con la pertenencia correcta.

### Evolución del ritmo

`match_rhythm.py` separa ritmo de condición física. La ganancia por partido depende de minutos y del margen restante hasta 100; no existe un techo artificial de 94. La inactividad produce una evolución gradual hacia una base sostenida por entrenamiento, menor durante una ausencia médica. Las tasas son parámetros explícitos de diseño del juego, no estimaciones fisiológicas.

La ganancia sénior conserva la calibración anterior. Los cambios de actividad/inactividad diaria se aplican a la cantera. No se reescriben atributos, potencial o resultados para forzar variedad. El motor mensual de desarrollo y envejecimiento sigue siendo el existente.

Se preservan transacciones: ante un fallo vuelven al estado anterior resultados juveniles, reloj, minutos y atributos afectados. La recuperación física se calcula por días para no producir ventajas por elegir un salto temporal distinto.

## 3. Pruebas ejecutadas

### Pruebas específicas del parche

**56 aprobadas**, distribuidas en tres archivos:

- `tests/test_ts_fix_01_substitutions.py`: 41 casos de determinismo, ambos equipos, ventanas y cupos configurables, bancos no disponibles, expulsiones, planes tácticos, prórroga, penales, causalidad y conciliación de minutos/estadísticas.
- `tests/test_ts_fix_01_youth_rhythm.py`: 11 casos de ritmo por minutos, inactividad, rotación, primer día del mes, lecturas sin efectos, ausencia de arquero, cruce de categorías, rollback y retorno juvenil fechado.
- `tests/test_ts_fix_01_integration_save.py`: 4 casos de rápida/calendario, no delegación, migración y continuidad SQLite.

### Simulación prolongada

`reports/ts_fix_01_validation.json` contiene la ejecución real con semilla 6606:

| Comprobación | Resultado |
|---|---|
| Muestra adicional de partidos con IA | 500, invariantes aprobadas |
| Carrera por calendario | 21/08/2026 a 30/06/2027 |
| Resultados del mundo al finalizar | 2.959 de 2.959 fixtures |
| Partidos dirigidos durante ese avance | 58 |
| Partidos de motor rápido instrumentados, incluida inicialización | 2.475 |
| Sustituciones registradas en esa instrumentación | 24.306 |
| Cambios del club del usuario en la muestra de temporada | Entre 4 y 5 por partido |
| Partidos juveniles procesados | 3.888 |
| Guardado y recarga de la temporada terminada | Aprobados |

Los 184 fixtures juveniles restantes son anteriores a la creación de las academias en esta carrera: 92 del 01/08 y 92 del 08/08. No se inventó participación anterior al alta de jugadores del 15/08.

La muestra neutral de 500 partidos utilizó equipos y bancos de calidad similar; ambos agotaron sus cinco cambios en esa muestra. No es una prueba de diversidad de decisiones por sí sola. Los escenarios de bancos no elegibles y cupos distintos están cubiertos aparte.

Ejemplo observado el 01/11/2026, sin fijar esos valores como objetivos:

| Equipo del usuario | Sharpness mínimo/máximo | Valores distintos sobre 18 jugadores |
|---|---|---|
| Sub-17 | 64,47 / 82,88 | 17 |
| Sub-21 | 60,16 / 85,03 | 18 |

### Consistencia al avanzar fechas

Se comparó un salto directo del 21/08 al 15/09 con avances diarios para 3.312 juveniles. Coincidieron fixtures, minutos registrados, desarrollo y estado físico. La mayor diferencia numérica de sharpness fue 7,11 × 10⁻¹⁴, atribuible al redondeo de coma flotante. Evidencia: `reports/ts_fix_01_cadence_validation.json`.

Las 56 pruebas específicas también se repitieron sobre una extracción limpia del ZIP original con la superposición del parche: 56 aprobadas.

### Compatibilidad con un guardado realmente anterior

Se generó una partida SQLite ejecutando el código original del ZIP, sin parche, en formato 25. El parche la cargó conservando fecha, 123 resultados y el sharpness de 3.312 juveniles. Se jugó el siguiente partido con 10 sustituciones entre ambos equipos, se avanzó al 29/08/2026, se guardó en formato 26 y se recargó correctamente. Evidencia: `reports/ts_fix_01_legacy_validation.json`.

### Regresión de pruebas existentes

Se ejecutaron **270 pruebas existentes: 256 aprobadas y 14 fallidas**. Las 14 fallidas se repitieron sobre el código original del ZIP y también fallaron: no se observaron fallos nuevos en esta selección. No se ocultaron ni se desactivaron esos casos.

Las causas observadas son datos sintéticos antiguos sin identidades financieras, dos aserciones que todavía esperan la versión de grafo 17, una migración heredada incompatible y un escenario de retiro con contratos desincronizados. No se amplía el alcance del parche para corregir esos sistemas. La lista exacta de pruebas y los errores original/parche están en `reports/ts_fix_01_regression.json`.

Esta selección cubre disciplina, prórroga, condición, cantera, preparación y presentación de partidos, desarrollo, envejecimiento, identidades, guardado, carga, backups y cambio de temporada. El caso de transición a 2027/28, guardado/recarga y siguiente partido también aprobó. Pasaron los controles de sintaxis de los módulos modificados y herramientas nuevas.


## 4. Guardado y migración

El grafo persistente pasa de versión **25 a 26**. Agrega reloj juvenil diario, registro reciente de minutos, fechas de actualización de estado y ventanas de sustitución en el contexto del encuentro.

La migración es hacia adelante: conserva resultados y valores de los jugadores al cargar y comienza la nueva contabilidad desde la fecha de la partida. No reconstruye apariciones históricas que el formato anterior no registró. Los encuentros juveniles antiguos todavía sin procesar, anteriores a esa fecha, no se simulan retroactivamente con la plantilla actual.

Una partida recién cargada puede seguir mostrando 65 o 94 al principio: el parche no maquilla esos valores ni los reinicia. La diferencia aparece al avanzar entrenamiento, inactividad y partidos.

El código anterior no puede abrir un guardado en formato 26. Para desinstalar el parche se necesita también el respaldo de la partida anterior a la migración.

## 5. Límites de esta validación

No se ejecutó una validación visual integral en navegador ni se probó Windows. No se cargó la partida concreta con la temporada terminada del usuario; se validaron carreras sintéticas reproducibles y un guardado generado con el código original. No se ejecutó la totalidad de la suite histórica del repositorio ni una simulación de muchas temporadas.

La cantera conserva el modelo ligero y sus reglas previas de calendario/categorías. No se ha rediseñado el sistema médico, el mercado ni el motor de partidos interactivo 2D. El informe de regresión distingue fallos anteriores de resultados aprobados; no se declara que toda la suite esté verde.

## 6. Reproducción

Desde la raíz del proyecto:

```text
python tools/verify_ts_fix_01.py
python -m pytest tests/test_ts_fix_01_substitutions.py tests/test_ts_fix_01_youth_rhythm.py tests/test_ts_fix_01_integration_save.py
python tools/validate_ts_fix_01.py --season --samples 500 --output reports/ts_fix_01_local_validation.json
```

El validador utiliza bases temporales y no abre ni sobrescribe slots reales. El chequeo de instalación verifica los hashes del manifiesto; una modificación local posterior produce una advertencia de archivo cambiado.

## 7. Instalación y GitHub Desktop

Seguir `TS_FIX_01_INSTALL.txt`: detener Python, respaldar código y partidas, extraer en la raíz manteniendo carpetas, reiniciar y recargar con `Ctrl + F5`.

Branch existente: `wip/scouting-08a-redesign`.

Summary:

```text
fix(simulation,youth): TS-FIX-01 substitutions and youth match rhythm
```

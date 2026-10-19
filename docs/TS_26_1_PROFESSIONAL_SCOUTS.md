# TS-26.1 — Ojeadores profesionales en el cuerpo técnico

Actualización incremental **sobre TS-26**, no un reemplazo del juego. Se agrega el cuarto rol del cuerpo técnico: ojeador profesional. No modifica el sistema de scouting juvenil (Youth Academy) ni oculta las estadísticas de los futbolistas.

## Cómo funciona

- Staff permite **contratar, renovar y despedir** ojeadores profesionales. Tienen calidad (1–100), contratos y salarios con el mismo sistema del resto del personal.
- Cada club empieza con un ojeador. Las plazas disponibles se determinan **provisionalmente por categoría inicial** (hasta que se incorporen instalaciones): 3 plazas en las divisiones 1 y 2, 2 en la 3 y 1 en la 4.
- **Capacidad simultánea:** un ojeador puede observar 1 jugador; si su calidad es **78 o más**, puede observar **2 jugadores a la vez**.
- **Velocidad:** un ojeador de calidad 48 tarda alrededor de 15 días de carrera por informe; uno de calidad 85 tarda alrededor de 7 días. La velocidad depende de la calidad de quien esté asignado; los ejemplos no son un límite fijo.
- En **Scouting → Player search**, usar **Scout player** junto a un futbolista rival. Los trabajos aparecen en **Scout reports**, donde se puede consultar su progreso y cancelarlos.
- Al completar un informe, el juego guarda el resultado y avisa en el **Inbox**, con enlace a Scouting. El informe contiene un resumen, GRL, valor en el momento de la observación y tres fortalezas derivadas de atributos reales.
- El jugador puede cambiar de club o retirarse; los trabajos pendientes inválidos se descartan al avanzar días. Si despedís a un ojeador, los trabajos conservan su progreso y se reasignan automáticamente cuando haya otro disponible.
- Los informes se pueden volver a solicitar después de **30 días**; la ficha conserva la fecha del informe original.
- La contratación aumenta los costos reales según la contabilidad de TS-26 y aplica sus límites de presupuesto. La primera contratación inicial se considera dentro de la estimación histórica de gastos de personal, para no duplicar el cargo.

## Diseño y límites

**NO cambia** la visibilidad de los atributos, GRL, valores ni la capacidad para presentar ofertas. Los informes sirven para priorizar fichajes: **no otorgan una ventaja artificial de negociación**. El scouting profesional sigue siendo independiente del juvenil. Se preservan el motor, el mercado, el entrenamiento y el centro médico de TS-26.

En una futura versión, el nivel de las instalaciones podrá sustituir el criterio provisional de plazas sin reescribir la gestión del personal.

## Migraciones

Los nuevos modelos se guardan en **grafo v19** y **sección manager_state v19** de SQLite. Las partidas TS-26 existentes (v18) migran al abrirlas: se añade un ojeador y la capacidad provisional, sin sobrescribir contratos anteriores, entrenamientos, lesiones ni jugadores. Las migraciones anteriores se conservan.

## Archivos afectados

- `src/football_manager/domain/club_support.py`: roles y modelos persistentes.
- `src/football_manager/services/club_support.py`: plantilla, mercado de personal, capacidades y compatibilidad.
- `src/football_manager/services/professional_scouting.py`: asignaciones, progreso, informes y lectura.
- `src/football_manager/services/transfer_negotiation.py`: informes incluidos en Scouting.
- `src/football_manager/services/manager_inbox.py`: navegación de informes recibidos.
- `src/football_manager/persistence/{session_codec,manager_career}.py`: versión de guardado y migración.
- `src/football_manager/ui_shell/{progression,application,server}.py`: avance diario y API.
- `frontend/portable/{club_support.js,transfers.js,transfers.css,inbox.js}`: interfaz.
- `tests/test_ts_26_1_professional_scouts.py`: pruebas de comportamiento y persistencia.

## Pendientes de validación

- Inspección visual y jugable en Windows.
- Simulación integral de 20 temporadas y regresión del resto del proyecto.
- Equilibrio económico y de capacidad en partidas humanas prolongadas.

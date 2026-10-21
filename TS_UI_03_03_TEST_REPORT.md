# TS-UI-03.03 — Training unificado + corrección Squad

## Instalación
Parche incremental para aplicar **encima de TS-UI-03.02**. Mantener la estructura de carpetas del ZIP.

## Cambios de producto

- Retirado **Training by squad group** de Training y de los modelos/órdenes de Python. Titulares, suplentes y resto del plantel dejan de poseer intensidades diferenciadas.
- Retirado **Automatic physical protection**, incluyendo toggle, sliders antiguos y la lógica paralela del servicio.
- **Una regla automática para el plantel:** cuatro límites vinculados (dos de condición/energía, dos de sharpness/rendimiento), persistidos y validados en Python. Condición insuficiente prioriza recuperación; sharpness bajo puede provocar entrenamiento intenso cuando el partido no es inminente.
- **Excepciones por jugador:** la intensidad manual prevalece sobre el entrenamiento automático. Reset (`default`) devuelve al jugador al plan automático. Las lesiones todavía impiden entrenamientos diarios.
- Las intensidades **modifican condición y fatiga durante el avance diario**, y registran una carga de entrenamiento que interviene en revisiones mensuales. Se conserva el foco individual (Balanced/Technical/Mental/Physical) compartido con Squad.
- **Arreglo Squad:** las filas de jugadores envían el nodo DOM real a `FMRoster.onClick` desde eventos de click y teclado; se actualiza el inspector para otros futbolistas manteniendo la pestaña abierta. Sin cambios en el layout, cabecera, atributos ni estadísticas de Squad.
- Continúan el banner fotográfico, el catálogo de imágenes compartido, los gráficos y el plantel de Training de TS-UI-03.02.

## Migración de partidas

- `GRAPH_VERSION`: 23 → **24**. Las partidas anteriores continúan cargando por la migración explícita de `TrainingPolicy`.
- Se eliminan del esquema los campos heredados `starters`, `bench`, `rest`, `protection`, `low_condition`, `medium_condition`.
- Se conservan los nuevos umbrales y excepciones individuales en partidas v23. Para partidas <=v22 se añaden los defaults de los umbrales y se retiran las reglas obsoletas.
- **Hacer copia de seguridad antes de instalar**, ya que un guardado en v24 no está diseñado para abrirse con builds anteriores.

## Pruebas verificadas en esta entrega

- Entrenamiento TS-UI-03.01 (adaptado): 5/5.
- Retratos y banner TS-UI-03.02: 4/4.
- Automatic/adaptive TS-UI-03.03: 6/6, más 2/2 casos de migración/captura de guardados.
- Suite nueva de unificación e integración Squad: 4/4 pruebas generales + 2/2 pruebas de migración v22/v23.
- Regresión TS-UI-02.14: 6/6.
- **Total de pruebas dirigidas aprobadas: 29**, ejecutadas en tandas separadas por carga de memoria del entorno.
- Chromium: 1680, 1366, 980, 560 y 390 px; sin overflow horizontal ni errores JS. Se probó cambiar intensidades individuales, eliminar excepción, persistir límites, filtros, cambios de jugador por click en nombre/celda y Enter manteniendo pestaña.
- `node --check` en los tres JS y `compileall` en Python: correctos.
- Confirmados por comparación binaria: `squad_ui02.js`, `presentation.js`, `squad_ui029.css` (aprobados) y foto existente (sin modificar).

### Límites de verificación

- **No** se ejecutó toda la suite global en un único proceso (las pruebas de reconstrucción de grandes partidas exceden el tiempo/memoria disponible cuando se acumulan). Los tests dirigidos se ejecutaron independientemente.
- **No** se realizó ejecución sobre el guardado del usuario ni en su Windows.
- Otras secciones no se rediseñaron.

# TS-24.8 — Reequilibrio estructural de plantillas, cantera y finanzas

## Objetivo

Corregir **causas** de desequilibrio observadas en TS-24.7. No modificar estética ni inventar un saldo universal equilibrado. La prueba anterior permitió simular 20 temporadas con cero huecos titulares, pero detectó 221 huecos suplentes, cotizaciones descendentes y un recambio joven insuficiente.

## Cambios que afectan partidas reales

### Gestión de plantillas y fichajes

- El plan táctico sigue resolviendo 11 puestos titulares + 11 suplentes + tercer arquero con asignación única; un jugador polivalente **no cubre dos puestos simultáneamente**.
- Antes, un club podía vender repetidamente a sus suplentes aun después de quedarse sin cobertura. Ahora, solo puede aceptar la pérdida de **un suplente** cuando su doble XI estaba completo; por debajo de diez suplentes cubiertos, no puede deteriorar aún más el plan mediante ventas automáticas. El usuario mantiene el control de sus propias ventas.
- Las compras por IA conservan urgencia titular/suplente/tercer arquero. Los futbolistas sub-24 reciben una pequeña preferencia, pero no sustituyen el criterio deportivo, el consentimiento ni el precio.
- Los jugadores libres se distribuyen según los huecos reales y un desempate determinista por club/fecha; se admite cobertura secundaria auténtica (familiaridad >=70) y se mantiene la validación de intereses, caja, contratos y presupuesto salarial.

### Cantera, retiros y oportunidades

- En la transición anual, los clubes IA consideran la **posición de la vacante y la familiaridad del juvenil** antes de promover a un U21.
- Un juvenil de 19/20 años puede subir antes de cumplir 21 si tiene calidad suficiente para su división y resuelve una vacante real. No se inventan jugadores, PA, goles, minutos ni salarios.
- Las solicitudes/deferencias de retiro se reconocen como necesidades futuras: una cantera puede incorporar un relevo **antes** de que el veterano abandone el club.
- Las promociones siguen sujetas a la capacidad del primer equipo, con máximo 29 futbolistas por esta vía y límite de 8 promociones anuales por IA. El equipo humano decide manualmente.
- En partidos registrados que se simulan de verdad, la IA puede dar **un único inicio por partido** a un U23 físicamente disponible, con familiaridad de al menos 75 y rendimiento proyectado a no más de 16 puntos del titular habitual. Ocurre en una selección reproducible de partidos; se conserva la calidad deportiva y la identidad del jugador. Solo el simulador de partidos registra los minutos realmente disputados. El equipo humano no sufre rotación automática de su alineación.

### Modelo económico

- El ingreso recurrente al comienzo de cada nueva temporada se recalcula por división y dimensión persistente del club, **no en función del salario de sus jugadores**. Descender con contratos altos puede causar pérdidas reales.
- Los gastos corrientes no salariales representan personal, instalaciones, viajes, operación y formación y tienen distinta escala por división. El gasto está anclado a la actividad, **no es un impuesto automático sobre la caja**.
- El presupuesto de nómina anual tiene en cuenta la capacidad recurrente estimada y los contratos ya firmados, en lugar de caer exclusivamente con la nómina anterior.
- No se inyecta dinero para cuadrar cuentas, no se congela el valor de los jugadores ni se garantiza una rentabilidad positiva. El propietario conserva la facultad de ofrecer contratos y gestionar el mercado de acuerdo con las reglas vigentes.

## Límites y decisiones pendientes

- El diagnóstico de 20 años utiliza un escenario acelerado que **no simula el partido senior detallado**. Por lo tanto, sus valores de mercado, edad efectiva de retirada y oportunidades de minutos no son equivalentes a los de una carrera completa.
- No se modificó la política general de valoración TS-24.1: hacerlo solo para revertir la caída observada sin minutos senior falsearía el funcionamiento de la simulación.
- Los clubes IA todavía no intercambian préstamos de forma completamente autónoma; los préstamos del usuario no se alteran.
- No hay un sistema de infraestructura de instalaciones con retornos explícitos, ni bancarrotas con cambio de propietario; los gastos de operaciones son una aproximación de funcionamiento del club.
- Las promociones siguen siendo una decisión de posibilidad deportiva y disponibilidad juvenil; no se promete que los 92 clubes cubran 22 plazas cada temporada.

## Compatibilidad e instalación

- Base obligatoria: **TS-24.7**, instalada sobre la versión TS-24.6 completa.
- No modifica el grafo de SQLite (se mantiene versión 16). Se aplican las decisiones nuevas a revisiones futuras; no se reescribe retroactivamente el historial de contratos, transferencias ni partidas.
- Para instalar, cerrar el juego, respaldar la carpeta y el SQLite, descomprimir el ZIP incremental en la raíz donde vive `INICIAR_INTERFAZ_WINDOWS.bat`, ejecutar el verificador y reiniciar. Ningún archivo de partida está incluido en el parche.

## Pruebas

- Nuevos tests TS-24.8: cobertura táctica, resguardo de suplentes, rotación juvenil real y determinista, oportunidades genuinas de minutos, contabilidad post-descenso, contratos e integridad de promociones, y control humano.
- Auditoría reutilizable `tools/stress_ts248_long_horizon.py`: 5, 10 y 20 temporadas aceleradas, resultados JSON con información acumulada para reproducibilidad.
- No equivale a una prueba nativa de Windows ni a una simulación con múltiples semillas de mundo.

## GitHub Desktop

- **Branch:** `feat/ts-24-8-structural-squad-economy-balance`
- **Commit summary:** `feat(career): rebalance AI squad depth, youth succession and club finances`

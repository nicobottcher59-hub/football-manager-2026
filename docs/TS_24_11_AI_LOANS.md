# TS-24.11 — Préstamos autónomos y consecuencias deportivas

**Base requerida:** TS-24.10. **Guardado:** grafo SQLite versión 16; sin migración.
**Excluido expresamente:** ideologías, perfiles de fichaje o personalidades de gestión de clubes (a conversar en otra versión).

## 1. Cesiones entre clubes autónomos

- Se ejecutan dentro de la misma transacción/journal que el mercado de fichajes, después de cerrar el mes de la ventana. El préstamo comienza el día real de registro siguiente (ej.: 1 de septiembre tras la ventana de agosto): no se retrotrae el salario.
- Solo entre clubes controlados por la IA. No se ejecutan compras, ventas ni préstamos automáticos del equipo del entrenador humano.
- Máximo 10 nuevos préstamos por revisión del mercado; como máximo uno cedido por club de origen en esa revisión. Se respetan el cupo de cinco cedidos por receptor, los 35 jugadores del préstamo y la cobertura de titulares/alternativas del prestador.
- Se consideran jugadores de hasta 24 años que ya están en el primer equipo y pueden salir sin dejar al club de origen sin cobertura indispensable. Las necesidades se calculan con la asignación de formación, no con recuentos duplicados de posiciones.
- Se negocia el reparto salarial según presupuesto real y una promesa creíble de titular o rotación. Se respeta la voluntad individual de cada jugador; no hay compra obligatoria ni opción de compra automática. Los contratos siguen perteneciendo al club prestador.
- Duraciones automáticas de 6 o 12 meses; los préstamos manuales preexistentes siguen admitiendo 6, 12 y 24 meses. El sistema no inventa futbolistas para producir cesiones.
- Las operaciones son reproducibles por semilla y fecha. Una excepción revierte movimientos de plantillas, contratos de préstamo e identificadores.

## 2. Minutos pactados: seguimiento y consecuencias

- Se cuentan únicamente minutos senior registrados en el motor y partidos realmente procesados por el club receptor después del inicio de la cesión.
- Las revisiones requieren al menos 90 días y 6 encuentros reales del receptor. Los objetivos orientativos siguen siendo 155 minutos mensuales para titular, 65 para rotación y 15 para suplente; la revisión limita el objetivo a los partidos reales disponibles.
- No se sanciona cuando solo se simularon marcadores acelerados, ni se atribuye automáticamente a una promesa incumplida la ausencia actual por lesión o suspensión.
- Para préstamos AI-AI, tras 180 días se admite una **recuperación anticipada** si el futbolista jugó menos del 25% del objetivo evaluable. Al terminar la cesión con menos del 40% del objetivo, sufre una pequeña caída de moral. No se aplican multas económicas arbitrarias.
- Los clubes de origen evitan futuras cesiones automáticas a un mismo receptor si tuvieron un préstamo AI-AI recuperado anticipadamente por incumplimiento. La relación se reconstruye a partir del historial persistente; no se agregan campos de guardado.
- Los préstamos con participación del club del usuario siguen bajo sus comandos preexistentes, sin acciones automáticas de otros clubes en su plantilla. Al finalizar, sí puede producirse la consecuencia de moral basada en partidos reales.

## 3. Imposibilidad de presentar once o arquero

- Cuando un equipo exclusivamente de la IA no puede alinear 11 futbolistas disponibles y al menos un arquero, el encuentro se resuelve administrativamente, sin crear ni recuperar un jugador retirado.
- Se guarda un resultado de 0-3/3-0 y un `resolver='administrative'` explícito. Una eliminatoria requiere un desenlace que respete las reglas de desempate existentes; ambos clubes inelegibles se desempatan determinísticamente para mantener el calendario.
- No se registran minutos, titularidades, goles individuales ni desarrollo de jugadores en esos encuentros.
- El club humano nunca recibe una derrota automática por esta rutina: requiere gestión explícita de su alineación.
- Limitación: la interfaz puede seguir mostrando el marcador; su presentación visual distintiva queda para el trabajo de UX. La derrota administrativa es consecuencia extrema, no una corrección instantánea de plantilla.

## 4. Contratos y compatibilidad

Se corrigió un fallo de integración: las revisiones de contratos omitían verificar si el futbolista cedido tenía como empleador al club que intentaba renovarlo. Ahora **el receptor no puede cambiar el propietario del contrato**. El sueldo del receptor se liquida mediante el porcentaje del préstamo; los contratos de origen permanecen intactos.

No se modifica `GRAPH_VERSION` ni los campos persistidos. Los registros nuevos y el identificador de resolución administrativa usan las clases existentes, con aceptación explícita del nuevo tipo de resolución.

## 5. Alcance de validación

- Pruebas unitarias e integradas de transferencias, mercado, préstamos, envejecimiento y guardado.
- Simulación acelerada de dos temporadas con calendario, ascensos, presupuestos, mercado y regresión de propiedad contractual. Un club finalizó con un solo arquero natural y seis con caja negativa: alertas admitidas, no objetivos globales de cero (no equivale a temporadas con partidos senior reales).
- Pruebas focalizadas del motor real de partidos, incluidos minutos de cedidos y falta de arquero.
- **Pendiente:** auditoría multisemilla de 5/10/20 temporadas con partidos reales y prueba nativa Windows, previstas para la etapa de validación integral TS-24.12.

# TS-24.9 — Calibración y validación avanzada

## Contexto y alcance

TS-24.8 redujo significativamente las vacantes de reservas, pero en la auditoría de veinte años todavía aparecieron clubes con saldos negativos y profesionales en edades extremas. TS-24.9 intenta mejorar las **decisiones que provocan** esos desajustes y, sobre todo, medir su variabilidad con datos reproducibles; no impone límites artificiales a los saldos o a las cotizaciones de mercado.

### Planificación sucesoria

- `imminent_succession_needs` calcula qué puestos perderían cobertura si un jugador que **ya solicitó retirarse** abandonara el equipo. Se aplica a futbolistas de 37 años o más y solo a clubes controlados por la IA en las ventanas del mercado.
- Las contrataciones buscan una familiaridad real de 70 o más, respetan topes de presupuesto, disponibilidad, consentimiento del jugador y acuerdos de clubs. Si ya hay suficiente cobertura no se compra un reemplazo.
- La búsqueda de agentes libres incluye estas vacantes futuras. Para cubrirlas por anticipado, no se incorpora a otro candidato mayor de 32 años. No se crean jugadores.
- La protección especial de retiros de 43 años o más se aplica solo a clubes IA: puede admitirse alguna vacante de suplente si el club conserva **los once puestos titulares, al menos nueve reservas cubiertos y dos arqueros naturales** en ambos esquemas tácticos. El jugador humano mantiene los requisitos ordinarios y control de sus decisiones. Si el retiro deja una posición inicial sin cubrir, se aplaza.

### Contratos y solvencia

- Antes de renovar automáticamente un contrato profesional, la IA calcula el déficit mensual que generarían salarios + operaciones menos ingresos recurrentes del club.
- Si el saldo actual no cubriría seis meses de ese déficit, la IA **no suscribe una nueva renovación**. Continúa pagando el contrato existente; su vencimiento sigue las reglas previas de protección de la plantilla y agentes libres.
- No se cancelan deudas, no se reescriben sueldos, no se garantiza flujo de caja positivo, no se modifican la valoración de mercado ni los derechos del manager.

### Semillas reproducibles, sin migración

`DevelopmentSession(world_seed=6606)` conserva el mundo habitual por defecto. Solo el auditor puede crear mundos con semillas alternativas; la semilla se transmite como parámetro de arranque y se guarda en `WorldSeasonRunner`, ya existente en SQLite v16. **No se agrega ningún atributo permanente a DevelopmentSession**: el conjunto de campos de sesión, estrictamente validado al guardar, sigue siendo el mismo. `reset()` conserva la semilla del mundo corriente.

La semilla afecta los jugadores generados, tácticas y decisiones del mundo. El club del usuario comienza con sus referencias de desarrollo existentes, por lo que se trata de mundos distintos pero no de recreaciones completamente independientes del sistema de interfaz.

### Auditorías realizadas y reproducibilidad

Se entregan tres herramientas separadas:

1. `tools/stress_ts249_multiseed.py`: simula con el calendario, transacciones y economía reales, pero usa **marcadores ligeros** en vez de partidos senior detallados, por costos de ejecución. Exporta checkpoints cada año, por semilla, a JSON atómico.
2. `tools/audit_ts249_real_match_minutes.py`: juega una muestra real mediante `FastMatchSimulator`, verifica `processed_fixtures` y las estadísticas `usage` efectivas. El campo `WorldMatchResult.resolver` se mantiene como `background` incluso para un partido FastMatchSimulator de la IA; la auditoría utiliza el ledger de participaciones para distinguirlos.
3. `tools/summarize_ts249_calibration.py`: agrega resultados y compara los datos solo para semillas comunes, sin presentar una ejecución incompleta como aprobada.

Se incorpora un recorrido acelerado de 20 años, además de tres semillas independientes de 5 años. Es intencional: un único mundo de 20 años permite buscar colapsos tardíos, mientras tres mundos a 5 años miden sensibilidad a la generación inicial. **No equivale** a 3×20 años ni permite establecer confianza estadística sobre todas las partidas futuras.

### Limitaciones conocidas

- Sigue faltando un modelo completo de decisiones de junta directiva y concurso de acreedores. Los saldos negativos se registran como problemas de sostenibilidad, no se maquillan con entradas artificiales.
- Los ingresos no están calibrados de forma dinámica en función de asistencia, resultados, acuerdos televisivos, patrocinadores e infraestructura específica.
- Las promociones U21 y contrataciones no garantizan suplentes perfectos en 92 clubes cada año.
- La prueba de veinte años acelerada no certifica veinte temporadas con minutos reales, lesiones o progresión realista de cada futbolista. La muestra de partidos no valida el desarrollo de jóvenes a largo plazo.
- La IA aún no negocia préstamos autónomos entre terceros. Sin cambios visuales ni en interfaz.

### Compatibilidad y Git

- Dependencia: TS-24.8 instalada. Guardado SQLite: **v16**, sin migración y sin carga de partidas dentro del ZIP.
- Branch: `feat/ts-24-9-multiseed-market-calibration`
- Commit: `test(career): calibrate succession, contract viability and multiseed horizons`
- Verificación: `python tools/verify_ts249_calibration_package.py`

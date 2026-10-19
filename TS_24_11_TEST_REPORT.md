# TS-24.11 — Informe técnico y pruebas

**Base:** TS-24.10 · **Guardado:** SQLite v16, sin migración · **Estado:** parche incremental listo con límites de validación explícitos.

## Alcance

1. Préstamos autónomos **AI-AI**, sin intervención en las plantillas ni contratos del entrenador humano. Solicitudes por cobertura táctica o mejoras verdaderamente útiles; elección por disponibilidad, voluntad del jugador, sueldo y cobertura del cedente. Se registran como `LoanAgreement` normales, conservando la identidad y el contrato de origen.
2. Revisión de minutos prometidos con participación del motor real: al menos seis encuentros verificables y 90 días para evaluar; después de 180 días un incumplimiento severo en una cesión AI-AI permite devolución anticipada. Consecuencias deportivas moderadas de moral al terminar una cesión incumplida; sin inventar sanciones financieras. Un prestador no repite cesiones automáticas al mismo receptor después de recuperar un préstamo AI-AI por incumplimiento.
3. Resultado administrativo explícito (`resolver='administrative'`) si un club de la IA no puede presentar once apto y arquero; sin jugadores ficticios, sin minutos ficticios y sin revocar retiros. Los clubes dirigidos por el usuario no reciben incomparecencia automática por esa rutina.
4. Corrección de renovación de contratos de futbolistas cedidos: el receptor no es el empleador contractual. Se evita sobrescribir `PlayerContract.club_id` al revisar renovaciones mensuales.
5. Sin ideologías de fichajes ni atributos nuevos en clubes. No se modifican archivos de interfaz. Préstamos manuales de 24 meses conservados; las nuevas cesiones automáticas suelen ser de 6 o 12 meses.

## Resultados de pruebas

- **14/14 casos nuevos TS-24.11 aprobados en instalación limpia**; 13 aprobados inicialmente y un caso adicional de persistencia SQLite v16 añadido después. Incluyen restricciones AI/usuario, reproducibilidad, distribución salarial, reversión atómica, vencimientos, evidencia real de seis encuentros, ausencia de sanciones con marcadores sintéticos, recuperación por incumplimiento grave, resultado administrativo y guardado de cedidos autónomos.
- **51 pruebas de regresión aprobadas (51/51)** de TS-24.6/24.7/24.8/24.9/24.10, en ejecución combinada. Esas pruebas no cubren por sí mismas todos los módulos históricos.
- **Simulación acelerada 2026/27 y 2027/28, semilla predeterminada:** completadas dos temporadas, 92 clubes profesionales, préstamos activos 16 y 29 respectivamente, transferencias acumuladas 44 y 79, y cero huecos titulares en ambos cierres. Al segundo año seis clubes registran caja negativa y uno tiene un solo arquero natural: es una alerta deportiva admisible, no un error estructural porque conserva sus titulares. El informe JSON preserva el indicador heredado en `legacy_hard_issues` y separa `sporting_warnings`. Las partidas de estrés no reproducen los minutos de partidos senior; no permiten validar el incumplimiento en 20 temporadas.
- **Pruebas reales de partido:** se registraron minutos en seis partidos del receptor dentro de las pruebas focalizadas, y se verificó una incomparecencia real con `resolver='administrative'`, sin computar minutos inexistentes.
- **Instalación limpia sobre TS-24.10:** verificada con `tools/verify_ts2411_ai_loans_package.py`; 14/14 casos nuevos aprobados tras aplicar el ZIP, y compatibilidad de guardado/carga v16 comprobada.
- **No ejecutados:** prueba nativa Windows; suite histórica completa; auditoría con 5/10/20 temporadas y múltiples semillas (planificada para TS-24.12).

## Problemas identificados y corregidos

La primera simulación acelerada detectó un error de propiedad contractual (`invalid contract identity`) al intentar renovar el contrato de un jugador cedido desde el club receptor. Se añadió la comprobación `contract.club_id == cid` antes de cada renovación de la IA. La repetición completa de dos temporadas terminó correctamente, sin reproducirlo.

## Riesgos y limitaciones conocidos

- Las cesiones autónomas usan políticas genéricas, **no ideologías de fichajes**; éstas se decidirán más adelante.
- No hay multas directas ni puntuación persistente nueva de reputación. El deterioro de la relación contractual se infiere del historial de devoluciones anticipadas de cesiones AI-AI; el estado de ánimo refleja incumplimientos evaluables.
- Si un club no puede presentar once, se registra una incomparecencia administrativa; la interfaz actual puede mostrarla como un marcador normal hasta la etapa UX.
- La evaluación de promesas excluye suspensiones o lesiones que siguen activas al revisar, pero no reconstruye toda una cronología médica histórica del préstamo. Su calibración a larga distancia queda pendiente.
- No se persiguen plantillas perfectas ni cero pérdidas económicas. Los déficits y decisiones desacertadas son comportamientos válidos del mundo.

## Instalación

1. Sobre TS-24.10, cerrar el juego y respaldar partida SQLite y carpeta.
2. Extraer el ZIP incremental en la raíz junto a `INICIAR_INTERFAZ_WINDOWS.bat`.
3. Ejecutar `python tools/verify_ts2411_ai_loans_package.py`.
4. Abrir juego, `Ctrl + F5`.

## GitHub Desktop

BRANCH: `feat/ts-24-11-autonomous-loans-promise-accountability`

SUMMARY: `feat(career): add autonomous AI loans and evidence-based playing-time accountability`

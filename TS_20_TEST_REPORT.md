# TS-20 - Player DNA & Dressing Room: informe de validación

## Base y alcance

Base reconstruida a partir del ZIP original, TS-18.5 revisado, TS-18.6 unificado,
TS-19.1, TS-19.1.1 y TS-19 Tactical Studio 2.0, en ese orden. La regresión de
esa base sin TS-20 terminó con **1197 passed en 476,45 s**.

TS-20 implementa una pirámide de influencia que evoluciona automáticamente,
relaciones, apoyo natural a la integración, personalidad oculta y una pantalla
informativa de vestuario. Hay un solo efecto deportivo social, limitado a
**-2 a +2 puntos de moral sobre 100**. No son puntos de OVR/ACT.

No incluye los retoques pendientes del editor TS-19, progresión de atributos,
envejecimiento, generación de lesiones, Newgens o un nuevo mercado de pases.
La propensión a lesiones se persiste, pero aún no tiene consumidor médico.
Los otros rasgos tienen consumidores pequeños de integración o contexto social.

## Resultados ejecutados

Entorno: Linux, Python 3.13.5. No se ejecutó Windows nativo.

| Validación | Resultado |
|---|---|
| Regresión de la base TS-19 | 1197 passed; 476,45 s |
| Regresión completa con TS-20 | **1271 passed; 0 fallos; 501,78 s (8 min 21 s)** |
| Pruebas específicas TS-20 | 74 passed; 15,20 s |
| Específicas sin Node en PATH | 73 passed, 1 skipped; 16,28 s |
| Instalación limpia desde base + ZIP: específicas | 74 passed; 17,74 s |
| Interacciones en Chromium | 21 comprobaciones; 0 errores JavaScript no capturados |
| Estrés del estado social | 5474 días, 782 registros sintéticos de participación |
| Dos temporadas reales de competiciones DEV | 56 + 62 partidos del equipo gestionado; persistencia idéntica tras cada temporada |

Las 74 pruebas nuevas están incluidas en las 1271. La instalación limpia y la
ejecución sin Node son repeticiones, no nuevos casos que deban sumarse al total.
El tiempo del proceso completo fue 504,02 s incluyendo el arranque y cierre;
501,78 s es el tiempo informado por pytest. El lote de estrés independiente
terminó en 12,24 s.

## Qué comprueban las pruebas nuevas

- Personalidad determinista, validada, sin consumir aleatoriedad del partido.
- Igualdad entre avanzar día por día y avanzar un intervalo con los mismos eventos.
- Invariancia frente al orden de inserción del plantel; lecturas y cambios de
  alineación no actualizan la jerarquía ni alteran moral.
- Minutos reales, solapamiento de intervalos, exclusión de jugadores no
  disponibles, resultados duplicados y rechazo de datos inválidos sin mutación.
- Ausencias sostenidas frente a rotaciones aisladas; caducidad del historial
  relevante durante períodos sin partidos.
- Llegada de veteranos sin liderazgo automático, ascenso gradual y apoyo natural.
- Salida de un referente: efecto pequeño solo en vínculos cercanos, recuperación
  sin contratar sustituto, sin acumulación ilimitada.
- Una primera revisión neutral no fabrica una pérdida de liderazgo por un cambio
  de fórmula de inicialización a revisión.
- Moral social aplicada una sola vez en el snapshot y en reasignaciones; no se
  modifican atributos base, OVR, confianza, condición o química por una vía paralela.
- Integración real con quick_simulate, progresión diaria y transición de temporada.
- Rollback de partido/día: mundo, jugadores y relaciones vuelven al estado previo
  si falla la transacción.
- SQLite y continuidad idéntica tras cargar; fixture de carrera v3 generado con
  el código anterior real y fixture v2 existente; conservación de TS-19 y migración
  social neutral, sin inventar participación pasada.
- Rechazo de guardados actuales sin campos obligatorios o con personalidad,
  enlaces o contexto social corruptos.
- Contrato HTTP real de la ruta de lectura y assets; ausencia de una API manual
  para asignar amigos; no divulgación de números privados al frontend.

Dos pruebas anteriores cambian únicamente su versión esperada de guardado,
de 3 a 4 (`test_ts_17_4_long_career_persistence.py` y
`test_ts_19_tactical_studio.py`). No se eliminan casos para conseguir el resultado.

## Navegador: evidencia y limitación

Chromium renderizó los HTML, JS y CSS reales. Se comprobó apertura desde el
menú, pirámide y 18 jugadores, selección, red navegable por teclado,
lecturas sin mutación, rutas existentes, actualización tras progresión real,
guardado/carga, escape de nombres, recuperación de errores y ausencia de
desbordamiento horizontal en 1280, 1024 y 800 px.

La política del navegador de este entorno bloquea navegación a loopback. El
harness no modifica esa política: carga assets locales en about:blank y conecta
fetch con los modelos Python reales mediante un puente en proceso. El transporte
queda identificado en `browser_results.json`. Las rutas HTTP se verifican por
separado en pytest contra el servidor real. No es una prueba de extremo a extremo
por HTTP en Windows, ni una nueva inspección interactiva completa de TS-19.

## Estrés: qué demuestra y qué no

El intervalo social de 15 años usa registros de participación de prueba, no
782 partidos completos del motor. Conservó 18 miembros, 153 enlaces, un máximo
de 256 IDs de partidos y 40 eventos. Todos los contextos quedaron dentro de sus
límites; atributos y estados base no cambiaron.

Separadamente se simularon las temporadas DEV 2026/27 y 2027/28 completas,
con 56 y 62 partidos reales del equipo gestionado, conservando relaciones y
personalidad tras guardar y cargar. Esto NO valida 15 temporadas de generación
de jugadores, canteras, desarrollo/declive o un mercado de pases completo.

## Instalación y cierre

El ZIP conserva rutas del proyecto y contiene frontend, backend, pruebas,
documentación y manifiesto SHA-256. Se instaló una copia sobre la base TS-19
limpia y se ejecutaron las 74 pruebas específicas allí. Los archivos de código
probados se comparan por hash con el paquete final antes de la entrega.

Pruebas descartadas, no contadas como éxito: una regresión previa se detuvo
voluntariamente para corregir la revisión neutral de jerarquía; una selección
ampliada en la copia limpia excedió el límite de esa llamada. Después terminaron
la regresión completa y la ejecución limpia específica reportadas arriba.

Pendiente externo: comprobación visual y regresión en el Windows del usuario.
Las carreras antiguas se leen; los nuevos guardados son v4 y necesitan respaldo
previo para volver al código anterior. El manifiesto verifica integridad de
archivos, no garantiza ausencia de todo error posible.

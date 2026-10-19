# TS-28.1 — Noticias del mundo y Home dinámico

## Alcance entregado

- `/api/news`: modelo de lectura **independiente del Inbox**, derivado de los resultados del `WorldSeasonRunner`, transferencias efectivamente completadas en el registro de contratos y campeones de copas y temporadas archivadas.
- Home: reemplazo del contenido estático de noticias por tarjetas reales; pestaña de noticias del mundo con hasta 24 entradas recientes, lectura del detalle y navegación hacia la competición o el buscador.
- Noticias: resultados del equipo dirigido, resultados destacados del resto del mundo, fichajes **completados con consentimiento** y campeones registrados. La pantalla no anuncia negociaciones abiertas, entrenadores despedidos, goleadores no registrados ni hechos futuros.
- Titulares verificados y filtrados para no saturar la pantalla: partidos ordinarios entre equipos IA no generan automáticamente noticias.
- Tras cerrar una temporada, las noticias de títulos archivados muestran **la temporada, no una fecha inventada**. Los títulos de nuestro equipo generan una sola notificación de Inbox por título mediante las claves persistentes de deduplicación.
- Se conservaron las notificaciones, conversaciones y decisiones de TS-25, sin convertir el Inbox en un periódico global.
- No hay duplicación de resultados/transferencias en la base de datos. No se cambia el esquema del guardado: se mantiene `GRAPH_VERSION = 20`.

## Pruebas ejecutadas

- `tests/test_ts_28_1_living_news.py`: **7/7 aprobadas** (origen del dato, idempotencia, resultados futuros, propuestas sin finalizar, transferencia completada, títulos archivados sin fecha ficticia, aviso de título sin duplicados, guardar/cargar v20, API HTTP real y assets).
- Regresión dirigida: **5/5 aprobadas**, una muestra de pruebas originales de TS-25 (Inbox), TS-26 (personal), TS-26.1 (ojeadores) y TS-27 (informe de rival y ejecutores).
- Avance real 21–31 agosto de 2026: **aprobado**. El mundo progresó de 74 a 184 resultados, creció el número de noticias comprobadas, se mantuvo la validación de la partida y no aparecieron hechos fechados en el futuro.
- `compileall` Python y `node --check` en los JavaScript afectados: **aprobado**.
- Se intentó abrir el Home con Chromium/Playwright local; el navegador respondió `ERR_BLOCKED_BY_ADMINISTRATOR` a la URL loopback. Por ese motivo **no se declara validación visual automatizada**.
- La batería conjunta de cuatro suites históricas superó el límite temporal del entorno tras 10 casos y no se considera una regresión integral completada.

## Limitaciones conocidas / pendientes

- Prueba visual y jugable en Windows.
- Simulación de 20 temporadas y prueba integral continua.
- El registro de `WorldMatchResult` no dispone de autores de goles para todos los encuentros de la IA: no se inventan nombres de goleadores.
- Noticias de cambios de entrenador, récords e hitos estadísticos individuales esperan registros reales de esos eventos en versiones posteriores.
- Los títulos de temporadas archivadas son hechos conocidos, pero no conservan una fecha individual exacta; se ordenan por temporada con fecha visible omitida.
- TS-28.2/28.3 abordarán un explorador histórico más amplio. Este parche es **TS-28.1 solamente**.

## Instalación

Aplicar **únicamente sobre TS-27**. Copiar la estructura del parche al directorio raíz y aceptar reemplazos. No se incluye el juego completo, partidas, `.git` ni archivos generados. No se requiere migración.

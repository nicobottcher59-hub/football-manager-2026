# TS-UI-01A | Informe de implementación y validación

## Base, alcance y arquitectura

**Base:** ZIP original `football-manager-2026--BackUp.zip`, recibido el 19/10/2026.

- El backend Python, la simulación, las competiciones, los jugadores, las finanzas y los archivos SQLite **no se modificaron**.
- La Home nueva sustituye visualmente el dashboard anterior (el código anterior permanece para no romper los consumidores existentes). Tiene una imagen panorámica, escudo y datos institucionales, con cuatro tarjetas grandes: Equipo, Calendario, Competiciones, Buzón.
- Catálogo visual de clubes en `frontend/portable/data/club-identities.json`, resuelto por **ID persistente**. La única identidad cargada en esta etapa corresponde al ID interno `northbridge`, cuya presentación se convierte en **Sunderland AFC**. Esta distinción es deliberada y evita renombrar referencias deportivas históricas.
- Los equipos no presentes en el catálogo reciben nombre deportivo y recursos genéricos, sin mostrar por accidente las imágenes del Sunderland.
- **La identidad Sunderland es solo visual e institucional:** división, plantel, contratos, fixtures, competiciones, transferencias y resultados proceden del mundo ficticio.
- La Home aprovecha `/api/squad`, `/api/calendar`, `/api/competitions`, `/api/competitions/{id}`, `/api/inbox` y `/api/news`, sin respuestas de demostración.
- Equipo: moral, condición, química, forma y alineación titular existente.
- Calendario: próximos cinco partidos del equipo y hasta cinco resultados realmente registrados, sin rellenar resultados futuros.
- Competiciones: solo las que el juego identifica como `managed`; ligas en tabla y copas en cuadro de eliminatorias con cruces registrados. Cuando un club aún no entró en una copa, indica su ronda de entrada y que el sorteo está pendiente.
- Buzón: pestañas Inbox y Noticias con sus mensajes reales. La noticia utiliza el detalle modal que ya existía.
- El tema, fotografías, logotipos y texto institucional están separados del componente Home para soportar otros clubes en el futuro.

## Activos visuales

- `assets/clubs/sunderland/hero.webp`: foto facilitada por el usuario, remuestreada y ajustada levemente para formato hero. No implica restauración por IA de detalles perdidos en el original.
- `assets/clubs/sunderland/crest.png`: escudo facilitado por el usuario, con fondo de cuadrícula eliminado y transparencia RGBA.
- **Nota de derechos:** antes de una distribución pública, verificar las condiciones de uso de imágenes y escudos reales.

## Verificaciones

| Verificación | Resultado |
| --- | --- |
| Pruebas dirigidas de TS-UI-01A (`tests/test_ts_ui_01a_home.py`) | 4/4 aprobadas |
| Regresión dirigida TS-28.2.1 / TS-28.2 / TS-28.1 | 16/16 aprobadas |
| Verificación de sintaxis JavaScript (`node --check`) | Aprobada |
| Backend HTTP, rutas de API y archivos estáticos | Respuestas correctas |
| Chromium aislado con respuestas reales de una partida inicial | Renderizado de Home, escudo, foto, 11 titulares y 5 próximos partidos confirmado |
| Interacción de pestañas de Competiciones y Noticias, diálogo de noticias, navegación y regreso a Home | Confirmada, sin errores JavaScript |
| Club secundario sin identidad visual / regreso al Sunderland | Fallback sin fuga de imágenes confirmado |
| Regresión TS-27 y TS-28.3/28.4 | 21/21 aprobadas |
| Ejecución visual nativa en Windows | Pendiente de prueba del usuario |
| Simulación de 20 temporadas | No ejecutada en esta actualización |

**Limitación del entorno:** Chromium impide navegar hacia el servidor local. La prueba visual cargó la interfaz en un documento aislado y suministró los JSON reales obtenidos del servidor por el proceso Python. Esto valida la maquetación y la interacción del frontend, pero no sustituye una prueba nativa de Windows.

**Sin migración:** el formato SQLite v22 no cambia. La progresión a club real será gradual por sección, tal como se acordó.

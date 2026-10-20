# TS-UI-02.4 — Perfil / Atributos de Squad

## Objetivo

Pulido de la **pestaña Perfil / Atributos** manteniendo los otros paneles, acciones, motor Python y partidas sin cambios. Base requerida: **TS-UI-02.3**.

## Cambios

- **Pestañas instantáneas**: la navegación entre Perfil, Temporada, Estado y Contrato ahora sustituye únicamente el contenido de `.s2-detail-scroll` (no recrea la cabecera, las tarjetas del plantel ni el inspector). La selección de otro jugador tampoco reconstruye el listado completo.
- **Mapa de posiciones en SVG**: campo vectorial con líneas, áreas, bandas y círculos. Cada posición real del jugador ofrece un botón y cada barra se puede seleccionar. Los dos quedan resaltados simultáneamente; la interacción es informativa, no modifica la formación.
- **Todos los atributos**: el listado se genera directamente de `player.attributes` por grupos registrados en el modelo Python. No se cortan a seis destacados. Valores ausentes no se inventan.
- **Radar único**: los ejes son las seis habilidades de mayor peso de `graphics.role.axes` del rol seleccionado. Cian = valores efectivos del jugador (0 a 100); rojo del club = **énfasis relativo del rol**, obtenido de `weight / maxWeight` y normalizado a una escala visual 0–100. **El énfasis NO representa una puntuación mínima requerida**, ni potencial o desempeño proyectado. Los selectores de posición y rol mantienen la consulta a la API existente.
- **Camiseta real de Sunderland**: imagen del usuario, procesada a WEBP RGBA, declarada en `frontend/portable/data/club-identities.json` por ID de club, no en los componentes. Cada club puede declarar su propia `kit_image`; si falta o el recurso falla se dibuja la camiseta genérica basada en sus colores.
- **Menos texto técnico**: las explicaciones del radar quedan en el tooltip de información, no en un bloque largo que ocupe pantalla. Los datos y opciones efectivos siguen accesibles.
- **Animaciones moderadas**: foco y hover del mapa, transición interna de pestaña, aparición del radar y carga visual de barras; `prefers-reduced-motion` elimina las animaciones.

## Cómo agregar clubes

En `frontend/portable/data/club-identities.json`, agregar un objeto con clave igual al ID **estable** del club y `primary_color`, `secondary_color`, `accent_color`, `crest`, `hero_image` y opcionalmente `kit_image`. La ruta de `kit_image` se interpreta desde `frontend/portable/`, por ejemplo `assets/clubs/club_id/home_kit.webp`.

No hace falta reescribir Squad. Para jugadores, el catálogo de fotos sigue siendo `frontend/public/squad/data/player-portraits.json`, por ID de jugador, con fallback ilustrado.

## Alcance y advertencias

- No se modifica **Home**, Tactics ni las otras pestañas de Squad a nivel de presentación; solo su mecanismo común de navegación.
- No se modifican datos del jugador, roles, contratos, atributos, recuperación, transferencias ni la base SQLite.
- La comparación de pesos relativos **no debe interpretarse como capacidades necesarias expresadas en GRL**; el motor no registra umbrales mínimos de atributos para roles.
- El render aislado en navegador utiliza datos simulados solo como fixtures de pruebas; la versión instalada consume el servicio Python real.
- Queda pendiente la comprobación visual definitiva y navegación en Windows con la partida del usuario.

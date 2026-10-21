# TS-UI-02.9 · Ajuste integral de cabecera, directorio y Perfil/Atributos

## Alcance

Actualizacion visual sobre TS-UI-02.8, sin cambios en el motor Python ni en los guardados:

- `squad_ui029.css`: estilo dedicado a la cabecera y directorio de Squad.
- `squad_ui02.js`: agrega puntos de anclaje de estilo `s29-*` sin cambiar los
  campos de los jugadores ni los handlers de acciones existentes.
- `presentation.js`: readapta el lienzo del radar para que los nombres de los
  atributos no se corten al compactar el panel.
- `embed.html`: incluye la hoja de estilo nueva despues de las anteriores.

## Comportamientos preservados

- Una tarjeta selecciona un jugador; el boton de perfil completo navega por
  separado, sin una segunda seleccion accidental.
- Dorsales y capitan proceden exclusivamente de los datos de la partida.
  No se asignan ni se predicen valores ausentes.
- Cambiar entre las cuatro pestanas cambia solo el panel de contenido.
  La lista y la cabecera permanecen montadas.
- Los puntos del campo y las barras de familiaridad se actualizan en conjunto.
- El radar compara habilidad registrada con enfasis relativo del rol, no con
  minimos inventados ni potencial oculto.
- Los atributos registrados se muestran por categoria completa.
- Las camisetas, los escudos y los colores siguen obteniendose del catalogo
  por ID de club; sin camiseta valida aparece el fallback SVG existente.

## Verificacion

- CSS + JS con el orden correcto y sintaxis validada.
- 66 tests dirigidos/de regresion de TS-UI-02.3 a 02.9.
- Chromium aislado 1680x940, 1366x830 y 980x900: cambios de pestañas,
  seleccion de tarjetas con mouse/teclado, mapa interactivo, capitania,
  dorsal no asignado, fallback de camiseta y ausencia de desbordamiento.
- No se verifico la ejecucion nativa en Windows con un guardado de la carrera.

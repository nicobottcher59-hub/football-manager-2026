# TS-UI-02.10 — Squad 01A: directorio de jugadores

## Alcance

Actualización real sobre TS-UI-02.9, centrada en la lista izquierda. La cabecera de jugador, el mapa de posiciones, el radar, las otras pestañas y el motor Python no se modifican.

## Diferencias visibles

- Tarjetas con **tres regiones** (retrato y dorsal, identidad y estado, GRL). Sustituyen las seis columnas antiguas.
- Nueva barra superior de dos niveles: total/aptos + búsqueda y orden, ocupando mejor el ancho.
- Condición con barra y porcentaje; moral con indicador y valor; **forma** real del jugador cuando está registrada.
- Dorsal superpuesto al retrato cuando existe: sin número no se inventa uno.
- Distintivo de capitán tipo cinta en la fila de quien figura como `set_pieces.roles[role=captain].effective_id`. No se infiere del GRL ni se inventa vicecapitán.
- Orden adicional por condición, conservando posición, GRL y nombre.
- Reglas de responsividad para 1500, 1350, 1000 y 560 px. Nombre truncado cuando haga falta sin deformar la tarjeta.
- Búsqueda, selección, navegación al perfil completo, scroll independiente y actualizaciones sin reconstruir la cabecera permanecen igual.

## Arquitectura

Se **edita** `squad_ui029.css` en lugar de seguir sumando archivos CSS. Se retiran los ajustes previos para el directorio que reconstruían seis columnas en los media queries. El sistema de identidad en `squad_ui02.js` sigue leyendo `frontend/portable/data/club-identities.json` por `club_id` (colores, escudo y camiseta); no hay reglas exclusivas de Sunderland.

Para habilitar otro club, se debe cargar una entrada en el catálogo con sus archivos de escudo/camiseta y colores. No hay que modificar las tarjetas.

## Alcance del parche

- `frontend/public/squad/squad_ui02.js`: plantilla de tarjeta y orden por condición.
- `frontend/public/squad/squad_ui029.css`: nueva estructura del directorio y estilo responsivo (sin sumar otra hoja).
- `tests/test_ts_ui_02_10_directory.py`: contratos de regresión de la nueva estructura.
- `docs/TS_UI_02_10_SQUAD_DIRECTORY.md`: descripción del alcance.

No se alteran los modelos de jugador, el simulador, datos de clubes, ni la persistencia.

# TS-UI-12.01 - Finance hero neutral

Base: TS-UI-12. Cambios unicamente en `finances.js`, `finances.css` y
`assets/finances/finance-operations.webp`.

## Comportamiento

- No se utiliza `club.hero_image` para el fondo de Finances.
- La cabecera muestra una fotografia generica de gestion financiera.
- Nombre, escudo y colores del club siguen resueltos mediante `FMClubIdentity`.
- Se conserva la distribucion y funcionalidad de Finances del parche anterior.
- Se utiliza una imagen empaquetada localmente (no requiere internet).

## Validaciones

- `node --check frontend/portable/finances.js`.
- Verificacion estructural: no queda referencia a `c.hero_image` en el hero.
- Asset WebP valido y disponible en la ruta CSS.
- Instalacion incremental sobre TS-UI-12 verificada por hashes.

La modificacion es exclusivamente visual; no se ejecuta una simulacion integral.

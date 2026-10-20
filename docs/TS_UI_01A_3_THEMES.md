# TS-UI-01A.3 — Escalabilidad de identidades visuales

## Separación técnica

- Los IDs y datos de la simulación **no se renombran**. La identidad visible se obtiene de un catálogo independiente usando el `club_id` estable.
- La Home y el chrome lateral/superior consumen variables CSS generadas por `FMClubIdentity.applyTheme` y `FMClubIdentity.applyShell`.
- Las competiciones no dependen del color del club: `FMCompetitionBranding` resuelve sus identificadores de torneo y assets.
- Los resultados V/D/E, lesiones, estados y alertas conservan la semántica visual universal.

## Alta de un club (sin cambiar componentes)

1. Identificar el **ID interno** del club en la partida (no asumir que el nombre visible es el ID).
2. Agregar una entrada en `frontend/portable/data/club-identities.json`, dentro de `clubs`, con esa clave. Mantener `schema_version: 1`.
3. Indicar `display_name`, `short_name`, `founded`, `stadium`, `location`, y opcionalmente `tagline`.
4. Guardar el escudo y la imagen panorámica en `frontend/portable/assets/clubs/<slug>/`.
5. En el catálogo, referenciar `crest` y `hero_image` con rutas relativas seguras: `assets/clubs/<slug>/crest.png`, `assets/clubs/<slug>/hero.webp`.
6. Definir los colores hexadecimales `primary_color`, `secondary_color` y `accent_color` (formato `#RRGGBB`). El motor de tema calcula automáticamente el contraste y los colores de iluminación/superficies.
7. Comprobar la Home en dos tamaños de ventana, contrastes y carga de imágenes. Reabrir otro club para validar que no herede los colores del anterior.

No se necesita alterar `ui_home.js`, `ui_home.css` ni `club_theme.css` para incorporar un club configurado correctamente. Si faltan colores o recursos, se utiliza el tema y los iconos de respaldo sin aplicar la identidad del club anterior.

**Nota sobre Sunderland:** la clave `northbridge` continúa representando el equipo ficticio de la simulación; su overlay visual es Sunderland AFC. No modifica los registros, fichajes, resultados, contratos ni nombres históricos. La integración de identidad en todas las pantallas queda como tarea transversal del rediseño.

## Alta de una competición

Los cuatro torneos de prueba están definidos por ID en `frontend/portable/competition_branding.js`, con `logo` completo, `icon` compacto, `accent`, `glow` y `shade`. Agregar un nuevo torneo a ese registro y sus PNG transparentes en `frontend/portable/assets/competitions/`. El calendario, la Home y la vista completa comparten la misma resolución de temas. Los IDs desconocidos muestran el tema neutral.

## Alcance y seguridad

- Validación estricta de colores `#RRGGBB` y rutas locales de imágenes, sin interpolar CSS arbitrario desde el catálogo.
- Interfaz oscura común; solo el chrome general, el menú, la cabecera y determinados acentos cambian por club.
- Pantallas de competiciones, resultados y atributos no reciben bonificaciones ni alteraciones de datos.
- Sin dependencias externas, sin cambios de Python y sin migraciones de SQLite.

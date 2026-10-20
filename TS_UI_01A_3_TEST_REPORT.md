# TS-UI-01A.3 — Informe de implementación y pruebas

## Alcance realizado

- Tema de club construido a partir de `club_id` + catálogo JSON; colores sanitarizados y variables CSS específicas para UI. Conserva superficies oscuras, acciones primarias y colores semánticos.
- Preservación de identidad de la competición separada del tema del club.
- Iconos compactos (Premier League, FA Cup, Champions League) derivados de las imágenes que proporcionó el usuario. Se conservan los PNG completos para marcas de agua y referencias.
- Pestañas con color y bordes propios, tanto activas como inactivas, en Home y explorador de competiciones.
- Altura igual y estable de los cuatro widgets; Inbox/News y lista de partidos tienen scroll vertical propio para evitar recortes.

## Verificaciones

| Comprobación | Resultado |
|---|---|
| Tests nuevos TS-UI-01A.3 y regresión dirigida de 01A, 01A.1 y 01A.2, excluyendo un test legado con ruta absoluta del entorno previo | **15/15 aprobados** |
| `node --check` de archivos JS modificados | **Aprobado** |
| Prueba Node de identidad del club (Sunderland, segundo club, desconocido, colores claros y valores malformados) | **Aprobada** |
| Prueba Node de competición (cuatro IDs y tema fallback) | **Aprobada** |
| Chromium aislado a 1680 × 945 y 1366 × 900 con modelos generados por el backend real | **Aprobado, 0 errores JavaScript** |
| Cuatro widgets con altura constante al alternar Inbox/Noticias | **1680 px: 555/555/555/555; 1366 px: 545/545/545/545** |
| Feed artificialmente extendido para comprobar el scroll interno (no se guarda en la partida) | **Aprobado, no expande tarjetas** |
| Carga de logos y ausencia de desbordamiento horizontal | **Aprobada en las dos resoluciones** |
| Cambio de tema a otro club no configurado y vuelta a Sunderland | **Aprobado** |
| Prueba integral de 20 temporadas | **No ejecutada** |
| Validación visual completa y jugable en Windows | **Pendiente** |

## Alcance del navegador aislado

El entorno bloquea la navegación de Chromium a un servidor HTTP local. Por eso el test visual ejecuta los módulos originales inyectados en un documento aislado con las hojas de estilo reales y datos obtenidos por los modelos Python de una sesión nueva. Los recursos visuales se insertan como `data:` URL solo durante la prueba. **No representa una prueba real de apertura en Windows**, que deberá comprobar el usuario.

## Datos y compatibilidad

No se modificaron servicios Python, motor de partidos, economía, competiciones, contratos, progresión ni migraciones. El esquema de guardado se conserva en v22. Northbridge sigue siendo el club interno con identidad visual Sunderland.

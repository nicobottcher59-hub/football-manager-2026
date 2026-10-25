# TS-UI-13.01 — Cabecera fotográfica de Competitions

## Base requerida

TS-UI-13 — Competitions Club Theme, con sus parches anteriores.

## Cambios

- Se reemplaza exclusivamente la ilustración SVG de fondo del hero de Competitions por una imagen fotográfica panorámica de un estadio nocturno, extraída del diseño visual aprobado y optimizada como WebP.
- Se mantienen la altura, las dimensiones, el escudo, el texto y la tarjeta de temporada.
- Se conservan los colores del club mediante las capas dinámicas CSS; las competiciones mantienen sus paletas independientes.
- No se modifican el JavaScript, las tablas, calendarios, eliminatorias, filtros ni el backend.
- Se actualiza el test de TS-UI-13 para verificar el nuevo recurso estático.

## Validación

- 30 pruebas Python de Competitions aprobadas (incluidas 4 de identidad/tema).
- Se comprobó que el único cambio en CSS respecto a TS-UI-13 es el fondo de la cabecera.
- Archivo WebP válido y accesible por ruta relativa desde la hoja de estilos.
- Parche ZIP validado y comparación SHA-256 tras instalación de control.
- No se completó una nueva prueba integral de navegador: el montaje Chromium aislado agotó el tiempo permitido.

## Compatibilidad

- Instalación incremental sobre TS-UI-13.
- Save schema v32 sin cambios; no hay dependencias nuevas.

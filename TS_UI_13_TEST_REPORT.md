# TS-UI-13 — Competitions: cabecera e identidad dinámica del club

## Base

Parche incremental para aplicar sobre **TS-UI-12.01 — Finance Hero Neutral**.
No cambia el backend ni el formato de guardado (continúa v32).
Los parches incrementales posteriores al ZIP fuente no reemplazan `competitions.js` ni `competitions.css` (manifiestos de ZIP verificados).

## Alcance real

- `Competitions` conserva las pestañas de ligas/copas, el selector de jornada, las tablas, el calendario de partidos, las llaves de eliminación y su navegación.
- Nueva cabecera compacta con el escudo, el nombre e identidad cromática del **club dirigido**, resueltos por ID estable mediante `FMClubIdentity`/`FMEntityAssets`.
- Imagen de fondo genérica: se reutiliza el archivo `assets/stadium.svg` ya incluido en el juego. No se utiliza una foto de Sunderland ni de otro club.
- Los colores del club se aplican a la cabecera, el elemento de navegación activo y los partidos/filas donde participa el club dirigido. Los colores de Premier League, FA Cup, Carabao Cup y Champions (variables `--ci-*`) permanecen independientes.
- Compatible con futura BD por ID de club: imagen/colores importados y fallback de iniciales si falta un escudo. Las vistas `Other Leagues` no reciben la cabecera de club.
- El encabezado se muestra también mientras se carga una competición y cuando no hay competiciones disponibles.

## Pruebas realizadas

- `node --check frontend/portable/competitions.js`: aprobado.
- **19 tests Python aprobados**: 15 pruebas preexistentes de Competitions y 4 pruebas adicionales de TS-UI-13.
- **Chromium aislado**: 1550, 1024 y 390 píxeles. Sin desbordamientos horizontales ni errores JavaScript detectados.
- Los datos de tablas, jornadas y competiciones de las pruebas visuales provinieron de los modelos reales de `DevelopmentSession` / `competition_read_model`; la interfaz fue montada aisladamente, sin utilizar el servidor completo.
- Verificado el cambio Premier League ↔ FA Cup sin alterar el tema propio de cada torneo.
- Verificado que `Other Leagues` no reciba la cabecera de club.
- Verificada una **identidad de club importada de prueba** (nombre y verde `#168c72`) y un escudo de respaldo, sin referencias específicas al Sunderland dentro de los archivos modificados.
- Integridad SHA-256 y extracción del ZIP sobre una copia de control: verificadas.

## Limitaciones

- El navegador del entorno bloqueó abrir direcciones HTTP locales (`ERR_BLOCKED_BY_ADMINISTRATOR`); por eso la verificación de Chromium fue un montaje aislado con el JavaScript/CSS reales del módulo, no una prueba end-to-end de todo el juego.
- No se ejecutó una temporada completa ni se alteró la partida del usuario.
- El estadio usado como fondo es una ilustración existente, no una fotografía nueva.

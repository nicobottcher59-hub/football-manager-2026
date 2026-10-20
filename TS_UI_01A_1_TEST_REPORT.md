# TS-UI-01A.1 — Pulido visual y forma de los rivales

## Base y alcance

**Base obligatoria:** proyecto que ya contiene TS-UI-01A y su catalogo de identidades; la comparacion de parche se hace respecto de ese estado exacto, no respecto del ZIP del juego completo.

- El frontend tiene una Home cinematografica mas alta, mejores contrastes y cuatro widgets mas legibles.
- En el calendario, el primer partido es una ficha destacada, con fecha, escudo dinamico, localia, torneo y forma de ese rival.
- Los siguientes cuatro partidos muestran cinco casilleros de forma. Verde = victoria, gris = empate, rojo = derrota **desde la perspectiva del rival**.
- Los casilleros punteados con guion **NO** son empates. Indican que aun no existe un resultado registrado para completar la muestra de cinco.
- El marcador se lee del `WorldSeasonRunner.results`, cruzado con `WorldSeasonRunner.fixtures`. Cada partido se cuenta solo si tiene resultado y fecha real `<= current_date`. Se incluyen todas las competiciones del rival en la temporada del mundo actual, sin usar suposiciones ni resultados futuros. En una tanda de penales se distingue al vencedor.
- `calendar_read_model` anade `opponent_form` como campo de **solo lectura** (V/E/D, en orden cronologico), sin ampliar el esquema de guardado.
- La identidad visual se resuelve por club ID con el catalogo TS-UI-01A existente; los rivales sin imagen personalizada conservan un emblema generico.
- No se cambia la logica de la simulacion ni el contenido de partidos, contratos o finanzas.

## Verificaciones confirmadas

| Verificacion | Resultado |
| --- | --- |
| Pruebas nuevas TS-UI-01A.1 (`tests/test_ts_ui_01a1_polish.py`) | 4/4 aprobadas |
| Regresion de Home TS-UI-01A | 4/4 aprobadas |
| Regresion noticias TS-28.1 e historial hotfix TS-28.2.1 | 10/10 aprobadas |
| Regresion historial TS-28.2 | 6/6 aprobadas |
| Regresion dirigida TS-28.3/28.4, excluyendo migracion pesada | 7/7 aprobadas |
| Regresion dirigida TS-27 (analisis rival, suplencia ejecutores, perfiles IA) | 3/3 aprobadas |
| `node --check` para `ui_home.js` | Aprobado |
| Servidor HTTP nuevo: `/api/calendar`, `/api/squad` y JS estatico | Aprobado |
| Chromium aislado: Home, 11 titulares, rival destacado, 4 partidos, seleccion de copas, Inbox y Noticias | Renderizado correcto, sin errores JS |
| Chromium 1366 px | Sin desbordamiento horizontal; dos columnas para legibilidad |

**No confirmados:** regresion integral de todos los sistemas, prueba TS-28.3/28.4 de migracion pesada, toda la bateria TS-27 (se excede el tiempo en la ejecucion conjunta), ejecucion visual nativa en Windows y simulacion de 20 temporadas. No se consideran aprobados.

## Limitaciones deliberadas

- La carrera de prueba empieza el 21/08/2026. Las formas pueden estar vacias hasta que se registren suficientes partidos; no se completan artificialmente.
- La fotografia panoramica del Sunderland proviene del usuario y ya estaba incluida en TS-UI-01A. Este parche **no** cambia esos recursos.
- Otras pantallas aun pueden exhibir nombres/escudos ficticios; requiere conectar progresivamente la identidad global en el resto de UI. La conversión deportiva a Sunderland real tampoco forma parte de esta version.
- Al igual que en TS-UI-01A, la inspeccion de Chromium se hizo en un documento aislado con JSON real del backend, porque el navegador aislado no puede llegar al servidor local desde este entorno.
- Sin cambios de version de SQLite (sigue en v22), sin migracion y sin dependencias adicionales.

# TS-UI-01A.2 — Reporte de implementación y verificación

## Base y alcance

- **Base obligatoria:** proyecto con TS-UI-01A.1 aplicado.
- Nueva identidad visual por competición, clave **ID persistente** del torneo, mediante un catálogo frontend compartido (no dependiente del club seleccionado).
- Recursos PNG aportados por el usuario convertidos a transparencias (sin inventar escudos ni logos). Patrones geométricos de baja intensidad realizados en CSS.
- Aplica logos, colores y patrones en los encuentros del Home, pestañas del widget y cabecera/tabla/cuadro de Competiciones expandida.
- Buzón / Noticias presenta una primera tarjeta destacada, iconos y estilos según categorías disponibles. No hay historias de prueba.
- El minicuadro de copa en Home muestra **máximo dos casillas**: cruce del club y cruce siguiente **solo si existe un sorteo real que incluya al club**. Con sorteo pendiente se ve una casilla informativa, no un rival inventado.
- La copa expandida conserva la visualización completa, interacción y reglas de enlaces previamente existentes; solo se tematiza.
- Sin cambios en Python, SQLite, jornadas, puntajes, clubes ni mecánicas.

## Verificaciones ejecutadas

| Comprobación | Resultado |
|---|---|
| Tests nuevos de identidad, HTML, integridad, estructura y PNG (pytest) | **5/5 aprobadas** |
| Runtime JavaScript para identidad y fallback seguro (Node) | **Aprobado (5 bloques de comprobación)** |
| Regresión dirigida TS-UI-01A y 01A.1 de HTML/Home | **2/2 aprobadas** |
| `node --check` de Home, Competiciones, nuevo módulo | **Aprobado** |
| Chromium con documento aislado, datos JSON del backend local, logos insertados desde los PNG reales | **Sin errores de JS** |
| Home con cuatro widgets, cinco rivales, temáticas y noticias | **Comprobado en Chromium** |
| Carabao Cup con dos casillas y rival pendiente no inventado | **Comprobado en Chromium** |
| Navegación a Competiciones expandida con tema y logo | **Comprobado en Chromium** |
| Pruebas de la suite histórica extensa en bloque | **No finalizadas: ejecución superó tiempo disponible** |
| Prueba visual nativa en Windows / carrera 20 temporadas | **Pendiente** |

### Límites de verificación

El navegador aislado recibe datos reales de un proceso Python que ya estaba corriendo, pero intercepta la red; no constituye una prueba completa de arranque en Windows. La prueba de presentación de imágenes las inyecta desde los PNG del parche debido a ese aislamiento; los archivos en producción se cargan por rutas relativas normales.

El club inicial sigue siendo **Northbridge** internamente con identidad visual **Sunderland AFC**. Las otras secciones del juego todavía pueden mostrar nombres/escudos ficticios. Para añadir más ligas basta extender el catálogo compartido con identidad y recursos, sin modificar el Home.

Este parche no modifica el esquema v22 de guardado.

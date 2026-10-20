# TS-UI-02.7 — Cabecera + directorio de Squad

**Base obligatoria:** TS-UI-02.6. Aplicar sustituyendo los archivos en la carpeta raíz del proyecto.

## Alcance

- Reconstrucción precisa de la cabecera con cuatro zonas: retrato, identidad, equipación del catálogo y tres indicadores (dorsal, GRL contextual y OVR base).
- Camiseta original con `object-fit: contain` y fondo rojo/navy asociado a los colores del club. Watermark cromático generado a partir del escudo del catálogo; respeta la carga asíncrona de identidad y el fallback existente.
- Directorio compacto: retrato, nombre, posición, edad, nacionalidad, dorsal **solo si está registrado**, capitán **solo si es el capitán efectivo**, moral, condición, GRL y chevrón. Seleccionar una tarjeta no abre la ficha completa; el botón dedicado ↗ sí.
- Perfil/Atributos: conserva mapa SVG interactivo, comparación de rol y **todos** los atributos registrados. Ajustes a su distribución para mantener mapa y radar contiguos a resoluciones de escritorio y evitar espacios muertos grandes.
- Cambios de pestaña internos sin reconstruir la lista ni la cabecera. Respeta `prefers-reduced-motion`.

## Datos y escalabilidad

Se reutilizan los IDs y modelos Python, club-identities, player-portraits y la camiseta ya instalada por TS-UI-02.4. El dibujo/foto de la camiseta y escudo no están codificados para Sunderland; cada club obtiene su propio catálogo o fallback.

El indicador pequeño «vs base» es exclusivamente ACT menos OVR base: **no** representa mejora temporal ni potencial. Los valores no disponibles se muestran sin suponer dorsales, capitanías, atributos o cláusulas.

## Fuera de alcance

No se modifican otras pestañas, motor Python, guardado, fichajes, competiciones, contratos ni datos de futbolistas. Las capturas de referencia son conceptuales y la equivalencia píxel a píxel aún requiere validación en la aplicación Windows y escalado del usuario.

# TS-19 - LM/RM en el selector de colocación y arquero fijo

## Cambios realizados

1. **Selector «Choose position»**: se muestran **LM / Left midfielder** en el costado izquierdo del mediocampo y **RM / Right midfielder** a la derecha; los mismos sectores más adelantados siguen ofreciendo LW / RW. Los rangos salen del backend, sin duplicar mapas arbitrarios en el navegador. El panel «Position in this zone» utiliza el mismo criterio.
2. **Representación de la ficha**: al elegir un costado de mediocampo, la ficha muestra LM/RM al ubicarse allí, incluso al recargar la página. El menú explica que se reutiliza internamente la posición LW/RW existente, porque el alcance acordado es el *selector*, no nuevos puestos ni coeficientes del simulador.
3. **Arquero inmóvil**: se deshabilita la captura de arrastre y la recolocación por flechas/Enter en la interfaz. El backend rechaza `studio_point` (mover), `studio_place` y `studio_shape` si se intenta anclar al GK. `Copy other phase` omite GK. La selección del arquero para consultar sus roles se conserva. Se permite resetear un anclaje viejo, pero no crear uno nuevo.
4. **Alcance limitado**: no se modifican fórmulas OVR/ACT, familiaridad, personas, relaciones, motor de partidos, esquema de partidas, 28 formaciones ni TS-20. El formato de guardado sigue en versión 4.

## Validaciones ejecutadas

| Prueba | Resultado |
|---|---|
| Pruebas TS-19 posicionamiento y TS-20 vestuario/frontend, sin Node en PATH | **106 passed, 2 skipped** (Node opcional) |
| TS-19 editor + posicionamiento sin dos simulaciones multitemporada de larga duración | **87 passed, 1 skipped, 2 deselected** |
| Chromium real con bridge Python, sin Node ni npm | **38 comprobaciones aprobadas**, sin errores JS |
| Integridad ZIP incremental | Verificador SHA-256, ejecutado sobre instalación ensamblada |

**Entorno**: Python 3.13.5, Linux, Chromium disponible mediante Playwright Python. **No se ejecutó en Windows nativo**. Tampoco se repitió la suite completa de 1300+ pruebas, ni dos pruebas de temporada/28 simulaciones (excluidas explícitamente de esa batería). No se presentan sus resultados históricos como nuevos.

## Casos críticos comprobados en el navegador

- Liberar una ficha izquierda en la banda media ofrece LM, nunca RM; al elegirla, el código interno sigue siendo LW y la ficha visible se lee LM.
- Liberar una ficha derecha en banda media ofrece RM, nunca LM; la ficha visible se lee RM sin agregar un enum nuevo.
- Liberar arriba mantiene LW/RW; centro, SS/AM/ST, defensores y otras zonas preservan restricciones.
- Un intento de drag del arquero no produce modal, envío de comando ni cambio de coordenadas; teclado tampoco lo mueve.
- La copia de fase excluye la ficha GK y realiza la copia para los demás jugadores; siguen funcionando capas de cobertura, vulnerabilidades, laboratorio, biblioteca y el modo Lineup.
- TS-20, perfiles sociales y relaciones permanecen idénticos tras los comandos de TS-19.

## Limitación explícita

**LM y RM son etiquetas de colocación dentro de Tactical Studio**, no puestos nuevos del dominio; la evaluación OVR/ACT y los roles aprovechan las posiciones de banda existentes LW/RW. Cambiar eso requeriría una actualización más amplia de atributos, roles, motor y persistencia, que no forma parte de esta corrección.

### Reproducción

```text
python tools/verify_ts19_lmrm_gk_package.py
python -m pytest -ra tests/test_ts_19_placement_heatmap.py
python tools/validate_ts19_placement_browser.py --output reports/ts19_hotfix_browser
```

El último comando es opcional y utiliza Chromium + Playwright Python para la validación visual; no se necesita para ejecutar el juego.

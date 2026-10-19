# TS-19 - Selección de puestos por zona y mapa de cobertura

## Alcance de la entrega

Esta entrega modifica exclusivamente el editor táctico de TS-19. Requiere
Tactical Studio 2.0; TS-20 no es un requisito. Se comprobó también la
compatibilidad con una instalación que ya incluye TS-20.
Ningún archivo modificado pertenece al ZIP de TS-20.

## Cambios implementados

Al soltar una ficha de campo se abre un selector compacto de puestos compatibles
con esa zona. La posición y la ubicación se confirman en una transacción:
no se aplica primero medio cambio ni se elige un puesto a escondidas.
Cancelar, Escape y los rechazos del servidor restauran el estado anterior.
El mismo filtro se usa en el panel individual, con la fase activa explícita.

Las bandas posicionales se solapan para permitir opciones vecinas. Respetan
izquierda/derecha y mantienen un único arquero. Son rangos de diseño del
editor, no coeficientes ni reglas nuevas de simulación. La configuración
sale de Python y es la misma que utiliza el navegador.

El puesto futbolístico/rol sigue siendo común a ambas fases. El movimiento
solo cambia la ubicación de la fase editada. Cuando un cambio de rol alteraría
la ubicación automática de la otra fase, se conserva esa ubicación.
Los roles incompatibles se sustituyen mediante la regla existente de rol por
defecto. OVR/ACT y familiaridad responden a la posición elegida con sus
fórmulas anteriores; no se agrega una penalización independiente.

La cobertura usa una escala fija: rojo (baja), naranja, amarillo (media),
verde lima y verde (alta), con interpolación y suavizado. Se conserva exactamente
la fórmula `1 - exp(-sum(kernel))`, sus radios y los porcentajes. No se
normaliza cada formación por separado. No cambia el motor ni las capas de
vulnerabilidades y laboratorio. La leyenda textual distingue los niveles.
Sigue siendo una estimación geométrica, no un mapa de eventos de partido.

## Resultados ejecutados

| Comprobación | Resultado |
| --- | --- |
| Regresión completa de la instalación con TS-19 y TS-20 | 1314 passed, 0 failed |
| Duración de pytest | 8 min 9 s (488.63 s) |
| Pruebas nuevas | 43 passed |
| Pruebas nuevas con Node fuera del PATH | 42 passed, 1 skipped |
| TS-19 reconstruido sin instalar TS-20: pruebas TS-19 + nuevas | 135 passed |
| Nuevo recorrido en Chromium | 32 comprobaciones aprobadas |
| Recorrido de regresión del estudio/biblioteca/planes/partido | 39 comprobaciones aprobadas |
| Catálogo | 56 colocaciones: 28 formaciones x 2 fases |
| Simulaciones de humo del catálogo | 112 ejecuciones: cada uno de los 56 casos repetido con la misma semilla |

Entorno: Python 3.13.5 en Linux. Las 43 pruebas nuevas están incluidas en el
total de la regresión; las otras ejecuciones no se suman como casos únicos.
La comprobación opcional con Node compara 8.649 ubicaciones entre Python y
JavaScript, además de los colores y extremos de la escala.

El navegador comprobó los colores reales del canvas, la vista previa sin
mutaciones, opciones por zona, cancelar/Escape, confirmación única,
filtrado en el panel individual, teclado, deshacer movimientos del mismo puesto,
rechazos, conservación de la otra fase, arquero, capas, biblioteca, planes,
partido y tarjetas de Lineup. El selector cabe en anchos 1100/1550/1920.
Las ediciones tácticas no alteraron el estado social instalado.

La navegación de Chromium a localhost está bloqueada en este entorno. Por eso
la prueba visual carga los archivos reales y conecta con la aplicación Python
mediante un puente en memoria: se reemplaza el transporte, no la lógica.
Los endpoints HTTP reales se prueban aparte mediante pytest, incluyendo rechazo
atómico, revisión obsoleta y confirmación de puesto/ubicación.
No se ejecutó Windows nativo. Esa comprobación queda pendiente en el equipo
usuario; la omisión opcional de Node no impide ejecutar el juego.

## Compatibilidad y límites deliberados

- No cambia la versión ni el esquema del guardado. Se verificaron biblioteca y
  carrera en SQLite. Los recursos frontend son locales, sin npm ni compilación.
- Las tácticas antiguas y los movimientos automáticos de los roles no se
  reclasifican retroactivamente. La API antigua `studio_position` sin fase se
  mantiene para compatibilidad; el editor actualizado siempre envía la fase.
- No se agregan nuevos códigos de posición. Se conserva el uso existente de
  LW/RW para jugadores de banda más retrasados.
- Undo sigue siendo de ubicaciones: un cambio de puesto/rol limpia esa cadena,
  evitando restaurar una ubicación antigua con un puesto nuevo incoherente.
- Ninguna prueba existente de pytest fue eliminada o desactivada. El guion
  histórico de navegador fue adaptado al nuevo paso de confirmación y a los
  cambios de puesto explícitos solicitados.
- No se modifican Lineup, motor de partidos, coeficientes futbolísticos,
  personalidad, relaciones, moral ni desarrollo de jugadores.

## Reproducción

```powershell
python tools/verify_ts19_placement_package.py
python -m pytest -ra tests/test_ts_19_placement_heatmap.py
python -m pytest -ra
```

Referencia para las pruebas específicas sin Node: **42 passed, 1 skipped**.
Los registros de las ejecuciones están en `reports/ts19_placement/`.

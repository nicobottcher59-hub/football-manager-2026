# TS-FIX-05 — Tactics: Drag & Drop entre titulares, suplentes y reservas

**Fecha:** 23/10/2026  
**Base obligatoria:** TS-FIX-04, aplicado sobre la secuencia TS-UI-08.03 → TS-FIX-01 → TS-FIX-02 → TS-UI-08.04 → TS-FIX-03 → TS-FIX-04.  
**Alcance:** parche incremental, sin rediseñar las pantallas Squad/Tactics y sin agregar dependencias.

## 1. Problema y solución

Antes, `frontend/public/squad/squad.js` permitía HTML drag & drop exclusivamente de un titular a otro titular. Las filas de suplentes solamente ofrecían el intercambio por selección y las filas de reservas no podían utilizarse para cambios en la alineación.

El parche incorpora arrastre **en ambas direcciones** para:

- Titulares ↔ titulares (mantiene el mecanismo existente).
- Titulares ↔ suplentes (reutiliza `swap_bench`).
- Titulares ↔ reservas (acción Python `swap_reserve`).
- Suplentes ↔ reservas (misma acción Python `swap_reserve`).
- Suplentes ↔ suplentes (acción `swap_bench_slots`, reordenamiento del banco).

Los suplentes y reservas disponibles pasan a ser elementos arrastrables. También existe alternativa por clic (primero se selecciona el suplente/reserva y después el destinatario), especialmente útil en pantallas táctiles o cuando los paneles requieren desplazamiento. Los destinos válidos tienen resaltado al arrastrar.

No se incorporó ordenamiento entre dos reservas, porque `outside` representa el conjunto dinámico de jugadores fuera de convocatoria, sin una secuencia de posiciones persistente.

## 2. Invariantes del motor

- Siempre hay 11 titulares y se conserva la cantidad previa de suplentes; no se añaden ni eliminan jugadores del club.
- No se admiten jugadores duplicados entre titulares, suplentes y reservas.
- Se conserva la formación, la posición táctica del slot y la asignación de roles; puede haber jugadores fuera de su posición natural, como ya admitía el sistema existente.
- Los reservas lesionados o suspendidos no pueden incorporarse a los 18 convocados. Las operaciones inválidas se rechazan en Python sin modificar la alineación.
- Los cambios afectan `DevelopmentSession.home_lineup`: se pueden guardar y recuperar mediante el grafo de partida existente. No se altera el motor de simulación ni los compromisos contractuales.
- No se altera la versión del guardado: **continúa en 29**, como en TS-FIX-04.

## 3. Archivos de código y pruebas (6)

| Archivo | Tipo | Alcance |
|---|---|---|
| `frontend/public/squad/squad.js` | Modificado | Arrastre, selección y despacho de intercambios de las tres categorías. |
| `frontend/public/squad/embed.html` | Modificado | Carga de hoja de estilo específica. |
| `frontend/public/squad/ts_fix_05.css` | Nuevo | Estilos de arrastre/destino y reservas seleccionables. |
| `src/football_manager/dev_ui/session.py` | Modificado | Intercambio con reservas y reordenamiento del banco. |
| `src/football_manager/ui_shell/models.py` | Modificado | Dos acciones validadas que conectan UI y sesión. |
| `tests/test_ts_fix_05_tactics_roster_drag.py` | Nuevo | Integridad, elegibilidad, ida/vuelta y guardado. |

## 4. Pruebas realizadas

1. **11 pruebas específicas de Python aprobadas** con `pytest -q tests/test_ts_fix_05_tactics_roster_drag.py`. Incluyen reservas ↔ titulares, reservas ↔ banco, titulares ↔ banco, suplentes ↔ suplentes, roles conservados, 11+7 sin duplicados, casos inválidos, bajas por lesión/suspensión, y persistencia del cambio al serializar/cargar versión 29.
2. **Nueve interacciones en Chromium aprobadas** en una vista aislada que carga el JavaScript/CSS real de Tactics y delega las llamadas API al modelo Python real mediante un adaptador del entorno: siete movimientos por drag & drop y dos intercambios por clic. **Cero errores JavaScript** observados en esa ejecución.
3. **Comprobación de sintaxis**: `node --check frontend/public/squad/squad.js` y compilación Python, sin errores.
4. En una selección de regresiones de UI/plantilla, **20 casos aprobaron y uno falló** por la suma de comprobación de una cabecera de Squad de una versión antigua. Ese mismo fallo fue reproducido sin aplicar TS-FIX-05. Dos fallos históricos adicionales, uno por un contrato de datos de partido (`managed`) y otro por una expectativa incorrecta de rutas absolutas de recursos, también se reprodujeron en la base TS-FIX-04.
5. La batería histórica ampliada mostró 31 pruebas completadas visualmente al 100 %, pero el proceso no terminó antes de su límite de ejecución. **No se contabiliza esa batería como íntegramente aprobada.**

## 5. Límites

- No se realizó una sesión nativa completa sobre la partida del usuario y su navegador en Windows. El navegador del entorno impide conexiones directas al servidor local, por lo que la comprobación visual utilizó un adaptador de transporte con los mismos scripts y comandos reales.
- El diseño general de Tactics se conserva; los paneles de reservas continúan ubicados debajo de la formación. Cuando arrastrarlos desde allí resulte incómodo, existe el intercambio por clic.
- No se cambian las ediciones tácticas temporales de Match Centre ni el drag de fichas del editor avanzado de posiciones.

## 6. Instalación y reversión

Extraer el ZIP sobre la raíz de `football-manager-2026` **con TS-FIX-04 ya instalado** (donde está `pyproject.toml`), manteniendo la estructura de carpetas y reemplazando los archivos. Reiniciar Python y forzar recarga con `Ctrl + F5`.

Se recomienda respaldar el proyecto y las partidas. No se requiere migración de partida para este parche. Para revertir el código, restaurar el respaldo TS-FIX-04 de los archivos modificados y eliminar `frontend/public/squad/ts_fix_05.css`.

**GitHub Desktop — branch:** `fix/ts-fix-05-tactics-drag-reserves`  
**Summary:** `fix(tactics): TS-FIX-05 XI bench reserve drag and drop`

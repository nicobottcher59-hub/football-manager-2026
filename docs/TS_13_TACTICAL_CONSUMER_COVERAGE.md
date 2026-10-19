# TS-13 — Tactical Consumer Coverage

## Objetivo

Auditar la correspondencia entre los controles tacticos disponibles y su consumo
real por el **simulador rapido**. Corregir tres casos con efectos ausentes sin
cambiar la UX, los nombres de instrucciones ni el formato de guardado.

Este parche **no declara completadas todas las instrucciones tacticas**.

## Causas reproducidas

- `out_of_possession.offside_trap` se guardaba en la tactica, pero no influia en
  ningun calculo del motor rapido.
- `game_management.time_wasting` solo aparecia en la etiqueta del estilo cuando
  el bloque era bajo; no ralentizaba un partido al ir ganando.
- `game_management.urgency_when_trailing` no tenia consumidor en el motor rapido.
- `game_management.risk_when_leading` entra en la media de riesgo de **todo**
  el partido, aunque el equipo no este ganando. Es una limitacion pendiente,
  no una correccion de TS-13.

## Correcciones

1. Se agregan las instrucciones anteriores al perfil del simulador, con
   valores predeterminados compatibles para quien instancie el perfil a mano.
2. **Trampa del fuera de juego**: la eficacia depende de la altura del bloque,
   la presion y el estilo directo del rival. Una trampa mal alineada con el
   bloque propio puede generar desventajas en lugar de ser una mejora gratis.
   Modifica ligeramente volumen y calidad de ocasiones, sin decretar goles.
3. **Perdida de tiempo**: desde el minuto 65, si un equipo esta ganando y usa
   una intensidad alta o muy alta, reduce de forma acotada las ocasiones de
   **ambos** equipos. La decision usa el marcador de los eventos aceptados
   cronologicamente: no cuenta goles eliminados como si hubieran ocurrido.
4. **Urgencia al ir perdiendo**: al minuto 70, un equipo que va perdiendo y
   selecciono `VERY_HIGH` puede crear oportunidades extra entre el 71 y el 90.
   Conservan las reglas normales de jugadores activos, remates y portero.
   El valor por defecto `HIGH` mantiene los RNG y volumen anteriores.
5. Si ninguna gestion de partido esta activa, se conserva directamente el
   camino anterior de remates (sin nuevos sorteos ni alteraciones del orden).
6. `tactical_coverage.py` inventaria cada campo declarado y lo clasifica como
   efecto en partido, efecto parcial, efecto fisico, etiqueta, agregado sin
   contexto o no modelado. Un test impide que controles nuevos queden sin
   registrar en el inventario.

## Resultado del inventario

Para esta version existen **59 controles** declarados:

| Categoria | Cantidad | Significado |
| --- | ---: | --- |
| `match_effect` | 29 | Influyen en el simulador rapido mediante estilos, perfiles o acciones |
| `partial_match_effect` | 2 | Solo situaciones e intensidades concretas tienen efecto |
| `player_conditioning` | 4 | Modifican el coste fisico del jugador |
| `aggregate_without_score_context` | 1 | Agregado global, sin evaluar marcador |
| `style_label_only` | 1 | Solo cambia la descripcion del estilo |
| `not_modelled` | 22 | No hay un consumidor rapido demostrado |

**Importante:** este inventario se limita al simulador rapido y al desgaste
posterior; el futuro motor 2D no esta evaluado aqui. Los 22 controles sin
modelar no deben considerarse una funcionalidad implementada. No se inventan
bonificaciones genericas para ellos.

Ejecutar `python tools/audit_tactical_consumers.py` desde la raiz del proyecto
para listar el estado de cada uno, sin Node ni dependencias adicionales.

## Compatibilidad y limites

- Conserva contratos HTTP, snapshots y la UI existente; no introduce migraciones.
- Las partidas con trampa del fuera de juego activa, perdida de tiempo alta o
  urgencia maxima pueden arrojar resultados diferentes; es una correccion
  intencional. La misma version, snapshot y semilla sigue siendo determinista.
- El simulador rapido sigue siendo probabilistico y de baja resolucion. Los
  controles de gestion no constituyen una linea temporal continua; la urgencia
  parte del marcador del minuto 70 y la perdida de tiempo del estado desde el
  minuto 65. No se extienden estos efectos a la prorroga en este parche.
- El valor `risk_when_leading` aun se agrega a `style.risk` de manera global;
  ese caso debe corregirse junto con el diseno de las instrucciones
  dependientes del marcador, no con un efecto de riesgo inventado.
- El modelo de trampa del fuera de juego y la gestion de ritmo utilizan
  coeficientes conservadores **sin validacion estadistica contra datos oficiales**.
  Requieren calibracion especifica antes de considerarlos realismo final.
- Sin nueva base de datos, sin cambios de guardado ni de UX.

## Validacion Windows

Desde la raiz del repositorio en PowerShell:

```powershell
python -m pytest -ra tests/test_ts_13_tactical_consumer_coverage.py
python -m pytest -ra tests/test_ts_12_fast_match_discipline.py tests/test_phase5_11b_fast_match_simulator.py tests/test_tactics.py
python tools/audit_tactical_consumers.py
python -m pytest -ra
```

Validacion manual: preparar dos previas con tacticas distintas, simular varios
partidos y comprobar que los cambios de tactica se guarden y apliquen, que
los resultados y las estadisticas sigan coherentes. Un solo partido no puede
probar una diferencia estadistica probabilistica.

# TS-18.4 - Match Engine Consistency (correcciones)

## Alcance

Parche **incremental** sobre TS-18.3. Se corrigen tres defectos comprobados en los motores de partido, sin agregar formaciones, roles, instrucciones, interfaz ni parametros de balance. Las formulas de OVR/ACT, los coeficientes para calificar partidos y las probabilidades de tiro o penal se conservan.

## A. Valoraciones individuales: goles y atajadas fuera de cancha

**Antes:** el simulador rapido calculaba la nota de un arquero con **todas** las atajadas y goles recibidos por su equipo, incluso despues de ser expulsado. Las notas de defensores tambien perdian el credito por mantener el arco en cero si el rival marcaba despues de que habian salido, incluida la prorroga.

**Ahora:** para las mismas formulas y coeficientes existentes, solo se consideran tiros del rival dentro de los minutos en los que el jugador estuvo efectivamente en el campo. Los goles y atajadas del equipo siguen siendo los mismos y el total del partido no cambia. La valoracion de jugadores que disputan el partido completo permanece intacta.

## B. Continuidad del arquero en el motor espacial 2D

**Antes:** una tarjeta roja directa o una doble amarilla al arquero podia dejar al equipo sin un agente activo en la posicion GK. A partir de ese momento, intentar atajar un tiro, ejecutar un saque de arco o realizar una tanda de penales podia lanzar `ValueError` o `KeyError`, bloqueando el partido.

**Ahora:** el motor reasigna al puesto de arquero a uno de los jugadores de campo que continuan en cancha (criterio determinista de mejor ACT existente, tambien empleado por el simulador rapido para el arquero de emergencia). Reutiliza `assign_match_player`, el mismo calculo canonico de posicion, rol y ACT ya corregido en TS-18.2. **No ingresa un duodecimo jugador:** el equipo sigue con diez activos despues de la roja. El otro equipo y el `MatchSnapshot` original no se modifican. El jugador de campo puede ser sustituido por un arquero del banco mediante el procedimiento existente.

## C. Tandas largas de penales en el motor 2D

**Antes:** si una tanda extraordinariamente larga seguia empatada despues de 20 rondas de muerte subita, el motor otorgaba un gol y un ganador al azar, sin un penal real ni un evento correspondiente.

**Ahora:** el resultado se resuelve solo mediante las ejecuciones ya programadas. La tanda continua hasta que los penales registrados producen una diferencia despues de una ronda completa, igual que en la ruta rapida. La semilla y las probabilidades existentes se conservan.

## Pruebas reproducibles

Los 8 casos de fallo iniciales fueron observados **antes de corregir el codigo**. Se incorporaron 14 tests nuevos, que cubren: GK expulsado, gol y atajadas antes/despues de la roja, defensores que se retiran antes del gol, roja directa y doble amarilla en ambos equipos, saque de arco, disparo espacial y tanda de penales con arquero improvisado, y tandas que superan 20 rondas de muerte subita.

- Pruebas especificas: `python -m pytest -ra tests/test_ts_18_4_match_engine_consistency.py`
- Pruebas relacionadas: `python -m pytest -ra tests/test_match_flow.py tests/test_ts_12_fast_match_discipline.py tests/test_phase5_11b_fast_match_simulator.py tests/test_ts_18_2_roles_position_integrity.py tests/test_ts_18_4_match_engine_consistency.py`
- Regresion general: `python -m pytest -ra`

**Control pareado:** 500 partidos con las mismas semillas frente a TS-18.3: 460 resultados completos identicos y 40 resultados diferentes, todos relacionados con expulsiones de jugadores defensivos y sus notas individuales; no se cambian las distribuciones deportivas intencionadamente.

**Fuera de alcance:** el sistema tactico avanzado, nueva IA de suplentes, una nueva capa de estadisticas individuales en el motor 2D y los controles no modelados del simulador rapido. Estos componentes siguen en el roadmap de funcionalidades, no en un parche correctivo.

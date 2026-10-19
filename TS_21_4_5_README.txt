TS-21.4/21.5 - Entrenamiento global y auditoria de balance
==========================================================

Requisito: TS-21.3 instalada. Esta es una actualizacion incremental.
No instala Node, no modifica OVR/ACT, ni el front, ni los workflows de GitHub.

WINDOWS (sin Node)
1. Cerrar el juego y el servidor Python.
2. Guardar una copia del proyecto y de las partidas .sqlite3.
3. Extraer TS-21.4-21.5-Entrenamiento-y-Balance.zip en la carpeta que
   contiene INICIAR_INTERFAZ_WINDOWS.bat, conservando todas las rutas.
4. Ejecutar:
       python tools/verify_ts2145_package.py
       python -m pytest -ra tests/test_ts_21_4_5_world_balance.py
5. Iniciar con INICIAR_INTERFAZ_WINDOWS.bat y recargar Ctrl + F5.

GUARDADOS
- Estado completo de carrera: version 9 (antes version 8).
- Al cargar v8, se instalan una unica vez estimaciones de contexto de
  entrenamiento por club; NO cambian atributos, edad, PA o estadisticas.
- Guardar en un NUEVO slot primero. Volver a software antiguo usando el
  backup anterior, no el guardado version 9.
- No hay autoguardado ni cambios en la exportacion JSON de resultados.

ENTRENAMIENTO
- No se crean entrenadores ni instalaciones ficticias: las calidades son
  estimaciones marcadas como tales, derivadas una sola vez del plantel
  inicial y variacion estable por club.
- Los datos de instalaciones/staff importados tienen prioridad.
- En meses con 5 o mas partidos, la oportunidad de entrenar disminuye
  modestamente para ambos lados. No hay bonos exclusivos del usuario.
- Jugadores reales, ficticios y futuros juveniles usan el mismo motor.

AUDITORIA REPRODUCIBLE (solo lectura)
    python tools/validate_ts2145_world_balance.py --mode opening --years 20 --output world_opening.json
    python tools/validate_ts2145_world_balance.py --mode cohort --years 20 --players 192 --output world_projection.json

La proyeccion es de futbolistas individuales, NO una simulacion integral de
20 temporadas de fixtures; utiliza minutos hipoteticos. La regeneracion
poblacional requiere canteras y Newgens, que NO se incluyen en este parche.
Las pruebas largas no garantizan balance demografico sin nuevos jugadores.

GITHUB DESKTOP
BRANCH: feat/ts-21-4-5-global-training-balance
SUMMARY: feat(careers): integrate club training and world balance audits

Informe: TS_21_4_5_TEST_REPORT.md

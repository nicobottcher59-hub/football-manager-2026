# TS-24.13 - Pruebas de compatibilidad e integracion

## Base y alcance

- Codigo inicial: TS-24.12 (`main`, commit 1880217) del ZIP proporcionado.
- Cambios de produccion: cantera (`services/youth_academy.py`), reloj
  de clubes inactivos (`services/world_squads.py`) y limite de capacidad
  de guardados (`persistence/session_codec.py`).
- Economia, mercado, retiros: API/estructuras originales intactas.
- SQLite: mismo esquema/version v16 y protecciones del serializador; solo
  aumenta la capacidad finita de nodos para un mundo completo.
- Guarda sin migracion: esquema de modo carrera SQLite v16.

## Pruebas de jugabilidad y codigo

- **59 pruebas integradas aprobadas** en la pasada previa a la ultima correccion del simulador de pruebas; la repeticion completa final excedio el tiempo disponible.
- Pruebas dirigidas finales del reloj (incluida una regresion por fixtures fuera de orden) y limite de nodos: **4/4 aprobadas**.
- 5 comprobaciones especificas de cantera TS-24.13: aprobadas tras ampliar
  cobertura (intake determinista, porteros U21 reales, deuda sin regalo de
  dinero, progreso U15 a U21 y limite de tercer GK).
- Muestra de 18 partidos con resolucion detallada: **completada**.
  Minutos reales sub-23 en el registro del motor: **3.006**. De 9
  titularidades juveniles rotadas proyectadas, 5 registraron minutos.
- `compileall` del codigo y herramientas nuevas: correcto.
- Comparacion de persistencia: TS-24.12 falla al guardar la primera temporada
  con 285.944 nodos frente a un limite de 250.000. TS-24.13 conserva la
  version de grafo 16 y amplía el limite, con prueba de roundtrip real.
- `git diff --check`: sin errores de formato.

## Pruebas de simulacion a largo plazo

Consultar `TS_24_13_VALIDATION_REPORT.md` y los archivos JSON, todos
reproducibles con `tools/run_ts2413_validation.py`. La auditoria acelera
los marcadores senior: no prueba todas las lesiones, tacticas ni la UI.

## Limitaciones

- No se ejecutaron los lanzadores `.bat` en Windows en este entorno Linux.
- No se editaron ni abrieron partidas SQLite reales del usuario.
- Los equipos pueden perder dinero y carecer de algun suplente de forma
  natural. No todos los puntos deportivos son condiciones de "0 errores".

## Estado de cierre

El horizonte completo de 20 temporadas sigue **sin validacion final**. El estudio principal registra 18 temporadas deportivas completas; el fallo al iniciar la 19 se atribuyo al reloj del simulador acelerado y cuenta con prueba unitaria tras la correccion, pero no con repeticion de 20 anios. Para resultados concretos, consultar `TS_24_13_VALIDATION_REPORT.md`.

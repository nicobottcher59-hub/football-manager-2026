# TS-11 — Session & Application Reliability

## Objetivo

Proteger las operaciones de sesion y de API existentes frente a fallos intermedios,
sin cambiar la interfaz, las reglas deportivas, el motor ni el formato de guardado.

## Defectos comprobados antes del parche

1. `POST /api/squad` podia modificar la tactica o la metadata de plantilla
   antes de que `squad_read_model()` construyera correctamente la respuesta.
   Una excepcion dejaba el cambio aplicado aun cuando la API devolvia un error.
2. Si `set_formation()` fallaba despues de recalcular familiaridad tactica,
   la alineacion y los valores de familiaridad ya habian cambiado.
3. La cola de cambios temporales de `POST /api/match` podia conservar un cambio
   fallido; `reset_match_tactics` podia borrar una cola valida antes de fallar;
   `match_kits` podia guardar una seleccion aunque fallara la vista previa.
4. El avance asincrono publicaba el mundo completo y luego cambiaba el estado
   del trabajo de `running` a `completed`, con una ventana de inconsistencia.
   Los trabajos completados o fallidos retenian su copia de toda la sesion.

## Solucion

- `ui_shell/transactions.py` incorpora un limite transaccional para comandos
  permanentes de plantilla y tactica servidos por `/api/squad`.
  Conserva las identidades de `DevelopmentSession`, `MatchLineup`, `Tactic`,
  jugadores, diccionarios y objetos de familiaridad incluso tras un rollback.
- El checkpoint se limita a la alineacion, tactica, familiaridad tactica de
  la plantilla y datos administrativos efimeros. **No clona el mundo completo**
  para cada click tactico, algo costoso en carreras multiliga.
- Los cambios de previa se confirman solamente despues de construir la vista
  valida. La cola anterior y la seleccion de equipaciones sobreviven a un error.
- `SimulationJob` publica la sesion y el estado `completed` bajo la misma
  region critica. Una simulacion fallida nunca se publica. Los trabajos
  finalizados mantienen eventos y el resumen, pero dejan de conservar una
  referencia innecesaria a la sesion privada.
- Se sigue bloqueando la edicion durante la ejecucion de un trabajo asincrono.

## Limites de alcance

- La transaccion de plantilla cubre **la ruta HTTP de edicion**. No reemplaza
  todos los usos directos de `DevelopmentSession` por APIs transaccionales.
- La escritura efectiva de una respuesta HTTP puede fallar por corte de red
  aun despues de confirmar el comando; no existe protocolo de confirmacion
  cliente/servidor. Eso no es equivalente a un error construyendo la vista.
- La cola de progreso conserva sus eventos hasta que sale del historial
  acotado de trabajos; el volumen de eventos se medira en las pruebas de
  escalabilidad general.
- El sistema completo de guardado de carrera sigue pendiente para TS-14/TS-15.
- No se altera el motor de simulacion, el calendario ni la UX.

## Validacion

Los tests nuevos fuerzan fallos de construccion de vistas, de sincronizacion de
familiaridad, de la cola de previa, de las equipaciones y de la coordinacion
entre hilos. Se reproducian antes de aplicar el parche.

En Windows, desde la raiz del proyecto:

```powershell
python -m pytest -ra tests/test_ts_11_session_application_reliability.py
python -m pytest -ra tests/test_ui_shell_squad.py tests/test_ui3_roster.py tests/test_ui35_matchday.py tests/test_ui341_calendar_progress.py
python -m pytest -ra
```

No se requiere Node.js local. Los chequeos JavaScript pueden ejecutarse en CI.

Validacion manual: editar permanentemente una tactica, intercambiar titulares,
modificar un dorsal; preparar un partido con cambios temporales, restablecerlos
y simular; finalmente iniciar una simulacion de varios dias y verificar que el
estado final, el calendario y las tablas coincidan con los resultados.

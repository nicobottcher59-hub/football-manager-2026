# TS-19 - Tactical Studio 2.0: informe de entrega

## Base y alcance

Actualizacion funcional incremental para `main` con TS-19.1.1 integrado, sobre el
proyecto recibido y TS-18.5 revisado, TS-18.6 completo y TS-19.1. No incluye `.git`,
partidas personales, entornos virtuales ni dependencias de Node.

Se implementaron juntos backend, frontend portable, migracion del guardado y pruebas.
TS-20, TS-21 y TS-22 no estan incluidos.

## Resultados ejecutados

| Comprobacion | Resultado real |
| --- | --- |
| Regresion de la base anterior | 1.105 passed, 0 failed; 380,18 s |
| Regresion completa de TS-19 | **1.197 passed, 0 failed, 0 skipped; 516,83 s** |
| Casos nuevos incorporados | 92, incluidos en la regresion completa |
| Casos nuevos con Node excluido del PATH | **90 passed, 2 skipped, 0 failed; 69,45 s** |
| Interacciones en Chromium | **39 comprobaciones aprobadas, 0 errores JS inesperados** |
| Geometria Python / JavaScript | 170 tableros completos contrastados |
| Lote adicional de simulacion | **1.000 partidos, 0 fallos de invariantes** |
| Instalacion limpia: pruebas de humo | **8 passed, 0 failed; 8,08 s** |

Entorno principal: Python 3.13.5, Linux x86_64. Los 516,83 segundos equivalen a
8 minutos y 36,83 segundos. Los conteos de navegador y simulaciones no se suman
al total pytest como si fueran casos adicionales de la suite.

Se preservaron los finales de linea originales de los archivos existentes.
El ZIP se extrajo sobre una copia limpia de la base y se verifico el contenido
archivo por archivo. Ocho pruebas de humo sobre esa instalacion aprobaron,
incluyendo recursos HTTP, geometria JS/Python, biblioteca y planes/guardado.
Una repeticion suplementaria de los 92 tests en esa copia limpia se interrumpio
a los 120 segundos: no se cuenta como aprobada. La regresion principal de 1.197
casos si finalizo y el contenido de codigo aplicado coincide con el validado.

Los registros reproducibles estan en `reports/ts19/`. La suite completa contiene
los tests anteriores; no se presenta la validacion parcial de TS-18 como un resultado
completo. El nuevo resultado completo se obtuvo sobre la base reconstruida.

### Estrés de simulacion

El lote contiene 500 partidos sin planes y 500 con planes programados; ademas realiza
20 repeticiones deterministas. Registro 777 cambios de plan aplicados, 348 reglas
no aplicadas por su condicion, 378 expulsiones y 114 partidos con prorroga. Hubo
125 comprobaciones de reglas de prorroga. Se verificaron integridad estadistica,
participantes, minutos, expulsiones y que el snapshot de entrada no se modificara.

Es estres de partidos sinteticos, no 1.000 temporadas ni una prueba de calibracion
estadistica contra futbol real. Los sistemas de envejecimiento pertenecen a TS-21.

### Interaccion y transporte

Chromium ejecuto los JS/CSS entregados. Un puente en proceso sustituyo el transporte
HTTP por llamadas a la aplicacion Python real. Se probaron arrastre, teclado,
confirmacion/cancelacion, cambios de fase, posicion explicita, biblioteca,
reglas por minuto/marcador, errores recuperables y el flujo Matchday/Quick Sim.

Una prueba HTTP independiente levanto el servidor real y verifico recursos locales,
rutas, revision de estado y comandos rechazados. No se afirma haber realizado
una sesion nativa de Windows. Los anchos probados fueron 1.100, 1.550 y 1.920 px;
no hubo desborde horizontal en esos casos. Lineup mantuvo sus once tarjetas y tamano
uniforme en la comprobacion de navegador.

## Funcionalidades entregadas

- Pizarra con arrastre, alternativa por teclado, deshacer, copia y reinicio por fase.
- Objetivos con y sin posesion independientes; asimetrias sobre las 28 formaciones.
- Cambio explicito de posicion futbolistica; arrastrar no reasigna roles a escondidas.
- Coverage, Vulnerabilities y Laboratory como capas de la misma cancha, con botones
  pequenos abajo y selector de rival dentro del propio laboratorio.
- Biblioteca de hasta 64 plantillas: crear, sobrescribir, cargar, duplicar, renombrar
  y eliminar, sin almacenar ni resucitar alineaciones viejas de jugadores.
- Planes A/B/C y hasta seis reglas por minuto y marcador, con eleccion de plan inicial
  en Matchday y eventos de cambio en el resultado de la simulacion.
- Consumidores del motor rapido para las instrucciones antes pendientes, con efectos
  acotados y contrapartidas documentadas, sin cambiar las formulas OVR/ACT.
- Guardado completo de carrera version 3, migracion explicita de versiones 1/2 y
  fixture real version 2 que contiene un partido jugado.
- Frontend integrado, sin npm ni Node para usarlo en Windows.

## Cambios deliberados en pruebas existentes

Cinco archivos de pruebas previas se ajustaron a cambios funcionales intencionales:

1. `test_ts_12_fast_match_discipline.py`: el ejemplo sin expulsiones con semilla 1
   pasa del marcador 1-6 y tiros 7/24 a 1-5 y tiros 7/22. TS-19 activa instrucciones
   y geometria antes no consumidas. Se mantiene una referencia estricta nueva y la
   repeticion determinista; no se ajustaron coeficientes para forzar el marcador viejo.
   Ambos resultados estan en los JSON de `reports/ts19/`.
2. `test_ts_13_tactical_consumer_coverage.py` y
   `test_ts_18_3_tactical_logic_instructions.py`: el inventario ya no debe declarar
   pendientes los consumidores implementados. Las pruebas nuevas verifican efectos
   en calculos y construccion de acciones, no solo etiquetas del inventario.
3. `test_ts_15_career_save_reliability.py`: una version desconocida sigue rechazandose;
   el ejemplo cambia de version 3 a 100 porque version 3 ahora es valida.
4. `test_ts_17_4_long_career_persistence.py`: la version esperada del grafo pasa a 3.

No se eliminaron pruebas fallidas ni se transformaron fallos en skips. Los dos
skips nuevos sin Node corresponden solo a comprobaciones opcionales de JavaScript.

## Decisiones y limites importantes

- **Plan durante el partido** significa un cambio ejecutado por el motor al cumplirse
  su minuto y condicion, no un boton para alterar un resultado ya calculado. Quick Sim
  termina la simulacion antes de mostrar el informe. Las reglas se eligen antes.
- Programar planes utiliza una ruta cronologica de aleatoriedad. Identica semilla
  con distinta configuracion, version o programacion no implica identico marcador.
- Los mapas son estimaciones geometricas estaticas, no mapas de calor registrados
  ni un pronostico de goles. El color de una alerta no penaliza directamente al equipo.
- Guardar una tactica actualiza la biblioteca de la carrera abierta. Hay que guardar
  la **carrera completa** para conservarla al cerrar el servidor.
- Se conserva el enum de posiciones existente, incluida la representacion RW/LW de
  los marcadores profundos RM/LM. No se agrego una familia posicional nueva.
- El motor 2D heredado recibe los objetivos por fase, pero no se redisenó ni se
  convirtio en motor principal; los nuevos planes se integran al motor rapido.
- Las formulas OVR/ACT se conservan. El motor incorpora nuevos ajustes tacticos
  acotados: esta es una expansion funcional, no un parche de resultados identicos.
- Se usaron eventos nativos de puntero/teclado en el frontend portable existente;
  no se migro a React ni se agrego `@dnd-kit` o una etapa npm en Windows.
- Regresion y estres aprobados no equivalen a ausencia absoluta de bugs ni a balance
  competitivo definitivo. La comprobacion nativa visual en el Windows del usuario
  sigue siendo recomendable antes del merge.

## Instalacion y verificacion

Seguir `TS_19_TACTICAL_STUDIO_INSTRUCTIONS.txt`. Respaldar primero las partidas:
al volver a guardar, la carrera se escribe en version 3. El codigo anterior no esta
comprometido a leer ese nuevo formato; para retroceder usar el respaldo previo.

```text
python tools/verify_ts19_package.py
python -m pytest -ra tests/test_ts_19_tactical_studio.py tests/test_ts_19_tactical_match.py tests/test_ts_19_frontend_contract.py
python -m pytest -ra
```

Sin Node, el resultado de referencia de las pruebas nuevas es 90 passed, 2 skipped.
En la suite completa puede haber otros skips de verificaciones JS anteriores.

El manifiesto registra tamano y SHA-256 de cada archivo del paquete (salvo el propio
manifiesto). No reemplaza `.git` ni instala recursos externos.

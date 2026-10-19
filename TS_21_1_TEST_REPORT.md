# TS-21.1 - Mundo inglés: planteles persistentes e identidades tácticas

## Entrega y alcance

Primera etapa de TS-21, construida sobre el ZIP del proyecto y el hotfix de
LM/RM y arquero fijo. Es una actualización incremental, no un juego independiente.
No necesita Node, npm, compilación frontend ni nuevas dependencias de ejecución.
Las pruebas específicas usan pytest, igual que las anteriores.

Se conservan TS-19 y TS-20. No se entrega todavía el sistema completo de desarrollo
y envejecimiento: no hay CA/PA, aumento o declive de atributos, nuevos planes de
entrenamiento, retiros, canteras ni Newgens en esta etapa.

## 1. El mundo inicial

| División | Clubes activos | Jugadores iniciales |
| --- | ---: | ---: |
| Premier League | 20 | 440 |
| Championship | 24 | 528 |
| League One | 24 | 528 |
| League Two | 24 | 528 |
| Total | 92 | 2.024 |

Cada club tiene 22 jugadores iniciales con identificadores estables, posiciones,
atributos, familiaridades, personalidad y fecha de nacimiento. No se generan
nuevamente al preparar un rival, cargar un guardado completo o cambiar de temporada.
El equipo gestionado conserva sus jugadores previos y recibe los refuerzos
necesarios para completar su plantilla. En una migración no se borran excedentes
para imponer 22: el total puede variar si una partida previa ya contiene más.

La generación es determinista a partir de la identidad del club y la semilla.
La estructura separa el generador ficticio del modelo persistente: una futura
base real puede utilizar el mismo modelo. Esta entrega no incorpora un importador
de jugadores reales ni sustituye identidades dentro de carreras comenzadas.

### Calidad y edades

La liga orienta la calidad inicial y dentro de cada liga existen equipos mejores
y peores. Los rangos se superponen; no son límites individuales ni modificadores
permanentes del motor. La distribución incluye figuras, titulares, suplentes y
edades variadas. Las cualidades se reparten según el perfil futbolístico, no como
22 copias con todos los atributos iguales.

En la semilla inicial comprobada, el OVR contextual medio del once principal
mostró estos valores. Son mediciones de esta base, no estadísticas de ligas reales
ni garantías del balance definitivo:

| División | Mínimo por club | Media | Máximo por club |
| --- | ---: | ---: | ---: |
| Premier | 73,3 | 80,0 | 86,6 |
| Championship | 63,3 | 69,8 | 76,3 |
| League One | 53,3 | 59,8 | 66,3 |
| League Two | 43,3 | 49,8 | 56,4 |

Ascender o descender no cambia los atributos por decreto. Los clubes mantienen
sus futbolistas, sus identificadores y sus capacidades reales.

## 2. Formaciones, tácticas y roles

La generación sigue este orden: nivel del club, identidad táctica, necesidades por
puesto, atributos y profundidad del plantel. Cada equipo tiene un plan principal
y una alternativa compatible. Se utilizan las 28 formaciones existentes como
catálogo; la base inicial ensayada representa 23 formaciones principales.

Se distribuyen 11 estilos existentes: equilibrado, posesión, tiki-taka, presión
constante, contrapresión, contraataque, contraataque directo, catenaccio, bloque
bajo, juego directo y ataque por bandas. Cada división tiene variedad de estilos.
Los planes contienen instrucciones de equipo reales y roles explícitos por puesto,
con pequeñas variaciones entre clubes; no son solamente un nombre o una formación.

El generador adapta los perfiles de atributos y familiaridades a esos roles.
Los roles utilizan las instrucciones individuales ya existentes. El simulador
recibe esos mismos planes e instrucciones al disputar partidos, tanto contra
el usuario como entre rivales ingleses en segundo plano.

### Coherencia del plantel

Se generan dos futbolistas por puesto de la formación principal, sin duplicar
una persona en la comprobación de profundidad. Por ejemplo:

| Sistema | Arqueros | Centrales naturales | Laterales/carrileros | Medios centrales | Bandas | Delanteros |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4-3-3 | 2 | 4 | 4 | 6 | 4 | 2 |
| 4-4-2 | 2 | 4 | 4 | 4 | 4 | 4 |
| 5-3-2 | 2 | 6 | 4 | 6 | 0 | 4 |
| 3-4-3 | 2 | 6 | 4 | 4 | 4 | 2 |

Los sistemas de tres centrales se generan con seis centrales naturales; no se
cubren esas necesidades contando laterales improvisados. Los carrileros conservan
su lugar propio. Los futbolistas polivalentes tienen posiciones secundarias
compatibles y familiaridad suficiente; no pueden contarse dos veces para ocupar
dos puestos simultáneos. La selección de once utiliza asignación óptima y jugadores
únicos, respeta disponibilidad y considera posición, rol, familiaridad y estado.

Estos repartos gobiernan la generación nueva. No se redistribuyen arbitrariamente
los puestos ni atributos de jugadores que ya estaban en una partida del usuario.

## 3. Simulación y continuidad

Los partidos que involucran clubes ingleses registrados se resuelven con sus
planteles persistentes y el simulador rápido existente. Se elimina, para esos
rivales, la reconstrucción de un plantel en función de la fuerza del usuario.

Se registran apariciones, minutos, goles, asistencias y datos agregados de
valoración cuando un resultado se confirma. La condición, la recuperación, la moral
y las familiaridades usan las reglas existentes. Esto no es todavía progresión
permanente de atributos. Las operaciones de partido tienen rollback de jugadores
y registros para evitar estados parciales ante un error.

Los equipos extranjeros siguen fuera de esta ampliación. Un encuentro entre dos
clubes externos puede conservar la resolución agregada anterior. No se ha creado
un mundo persistente extranjero, un mercado de fichajes autónomo nuevo ni un
nuevo sistema integral de sustituciones.

### Límite inferior de la pirámide

Se respeta la política de ascensos y descensos que ya traía el proyecto. Al salir
dos equipos de League Two, se conservan sus jugadores en el registro fuera de
las cuatro divisiones activas, sin inventar una quinta liga simulada. Los dos
nuevos entrantes externos reciben su plantilla una sola vez.

Por eso, tras el primer cambio de temporada siguen existiendo 92 equipos y 2.024
jugadores activos en las cuatro ligas, pero el registro total retiene 94 equipos
y 2.068 jugadores en una carrera nueva normal. No se eliminan los salientes.
Esto no reemplaza el futuro sistema de canteras y recambio generacional.

## 4. Consulta desde la interfaz portable

Dentro de Competitions / Other Leagues, al abrir una división inglesa aparece
**Club squads & tactical identities**, debajo del explorador existente.
**Inspect club** permite consultar cada equipo. Los apartados **Primary plan** y
**Alternative plan** muestran formación, estilo, roles y grupos de instrucciones.
La tabla contiene los jugadores reales del registro y permite expandir atributos.

El once de otros clubes es una referencia de sus mejores jugadores disponibles,
no una promesa de su próxima alineación. Las estadísticas muestran solo partidos
registrados desde la fecha de seguimiento. No se revela la personalidad oculta.
La consulta no avanza fechas, no entrena jugadores y no cambia la partida.

La implementación usa JavaScript y CSS nativos, sin build ni Node.
No se adjuntan imágenes ni se añade una sección lateral nueva.

## 5. Guardados y compatibilidad

El guardado completo pasa a versión 5 para incluir clubes, identidades, jugadores,
estadísticas y referencias compartidas. Las versiones anteriores compatibles se
validan y migran en memoria. Cargar no sobrescribe el archivo original; guardar
posteriormente en v5 requiere conservar esta actualización.

Se preservan jugadores existentes, atributos, tácticas, relaciones, resultados y
referencias canónicas. Las relaciones antiguas de TS-20 y la moral se conservan al
incorporar a los jugadores que completan el plantel. No se inventan minutos de
rivales anteriores a la migración. Hay una fixture sintética v4 generada con el
código anterior para probar la migración real, además de pruebas previas v2/v3.

**Esta entrega no agrega autoguardado ni una nueva pantalla de guardar/cargar.**
La persistencia está integrada en el guardado SQLite completo ya existente.
Cerrar sin guardar sigue sin conservar la sesión. Los exportadores de resultados
JSON no contienen el estado completo de los jugadores: al importar resultados
se reinicia el seguimiento actual, no se reconstruye una carrera histórica completa.
Conviene conservar copias de los SQLite antes de instalar o convertir guardados.

Se comprobó que los archivos de fórmulas OVR/ACT, catálogo de roles,
familiaridad posicional, familiaridad táctica y motor rápido son idénticos a los
de la base. No se cambiaron esas fórmulas ni se deshizo el hotfix LM/RM/arquero.
Los manifiestos de paquetes anteriores pueden detectar como modificados algunos
archivos actualizados legítimamente por TS-21.1: para esta entrega se usa su propio
verificador, no se intenta que hashes históricos sigan coincidiendo.

## 6. Pruebas ejecutadas

Entorno: Linux del contenedor, Python 3.13. Las baterías indicadas como sin Node
se lanzaron con PATH restringido para que Node/npm no estuvieran disponibles.
No se ejecutó una instalación nativa en Windows ni la suite completa del repositorio.

| Comprobación | Resultado |
| --- | --- |
| TS-21.1: generación, 28 formaciones, 11 estilos, roles, mundo, API, transacciones, migración | 76 passed, 26,21 s; sin Node |
| Regresión dirigida TS-19, TS-20, transacciones TS-04 y oposición TS-18.5 | 134 passed, 2 skipped, 283,00 s; sin Node |
| Guardado completo y fiabilidad TS-15 | 21 passed, 301,35 s; sin Node |
| Compatibilidad del modo DEV favorable con planteles persistentes | 1 passed, 5,69 s; sin Node |
| Interfaz nueva en Chromium: 4 divisiones, planteles, roles, instrucciones, errores/reintentos | 24 comprobaciones aprobadas; 0 excepciones JavaScript |
| Temporada completa, cambio de temporada y SQLite | PASS; 130,41 s; sin Node |

Las dos omisiones son comprobaciones opcionales de sintaxis con Node de TS-19
y TS-20. No son funcionalidades omitidas del juego. Los 76 tests nuevos no
requieren Node y no omiten casos por su ausencia.

La validación de interfaz se ejecutó con el código JavaScript real y respuestas
reales del modelo de lectura cargadas en memoria. La navegación HTTP de Chromium
está bloqueada por la política del entorno, por lo que no se presenta como una
prueba manual end-to-end de toda la aplicación. Los endpoints HTTP y los recursos
estáticos se verificaron aparte mediante pruebas Python reales.

La prueba larga resolvió **2.959 de 2.959 partidos**, incluidos **51 partidos del
equipo gestionado**. Hubo **1.853 futbolistas con apariciones registradas**;
no todos los 2.024 tienen por qué jugar. Pasó a **2027/28**, conservó los jugadores
y atributos originales, disputó otros dos partidos gestionados y verificó
SQLite después del cambio de temporada. Esto comprueba continuidad a ese alcance;
no certifica balance de 15 temporadas ni sistemas de envejecimiento aún ausentes.

### Comandos reproducibles

Desde la raíz del proyecto:

```text
python tools/verify_ts21_english_world_package.py
python -m pytest -ra tests/test_ts_21_english_world.py
```

Prueba larga aislada, sin abrir ni modificar partidas reales:

```text
python tools/check_ts21_full_season.py
```

Regresión dirigida ejecutada:

```text
python -m pytest -ra tests/test_ts_19_placement_heatmap.py tests/test_ts_20_dressing_room.py tests/test_ts_20_frontend.py tests/test_ts_20_integration.py tests/test_ts_04_managed_match_transactions.py tests/test_ts_18_5_opposition_ai_reliability.py
python -m pytest -ra tests/test_ts_15_career_save_reliability.py
```

## 7. Instalación

Cerrá el juego, hacé copia del proyecto y de los SQLite, y extraé el ZIP en la
raíz donde está INICIAR_INTERFAZ_WINDOWS.bat, conservando rutas y reemplazando
los archivos. La base requerida es TS-20 con el hotfix TS-19 de LM/RM y arquero.
Ejecutá el verificador, reiniciá con el BAT y recargá con Ctrl + F5.

El manifiesto SHA-256 valida los archivos entregados, no sustituye las pruebas
funcionales ni constituye una firma digital de autenticidad. No se distribuye
.git, cachés, dependencias, partidas del usuario ni imágenes.


### Verificación del paquete e instalación limpia

Se reconstruyó una instalación limpia desde football-manager-game.zip, se aplicó
el hotfix TS-19-LM-RM-Arquero-Fijo y luego este ZIP incremental. El verificador
comprobó todos los archivos del paquete y los 76 tests nuevos volvieron a pasar
en esa copia independiente, con Node ausente del PATH.

El ZIP contiene 28 archivos: 27 con tamaño y SHA-256 registrados, más el propio
manifiesto. Se verificó el CRC de todo el ZIP. También se probó que el verificador
rechaza un archivo modificado o faltante y vuelve a aceptar el paquete restaurado.
La fixture SQLite comprimida incluida es sintética, no una partida del usuario.

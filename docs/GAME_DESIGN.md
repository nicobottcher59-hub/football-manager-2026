# Game Design Document

## 1. Visión general

El proyecto consiste en un simulador de gestión futbolística inspirado en juegos como Football Manager y los modos carrera de EA Sports FC.

El jugador asumirá funciones de entrenador, director deportivo y eventualmente gestión institucional del club.

No habrá jugabilidad directa de los partidos. El fútbol será resuelto mediante un motor de simulación.

El objetivo principal es construir un mundo futbolístico dinámico en el que las situaciones surjan de la interacción entre múltiples sistemas, en lugar de depender principalmente de eventos predeterminados o guionados.

---

# 2. Principios fundamentales

## 2.1 La temporada no está predeterminada

Al comenzar una temporada pueden definirse elementos como:

- calendario;
- competiciones;
- planteles;
- contratos;
- situación económica;
- estado inicial de los clubes.

Pero los resultados deportivos nunca deben calcularse previamente.

Cada partido se simulará cuando llegue el momento de disputarlo utilizando el estado actual del mundo.

Por lo tanto, un partido debe considerar, entre otras cosas:

- jugadores disponibles;
- XI titular;
- suplentes;
- lesiones;
- suspensiones;
- condición física;
- fatiga;
- forma;
- táctica;
- familiaridad táctica;
- familiaridad posicional;
- química entre jugadores;
- localía;
- características del rival.

Las consecuencias de un partido modifican el estado del mundo y, por lo tanto, pueden afectar partidos posteriores.

---

# 3. Filosofía de simulación

El juego debe intentar producir historias mediante sistemas.

No se busca crear situaciones mediante eventos arbitrarios como:

> "Jugador joven se convierte en estrella."

En cambio, deberían poder ocurrir situaciones como:

1. El delantero titular se lesiona.
2. Un juvenil recibe minutos.
3. El juvenil juega bien.
4. Mejora su forma y confianza.
5. Empieza a disputar la titularidad.
6. Otros clubes comienzan a interesarse.
7. Su situación contractual cambia.
8. Puede terminar convirtiéndose en una pieza importante del equipo.

La historia aparece como consecuencia del sistema.

---

# 4. Jugadores

Los jugadores no deben estar representados únicamente mediante una valoración general.

Cada jugador tendrá diferentes grupos de información.

## 4.1 Identidad

Ejemplos:

- ID interno;
- nombre;
- apellido;
- fecha de nacimiento;
- nacionalidad.

El código nunca debe depender del nombre visible de un jugador.

Los jugadores serán identificados mediante IDs internos.

---

## 4.2 Atributos

Los atributos representan las capacidades relativamente estables del jugador.

Ejemplos:

- técnica;
- pase;
- definición;
- visión;
- control;
- marcaje;
- entradas;
- posicionamiento;
- velocidad;
- aceleración;
- resistencia;
- fuerza;
- inteligencia táctica.

Los atributos pueden evolucionar con el tiempo, pero no deben cambiar drásticamente únicamente por uno o dos partidos.

---

## 4.3 Estado actual

Debe existir una separación entre capacidad y estado actual.

Ejemplos de estado:

- forma;
- moral;
- confianza;
- condición física;
- fatiga;
- ritmo competitivo;
- lesiones;
- molestias;
- suspensión.

Un gran jugador puede atravesar un mal momento sin dejar de ser un gran jugador.

## 4.4 OVR y ACT

La interfaz distinguirá dos valoraciones conceptualmente diferentes:

```text
◆ OVR
= calidad estructural del futbolista

◇ ACT
= cuánto de esa calidad está pudiendo expresar en su contexto actual
```

`OVR` se deriva de los atributos mediante ponderaciones apropiadas; no es un atributo independiente ni debe resolver acciones por sí solo. Cambia lentamente cuando evolucionan o declinan las capacidades reales del jugador.

`ACT` puede estar por encima o por debajo de OVR y considera factores como:

- familiaridad posicional;
- familiaridad de rol;
- familiaridad táctica;
- forma;
- confianza;
- química;
- ritmo competitivo;
- condición física.

Las escalas contextuales positivas utilizan aproximadamente `65` como zona neutral: por encima pueden ayudar y por debajo pueden perjudicar. La condición física es una excepción: estar fresco no otorga un bonus por encima del nivel normal; la penalización aparece cuando la condición cae.

No existe un “Overall por rol”. Un extremo de 84 sigue siendo un jugador de 84 aunque sea utilizado de 9 o de central; lo que cambia es cuánto puede expresar de su nivel en esa función.

## 4.5 Progresión no garantizada

Acumular minutos no garantiza progresar.

Un fichaje joven puede:

- no adaptarse;
- rendir mal;
- perder confianza;
- estancar su desarrollo;
- deteriorar atributos a largo plazo;
- terminar siendo un fichaje fallido.

El aprendizaje de una posición, rol o sistema depende de minutos, adaptabilidad, inteligencia táctica, entrenamiento, similitud, rendimiento y confianza. Algunos jugadores pueden no dominar nunca una función nueva.

Los cambios de forma/confianza son de corto plazo; familiaridades y química evolucionan en semanas/meses; atributos y OVR cambian en escalas de meses/temporadas.

---

# 5. Posiciones dinámicas

Los jugadores no tendrán una única posición rígida.

Cada jugador tendrá un grado de familiaridad con diferentes posiciones.

Ejemplo:

- Extremo izquierdo: 95
- Extremo derecho: 82
- Mediocampista ofensivo: 70
- Delantero centro: 45

La familiaridad posicional podrá evolucionar.

Un jugador que comienza a jugar regularmente en una nueva posición puede adaptarse progresivamente.

La adaptación dependerá de factores como:

- minutos jugados;
- entrenamiento;
- rendimiento;
- inteligencia táctica;
- edad;
- atributos;
- similitud con posiciones conocidas.

Acumular minutos no garantiza una adaptación perfecta.

---

# 6. Posición principal dinámica

La posición principal de un jugador podrá cambiar a lo largo de su carrera.

Ejemplo:

Jugador comienza como:

> Extremo izquierdo

y después de varias temporadas puede convertirse principalmente en:

> Delantero centro

El sistema deberá conservar información sobre su formación y experiencia previa.

Una posición abandonada durante años no necesariamente debe olvidarse completamente.

---

# 7. Posición y rol son conceptos diferentes

Jugar como delantero centro no define completamente el comportamiento de un jugador.

Ejemplos de roles:

- delantero avanzado;
- falso 9;
- delantero presionante;
- hombre objetivo;
- segundo delantero;
- finalizador.

Un jugador puede ser muy efectivo como falso 9 y poco efectivo como hombre objetivo aunque ambas funciones utilicen la posición de delantero centro.

La compatibilidad con un rol dependerá principalmente de sus atributos y experiencia.

---

# 8. Química entre jugadores

Los jugadores podrán desarrollar relaciones futbolísticas entre sí.

No se utilizará únicamente una barra global de química.

La relación puede contemplar variables como:

- entendimiento táctico;
- experiencia jugando juntos;
- confianza futbolística;
- relación personal;
- compatibilidad de estilos.

La relación personal y el entendimiento futbolístico deben ser conceptos diferentes.

Dos jugadores pueden:

- llevarse bien y jugar mal juntos;
- llevarse mal personalmente y entenderse perfectamente dentro del campo.

---

# 9. Efectos de la química

La química no debe convertirse simplemente en un bonus general de atributos.

Debe influir sobre acciones concretas.

Ejemplos:

- coordinación de movimientos;
- pases al espacio;
- paredes;
- coberturas;
- presión coordinada;
- movimientos ofensivos;
- automatismos defensivos.

Ejemplo:

Un mediapunta conoce perfectamente los movimientos del delantero con el que lleva jugando varias temporadas.

Puede anticipar mejor cuándo realizará un desmarque.

---

# 10. Química colectiva

Además de relaciones entre dos jugadores, eventualmente podrán desarrollarse automatismos entre grupos.

Ejemplos:

- pareja de centrales;
- lateral + extremo;
- mediocentro + centrales;
- triángulo lateral-interior-extremo.

El tiempo jugando juntos puede aumentar la coordinación colectiva.

---

# 11. Tácticas

Las tácticas deberán tener una influencia real sobre el resultado de los partidos.

El equipo con mejores jugadores no debe ganar automáticamente.

La calidad del plantel será una ventaja, pero solo una parte de la simulación.

Un partido debe surgir aproximadamente de:

Calidad de jugadores
+
Táctica
+
Ejecución táctica
+
Estado actual
+
Interacción con el rival
+
Contexto
+
Variabilidad natural del fútbol

---

# 12. No existe una táctica universalmente superior

No debe existir una lógica simple como:

> 4-3-3 vence a 4-4-2.

Las tácticas deberán interactuar mediante sus características.

Ejemplos:

- altura de la línea defensiva;
- intensidad de presión;
- anchura;
- ritmo;
- salida de balón;
- juego directo;
- ataques posicionales;
- transiciones;
- comportamiento de laterales;
- ocupación de espacios.

Una táctica puede ser especialmente efectiva contra otra por las situaciones que genera.

---

# 13. Matchups tácticos

Ejemplo:

Equipo A:

- defensa muy adelantada;
- presión alta;
- laterales ofensivos.

Equipo B:

- bloque bajo;
- transición rápida;
- delanteros veloces;
- ataques al espacio.

Aunque el Equipo B tenga jugadores inferiores, su estrategia puede explotar espacios que deja el Equipo A.

La efectividad también dependerá de que los jugadores del Equipo B tengan atributos adecuados para ejecutar ese plan.

El objetivo es que el juego sea un simulador de DT y no un simulador de “tener mejores jugadores”. Una diferencia moderada de calidad puede ser compensada por una selección correcta, un contra-plan adecuado y una ejecución colectiva superior.

Esto no debe implementarse mediante un bonus genérico de “buena táctica”. Una idea correctamente ejecutada pero mal elegida contra ese rival puede rendir peor que un plan más apropiado.

---

# 14. Familiaridad táctica

Los equipos deben aprender las tácticas que utilizan.

La familiaridad no será necesariamente una única valoración.

Puede existir familiaridad con diferentes conceptos:

- formación;
- presión;
- altura defensiva;
- estilo de salida;
- ritmo;
- transiciones;
- marcaje;
- anchura.

Ejemplo:

- 4-3-3: 92
- 4-2-3-1: 75
- 3-4-2-1: 40

Cambiar de formación no significa necesariamente perder todo el conocimiento táctico si se mantienen principios similares.

---

# 15. Familiaridad individual

La familiaridad táctica también debe existir a nivel de jugador.

Un fichaje nuevo puede ingresar a un equipo que domina perfectamente un sistema, pero necesitar tiempo para comprenderlo.

La adaptación dependerá de:

- tiempo;
- entrenamiento;
- minutos;
- inteligencia táctica;
- experiencia previa en sistemas similares.

---

# 16. Consistencia vs flexibilidad

Utilizar constantemente una táctica puede generar:

- mejores automatismos;
- mayor coordinación;
- menos errores;
- mejor interpretación de movimientos.

Cambiar tácticas frecuentemente puede permitir:

- explotar debilidades concretas;
- sorprender rivales;
- adaptarse a distintos partidos.

Pero también puede provocar:

- menor familiaridad;
- errores de ejecución;
- falta de automatismos;
- menor estabilidad colectiva.

No debe existir una estrategia automáticamente correcta.

---

# 17. Preparación específica de partidos

El jugador podrá preparar planes específicos para determinados rivales.

La calidad teórica del plan y la capacidad del equipo para ejecutarlo serán conceptos separados.

Una gran idea táctica puede fallar si los jugadores:

- no están familiarizados;
- no tienen los atributos adecuados;
- interpretan mal los movimientos;
- tienen poco tiempo de preparación.

---

# 18. Rivales y adaptación

A largo plazo, los equipos controlados por IA deberán analizar a sus rivales.

Un equipo que utiliza siempre exactamente los mismos patrones puede volverse más predecible.

Esto no debe generar una penalización artificial.

Los rivales simplemente podrán conocer mejor:

- dónde presionar;
- cómo defender determinados movimientos;
- qué espacios atacar;
- qué jugadores son clave.

---

# 19. Simulación del partido

El resultado no debe decidirse directamente.

El motor debe producir situaciones futbolísticas.

Conceptualmente:

Estado actual de los equipos
↓
Tácticas
↓
Interacción táctica
↓
Ejecución
↓
Posesiones / situaciones
↓
Ocasiones
↓
Remates
↓
Goles
↓
Resultado

Esto permite que el resultado surja naturalmente.

## 19.1 Dos caminos de resolución

El juego tendrá dos formas de resolver partidos, desacopladas del resto del mundo:

```text
Fast Match Simulator
→ todos los partidos ajenos
→ Quick Sim del partido del usuario
→ camino oficial para temporadas y competiciones

2D Match Engine V2 (futuro)
→ opción de ver/dirigir el partido del equipo del usuario
→ cambios tácticos y sustituciones en vivo
```

El motor 2D legacy de Phase 5.0-5.9 queda congelado. El futuro 2D se reconstruirá desde fundamentos y no bloqueará el desarrollo del resto del juego.

Ambos caminos deberán respetar la misma frontera conceptual:

```text
MatchSnapshot → simulación → resultado/consecuencias
```

---

# 20. El peor equipo puede ganar

La calidad aumenta las probabilidades de producir mejores situaciones, pero nunca garantiza un resultado.

Ejemplo:

Equipo superior:

- 18 remates;
- 2.1 xG.

Equipo inferior:

- 5 remates;
- 0.7 xG.

El resultado puede ser:

> 0-1

sin necesidad de activar artificialmente un evento de sorpresa.

El fútbol debe conservar una cantidad razonable de variabilidad.

---

# 21. Resultado y rendimiento son diferentes

Dos partidos pueden terminar con el mismo resultado pero haber sido completamente distintos.

Ejemplo A:

- Equipo A: 2.4 xG
- Equipo B: 0.3 xG
- Resultado: 0-1

Ejemplo B:

- Equipo A: 0.6 xG
- Equipo B: 1.5 xG
- Resultado: 0-1

Esto será importante para:

- estadísticas;
- evaluación de rendimiento;
- moral;
- confianza;
- análisis táctico;
- prensa;
- decisiones de IA.

---

# 22. XI titular real

Los equipos no tendrán únicamente un nivel general.

El Match Engine debe utilizar los jugadores que efectivamente participan.

Por lo tanto:

- jugar con suplentes modifica el rendimiento;
- las lesiones importan;
- las suspensiones importan;
- las rotaciones importan;
- las posiciones utilizadas importan.

El rendimiento del equipo debe surgir de los jugadores disponibles y elegidos.

---

# 23. Sustituciones

A largo plazo, las sustituciones deberán modificar el estado del partido.

Un jugador que entra puede aportar:

- diferentes atributos;
- mayor energía;
- características tácticas distintas;
- diferente familiaridad;
- distinta química.

El partido después de una sustitución no debe utilizar exactamente las mismas condiciones que antes.

## 23.1 Condición, resistencia y recuperación

La condición física debe crear decisiones reales de rotación.

Durante un partido, `stamina` es el principal atributo de resistencia al esfuerzo. El desgaste depende también de posición, rol y carga táctica. Presionar alto, jugar a gran ritmo o recorrer constantemente grandes distancias tiene un costo físico.

`condition` representa la frescura actual. Un jugador de campo que comienza fresco debe terminar un partido normal claramente desgastado; la prórroga profundiza ese desgaste de forma no lineal.

Entre partidos, `natural_fitness` es el principal atributo de recuperación y `stamina` también contribuye. El calendario debe importar:

- una semana limpia normalmente permite recuperar un partido de 90 minutos;
- pocos días entre partidos generan una decisión de rotación;
- 120 minutos pueden dejar secuelas incluso una semana después.

`fatigue` representa deuda física acumulada y no debe aplicarse como una segunda penalización directa si esa misma carga ya se expresa mediante `condition`.

En un futuro 2D, la condition podrá modificar una efectividad interna minuto a minuto para que un suplente fresco pueda convertirse en una mejor opción que un titular superior pero exhausto.

---

# 24. Consecuencias de los partidos

El Match Engine debe devolver información suficiente para actualizar el mundo.

Ejemplos:

- resultado;
- goles;
- asistencias;
- minutos;
- remates;
- xG;
- tarjetas;
- lesiones;
- fatiga;
- rendimiento individual.

Posteriormente otro sistema actualizará:

- tabla;
- estadísticas;
- forma;
- condición;
- moral;
- familiaridad;
- relaciones;
- suspensiones.

---

# 25. Separación entre simulación y estado del mundo

El Match Engine no debe modificar directamente toda la base de datos durante la simulación.

Idealmente:

1. Se crea un snapshot del partido.
2. El Match Engine recibe ese estado.
3. Simula el encuentro.
4. Devuelve un resultado y eventos.
5. Otro sistema aplica las consecuencias al mundo.

Esto permitirá:

- testing;
- debugging;
- reproducibilidad;
- análisis;
- cambios futuros del motor.

---

# 26. Seeds y reproducibilidad

El motor utilizará generación aleatoria controlable mediante seeds.

Con:

> mismo estado inicial + misma seed

el partido debe poder reproducirse exactamente.

Esto será especialmente importante para debugging y testing.

---

# 27. Datos y nombres reales

Durante el desarrollo se podrán utilizar nombres reales para facilitar el trabajo.

Sin embargo, la lógica del juego nunca deberá depender directamente de esos nombres.

Ejemplo:

Incorrecto:

if club.name == "River Plate"

Correcto:

utilizar IDs y propiedades del club.

Los datos deben poder reemplazarse sin modificar el motor.

---

# 28. Data packs y mods

A largo plazo se busca permitir diferentes bases de datos.

Ejemplo:

- database_default;
- database_real;
- database_custom.

Elementos como:

- nombres;
- jugadores;
- clubes;
- competiciones;
- escudos;
- kits;
- imágenes;

deberán estar desacoplados de la lógica principal.

---

# 29. Filosofía de desarrollo

El proyecto será construido de forma incremental.

No se intentará implementar todo Football Manager desde el comienzo.

Cada versión deberá producir un sistema funcional sobre el cual se agregará profundidad.

La prioridad es construir buenas bases de simulación antes que una interfaz compleja.

---

# 30. Primera meta técnica

La primera gran meta será poder simular correctamente un único partido.

El partido deberá considerar inicialmente:

- jugadores;
- XI titular;
- atributos;
- posiciones;
- familiaridad posicional;
- forma;
- condición física;
- táctica básica;
- familiaridad táctica;
- localía;
- componente aleatorio.

A partir de ese núcleo se incorporarán progresivamente sistemas más avanzados.

---

# 31. Objetivo de largo plazo

El objetivo final no consiste únicamente en obtener resultados realistas.

El objetivo es crear un mundo futbolístico en el que:

- los futbolistas evolucionen;
- las relaciones evolucionen;
- las tácticas evolucionen;
- los clubes evolucionen;
- las decisiones tengan consecuencias;
- aparezcan situaciones no previstas por el desarrollador;
- cada partida pueda generar su propia historia.

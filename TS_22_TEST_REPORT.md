# TS-22 - Squad & Match Presentation

## Base y alcance

Incremental sobre TS-21.1.1 Optimización y Calendario, conservando TS-19, su
hotfix LM/RM-arquero, TS-20 y los planteles persistentes de TS-21.1. Implementado
para la interfaz portable que inicia INICIAR_INTERFAZ_WINDOWS.bat. No se requiere
Node, npm, un build de frontend ni GitHub Actions para instalar o jugar.

No es un rebrand: se conservan la estructura de Home/Squad/Tactics, la identidad
visual, tablas, filtros y las canchas del prepartido. No se agrega una nueva
sección permanente a la barra lateral. El desarrollo y envejecimiento de TS-21.2
no forman parte de esta entrega.

## 1. Squad, perfiles y gráficos

- El nombre del jugador abre sus detalles; el botón +/Más mantiene separado el
  menú contextual. En clubes rivales no permite editar jugadores ni alineaciones.
- Los detalles incorporan dos radares SVG nativos: capacidades generales y
  atributos relevantes del rol inspeccionado. No necesitan librerías gráficas.
- El radar general agrupa atributos mediante medias aritméticas. El de rol utiliza
  hasta seis atributos de mayor peso del catálogo real del motor. Hay definiciones
  y valores accesibles debajo de los gráficos, y un perfil propio para arqueros.
- Inspeccionar otra posición o rol no cambia la táctica ni el entrenamiento.
  Las respuestas tardías de consultas anteriores no reemplazan la última selección.
- Familiaridades y atributos existentes permanecen visibles. Los radares no son
  CA/PA, proyecciones de potencial ni una nueva fórmula de valoración.
- La evolución figura como no disponible hasta que exista historial real de
  atributos. No se inventan flechas y no se confunde cansancio con declive.

## 2. GRL actual y Match Center integrado

La GRL actual (ACT) pasa a ser el valor principal en las fichas de Tactics y en
el resumen táctico de Home. OVR base sigue disponible en el detalle/contexto
correspondiente. No se cambian las fórmulas de OVR, ACT, roles o familiaridades.

El prepartido conserva su diseño y agrega GRL actual y condición porcentual a
los titulares y suplentes de ambos equipos. Los titulares usan su puesto, rol y
contexto táctico efectivos; el banco muestra su contexto individual, no una
posición de entrada supuesta. La distribución visual evita que los indicadores
se superpongan innecesariamente, sin cambiar coordenadas tácticas del motor.

Match Center ocupa la pantalla del juego en la misma pestaña. Las rutas de
Home, club, jugador y partido utilizan el historial de navegación de la app.
Consultar un club y volver conserva la preparación temporal del partido.
Un reintento de Quick Sim para el mismo último encuentro devuelve su resumen,
sin repetir resultado, minutos, goles, cansancio ni otras consecuencias.

Recargar el navegador conserva esa preparación mientras el servidor Python
permanece activo. Esto NO es autoguardado: reiniciar el servidor requiere cargar
un guardado completo. Las instrucciones temporales del prepartido siguen siendo
estado de sesión, no un nuevo formato de guardado de partidas en vivo.

## 3. Estadísticas reales de temporada

Season stats consulta acumulados por identificador de jugador, temporada y
competición. Incluye apariciones, titularidades, minutos, goles, asistencias,
porterías a cero, xG, tiros, tiros al arco, porcentaje de pases, amarillas,
rojas y nota media de partido. xA y entradas/tackles no tienen un contador
completo en esta base y se ocultan: no se rellenan con ceros ficticios.

Definiciones importantes:

- Participar requiere minutos de juego; estar en el banco no suma una aparición.
- El porcentaje de pases usa completados/intentos acumulados, no la media simple
  de porcentajes de cada encuentro. La nota media es la media de calificaciones
  registradas y NO equivale a GRL/ACT.
- Portería a cero: arquero o defensor con al menos 60 minutos, con cero goles
  recibidos por su equipo en ese partido. Es una definición explícita de esta
  entrega, no un cálculo del intervalo individual de goles concedidos.
- Las tandas de penales no suman goles, tiros, asistencias o xG al registro.
- El registro se integra en la misma transacción del resultado. Un fallo revierte
  el conjunto; guardar/cargar o repetir solicitudes no duplica estadísticas.
- Se usa el mismo registro para el usuario y los clubes persistentes de la IA.
  Al abrir Squad se leen acumulados, sin reconstruir todos los partidos.
- Se pueden filtrar temporadas y competiciones. Al cambiar de temporada los
  contadores nuevos comienzan en cero y el historial disponible se conserva.

### Carreras anteriores

Las partidas antiguas conservan los totales básicos verificados que ya contenían.
El seguimiento detallado comienza con cobertura explícita desde la migración.
No se asignan a una competición goles históricos cuyo desglose no se guardó.
Tampoco se reejecutan partidos para fabricar detalles perdidos. Un guion puede
seguir apareciendo donde el dato sea desconocido; cero significa un cero real.
La interfaz informa si está mostrando la temporada completa o partidos registrados.

## 4. Clubes rivales

El nombre o escudo del club abre una vista reutilizable de Squad en modo consulta,
desde Home, tablas y copas, calendario, resultados y prepartido. Los jugadores
abren sus detalles y radares con el mismo componente de Squad.

Se muestran hasta cinco resultados recientes, competición/posición, país y los
datos de ubicación/estadio/capacidad que realmente existan. Un dato ausente aparece
como no registrado. La identidad táctica principal y alternativa se consulta
sin editarla; no es una confirmación del próximo once rival.

El estado físico consultado se identifica con su fecha de registro. Abrir un
club no recupera artificialmente a sus jugadores ni altera la simulación.
Los clubes externos que todavía no tienen plantilla persistente muestran esa
limitación; no se genera un plantel nuevo al visitarlos. Las negociaciones y
el interés siguen pendientes, no son botones con acciones ficticias.

## 5. Competiciones dentro de Home

Las pestañas cambian el contenido dentro del recuadro. Al entrar se prioriza la
competición del próximo partido; luego se respeta la selección del usuario
mientras permanezca en Home. Ver competición abre explícitamente el centro completo.

Las fases de liga/grupos muestran una tabla compacta alrededor del equipo. En
eliminatorias se muestra el cruce propio, ronda, fechas, resultados, global y
penales cuando corresponda. Se señala clasificación, eliminación o título.

No se inventa el siguiente adversario: las rondas sucesivas del motor actual se
resuelven mediante sorteos. Mientras no estén definidas se informa pendiente de
sorteo. El componente admite un siguiente cruce si un formato futuro expone una
conexión real en su cuadro; esta entrega no fabrica ese enlace.

## 6. Northbridge: ajuste inicial separado

Las carreras nuevas usan una base inicial cinco puntos inferior en los atributos
de los 18 jugadores originales de Northbridge, conservando sus diferencias de
perfil. El once inicial en sus puestos/roles originales queda entre 80 y 81 de
OVR base, verificado por pruebas. Los otros cuatro jugadores incorporados por
el generador no reciben una segunda rebaja.

En partidas existentes no se aplica al cargar. En Squad aparece un aviso
opcional **Review and apply** solo si hay originales elegibles. Exige confirmación,
se aplica una vez y excluye jugadores que ya tengan atributos modificados o no
coincidan con la plantilla original identificada. No rebaja fichajes ni otros
clubes. Es necesario guardar la carrera para conservar la decisión.

El ajuste no promete 80-81 para cualquier once modificado de una carrera en curso.
No toca condición, fatiga, familiaridades, personalidad ni resultados anteriores.
No establece un límite permanente y no aumenta artificialmente la penalización
por cansancio. No se afirma haber recalibrado el equilibrio competitivo global.

## 7. Instalación y guardados

1. Guardar la carrera y conservar una copia externa del proyecto y de sus slots.
2. Cerrar el juego y el servidor Python. Instalar sobre TS-21.1.1 descomprimiendo
   en la raíz, junto a INICIAR_INTERFAZ_WINDOWS.bat, conservando rutas.
3. Ejecutar `python tools/verify_ts22_package.py`.
4. Ejecutar `python -m pytest -ra tests/test_ts_22_presentation.py`.
5. Reiniciar con el BAT habitual y recargar con Ctrl + F5. Cargar el slot completo.

El estado de carrera completo pasa a versión 6, con lectura/migración de las
versiones anteriores compatibles. Los fixtures heredados verificados incluyen
estados v2, v3 y v5. El archivo antiguo no se sobrescribe por el mero hecho de
cargarlo; la versión nueva se escribe al guardar. Para volver a una versión del
juego anterior a TS-22 se debe usar la copia del guardado anterior.

Usar los slots SQLite completos. El JSON de resultados sigue sin ser un guardado
completo del mundo, estadísticas y planteles. No se agrega autoguardado.

## 8. Pruebas y evidencias

| Batería | Resultado |
|---|---|
| TS-22 + regresion de interfaz/API | 115 passed |
| TS-19 y TS-20 | 123 passed, 2 skipped |
| Mundo, calendario, transacciones y guardados | 183 passed |
| TS-22 en instalacion limpia sin Node en PATH | 71 passed |
| Navegador Chromium: recorrido previo en la base de trabajo | 45 comprobaciones aprobadas |

Las baterías tienen solapamientos: no deben sumarse como pruebas distintas. Las
dos omisiones de TS-19/20 corresponden a comprobaciones opcionales con Node.
La validación obligatoria de la instalación limpia se ejecutó con Node y npm
fuera de PATH. Se verificó además que el comprobador SHA-256 detecta un archivo
alterado, y que vuelve a aprobar después de restaurar los bytes originales.

La reconstrucción limpia parte del ZIP original del usuario, luego aplica TS-19
LM/RM, TS-21.1, TS-21.1.1 y esta entrega. No depende del directorio de trabajo.
Las regresiones incluyen una temporada completa, cambio de temporada, rollback,
determinismo y recuperación de guardados. Se actualizaron pruebas heredadas que
exigían el antiguo contrato de stats vacías, ventanas nuevas y rechazo del
reintento: ahora verifican los contratos funcionales nuevos, sin quitar las
comprobaciones de no duplicación ni coherencia deportiva.

El recorrido de navegador previo comprobó navegación, roles de consulta, pantallas de Squad/rivales,
pestañas Home, partido, reintento, recarga y retorno con estadísticas visibles.
No registró excepciones JavaScript ni solicitudes HTTP fallidas en ese recorrido.
La repetición de navegador sobre la instalación limpia final fue bloqueada por
la política URL del Chromium de este entorno ANTES de cargar la aplicación.
Por ello NO se informa como una segunda pasada aprobada. La instalación limpia
sí completó las 71 pruebas obligatorias Python, sintaxis Python e integridad.
Los JavaScript modificados también pasaron una comprobación de sintaxis interna
con Node; esa herramienta no es un requisito de instalación o ejecución del juego.
La herramienta de navegador es opcional: requiere Python Playwright/Chromium en
el equipo de pruebas, no en la instalación normal del usuario.

No se ejecutó la suite completa del repositorio ni una prueba nativa en Windows.
No se hicieron cambios en GitHub, sus cuentas o workflows de Actions.

## 9. Rendimiento y equivalencia deportiva

Tres repeticiones por escenario, Linux/Python 3.13.5. Se usa el MISMO snapshot v5
para las dos versiones, por lo que el cambio intencional de Northbridge en las
carreras nuevas no contamina la comparación.

| Operación | TS-21.1.1 | TS-22 | Resultados nuevos por repetición |
|---|---:|---:|---:|
| Continue pospartido | 2.605 s | 2.549 s | 42 |
| Avance de 7 días | 5.207 s | 4.077 s | 67 |
| Lote fijo de 48 partidos | 2.266 s | 2.296 s | 48 |

En todos los escenarios coincidieron exactamente los resultados y el hash del
estado mutable de los jugadores. No se redujo el número de partidos ni la
profundidad de simulación para mantener esa equivalencia.

El primer benchmark mostró picos irregulares. Se repitió con una carrera
desechable por muestra, liberando las anteriores y recolectando su basura antes
del cronómetro EN AMBAS versiones; el recolector sigue activo durante la operación.
Se registran tiempos de pared, CPU y pausas de GC. Los datos iniciales y los
controlados quedan en TS_22_VALIDATION.json. Son mediciones de este entorno, no
una promesa de latencia para Windows ni una prueba de escalabilidad de 20 ligas.

Para medir la instalación actual, sin tocar slots personales:

`python tools/benchmark_ts22.py --repeats 3 --days 7 --matches 48`

## Fuera de alcance

CA/PA, progresión/envejecimiento, retiros, Newgens, scouting avanzado,
comparadores y negociaciones completas siguen pendientes. No se alteran las
fórmulas ni se aplican nuevas penalizaciones de cansancio. La migración de
GitHub se abordará por separado después de probar esta entrega.

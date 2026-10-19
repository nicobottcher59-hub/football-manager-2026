# TS-21.2 - Desarrollo global y potencial

## Entrega y alcance

Incremental para instalar sobre TS-22 Squad & Match Presentation. Python y frontend
portable existente; sin Node/npm para instalar, jugar o ejecutar la batería obligatoria.
No modifica GitHub, sus cuentas, remotos ni workflows.

Esta entrega implementa crecimiento, CA/PA y maduración. No es todavía el sistema completo
de envejecimiento y renovación generacional. Declive, retiros, canteras y Newgens quedan fuera.

## Cambios reales

- Perfil de desarrollo persistente para cada futbolista registrado. Se aplica a los 92
  clubes y 2.024 jugadores iniciales, no solo al equipo gestionado.
- CA derivada de atributos con un presupuesto estable según la posición original.
  PA privado, margen de mejora variable y ventanas individuales de crecimiento.
- Se reutilizan las fechas de nacimiento completas que ya existían. No se inventan ni
  redistribuyen cumpleaños. La edad visible cambia por cumpleaños; la curva utiliza el
  tiempo transcurrido. Las reglas admiten jóvenes de 15/16 años sin una rama especial de motor.
- Minutos, roles y exposición competitiva registrados al confirmar cada encuentro de ambos
  equipos. Los suplentes que no entraron no reciben minutos. Repetir un resultado no duplica experiencia.
- Cierre mensual global antes de los encuentros del mes nuevo. Incluye meses sin partidos,
  jugadores sin participación y el receso entre temporadas.
- Progreso fraccionario por atributo, orientado por edad, rol, aptitudes, personalidad TS-20,
  oportunidades y enfoque. Los enteros visibles cambian cuando se acumula suficiente progreso.
- Rendimientos decrecientes de los minutos y menor beneficio por sobrecarga, especialmente
  en menores de 18. El entrenamiento basal permite crecer sin ser titular del primer equipo.
- Presencia de veteranos profesionales e influyentes aporta un efecto de mentoría pequeño,
  limitado y aplicado igual a todos los clubes. No se crea otro grafo social.
- Perfil dentro de Squad: nacimiento, edad, próxima revisión, minutos del periodo,
  cambios de atributos, 12 cierres mensuales y hasta 40 resúmenes anuales (julio).
- Enfoque propio Balanced / Technical / Mental / Physical. Orienta el siguiente cierre,
  sin regalo instantáneo de atributos. Los perfiles rivales son de solo lectura.
- Se elimina la caché antigua del detalle para no mostrar historial o enfoque obsoletos
  tras cambiar de carrera, recargar o continuar.

## Qué significa CA y qué no significa

CA es una medida interna del presupuesto de atributos, no una nueva nota visible de partido.
Combina los pesos normalizados de roles existentes en la posición de referencia (85%) con
una base amplia de atributos (15%). Cambiar de rol o posición de uso no crea margen de PA.
El progreso fraccionario también consume presupuesto: no puede acumularse para superar el techo.

OVR/ACT siguen usando sus archivos y fórmulas existentes, sin cambios. El historial muestra
una referencia de OVR basada en los atributos del rol original, excluyendo condición, forma
y familiaridad. No confunde una bajada de ACT por cansancio con declive permanente.

El PA exacto, CA interna, semillas y parámetros de la curva no se devuelven en el perfil
público. Oculto en la interfaz no significa cifrado: el guardado local necesariamente
contiene esos datos para continuar la simulación.

## Potencial y curvas: parámetros iniciales de diseño

La inicialización distingue márgenes limitados, ordinarios, altos y excepcionales, reduciendo
el margen esperado según la edad existente. Es determinista por identificador y semilla,
y se ejecuta una sola vez. Los perfiles importados pueden proporcionar sus propios valores.
No se asigna una estrella por club ni se garantiza alcanzar el PA.

La distribución y las tasas son una calibración inicial del juego, no pronósticos empíricos
sobre futbolistas. No se generaron canteranos ni se prometen prodigios periódicos en esta
entrega. El equilibrio de cohortes y la renovación de población se cerrarán con las fases posteriores.

## Entrenamiento, entrenadores y lesiones: límites explícitos

La base no tenía un sistema operativo de instalaciones ni entrenadores individuales.
Cada club guarda por ahora un DevelopmentEnvironment neutral (60/60, identificado como
provisional). Sus parámetros son entradas del motor; no se inventan empleados ni ventajas
ocultas por liga o por controlar Northbridge. El selector de enfoque no es un planificador
completo de entrenamientos. La IA utiliza enfoque equilibrado y sus minutos/roles reales.

Una lesión activa al efectuar la revisión pausa ese cierre. Todavía no se modelan en este
módulo los días lesionado durante todo el mes, secuelas médicas o lesiones permanentes:
corresponden a TS-21.3. El historial de atributos no aplica pérdidas por edad en TS-21.2.

## Migración y guardado

Estado completo versión 7, con carga de versiones anteriores compatibles hasta la 6.
La prueba de migración utiliza un fixture sintético generado realmente con TS-22, no un
archivo nuevo renombrado como antiguo. Se comparan registros de más de 2.000 jugadores
por identificador: atributos, identidad, estado, personalidad y familiaridades conservados.

La inicialización no modifica atributos ni concede experiencia retroactiva por los partidos
antiguos. Guardar/cargar mantiene potencial, curva, fracciones, enfoque e historial.
Las revisiones son transaccionales: un fallo revierte atributos, perfiles y reloj global.
Cargar no sobrescribe el archivo; guardar escribe la nueva versión. No hay autoguardado.

El ajuste opcional anterior de Northbridge sigue exigiendo confirmación. Si se aplica a
un jugador original todavía elegible, su PA se corrige en el mismo importe de CA, conservando
el margen y la curva. Se reinicia la referencia de seguimiento para no presentarlo como
un declive por edad. No se aplica silenciosamente a carreras existentes.

El JSON de resultados no contiene una carrera individual completa. Importarlo conserva
los atributos actuales y perfiles presentes, pero reinicia la ventana de observación:
no reconstruye minutos ni crecimiento a partir de marcadores. Para continuar la carrera,
usá el guardado SQLite completo.

## Escalabilidad

Las reglas nuevas no consultan país, división ni nombre de club. Una prueba utiliza clubes
sintéticos ajenos a Inglaterra. Un importador acepta opcionalmente datos de desarrollo
con fecha de referencia explícita, PA y curva, manteniendo el modelo Player compartido.
La fecha de referencia del perfil importado debe corresponder a su alta en la simulación; no se concede entrenamiento retroactivo desde archivos antiguos.
Esto prepara jugadores reales y futuros Newgens; no incorpora una base real ni una UI de importación.

Los partidos registran exposición y el crecimiento se procesa por lotes mensuales; dentro
del mes la comprobación del reloj es constante. Los historiales y cachés están acotados.
La prueba de 20.000 jugadores es del bucle de desarrollo, no de calendarios, interfaz ni
guardados de un universo completo de ese tamaño. La persistencia global conserva los
límites de seguridad del proyecto; esta entrega no elimina esos límites.

## Pruebas ejecutadas

Entorno: Linux, Python 3.13.5; sin prueba nativa en Windows.
Node/npm fuera del PATH para la instalación limpia y la batería obligatoria.

| Batería | Resultado |
|---|---|
| TS-21.2, instalación limpia | 110 passed in 46.48s |
| Mundo persistente + calendario + TS-22 | 191 passed in 400.29s (0:06:40) |
| TS-19 + TS-20 | 163 passed + 1 passed on corrected legacy-v2 assertion rerun |
| Comprobación de migración v2, aserción actualizada | 1 passed in 8.01s |
| Transacciones + guardados + aplicación + avance diario | 51 passed in 1632.97s (0:27:12) |

Las ejecuciones de corrección no se suman como pruebas diferentes. Se actualizaron
aserciones antiguas del número de versión y, en migración v4, se comparan alineaciones
por identidad y configuración conservadas, además de todos los atributos/estado originales;
la nueva metadata de desarrollo ya no hace fallar una igualdad de dataclasses completa.
No se elimina una verificación de integridad para ocultar un cambio de datos.
La tanda larga de TS-19/TS-20 arrancó antes de actualizar esa aserción y terminó con
163 aprobadas y un fallo `7 == 4`. El test se repitió en un proceso nuevo y aprobó.
La tanda también ejecutó sus verificaciones opcionales de JavaScript con Node en este
entorno; eso no es un requisito de instalación. La nueva batería obligatoria se
comprobó por separado con Node/npm fuera del PATH.

Se verificaron integridad SHA-256 y detección de una modificación deliberada del paquete.
La sintaxis del JavaScript modificado pasó un chequeo interno opcional, no requerido al usuario.
La prueba de navegador fue bloqueada antes de cargar la página por
`net::ERR_BLOCKED_BY_ADMINISTRATOR`; cero comprobaciones visuales aprobadas en esa ejecución.
El endpoint HTTP, autorización del enfoque y modelos públicos sí se comprobaron con Python.
No se ejecutó toda la suite del repositorio.

## Temporada completa y pruebas largas

Una temporada con partidos reales completó 2959 encuentros, incluidos
51 del club gestionado, y avanzó a 2027-08-20. Guardado/carga y
el siguiente partido conservaron resultados y estado idénticos. Se validaron los techos
individuales. 601 de los 2.024 jugadores iniciales
registraron cambios visibles de atributos; el resto puede acumular fracciones o no crecer.

Después del cambio de temporada quedaron 2068 jugadores registrados:
los 2.024 originales siguen presentes y los 44 adicionales corresponden a planteles de
clubes que entran desde fuera del ámbito inicial, una conducta del mundo de TS-21.1.
Eso NO constituye un sistema de Newgens ni una prueba de población constante.

Se compararon dos cohortes sintéticas de 120 jugadores durante
20 años. La ganancia media de CA fue 9.68
con más oportunidades y mejor entorno, frente a 6.106
con oportunidades limitadas. PA estable, límites respetados e historiales acotados.
Son trayectorias aisladas de crecimiento: no incluyen retiros ni sustitución generacional.

## Rendimiento observado

Lote mensual de 2.024 jugadores: mediana 0.85 s.
Lote aislado de 20.000 jugadores: mediana 13.72 s.
Tres muestras por tamaño; hubo variabilidad, especialmente en el lote grande.
No son promesas para una PC Windows ni para el juego completo con 20.000 jugadores.

La comparación de operación partió del mismo snapshot y conservó exactamente
marcadores y estados en los tres escenarios. Se hizo antes del primer cierre mensual,
por lo que verifica que registrar desarrollo no altera esos encuentros; una vez que
cambian atributos, los resultados deportivos posteriores pueden cambiar legítimamente.

| Operación | TS-22, mediana | TS-21.2, mediana | Resultados nuevos |
|---|---:|---:|---:|
| postmatch_continue | 16.89 s | 10.04 s | 42 |
| calendar_days | 10.77 s | 13.25 s | 67 |
| fixed_league_batch | 6.94 s | 7.35 s | 48 |

Los tiempos variaron mucho durante pruebas concurrentes (por ejemplo, Continue de base
entre 4,47 y 19,99 s). No se interpreta esa comparación como una mejora de velocidad ni
como demostración concluyente de ausencia de regresión. Se conserva el detalle de tiempo
real, CPU y recolección de memoria en TS_21_2_VALIDATION.json.

## Instalación

1. Guardá la carrera completa y respaldá proyecto y archivo SQLite.
2. Cerrá el juego y el servidor Python.
3. Extraé el ZIP en la raíz del proyecto con TS-22, conservando las rutas.
4. Ejecutá:

```powershell
python tools/verify_ts212_development_package.py
python -m pytest -ra tests/test_ts_21_2_player_development.py
```

Reiniciá INICIAR_INTERFAZ_WINDOWS.bat y recargá con Ctrl + F5. Abrí el detalle de
un jugador en Squad; el primer cierre aparece al llegar al comienzo del mes siguiente.
El progreso visible no está garantizado todos los meses. Guardá normalmente para conservar
el estado y el enfoque elegido. No uses una versión vieja del código sobre el guardado
nuevo: restaurá el respaldo si necesitás volver a TS-22.

## GitHub Desktop

Branch: `feat/ts-21-2-global-player-development`

Summary: `feat(development): add persistent potential and monthly player growth`

Este paquete no realiza acciones sobre GitHub. El siguiente desarrollo es TS-21.3:
declive, longevidad, consecuencias médicas y retiro, reutilizando la misma base.

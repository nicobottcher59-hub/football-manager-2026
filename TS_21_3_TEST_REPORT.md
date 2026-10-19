# TS-21.3 - Envejecimiento, lesiones y retiro

## Alcance y base

Paquete incremental sobre **TS-21.2 Desarrollo Global y Potencial**, con TS-22 y
las actualizaciones anteriores ya instaladas. Backend Python y frontend portable.
No requiere Node ni npm para instalar, jugar, verificar el paquete o ejecutar las
pruebas obligatorias. No cambia GitHub, remotos ni workflows.

La mejora visual del panel de desarrollo queda pendiente, según lo solicitado.
Esta entrega implementa reglas de carrera; solo ajusta signos negativos y textos
médicos/retiro dentro de las vistas existentes. No crea otro Medical Centre.

## 1. Envejecimiento individual

Cada futbolista recibe un perfil persistente con ventanas de declive físico,
técnico y mental, ritmo individual y longevidad. Se inicializa una sola vez; no
se vuelve a sortear al cargar, cambiar de puesto o ascender. Admite datos
importados, sin consultar la liga o el prefijo del identificador del jugador.

Las pérdidas se calculan sobre el tiempo transcurrido y se acumulan por atributo.
Se publican en la revisión mensual compartida con el crecimiento. Velocidad,
aceleración y agilidad empiezan antes; otras capacidades físicas, técnica y
atributos mentales siguen ventanas diferentes. Los arqueros tienen matices en
sus perfiles y capacidades específicas. No hay un descuento de OVR por cumplir
años, ni una rebaja general al abrir el guardado.

Un jugador puede mejorar unos atributos y perder otros en el mismo período.
Se cancelan primero fracciones opuestas para no duplicar crédito de crecimiento
y deuda de declive. Se respetan los límites de atributos y el potencial ya
asignado. El historial muestra diferencias firmadas, no '+-1'. Natural fitness,
agresión y valentía conservan el tratamiento de atributos innatos de TS-21.2.

**No se modifican las fórmulas OVR/ACT, los roles ni las fórmulas existentes
de fatiga/recuperación.** Se verificó igualdad SHA-256 en los 13 archivos
correspondientes de atributos, valoraciones, roles, condición y motor rápido.
El cansancio temporal no se registra como envejecimiento.

## 2. Lesiones con fechas y posibles consecuencias

Se añade un episodio médico persistente: identificador, descripción, comienzo,
retorno y origen. El calendario libera las ausencias al llegar su fecha, sin
poner la condición en 100 ni reiniciar el cansancio. El desarrollo mensual
considera la parte del período que estuvo disponible, no solo el indicador de
lesión en el día de revisión.

Las lesiones nuevas se evalúan **después del partido** para quienes jugaron,
con las mismas reglas para ambos equipos y los partidos de fondo. La carga,
los minutos, la condición y la susceptibilidad existente influyen en el riesgo.
No se inventan lesiones ni sustituciones en el minuto a minuto: el simulador
rápido sigue sin un flujo de lesiones dentro del encuentro. La API lo distingue
con `injury_tracking_supported=true` e `in_match_injuries_supported=false`.

Parámetros iniciales de juego, sujetos a calibración: base 0,012 por 90 minutos,
riesgo individual acotado a 0,055; como máximo una ausencia nueva por club y
partido. Las duraciones generadas abarcan 2-6, 7-21, 22-55 o 60-150 días según
la gravedad sorteada. No son probabilidades médicas empíricas. Las ausencias
largas pueden dejar pequeñas secuelas físicas aplicadas una vez, después del
retorno, y afectar a la longevidad. La mayoría no tiene secuelas. El PA no se
resortea ni disminuye como atajo.

Hasta que existan reemplazos juveniles, se evita generar otra ausencia cuando
quedan 13 o menos disponibles y se protege al último arquero disponible. Es una
protección provisional explícita, no una ventaja exclusiva del usuario.

La preparación del próximo partido y la simulación por calendario reemplazan
seleccionados no disponibles por compañeros aptos. Conservan titulares sanos en
sus puestos y el plan táctico. No curan al lesionado para permitirle jugar.

## 3. Retiro y protección provisional de planteles

La revisión mensual puede registrar la decisión de retirarse. Se resuelve al
cambiar de temporada, no a mitad de un partido. Influye la longevidad individual;
participación e historial de lesiones pueden adelantar o demorar la solicitud.

Un retiro aprobado quita al jugador del plantel activo y conserva su registro
final, identidad, nacimiento, potencial y estadísticas. El guardado incluye el
archivo de retirados; no se elimina su historia ni se lo vuelve a generar.

Sin canteras ni Newgens no se puede permitir una salida ilimitada y, a la vez,
prometer planteles jugables. Por eso se posterga el retiro si el club no conserva
al menos 18 futbolistas, dos arqueros naturales, suficientes centrales, al menos
16 disponibles y un once de jugadores distintos compatible con sus planes.
Una línea de tres centrales requiere conservar al menos cinco centrales
naturales. También se comprueba el planteamiento actual del club gestionado.
Las solicitudes aplazadas se revisan en la siguiente transición.

**No se crean sustitutos ocultos, ni se rejuvenecen jugadores, ni se detiene su
declive por haber aplazado el retiro.** Esta protección evita un bloqueo inmediato,
pero no sustituye la renovación generacional. El equilibrio de cantidad/calidad
a 15-20 temporadas sigue dependiendo de la futura entrada de juveniles.

## 4. Guardados, migración y transacciones

El estado completo `manager_state` y su grafo pasan a **versión 8**. Se aceptan
las versiones anteriores compatibles, incluida la 7. El contenedor sigue siendo
el guardado SQLite completo. Cargar no sobrescribe el archivo; la nueva versión
se escribe al guardar normalmente. Conservá un respaldo v7 para volver al
código anterior. No se agrega autoguardado.

La migración crea perfiles desde la fecha actual de la carrera y preserva todos
los atributos, fechas de nacimiento, potenciales y estados existentes. No aplica
años de declive retroactivo. Se probó con un grafo v7 real generado por TS-21.2,
no solamente cambiando el número de versión de un grafo nuevo.

Una lesión antigua sin duración sigue identificada como fecha desconocida: no se
inventa un retorno ni una secuela. Los JSON de resultados no restauran una
carrera individual completa. Su importación conserva el estado actual y reinicia
la observación, sin volver a aplicar fechas médicas de una línea temporal distinta.

Las escrituras de desarrollo, salud, índice de recuperación, estadísticas y
retiros participan de las transacciones existentes. Los fallos inyectados
comprueban restauración del estado y de los índices. Se permite reutilizar el
dorsal de un retirado sin invalidar sus metadatos históricos.

## 5. Validación ejecutada

### Instalación limpia y pruebas dirigidas

Se reconstruyó el proyecto desde el ZIP original y los incrementales TS-19
LM/RM, TS-21.1, TS-21.1.1, TS-22 y TS-21.2. Sobre esa base se extrajo TS-21.3.
Node y npm se quitaron del PATH para las pruebas obligatorias.

| Batería | Resultado |
|---|---|
| TS-21.3 + TS-21.2 en instalación limpia | 167 passed in 49.46s |
| Mundo, calendario, TS-19, TS-20, atomicidad y avance diario | 352 passed, 1 skipped in 833.15s (0:13:53) |
| Presentación, API, condición, transacciones y guardados: primera ejecución | 2 failed, 133 passed in 465.83s (0:07:45) |
| Repetición de los casos corregidos y contrato HTTP relacionado | 5 passed in 30.65s |

La tercera fila tuvo dos fallos: una expectativa antigua de guardado v7 y la
falta de la bandera explícita `in_match_injuries_supported` en la versión cargada
por esa ejecución. Se actualizó la expectativa a v8 y se incorporó la bandera
`false`; ambos casos y las comprobaciones relacionadas pasaron en la repetición.
No se presenta esa primera batería como una ejecución totalmente aprobada.
Las baterías se solapan: no deben sumarse como pruebas distintas.

Las pruebas nuevas incluyen crecimiento juvenil inalterado sin lesiones,
curvas deterministas, separación de fatiga, pérdidas fraccionarias, disponibilidad
parcial, secuelas aplicadas una vez, ausencia de duplicados, retiros aplazados,
archivo, recuperación al avanzar varios días, rollback y migración v7 genuina.
Se corrigieron además dos supuestos del propio banco de pruebas: se compara
estado lógico restaurado, no la numeración incidental de nodos serializados, y
las pruebas de retiro manual sincronizan el vestuario igual que producción.

### Dos temporadas con partidos reales

Se resolvió el calendario completo de ambas temporadas y se pasó al siguiente
inicio de liga, con validación de identidad, nacimiento y potencial de todos los
jugadores iniciales, tanto activos como archivados.

| Temporada | Partidos | Retirados en transición | Activos al nuevo inicio | Plantel más corto | Retiros aplazados |
|---|---:|---:|---:|---:|---:|
| 2026/27 | 2959 | 33 | 2035 | 21 | 2 |
| 2027/28 | 2959 | 31 | 2048 | 20 | 5 |

La política preexistente de ascensos externos incorpora dos clubes y sus
planteles por año, conservando también clubes que salen del ámbito activo.
Eso explica que el total registrado cambie: **no son Newgens de esta entrega
ni una prueba de población constante**. Guardar/cargar tras las transiciones y
jugar/continuar un encuentro produjo el mismo estado que seguir sin recargar.

### Observación individual de 20 años

Se observaron 140 futbolistas sintéticos de edades iniciales diversas durante
20 años, con oportunidades de crecimiento y declive. Se conservaron los
potenciales y los límites de atributos; la pérdida física precedió a la mental
en el agregado. Para observar sus curvas, se mantuvieron en la muestra incluso
tras solicitar el retiro. **No es una simulación demográfica ni demuestra que
el mundo conserve medias constantes sin juveniles nuevos.**

### Rendimiento aislado

Medianas de tres ejecuciones por caso, en este entorno Linux, sin las otras
baterías de validación corriendo. Misma cohorte sintética, comparación del
crecimiento solo con el crecimiento más envejecimiento.

| Jugadores | Cálculo | Mediana |
|---:|---|---:|
| 2024 | growth_only | 0.243 s |
| 2024 | growth_and_aging | 0.342 s |
| 10000 | growth_only | 1.403 s |
| 10000 | growth_and_aging | 2.065 s |

Esto mide una revisión mensual, no Continue completo ni tu computadora Windows.
El crecimiento/envejecimiento se procesa por meses y las recuperaciones se
consultan por índice de episodios activos, sin revisar todos los atributos cada
día. Los historiales mensuales y médicos tienen límites explícitos.

### Frontend y límites de las pruebas

Los dos JavaScript modificados pasaron `node --check` en el entorno de trabajo;
esto no agrega Node como dependencia del usuario. La prueba de navegador
Chromium se bloqueó antes de cargar la página con
`net::ERR_BLOCKED_BY_ADMINISTRATOR`. No se cuenta como validación visual aprobada.
Las pruebas de API sí se ejecutaron, incluidas fechas médicas, lectura sin
mutaciones, resumen pospartido y distinción respecto de eventos durante el juego.
No se ejecutó una prueba nativa en Windows ni toda la suite del repositorio.

## 6. Instalación y uso

Cerrá juego y servidor, respaldá la carpeta y el SQLite, y extraé el ZIP en la
raíz de TS-21.2 conservando las rutas. Ejecutá:

```powershell
python tools/verify_ts213_aging_package.py
python -m pytest -ra tests/test_ts_21_3_player_aging.py
```

Luego reiniciá con `INICIAR_INTERFAZ_WINDOWS.bat` y recargá con Ctrl + F5.
En Squad, los detalles existentes muestran las revisiones firmadas y el estado
médico/retiro. En prepartido aparecen las ausencias; en el resumen, los nuevos
partes pospartido. El crecimiento/declive se registra al llegar al siguiente
mes; las recuperaciones, según su fecha; los retiros, al cambiar de temporada.

Pruebas prolongadas opcionales (no abren guardados personales):

```powershell
python tools/validate_ts213_careers.py season --seasons 2 --output ts213_seasons_local.json
python tools/validate_ts213_careers.py cohort --players 140 --years 20 --output ts213_cohort_local.json
```

El manifiesto SHA-256 verifica los bytes del paquete y dependencias base; no
certifica el balance deportivo. Las mediciones y evidencias están también en
`TS_21_3_VALIDATION.json`.

## 7. Pendientes explícitos

Canteras/Newgens, reposición generacional, cuerpo técnico e instalaciones
completos, renovación visual del panel y eventos de lesión dentro del encuentro.
El entorno de entrenamiento neutral de TS-21.2 se conserva. Las tasas de
lesión y declive necesitan calibración jugable adicional; no se impone una media
global artificial ni se modifica el potencial para compensar generaciones.

# TS-24.12 - Validacion integral del modo carrera

**Base requerida:** TS-24.11. **Formato de guardado:** SQLite v16 (sin migracion).
**Naturaleza:** actualizacion de auditoria, pruebas y reproducibilidad; no introduce ideologias de fichajes ni cambia la interfaz.

## Objetivo

Certificar lo que realmente se puede comprobar sobre calendario, competiciones, mercado, prestamos autonomos, contratos, envejecimiento, canteras, economia y persistencia; exponer las limitaciones y riesgos sin declarar "perfectos" los clubes.

## Tres tipos de evidencia

1. **Estres acelerado 5/10/20 temporadas.** Se juegan las competiciones, cierres de mes, ventanas, prestamos, promociones, retiros y cambios de temporada. Los encuentros senior usan resultados acelerados, sin el motor detallado de minutos, fatiga o lesiones. No equivale a jugar veinte anos completos en la interfaz.
2. **Multiples semillas.** Se generan mundos independientes para detectar sensibilidad a las plantillas iniciales y los resultados. No es una estimacion estadistica universal.
3. **Partidos reales y persistencia.** Se comprueba una muestra de partidos completos con minutos efectivos de sub-23, y regresiones de registros, contratos, prestamos, resultados administrativos y SQLite v16.

## Un entrenador humano no es un club automatico

TS-24.10 confirma retiros de jugadores incluso si el plantel humano queda debilitado. En una simulacion totalmente desatendida, al cabo de doce temporadas el club del entrenador se queda sin jugadores suficientes para reconstruir su alineacion: intentar abrir el ano siguiente exige que el usuario intervenga. No corresponde devolver a retirados ni inventar jugadores.

Por ello, la prueba de 20 anos usa un **entrenador ficticio de pruebas** que asciende jugadores ya existentes de la cantera antes del cambio de temporada, mediante el mismo comando de usuario (`youth_command`). Queda registrado el ID y la edad de cada futbolista promovido. Solo se hace en mundos descartables de auditoria; no cambia las decisiones del juego ni transfiere el control del club humano a la IA.

El test sin esa intervencion se conserva como una limitacion explicita, no se sustituye retroactivamente.

## Clasificacion de hallazgos

- **Fallo estructural:** duplicacion de identidades, contabilidad sin cuentas, partidos oficialmente pendientes al cierre, excepciones no recuperadas o futbolistas activos de 50 anos por una anomalia.
- **Riesgo deportivo:** incapacidad de cubrir una formacion, un plantel excepcionalmente pequeno, varios encuentros perdidos administrativamente; exige investigacion, no fichajes forzados.
- **Advertencia de plantilla:** un unico arquero o pocos suplentes sin afectar automaticamente la continuidad.
- **Riesgo economico:** perdidas recurrentes, caja muy negativa, contratos mal adaptados a un descenso o valores de mercado distorsionados. Una perdida aislada **no** es un bug.

Ni el informe ni el juego fijan una cuota de clubes rentables ni fuerzan a todos a tener planteles impecables. Los errores de planificacion son una parte valida de la simulacion.

## Reproduccion

Desde la raiz del proyecto, con Python y pytest instalados:

```bash
python tools/verify_ts2412_integral_package.py
python tools/run_ts2412_validation.py --mode quick
```

Para repetir las simulaciones largas, con un coste de procesamiento considerable:

```bash
python tools/run_ts2412_validation.py --mode extended
```

Los resultados se guardan bajo `reports/`. Las partidas existentes del usuario no son entradas para las auditorias, y no se sobrescriben. La auditoria de veinte anos se realiza con un mundo descartable y promociones explicitas del entrenador ficticio.

## Limitaciones

- Las pruebas largas no ejecutan lesiones y minutos del motor senior completo; la muestra real es acotada.
- No se realizaron pruebas nativas en Windows ni validacion manual de la interfaz Electron/web.
- La suite historica completa conserva errores de importacion de pruebas antiguas de calibracion presentes ya en TS-24.11.
- El deterioro financiero prolongado y las plantillas ocasionalmente inviables pueden ser riesgos de realismo. No se corrigieron con topes economicos ni generacion artificial de futbolistas.
- Las ideologias de fichajes no forman parte de TS-24.12: se debatiran cuando se carguen clubes reales individualmente.

## Análisis económico de gravedad

Una pérdida aislada o una caja negativa temporal **no** invalida la simulación.
En cambio, se identifican para revisión específica saldos inferiores a GBP -100 millones,
rachas prolongadas de caja negativa, presupuestos de fichajes inconsistentes y ausencia
de recuperación económica creíble. El umbral de GBP -100m es **una alerta del
auditor, no una regla de juego**; no aplica quiebras ni bloqueos financieros.
Se conserva el identificador de cada club en el informe JSON para estudiar
sus decisiones y la evolución de su saldo a lo largo de las temporadas.

## Reglas de clasificación deportiva

Una vacante de suplente o disponer de un solo arquero es una alerta.
No poder cubrir el once según la táctica es un riesgo deportivo serio, pero
no se compensa con fichajes o retiros ficticios. Si el calendario necesita
resolver una incomparecencia, se utiliza exclusivamente el contrato
administrativo que ya implementa TS-24.11 y se mantiene la evidencia.
Estas clasificaciones **no alteran** decisiones de los clubes ni porcentajes
de éxito de su IA.

## Diferencias entre marcadores acelerados e incomparecencias

El acelerador de veinte años utiliza el resolutor de resultados de fondo para
completar el calendario; por tanto **no comprueba partido por partido** si cada
club podía presentar jugadores aptos. Las incomparecencias y la falta de un
arquero elegible se prueban de forma independiente con el motor detallado en
los tests heredados de TS-24.11. Un cierre anual con vacantes no certifica que
todos los partidos de ese año hubieran podido disputarse con el motor completo.

## Resultado definitivo de esta entrega (después de la interrupción)

El escenario principal completó **18 de las 20 temporadas solicitadas**. Al iniciar
la temporada 19, la vista previa del partido controlado intentó seleccionar a
Hillcrest Athletic, que ya no podía formar un once válido, y arrojó
`ValueError: Hillcrest Athletic has no valid lineup`.

Esto **sí es un error técnico**, distinto de aceptar que el club se planificó mal.
Se corrigió la ruta `DevelopmentSession._prepare_development_opponent`: cuando
el rival registrado de la IA carece de un equipo legal, el resultado administrativo
se registra en el mundo y el calendario avanza al siguiente partido. No se crean
jugadores ni minutos y no se anulan retiros. El equipo humano conserva sus
propias obligaciones de alineación. El flujo está probado con once tests de
TS-24.12 y un smoke reproducible.

El parche **sí modifica el código de sesión** en este caso puntual, a diferencia
del plan inicial de una actualización solo de diagnóstico. No introduce cambios
de esquema SQLite. El resto de la lógica de mercado/economía no se modificó.

**La prueba de veinte años no fue completada nuevamente con el parche aplicado**:
los datos del archivo de horizonte largo muestran expresamente `status: failed`
y `completed_seasons: 18`. No se deben presentar como una auditoría superada.

### Riesgos principales que continúan abiertos

- Año 18: 33 clubes con menos de dos arqueros naturales.
- Año 18: seis vacantes titulares y 41 vacantes de suplentes.
- Mínimo de caja observado en todo el recorrido: alrededor de -GBP 235,55 millones.
- La prueba acelerada no comprueba once disponible en cada encuentro ni reproduce
  los minutos/lesiones de partidos senior completos.

La siguiente corrección necesaria no es ideológica ni estética: es una mejora
de planificación de posiciones y reacción deportiva de la IA para impedir que
la carencia de arqueros se generalice. Debe permitir errores ocasionales,
pero detectar tendencias que afectan a una fracción importante de la liga.

### Verificación específica después de instalar

```bash
python tools/verify_ts2412_integral_package.py
python tools/smoke_ts2412_forfeit.py --output reports/ts2412_local_forfeit_check.json
pytest -q tests/test_ts_24_12_integral.py
```

El smoke usa un mundo de prueba nuevo y no toca los guardados existentes.
El archivo `reports/ts2412_seed6606_20y.json` es un registro histórico de
la ejecución interrumpida **antes** de esta corrección, no una nueva simulación
completada.

# TS-24.13 - Reequilibrio deportivo a largo plazo

## Alcance

Actualizacion incremental sobre TS-24.12. Prioriza el deterioro sistemico de
plantillas profesionales a lo largo de carreras extensas, especialmente la
escasez de arqueros y la disponibilidad de recambios reales. No es una
reforma economica ni una promesa de igualdad entre clubes.

## Problema comprobado en TS-24.12

La auditoria de la semilla 6606 se interrumpio al iniciar la temporada 19.
Al cierre de la temporada 18 se observaban 33 de 92 clubes activos con menos
de dos arqueros profesionales, seis huecos en puestos titulares y 41 huecos de
suplentes. El fallo tecnico de alineacion del rival ya tenia una correccion
puntual en TS-24.12, pero no se habia validado el horizonte completo despues
de aplicar esa correccion.

### Causa de fondo: cantera U15

La reposicion anual anterior seleccionaba `POSITION_POOL` comenzando en el
indice `starting_count`. Normalmente quedaban muchos U15 al inicio de cada
nuevo curso: las nuevas incorporaciones recorrian siempre los indices finales,
sin GK. La generacion inicial tenia dos arqueros, pero los posteriores no
reponian de forma fiable esos puestos. Cuando las promociones y jubilaciones
superaban la reserva existente, los 92 clubes competian por una oferta
real de guardametas que se iba agotando.

## Solucion

1. **Ingreso anual de cantera real.** El plantel U15 conserva su maximo
   existente de 20 futbolistas. Las vacantes se cubren con futbolistas de 14
   anios y IDs estables; no se alteran sus probabilidades de calidad ni
   potencial. Si U15 perdio a sus arqueros, hasta dos de las vacantes se
   cubren con arqueros naturales. Si quedan menos vacantes, no se crean
   personas extra.
2. **Puestos de campo rotatorios.** El resto de incorporaciones rota entre
   las posiciones de campo. El orden depende de la semilla, el club y el
   anio; evita repetir el mismo tramo final de una lista fija.
3. **Tercer arquero por formacion.** La IA puede promover un GK U21 existente
   como tercer arquero profesional, con edad y nivel creibles, si tenia solo
   dos arqueros y hay lugar en la plantilla. Nunca agrega un cuarto GK por
   acumulacion de promociones. Las vacantes titulares y de suplentes siguen
   siendo prioritarias. Se conserva el derecho exclusivo del entrenador
   humano a decidir sus promociones.
4. **Relojes de clubes fuera de liga.** Los clubes que pasan temporadas
   sin encuentros oficiales mantienen un reloj de recuperacion fisica
   actualizado en el cambio de temporada. Sin esto, cuando ascienden
   juveniles que nacieron despues del ultimo partido profesional del club,
   una comprobacion de integridad rechazaba la temporada 19. La
   recuperacion se aplica sobre personas reales y sin eventos inventados.
5. **Guardados SQLite longitudinales.** Se eleva el limite finito del grafo
   de guardado de 250.000 a 1.000.000 de nodos: una carrera completa con
   92 clubes ya superaba 285.000 nodos tras el primer anio en TS-24.12.
   El codec y el esquema siguen en v16, sin migraciones de partidas ni
   desactivar controles de integridad.
6. **Nada de rescates.** Un club con caja negativa puede desarrollar a sus
   propios juveniles. No recibe dinero, traspasos gratuitos ficticios ni
   futbolistas inventados. Los contratos, salarios y limites del mercado
   conservan su comportamiento de TS-24.12.

## Lo que se deja deliberadamente intacto

- Ingresos, gastos, deuda, presupuestos, reglas de compra y venta.
- Prestamos entre clubes de la IA, promesas de minutos y retiradas anticipadas.
- Autonomia absoluta de retiro del jugador: la ausencia de sustituto no
  puede impedir una jubilacion elegida por el futbolista.
- Derrota administrativa de IA sin once valido implementada en TS-24.12.
- Criterios particulares de fichajes por identidad de cada club: pospuestos
  hasta que se carguen los clubes reales de manera individual.
- Formato y version de persistencia SQLite v16: el limite de capacidad
  aumenta, pero el formato de datos no cambia.

## Metodo de validacion

- Tests unitarios de cantera, elegibilidad, identidades reales, relojes de
  clubes inactivos, limites del serializador y estado economico preservado.
- Regresiones TS-24.8 a TS-24.12, en especial retiros y cesiones.
- Carreras con tres semillas (6606, 7707 y 8808), multiples horizontes
  entre 5 y 20 temporadas; conteo de vacantes titulares, reservas, arqueros,
  jugadores, cajas negativas y errores estructurales.
- Simulador acelerado: se ejecuta el calendario real y los cambios de
  temporada, contratos, mercado, juveniles, finanzas y jubilaciones, pero
  los marcadores de partidos senior usan un resolvedor de prueba. Esto NO
  certifica las lesiones ni minutos detallados de 20 temporadas jugadas a
  mano. No se tocan partidas SQLite del usuario.

## Criterio de realismo

No se exige una plantilla ideal para cada club ni caja positiva. Una entidad
puede quebrar, perder suplentes, competir con un equipo inferior o fichar
mal. Si falta un segundo arquero en uno o dos equipos, se observa como riesgo;
si le ocurre a un tercio de la liga por falta de renovacion de la cantera,
es un problema sistemico a corregir. Los grandes pueden formar planteles
superiores; la simulacion no fuerza paridad deportiva.

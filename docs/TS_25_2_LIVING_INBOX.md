# TS-25.2 — Inbox vivo, decisiones y relaciones

## Alcance

Extensión incremental de TS-25.1. Reutiliza los eventos y la moral de TS-20,
los contratos/mercado de TS-24 y los juveniles de TS-23. Se preserva el formato
SQLite/graph v17 de TS-25.1: no se agregan campos persistidos nuevos y no se
cambian los algoritmos de valoración, presupuestos, partidos ni retiros.

### Conversaciones voluntarias

Además de los seis temas de TS-25.1, se incorporan desarrollo, liderazgo,
posible cesión, transferencia y recuperación médica. La afinidad con el
entrenador modifica levemente la recepción de conversaciones futuras. La
presión aumenta si se repiten charlas y disminuye con los días. Las charlas
repetidas pierden eficacia y pueden hacer que el jugador se sienta agobiado.
Ninguna charla renueva contratos, cierra fichajes o mejora atributos deportivos.

### Pedidos espontáneos y decisiones

Los futbolistas pueden pedir una conversación por falta de minutos (eventos
del vestuario), contratos próximos a vencer, estado de ánimo y forma malos,
o lesiones reales en casos justificados. No se inventan resultados ni citas.

Cada solicitud aparece en Inbox como pendiente durante 28 días; se puede
**discutir** o **declinar**. Declinar produce un impacto pequeño y definitivo;
ignorarlo produce otra consecuencia pequeña al expirar. El usuario puede
seguir avanzando: no hay bloqueo injustificado de la simulación. Una charla
sobre un tema distinto no resuelve la solicitud. La demanda se limita a un
máximo de cinco solicitudes abiertas en un momento dado.

### Promesas verificables

| Tipo | Evidencia necesaria | Plazo inicial |
|---|---|---|
| Tiempo de juego | >=35% de minutos en partidos elegibles | 56 días |
| Rol de titular | >=55% de minutos en partidos elegibles | 70 días |
| Oportunidad juvenil | >=15 minutos en un partido elegible | 56 días |
| Renovación | Contrato efectivamente renovado en el registro del club | 90 días |
| Cesión saliente | Préstamo real firmado con otra entidad | 70 días |

Los compromisos deportivos precisan al menos dos partidos elegibles; si no
los hay, se amplía una vez en 21 días y pueden quedar sin evaluación justa.
Se premia moderadamente cumplir (+3 confianza, +1.5 moral) y se penaliza
incumplir (-5 confianza, -2.5 moral), con confianza siempre limitada a
35–65. No se puede aceptar un segundo compromiso activo con el mismo jugador.
Los compromisos no sustituyen las negociaciones auténticas.

### Inbox informativo

Además de los avisos de TS-25.1, incorpora: renovaciones reales, inicio y fin
de préstamos, traspasos importantes completados entre clubes del mundo,
altas de juveniles al primer equipo y acontecimientos sociales del vestuario.
Los avisos dependen de registros de la simulación y tienen claves persistentes
para evitar duplicados. La UI ofrece filtros por pendientes/no leídos/categoría,
acciones de respuesta y archivo, junto con acceso contextual a las pantallas
ya existentes.

### Qué NO hay todavía

- No se simulan convocatorias individuales de selecciones nacionales ni sus
  lesiones. Antes hay que construir ese sistema real.
- No se han implementado ruedas de prensa, negociaciones de contrato a través
  del chat, ni intervención táctica mediante mensajes.
- No se bloquea artificialmente la progresión para obligar a contestar.
- Sin evaluación visual manual en Windows ni stress de 20 temporadas en TS-25.2.

## Integridad, seguridad y compatibilidad

Se mantienen las rutas y comandos HTTP existentes. Los POST operan sobre una
copia transaccional de la sesión, los datos se validan en Python y los mensajes
se escapan en la interfaz. El decodificador SQLite mantiene lista blanca de
clases. Las conversaciones y promesas existentes en partidas v17 se mantienen.

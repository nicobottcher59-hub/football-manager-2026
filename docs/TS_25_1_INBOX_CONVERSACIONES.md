# TS-25.1 - Inbox real y conversaciones con jugadores

## Alcance

Esta es la primera entrega funcional de TS-25, instalada sobre TS-24.13.

- Inbox real y persistente, con filtros, contador de no leidos y detalle.
- Noticias del equipo generadas por hechos registrados en la partida: lesiones y recuperaciones, contratos cercanos a vencer, reportes de ojeadores juveniles, candidatos descubiertos, resultados de partidos, movimientos de negociaciones y cambios efectivos en el calendario.
- Solicitudes de reunion originadas en quejas por minutos que ya genera el sistema TS-20 de vestuario; se resuelven mediante una charla.
- Conversaciones iniciadas por el entrenador desde Inbox o desde el perfil del vestuario: felicitar, apoyar, criticar, hablar del futuro/contrato, del rol y de minutos.
- Promesa opcional de minutos para las proximas ocho semanas. Se comprueba usando apariciones reales y minutos elegibles; si no hay partidos suficientes, el plazo se amplia una vez y luego se anula sin falsos incumplimientos.
- Moral y confianza independientes: charlas producen efectos pequenios; repetir el tema pierde eficacia, hablar demasiado genera agobio, hay un tope de tres charlas por jugador y dia. La confianza oscila solo entre 35 y 65.
- Integracion en el Home y persistencia real en guardados SQLite.

## Limites deliberados

- Las conversaciones no renuevan contratos ni prometen salarios automaticamente. Cualquier operacion contractual exige el flujo financiero existente.
- No se crean convocatorias a selecciones porque la simulacion individual de selecciones no existe todavia.
- Las noticias de reprogramacion solo se generan si un partido real cambia de fecha. No se inventan cambios de calendario.
- Las charlas iniciadas por los futbolistas abarcan por ahora las preocupaciones TS-20 de minutos, no todo el abanico propuesto de conflictos.
- No hay todavia noticias editoriales de todos los clubes, promesas de contratos o ascensos, entrevistas de prensa ni bloqueo del reloj ante decisiones criticas.
- La UI esta en ingles por consistencia con la interfaz actual.
- Esta primera entrega no constituye una certificacion de 20 temporadas ni una prueba grafica manual en Windows.

## Compatibilidad

Versiones antiguas de guardados manager_state v16 se migran al nuevo grafo v17 en carga. No se borran los datos existentes; se crea un Inbox inicial y se registran los hechos futuros. Una partida guardada con v17 requiere TS-25.1 o superior, no versiones anteriores.

## Prueba rapida

1. Iniciar la UI de Python con INICIAR_INTERFAZ_WINDOWS.bat.
2. Abrir Inbox. Debe aparecer un mensaje inicial real y no noticias falsas.
3. Iniciar una conversacion con un futbolista y comprobar la reaccion.
4. Intentar repetir el tema: se debe notar el desgaste; al cuarto intento del mismo dia el jugador necesita espacio.
5. Guardar y cargar la partida para comprobar que el historial persiste.
6. Avanzar fechas y comprobar que las notificaciones provienen de hechos efectivamente registrados.

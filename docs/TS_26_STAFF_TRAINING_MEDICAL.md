# TS-26 - Cuerpo tecnico, entrenamiento y centro medico

Version integrada sobre TS-25.2. Se conservaron Inbox, conversaciones, vestuario, scouting, mercado, competiciones y el simulador. El objetivo es tomar pocas decisiones con efectos moderados, no convertir cada dia en una rutina administrativa.

## Cuerpo tecnico

- Tres roles: entrenadores (progresion), medicos (duracion de lesiones nuevas) y preparadores fisicos (recuperacion entre partidos).
- Contratos fechados, salario semanal y calidad 1-100. Permite contratar, renovar y despedir con liquidacion pequena.
- Existen uno por departamento desde el inicio para todos los clubes; el numero de plazas depende **provisionalmente de la division inicial**. Esto NO implementa las instalaciones futuras.
- Su influencia es acotada y con rendimiento decreciente: mas empleados no multiplican linealmente el progreso ni reemplazan potencial, edad, minutos o forma fisica.
- El primer equipo gestiona directamente a su personal. Los equipos de IA renuevan contratos de manera automatica para evitar vaciar sus departamentos en carreras largas. El Inbox avisa antes de vencimientos del personal propio.
- Los salarios se integran en la contabilidad mensual, ajustando el gasto operativo que antes representaba implicitamente parte del personal. Los fichajes adicionales aumentan los costos reales.

## Entrenamiento

- Un selector por grupo: titulares, suplentes y resto del plantel.
- Modos: automatico, liviano, equilibrado, intensivo. Valores iniciales: liviano/equilibrado/intensivo.
- Proteccion de condicion habilitada por defecto: por debajo de 70, liviano; entre 70 y 85 se limita la intensidad a equilibrado. Los rangos pueden editarse.
- En modo automatico se consideran condicion, fatiga y proximidad del siguiente partido.
- Se mantiene el **foco individual de desarrollo existente** y la calidad del entorno previo. No se generan sesiones diarias manuales ni un segundo sistema de desarrollo.
- El entrenamiento se aplica solo al avanzar dias de la partida, registrando una influencia pequena en la revision mensual de atributos. Abrir la pantalla no consume tiempo ni modifica jugadores.

## Centro medico

- Lista real de ausencias del primer equipo, nombre de lesion, fecha y dias estimados para volver.
- Si la ausencia tiene al menos siete dias por delante, se habilita UNA eleccion por episodio: conservador (pronostico normal, sin riesgo adicional) o agresivo (retorno adelantado, con probabilidad acotada de recaida).
- La decision agresiva se resuelve deterministicamente a partir del episodio y la semilla de partida, para impedir explotar el sistema guardando/cargando hasta obtener otro resultado.
- Una recaida prolonga la ausencia real, queda reflejada en el seguimiento medico y puede generar una notificacion y una consecuencia moderada en confianza/moral.
- Los jugadores pueden preferir tratamientos distintos segun su personalidad; la decision de su entrenador repercute ligeramente en la relacion que ya existe en TS-25.
- No hay tratamientos obligatorios para molestias breves. No se simulan operaciones, especialistas ni lesiones en pleno partido; el motor actual evalua nuevas lesiones tras los encuentros.

## Archivos principales

- `src/football_manager/domain/club_support.py`: modelo, invariantes y limites.
- `src/football_manager/services/club_support.py`: acciones y efectos del cuerpo tecnico, entrenamiento y medicina.
- `src/football_manager/services/player_development.py`: enlace a la progresion mensual.
- `src/football_manager/services/player_aging.py`: recuperacion medica y recaidas.
- `src/football_manager/services/club_economy.py`: salarios y contabilidad.
- `src/football_manager/services/manager_inbox.py`: opiniones, alertas y vencimientos.
- `src/football_manager/ui_shell/{application,server,progression}.py`: acciones HTTP y avance del juego.
- `frontend/portable/club_support.{js,css}` y `portable.js`: pantallas Staff, Training y Medical Centre.
- `tests/test_ts_26_club_support.py`: pruebas de regresion nuevas.

## Guardado y compatibilidad

El grafo de partidas utiliza version 18 (TS-25 usaba 17), y migra una partida version 17 creando los departamentos necesarios sin reemplazar jugadores, contratos ni el Inbox. La informacion nueva de contrataciones, entrenamientos y tratamientos se guarda en el estado de carrera SQLite existente. No se agregaron controles visuales de Guardar/Cargar: siguen pendientes segun el roadmap.

## Limites conocidos

- No se ha verificado aun el aspecto de las tres pantallas en Windows.
- No se ha ejecutado una simulacion completa de 20 temporadas sobre TS-26.
- Instalaciones reales y evolucion de sus niveles siguen reservadas para una version futura.
- La calidad de personal y las cifras de balance son parametros iniciales; requieren observacion en partidas humanas prolongadas.

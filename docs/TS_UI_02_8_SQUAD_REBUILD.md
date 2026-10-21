# TS-UI-02.8 - Rebuild de directorio y cabecera de Squad

## Objetivo

Reconstruir las dos areas aprobadas (lista izquierda y hero del jugador) en
componentes visuales independientes, sin encadenar ajustes de los estilos
anteriores. Mantener el motor de simulacion, el contenido interno de las pestanas
y la identidad escalable por club.

## Comportamiento

- Directorio: avatar reemplazable por ID, nombre, numero de camiseta si existe,
  capitania segun los roles efectivos del juego, posicion principal, edad,
  nacionalidad, moral, condicion, GRL y flecha de seleccion.
- Clic en fila: selecciona dentro de Squad; boton especifico ↗ abre el perfil.
- Hero: retrato, nombre, posiciones, disponibilidad, camiseta del club,
  escudo atenuado detras, dorsal registrado, GRL actual y OVR base.
- Camiseta: nuevo `home_kit_clean.webp` con canal alfa recuperado desde la
  camiseta original; la version antigua permanece para compatibilidad.
- Ajuste de Perfil: mapa tactico y comparacion de rol lado a lado en escritorio;
  atributos completos debajo, sin altura extendida artificial de la cancha.
- Pestañas: siguen actualizando solo el inspector interno; no se reconstruye
  el directorio al cambiar de pestaña.
- Catalogo: club_id -> imagenes, nombre y variables de color; clubs futuros
  sin camiseta con imagen obtienen el fallback ilustrado.

## Lo que NO se modifico

- Lógica deportiva, estadisticas y contratos del motor Python.
- Formato de guardado, bases de datos, reglas de potencial.
- Pestañas de Temporada, Estado o Contrato/Acciones fuera de sus estilos compartidos.
- Datos reales de jugadores, numeros y capitanias (nunca se inventan).

## Validaciones

Vease `TS_UI_02_8_TEST_REPORT.md`. La captura de Chromium es una
aproximacion visual aislada, no una prueba en el sistema Windows del usuario.

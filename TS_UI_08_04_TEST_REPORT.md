# TS-UI-08.04 — Scouting, identidad escalable y rangos de atributos

## Base y contenido

Parche **incremental** preparado a partir del proyecto subido (`football-manager-2026.zip`, TS-UI-08.03), **con TS-FIX-01 y TS-FIX-02 aplicados en ese orden**. La entrega reemplaza solamente los archivos listados en el manifiesto. No incluye un repositorio entero ni modifica los elementos de negociación de TS-FIX-02.

## 1. Identidad de jugadores, clubes y países

- La lista lateral muestra **retrato, posición, edad, bandera e insignia** de cada jugador. Reemplaza el nombre del país y del club por los recursos visuales, conserva el nombre del torneo como contexto y permite consultar el club con el texto alternativo/título de la insignia.
- La cabecera del perfil tiene bandera e **insignia del club** en vez de balón genérico. Conserva el nombre y la liga del club seleccionado para no perder contexto.
- Los escudos reales se resuelven por **ID estable de club** a través del catálogo compartido y el manifiesto importable `entity-assets.json`. Cuando se carguen recursos nuevos bajo esos IDs, la vista los utiliza automáticamente sin cambios en este archivo.
- El módulo compartido conserva la jerarquía visual: **sidebar y estructura del club dirigido**; **solo el perfil del jugador seleccionado** adopta la paleta del club vendedor. Prioridad: color importado, color registrado en catálogo, extracción del escudo si existe, y color de respaldo estable por ID si no hay ningún dato visual auténtico. Un color de respaldo NO es el color oficial del club.
- Sin imagen oficial, la insignia es un **escudito con iniciales**; no se suplanta con el escudo de otro equipo ni se utiliza una pelota. Si falla una imagen importada, también se convierte en escudito.
- El módulo de banderas acepta **códigos ISO de dos letras** y nombres de nacionalidad habituales. Las banderas de Inglaterra, Escocia y Gales están incluidas como SVG locales. Los otros países reconocidos usan el indicador nacional emoji. Si llega un nombre sin correspondencia, se muestra un marcador neutro sin asignar una bandera falsa.
- Se conserva el servicio ID-clave de retratos ilustrados y fotos importables existente; no se generan fotografías reales.

## 2. Indicaciones sin informes

- El API de Scouting devuelve **rangos deterministas** para los atributos técnicos, mentales, físicos y de portero (cuando existen) de los jugadores sin informe. No entrega en ese bloque los enteros reales ni la media general, el precio de mercado o el potencial oculto.
- La banda de un mismo jugador/atributo es **estable entre lecturas**. Cambia de forma gradual cuando evoluciona el atributo real o aumenta el progreso de observación. **La amplitud disminuye con el progreso**, y un informe completado usa bandas más estrechas según calidad del observador. Esto no convierte la banda en un atributo exacto ni implica una probabilidad de acierto.
- Las bandas se muestran tanto en **Attributes** (grupos completos) como en una vista compacta de **Overview** (cuatro atributos representativos). Se identifican como estimaciones.
- GRL, valor y potencial permanecen en los espacios anteriores y **ocultos (`??`) sin conocimiento**, según la política ya vigente. Un informe completado ofrece rangos de evaluación; los jugadores de valoración pública 85+ mantienen la excepción previa (datos públicamente conocidos sin informe).
- No se rellenan altura o peso: esos datos no existen en la base actual y no se fabrican.
- No se modifican los ratings de los jugadores, sus contratos, probabilidades de traspaso, calendario, informes guardados ni formato de partidas. El grafo de guardado sigue en **versión 27**.

## 3. Optimización visual

- Cabecera de Scouting ligeramente más compacta, filas más densas, mejor jerarquía en la lista, bandera visible junto a edad y puesto, insignia del club en lugar del nombre repetido y más información útil dentro de Overview.
- En ventanas angostas se reduce la barra lateral a iconos para conservar ancho útil; los perfiles se distribuyen verticalmente. Se mantiene el desplazamiento interno de la lista y la ficha.

## 4. Verificaciones realizadas

1. **16 pruebas Python aprobadas** en selecciones controladas: 3 nuevas de bandas/identidad, 4 de identidad 08.03, 4 de 08.02, 2 de búsqueda/informes existentes y 3 de conocimiento de mercado TS-FIX-02. Se ejecutaron en grupos para limitar recursos; no representa toda la suite histórica.
2. **6 casos de banderas JavaScript aprobados**: Inglaterra, Escocia, Gales, Argentina, código `DE` y país desconocido. Comprobación sintáctica de los archivos JavaScript modificados y compilación de Python.
3. **Medición de Scouting**: un modelo de **2.002 jugadores** se construyó en aproximadamente **0,17 segundos** en la máquina de prueba, y su respuesta JSON completa ocupa aproximadamente **5,38 MB**. Estos números no garantizan el mismo rendimiento en otros equipos.
4. **Prueba de navegador aislada con HTML/CSS/JS de producción** (transportando una muestra del modelo real): 32 jugadores, 32 banderas, 32 insignias, 35 atributos por futbolista de campo, cambio de paleta entre dos clubes y ausencia de errores JavaScript; se inspeccionó ancho a 1.366, 1.024 y 390 px sin desbordamiento horizontal del documento.
5. Se generaron capturas de las pestañas Overview y Attributes y se revisó la distribución.

**Límites**: El entorno de navegador bloquea navegar directamente a `127.0.0.1` desde Chromium, por lo que la prueba visual montó el módulo real con los datos del motor inyectados en una página de comprobación. **No** equivale a una prueba end-to-end de navegación nativa en el equipo del usuario. No se ejecutó una temporada completa ni se probó la partida concreta del usuario; tampoco se recalcularon los datos de ningún guardado.

## 5. Compatibilidad y alcance pendiente

El ZIP no reemplaza el motor del partido, TS-FIX-01, TS-FIX-02, acuerdos de traspaso, cuotas, negociaciones ni su tolerancia. Para pintar escudos reales de todos los clubes en la futura BD, deberá importarse su catálogo de imágenes y/o colores bajo sus IDs. La identificación nacional debe normalizarse a nombres reconocidos o códigos ISO. Los nombres no reconocidos quedan neutros, no incorrectos.

Instalar sobre la base exacta indicada en `TS_UI_08_04_INSTALL.txt`; detener Python y hacer `Ctrl + F5` para cargar scripts/estilos/recursos SVG nuevos.

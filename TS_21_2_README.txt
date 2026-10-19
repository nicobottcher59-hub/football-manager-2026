TS-21.2 - Desarrollo global y potencial
=======================================

BASE: juego completo con TS-22 Squad & Match Presentation ya instalado.
Paquete incremental: no contiene el juego completo.
No requiere Node, npm ni compilacion de frontend en tu computadora.

INSTALACION EN WINDOWS
1. Guarda la carrera completa en SQLite. Conserva un respaldo del archivo y del proyecto.
2. Cierra el juego y el servidor Python (tambien la consola del launcher).
3. Extrae el ZIP en la raiz donde esta INICIAR_INTERFAZ_WINDOWS.bat.
   Conserva las rutas y acepta reemplazar los archivos. No extraigas en otra subcarpeta.
4. Desde esa raiz:
   python tools/verify_ts212_development_package.py
   python -m pytest -ra tests/test_ts_21_2_player_development.py
5. Reinicia INICIAR_INTERFAZ_WINDOWS.bat y recarga con Ctrl + F5.
6. Carga la carrera completa. Revisa un perfil en Squad.
7. Guarda normalmente para conservar los nuevos datos. No se agrega autoguardado.

GUARDADOS
- Estado completo version 7; migra versiones compatibles anteriores hasta la 6.
- Cargar no sobrescribe el archivo. La version 7 se escribe al guardar.
- No se puede garantizar que TS-22 lea un guardado version 7: usa el respaldo para volver atras.
- Fechas de nacimiento existentes, atributos, estado y personalidad se conservan al migrar.
- El PA y la curva se inicializan una sola vez y se guardan; no hay mejoras retroactivas.
- JSON de resultados no es una copia de carrera completa y no preserva desarrollo.

DONDE VERLO
Squad -> nombre/detalle del jugador -> debajo de los radares: Player development.
Muestra nacimiento, edad por cumpleanios, proxima revision, minutos del periodo,
cambios reales de atributos e historial. Los rivales tienen la misma vista en solo lectura.
El PA exacto y los parametros internos de la curva no se muestran.
Development focus: Balanced / Technical / Mental / Physical.
El cambio orienta el siguiente cierre mensual, no da una mejora instantanea; guarda despues.

COMO SE PROCESA
Se registran minutos reales y roles de los partidos. El primer dia del mes se cierra
el periodo anterior para todos los futbolistas persistentes, incluso los que no jugaron.
Se acumulan fracciones internas: no ver +1 en el primer mes no significa que este roto.
CA es un presupuesto estable de atributos de la posicion de origen, NO OVR ni ACT.
Las formulas de OVR/ACT, cansancio, partidos y posiciones no se sustituyen.
La referencia OVR del historial excluye condicion, forma y familiaridad.

ALCANCE
Hay perfiles variados, curvas individuales, personalidad TS-20, oportunidades,
sobrecarga y enfasis de desarrollo. Edades 15/16 admitidas por las mismas reglas.
Entrenamiento/cuerpo tecnico usan un entorno neutral provisional almacenado por club.
NO hay todavia instalaciones, entrenadores individuales ni calendario de entrenamiento.
Una lesion activa en la revision pausa el crecimiento; su historial medico y efectos
permanentes se completan en TS-21.3.
NO incluye declive por edad, retiros, generacion de canteranos ni Newgens.
NO prueba equilibrio demografico de 15-20 temporadas; los ensayos largos de cohortes
solo comprueban crecimiento, techos y diversidad de trayectorias.
No hay migracion Git, cambios de cuenta ni modificaciones de GitHub Actions.

HERRAMIENTAS OPCIONALES (SOLO PYTHON; DATOS DESECHABLES)
python tools/validate_ts212_development.py --mode cohort --players 120 --years 20
python tools/validate_ts212_development.py --mode season
python tools/validate_ts212_development.py --mode benchmark --players 20000
Estas pruebas son mas lentas y no son necesarias para instalar el paquete.
Ver TS_21_2_TEST_REPORT.md para los resultados exactos y sus limitaciones.

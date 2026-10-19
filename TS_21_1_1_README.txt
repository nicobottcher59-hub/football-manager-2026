TS-21.1.1 - Optimización y calendario
=======================================

BASE: TS-21.1 Mundo Inglés, sobre TS-20 y el hotfix TS-19 LM/RM + arquero fijo.
No es una instalación completa. Python 3.11 o superior, como el proyecto actual.
No requiere Node, npm, recompilar el frontend ni instalar nuevas dependencias.

1. Guardá tu carrera y cerrá el juego. Conservá una copia del proyecto y
   de la base de guardados SQLite.
2. Extraé el contenido en la raíz que contiene INICIAR_INTERFAZ_WINDOWS.bat,
   conservando las carpetas src/, tests/ y tools/. Aceptá reemplazar archivos.
3. Verificá desde esa raíz:
   python tools/verify_ts2111_performance_calendar_package.py
4. Pruebas de la actualización y del mundo persistente:
   python -m pytest -ra tests/test_ts_21_1_1_performance_calendar.py tests/test_ts_21_english_world.py
5. Reiniciá con INICIAR_INTERFAZ_WINDOWS.bat. Recargá con Ctrl + F5.
   Para seguir una carrera, cargá su guardado SQLite completo. Las fechas
   futuras generadas se revisan al cargar. Guardá normalmente para conservar
   los cambios: el parche no sobrescribe el archivo original durante la carga.

El formato completo sigue siendo versión 5. No se reescriben partidos jugados,
resultados, fechas de hoy o anteriores, ni fixtures importados como oficiales.
No se modifican atributos, fatiga, fórmulas OVR/ACT, fuerza de Northbridge,
planteles, roles, ni la interfaz. Las fechas futuras corregidas sí pueden cambiar
la recuperación y los resultados posteriores de una carrera.

Política: preferencia de 72 horas y fines de semana cuando sean viables,
comprobando ambos clubes. Se mantiene el piso técnico anterior de 48 horas;
la congestión y las fechas protegidas pueden dejar excepciones a las 72 horas.
No es una afirmación sobre reglamentos oficiales.

Herramientas opcionales, sobre carreras sintéticas desechables:
   python tools/benchmark_ts2111.py --repeats 3
   python tools/check_ts2111_calendar.py
   python tools/check_ts2111_long_calendar.py
La última prueba aísla SOLO el calendario durante 15 temporadas. No simula
15 temporadas completas de evolución individual de futbolistas.

Usá el verificador de este paquete. Los manifiestos de actualizaciones
anteriores describen archivos de sus versiones anteriores y pueden detectar
como modificados los archivos que este incremental reemplaza correctamente.
La comprobación SHA-256 valida integridad, no el comportamiento futbolístico.

Informe: TS_21_1_1_TEST_REPORT.md
Mediciones: TS_21_1_1_BENCHMARK.json

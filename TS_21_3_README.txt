TS-21.3 - Envejecimiento, lesiones y retiro
========================================
Base requerida: TS-21.2 Desarrollo Global y Potencial instalada.
ZIP incremental; no es el juego completo. No requiere Node ni npm.

INSTALACION EN WINDOWS
1. Guarda la carrera completa y conserva copia del proyecto y del SQLite.
2. Cierra el juego Y el servidor Python.
3. Extrae este ZIP en la raiz que contiene INICIAR_INTERFAZ_WINDOWS.bat.
   Conserva las rutas y reemplaza los archivos. No copies dentro de otra subcarpeta.
4. Abre una consola en esa raiz y ejecuta:
   python tools/verify_ts213_aging_package.py
   python -m pytest -ra tests/test_ts_21_3_player_aging.py
5. Reinicia INICIAR_INTERFAZ_WINDOWS.bat y recarga con Ctrl + F5.
6. Carga el guardado completo. La migracion no sobrescribe el archivo al cargar:
   guarda normalmente para escribir la version 8.

ALCANCE
- Curvas individuales de declive, acumulacion fraccionaria y revision mensual.
- Perdidas por grupos de atributos; no un descuento directo al OVR por edad.
- Lesiones fechadas, recuperacion por calendario y posibles secuelas fisicas.
- Evaluaciones pospartido: el simulador rapido no genera eventos de lesion
  dentro del encuentro. Las nuevas evaluaciones pueden causar ausencias futuras.
- Misma regla para ambos equipos y todos los clubes persistentes.
- Retiros solicitados por cada perfil y resueltos al cambiar de temporada.
- Se archivan los retirados sin borrar identidad, nacimiento o estadisticas.
- Proteccion provisional de planteles: si falta cobertura, se posterga el retiro.
  No se generan sustitutos invisibles ni se rejuvenecen jugadores.
- Preparacion del proximo partido: reemplaza seleccionados no disponibles,
  conservando titulares sanos y el plan tactico.

PRESENTACION
La mejora visual del panel de desarrollo queda para mas adelante. Solo se
corrigieron signos negativos y se agregaron estado medico/retorno/retiro en los
detalles existentes. El prepartido muestra las ausencias; el resumen, las nuevas
evaluaciones medicas. No se implemento otra pantalla de Medical Centre.

COMPATIBILIDAD
Guardado completo: version 8. Importa las versiones anteriores compatibles,
incluida la 7. Una vez guardado en v8, usa este codigo o posterior; conserva
el respaldo v7 para volver a TS-21.2. No hay autoguardado nuevo.
No cambia atributos/PA/nacimiento al migrar, no simula declive retroactivo.
Un flag antiguo de lesion sin fechas permanece identificado como fecha desconocida;
no se inventan su duracion ni secuelas. El JSON de resultados no sustituye al
SQLite completo y no contiene una carrera individual recuperable.

LIMITES
No incluye canteras, Newgens, nuevos entrenadores/instalaciones, transferencias
ni rediseño del panel. Los perfiles son reutilizables por futuras bases reales
sin reglas de envejecimiento por liga. La renovacion generacional sera necesaria
para sostener cantidad y distribucion de talento durante 15-20 temporadas.
Los controles de cobertura son provisionales hasta disponer de reemplazos.
Los parametros de riesgo y declive son decisiones de balance del juego, no
predicciones medicas ni datos de futbolistas reales.

VALIDACION OPCIONAL, MAS LENTA
python tools/validate_ts213_careers.py season --seasons 2 --output ts213_seasons_local.json
python tools/validate_ts213_careers.py cohort --players 140 --years 20 --output ts213_cohort_local.json
La segunda prueba observa individuos; no demuestra equilibrio de poblacion.
Estos comandos no abren partidas personales ni requieren GitHub Actions.

Lee TS_21_3_TEST_REPORT.md para resultados ejecutados y limitaciones.

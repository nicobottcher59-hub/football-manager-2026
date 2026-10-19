TS-18.6 - PAQUETE UNIFICADO (parche original + validacion ampliada)
====================================================================

Este ZIP contiene AMBAS entregas de TS-18.6 en un solo archivo. NO incluye
el juego completo ni el parche TS-18.5: es un parche incremental de tests.
No modifica archivos del codigo productivo.

REQUISITO: instalar sobre el repositorio con TS-18.5 REVISADO ya integrado.
Extraer este ZIP directamente en la raiz del proyecto, manteniendo carpetas.
NO es necesario aplicar ninguno de los dos ZIP TS-18.6 anteriores.

Incluye:
- tests/test_ts_18_6_football_regression_stress.py (bateria inicial)
- tests/test_ts_18_6_spatial_seeded_regression.py (extension 2D)
- TS_18_6_PATCH_INSTRUCTIONS.txt (instrucciones originales)
- TS_18_6_VALIDATION_REPORT.md (informe de pruebas)
- TS_18_6_WINDOWS_VALIDATION.ps1 (script para pruebas en Windows)
- Manifiestos originales y manifest de integridad unificado

GITHUB DESKTOP
Branch: test/ts-18-6-football-regression-stress
Summary: test(football): consolidate TS-18.6 regression and spatial validation

COMANDOS
python -m pytest -ra tests/test_ts_18_6_football_regression_stress.py tests/test_ts_18_6_spatial_seeded_regression.py
python -m pytest -ra

ESTADO: VALIDACION PARCIAL. La regresion completa y las pruebas de temporadas
no terminaron en Linux por limites de tiempo. Ejecutarlas en Windows antes
de considerar TS-18.6 validado o hacer merge.

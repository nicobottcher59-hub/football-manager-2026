# TS-24.10 — Informe técnico de implementación y pruebas

**Versión base:** TS-24.9. **Formato de partida:** 16 (sin cambio de esquema).

## Funcionalidad

1. Finalización incondicional de retiros solicitados por el jugador al cierre de la temporada. Se descarta el veto por cobertura táctica o cantidad de arqueros.
2. Formalización de retiros de jugadores cedidos, terminación de préstamo, liberación del contrato y archivo del futbolista.
3. Tratamiento coherente de jugadores lesionados y limpieza transaccional de índices médicos, ofertas pendientes y contratos.
4. No renovación y no negociación de un jugador cuya decisión de retirarse está confirmada.
5. Agentes libres: retiro subordinado a su propia decisión y actualización de la progresión; no expulsión por edad o desempleo solamente.
6. Diagnóstico financiero informativo que permite déficits, sin arreglar balances creando dinero.

## Pruebas realizadas

- **11/11 nuevas pruebas TS-24.10:** aprobadas. Incluyen posiciones críticas, legados `deferred`, lesiones, préstamos, rollback, no renovación, persistencia v16 de grafo y comportamiento de agente libre.
- **4/4 pruebas antiguas focalizadas de envejecimiento:** aprobadas tras adaptar expectativas al criterio nuevo.
- **Suite histórica conjunta:** una ejecución de módulos TS-24.6 a TS-24.10 superó varias pruebas iniciales pero agotó el tiempo en una prueba lenta; no se contabiliza como batería completa aprobada.
- **Auditoría acelerada de cinco temporadas (semilla 6606):** completada. 92 clubes; 0 huecos titulares al año 5; mínimo 21 jugadores por club; 298 fichajes entre clubes y 11 clubes con caja negativa. Hubo temporalmente un equipo con solo un arquero en el segundo año, subsanado en el tercero. El auditor heredado lo marcó como incidencia dura, pero es una carencia deportiva permitida por el diseño actualizado.
- **20 temporadas TS-24.10:** no ejecutadas; no hay certificado de equilibrio a largo plazo.
- **Partidos senior nativos durante esta auditoría:** no ejecutados; se utilizó marcador acelerado.
- **Prueba Windows:** no ejecutada.

## Riesgos

Retirar sin veto es esencial para la autonomía, pero deja visible una limitación distinta: clubes incapaces de presentar once o arquero podrían requerir una política explícita de emergencia/derrota administrativa en el motor completo. No hay un reemplazo garantizado ni se retiene al futbolista para evitarla.

Las pérdidas económicas, las vacantes de suplentes y la planificación imperfecta son resultados válidos. Deben tratarse como problemas de clubes individuales, no metas globales de cero.

## Instalación

1. Partir de TS-24.9, cerrar el juego y respaldar carpeta y partida SQLite.
2. Extraer ZIP incremental sobre la raíz junto a `INICIAR_INTERFAZ_WINDOWS.bat`.
3. Ejecutar `python tools/verify_ts2410_player_autonomy_package.py`.
4. Reiniciar el juego y actualizar navegador con Ctrl+F5.

## GitHub Desktop

BRANCH: `feat/ts-24-10-player-retirement-autonomy`

SUMMARY: `fix(career): honor player retirement decisions independently of squad depth`

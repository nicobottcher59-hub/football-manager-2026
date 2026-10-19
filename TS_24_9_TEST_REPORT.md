# TS-24.9 — Informe técnico y pruebas

**Base obligatoria:** TS-24.8. **Guardado:** SQLite v16, sin migración.

## Cambios incorporados

- Reemplazos de jugadores con retiro solicitado antes de perder titulares o suplentes; compradores IA respetan presupuesto, posiciones y consentimiento.
- Retiro de profesionales de 43+ sin exigencias excesivas de banquillo, pero nunca sin un once de titulares o sin dos porteros naturales.
- En renovaciones de IA, control de cobertura de seis meses para el déficit operativo mensual previsto; contratos existentes permanecen intactos.
- Auditoría reproducible con semillas 6606, 7707 y 8808 durante cinco temporadas y semilla 9909 hasta veinte años.
- Muestra independiente de 18 partidos reales del motor FastMatchSimulator y registro comprobable de uso de juveniles.
- Corrección de compatibilidad: semilla de mundo como parámetro efímero; no añade campos a DevelopmentSession y conserva esquema v16.

## Validación y resultados

| Batería | Estado |
|---|---|
| Pruebas nuevas TS-24.9 | 7/7 aprobadas |
| Regresiones mercado y préstamos TS-24.5/24.6 | 24/24 aprobadas (repetidas tras corregir SQLite) |
| Regresiones TS-24.7 | 8/8 aprobadas (7 unitarias + transición anual separada) |
| Regresiones TS-24.8 | 9/9 aprobadas |
| Tres mundos de cinco años | 15/15 temporadas-semilla completadas |
| Horizonte independiente de 20 años | 20/20 temporadas completadas; **integridad NO aprobada** (jugador de 50+ años) |
| Partidos completos y minutos U23 | 18/18 partidos completados |
| Compilación Python | Aprobada |
| Instalación limpia sobre TS-24.8 | Verificada con SHA-256 y tests (ver proceso de publicación) |
| Suite histórica global | No ejecutada íntegramente; tests heredados incompatibles ya conocidos |
| Ejecución nativa Windows | No realizada |
**Resultado de integridad: NO APROBADO.** Se detectó **1 incidencia grave** al cierre del año 20:
un futbolista activo de **50 años o más**, pese a que la retirada debía haberse solicitado
anteriormente. El sistema la aplazó para conservar la cobertura del once. No se fuerza
su eliminación ni se inventa un reemplazo. Es una limitación abierta que necesita
un flujo de reemplazo/retirada probado en varias semillas. Las 20 temporadas sí
terminaron de procesarse, pero eso no implica que el mundo esté equilibrado.

### Comparación controlada a cinco años — misma semilla 6606

| Indicador | TS-24.8 | TS-24.9 |
|---|---:|---:|
| Clubes profesionales | 92 | 92 |
| Huecos titulares | 0 | 0 |
| Huecos de suplentes | 11 | 10 |
| Clubes con caja negativa | 11 | 10 |
| Jugadores U23 | 231 | 222 |
| Mayores de 45 | 0 | 0 |

### Auditoría de veinte temporadas — semilla 9909

| Indicador | Año 5 | Año 10 | Año 20 |
|---|---:|---:|
| Clubes profesionales | 92 | 92 | 92 |
| Huecos titulares | 0 | 0 | 0 |
| Huecos de suplentes | 10 | 16 | 11 |
| Clubes con caja negativa | 10 | 13 | 9 |
| Jugadores U23 | 235 | 203 | 247 |
| Mayores de 45 | 0 | 0 | 14 |

### Minutos juveniles reales

- 18 partidos mediante FastMatchSimulator: **2,517** minutos sub-23, en 15 encuentros.
- 9 titulares jóvenes proyectados, pero solo 6 de esas proyecciones tuvieron minutos confirmados: la alineación puede cambiar tras la revisión de desarrollo previa al partido.

## Limitaciones y riesgos abiertos

- La prueba larga utiliza marcadores ligeros para partidos senior: no verifica 20 años de minutos, fatiga, lesiones o progresión basada en partidos completos.
- Los clubes con caja negativa siguen siendo un problema económico; no se cubrieron déficits creando dinero nuevo ni se diseñó un procedimiento de insolvencia.
- **Incidencia grave abierta:** al menos un futbolista activo de 50 años o más en el año 20; las garantías de reemplazo no bastaron para efectuar su retiro.
- Persisten huecos de suplentes y veteranos extremos; los puestos titulares sí permanecen cubiertos.
- Tres semillas y una extensión de veinte años son muestras, no un estudio estadístico completo.
- Sin rediseño estético ni automatización de préstamos entre clubes IA.

## Instalación

1. Tener TS-24.8 instalada, cerrar el juego y respaldar proyecto y SQLite.
2. Extraer el ZIP en la carpeta raíz junto a `INICIAR_INTERFAZ_WINDOWS.bat`.
3. Ejecutar `python tools/verify_ts249_calibration_package.py`.
4. Abrir el juego y pulsar Ctrl + F5 en el navegador.

## GitHub Desktop

BRANCH
```text
feat/ts-24-9-multiseed-market-calibration
```
SUMMARY
```text
test(career): calibrate succession, contract viability and multiseed horizons
```


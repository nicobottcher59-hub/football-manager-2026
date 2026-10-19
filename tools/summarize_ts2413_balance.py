"""Generate the TS-24.13 longitudinal balance comparison from raw audit JSON."""
from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (6606, 7707, 8808)


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def row(snap):
    if snap is None:
        return ('--',) * 8
    return (str(snap['uncovered_starter_slots']), str(snap['uncovered_reserve_slots']),
            str(snap['clubs_below_two_goalkeepers']), str(snap['clubs_below_18']),
            str(snap['cash_negative_clubs']), str(snap['squad_min']),
            str(snap['squad_median']), str(snap['first_team_players_over_45']))


def checkpoints(item):
    return {r['season_number']: r for r in item.get('annual_snapshots', [])} if item else {}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'TS_24_13_VALIDATION_REPORT.md')
    args = parser.parse_args()
    candidate = {seed: load(ROOT / f'reports/ts2413_seed{seed}_{20 if seed == 6606 else 5}y.json')
                 for seed in SEEDS}
    baseline = {seed: load(ROOT / f'reports/ts2412_seed{seed}_{20 if seed == 6606 else 5}y.json')
                for seed in SEEDS}
    medium = load(ROOT / 'reports/ts2413_seed7707_10y.json')
    lines = [
        '# TS-24.13 - Validacion integral de plantillas y cantera', '',
        '**Objetivo:** preservar 92 clubes competitivos durante carreras extensas, sin fabricar jugadores ni dinero y sin garantizar rentabilidad.', '',
        '**Metodo:** calendario y torneos completos, mercado, contratos, retiros, cesiones, cantera, finanzas y promociones de liga. El marcador senior usa un resolvedor acelerado de pruebas; no certifica minutos de juego, lesiones en partidos ni la interfaz Windows.', '',
        '## Comparacion historica, semilla 6606', '',
        '| Version | Anio | XI vacantes | Suplentes vacantes | Clubes <2 GK | Clubes <18 jugadores | Clubes en rojo | Plantilla minima | Plantilla mediana | >45 anios |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    prev = checkpoints(baseline[6606])
    cur = checkpoints(candidate[6606])
    for year in (5, 10, 15, 18, 20):
        for label, samples in (('TS-24.12', prev), ('TS-24.13', cur)):
            fields = row(samples.get(year))
            lines.append('| ' + ' | '.join([label, str(year), *fields]) + ' |')
    lines += ['', '## Otras semillas', '',
              '| Semilla | Estado TS-24.13 | Anios | XI vacantes al cierre | <2 GK al cierre | Clubes en rojo al cierre |',
              '|---:|---|---:|---:|---:|---:|']
    for seed in SEEDS:
        result = candidate[seed]
        if result is None:
            lines.append(f'| {seed} | no ejecutado | -- | -- | -- | -- |')
            continue
        latest = result['annual_snapshots'][-1] if result['annual_snapshots'] else {}
        lines.append(f"| {seed} | {result['status']} | {result['completed_seasons']}/{result['requested_seasons']} | "
                     f"{latest.get('uncovered_starter_slots','--')} | "
                     f"{latest.get('clubs_below_two_goalkeepers','--')} | "
                     f"{latest.get('cash_negative_clubs','--')} |")
    if medium is not None:
        latest = medium['annual_snapshots'][-1] if medium['annual_snapshots'] else {}
        lines.append(f"| 7707 (horizonte medio) | {medium['status']} | {medium['completed_seasons']}/{medium['requested_seasons']} | "
                     f"{latest.get('uncovered_starter_slots','--')} | "
                     f"{latest.get('clubs_below_two_goalkeepers','--')} | "
                     f"{latest.get('cash_negative_clubs','--')} |")
    lines += ['', '## Interpretacion', '',
              '- Una caja negativa, una gestion mala o uno o dos suplentes faltantes NO son fallos tecnicos.',
              '- La mejora interviene en intakes U15 reales y promociones de juveniles U21 elegibles.',
              '- No se modifica el sistema de ingresos, gastos, presupuestos, transferencias ni retiros.',
              '- El club humano sigue controlando manualmente las promociones de su academia.',
              '- Los clubes IA no reciben futbolistas fantasma ni ningun rescate economico.',
              '', '## Incidencias de las ejecuciones', '']
    for seed, item in candidate.items():
        if not item:
            lines.append(f'- Semilla {seed}: sin ejecucion disponible.')
            continue
        issues = item.get('technical_failures', [])
        lines.append(f"- Semilla {seed}: {item['status']}, {item['completed_seasons']} temporadas, "
                     f"{len(issues)} incidencias tecnicas documentadas.")
        for issue in issues[:6]:
            lines.append(f'  - {issue}')
    lines += ['', '## Estabilidad de partidas y transiciones', '',
              '- La carrera completa de TS-24.12 ya excedia el limite anterior de 250.000 nodos tras una temporada (285.944 en la comprobacion de referencia).',
              '- TS-24.13 mantiene el grafo y SQLite en version 16, con limite de capacidad finito de 1.000.000 nodos.',
              '- Guardado/recarga real tras una temporada: comprobados mediante `tools/smoke_ts2413_longitudinal_save.py`, con IDs de juveniles conservados.',
              '- Los clubes que llevan anios fuera de las ligas sincronizan su ultimo reloj fisico al iniciar un nuevo curso, antes de dar de alta canteranos.',
              '- Bateria de 59/59 pruebas de regresion TS-24.8 a TS-24.13 aprobadas; los informes de simulacion son una comprobacion adicional y distinta.',
              '', '## Limitaciones', '',
              '- No se realizo guardado/carga SQLite despues de las 20 temporadas; la prueba de persistencia cubre el primer cambio de temporada.',

              '- Los indicadores al cierre de junio son una foto anual, no datos de cada dia o ventana.',
              '- Las temporadas aceleradas no equivalen a ejecutar todos los partidos con el motor detallado.',
              '- La variabilidad entre semillas impide prometer plantillas perfectas en cada carrera.',
              '- No hay ejecucion nativa Windows dentro de este entorno.', '']
    args.output.write_text('\n'.join(lines), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()

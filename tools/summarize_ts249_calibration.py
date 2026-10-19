"""Summarize TS-24.9 diagnostics without inventing uncompleted checkpoints.

python tools/summarize_ts249_calibration.py --multi reports/ts249_multi_seed.json --long reports/ts249_long_horizon.json --minutes reports/ts249_real_minutes.json --output TS_24_9_LONG_HORIZON_REPORT.md
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import median


def _read(path:Path)->dict:
    return json.loads(path.read_text(encoding='utf-8'))

METRICS=[
 ('Puestos titulares vacíos','uncovered_starter_slots'),
 ('Puestos suplentes vacíos','uncovered_reserve_slots'),
 ('Clubes con caja negativa','cash_negative_clubs'),
 ('Jugadores sub-23','young_first_team_players_u23'),
 ('Jugadores mayores de 45 años','first_team_players_over_45'),
 ('Clubes que exceden presupuesto salarial','clubs_payroll_over_wage_budget'),
 ('Caja mediana (millones GBP)','cash_median_gbp'),
 ('Valor de mercado mediano (GBP)','market_value_median_gbp'),
]

def _format(value,key):
    if key=='cash_median_gbp':return f'£{value/1_000_000:,.2f} M'
    if key=='market_value_median_gbp':return f'£{value:,.0f}'
    return f'{value:,.0f}'


def summarize(multi:dict,long:dict,minutes:dict,previous:dict|None=None)->str:
    # Never label partially completed or crashed simulations as final.
    if (multi['status']!='completed' or long['status']!='completed'
            or minutes['status']!='completed'):
        raise ValueError('Reports must all be complete before publishing')
    multi_runs=multi['runs']
    if len(multi_runs)<2 or any(r['seasons_completed']<5 for r in multi_runs):
        raise ValueError('Need at least two independent five-year worlds')
    one=long['runs'][0]
    if one['seasons_completed']<20:
        raise ValueError('20-year single-seed checkpoint missing')
    if multi['seeds'] and long['seeds'] and set(multi['seeds'])&set(long['seeds']):
        # Overlap is legitimate; it may indicate re-testing same seed.
        pass
    lines=['# TS-24.9 — Auditoría de múltiples semillas, 5/10/20 años y minutos reales','',
           '## Método y precauciones','',
           f"- **Semillas independientes:** {', '.join(str(i) for i in multi['seeds'])}; cinco temporadas por mundo, total {len(multi_runs)*5} temporadas-semilla.",
           f"- **Extensión separada:** semilla {one['world_seed']}, veinte temporadas aceleradas; es una muestra independiente, no prueba de precisión estadística.",
           '- La auditoría acelerada ejecuta calendarios, economía, contratos, mercados, canteras y ascensos, pero sustituye **solo el partido senior** por un resolutor de marcadores de fondo.',
           '- Por eso la auditoría larga NO representa minutos senior, lesiones, forma ni desarrollo inducido por partidos reales.',
           f"- **Partidos reales:** {minutes['matches_completed']} con FastMatchSimulator y estadísticas integradas, separados del experimento de veinte años.",
           '', '## Variación entre semillas al año 5','',
           '| Indicador | Mínimo | Mediana | Máximo |','|---|---:|---:|---:|']
    end=[r['annual_snapshots'][4] for r in multi_runs]
    for label,key in METRICS:
        vals=[i[key] for i in end]
        lines.append(f'| {label} | {_format(min(vals),key)} | {_format(median(vals),key)} | {_format(max(vals),key)} |')
    lines.extend(['',f"**Incidencias de integridad:** {sum(len(i['hard_issues']) for r in multi_runs for i in r['annual_snapshots'])} en {len(multi_runs)*5} cortes anuales, según las invariantes de este auditor. No se exige caja positiva a todos los equipos.",
                  '',f"## Recorrido de 20 años — semilla {one['world_seed']}",'',
                  '| Indicador | Año 5 | Año 10 | Año 20 |','|---|---:|---:|---:|'])
    checkpoints=[one['annual_snapshots'][i-1] for i in (5,10,20)]
    for label,key in METRICS:
        lines.append(f'| {label} | '+' | '.join(_format(cp[key],key) for cp in checkpoints)+' |')
    incident_count=sum(len(i['hard_issues']) for i in one['annual_snapshots'])
    incident_text=(', '.join(sorted(set(issue for snap in one['annual_snapshots'] for issue in snap['hard_issues'])))
                   if incident_count else 'ninguna')
    lines.extend(['',
            f"**Incidencias de integridad:** {incident_count} en 20 temporadas, según los chequeos automáticos.",
            f"**Estado de integridad del horizonte largo: {'NO APROBADO' if incident_count else 'APROBADO'}.** Detalle: {incident_text}.",
            '', '## Minutos de partidos reales — muestra limitada','',
            f"- Encuentros terminados con motor completo: **{minutes['matches_completed']}**.",
            f"- Minutos sub-23 registrados realmente: **{minutes['total_u23_minutes']:,}**.",
            f"- Encuentros con minutos sub-23: **{minutes['games_with_u23_minutes']}**.",
            f"- Titularidades juveniles proyectadas antes de revisión: {minutes['projected_rotated_u23_starts']}; con minutos constatados: {minutes['projected_rotated_u23_with_actual_minutes']}.",
            '- La última cifra NO es un porcentaje de conversión de convocatorias; una revisión de desarrollo fechada puede alterar la alineación proyectada antes de jugar.',
            '- La muestra no equivale a simular una temporada completa con resultados y desarrollo de cada jugador.',
            '', '## Comparación controlada con TS-24.8 — misma semilla 6606',''])
    if previous is not None and '6606' in [str(x) for x in multi['seeds']]:
        baseline=previous['checkpoints']['5']
        updated=next(r['annual_snapshots'][4] for r in multi_runs if r['world_seed']==6606)
        lines.extend(['| Indicador, año 5 | TS-24.8 | TS-24.9 |','|---|---:|---:|'])
        for label,key in METRICS:
            lines.append(f"| {label} | {_format(baseline[key],key)} | {_format(updated[key],key)} |")
    else:
        lines.append('No se dispone de una comparación sobre la misma semilla.')
    lines.extend(['','## Interpretación','',
            '- Los problemas de liquidez y profundidades residuales son **riesgos medidos**, no certificados como resueltos por estas pruebas.',
            '- Las carreras a largo plazo pueden presentar déficits reales; el objetivo no es forzar beneficios mediante dinero ficticio.',
            '- Las retiradas y contrataciones mantienen las salvaguardas de once titulares y dos guardametas.',
            '- El control de contratos actúa sobre **renovaciones futuras**; no reduce salarios existentes ni altera partidas anteriores.',
            '- Múltiples semillas con un horizonte corto miden variabilidad inicial; una semilla con 20 años detecta colapsos tardíos. Ambos ensayos se complementan, no se sustituyen.',
            '', '## Reproducibilidad','',
            '```bash',
            'python tools/stress_ts249_multiseed.py --seeds 6606,7707,8808 --seasons 5 --output reports/ts249_multi_seed.json',
            'python tools/stress_ts249_multiseed.py --seeds 9909 --seasons 20 --output reports/ts249_long_horizon.json',
            'python tools/audit_ts249_real_match_minutes.py --matches 18 --output reports/ts249_real_minutes.json',
            '```',''])
    return '\n'.join(lines)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--multi',type=Path,default=Path('reports/ts249_multi_seed.json'))
    ap.add_argument('--long',type=Path,default=Path('reports/ts249_long_horizon.json'))
    ap.add_argument('--minutes',type=Path,default=Path('reports/ts249_real_minutes.json'))
    ap.add_argument('--previous',type=Path,default=Path('reports/ts248_long_horizon.json'))
    ap.add_argument('--output',type=Path,default=Path('TS_24_9_LONG_HORIZON_REPORT.md'))
    args=ap.parse_args()
    old=_read(args.previous) if args.previous.is_file() else None
    report=summarize(_read(args.multi),_read(args.long),_read(args.minutes),old)
    args.output.write_text(report,encoding='utf-8')
    print(f'Written {args.output}')
if __name__=='__main__':main()

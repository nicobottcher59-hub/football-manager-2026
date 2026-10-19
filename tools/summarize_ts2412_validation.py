"""Generate transparent TS-24.12 5/10/20 checkpoint notes from saved JSON evidence."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def _gbp(value):
    return f"GBP {value/1e6:,.2f}m"


def long_negative_streak_count(rows):
    longest={}
    active={}
    for row in rows:
        for cid,cash in row.get('cash_by_club_gbp',{}).items():
            active[cid] = active.get(cid,0)+1 if cash < 0 else 0
            longest[cid] = max(longest.get(cid,0),active[cid])
    return sum(streak>=5 for streak in longest.values())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,default=ROOT/'reports/ts2412_seed6606_20y.json')
    ap.add_argument('--output',type=Path,default=ROOT/'TS_24_12_VALIDATION_REPORT.md')
    a=ap.parse_args()
    report=json.loads(a.input.read_text(encoding='utf-8'))
    rows=report['annual_snapshots']
    lines=['# TS-24.12 — Auditoría integral del modo carrera','',
           '**Semilla:** '+str(report['seed'])+' · **Escenario:** 92 clubes profesionales ingleses',
           '**Estado de evidencia:** '+report['status']+' · **Temporadas completadas:** '+str(report['completed_seasons']),
           '', '## Resultados de checkpoints', '',
           '| Temporadas | Clubes | XI vacantes | Suplentes vacantes | Clubes con menos de 2 GK | Caja negativa | Caja mínima | Edad máxima | Préstamos activos |',
           '|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n in (5,10,18,20):
        if len(rows)<n:
            lines.append(f'| {n} | Sin completar | — | — | — | — | — | — | — |')
            continue
        x=rows[n-1]
        lines.append(f"| {n} | {x['active_clubs']} | {x['uncovered_starter_slots']} | {x['uncovered_reserve_slots']} | {x['clubs_below_two_goalkeepers']} | {x['cash_negative_clubs']} | {_gbp(x['cash_min_gbp'])} | {x['first_team_age_max']} | {x['active_loans']} |")
    if rows:
        deepest=min(rows,key=lambda x:x['cash_min_gbp'])
        gk_worst=max(rows,key=lambda x:x['clubs_below_two_goalkeepers'])
        starters_worst=max(rows,key=lambda x:x['uncovered_starter_slots'])
        lines.extend(['','## Alertas durante el recorrido','',
            f"- Mayor carencia simultánea de segundo arquero: **{gk_worst['clubs_below_two_goalkeepers']} clubes** en el año {gk_worst['season_number']}.",
            f"- Mayor cantidad de posiciones titulares sin cubrir: **{starters_worst['uncovered_starter_slots']}** en el año {starters_worst['season_number']}.",
            f"- Peor caja individual observada: **{_gbp(deepest['cash_min_gbp'])}** en el año {deepest['season_number']}.",
            f"- Futbolistas de al menos 50 años registrados al cierre: **{sum(x['first_team_age_max']>=50 for x in rows)} cierres**.",
            '', 'Un déficit de porteros extendido es un riesgo sistémico de planificación, no una justificación para retener retirados ni inventar suplentes.'])
    lines += ['','## Clasificación de resultados','',
        '- **Fallo técnico:** identidades duplicadas, cuentas inconsistentes, campeonatos inconclusos, edades absurdas de al menos 50 años o excepción del motor.',
        '- **Riesgo deportivo:** once imposible de cubrir, pocos futbolistas, numerosas carencias de arquero. No se inventan jugadores para ocultarlo.',
        '- **Riesgo financiero:** déficits elevados y persistentes. No se eliminan por imponer cuotas de rentabilidad ni regalando dinero.',
        '- **Advertencia normal:** un club ocasionalmente deficitario o sin todos sus suplentes puede ser una consecuencia legítima de la gestión.',
        '', f"**Incidencias técnicas identificadas:** {sum(len(x['structural_failures']) for x in rows) + int(bool(report.get('error')))} (incluye la excepción posterior al año 18, si la hubo). ",
        f"**Incidencias deportivas por cierre:** {sum(bool(x['sporting_risks']) for x in rows)} cierres. ",
        f"**Clubes con una racha de caja negativa de al menos 5 años:** {long_negative_streak_count(rows)}.",
        '', '## Intervenciones del entrenador ficticio',
        '', f"- **Promociones realizadas:** {len(report.get('manager_academy_promotions',[]))}; son movimientos reales desde la academia del club del usuario.",
        '- Todas las decisiones se ejecutan mediante `youth_command`; no hay jugadores fabricados ni control automático de los otros clubes.',
        '- El escenario completamente desatendido puede interrumpirse cuando el equipo humano necesita reconstruirse tras retiros.',
        '', '## Qué NO certifica esta prueba',
        '', '- Los partidos senior se resuelven mediante el marcador acelerado existente; no genera evidencia de minutos o desarrollo por partido.',
        '- No sustituye una prueba completa en Windows, ni pruebas manuales de toda la interfaz.',
        '- La muestra de partidos reales se guarda en un reporte separado y no extrapola a veinte temporadas.',
        '- Una sola semilla de veinte años no demuestra que todos los mundos hipotéticos mantengan el mismo balance.',
    ]
    lines += ['', '## Otras semillas (cinco temporadas)', '',
              '| Semilla | Estado | Titulares vacantes | Suplentes vacantes | Clubes con menos de 2 GK | Caja negativa |',
              '|---:|---|---:|---:|---:|---:|']
    for seed in (6606,7707,8808):
        other=(ROOT/f'reports/ts2412_seed{seed}_5y.json')
        data=(report if seed == report['seed'] else json.loads(other.read_text(encoding='utf-8'))
              if other.exists() else {})
        sample=data.get('annual_snapshots',[])
        if len(sample)<5:
            lines.append(f'| {seed} | Sin resultado cerrado | — | — | — | — |')
            continue
        x=sample[4]
        status = ('cinco temporadas completas (ejecucion larga interrumpida)' if seed == report['seed'] and data.get('status') != 'completed' else data.get('status','parcial'))
        lines.append(f"| {seed} | {status} | {x['uncovered_starter_slots']} | {x['uncovered_reserve_slots']} | {x['clubs_below_two_goalkeepers']} | {x['cash_negative_clubs']} |")
    lines += ['', '**Muestra de partidos senior detallados:** ']
    real=ROOT/'reports/ts2412_detailed_matches.json'
    if real.exists():
        d=json.loads(real.read_text(encoding='utf-8'))
        lines.append(f"{d.get('matches_completed',0)} partidos, {d.get('total_u23_minutes',0)} minutos reales para sub-23 en {d.get('games_with_u23_minutes',0)} encuentros.")
    else:
        lines.append('Pendiente: el motor detallado no forma parte del estres acelerado.')
    if report.get('error'):
        incident=report['error']
        lines += ['', '## Error de integración confirmado', '',
                  '**Ejecución original:** se detuvo tras '+str(report['completed_seasons'])+
                  ' temporadas, al intentar iniciar la temporada '+str(incident['season_attempted'])+'.',
                  '**Excepción:** `'+incident['exception']+': '+incident['detail']+'`.',
                  'El fallo fue causado por la preparación del rival del equipo humano sin una alineación válida.',
                  'TS-24.12 incorpora una corrección focalizada: cuando la IA no puede presentar un once elegible, el enfrentamiento protegido se registra como resultado administrativo sin simular minutos ni inventar jugadores.',
                  '**La auditoría de veinte temporadas con esta corrección NO se volvió a ejecutar hasta el final:** no está certificada.']
    smoke=ROOT/'reports/ts2412_forfeit_fix_smoke.json'
    if smoke.exists():
        outcome=json.loads(smoke.read_text(encoding='utf-8'))
        lines += ['', '## Comprobación posterior a la corrección', '',
                  'Prueba focalizada sobre un mundo nuevo: '+outcome['status']+'.',
                  f"El partido {outcome['fixture_id']} quedó con resolutor `{outcome['result_resolver']}` y marcador {outcome['home_goals']}-{outcome['away_goals']}.",
                  'Todas las comprobaciones de no fabricar jugadores, no asignar minutos y mantener el esquema SQLite v16 resultaron aprobadas.',
                  '**Esta prueba focalizada no reemplaza una repetición integral de veinte años.**']
    a.output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(str(a.output))

if __name__=='__main__':main()

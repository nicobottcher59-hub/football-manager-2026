"""TS-24.8: turn a measured 5/10/20-season JSON audit into a readable report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _money(value):
    return f"£{value:,.0f}"


def _pct_change(start, finish):
    return f"{(finish / start - 1) * 100:+.1f}%" if start else 'sin base'


def summarize(data: dict) -> str:
    opening = data['baseline']
    snapshots = data.get('annual_snapshots', [])
    endpoints = [opening, *(data.get('checkpoints', {}).get(str(yr)) for yr in (5, 10, 20))]
    status = data['status']
    any_fail = any(s['hard_issues'] for s in snapshots)
    lines = [
        '# TS-24.8 — Auditoría de balance a largo plazo', '',
        f"**Ejecución:** {status}. Temporadas completadas: **{data['years_completed']} de {data['years_requested']}**.",
        '',
        '**Metodología.** Se ejecuta el calendario real de competiciones inglesas generadas, los cambios de',
        'temporada y divisiones, los contratos, mercado de la IA, salarios, caja, retiros y canteras.',
        'Únicamente el resultado de los partidos de los equipos senior usa el resolvedor rápido',
        'de fondo, en vez del simulador táctico detallado. Es una **prueba acelerada del ecosistema**,',
        'no una partida completa de veinte años ni una prueba de minutos de juego.',
        '',
        '## Checkpoints', '',
        '| Métrica | Inicio | 5 años | 10 años | 20 años |',
        '|---|---:|---:|---:|---:|',
    ]
    measures = [
        ('Clubes profesionales activos', 'active_clubs', None),
        ('Jugadores en primeros equipos', 'first_team_players', None),
        ('Mínimo jugadores por plantilla', 'squad_min', None),
        ('Puestos titulares sin cubrir', 'uncovered_starter_slots', None),
        ('Puestos suplentes sin cubrir', 'uncovered_reserve_slots', None),
        ('Clubes con menos de dos arqueros', 'clubs_below_two_goalkeepers', None),
        ('Jugadores menores de 23 años', 'young_first_team_players_u23', None),
        ('Edad mediana en primer equipo', 'first_team_age_median', None),
        ('Clubes con caja negativa', 'cash_negative_clubs', None),
        ('Caja mediana por club', 'cash_median_gbp', _money),
        ('Nómina salarial semanal mediana', 'salary_weekly_median_gbp', _money),
        ('Valor de mercado mediano', 'market_value_median_gbp', _money),
        ('Transferencias completadas acumuladas', 'completed_transfers_cumulative', None),
        ('Retirados acumulados', 'retirements_cumulative', None),
        ('Agentes libres', 'free_agents', None),
        ('Préstamos vigentes', 'active_loans', None),
        ('Mayores de 45 años activos', 'first_team_players_over_45', None),
    ]
    for title, key, fmt in measures:
        values = []
        for record in endpoints:
            if record is None:
                values.append('sin ejecutar')
            elif key not in record:
                values.append('no recolectado')
            else:
                value = record[key]
                values.append(fmt(value) if fmt is not None else str(value))
        lines.append('| ' + title + ' | ' + ' | '.join(values) + ' |')
    lines += ['', '## Interpretación y alertas', '']
    if status == 'completed':
        lines.append('- **Continuidad:** se procesaron todas las temporadas solicitadas.')
    else:
        lines.append('- **Continuidad:** recorrido incompleto; no se puede certificar el horizonte pedido.')
    if any_fail:
        years = ', '.join(str(s['season_number']) for s in snapshots if s['hard_issues'])
        lines.append(f'- **Cobertura/integridad: NO APROBADA.** Hubo incidencias duras en las temporadas {years}.')
    elif snapshots:
        lines.append('- **Cobertura/integridad:** ninguna incidencia dura en las temporadas recorridas bajo este método.')
    else:
        lines.append('- **Cobertura/integridad:** pendiente de ejecución.')
    if snapshots:
        end = snapshots[-1]
        baseline_cash = opening.get('cash_median_gbp', 0)
        initial_market = opening.get('market_value_median_gbp', 0)
        if end.get('cash_median_gbp', 0) > 0 and baseline_cash > 0:
            lines.append(f"- **Caja mediana:** {_pct_change(baseline_cash, end['cash_median_gbp'])} frente al inicio; acumulación de liquidez a vigilar, no prueba automática de inflación.")
        if initial_market > 0:
            lines.append(f"- **Cotización mediana:** {_pct_change(initial_market, end['market_value_median_gbp'])} frente al inicio. La ausencia de minutos senior en esta prueba puede acelerar la pérdida de desarrollo/rendimiento; no extrapolar sin partidos reales.")
        if end.get('youth'):
            grads = end['youth'].get('promoted_cumulative')
            lines.append(f'- **Canteras:** {grads if grads is not None else "dato pendiente"} promociones registradas al primer equipo; los minutos prometidos y las oportunidades de juego no se midieron.')
        if end.get('uncovered_reserve_slots', 0):
            lines.append(f"- **Profundidad: NO EQUILIBRADA.** {end['uncovered_reserve_slots']} asignaciones de suplentes no cubiertas, aun con un once completo; requiere fichajes y promociones según la formación.")
        first_u23 = opening.get('young_first_team_players_u23', 0)
        if first_u23 and end.get('young_first_team_players_u23', 0) < first_u23 / 2:
            lines.append(f"- **Recambio insuficiente:** los sub-23 en primeros equipos pasaron de {first_u23} a {end['young_first_team_players_u23']}; las promociones acumuladas no garantizan minutos ni una pirámide de edades saludable.")
        if end.get('first_team_players_over_45', 0):
            lines.append(f"- **Veteranos retenidos:** {end['first_team_players_over_45']} futbolistas superan los 45 años en primer equipo. Una jubilación aplazada conserva cobertura, pero no soluciona el relevo deportivo.")
        if not end.get('active_loans', 0):
            lines.append('- **Préstamos:** no hay cesiones activas en el escenario de IA, porque los clubes todavía no negocian préstamos autónomamente; no demuestra funcionamiento del mercado de cesiones entre IA.')
        lines.append(f"- **Dificultad económica:** {end['cash_negative_clubs']} clubes con caja negativa y {end['clubs_payroll_over_wage_budget']} con nómina superior al presupuesto al cierre del último año; requieren examen financiero antes de recalibrar parámetros.")
    lines += ['', '## Año a año', '']
    if not snapshots:
        lines.append('No se completaron temporadas.')
    else:
        for item in snapshots:
            cash_delta = ''
            if 'clubs_cash_increased_vs_previous' in item:
                cash_delta = (f", caja subió en {item['clubs_cash_increased_vs_previous']} clubes "
                              f"y bajó en {item['clubs_cash_decreased_vs_previous']}")
            issues = '; '.join(item['hard_issues']) if item['hard_issues'] else 'sin incidentes duros'
            lines.append(f"- **{item['label']}**: {item['completed_fixtures']} resultados, "
                f"{item['uncovered_starter_slots']} huecos titulares, "
                f"{item['cash_negative_clubs']} clubes con caja negativa" + cash_delta + f"; {issues}.")
    lines += ['', '## Qué NO demuestra esta auditoría', '']
    translations = {
        'Actual fixture schedules, tournament rounds, promotions, annual youth rollover, month-end finances, contract renewals and AI markets are executed.':
            'Se ejecutan calendarios de competiciones, rondas, ascensos y descensos, cambios anuales de canteras, cierres económicos, renovaciones y mercado de la IA.',
        'The senior games use the existing background score resolver rather than FastMatchSimulator, solely inside this disposable test run.':
            'En esta prueba descartable, los partidos senior se resuelven con el marcador de fondo existente en vez del simulador de encuentros completos.',
        'Senior player appearances, minutes, injuries, fatigue, tactics and match-based development are NOT exercised; minutes opportunities cannot be established from these results.':
            'No se miden apariciones ni minutos senior, lesiones, fatiga, tácticas o desarrollo derivado de partidos: las oportunidades de minutos NO quedan certificadas.',
        'One default fictional-world seed. This is not a statistical multiple-seed calibration or proof of fully interactive 20-year play.':
            'Solo se utiliza una semilla del mundo ficticio; no es un experimento estadístico multisemilla ni prueba de veinte temporadas interactivas completas.',
        'No player save or user database is loaded or changed.':
            'No se carga ni se modifica ninguna partida guardada del usuario.',
    }
    for notice in data.get('disclaimer', []):
        lines.append('- ' + translations.get(notice, notice))
    lines += [
        '- Las métricas económicas son descriptivas. No se compararon con series históricas validadas de la industria.',
        '- No se ejecutaron varias semillas ni pruebas de rendimiento/compatibilidad nativas en Windows.',
        '- Sin apariciones senior reales, no se puede certificar que las promesas progresen como corresponde.',
    ]
    if data.get('error'):
        lines += ['', '## Bloqueo de la ejecución', '',
                  f"Temporada {data['error_season']}: {data['error']}"]
    return '\n'.join(lines) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('reports/ts248_long_horizon.json'))
    parser.add_argument('--output', type=Path, default=Path('TS_24_8_LONG_HORIZON_REPORT.md'))
    options = parser.parse_args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(summarize(json.loads(options.input.read_text(encoding='utf-8'))), encoding='utf-8')
    print(f'Informe escrito en: {options.output}')


if __name__ == '__main__':
    main()

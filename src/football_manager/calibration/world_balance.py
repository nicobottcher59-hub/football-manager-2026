"""TS-21.5: read-only longitudinal balance diagnostics for a registered world.

Metrics use attribute-based reference OVR, never temporary ACT. They do not
change any player's rating, potential, birth date or retirement status.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from statistics import mean
from typing import Iterable

from football_manager.domain.player_development import current_ability, reference_overall

BINS = ((0, 49, '<50'), (50, 59, '50-59'), (60, 69, '60-69'),
        (70, 79, '70-79'), (80, 84, '80-84'), (85, 89, '85-89'),
        (90, 94, '90-94'), (95, 100, '95-100'))


def _quantile(values: list[float], portion: float) -> float | None:
    if not values:
        return None
    data = sorted(values)
    index = portion * (len(data) - 1)
    low = int(index)
    high = min(len(data)-1, low+1)
    return round(data[low] * (1 - (index - low)) + data[high] * (index - low), 2)


def population_metrics(players: Iterable, on_date: date) -> dict:
    """Summarize *existing* active players; no imputation of missing seasons."""
    members = list(players)
    scores = [reference_overall(p) for p in members]
    abilities = [current_ability(p) for p in members]
    # Floats such as 84.2 must be grouped by integer rating to avoid gaps.
    bucket = Counter(next(name for low, high, name in BINS if low <= int(min(100, max(0, score))) <= high)
                     for score in scores)
    ages = [p.age_on(on_date) for p in members]
    return {
        'players': len(members),
        'reference_ovr_mean': round(mean(scores), 2) if scores else None,
        'reference_ovr_p10': _quantile(scores, .10),
        'reference_ovr_p50': _quantile(scores, .50),
        'reference_ovr_p90': _quantile(scores, .90),
        'current_ability_mean': round(mean(abilities), 2) if abilities else None,
        'age_mean': round(mean(ages), 2) if ages else None,
        'under_21': sum(age < 21 for age in ages),
        'over_33': sum(age >= 34 for age in ages),
        'reference_90_plus': sum(score >= 90 for score in scores),
        'reference_95_plus': sum(score >= 95 for score in scores),
        'bins': {label: bucket.get(label, 0) for _, _, label in BINS},
    }


def world_balance_snapshot(registry, on_date: date) -> dict:
    """One-pass diagnostic; tiers for reporting only, never development multipliers."""
    cohorts = defaultdict(list)
    active = []
    for club_id, club in registry.clubs.items():
        members = club.squad.players
        active.extend(members)
        identity = registry.identities.get(club_id)
        cohorts[str(identity.tier) if identity else 'unassigned'].extend(members)
    archived = registry.retired_players
    return {
        'date': on_date.isoformat(),
        'season': registry.season_label,
        'clubs': len(registry.clubs),
        'active': population_metrics(active, on_date),
        'by_tier': {key: population_metrics(cohorts[key], on_date) for key in sorted(cohorts)},
        'retired_archived': len(archived),
        'retirement_deferred': sum(p.aging is not None and p.aging.retirement_status == 'deferred'
                                   for p in active),
        'medical_active': len(registry.medical_followups),
        'academy_intake_enabled': False,
        'source': 'persistent-players-only-v1',
    }


def compare_world_snapshots(before: dict, after: dict) -> dict:
    """Report drift rather than secretly clamping players to a league average."""
    start, end = before['active'], after['active']
    left, right = start['reference_ovr_mean'], end['reference_ovr_mean']
    return {
        'active_population_delta': right_players_delta(start, end),
        'reference_ovr_mean_delta': round(right-left, 2) if left is not None and right is not None else None,
        'elite_90_plus_delta': end['reference_90_plus'] - start['reference_90_plus'],
        'deferred_retirement_delta': after['retirement_deferred'] - before['retirement_deferred'],
        'notes': [
            'No player ability or potential is modified by this report.',
            'A nonzero population deficit cannot be corrected without youth intake/Newgens.',
            'Retirement safeguards can postpone departures without creating youth replacements.',
        ],
    }


def right_players_delta(start: dict, end: dict) -> int:
    return end['players'] - start['players']


def balance_warnings(baseline: dict, latest: dict) -> tuple[str, ...]:
    """Conservative diagnostics only, with explicit missing-intake semantics.

    Thresholds are initial QA alarms, not assertions of empirical realism.
    No per-player ratings, ages, club strengths or save objects are modified.
    """
    initial, now = baseline['active'], latest['active']
    warnings = []
    if not initial['players']:
        return ('Baseline population is empty: no calibration possible.',)
    population_ratio = now['players'] / initial['players']
    if population_ratio < .85:
        warnings.append('Active-player population has fallen more than 15%; Newgens/youth intake is needed.')
    if now['players'] and now['under_21'] / now['players'] < .08:
        warnings.append('Under-21 players are fewer than 8% of the active population; no youth intake is modeled.')
    if now['players'] and now['reference_90_plus'] / now['players'] > .02:
        warnings.append('Reference OVR 90+ exceeds the provisional 2% QA alert threshold.')
    if initial['reference_ovr_mean'] is not None and now['reference_ovr_mean'] is not None:
        if abs(now['reference_ovr_mean'] - initial['reference_ovr_mean']) > 3:
            warnings.append('Mean reference OVR has drifted by more than 3 points; inspect cohort survival and potential.')
    if latest['retirement_deferred'] > max(10, .05*now['players']):
        warnings.append('Deferred retirements are accumulating because youth replacements are unavailable.')
    return tuple(warnings)

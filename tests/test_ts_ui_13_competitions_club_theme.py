"""TS-UI-13: presentation contracts for the club-themed Competitions screen.

These are lightweight tests: real competition state remains owned by Python.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend' / 'portable'
JS = (FRONTEND / 'competitions.js').read_text(encoding='utf-8')
CSS = (FRONTEND / 'competitions.css').read_text(encoding='utf-8')


def test_club_identity_uses_ids_and_not_hardcoded_team_names():
    assert "index?.managed_id||data?.managed_id" in JS
    assert "FMClubIdentity?.resolve?.(managerId(),managerName())" in JS
    assert "data-fm-club-theme=" in JS
    assert "FMClubIdentity?.paintWithin?.(root)" in JS
    assert 'Sunderland' not in JS and 'Sunderland' not in CSS


def test_hero_is_restricted_to_own_competitions_and_safe_in_empty_states():
    assert "if(explorerView!=='mine')return '';" in JS
    assert '${managerHero()}${navigation}' in JS
    assert '${managerHero()}\n      ${explorerView' in JS
    assert 'window.FMClubIdentity?.paintWithin?.(root)' in JS
    assert 'No competition selected' in JS


def test_competition_brands_and_matchday_navigation_unchanged():
    assert "data-competition-brand=" in JS
    assert "data-cmp-competition=" in JS
    assert "data-cmp-round" in JS
    assert "data-cmp-step" in JS
    assert "data-cmp-zoom" in JS
    assert "data-cmp-stage" in JS
    assert 'window.FMCompetitionBranding?.resolve' in JS
    assert '--ci-accent:' not in CSS.split('/* TS-UI-13')[1]


def test_club_background_is_generic_and_responsive():
    assert "url('assets/competitions/competition-centre-hero.webp')" in CSS
    assert (FRONTEND / 'assets' / 'competitions' / 'competition-centre-hero.webp').is_file()
    assert '@media(max-width:560px)' in CSS
    assert '.cmp-manager-hero' in CSS
    assert '.cmp-fixture-row.cmp-highlight' in CSS

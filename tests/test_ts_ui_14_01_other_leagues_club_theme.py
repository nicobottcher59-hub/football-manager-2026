"""TS-UI-14.01: club shell accents, distinct from the selected league brand."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CSS = (PROJECT/'frontend/portable/competitions.css').read_text(encoding='utf-8')


def test_manager_club_colours_are_not_hardcoded_to_sunderland():
    assert '--cmp-shell-rgb:var(--ui-club-rgb' in CSS
    assert '--cmp-shell-accent:var(--ui-club-highlight' in CSS
    assert '.cmp-root.cmp-other-leagues .cmp-other-hero::after' in CSS
    assert '.cmp-root.cmp-other-leagues .cmp-other-hero-eyebrow' in CSS
    assert '.cmp-root.cmp-other-leagues[data-competition-brand] .cmp-directory' in CSS
    assert 'body:has(.fm-competitions-screen[style*="display: block"] .cmp-other-hero) .sidebar .nav-item.is-active' in CSS


def test_selected_competition_keeps_its_own_identity():
    assert '--ci-' in CSS
    assert '.cmp-root.cmp-other-leagues .cmp-title-emblem' not in CSS.split('/* TS-UI-14.01')[1]
    assert '.cmp-root.cmp-other-leagues .cmp-table' not in CSS.split('/* TS-UI-14.01')[1]
    assert '.cmp-manager-hero' not in CSS.split('/* TS-UI-14.01')[1]

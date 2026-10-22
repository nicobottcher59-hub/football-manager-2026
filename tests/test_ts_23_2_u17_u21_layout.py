"""TS-23.2.1: youth layout contracts. No browser or Node required."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/portable/youth_academy.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/portable/youth_academy.css").read_text(encoding="utf-8")


def test_u17_u21_have_a_compact_readonly_formation_above_the_management_table():
    assert 'function formationBoard(level, players)' in JS
    assert 'ya-formation-pitch" role="group"' in JS
    assert 'formationBoard(level,players)' in JS
    assert 'Visual 4-3-3 preview' in JS
    assert 'data-youth-action="move"' in JS
    assert 'data-youth-action="release"' in JS
    assert 'ya-roster-stack' in JS


def test_pitch_uses_fixed_size_player_cards_and_no_stretchy_old_cards():
    assert '.ya-formation-row-keeper{top:85%;justify-content:center}' in CSS
    assert '.ya-formation-chip{flex:0 0 126px;' in CSS
    assert '.ya-formation-vacant' in CSS
    assert 'ya-lineup-card' not in JS
    assert '.ya-lineup-card' not in CSS
    assert 'ya-board-bench-chip' not in JS


def test_roster_reuses_existing_portraits_without_extra_assets():
    assert 'window.FMPortraits?.portrait?.(p,' in JS
    assert 'ya-roster-portrait' in JS
    assert '.ya-roster-portrait>.fm-face' in CSS
    assert 'ya-chip-rating' in JS


def test_u15_intake_and_youth_scouting_are_preserved():
    assert 'function field()' in JS
    assert 'ya-u15-card' in JS
    assert 'function scouting()' in JS
    assert 'data-youth-action="sign"' in JS
    assert 'data-youth-action="watch"' not in JS
    assert 'candidateFilter' in JS

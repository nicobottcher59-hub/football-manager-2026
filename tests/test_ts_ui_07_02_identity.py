"""TS-UI-07.02: stable youth competition IDs vs presentation identity."""
from pathlib import Path

import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.youth_academy import youth_read_model


@pytest.fixture(scope='module')
def session():
    return DevelopmentSession()


def test_table_rows_keep_stable_real_club_ids(session):
    model = youth_read_model(session)
    registry = session._world_squads
    assert model['club_id'] == session.home_club.id
    for level in ('u17', 'u21'):
        table = model['standings'][level]
        assert len(table) == 20
        ours = [row for row in table if row['club_id'] == model['club_id']]
        assert len(ours) == 1
        assert ours[0]['club'] == registry.clubs[model['club_id']].name
        assert model['club_id'] in registry.youth.academies


def test_next_match_opponent_ids_match_the_live_fixture_record(session):
    model = youth_read_model(session)
    registry = session._world_squads
    cid = model['club_id']
    for level in ('u17', 'u21'):
        rows = model['fixtures'][level]
        assert rows
        for entry in rows:
            assert entry['opponent_club_id'] in registry.clubs
            assert entry['opponent_club_id'] != cid
            assert entry['opponent'] == registry.clubs[entry['opponent_club_id']].name
            actual = [f for f in registry.youth.fixtures.values()
                      if f.level == level and f.match_date.isoformat() == entry['date']
                      and cid in (f.home_club_id, f.away_club_id)]
            assert any(f.away_club_id == entry['opponent_club_id'] if f.home_club_id == cid
                       else f.home_club_id == entry['opponent_club_id'] for f in actual)


def test_frontend_resolves_standings_through_club_catalogue_not_literal_names():
    root = Path(__file__).resolve().parents[1]
    js = (root/'frontend/portable/youth_academy.js').read_text()
    css = (root/'frontend/portable/youth_academy.css').read_text()
    assert 'window.FMClubIdentity?.resolve?.(id,name)' in js
    assert 'clubDisplayName(row.club_id,row.club)' in js
    assert 'clubEmblem(row.club_id,row.club)' in js
    assert 'clubDisplayName(g.opponent_club_id,g.opponent)' in js
    assert 'Northbridge FC' not in js
    assert 'Sunderland AFC' not in js
    assert '.ya-standing.is-own' in css


def test_roster_labels_and_actions_reuse_real_age_and_minutes():
    root = Path(__file__).resolve().parents[1]
    js = (root/'frontend/portable/youth_academy.js').read_text()
    css = (root/'frontend/portable/youth_academy.css').read_text()
    assert 'const minutes=Math.max(0,Math.round(Number(p.minutes)||0));' in js
    assert "level==='u21'&&Number(p.age)>17" in js
    assert 'data-youth-action="move"' in js
    assert 'ya-btn-academy' in js and 'ya-btn-first' in js and 'ya-btn-release' in js
    assert 'ya-btn-first:hover' in css and 'ya-btn-academy:hover' in css

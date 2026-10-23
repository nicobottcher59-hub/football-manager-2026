"""TS-UI-08.04 — Stable, report-aware ranges and ID-keyed scouting identity."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.professional_scouting import (
    advance_professional_scouting, scouting_command, scouting_hub_read_model,
)
from football_manager.services.transfer_negotiation import transfer_read_model

UI = Path(__file__).parents[1] / 'frontend' / 'portable'


@pytest.fixture(scope='module')
def session():
    return DevelopmentSession()


def _by_id(data, pid):
    return next(p for p in data['players'] if p['id'] == pid)


def test_unscouted_attributes_are_ranges_without_overall_value_or_potential(session):
    model = scouting_hub_read_model(session)
    assert len(model['players']) > 100
    for item in model['players']:
        if item['public_profile']:
            # Preserve existing exception for internationally known 85+ talent.
            assert 'attribute_estimates' not in item
            continue
        assert 'report' not in item
        attrs = item['attribute_estimates']
        assert len(attrs) >= 35
        assert {'technical', 'mental', 'physical'} <= {a['group'] for a in attrs}
        assert all(set(a) == {'group', 'name', 'range'} for a in attrs)
        assert all(len(a['range']) == 2 and 1 <= a['range'][0] < a['range'][1] <= 100 for a in attrs)
        assert 'ovr' not in item and 'value_gbp' not in item and 'potential' not in item
        assert 'overall_rating' not in item and 'true_value' not in item
        assert item.get('public_profile') is None
    # Prices and ratings remain hidden throughout the related Transfer screen.
    unknown = next(p for p in model['players'] if not p['public_profile'])
    transfer = next(x for x in transfer_read_model(session)['targets'] if x['id'] == unknown['id'])
    assert transfer['ovr'] is None and transfer['value_gbp'] is None


def test_stable_indications_change_only_with_real_scouting_progress(session):
    original = scouting_hub_read_model(session)
    other = scouting_hub_read_model(session)
    assert original == other
    pid = next(p['id'] for p in original['players'] if not p['public_profile'])
    first = _by_id(original, pid)['attribute_estimates']
    world = session._world_squads
    player = next(p for c in world.clubs.values() for p in c.squad.players if p.id == pid)
    for item in first:
        raw = getattr(getattr(player.attributes, item['group']),
                      item['name'].lower().replace(' ', '_'))
        assert item['range'][0] <= raw <= item['range'][1]
    career = deepcopy(session)
    scouting_command(career, {'action': 'assign', 'player_id': pid})
    for _ in range(4):
        career.current_date += timedelta(days=1)
        advance_professional_scouting(career, career.current_date)
    partial = _by_id(scouting_hub_read_model(career), pid)
    assert partial['scouting']['progress'] > 0
    assert partial['attribute_estimates']
    assert all(b['range'][1]-b['range'][0] <= a['range'][1]-a['range'][0]
               for a,b in zip(first, partial['attribute_estimates']))
    for _ in range(20):
        career.current_date += timedelta(days=1)
        advance_professional_scouting(career, career.current_date)
    completed = _by_id(scouting_hub_read_model(career), pid)
    assert completed['report'] and 'attribute_estimates' not in completed
    final = completed['report']['attributes']
    assert all(b['range'][1]-b['range'][0] <= a['range'][1]-a['range'][0]
               for a,b in zip(first, final))
    assert all('value' not in a for a in final)
    assert completed['report']['value_range_gbp'] and completed['report']['overall_range']


def test_visual_assets_are_scalable_and_match_ui_08_03(session):
    source = (UI / 'scouting_hub.js').read_text(encoding='utf-8')
    colors = (UI / 'club_identity.js').read_text(encoding='utf-8')
    css = (UI / 'scouting_hub.css').read_text(encoding='utf-8')
    page = (UI / 'index.html').read_text(encoding='utf-8')
    assert 'clubMark(p.club_id)' in source
    assert 'clubMark(p.club_id,p.club,true)' in source
    assert 'data-fm-club-theme="${esc(selectedPlayer().club_id)}"' in source
    assert 'FMNationFlags?.render?.(n' in source
    assert '<script src="nation_flags.js" defer></script>' in page
    assert page.index('nation_flags.js') < page.index('scouting_hub.js')
    assert "'⚽'" not in source.split('const clubMark')[1].split('const flag')[0]
    assert 'selectColour(item.crest)' in colors
    assert 'fallbackColour' in colors
    assert 'var(--player-club-rgb' in css
    assert 'sc-attribute-preview' in css
    for name in ('england','scotland','wales'):
        assert (UI / 'assets' / 'flags' / f'{name}.svg').is_file()
    assert "_attribute_indications" in (
        Path(__file__).parents[1] / 'src' / 'football_manager' / 'services' / 'professional_scouting.py'
    ).read_text()

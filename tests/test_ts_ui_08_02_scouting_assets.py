"""Scouting 08.02 & universal ID asset overlay safety/compatibility."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.professional_scouting import scouting_hub_read_model


@pytest.fixture(scope='module')
def seed():
    return DevelopmentSession()


def test_public_salaries_are_contract_backed_and_elite_is_public(seed):
    model = scouting_hub_read_model(seed)
    records = {p['id']: p for p in model['players']}
    players = {p.id: p for c in seed._world_squads.clubs.values() for p in c.squad.players}
    assert len(records) > 100
    elites = 0
    for pid, p in records.items():
        con = seed._world_squads.contracts[pid]
        assert p['weekly_wage_gbp'] == con.weekly_wage_gbp
        assert p['contract_until'] == con.expires_on.isoformat()
        assert 'overall_rating' not in p and 'potential' not in p
        profile = p['public_profile']
        if players[pid].overall_rating >= 85:
            elites += 1
            assert profile is not None
            assert profile['overall'] == round(players[pid].overall_rating, 1)
            assert profile['market_value_gbp'] > 0
            assert profile['attributes']
            assert profile['potential_range'][0] >= 85
        else:
            assert profile is None
            assert 'market_value_gbp' not in p
            assert 'overall' not in p
            assert 'attributes' not in p
    assert elites > 0
    assert model == scouting_hub_read_model(seed)


def test_elite_public_knowledge_does_not_create_report(seed):
    model = scouting_hub_read_model(deepcopy(seed))
    elite = next(p for p in model['players'] if p['public_profile'])
    assert 'report' not in elite
    assert 'scouting' not in elite
    assert all(1 <= attr['value'] <= 100 for attr in elite['public_profile']['attributes'])
    assert elite['public_profile']['potential_range'][1] <= 100


def test_manifest_import_uses_ids_validates_paths(tmp_path):
    import importlib.util
    source = Path(__file__).parents[1] / 'tools/import_entity_assets.py'
    spec = importlib.util.spec_from_file_location('entity_asset_import', source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.valid_id('northbridge')
    assert not module.valid_id('../northbridge')
    assert not module.valid_id('__proto__')
    input_dir = tmp_path / 'input'
    (input_dir/'players').mkdir(parents=True)
    (input_dir/'clubs/club-a').mkdir(parents=True)
    (input_dir/'competitions').mkdir(parents=True)
    # Tiny valid PNG fixture; the importer checks image validity.
    from PIL import Image
    Image.new('RGB',(12,12),(30,120,160)).save(input_dir/'players/player-17.png')
    Image.new('RGBA',(12,12),(30,120,160,255)).save(input_dir/'clubs/club-a/crest.png')
    Image.new('RGB',(12,12),(30,120,160)).save(input_dir/'competitions/league-01.png')
    metadata = tmp_path / 'metadata.json'
    metadata.write_text(json.dumps({'clubs':{'club-a':{'display_name':'A long club name',
                         'primary_color':'#123456'}}}),encoding='utf8')
    destination = tmp_path/'out'
    output = module.import_assets(input_dir, destination, metadata)
    assert output['clubs']['club-a']['display_name'] == 'A long club name'
    assert output['players']['player-17']['photo'].startswith('assets/imported/players/')
    assert (destination/'data/entity-assets.json').exists()
    assert (destination/output['clubs']['club-a']['crest']).exists()
    assert output['competitions']['league-01']['logo'].endswith('.png')


def test_template_json_schema_and_client_wiring():
    root = Path(__file__).resolve().parents[1]
    frontend = root/'frontend/portable'
    manifest = json.loads((frontend/'data/entity-assets.json').read_text())
    assert manifest['schema_version'] == 1
    assert set(('clubs','players','competitions')).issubset(manifest)
    for source in ('index.html','match.html'):
        assert 'assets_registry.js' in (frontend/source).read_text()
    assert '/portable/assets_registry.js' in (root/'frontend/public/squad/embed.html').read_text()
    assert 'Northbridge FC' not in (frontend/'match.js').read_text()
    assert 'md-sunderland' not in (frontend/'club_support.js').read_text()
    assert 'FMEntityAssets' in (frontend/'club_identity.js').read_text()

"""TS-UI-14: world directory branding/asset importer presentation contracts."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
FRONT = BASE / 'frontend/portable'


def test_other_leagues_header_and_no_automatic_world_squad_archive():
    js = (FRONT / 'competitions.js').read_text(encoding='utf8')
    css = (FRONT / 'competitions.css').read_text(encoding='utf8')
    assert 'function otherHero()' in js
    assert "if(explorerView!=='other')return '';" in js
    assert 'cmp-other-hero' in js and '.cmp-other-hero' in css
    assert "explorerView==='mine' && data?.kind==='league' && window.FMWorldSquads" in js
    assert "explorerView==='mine'?clubTabs():otherHero()+directoryBrowser()" in js
    assert "${managerHero()}${otherHero()}${explorerView==='mine'?clubTabs():directoryBrowser()}" in js
    assert 'data-cmp-competition-select' in js and 'data-cmp-filter' in js
    assert "url('assets/competitions/competition-centre-hero.webp')" in css
    assert (FRONT / 'assets/competitions/competition-centre-hero.webp').is_file()


def test_all_six_existing_world_competitions_have_distinct_palettes():
    js = (FRONT / 'competition_branding.js').read_text(encoding='utf8')
    ids = ('dev-championship', 'dev-league-one', 'dev-league-two',
           'efl-trophy', 'europa-league', 'conference-league')
    for cid in ids:
        assert f"'{cid}':{{" in js
    assert "window.FMEntityAssets?.getCompetitionTheme?.(id)" in js
    assert 'validHex(importedTheme?.primary_color)' in js
    assert 'glow:rgb(accent)' in js
    css = (FRONT / 'competition_branding.css').read_text(encoding='utf8')
    assert '.cmp-root.cmp-other-leagues .cmp-title-emblem img.ci-title-logo' in css
    assert 'object-fit:contain' in css
    assert 'ci-full-logo' in (FRONT/'competitions.js').read_text(encoding='utf8')


def test_id_importer_accepts_future_league_png_and_safe_palette(tmp_path):
    script = BASE/'tools/import_entity_assets.py'
    spec = importlib.util.spec_from_file_location('ui14_assets', script)
    assert spec and spec.loader
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    source = tmp_path/'source'
    (source/'competitions').mkdir(parents=True)
    Image.new('RGBA', (440, 100), (20, 80, 100, 255)).save(source/'competitions/league-test.png')
    metadata = tmp_path/'metadata.json'
    metadata.write_text(json.dumps({'competitions': {
        'league-test': {'primary_color': '#AABBCC', 'secondary_color': '#112233'},
        'league-without-logo': {'primary_color': '#DDEEFF'},
    }}), encoding='utf8')
    dest=tmp_path/'output'
    result=loader.import_assets(source,dest,metadata)
    assert result['competitions']['league-test']['logo'].endswith('league-test.png')
    assert result['competitions']['league-test']['primary_color']=='#aabbcc'
    assert result['competitions']['league-test']['secondary_color']=='#112233'
    assert result['competitions']['league-without-logo']['primary_color']=='#ddeeff'
    assert (dest/result['competitions']['league-test']['logo']).is_file()
    assert json.loads((dest/'data/entity-assets.json').read_text())['competitions']==result['competitions']
    assert 'getCompetitionTheme' in (FRONT/'assets_registry.js').read_text(encoding='utf8')


def test_unsafe_competition_metadata_rejected(tmp_path):
    script=BASE/'tools/import_entity_assets.py'
    spec=importlib.util.spec_from_file_location('ui14_importer_invalid',script)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    input_dir=tmp_path/'source'
    input_dir.mkdir()
    metadata=tmp_path/'bad.json'
    metadata.write_text(json.dumps({'competitions':{'../bad':{'primary_color':'#FF0000'}}}),encoding='utf8')
    import pytest
    with pytest.raises(ValueError,match='competition identity'):
        module.import_assets(input_dir,tmp_path/'target',metadata)

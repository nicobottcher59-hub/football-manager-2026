"""TS-UI-10.01: country-aware honour categories and transparent supplied trophy art.

The module never changes a save: honours come from confirmed career reports and
optional historical imports by immutable club ID.
"""
import json
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'frontend' / 'portable'


def _catalogue():
    return json.loads((ROOT / 'data' / 'honour-competitions.json').read_text('utf-8'))


def test_catalogue_is_extendable_by_country_and_region():
    data = _catalogue()
    assert data['schema_version'] == 1
    assert 'england' in data['countries']
    assert data['regions']['uefa']['countries']
    assert data['global_categories']


def test_every_declared_trophy_png_is_real_transparent_asset():
    data = _catalogue()
    entries = data['countries']['england']['categories'] + data['regions']['uefa']['categories'] + data['global_categories']
    files = {x['image'] for x in entries if x.get('image')}
    assert len(files) == 8
    for name in files:
        path = ROOT / 'assets' / 'trophies' / name
        raw = path.read_bytes()
        assert raw[:8] == b'\x89PNG\r\n\x1a\n'
        width, height, bitdepth, colourtype = struct.unpack('>IIBB', raw[16:26])
        assert 0 < width <= 360 and 0 < height <= 360
        assert bitdepth == 8 and colourtype == 6  # RGBA, not checkerboard-only RGB


def test_world_titles_include_legacy_and_modern_competitions():
    ids = set(next(row for row in _catalogue()['global_categories'] if row['id'] == 'club-world-titles')['competition_ids'])
    assert {'fifa-club-world-cup-expanded', 'intercontinental-cup', 'mundialito'} <= ids


def test_lower_division_trophies_are_explicit_subsets_not_an_extra_league_win():
    cat = _catalogue()['countries']['england']['categories']
    groups = {x['id']: x for x in cat}
    assert groups['eng-lower']['subset_of'] == 'eng-leagues-all'
    assert set(groups['eng-lower']['competition_ids']) < set(groups['eng-leagues-all']['competition_ids'])


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js unavailable')
def test_javascript_counts_career_history_and_foreign_clubs():
    result = subprocess.run(['node', str(Path(__file__).with_suffix('.js'))], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS' in result.stdout

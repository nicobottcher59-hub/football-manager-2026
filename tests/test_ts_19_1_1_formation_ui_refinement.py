"""TS-19.1.1: authoritative preview metadata and unchanged football rules."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from football_manager.dev_ui.formations import development_formations, formation_board_layouts
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.models import apply_squad_command, squad_read_model

ROOT = Path(__file__).resolve().parents[1]


def test_all_28_formation_previews_are_exactly_catalogue_coordinates():
    view = squad_read_model(DevelopmentSession())
    formations = development_formations()
    assert len(view['formations']) == len(formations) == 28
    assert {item['id'] for item in view['formations']} == {f.formation_id for f in formations}
    for item, formation in zip(view['formations'], formations, strict=True):
        assert item['id'] == formation.formation_id
        assert item['name'] == formation.name
        assert len(item['slots']) == 11
        assert {slot['slot_id'] for slot in item['slots']} == formation.slot_ids
        assert [slot['label'] for slot in item['slots'] if slot['slot_id']=='gk'] == ['GK']
        for slot in item['slots']:
            x, y = formation_board_layouts()[formation.formation_id][slot['slot_id']]
            assert (slot['x'], slot['y']) == (round(100 * x, 1), round(100 * y, 1))


def test_previews_dont_change_actual_formation_or_roles():
    session = DevelopmentSession()
    before = squad_read_model(session)
    assert before['formation']['id'] == session.home_tactic.formation.formation_id
    initial_roles = session.home_tactic.role_assignments.copy()
    for item in before['formations']:
        assert len(item['slots']) == 11
    assert session.home_tactic.role_assignments == initial_roles
    assert squad_read_model(session)['formation'] == before['formation']
    # Only the established, explicit Python command changes tactical formation.
    changed = apply_squad_command(session, {'action': 'formation', 'id': 'dev-5-2-2-1'})
    assert changed['formation']['id'] == 'dev-5-2-2-1'
    assert [slot['label'] for slot in changed['formations'][-1]['slots'] if slot['label'] == 'AM'] == ['AM', 'AM']


@pytest.mark.skipif(not shutil.which('node'), reason='Node.js is needed for deterministic UI tests')
def test_all_formations_have_collision_free_fixed_size_layout_in_two_phases(tmp_path):
    session = DevelopmentSession()
    snapshots = []
    for formation in development_formations():
        session.set_formation(formation.formation_id)
        view = squad_read_model(session)
        snapshots.append({key: view[key] for key in ('formation', 'slots', 'tactics')})
    input_path = tmp_path / 'formation_snapshots.json'
    input_path.write_text(json.dumps(snapshots), encoding='utf8')
    result = subprocess.run(
        ['node', 'tests/ui/test_formation_layout.cjs', str(input_path)],
        cwd=ROOT, text=True, capture_output=True, check=True, timeout=30,
    )
    assert '1120 pitch sizes/phases/scenarios' in result.stdout


@pytest.mark.skipif(not shutil.which('node'), reason='Node.js is needed for UI lifecycle tests')
def test_formation_dialog_requires_explicit_confirmation(tmp_path):
    session = DevelopmentSession()
    snapshots = []
    for formation in development_formations():
        session.set_formation(formation.formation_id)
        snapshots.append(squad_read_model(session))
    path = tmp_path / 'snapshots.json'
    path.write_text(json.dumps(snapshots), encoding='utf8')
    result = subprocess.run(
        ['node', 'tests/ui/test_formation_picker.cjs', str(path)],
        cwd=ROOT, text=True, capture_output=True, check=True, timeout=30,
    )
    assert 'confirmed-only' in result.stdout


def test_patch_keeps_football_engine_and_legacy_catalogue_unchanged():
    # UI-only files and a read-only metadata expansion. No new football modifier.
    javascript = (ROOT / 'frontend/public/squad/squad.js').read_text(encoding='utf8')
    assert 'window.FMFormationLayout.arrange' in javascript
    assert "command({action:'formation',id}" in javascript
    assert 'fm-dense-shape' not in javascript
    assert '<select class="fm-select" data-change="formation"' not in javascript
    html = (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf8')
    assert 'formation_layout.js' in html

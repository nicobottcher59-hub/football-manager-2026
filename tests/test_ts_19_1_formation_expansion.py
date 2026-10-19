"""TS-19.1: catalogue, live tactical frontend, match and save compatibility."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import shutil
import subprocess
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from football_manager.dev_ui.formations import (
    development_formations, formation_board_layouts,
)
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.tactical_presets import TacticalPreset
from football_manager.domain.tactics import Tactic
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.ui_shell.models import apply_squad_command, squad_read_model
from football_manager.ui_shell.server import create_server

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LEGACY_IDS = ('dev-4-3-3', 'dev-4-2-3-1', 'dev-4-4-2', 'dev-3-4-2-1')
USER_REQUESTED = (
    'dev-4-3-3-double-dm', 'dev-4-4-2-double-dm',
    'dev-4-2-4', 'dev-4-5-1-am-duo', 'dev-5-2-2-1',
)


def test_catalogue_has_28_unique_compatible_shapes_without_changing_legacy_ids():
    formations = development_formations()
    assert len(formations) == 28
    assert tuple(f.formation_id for f in formations[:4]) == EXPECTED_LEGACY_IDS
    assert len({f.formation_id for f in formations}) == len(formations)
    assert len({f.name for f in formations}) == len(formations)
    assert set(USER_REQUESTED) <= {f.formation_id for f in formations}
    for formation in formations:
        assert len(formation.slots) == 11
        assert len({slot.slot_id for slot in formation.slots}) == 11
        assert Counter(slot.position for slot in formation.slots)[Position.GK] == 1
        tactic = Tactic.from_preset('test', 'test', formation, TacticalPreset.BALANCED)
        assert set(tactic.role_assignments) == formation.slot_ids
        assert all(tactic.role_for_slot(slot.slot_id).supports(slot.position)
                   for slot in formation.slots)
        coordinates = formation_board_layouts()[formation.formation_id]
        assert set(coordinates) == formation.slot_ids
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in coordinates.values())
        assert len(set(coordinates.values())) == 11, formation.formation_id


def test_original_four_slot_assignments_are_unchanged():
    formations = development_formations()[:4]
    expected = (
        ('gk', 'rb', 'rcb', 'lcb', 'lb', 'dm', 'rcm', 'lcm', 'rw', 'st', 'lw'),
        ('gk', 'rb', 'rcb', 'lcb', 'lb', 'rdm', 'ldm', 'rw', 'am', 'lw', 'st'),
        ('gk', 'rb', 'rcb', 'lcb', 'lb', 'rw', 'rcm', 'lcm', 'lw', 'rst', 'lst'),
        ('gk', 'rcb', 'cb', 'lcb', 'rwb', 'rcm', 'lcm', 'lwb', 'ram', 'lam', 'st'),
    )
    for formation, slots in zip(formations, expected, strict=True):
        assert tuple(slot.slot_id for slot in formation.slots) == slots


def test_each_formation_updates_live_model_and_simulates_without_new_match_rules():
    session = DevelopmentSession()
    originals = {player.id for player in session.home_lineup.starting_players}
    original_away = session.away_lineup.formation.formation_id
    original_instructions = session.home_tactic.team_instructions
    simulator = FastMatchSimulator()
    for formation in development_formations():
        view = apply_squad_command(session, {'action': 'formation', 'id': formation.formation_id})
        assert view['formation'] == {'id': formation.formation_id, 'name': formation.name}
        assert len(view['formations']) == 28
        assert {p['id'] for p in view['starters']} == originals
        assert session.away_lineup.formation.formation_id == original_away
        assert session.home_tactic.team_instructions == original_instructions
        assert {s['slot_id'] for s in view['slots']} == formation.slot_ids
        assert all(len(s['individual']) == 15 and len(s['roles']) >= 1 for s in view['slots'])
        for slot in view['slots']:
            x, y = formation_board_layouts()[formation.formation_id][slot['slot_id']]
            assert slot['base_x'] == round(100 * x, 1)
            assert slot['base_y'] == round(100 * y, 1)
        snapshot = session._build_snapshot()
        result = simulator.simulate(snapshot)
        assert len(snapshot.home_team.starters) == 11
        assert result.home_goals >= 0 and result.away_goals >= 0
    with pytest.raises(ValueError, match='unknown development formation'):
        apply_squad_command(session, {'action': 'formation', 'id': 'dev-not-a-formation'})


def test_user_requested_structures_have_exact_counts_and_midfield_labels():
    formations = {f.formation_id: f for f in development_formations()}
    double_433 = Counter(s.position for s in formations['dev-4-3-3-double-dm'].slots)
    assert double_433[Position.DM] == 2
    assert double_433[Position.CM] == 1
    assert double_433[Position.RW] == double_433[Position.LW] == 1

    double_442 = Counter(s.position for s in formations['dev-4-4-2-double-dm'].slots)
    assert double_442[Position.DM] == double_442[Position.ST] == 2

    offensive_451 = formations['dev-4-5-1-am-duo']
    positions = Counter(s.position for s in offensive_451.slots)
    assert positions[Position.CM] == 1
    assert positions[Position.AM] == 2
    assert positions[Position.RW] == positions[Position.LW] == 1
    session = DevelopmentSession()
    session.set_formation(offensive_451.formation_id)
    labels = {s['slot_id']: s['label'] for s in squad_read_model(session)['slots']}
    assert labels['rm'] == 'RM' and labels['lm'] == 'LM'
    # Engine keeps existing RW/LW roles/familiarity for deep wide midfield slots.
    assert offensive_451.slot('rm').position is Position.RW
    assert offensive_451.slot('lm').position is Position.LW

    narrow_5221 = formations['dev-5-2-2-1']
    assert Counter(s.position for s in narrow_5221.slots)[Position.AM] == 2
    assert Counter(s.position for s in narrow_5221.slots)[Position.RW] == 0
    assert Counter(s.position for s in narrow_5221.slots)[Position.LW] == 0
    assert {Position.RB, Position.LB} <= {s.position for s in narrow_5221.slots}
    assert not any(s.position in (Position.RWB, Position.LWB) for s in narrow_5221.slots)

    # The earlier 3-5-2 and 3-1-4-2 proposals are not duplicate midfield shapes.
    assert Counter(s.position for s in formations['dev-3-5-2'].slots)[Position.CM] == 1
    assert Counter(s.position for s in formations['dev-3-5-2'].slots)[Position.DM] == 0
    assert Counter(s.position for s in formations['dev-3-1-4-2'].slots)[Position.DM] == 1


def test_new_formation_survives_existing_career_graph_roundtrip():
    session = DevelopmentSession()
    session.set_formation('dev-5-2-2-1')
    restored = restore_manager_graph(capture_manager_graph(session))
    assert restored.home_lineup.formation == session.home_lineup.formation
    assert restored.home_tactic.formation == session.home_tactic.formation
    assert restored.home_tactic.role_assignments == session.home_tactic.role_assignments
    assert len(squad_read_model(restored)['slots']) == 11


def test_live_http_formation_switch_updates_positions_and_names():
    session = DevelopmentSession()
    server = create_server(port=0, session=session)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/squad', timeout=10) as response:
            data = json.loads(response.read())
        assert len(data['formations']) == 28
        cmd = Request(base + '/api/squad', method='POST', headers={'Content-Type': 'application/json'},
                      data=json.dumps({'action': 'formation', 'id': 'dev-5-2-2-1'}).encode())
        with urlopen(cmd, timeout=10) as response:
            data = json.loads(response.read())
        assert data['formation']['id'] == 'dev-5-2-2-1'
        assert len(data['slots']) == 11
        assert [s['position'] for s in data['slots']].count('AM') == 2
        assert data['slots'][-1]['base_y'] < data['slots'][0]['base_y']
        with urlopen(base + '/squad/board.js', timeout=10) as response:
            assert b'slot.base_x' in response.read()
        with urlopen(base + '/squad/squad.js', timeout=10) as response:
            assert b'data.formations.map' in response.read()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js not available to validate portable field rendering')
def test_portable_board_renders_all_28_shapes_in_both_phases():
    session = DevelopmentSession()
    payload = []
    for formation in development_formations():
        session.set_formation(formation.formation_id)
        payload.append(squad_read_model(session))
    js = r'''
const fs = require('node:fs');
const assert = require('node:assert/strict');
const vm=require('node:vm');
const scope={module:{exports:{}},window:{}};
vm.runInNewContext(fs.readFileSync('./frontend/public/squad/board.js','utf8'),scope);
const {place,base}=scope.module.exports;
const all = JSON.parse(fs.readFileSync(0,'utf8'));
for(const data of all){
  for(const phase of ['in_possession','out_of_possession']){
    const map=place(data,phase);
    assert.equal(Object.keys(map).length,11,data.formation.id);
    for(const slot of data.slots){
      const p=map[slot.slot_id];
      const raw=base(slot);
      assert.equal(raw[0],slot.base_x,'board must use Python x coordinate');
      assert.equal(raw[1],slot.base_y,'board must use Python y coordinate');
      assert.ok(p && Number.isFinite(p.x) && Number.isFinite(p.y),data.formation.id+' '+slot.slot_id);
      assert.ok(p.x>=5 && p.x<=95 && p.y>=5 && p.y<=95);
    }
  }
}
console.log(all.length+' formations render in both phases');
'''
    result = subprocess.run(['node', '-e', js], input=json.dumps(payload), text=True,
                            capture_output=True, cwd=ROOT, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert '28 formations render in both phases' in result.stdout

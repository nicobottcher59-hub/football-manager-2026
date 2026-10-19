"""TS-26.1: first-team scout workforce and observation progress."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club_support import ROLES
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.club_support import staff_read_model, staff_command
from football_manager.services.manager_inbox import inbox_read_model, synchronize_manager_inbox
from football_manager.services.professional_scouting import (
    scouting_read_model, scouting_command, advance_professional_scouting,
)
from football_manager.services.transfer_negotiation import transfer_read_model


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def setup(starting):
    return deepcopy(starting)


def targets(session, quantity=5):
    return [t['id'] for t in transfer_read_model(session)['targets'][:quantity]]


def advance(session, days):
    for _ in range(days):
        session.current_date += timedelta(days=1)
        advance_professional_scouting(session, session.current_date)
        synchronize_manager_inbox(session)


def test_scouts_are_real_staff_with_provisional_facilities_and_wages(starting):
    assert 'scout' in ROLES
    assert set(starting._world_squads.club_support) == set(starting._world_squads.clubs)
    for dept in starting._world_squads.club_support.values():
        assert dept.capacity['scout'] >= 1
        assert any(m.role == 'scout' for m in dept.members.values())
        dept.validate()
    staffing = staff_read_model(starting)
    assert staffing['market']['scout']
    assert sum(m['wage_weekly_gbp'] for m in staffing['members']) == staffing['weekly_payroll_gbp']
    assert scouting_read_model(starting)['scout_count'] == 1
    validate_manager_session(starting)


def test_more_scouts_increase_concurrent_player_capacity(starting):
    session = setup(starting)
    first, second, third = targets(session, 3)
    scouting_command(session, {'action': 'assign', 'player_id': first})
    with pytest.raises(ValueError, match='occupied'):
        scouting_command(session, {'action': 'assign', 'player_id': second})
    candidate = staff_read_model(session)['market']['scout'][0]
    staff_command(session, {'action': 'hire', 'member_id': candidate['id']})
    status = scouting_read_model(session)
    assert status['scout_count'] == 2 and status['capacity'] >= 2
    scouting_command(session, {'action': 'assign', 'player_id': second})
    assert len(scouting_read_model(session)['assignments']) == 2
    with pytest.raises(ValueError):
        scouting_command(session, {'action': 'assign', 'player_id': second})
    assert third not in session._world_squads.club_support[session.home_club.id].scouting_assignments


def test_high_quality_scouts_cover_more_and_finish_faster(starting):
    fast, slow = setup(starting), setup(starting)
    for session, quality in ((slow, 48), (fast, 90)):
        dept = session._world_squads.club_support[session.home_club.id]
        scout = next(m for m in dept.members.values() if m.role == 'scout')
        dept.members[scout.member_id] = replace(scout, quality=quality)
    p1, p2 = targets(slow, 2)
    scouting_command(slow, {'action': 'assign', 'player_id': p1})
    scouting_command(fast, {'action': 'assign', 'player_id': p1})
    assert scouting_read_model(fast)['capacity'] == 2
    scouting_command(fast, {'action': 'assign', 'player_id': p2})
    advance(fast, 7)
    advance(slow, 7)
    assert p1 in fast._world_squads.club_support[fast.home_club.id].scouting_reports
    assert p2 in fast._world_squads.club_support[fast.home_club.id].scouting_reports
    assert p1 in slow._world_squads.club_support[slow.home_club.id].scouting_assignments
    assert fast._world_squads.club_support[fast.home_club.id].scouting_reports[p1].overall > 0


def test_report_shows_grounded_attributes_but_does_not_hide_grl_or_offers(starting):
    session = setup(starting)
    targets_before = transfer_read_model(session)['targets']
    target = targets_before[0]
    assert 'ovr' in target and 'value_gbp' in target
    scouting_command(session, {'action': 'assign', 'player_id': target['id']})
    advance(session, 18)
    report = session._world_squads.club_support[session.home_club.id].scouting_reports[target['id']]
    assert report.player_name == target['name']
    assert report.overall == target['ovr']
    assert len(report.strengths) == 3
    assert all(isinstance(name, str) and name for name in report.strengths)
    after = transfer_read_model(session)
    assert target['id'] in {p['id'] for p in after['targets']}
    assert target['id'] in {r['player_id'] for r in after['professional_scouting']['reports']}
    assert 'available_transfer_budget_gbp' in after
    inbox = inbox_read_model(session)
    notices = [m for m in inbox['messages'] if m['source_key'].startswith('professional-scout:report:')]
    assert len(notices) == 1 and notices[0]['category'] == 'scouting'
    advance_professional_scouting(session, session.current_date)  # Never duplicate a completed report.
    assert len([m for m in inbox_read_model(session)['messages'] if m['source_key'].startswith('professional-scout:report:')]) == 1
    validate_manager_session(session)


def test_release_or_expiry_pauses_then_reassigns_without_losing_progress(starting):
    session = setup(starting)
    player_id = targets(session, 1)[0]
    scouting_command(session, {'action': 'assign', 'player_id': player_id})
    advance(session, 3)
    dept = session._world_squads.club_support[session.home_club.id]
    points = dept.scouting_assignments[player_id].progress_points
    scout_id = next(m.member_id for m in dept.members.values() if m.role == 'scout')
    staff_command(session, {'action': 'release', 'member_id': scout_id})
    advance(session, 2)
    assert dept.scouting_assignments[player_id].progress_points == points
    assert scouting_read_model(session)['assignments'][0]['days_left'] is None
    replacement = staff_read_model(session)['market']['scout'][0]['id']
    staff_command(session, {'action': 'hire', 'member_id': replacement})
    advance(session, 1)
    assert dept.scouting_assignments[player_id].progress_points > points
    assert dept.scouting_assignments[player_id].scout_id == replacement


def test_cancel_frees_slot_and_old_report_requires_refresh_cooldown(starting):
    session = setup(starting)
    p1, p2 = targets(session, 2)
    scouting_command(session, {'action': 'assign', 'player_id': p1})
    scouting_command(session, {'action': 'cancel', 'player_id': p1})
    assert scouting_read_model(session)['free_slots'] == 1
    scouting_command(session, {'action': 'assign', 'player_id': p2})
    advance(session, 18)
    with pytest.raises(ValueError, match='30 days'):
        scouting_command(session, {'action': 'assign', 'player_id': p2})
    advance(session, 30)
    scouting_command(session, {'action': 'assign', 'player_id': p2})
    assert p2 in session._world_squads.club_support[session.home_club.id].scouting_assignments


def test_pending_and_reports_survive_sqlite_style_graph_roundtrip(starting):
    session = setup(starting)
    first, second = targets(session, 2)
    scout = next(m for m in session._world_squads.club_support[session.home_club.id].members.values() if m.role=='scout')
    session._world_squads.club_support[session.home_club.id].members[scout.member_id] = replace(scout, quality=90)
    scouting_command(session, {'action':'assign','player_id':first})
    advance(session, 7)
    scouting_command(session, {'action':'assign','player_id':second})
    advance(session, 2)
    graph = capture_manager_graph(session)
    assert graph['version'] == GRAPH_VERSION == 22
    restored = restore_manager_graph(graph)
    info = scouting_read_model(restored)
    assert first in {r['player_id'] for r in info['reports']}
    assert second in {a['player_id'] for a in info['assignments']}
    validate_manager_session(restored)


def test_explicit_v18_upgrade_adds_only_scout_without_erasing_existing_staff(starting):
    session = setup(starting)
    dept = session._world_squads.club_support[session.home_club.id]
    staff_ids = {m.member_id for m in dept.members.values() if m.role != 'scout'}
    dept.training.starters = 'intense'
    graph = capture_manager_graph(session)
    graph['version'] = 18
    # Reproduce the 18-schema records: three departments, no scout and no reports.
    for node in graph['nodes']:
        if node.get('class') != 'football_manager.domain.club_support:ClubSupport':
            continue
        fields = node['fields']
        fields.pop('scouting_assignments')
        fields.pop('scouting_reports')
        cap = graph['nodes'][fields['capacity']['$ref']]
        cap['items'] = [pair for pair in cap['items'] if pair[0] != 'scout']
        members = graph['nodes'][fields['members']['$ref']]
        old_scouts = [pair for pair in members['items'] if ':scout:' in pair[0]]
        members['items'] = [pair for pair in members['items'] if ':scout:' not in pair[0]]
        for ident, ref in old_scouts:
            wage = graph['nodes'][ref['$ref']]['fields']['wage_weekly_gbp']
            fields['baseline_weekly_gbp'] -= wage
    upgraded = restore_manager_graph(graph)
    upgraded_dept = upgraded._world_squads.club_support[session.home_club.id]
    assert staff_ids <= set(upgraded_dept.members)
    assert upgraded_dept.training.starters == 'intense'
    assert upgraded_dept.capacity['scout'] >= 1
    assert len([m for m in upgraded_dept.members.values() if m.role=='scout']) == 1
    assert upgraded_dept.scouting_assignments == upgraded_dept.scouting_reports == {}
    validate_manager_session(upgraded)


def test_invalid_targets_do_not_change_career(starting):
    session = setup(starting)
    dept = session._world_squads.club_support[session.home_club.id]
    own_id = session.home_club.squad.players[0].id
    for bad in (own_id, 'ghost', 55, None):
        with pytest.raises(ValueError):
            scouting_command(session, {'action': 'assign', 'player_id': bad})
    assert dept.scouting_assignments == {}


def test_sqlite_save_and_load_persist_real_scout_reports(starting, tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career, load_manager_career, MANAGER_STATE_VERSION
    session = setup(starting)
    scout = next(m for m in session._world_squads.club_support[session.home_club.id].members.values() if m.role=='scout')
    session._world_squads.club_support[session.home_club.id].members[scout.member_id] = replace(scout, quality=90)
    pid = targets(session, 1)[0]
    scouting_command(session, {'action': 'assign', 'player_id': pid})
    advance(session, 7)
    repository = SQLiteSaveRepository(tmp_path / 'career.sqlite3')
    save_manager_career(repository, slot_id='test-career', display_name='Test career',
                        session=session, expected_revision=0)
    assert MANAGER_STATE_VERSION == 22
    restored = load_manager_career(repository, 'test-career').session
    assert pid in restored._world_squads.club_support[restored.home_club.id].scouting_reports
    assert any(m.source_key.startswith('professional-scout:report:') for m in restored.manager_inbox.messages)
    assert scouting_read_model(restored)['reports'][0]['player_id'] == pid


def test_atomic_http_command_does_not_modify_session_on_bad_player(starting):
    from football_manager.ui_shell.application import GameApplication
    from football_manager.ui_shell.runtime import UIRuntime
    from football_manager.ui_shell.match import prematch_read_model
    runtime = UIRuntime(setup(starting))
    app = GameApplication(runtime, prematch_builder=prematch_read_model)
    old = runtime.session
    pid = targets(old, 1)[0]
    result = app.command('scouting.command', {'action': 'assign', 'player_id': pid})
    assert result['assigned'] == pid
    assert runtime.session is not old
    before = capture_manager_graph(runtime.session)['version']
    with pytest.raises(ValueError):
        app.command('scouting.command', {'action': 'assign', 'player_id': 'missing-player'})
    assert len(scouting_read_model(runtime.session)['assignments']) == 1
    assert before == GRAPH_VERSION == 22


def test_real_http_get_and_post_expose_scouts_without_masking_targets(starting):
    import json
    from threading import Thread
    from urllib.request import Request, urlopen
    from football_manager.ui_shell.server import create_server
    server = create_server(port=0, session=setup(starting))
    server.timeout = 1
    port = server.server_port
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def get(path):
            with urlopen(f'http://127.0.0.1:{port}{path}', timeout=10) as r:
                return json.load(r)
        def post(path, data):
            body = json.dumps(data).encode()
            with urlopen(Request(f'http://127.0.0.1:{port}{path}', data=body,
                                 headers={'Content-Type': 'application/json'}), timeout=10) as r:
                return json.load(r)
        staff = get('/api/staff')
        assert 'scout' in staff['capacity']
        transfer = get('/api/transfers')
        pid = transfer['targets'][0]['id']
        assert isinstance(transfer['targets'][0]['ovr'], float)
        assert transfer['professional_scouting']['capacity'] >= 1
        assert post('/api/scouting', {'action': 'assign', 'player_id': pid})['assigned'] == pid
        scouting = get('/api/scouting')
        assert len(scouting['assignments']) == 1
        assert get('/api/transfers')['targets'][0]['ovr'] == transfer['targets'][0]['ovr']
    finally:
        server.shutdown()
        thread.join(timeout=4)
        server.server_close()

"""TS-17.4: long-career archive compression and v1 save compatibility."""
from copy import deepcopy

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import (
    SQLiteSaveRepository, SaveDocument, SaveSection, SaveIntegrityError,
    load_manager_career, manager_career_document,
)
from football_manager.persistence.session_codec import (
    capture_manager_graph, restore_manager_graph,
)
from tools.profile_long_career import profile


def test_completed_seasons_are_archived_without_losing_shared_current_world():
    session = DevelopmentSession()
    session.simulate_remaining_season()
    session.begin_next_season()
    graph = capture_manager_graph(session)
    assert graph['version'] == 4  # TS-20 adds explicit player/social-state migration.
    archives = [n for n in graph['nodes'] if n.get('type') == 'archived_world']
    assert len(archives) == 1
    assert len(graph['nodes']) < 50_000
    recovered = restore_manager_graph(graph)
    assert recovered._career.current is recovered._world
    assert recovered._world.to_dict() == session._world.to_dict()
    assert recovered._career.worlds[0].to_dict() == session._career.worlds[0].to_dict()


def test_corrupt_archived_season_is_rejected_without_code_execution():
    session = DevelopmentSession()
    session.simulate_remaining_season()
    session.begin_next_season()
    graph = capture_manager_graph(session)
    archive = next(n for n in graph['nodes'] if n.get('type') == 'archived_world')
    original = archive['data']
    archive['data'] = 'not-base64!'
    with pytest.raises(SaveIntegrityError, match='archived'):
        restore_manager_graph(graph)
    archive['data'] = original[:40]
    with pytest.raises(SaveIntegrityError, match='archived'):
        restore_manager_graph(graph)


def test_previous_version_manager_snapshots_still_load(tmp_path):
    session = DevelopmentSession()
    document = manager_career_document(session)
    sections = tuple(
        SaveSection(section.name, 1, {**section.payload, 'version': 1})
        if section.name == 'manager_state' else section
        for section in document.sections
    )
    legacy = SaveDocument(kind=document.kind, version=document.version,
                          sections=sections, entities=document.entities,
                          links=document.links)
    repo = SQLiteSaveRepository(tmp_path / 'old-version.sqlite3')
    repo.save('legacy', 'Old Valid Career', legacy, expected_revision=0)
    restored = load_manager_career(repo, 'legacy').session
    assert restored._world.to_dict() == session._world.to_dict()


def test_long_career_profiler_saves_and_restores_without_persistent_artifacts():
    results = profile(seasons=2, every=2)
    assert len(results) == 2
    assert results[-1]['graph_nodes'] > 0
    assert results[-1]['seconds_load'] >= 0
    assert results[-1]['sqlite_mib'] > 0

"""TS-UI-06.01: scoped Dressing Room visual regression contracts.

The existing TS-20 Python model stays authoritative: this patch is read-only
and does not alter squad hierarchy, connections, persistence or simulation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.ui_shell.dressing_room import dressing_room_read_model

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/portable/dressing_room.js"
CSS = ROOT / "frontend/portable/dressing_room.css"


@pytest.fixture(scope="module")
def model():
    return dressing_room_read_model(DevelopmentSession())


def test_read_model_still_uses_career_players_and_exact_tier_counts(model):
    assert model["source"] == "python-dressing-room"
    assert model["automated"] is True
    assert model["decisions_required"] is False
    assert len(model["members"]) == sum(t["count"] for t in model["tiers"])
    assert {m["id"] for m in model["members"]}
    assert [t["id"] for t in model["tiers"]] == ["leaders", "influential", "core", "emerging"]


def test_career_dynamics_are_not_invented_by_redesign(model):
    assert model["events"] == []
    assert all("morale" in m and "integration" in m for m in model["members"])
    player_ids = {m["id"] for m in model["members"]}
    assert all(l["a"] in player_ids and l["b"] in player_ids for l in model["links"])


def test_scoped_pyramid_contains_four_true_trapezoids():
    js, css = JS.read_text(), CSS.read_text()
    assert "model.tiers.map(pyramidTier)" in js
    for tier in ("leaders", "influential", "core", "emerging"):
        assert f".dr-tier-{tier}" in css
    assert "clip-path:polygon(" in css
    assert "model.members.filter(p => p.tier === t.id)" in js
    assert "p.id === selected" in js


def test_details_and_network_share_existing_career_player_ids():
    js = JS.read_text()
    assert "window.FMPortraits?.portrait(p" in js
    assert "data-dr-player=" in js
    assert "model.links.filter(" in js
    assert "data-career-id=" in js
    assert "FMNavigation?.navigate('Inbox'" in js
    assert "addEventListener('click'" in js
    assert "window.fetch=async" not in js
    assert "'/api/dressing-room'" in js
    assert "method:'POST'" not in js and "method: 'POST'" not in js


def test_club_header_reuses_shared_identity_without_hardcoded_team():
    js, css = JS.read_text(), CSS.read_text()
    assert 'FMClubIdentity?.resolve?.(model.club_id,model.club)' in js
    assert 'FMClubIdentity?.applyTheme?.(model.club_id,model.club)' in js
    assert "window.addEventListener('fm-identity-ready'" in js
    assert 'Dressing Room</h2>' in js
    assert 'dr-hero-kpis' in js
    assert 'assets/dressing-room/locker-room-team-talk.webp' in css
    for team in ('Sunderland', 'Brighton', 'northbridge'):
        assert team.lower() not in js.lower()
        assert team.lower() not in css.lower()


def test_graph_is_compact_and_does_not_overflow_on_mobile():
    js, css = JS.read_text(), CSS.read_text()
    assert "function centerScrollableGraph()" in js
    assert "shell.scrollLeft=" in js
    assert "addEventListener('resize',centerScrollableGraph)" in js
    assert "overflow-x:auto" in css
    assert "prefers-reduced-motion:reduce" in css

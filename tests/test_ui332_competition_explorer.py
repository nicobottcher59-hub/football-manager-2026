"""UI-3.3.2 directory metadata and existing WorldRunner competition coverage."""
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.competitions import competition_options, competition_read_model


@pytest.fixture(scope="module")
def session():
    return DevelopmentSession()


def test_club_and_other_collections_partition_registered_world(session):
    result = competition_options(session)
    my = {item["id"]: item for item in result["competitions"]}
    other = {item["id"]: item for item in result["other_competitions"]}
    assert result["schema_version"] == 2
    assert set(my) == {"dev-premier", "fa-cup", "carabao-cup", "champions-league"}
    assert set(other) == {"dev-championship", "dev-league-one", "dev-league-two",
                          "europa-league", "conference-league", "efl-trophy"}
    assert set(my).isdisjoint(other)
    assert set(my) | set(other) == set(session._world.leagues) | set(session._world.cups) | set(session._world.staged)
    assert all(item["managed"] for item in my.values())
    assert all(not item["managed"] for item in other.values())
    assert all(item["participant_type"] == "clubs" for item in [*my.values(), *other.values()])


def test_domestic_country_division_and_cups_are_classified_separately(session):
    items = {x["id"]: x for group in (competition_options(session)["competitions"],
                                    competition_options(session)["other_competitions"]) for x in group}
    for level, league in enumerate(("dev-premier", "dev-championship", "dev-league-one", "dev-league-two"), 1):
        item = items[league]
        assert (item["scope"], item["continent"], item["country"], item["division"], item["competition_type"]) == (
            "national", "Europe", "England", level, "league")
    for cup in ("fa-cup", "carabao-cup", "efl-trophy"):
        item = items[cup]
        assert (item["scope"], item["country"], item["division"], item["competition_type"]) == (
            "national", "England", None, "cup")
    for european in ("champions-league", "europa-league", "conference-league"):
        item = items[european]
        assert (item["scope"], item["continent"], item["country"], item["competition_type"]) == (
            "international", "Europe", None, "continental")


def test_fa_cup_waiting_for_entry_is_selectable_without_fake_draw(session):
    fa = next(item for item in competition_options(session)["competitions"] if item["id"] == "fa-cup")
    assert fa["managed"] and fa["competition_type"] == "cup"
    model = competition_read_model(session, fa["id"])
    assert model["managed_entry_round_id"]
    assert model["bracket_prediction_supported"] is False
    assert not any(t["managed"] for rnd in model["knockout"] for t in rnd["ties"])


@pytest.mark.parametrize("cid", ["dev-championship", "dev-league-one", "dev-league-two",
                                  "europa-league", "conference-league", "efl-trophy"])
def test_other_competitions_have_readonly_real_data(session, cid):
    model = competition_read_model(session, cid)
    assert model["source"] == "python-world-runner"
    assert model["id"] == cid and model["persistent"] is False
    assert model["rounds"]


def test_explorer_uses_filters_and_preserves_bracket_code():
    root = Path(__file__).resolve().parents[1] / "frontend" / "portable"
    js = (root / "competitions.js").read_text(encoding="utf8")
    css = (root / "competitions.css").read_text(encoding="utf8")
    html = (root / "index.html").read_text(encoding="utf8")
    shell = (root / "portable.js").read_text(encoding="utf8")
    # Separate sidebar pages: club-competition tabs remain exactly as UI-3.3.1.
    assert '<span>Competitions</span></button>' in html
    assert '<span>Other Leagues</span></button>' in html
    assert html.index('<span>Competitions</span></button>') < html.index('<span>Other Leagues</span></button>')
    assert "otherLeagues = page === 'Other Leagues'" in shell
    assert "mount(competitionPanel, otherLeagues ? 'other' : 'mine', extra.competition)" in shell
    assert 'data-cmp-competition=' in js and 'cmp-comp-selector' in js
    assert 'data-cmp-view="mine"' not in js and 'data-cmp-view="other"' not in js
    # The directory filters are ONLY on the separate Other Leagues route.
    assert "explorerView==='mine'?clubTabs():directoryBrowser()" in js
    assert 'data-cmp-competition-select' in js
    assert 'data-cmp-filter="participant"' in js and 'data-cmp-filter="scope"' in js
    assert "filterSelect('country'" in js and "filterSelect('continent'" in js
    assert "filterSelect('division'" in js and "filterSelect('type'" in js
    assert "'South America'" in js and "'Spain'" in js and "'Argentina'" in js
    assert 'cmp-bilateral-board' in js and 'drawConfirmedLinks' in js
    assert '.cmp-directory-note' in css


def test_frontend_rejects_outdated_python_api_instead_of_misclassifying_competitions():
    frontend = Path(__file__).resolve().parents[1] / 'frontend' / 'portable' / 'competitions.js'
    js = frontend.read_text(encoding='utf8')
    assert 'next.schema_version!==2' in js
    assert 'Array.isArray(next.other_competitions)' in js
    assert 'next.competitions.some(c=>c.managed!==true)' in js
    assert 'next.other_competitions.some(c=>c.managed!==false)' in js
    assert 'OUTDATED_COMPETITIONS_API' in js
    assert 'src/football_manager/ui_shell/competitions.py' in js

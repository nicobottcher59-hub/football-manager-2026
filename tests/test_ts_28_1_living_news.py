"""TS-28.1: news must only describe persisted sporting facts."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from threading import Thread
from types import SimpleNamespace
from urllib.request import urlopen
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import WorldMatchResult
from football_manager.domain.season_cycle import SeasonReport
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.manager_inbox import synchronize_manager_inbox
from football_manager.ui_shell.home_news import home_news_read_model
from football_manager.ui_shell.server import create_server


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def test_home_news_is_read_only_stable_and_grounded(starting):
    before = len(starting._world.results), len(starting._world_squads.transfer_offers), starting.current_date
    left = home_news_read_model(starting)
    right = home_news_read_model(starting)
    assert left == right
    assert left['source'] == 'career-ledgers'
    assert (len(starting._world.results), len(starting._world_squads.transfer_offers), starting.current_date) == before
    assert all(item['date'] is None or item['date'] <= starting.current_date.isoformat() for item in left['stories'])
    for item in left['stories']:
        assert item['id'].startswith(('match:', 'transfer:', 'title:', 'archive-title:'))
        assert item['title'] and item['body']
        if item['id'].startswith('match:'):
            assert item['id'].split(':',1)[1] in starting._world.results


def test_future_fixture_score_is_never_reported(starting):
    session = deepcopy(starting)
    fixture = next(f for fid, f in session._world.fixtures.items() if fid not in session._world.results
                   and f.kickoff is not None and f.kickoff.date() > session.current_date)
    session._world.results[fixture.fixture_id] = WorldMatchResult(fixture.fixture_id, 9, 0)
    news = home_news_read_model(session)
    assert not any(story['id'] == f'match:{fixture.fixture_id}' for story in news['stories'])


def test_completed_transfer_not_pending_bid_generates_headline(starting):
    session = deepcopy(starting)
    registry = session._world_squads
    sellers = list(registry.clubs)
    seller, buyer = sellers[:2]
    p = registry.clubs[seller].squad.players[0]
    event = SimpleNamespace(on_date=session.current_date)
    fake = SimpleNamespace(deal_id='news-pending', status='agreed', personal_status='completed',
        personal_events=(event,), terms=SimpleNamespace(fixed_gbp=42_000_000),
        player_id=p.id, seller_id=seller, buyer_id=buyer)
    registry.transfer_offers['news-pending'] = fake
    assert not any(x['id'] == 'transfer:news-pending' for x in home_news_read_model(session)['stories'])
    fake.status = 'completed'
    news = home_news_read_model(session)
    article = next(x for x in news['stories'] if x['id'] == 'transfer:news-pending')
    assert p.full_name in article['title']
    assert '42,000,000' in article['body']
    assert article['route'] == 'Scouting'
    fake.personal_events = (SimpleNamespace(on_date=session.current_date+timedelta(days=1)),)
    assert not any(x['id'] == 'transfer:news-pending' for x in home_news_read_model(session)['stories'])


def test_career_archive_awards_have_season_but_no_fabricated_day(starting):
    session = deepcopy(starting)
    winner = session.home_club.id
    report = SeasonReport(
        '2025/26', {'dev-premier':(winner,)}, {'dev-premier':winner},
        {},{},{},{},(), 0)
    session._career.reports.append(report)
    story = next(x for x in home_news_read_model(session)['stories'] if x['id'] == 'archive-title:2025/26:dev-premier')
    assert story['season']=='2025/26'
    assert story['date'] is None
    assert winner == story['club_id']
    synchronize_manager_inbox(session)
    news = [m for m in session.manager_inbox.messages if m.source_key == 'club-league-title:2025/26:dev-premier']
    assert len(news) == 1
    synchronize_manager_inbox(session)
    assert len([m for m in session.manager_inbox.messages if m.source_key == 'club-league-title:2025/26:dev-premier']) == 1


def test_managed_match_is_published_and_survives_save_load(starting):
    session = deepcopy(starting)
    result = session.quick_simulate()
    assert result.home_goals >= 0
    stories = home_news_read_model(session)['stories']
    fid = session._active_match.fixture.fixture_id
    assert any(item['id']==f'match:{fid}' for item in stories)
    graph = capture_manager_graph(session)
    assert graph['version'] == GRAPH_VERSION == 26  # TS-28.2 migrates the history ledger to v21.
    loaded = restore_manager_graph(graph)
    assert home_news_read_model(loaded) == home_news_read_model(session)


def test_limit_validation_and_zero_unsupported_facts(starting):
    with pytest.raises(ValueError):
        home_news_read_model(starting, 0)
    with pytest.raises(ValueError):
        home_news_read_model(starting, 100)
    assert all(item['category'] in ('result','transfer','title') for item in home_news_read_model(starting)['stories'])


def test_real_api_news_and_frontend_assets(starting):
    server = create_server(port=0, session=starting)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with urlopen(base+'/api/news', timeout=15) as response:
            payload = json.load(response)
            assert response.status == 200
        assert payload == home_news_read_model(starting)
        for asset in ('/portable/news.js','/portable/news.css','/portable/index.html'):
            with urlopen(base+asset, timeout=15) as response:
                assert response.status == 200
                body = response.read().decode('utf-8')
                assert body
                if asset.endswith('index.html'):
                    assert 'src="news.js"' in body and 'href="news.css"' in body
                    assert 'Northbridge close in on promotion glory' not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=6)

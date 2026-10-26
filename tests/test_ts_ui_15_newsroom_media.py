"""TS-UI-15 presentation regression checks, independent of match simulation."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'frontend' / 'portable'


def test_neutral_image_bank_is_local_compact_and_contains_no_named_club_assets():
    files = sorted((ROOT / 'assets' / 'news').glob('*.webp'))
    assert len(files) == 11
    for file in files:
        assert file.stat().st_size < 350_000, file
        assert 'sunderland' not in file.name.lower()
        data = file.read_bytes()
        assert data[:4] == b'RIFF' and data[8:12] == b'WEBP' 


def test_player_photos_are_keyed_by_id_and_do_not_use_stock_lookalikes():
    src = (ROOT / 'news_media.js').read_text()
    assert 'FMEntityAssets?.getPhoto?.(story.player_id)' in src
    assert 'FMEntityAssets?.safePath?.(file)' in src
    assert 'nr-media-player' in src
    assert 'player-with-photo' not in src
    assert 'Math.random' not in src
    assert '/portable/assets/news/' in src


def test_newsroom_is_a_real_route_and_separate_from_manager_inbox():
    html = (ROOT / 'index.html').read_text()
    app = (ROOT / 'portable.js').read_text()
    assert '<span>Newsroom</span>' in html
    assert html.index('news_media.js') < html.index('news.js')
    assert 'const newsroom = page === \'Newsroom\'' in app
    assert 'window.FMNews?.mount(newsroomPanel)' in app
    assert "window.FMInbox?.mount(inboxPanel" in app
    assert 'window.FMNavigation?.navigate?.(\'Newsroom\')' in (ROOT/'inbox.js').read_text()


def test_newsroom_only_consumes_verified_api_records():
    src = (ROOT / 'news.js').read_text()
    assert "fetch('/api/news'" in src
    assert "payload.source!=='career-ledgers'" in src
    assert 'verified career records' in src.lower()
    assert 'No confirmed events have been recorded yet' in src
    assert 'Math.random' not in src
    assert re.search(r'window\.FMNews=\{.*mount', src)

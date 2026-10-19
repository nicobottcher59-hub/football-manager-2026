"""TS-28.2.1: catch the malformed portable script tag and verify squad links."""
from html.parser import HTMLParser
from pathlib import Path

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.career_history import player_career_read_model, club_career_read_model

FRONTEND = Path(__file__).resolve().parents[1] / 'frontend'


class PortableScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []
        self.active = False
        self.invalid_nested = False
        self.inline_content = False

    def handle_starttag(self, tag, attrs):
        if tag != 'script':
            return
        if self.active:
            self.invalid_nested = True
        self.active = True
        self.sources.append(dict(attrs).get('src'))

    def handle_data(self, data):
        if self.active and data.strip():
            self.inline_content = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def test_portable_history_and_news_scripts_are_separate():
    document = (FRONTEND / 'portable/index.html').read_text(encoding='utf-8')
    parsed = PortableScripts()
    parsed.feed(document)
    assert not parsed.invalid_nested
    assert not parsed.inline_content
    assert not parsed.active
    i = parsed.sources.index('news.js')
    assert parsed.sources[i:i+4] == ['news.js', 'history.js', 'club_support.js', 'portable.js']
    assert document.count('<script') == len(parsed.sources)
    assert document.count('</script>') == len(parsed.sources)
    for src in parsed.sources:
        if src is None:
            continue
        path = (FRONTEND / 'portable' / src).resolve()
        assert path.is_file(), src


def test_history_links_available_from_roster_and_selected_lineup():
    roster = (FRONTEND / 'public/squad/roster.js').read_text(encoding='utf-8')
    squad = (FRONTEND / 'public/squad/squad.js').read_text(encoding='utf-8')
    router = (FRONTEND / 'portable/portable.js').read_text(encoding='utf-8')
    assert 'class="rt-history-shortcut"' in roster
    assert 'data-open-career-player="${html(p.id)}"' in roster
    assert 'data-open-career-player="${esc(player.id)}"' in squad
    assert "parent.postMessage({type:'fm-open-history',entity:'player',id}" in squad
    assert "if(event.data?.type==='fm-open-history'" in router
    assert "History module failed to load" in router
    assert "Club information unavailable" in router


def test_starting_career_provides_live_club_and_player_details():
    session = DevelopmentSession()
    club = club_career_read_model(session, session.home_club.id)
    player = player_career_read_model(session, session.home_club.squad.players[0].id)
    assert club['name'] == session.home_club.name
    assert club['seasons'] and not club['seasons'][0]['complete']
    assert player['name'] and player['status'] == 'active'
    assert player['current_club_id'] == session.home_club.id

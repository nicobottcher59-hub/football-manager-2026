"""TS-UI-02.3: presentation-only structural/interaction contracts."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
SQUAD=ROOT/'frontend/public/squad'

def read(path): return (ROOT/path).read_text(encoding='utf-8')

def test_assets_and_layer_order():
    doc=read('frontend/public/squad/embed.html')
    assert 'squad_ui023.css' in doc
    assert doc.index('squad_ui02.css')<doc.index('squad_ui023.css')
    assert doc.index('squad_ui02.js')<doc.index('squad.js')

def test_split_view_remains_data_driven():
    code=read('frontend/public/squad/squad_ui02.js')
    assert 'club-identities.json' in code
    assert 'entry.primary_color' in code
    assert 'entry.secondary_color' in code
    assert 'data.club_id' in code
    assert 'Sunderland' not in code
    assert 's2-roster-row' in code and 's2-inspector' in code
    assert 'data-s2-row' in code
    assert 's28-row-condition' in code

def test_no_competing_name_link_and_row_navigation():
    code=read('frontend/public/squad/squad_ui02.js')
    assert 's28-row-title' in code
    assert 's28-profile-link' in code
    assert 'data-open-career-player="${html(p.id)}"' in code
    assert 'data-roster-expand="${html(p.id)}"' in code
    assert 'class="s2-name-link"' not in code
    assert 'class="s2-player-name" data-open-career-player' not in code
    controller=read('frontend/public/squad/squad.js')
    assert "event.target.closest('[data-s2-row]')" in controller
    assert "event.target.closest('button,input,select,textarea,a')" in controller
    assert 'event.preventDefault()' in controller

def test_rich_header_uses_player_and_club_identity():
    code=read('frontend/public/squad/squad_ui02.js')
    for token in ('s28-dorsal-metric','s28-portrait-frame','s2-shirt-art','kit_style','kit_image','s28-crest-watermark'):
        assert token in code
    assert "p.number==null?'—':html(p.number)" in code
    assert 'safeAsset(identity.kit_image)' in code
    assert 'kitGraphic(active,view.data)' in code

def test_portraits_are_optional_and_keyed_by_player_id():
    code=read('frontend/public/squad/squad_ui02.js')
    assert 'view.images[player.id]' in code
    assert 'FMPortraits?.portrait(player' in code
    assert 'image.addEventListener(\'error\',()=>image.remove()' in code
    cat=json.loads(read('frontend/public/squad/data/player-portraits.json'))
    assert cat['schema_version']==1

def test_positions_depend_on_actual_roster_not_fake_formation():
    code=read('frontend/public/squad/squad_ui02.js')
    assert 'p.primary_position' in code
    assert 'p.secondary_positions||[]' in code
    assert 's2-pos-pitch' in code
    assert 'Positional familiarity' not in code or 'familiarities' in code

def test_four_tabs_and_real_stats_scope():
    code=read('frontend/public/squad/squad_ui02.js')
    for tab in ('Profile / Attributes','Season statistics','Status & development','Contract & actions'):
        assert tab in code
    assert 'All competitions' in code
    assert "state.competition='all'" in code
    assert 'data-s2-season' in code and 'data-s2-competition' in code
    assert 'opt.supported' in code
    assert 'stats=p.season_stats||{}' in code

def test_existing_actions_preserved_without_fake_negotiations():
    code=read('frontend/public/squad/squad_ui02.js')
    assert "action:'squad_number'" in code and "action:'transfer_status'" in code
    assert 'data-open-finances' in code
    assert 'data-s2-navigate="Dressing Room"' in code
    assert 'data-s2-navigate="Training"' in code
    assert 's2-contract-card' in code and 's2-actions-card' in code

def test_microanimations_reduced_motion_and_club_tokens():
    css=read('frontend/public/squad/squad_ui023.css')
    for item in ('@keyframes s23-content-in','@keyframes s23-radar-in','@keyframes s23-meter-in',
                 '@keyframes s23-ambient','@keyframes s23-dot-pop','@media(prefers-reduced-motion:reduce)',
                 '--s2-club-rgb','--s2-club-primary','--s2-club-accent'):
        assert item in css
    assert '#c72838' not in css

def test_club_kit_style_in_catalogue_not_special_cased():
    club=json.loads(read('frontend/portable/data/club-identities.json'))
    assert club['clubs']['northbridge']['kit_style']=='vertical_stripes'
    assert club['schema_version']==1

def test_no_engine_or_database_patch_required():
    # This version changes only independent presentation assets and navigation.
    assert (SQUAD/'squad_ui023.css').exists()
    assert not any(x in read('frontend/public/squad/squad_ui02.js') for x in ('DROP TABLE','UPDATE players SET','ALTER TABLE'))

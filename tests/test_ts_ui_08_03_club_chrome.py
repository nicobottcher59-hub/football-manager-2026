"""TS-UI-08.03 — ID-keyed visual identity regression guardrails.

The integration browser check lives in the release report. No career state is
modified by these tests; they validate production presentation wiring.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend' / 'portable'
SQUAD = ROOT / 'frontend' / 'public' / 'squad'


def source(name):
    return (UI / name).read_text(encoding='utf-8')


def test_squad_iframe_always_resolves_club_catalog_by_absolute_web_path():
    identity = source('club_identity.js')
    roster = (SQUAD / 'squad_ui02.js').read_text(encoding='utf-8')
    assert "fetch('/portable/data/club-identities.json'" in identity
    assert 'view.identities[id]' in roster
    assert 'window.FMEntityAssets?.getClub?.(id)' in roster
    assert 'data-s26-club-name' in roster
    catalog = json.loads((UI / 'data' / 'club-identities.json').read_text())
    assert catalog['clubs']['northbridge']['display_name'] == 'Sunderland AFC'
    assert (UI / catalog['clubs']['northbridge']['crest']).is_file()
    assert (UI / catalog['clubs']['northbridge']['kit_image']).is_file()


def test_scouting_and_transfers_badges_are_club_id_keyed_and_scoped():
    scout = source('scouting_hub.js')
    transfer = source('transfers.js')
    identity = source('club_identity.js')
    assert 'clubMark(p.club_id,p.club,true)' in scout
    assert 'clubMark(p.club_id)' in scout
    assert 'data-fm-club-theme="${esc(selectedPlayer().club_id)}"' in scout
    assert 'transferCrest(p.club_id,p.club)' in transfer
    assert 'transferCrest(otherId,otherName,true)' in transfer
    assert 'transferCrest(own,model.club,true)' in transfer
    assert 'const actual=' in transfer
    assert 'data-fm-club-theme="${esc(actual.club_id)}"' in transfer
    assert 'data-fm-club-theme="${esc(e.by_club_id)}"' in transfer
    assert 'window.FMClubIdentity?.paintWithin?.(host)' in scout
    assert 'window.FMClubIdentity?.paintWithin?.(host)' in transfer
    assert 'element.dataset.fmClubTheme' in identity
    assert "setScopedColour(element" in identity
    # A selected rival may never override the manager club global tokens.
    scoped_block = identity.split('function paintWithin(scope)')[1].split('function applyTheme(id,name)')[0]
    assert "root.style.setProperty('--ui-club" not in scoped_block
    assert 'selectColour(item.crest)' in scoped_block


def test_sidebar_medical_and_scouting_match_squad_palette():
    nav = source('portable.js')
    theme = source('club_theme.css')
    scout_css = source('scouting_hub.css')
    support = source('club_support.js')
    assert "classList.toggle('tsui-medical-active',page==='Medical Centre')" in nav
    assert 'body.tsui-medical-active .sidebar::before' in theme
    assert 'body.tsui-scouting-active .sidebar::before' in scout_css
    assert 'rgba(var(--ui-club-rgb),.21)' in theme
    assert 'rgba(var(--ui-club-rgb),.21)' in scout_css
    assert 'FMClubIdentity?.applyShell?.(payload.club_id,payload.club)' in support


def test_imported_assets_do_not_embed_club_names_into_styles():
    assert 'Sunderland' not in source('scouting_hub.css')
    assert 'Sunderland' not in source('transfers.css')
    assert 'Northbridge' not in source('club_identity.js')

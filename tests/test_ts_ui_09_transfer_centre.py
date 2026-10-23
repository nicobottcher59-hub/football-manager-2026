"""TS-UI-09 lightweight contracts for the Transfers Hub and its data sources."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ROOT / 'frontend' / 'portable'


def source(filename: str) -> str:
    return (PORTABLE / filename).read_text(encoding='utf-8')


def test_page_is_linked_and_the_old_redirect_is_removed():
    markup = source('index.html')
    router = source('portable.js')
    assert '<span>Transfers</span></button>' in markup
    assert 'transfer_centre.css' in markup and 'transfer_centre.js' in markup
    assert "if(page==='Transfers')page='Scouting'" not in router
    assert "transferCentrePage=page==='Transfers'" in router
    assert 'window.FMTransferCentre?.mount(transferCentrePanel)' in router
    assert "transferCentrePage ? 'Transfer Centre'" in router


def test_shortlist_moved_without_removing_scouting_updates():
    scouting = source('scouting_hub.js')
    hub = source('transfer_centre.js')
    assert "['shortlist',`Shortlist" not in scouting
    assert "sc-intelligence-panel" in scouting
    assert "data-sc-action=\"transfers\"" in scouting
    assert "action:'shortlist_add'" in scouting
    assert "action:'shortlist_remove'" in hub
    assert "'/api/scouting/hub'" in hub
    assert "p.public_profile?.market_value_gbp" in hub
    assert "'??'" in hub


def test_hub_unifies_offer_types_and_directions_with_history():
    hub = source('transfer_centre.js')
    for token in ("type:'transfer'", "type:'loan'", "'received'", "'sent'", "'transfer'", "'loan'", 'Negotiation History', 'Shortlist', 'Market Activity', 'Budget Summary', 'Transfer Window'):
        assert token in hub, token
    assert "'/api/loans'" in hub
    assert 'data-tc-loan' in hub and 'data-tc-deal' in hub
    assert 'data-tc-type' in hub and 'data-tc-open-loans' in hub


def test_generic_image_and_club_identity_are_independent():
    style = source('transfer_centre.css')
    script = source('transfer_centre.js')
    image = PORTABLE / 'assets' / 'transfers-transfer-window.jpg'
    assert image.is_file() and image.stat().st_size > 10000
    assert 'assets/transfers-transfer-window.jpg' in style
    assert 'FMClubIdentity?.resolve?' in script and 'FMEntityAssets?.url?' in script
    assert 'data-fm-club-theme' in script and '--ui-club-highlight' in style
    assert 'sunderland' not in style.lower() and 'sunderland' not in script.lower()


def test_negotiate_transfer_and_loan_share_same_entrypoint():
    router = source('portable.js')
    negotiate = source('transfers.js')
    assert "loanPage=page==='Loan Negotiation'" in router
    assert 'loanTalk:id=>' in router and 'loanPlayer:(id,owner)' in router
    assert 'data-tr-switch-loan' in negotiate and 'data-tr-switch-transfer' in negotiate
    assert "embeddedLoanView()" in negotiate and "dealMode" in negotiate


@pytest.fixture(scope='module')
def live_session():
    from football_manager.dev_ui.session import DevelopmentSession
    return DevelopmentSession()


def test_existing_backend_models_are_sufficient_without_new_save_fields(live_session):
    from football_manager.services.transfer_negotiation import transfer_read_model
    from football_manager.services.professional_scouting import scouting_hub_read_model
    from football_manager.services.loan_market import loan_read_model
    from football_manager.services.club_economy import finances_read_model
    from football_manager.persistence.session_codec import GRAPH_VERSION
    transfers = transfer_read_model(live_session)
    scout = scouting_hub_read_model(live_session)
    loans = loan_read_model(live_session)
    finances = finances_read_model(live_session)
    assert transfers['club_id'] == scout['club_id'] == loans['manager_club_id'] == finances['club_id']
    assert all(k in transfers for k in ('offers','world_transfers','window','available_transfer_budget_gbp'))
    assert all(k in scout for k in ('players','recommendations','shortlisted'))
    assert all(k in loans for k in ('negotiations','loans','incoming','outgoing'))
    assert all(k in finances for k in ('wage_budget_weekly_gbp','weekly_payroll_gbp'))
    assert GRAPH_VERSION == 31, 'Unified negotiations persist cross-mode conversations'
    assert all('ovr' not in p and 'value_gbp' not in p for p in scout['players'])

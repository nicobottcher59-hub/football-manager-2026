"""Reproducible integration exercise on temporary careers, never user save slots.

Run from the project root: python tools/validate_ts_fix_02.py --days 35
The test deliberately answers transfer interruptions, rather than bypassing
new pauses or pretending that an unattended calendar can pass decisions.
"""
from __future__ import annotations
import argparse,json,sys,tempfile,time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from football_manager.persistence.manager_career import save_manager_career,load_manager_career
from football_manager.persistence.session_codec import capture_manager_graph,GRAPH_VERSION
from football_manager.services.transfer_negotiation import negotiate,_quote,transfer_read_model
from football_manager.services.transfer_personal import agent_demand
from football_manager.services.transfer_installments import finance_summary
from football_manager.services.manager_inbox import synchronize_manager_inbox
from football_manager.ui_shell.progression import simulate_until


def run(days:int)->dict:
    started=time.perf_counter();s=DevelopmentSession();r=s._world_squads;mid=s.home_club.id
    start=s.current_date;world_start=len(s._world.results)
    # A modest signing exercises real club response, personal consent and debt
    # persistence. Private data below selects a test fixture, not UI advice.
    seller,player=next((cid,p) for cid,c in r.clubs.items() for p in c.squad.players
        if cid!=mid and p.id in r.contracts and r.contracts[p.id].kind=='professional'
        and 50<p.overall_rating<64 and p.age_on(start)>=20 and _quote(r,p).value_gbp<500000)
    value=_quote(r,player).value_gbp
    answer=negotiate(s,{'action':'submit','seller_id':seller,'player_id':player.id,
        'terms':{'fixed_gbp':max(100000,round(value*1.2)), 'installments_gbp':max(100000,round(value*.7)),
                 'installment_count':4,'installment_interval_months':6}})
    deal=r.transfer_offers[answer['deal_id']]
    if deal.status=='manager_turn':negotiate(s,{'action':'accept','deal_id':deal.deal_id})
    deal=r.transfer_offers[deal.deal_id];assert deal.status=='agreed'
    q=agent_demand(r,player,seller,mid,start);assert q['interested']
    result=negotiate(s,{'action':'personal_offer','deal_id':deal.deal_id,'terms':{
        'weekly_wage_gbp':q['weekly_wage_gbp'],'years':q['years'],'role':q['role'],'signing_bonus_gbp':0}})
    assert result['status']=='completed'
    signed=r.transfer_offers[deal.deal_id]
    assert signed.terms.installments_gbp>0
    original={p.id for p in s.home_club.squad.players}
    target=start+timedelta(days=days);stops=[];received=set();seen_results=set()
    for _ in range(200):
        batch=simulate_until(s,target,on_day=lambda day,rows:seen_results.update(x['id'] for x in rows))
        if not batch['stopped_for_decision']:break
        stops.append({'on_date':s.current_date.isoformat(),'decisions':batch['decisions']})
        for pending in batch['decisions']:
            d=r.transfer_offers[pending['deal_id']]
            if d.seller_id==mid:received.add(d.deal_id)
            assert d.status=='manager_turn','No unexplained automatic club agreement is allowed'
            negotiate(s,{'action':'reject','deal_id':d.deal_id})
        synchronize_manager_inbox(s)
    assert s.current_date==target
    # No managed sales are authorized by this integration test.
    assert not [d for d in r.transfer_offers.values() if d.seller_id==mid and d.status=='completed']
    assert original<={p.id for p in s.home_club.squad.players}
    r.validate()
    before=finance_summary(r,mid,s.current_date)
    with tempfile.TemporaryDirectory(prefix='tsfix02-validation-') as directory:
        repository=SQLiteSaveRepository(Path(directory)/'test.sqlite3')
        save_manager_career(repository,slot_id='fix02-validation',display_name='Temporary test',session=s,expected_revision=0)
        loaded=load_manager_career(repository,'fix02-validation').session
        assert loaded.current_date==s.current_date and loaded._world.results==s._world.results
        assert loaded._world_squads.transfer_offers==r.transfer_offers
        assert before==finance_summary(loaded._world_squads,mid,loaded.current_date)
        assert capture_manager_graph(loaded)['version']==GRAPH_VERSION==27
        loaded._world_squads.validate()
    return {'patch':'TS-FIX-02','from_date':start.isoformat(),'to_date':s.current_date.isoformat(),
        'calendar_days':days,'new_world_results':len(s._world.results)-world_start,
        'streamed_unique_results':len(seen_results),'decision_stops':stops,'incoming_offers_reviewed':len(received),
        'unapproved_managed_sales':0,'completed_world_deals':sum(d.status=='completed' and mid not in (d.seller_id,d.buyer_id) for d in r.transfer_offers.values()),
        'test_signing':{'deal_id':signed.deal_id,'player_id':signed.player_id,'upfront_gbp':signed.terms.fixed_gbp,
            'installments_gbp':signed.terms.installments_gbp,'count':signed.terms.installment_count,
            'interval_months':signed.terms.installment_interval_months},
        'outstanding_payable_gbp':before['outstanding_payable_gbp'],'sqlite_roundtrip':True,
        'save_version':GRAPH_VERSION,'elapsed_seconds':round(time.perf_counter()-started,2)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=35)
    parser.add_argument('--output',type=Path,default=Path('reports/ts_fix_02_calendar_validation.json'))
    args=parser.parse_args()
    if not 1<=args.days<=60:parser.error('--days must be between 1 and 60 for this bounded smoke test')
    result=run(args.days);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

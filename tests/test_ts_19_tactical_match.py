"""TS-19: causal tactical consumers, actual match plans and phase integration."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import pytest
from examples.demo_match_factory import build_demo_snapshot
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.tactical_shapes import PhaseShape, SlotPoint
from football_manager.domain.tactical_studio import PlanRule
from football_manager.domain.tactical_instructions import (
    Level, PlayerInstructionOverrides, PlayerInstructions, TacticalTarget, TargetKind,
    AfterWinBehavior, CrossType, InPossessionPosition, OutOfPossessionPosition,
)
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.fast_simulation.plans import FastTacticalChange
from football_manager.fast_simulation.randomness import FastMatchRandom
from football_manager.fast_simulation.profiles import build_fast_team_profile
from football_manager.fast_simulation import tactical_effects as effects
from football_manager.domain.tactical_geometry import phase_points, shape_summary
from football_manager.services.tactical_studio import prepared_match_plans
from football_manager.ui_shell.models import apply_squad_command
from football_manager.simulation import SpatialMatchEngine, TacticalPhase, TeamSide


def team_change(snapshot, group, field, value):
    team = snapshot.home_team
    instructions = team.tactic.team_instructions
    group_value = replace(getattr(instructions, group), **{field: value})
    tactic = replace(team.tactic, team_instructions=replace(instructions, **{group: group_value}))
    return replace(snapshot, home_team=replace(team, tactic=tactic))


def effects_signature(snapshot):
    sim = FastMatchSimulator()
    a, d = sim.profiles(snapshot)
    from football_manager.fast_simulation.engine import _TeamRuntime
    home, away = _TeamRuntime(snapshot.home_team, a), _TeamRuntime(snapshot.away_team, d)
    return (sim._home_possession(a,d,FastMatchRandom(3)), sim._expected_shots(home,away,home_advantage=True),
            sim._expected_shots(away,home,home_advantage=False),
            tuple(sim._chance_xg(a,d,FastMatchRandom(i)) for i in range(12)),
            tuple(sim._chance_xg(d,a,FastMatchRandom(i)) for i in range(12)),
            effects.pass_completion_edge(a.tactical_features,d.tactical_features))


# All 12 previously uncovered team controls, including the old label-only width.
@pytest.mark.parametrize('group,field,low,high', [
    ('in_possession','defense_midfield_gap',Level.VERY_LOW,Level.HIGH),
    ('in_possession','midfield_attack_gap',Level.VERY_LOW,Level.HIGH),
    ('in_possession','switch_play',Level.VERY_LOW,Level.VERY_HIGH),
    ('in_possession','central_focus',Level.VERY_LOW,Level.VERY_HIGH),
    ('in_possession','overlap_frequency',Level.VERY_LOW,Level.VERY_HIGH),
    ('in_possession','long_shot_frequency',Level.VERY_LOW,Level.VERY_HIGH),
    ('transition','goalkeeper_release_speed',Level.VERY_LOW,Level.VERY_HIGH),
    ('out_of_possession','defensive_line_width',Level.VERY_LOW,Level.VERY_HIGH),
    ('out_of_possession','midfield_width',Level.VERY_LOW,Level.VERY_HIGH),
    ('out_of_possession','attacking_line_width',Level.VERY_LOW,Level.VERY_HIGH),
    ('out_of_possession','force_direction','inside','outside'),
    ('out_of_possession','marking_style','zonal','man'),
])
def test_previously_unconsumed_team_controls_reach_match_calculations(group,field,low,high):
    snapshot = build_demo_snapshot(seed=39)
    from football_manager.domain.tactical_instructions import ForceDirection, MarkingStyle
    if field=='force_direction': low,high=ForceDirection(low),ForceDirection(high)
    if field=='marking_style': low,high=MarkingStyle(low),MarkingStyle(high)
    snapshot=team_change(snapshot,'transition','after_win',AfterWinBehavior.DIRECT)
    small,big=team_change(snapshot,group,field,low),team_change(snapshot,group,field,high)
    assert effects_signature(small)!=effects_signature(big), (group,field)
    assert [(p.overall_rating,p.current_rating) for p in small.home_team.starters]==[(p.overall_rating,p.current_rating) for p in big.home_team.starters]


@pytest.mark.parametrize('field,low,high',[
    ('dribbling_frequency',Level.VERY_LOW,Level.VERY_HIGH),
    ('crossing_frequency',Level.VERY_LOW,Level.VERY_HIGH),
    ('shooting_frequency',Level.VERY_LOW,Level.VERY_HIGH),
    ('passing_risk',Level.VERY_LOW,Level.VERY_HIGH),
    ('hold_up_play',Level.VERY_LOW,Level.VERY_HIGH),
    ('attack_space',Level.VERY_LOW,Level.VERY_HIGH),
    ('in_possession_position',InPossessionPosition.WIDE,InPossessionPosition.INSIDE),
    ('out_of_possession_position',OutOfPossessionPosition.STEP_UP,OutOfPossessionPosition.DROP),
])
def test_individual_instructions_have_actual_geometry_or_action_consumers(field,low,high):
    session=DevelopmentSession()
    snapshots=[]
    for value in (low,high):
        session.home_tactic.set_player_overrides('lb',PlayerInstructionOverrides(**{field:value}))
        snapshots.append(session._build_snapshot())
    signatures=[]
    for snapshot in snapshots:
        team=snapshot.home_team
        player=next(p for p in team.starters if p.assigned_slot_id=='lb')
        signatures.append((effects_signature(snapshot),effects.shooter_factor(player,team),
                           effects.creator_factor(player),effects.pass_share_factor(player)))
    assert signatures[0]!=signatures[1],field


class RouteRandom:
    """Force construction routes without relying on chance to exercise a branch."""
    def __init__(self,route=''):
        self.route=route
    def fork(self,name):
        return RouteRandom(name)
    def random(self):
        return 0.0 if self.route=='cross' else .999


@pytest.mark.parametrize('kind',[CrossType.EARLY,CrossType.BYLINE,CrossType.LOW,CrossType.HIGH,CrossType.CUTBACK])
def test_every_nondefault_cross_type_changes_a_real_constructed_chance(kind):
    snapshot=build_demo_snapshot(seed=9)
    team=snapshot.home_team
    shooter=next(p for p in team.starters if p.assigned_position is Position.ST)
    creator=next(p for p in team.starters if p.assigned_position is Position.LW)
    defenders=snapshot.away_team.starters
    baseline=replace(creator,effective_instructions=PlayerInstructions(cross_type=CrossType.MIXED))
    changed=replace(creator,effective_instructions=PlayerInstructions(cross_type=kind))
    before=effects.action_quality(.17,shooter,baseline,team,defenders,RouteRandom())
    after=effects.action_quality(.17,shooter,changed,team,defenders,RouteRandom())
    assert before!=after
    assert 0<after[0]<1


@pytest.mark.parametrize('field',['marking','pressing_target'])
@pytest.mark.parametrize('kind',[TargetKind.PLAYER,TargetKind.POSITION,TargetKind.ROLE])
def test_targeted_instructions_only_pressure_matching_present_opponents(field,kind):
    snapshot=build_demo_snapshot(seed=9)
    player=next(p for p in snapshot.home_team.starters if p.assigned_position is Position.ST)
    other=next(p for p in snapshot.home_team.starters if p.assigned_position is Position.GK)
    marker=snapshot.away_team.starters[1]
    value={TargetKind.PLAYER:player.player_id,TargetKind.POSITION:player.assigned_position.value,TargetKind.ROLE:player.role_id}[kind]
    marker=replace(marker,effective_instructions=PlayerInstructions(**{field:TacticalTarget(kind,value)}))
    assert effects.targeted_pressure(player,(marker,))>0
    assert effects.targeted_pressure(other,(marker,))==0
    assert effects.targeted_pressure(player,())==0


def test_advanced_fullbacks_reduce_rest_defence_without_changing_ovr():
    snapshot=build_demo_snapshot(seed=39)
    team=snapshot.home_team
    changed=replace(team,tactic=replace(team.tactic,phase_shapes=(PhaseShape('in_possession',(SlotPoint('lb',.10,.22),SlotPoint('rb',.90,.22))),)))
    a,b=shape_summary(team.tactic),shape_summary(changed.tactic)
    assert b.left_cover<a.left_cover and b.right_cover<a.right_cover
    assert [(p.overall_rating,p.current_rating) for p in team.starters]==[(p.overall_rating,p.current_rating) for p in changed.starters]
    assert effects_signature(snapshot)!=effects_signature(replace(snapshot,home_team=changed))


def test_defensive_phase_targets_are_consumed_not_only_attacking_targets():
    snapshot=build_demo_snapshot(seed=39)
    team=snapshot.home_team
    shape=PhaseShape('out_of_possession',tuple(SlotPoint(s.slot_id,.5,.2) for s in team.formation.slots if s.position is not Position.GK))
    changed=replace(snapshot,home_team=replace(team,tactic=replace(team.tactic,phase_shapes=(shape,))))
    a,b=build_fast_team_profile(team),build_fast_team_profile(changed.home_team)
    assert a.tactical_features.shape.left_cover==b.tactical_features.shape.left_cover
    assert a.tactical_features.shape.block_centre_cover>b.tactical_features.shape.block_centre_cover
    assert effects_signature(snapshot)!=effects_signature(changed)


@pytest.mark.parametrize('side',[TeamSide.HOME,TeamSide.AWAY])
@pytest.mark.parametrize('phase',[TacticalPhase.IN_POSSESSION,TacticalPhase.OUT_OF_POSSESSION])
def test_spatial_engine_uses_exact_phase_targets_with_single_away_mirror(side,phase):
    snapshot=build_demo_snapshot(seed=5)
    attr='home_team' if side is TeamSide.HOME else 'away_team'
    team=getattr(snapshot,attr)
    tactic=replace(team.tactic,phase_shapes=(PhaseShape(phase.value,(SlotPoint('lb',.24,.32),)),))
    snapshot=replace(snapshot,**{attr:replace(team,tactic=tactic)})
    engine=SpatialMatchEngine(snapshot)
    possessing=side if phase is TacticalPhase.IN_POSSESSION else (TeamSide.AWAY if side is TeamSide.HOME else TeamSide.HOME)
    engine.set_team_possession(possessing)
    target=engine.state.player_for_slot(side,'lb').tactical_target
    expected_x=.68*engine.state.pitch.length_m
    expected_y=.24*engine.state.pitch.width_m
    if side is TeamSide.AWAY:
        expected_x=engine.state.pitch.length_m-expected_x
        expected_y=engine.state.pitch.width_m-expected_y
    assert target.x==pytest.approx(expected_x)
    assert target.y==pytest.approx(expected_y)


def plans_session():
    session=DevelopmentSession()
    def run(action,**values):
        return apply_squad_command(session,{'action':action,**values})
    run('studio_save',name='Original')
    first=session.tactical_studio.active_id
    run('studio_plan',plan='A',entry_id=first)
    run('studio_position',slot_id='lb',position='AM')
    run('studio_point',phase='in_possession',slot_id='lb',x=32,y=25)
    run('studio_save',name='Attacking alternative')
    run('studio_plan',plan='B',entry_id=session.tactical_studio.active_id)
    run('studio_load',entry_id=first)
    return session,run


def test_plan_preparation_does_not_mutate_live_roster_or_familiarity():
    from football_manager.persistence.session_codec import capture_manager_graph
    session,run=plans_session()
    run('studio_rules',rules=[{'plan':'B','minute':60,'condition':'always'}])
    before=capture_manager_graph(session)
    prepared=prepared_match_plans(session)
    assert len(prepared)==1
    assert capture_manager_graph(session)==before


@pytest.mark.parametrize('condition',['always','leading','level','trailing'])
def test_match_plans_check_actual_score_before_scheduled_minute(condition):
    session,run=plans_session()
    run('studio_rules',rules=[{'plan':'B','minute':60,'condition':condition}])
    snapshot=session._build_snapshot()
    plans=prepared_match_plans(session)
    result=FastMatchSimulator().simulate(snapshot,tactical_plans=plans)
    event=result.tactical_events[0]
    own=sum(g.club_id==event.club_id and g.minute<60 for g in result.goals)
    other=sum(g.club_id!=event.club_id and g.minute<60 for g in result.goals)
    assert (event.own_goals,event.opponent_goals)==(own,other)
    assert event.applied==PlanRule('B',60,condition).matches(own,other)
    stats={(p.club_id,p.player_id):p for p in result.player_statistics}
    for key,p in stats.items():
        assert sum(s.minutes for s in result.role_segments if (s.club_id,s.player_id)==key)==p.minutes
    assert FastMatchSimulator().simulate(snapshot,tactical_plans=plans)==result


def test_different_later_plans_do_not_rewrite_previous_goals_or_cards():
    session,run=plans_session()
    snapshot=session._build_snapshot()
    results=[]
    for key in ('A','B'):
        run('studio_rules',rules=[{'plan':key,'minute':60,'condition':'always'}])
        results.append(FastMatchSimulator().simulate(snapshot,tactical_plans=prepared_match_plans(session)))
    a,b=results
    assert [g for g in a.goals if g.minute<60]==[g for g in b.goals if g.minute<60]
    assert [c for c in a.cards if c.minute<60]==[c for c in b.cards if c.minute<60]
    assert a.role_segments!=b.role_segments


def test_match_plans_cannot_smuggle_different_players_or_teams():
    snapshot=build_demo_snapshot(seed=3)
    wrong=replace(snapshot.home_team,club_id='other')
    with pytest.raises(ValueError):
        FastMatchSimulator().simulate(snapshot,tactical_plans=(FastTacticalChange(PlanRule('A',60),'Bad',wrong),))
    player=replace(snapshot.home_team.starters[0],player_id='unregistered')
    wrong=replace(snapshot.home_team,starters=(player,*snapshot.home_team.starters[1:]))
    with pytest.raises(ValueError):
        FastMatchSimulator().simulate(snapshot,tactical_plans=(FastTacticalChange(PlanRule('A',60),'Bad',wrong),))


def test_unplanned_simulation_keeps_normal_path_and_reproducibility():
    snapshot=build_demo_snapshot(seed=1)
    simulator=FastMatchSimulator()
    plain=simulator.simulate(snapshot)
    assert plain==simulator.simulate(snapshot,tactical_plans=())
    assert plain.tactical_events==() and plain.role_segments==()


def test_seeded_plan_stress_keeps_dismissals_stats_participation_and_learning_consistent():
    session,run=plans_session()
    run('studio_rules',rules=[{'plan':'B','minute':35,'condition':'always'},{'plan':'A','minute':70,'condition':'always'}])
    base=session._build_snapshot()
    plans=prepared_match_plans(session)
    red_count=0
    for seed in range(24):
        result=FastMatchSimulator().simulate(replace(base,seed=seed),tactical_plans=plans)
        result.__post_init__()
        for team,stats in ((base.home_team,result.statistics_home),(base.away_team,result.statistics_away)):
            players=[p for p in result.player_statistics if p.club_id==team.club_id]
            assert stats.shots==sum(p.shots for p in players)
            assert stats.passes_attempted==sum(p.passes_attempted for p in players)
            assert stats.passes_completed==sum(p.passes_completed for p in players)
            assert stats.red_cards==sum(p.red_cards for p in players)
            assert all(0<=p.condition_after<=100 and 0<=p.fatigue_after<=100 for p in players)
        for card in result.cards:
            if card.card.value!='red':continue
            red_count+=1
            assert not any(g.club_id==card.club_id and card.player_id in (g.scorer_player_id,g.assist_player_id) and g.minute>card.minute for g in result.goals)
            assert max(s.end_minute for s in result.role_segments if s.club_id==card.club_id and s.player_id==card.player_id)==card.minute
    assert red_count>0


def test_goalkeeper_custom_targets_are_not_a_free_build_up_bonus():
    snapshot=build_demo_snapshot(seed=39)
    team=snapshot.home_team
    changed=replace(snapshot,home_team=replace(team,tactic=replace(team.tactic,phase_shapes=(
        PhaseShape('in_possession',(SlotPoint('gk',.5,.55),)),
        PhaseShape('out_of_possession',(SlotPoint('gk',.5,.45),)),
    ))))
    shape=shape_summary(changed.home_team.tactic)
    assert shape.keeper_support>0 and shape.keeper_exposure>0
    assert effects_signature(snapshot)!=effects_signature(changed)


def test_extra_time_plan_tracks_real_substitutes_and_preserves_penalty_integrity():
    from football_manager.domain import MatchDecider
    from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
    base=neutralize_fast_snapshot(build_demo_snapshot(seed=1),rating=70,seed=1)
    def prepared_bench(team):
        roles=tuple((s.role_id,65.0) for s in team.tactic.slots)
        return replace(team,bench=tuple(replace(p,familiarity=replace(p.familiarity,roles=roles,tactics=((team.tactic.tactic_id,65.0),))) for p in team.bench))
    base=replace(base,home_team=prepared_bench(base.home_team),away_team=prepared_bench(base.away_team),
                 context=replace(base.context,competition=replace(base.context.competition,match_decider=MatchDecider.EXTRA_TIME_AND_PENALTIES,extra_time_additional_substitutions=1)))
    target=replace(base.home_team,tactic=replace(base.home_team.tactic,phase_shapes=(PhaseShape('in_possession',(SlotPoint('lb',.22,.38),)),)))
    plans=(FastTacticalChange(PlanRule('B',100),'Extra-time alternative',target),)
    simulator=FastMatchSimulator()
    found=None
    for seed in range(1,81):
        snapshot=replace(base,seed=seed)
        result=simulator.simulate(snapshot,tactical_plans=plans)
        if result.tactical_events and result.substitutions:
            found=result
            assert result.tactical_events[0].minute==100 and result.tactical_events[0].applied
            assert result==simulator.simulate(snapshot,tactical_plans=plans)
            for sub in result.substitutions:
                segments=[s for s in result.role_segments if s.club_id==sub.club_id]
                assert max(s.end_minute for s in segments if s.player_id==sub.player_out_id)==90
                assert any(s.player_id==sub.player_in_id and s.start_minute>=90 for s in segments)
            result.__post_init__()
            break
    assert found is not None,'seed batch must exercise a real extra-time substitution and subsequent plan'


def test_matchday_plan_edits_are_temporary_and_complete_save_keeps_played_segments(tmp_path):
    from copy import deepcopy
    from football_manager.persistence import SQLiteSaveRepository,save_manager_career,load_manager_career
    from football_manager.ui_shell.runtime import UIRuntime
    from football_manager.ui_shell.application import GameApplication
    from football_manager.ui_shell.match import prematch_read_model
    from football_manager.ui_shell.progression import pending_managed_match,advance_day
    from football_manager.services.tactical_studio import same_tactic
    session,run=plans_session()
    while session.current_date < pending_managed_match(session).match_date:
        advance_day(session)
    baseline_tactic,baseline_studio=deepcopy((session.home_tactic,session.tactical_studio))
    runtime=UIRuntime(session,SQLiteSaveRepository(tmp_path/'matchday.sqlite3'))
    app=GameApplication(runtime,prematch_builder=prematch_read_model)
    fixture=prematch_read_model(session,runtime.admin)['match']['fixture_id']
    def match(action,**values):
        return app.command('match.command',{'action':action,'fixture_id':fixture,**values})
    preview=match('match_tactic',command={'action':'studio_activate_plan','plan':'B'})
    assert preview['tactical']['studio']['active_id']==baseline_studio.plans['B']
    assert same_tactic(runtime.session.home_tactic,baseline_tactic)
    assert runtime.session.tactical_studio==baseline_studio
    match('match_tactic',command={'action':'studio_rules','rules':[{'plan':'A','minute':60,'condition':'always'}]})
    summary=match('quick_sim')
    assert summary['status']=='finished'
    assert any(e['kind']=='tactical_plan' and e['plan']=='A' and e['applied'] for e in summary['events'])
    assert same_tactic(runtime.session.home_tactic,baseline_tactic)
    assert runtime.session.tactical_studio==baseline_studio
    assert runtime.session.last_result.role_segments
    save_manager_career(runtime.save_repository,slot_id='ts19-match',display_name='Plans',session=runtime.session,expected_revision=0)
    restored=load_manager_career(runtime.save_repository,'ts19-match').session
    assert restored.last_result==runtime.session.last_result
    assert restored.tactical_studio==baseline_studio

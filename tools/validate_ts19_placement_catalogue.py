"""Small Python-only smoke run: confirmed drops in all 28 formations / both phases."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.dev_ui.formations import development_formations
from football_manager.domain.enums import Position
from football_manager.domain.tactical_geometry import phase_points
from football_manager.domain.roles import get_role
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.ui_shell.transactions import apply_squad_command_atomically


def main():
    template=DevelopmentSession()
    simulator=FastMatchSimulator()
    results=[]
    for formation in development_formations():
        for phase in ('in_possession','out_of_possession'):
            session=deepcopy(template)
            session.set_formation(formation.formation_id)
            slot=next(s.slot_id for s in session.home_tactic.formation.slots if s.position is not Position.GK)
            other='out_of_possession' if phase=='in_possession' else 'in_possession'
            previous=phase_points(session.home_tactic,other)
            ids={e.slot_id:e.player.id for e in session.home_lineup.starters}
            apply_squad_command_atomically(session,dict(action='studio_place',slot_id=slot,phase=phase,x=50,y=29,position='AM'),None)
            assert phase_points(session.home_tactic,phase)[slot]==(.5,.29)
            assert phase_points(session.home_tactic,other)==previous
            assert session.home_tactic.formation.slot(slot).position is Position.AM
            assert get_role(session.home_tactic.role_assignments[slot].role_id).supports(Position.AM)
            assert {e.slot_id:e.player.id for e in session.home_lineup.starters}==ids
            snapshot=session._build_snapshot()
            match=simulator.simulate(snapshot)
            assert simulator.simulate(snapshot)==match
            assert match.home_goals>=0 and match.away_goals>=0
            results.append(dict(formation=formation.formation_id,phase=phase,slot=slot,score=[match.home_goals,match.away_goals]))
    print(json.dumps(dict(confirmed_placements=len(results),simulations=len(results)*2,checks='identity, role, coordinates, opposite phase, snapshot, same-seed determinism',results=results),indent=2))


if __name__=='__main__':main()

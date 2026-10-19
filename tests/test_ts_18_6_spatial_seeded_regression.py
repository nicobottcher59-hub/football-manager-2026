"""TS-18.6 supplementary spatial engine smoke tests; no gameplay changes."""
from dataclasses import replace

import pytest

from football_manager.simulation import FlowConfig, MatchFlowController, MatchPhase
from test_spatial_core import make_snapshot


@pytest.mark.parametrize("seed", range(18660, 18684))
def test_spatial_flow_finishes_with_consistent_active_agents(seed):
    config = FlowConfig(
        regulation_half_seconds=2.0,
        extra_time_half_seconds=1.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=2.0,
        extra_time_added_time_cap_seconds=1.0,
        autonomous_actions=False,
        autonomous_tackles=False,
    )
    flow = MatchFlowController(make_snapshot(seed=seed), config=config)
    flow.start()
    for _ in range(250):
        if flow.phase is MatchPhase.FINISHED:
            break
        flow.step()
        agents = flow.engine.state.players
        assert len(agents) == len(set(agents))
    assert flow.phase is MatchPhase.FINISHED

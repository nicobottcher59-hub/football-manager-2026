from __future__ import annotations

from football_manager.calibration import audit_match_events
from football_manager.simulation import (
    MatchEvent,
    MatchEventType,
    MatchPhase,
    MatchRandom,
    TeamSide,
)


def _event(
    sequence: int,
    event_type: MatchEventType,
    *,
    side: TeamSide | None = None,
    data: tuple[tuple[str, str], ...] = (),
) -> MatchEvent:
    return MatchEvent(
        sequence=sequence,
        tick=sequence,
        time_label=f"{sequence}'",
        phase=MatchPhase.FIRST_HALF,
        event_type=event_type,
        side=side,
        data=data,
    )


def test_named_rng_streams_are_reproducible_and_independent() -> None:
    root_a = MatchRandom(510_200)
    passing_a = root_a.fork("passing")
    shooting_a = root_a.fork("shooting")

    # Burning extra passing draws must not move the shooting sequence.
    _ = [passing_a.random() for _ in range(25)]
    shooting_values = [shooting_a.random() for _ in range(4)]

    root_b = MatchRandom(510_200)
    shooting_b = root_b.fork("shooting")
    assert shooting_values == [shooting_b.random() for _ in range(4)]

    # Namespaces are deterministic but intentionally distinct.
    passing_b = root_b.fork("passing")
    assert [passing_b.random() for _ in range(4)] != shooting_values


def test_keyed_random_is_stable_without_advancing_stream() -> None:
    first = MatchRandom(42).fork("decisions")
    second = MatchRandom(42).fork("decisions")

    before = first.random()
    keyed_1 = first.keyed_random(120, "home:cm", "press")
    keyed_2 = first.keyed_random(120, "home:cm", "press")
    after = first.random()

    assert keyed_1 == keyed_2
    assert before == second.random()
    assert after == second.random()


def test_event_details_parse_legacy_metadata_once_into_typed_fields() -> None:
    event = _event(
        1,
        MatchEventType.SHOT,
        side=TeamSide.HOME,
        data=(
            ("shot_id", "shot:10:home:st:1"),
            ("xg", "0.3275"),
            ("scored", "false"),
            ("seconds", "120"),
        ),
    )

    assert event.details is not None
    assert event.details.shot_id == "shot:10:home:st:1"
    assert event.details.xg == 0.3275
    assert event.details.scored is False
    assert event.details.seconds == 120
    # Legacy presentation consumers remain supported.
    assert event.value("xg") == "0.3275"


def test_event_audit_accepts_one_shot_one_linked_goal_and_matching_score() -> None:
    shot_id = "shot:20:home:st:7"
    events = (
        _event(
            1,
            MatchEventType.SHOT,
            side=TeamSide.HOME,
            data=(("shot_id", shot_id), ("xg", "0.35")),
        ),
        _event(
            2,
            MatchEventType.GOAL,
            side=TeamSide.HOME,
            data=(("shot_id", shot_id), ("xg", "0.35"), ("outcome", "goal")),
        ),
    )

    audit = audit_match_events(events, home_goals=1, away_goals=0)

    assert audit.is_consistent
    assert audit.integrity_issues == 0
    assert audit.shot_attempts == 1
    assert audit.shot_resolutions == 1


def test_event_audit_flags_goal_without_shot_and_score_event_mismatch() -> None:
    events = (
        _event(1, MatchEventType.GOAL, side=TeamSide.HOME, data=(("xg", "0.2"),)),
    )

    audit = audit_match_events(events, home_goals=2, away_goals=0)

    assert not audit.is_consistent
    assert audit.orphan_shot_resolutions == 1
    assert audit.score_goal_delta == 1
    assert audit.integrity_issues >= 2

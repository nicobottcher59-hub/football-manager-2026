from datetime import date

import pytest

from football_manager.domain import (
    Club,
    Foot,
    Formation,
    FormationSlot,
    LineupEntry,
    MatchLineup,
    MentalAttributes,
    PhysicalAttributes,
    Player,
    PlayerAttributes,
    PlayerIdentity,
    Position,
    PositionalFamiliarity,
    Squad,
    TechnicalAttributes,
)


def make_player(player_id: str, position: Position = Position.CM) -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id=player_id,
            first_name="Player",
            last_name=player_id,
            birth_date=date(2000, 1, 1),
            nationality="Argentina",
            dominant_foot=Foot.RIGHT,
        ),
        attributes=PlayerAttributes(
            technical=TechnicalAttributes(
                passing=70,
                technique=70,
                finishing=70,
                first_touch=70,
                dribbling=70,
                crossing=70,
                tackling=70,
                heading=70,
                long_shots=70,
                shot_power=70,
                marking=70,
                set_pieces=70,
                penalties=70,
            ),
            mental=MentalAttributes(
                vision=70,
                decisions=70,
                anticipation=70,
                concentration=70,
                composure=70,
                positioning=70,
                off_the_ball=70,
                teamwork=70,
                work_rate=70,
                aggression=70,
                bravery=70,
                creativity=70,
                tactical_intelligence=70,
            ),
            physical=PhysicalAttributes(
                pace=70,
                acceleration=70,
                strength=70,
                stamina=70,
                agility=70,
                balance=70,
                jumping_reach=70,
                natural_fitness=70,
            ),
        ),
        positional_familiarity=PositionalFamiliarity({position: 90}),
        original_position=position,
        primary_position=position,
    )


def make_formation() -> Formation:
    return Formation(
        formation_id="4-3-3-test",
        name="4-3-3 Test",
        slots=(
            FormationSlot("gk", Position.GK),
            FormationSlot("rb", Position.RB),
            FormationSlot("rcb", Position.RCB),
            FormationSlot("lcb", Position.LCB),
            FormationSlot("lb", Position.LB),
            FormationSlot("rcm", Position.RCM),
            FormationSlot("cm", Position.CM),
            FormationSlot("lcm", Position.LCM),
            FormationSlot("rw", Position.RW),
            FormationSlot("st", Position.ST),
            FormationSlot("lw", Position.LW),
        ),
    )


def make_players(count: int = 16) -> list[Player]:
    return [make_player(f"p{i}") for i in range(1, count + 1)]


def make_lineup(players: list[Player], club_id: str = "club-1") -> MatchLineup:
    formation = make_formation()
    starters = tuple(
        LineupEntry(slot.slot_id, player)
        for slot, player in zip(formation.slots, players[:11], strict=True)
    )
    return MatchLineup(
        club_id=club_id,
        formation=formation,
        starters=starters,
        bench=tuple(players[11:16]),
    )


def test_squad_add_get_remove_and_contains() -> None:
    player = make_player("p1")
    squad = Squad()
    squad.add(player)

    assert squad.contains("p1")
    assert squad.get("p1") is player
    assert len(squad) == 1
    assert squad.remove("p1") is player
    assert not squad.contains("p1")


def test_squad_rejects_duplicate_player_ids() -> None:
    squad = Squad()
    squad.add(make_player("p1"))
    with pytest.raises(ValueError, match="already in the squad"):
        squad.add(make_player("p1"))


def test_formation_requires_exactly_eleven_slots() -> None:
    with pytest.raises(ValueError, match="exactly 11"):
        Formation(
            formation_id="bad",
            name="Bad",
            slots=(FormationSlot("gk", Position.GK),),
        )


def test_formation_requires_one_goalkeeper_slot() -> None:
    slots = tuple(FormationSlot(f"s{i}", Position.CM) for i in range(11))
    with pytest.raises(ValueError, match="exactly one goalkeeper"):
        Formation(formation_id="bad", name="Bad", slots=slots)


def test_formation_supports_repeated_positions_via_unique_slots() -> None:
    formation = Formation(
        formation_id="4-4-2-test",
        name="4-4-2 Test",
        slots=(
            FormationSlot("gk", Position.GK),
            FormationSlot("rb", Position.RB),
            FormationSlot("rcb", Position.CB),
            FormationSlot("lcb", Position.CB),
            FormationSlot("lb", Position.LB),
            FormationSlot("rm", Position.RW),
            FormationSlot("rcm", Position.CM),
            FormationSlot("lcm", Position.CM),
            FormationSlot("lm", Position.LW),
            FormationSlot("rst", Position.ST),
            FormationSlot("lst", Position.ST),
        ),
    )

    assert len(formation.slots) == 11
    assert formation.slot("rst").position is Position.ST
    assert formation.slot("lst").position is Position.ST


def test_match_lineup_maps_players_to_formation_positions() -> None:
    players = make_players()
    lineup = make_lineup(players)

    assert lineup.player_for_slot("gk") is players[0]
    assert lineup.assigned_position(players[9].id) is Position.ST
    assert len(lineup.starting_players) == 11
    assert len(lineup.bench) == 5


def test_match_lineup_rejects_duplicate_player() -> None:
    players = make_players()
    formation = make_formation()
    starters = [
        LineupEntry(slot.slot_id, player)
        for slot, player in zip(formation.slots, players[:11], strict=True)
    ]
    starters[-1] = LineupEntry("lw", players[0])

    with pytest.raises(ValueError, match="cannot appear more than once"):
        MatchLineup(
            club_id="club-1",
            formation=formation,
            starters=tuple(starters),
        )


def test_match_lineup_rejects_unknown_or_missing_slot() -> None:
    players = make_players()
    formation = make_formation()
    starters = [
        LineupEntry(slot.slot_id, player)
        for slot, player in zip(formation.slots, players[:11], strict=True)
    ]
    starters[-1] = LineupEntry("mystery", players[10])

    with pytest.raises(ValueError, match="lineup does not match formation"):
        MatchLineup(
            club_id="club-1",
            formation=formation,
            starters=tuple(starters),
        )


def test_match_lineup_rejects_unavailable_player() -> None:
    players = make_players()
    players[3].state.injury = "hamstring"

    with pytest.raises(ValueError, match="unavailable players"):
        make_lineup(players)


def test_club_accepts_lineup_made_only_from_its_squad() -> None:
    players = make_players()
    club = Club(
        club_id="club-1",
        name="Test Club",
        short_name="TST",
        country="Argentina",
        squad=Squad.from_players(players),
    )
    lineup = make_lineup(players)

    club.validate_lineup(lineup)


def test_club_rejects_lineup_with_outside_player() -> None:
    players = make_players()
    club = Club(
        club_id="club-1",
        name="Test Club",
        short_name="TST",
        country="Argentina",
        squad=Squad.from_players(players[:15]),
    )
    lineup = make_lineup(players)

    with pytest.raises(ValueError, match="outside the club squad"):
        club.validate_lineup(lineup)


def test_club_rejects_lineup_for_different_club() -> None:
    players = make_players()
    club = Club(
        club_id="club-1",
        name="Test Club",
        short_name="TST",
        country="Argentina",
        squad=Squad.from_players(players),
    )
    lineup = make_lineup(players, club_id="club-2")

    with pytest.raises(ValueError, match="different club"):
        club.validate_lineup(lineup)

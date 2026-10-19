from __future__ import annotations

from dataclasses import dataclass, field

from .lineup import MatchLineup
from .squad import Squad


@dataclass(slots=True)
class Club:
    club_id: str
    name: str
    short_name: str
    country: str
    squad: Squad = field(default_factory=Squad)

    def __post_init__(self) -> None:
        if not self.club_id.strip():
            raise ValueError("club_id cannot be empty")
        if not self.name.strip():
            raise ValueError("club name cannot be empty")
        if not self.short_name.strip():
            raise ValueError("club short_name cannot be empty")
        if not self.country.strip():
            raise ValueError("club country cannot be empty")

    @property
    def id(self) -> str:
        return self.club_id

    def validate_lineup(self, lineup: MatchLineup) -> None:
        if lineup.club_id != self.club_id:
            raise ValueError("lineup belongs to a different club")

        outsiders = [
            player.id for player in lineup.selected_players if not self.squad.contains(player.id)
        ]
        if outsiders:
            raise ValueError(f"lineup contains players outside the club squad: {sorted(outsiders)}")

        # Validate the canonical player object, not just an identical ID. This
        # catches stale or copied players whose attributes/state diverge from
        # the club's authoritative squad between submission and kickoff.
        impostors = [
            player.id for player in lineup.selected_players
            if self.squad.get(player.id) is not player
        ]
        if impostors:
            raise ValueError(f"lineup contains non-canonical squad players: {sorted(impostors)}")

        # A valid lineup at submission may become invalid before kickoff due
        # to an injury, suspension or loss of fitness (including substitutes).
        unavailable = [player.id for player in lineup.selected_players
                       if not player.state.is_available]
        if unavailable:
            raise ValueError(f"unavailable players cannot be selected: {sorted(unavailable)}")

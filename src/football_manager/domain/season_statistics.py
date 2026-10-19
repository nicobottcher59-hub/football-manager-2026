"""TS-22: compact, season/competition-scoped actual match statistics.

No events are manufactured and no attribute/OVR formula lives in this module.
Immutable player totals allow the existing world undo journal to commit them
atomically alongside results. A legacy save may have only basic season totals;
coverage is explicit instead of pretending missing matches were zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from math import isfinite


@dataclass(frozen=True, slots=True)
class SeasonPlayerStatistics:
    appearances: int = 0
    starts: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    xg: float = 0.0
    passes_attempted: int = 0
    passes_completed: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating_total: float = 0.0
    clean_sheets: int = 0

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in ('xg', 'rating_total'):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                    raise ValueError('invalid season statistic')
            elif type(value) is not int or value < 0:
                raise ValueError('invalid season count')
        if (self.starts > self.appearances or self.minutes > self.appearances * 120
                or self.clean_sheets > self.appearances or self.rating_total > 10 * self.appearances
                or self.shots_on_target > self.shots or self.passes_completed > self.passes_attempted):
            raise ValueError('inconsistent season statistics')

    def __deepcopy__(self, memo):
        # Totals contain only immutable scalar values. Transaction snapshots can
        # share them safely: recording replaces a total, never mutates it.
        memo[id(self)] = self
        return self

    def plus(self, other: SeasonPlayerStatistics) -> SeasonPlayerStatistics:
        return SeasonPlayerStatistics(**{f.name: getattr(self, f.name) + getattr(other, f.name)
                                        for f in fields(self)})

    def view(self) -> dict:
        result = {f.name: getattr(self, f.name) for f in fields(self)
                  if f.name != 'rating_total'}
        result.update(xg=round(self.xg, 2),
                      pass_completion=round(100 * self.passes_completed / self.passes_attempted, 1)
                      if self.passes_attempted else None,
                      average_match_rating=round(self.rating_total / self.appearances, 2)
                      if self.appearances else None,
                      xa=None, tackles=None)
        return result


@dataclass(slots=True)
class SeasonStatisticsLedger:
    # season -> competition -> player -> totals; IDs are stable, not names.
    seasons: dict[str, dict[str, dict[str, SeasonPlayerStatistics]]] = field(default_factory=dict)
    recorded_fixtures: dict[str, bool] = field(default_factory=dict)
    coverage_from: dict[str, date] = field(default_factory=dict)
    complete_seasons: dict[str, bool] = field(default_factory=dict)
    competition_names: dict[str, str] = field(default_factory=dict)
    version: int = 1

    def start_season(self, season: str, on_date: date, *, complete: bool) -> None:
        self.seasons.setdefault(season, {})
        self.coverage_from.setdefault(season, on_date)
        self.complete_seasons.setdefault(season, complete)

    def validate(self) -> None:
        mappings = (self.seasons, self.recorded_fixtures, self.coverage_from, self.complete_seasons, self.competition_names)
        if any(not isinstance(v, dict) for v in mappings):
            raise ValueError('invalid statistics ledger maps')
        if any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in self.competition_names.items()):
            raise ValueError('invalid statistics competition labels')
        if type(self.version) is not int or self.version != 1 or set(self.seasons) != set(self.coverage_from) or set(self.seasons) != set(self.complete_seasons):
            raise ValueError('invalid statistics ledger version/coverage')
        for season, competitions in self.seasons.items():
            if not isinstance(season, str) or not season or not isinstance(self.coverage_from[season], date) or type(self.complete_seasons[season]) is not bool:
                raise ValueError('invalid statistics season')
            if not isinstance(competitions, dict):
                raise ValueError('invalid statistics competitions')
            for cid, players in competitions.items():
                if not isinstance(cid, str) or not cid:
                    raise ValueError('invalid statistics competition')
                if not isinstance(players, dict):
                    raise ValueError('invalid statistics totals')
                for pid, totals in players.items():
                    if not isinstance(pid, str) or not pid or not isinstance(totals, SeasonPlayerStatistics):
                        raise ValueError('invalid statistics player')
                    totals.__post_init__()
        if any(not isinstance(k, str) or v is not True for k, v in self.recorded_fixtures.items()):
            raise ValueError('invalid statistics fixture ledger')

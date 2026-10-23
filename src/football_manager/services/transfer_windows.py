"""TS-FIX-04: calendar-driven professional transfer registration windows.

Windows are keyed by the buying club's country, not by its display name.
This data pack contains English leagues. Other countries use the English
fallback ONLY until their actual league calendars are imported and configured.
Negotiations can happen year-round; registration and payment cannot.
"""
from __future__ import annotations
from datetime import date

# (starting month, starting day, ending month, ending day); no cross-year
# intervals for the initial English development world.
WINDOWS_BY_COUNTRY = {
    'England': ((1, 1, 1, 31), (7, 1, 8, 31)),
}
DEFAULT_COUNTRY = 'England'


def windows_for_year(year: int, country: str = DEFAULT_COUNTRY) -> tuple[tuple[date, date], ...]:
    rules = WINDOWS_BY_COUNTRY.get(country, WINDOWS_BY_COUNTRY[DEFAULT_COUNTRY])
    return tuple((date(year, m, day), date(year, end_m, end_day))
                 for m, day, end_m, end_day in rules)


def window_open(day: date, country: str = DEFAULT_COUNTRY) -> bool:
    return any(start <= day <= end for start, end in windows_for_year(day.year, country))


def next_opening(day: date, country: str = DEFAULT_COUNTRY) -> date:
    for year in (day.year, day.year + 1, day.year + 2):
        for start, end in windows_for_year(year, country):
            if start <= day <= end:
                return day
            if start > day:
                return start
    raise ValueError('No configured future transfer window')


def window_info(day: date, country: str = DEFAULT_COUNTRY) -> dict:
    current = next(((start, end) for start, end in windows_for_year(day.year, country)
                    if start <= day <= end), None)
    next_day = next_opening(day, country)
    upcoming = next(((start, end) for start, end in windows_for_year(next_day.year, country)
                     if start <= next_day <= end), None)
    return {'country': country, 'open': current is not None,
            'opens_on': (current or upcoming)[0].isoformat(),
            'closes_on': (current or upcoming)[1].isoformat(),
            'next_registration_on': next_day.isoformat()}

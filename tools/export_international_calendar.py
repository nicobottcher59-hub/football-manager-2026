"""Export the TC-E1 international reservation calendar to CSV or JSON.

Projected dates are game templates, not official fixtures or announcements.
Usage: python tools/export_international_calendar.py --from-year 2026 --to-year 2050 --output international_calendar.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from football_manager.domain.international_calendar import build_international_calendar


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, default=2026)
    parser.add_argument("--to-year", type=int, default=2050)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    calendar = build_international_calendar(args.from_year, args.to_year)
    path: Path = args.output
    if path.suffix.lower() not in (".csv", ".json"):
        parser.error("--output must end with .csv or .json")
    path.parent.mkdir(parents=True, exist_ok=True)
    events = calendar.to_dict()["events"]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps({"note": "Not a fixture list; dates marked projected are game templates.",
                                    "events": events}, indent=2), encoding="utf-8")
    else:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=("event_id", "name", "start_date", "end_date",
                                                      "impact", "source", "confederation",
                                                      "release_start", "release_end"))
            writer.writeheader()
            writer.writerows(events)
    print(f"Wrote {len(events)} international calendar reservations to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

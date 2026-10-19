"""Print tactical instruction coverage of the current fast simulator."""

from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from football_manager.fast_simulation.tactical_coverage import tactical_consumer_coverage


def main() -> None:
    entries = tactical_consumer_coverage()
    counts = Counter(entry.status for entry in entries)
    print(f"Tactical controls audited: {len(entries)}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    print("\nDetails:")
    for entry in entries:
        print(f"{entry.control}: {entry.status}")


if __name__ == "__main__":
    main()

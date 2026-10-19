from __future__ import annotations

from demo_match_factory import build_demo_snapshot
from football_manager.presentation.debug_viewer import run_debug_viewer


def main() -> None:
    snapshot = build_demo_snapshot(seed=5901)
    run_debug_viewer(snapshot)


if __name__ == "__main__":
    main()

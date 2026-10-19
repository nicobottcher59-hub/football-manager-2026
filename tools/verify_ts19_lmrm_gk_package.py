"""Verify the TS-19 LM/RM + locked keeper incremental install; Python only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        manifest = json.loads((root / "TS_19_LMRM_GK_MANIFEST.json").read_text(encoding="utf-8"))
        files = manifest["files"]
        problems = []
        for record in files:
            candidate = (root / record["path"]).resolve()
            if not candidate.is_relative_to(root):
                problems.append("Unsafe manifest path: " + record["path"])
            elif not candidate.is_file():
                problems.append("Missing: " + record["path"])
            elif hashlib.sha256(candidate.read_bytes()).hexdigest() != record["sha256"]:
                problems.append("Changed: " + record["path"])
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"TS-19 LM/RM + fixed goalkeeper: {len(files)} files verified (SHA-256).")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot verify TS-19 LM/RM patch: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

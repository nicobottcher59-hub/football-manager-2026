"""Verify the installed files of the TS-23.1 incremental release (stdlib only)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_23_1_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_23_MANIFEST.json').is_file():
        print('ERROR: TS-23 base not detected. Install TS-23 before TS-23.1.')
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: missing/invalid TS-23.1 manifest: {exc}')
        return 1
    bad = []
    for name, expected in data['sha256'].items():
        target = (ROOT / name).resolve()
        if target != ROOT.resolve() and ROOT.resolve() not in target.parents:
            bad.append(name + ': invalid path')
            continue
        if not target.is_file():
            bad.append(name + ': missing')
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            bad.append(name + ': SHA-256 mismatch')
    if bad:
        print('TS-23.1 package FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-23.1 package OK: {len(data["sha256"])} files checked; SHA-256 verified.')
    print('No Node or npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

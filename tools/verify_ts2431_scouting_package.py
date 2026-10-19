"""Verify TS-24.3.1 incremental files using Python stdlib only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_3_1_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_3_MANIFEST.json').is_file():
        print('ERROR: TS-24.3 is required before TS-24.3.1.')
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: missing or invalid TS-24.3.1 manifest: {exc}')
        return 1
    bad = []
    for name, expected in data['sha256'].items():
        dest = (ROOT / name).resolve()
        if ROOT.resolve() not in dest.parents:
            bad.append(name + ': invalid path')
        elif not dest.is_file():
            bad.append(name + ': missing')
        elif hashlib.sha256(dest.read_bytes()).hexdigest() != expected:
            bad.append(name + ': hash mismatch')
    if bad:
        print('TS-24.3.1 verification FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-24.3.1 OK: {len(data["sha256"])} files checked, SHA-256 verified.')
    print('No Node or npm required to play.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

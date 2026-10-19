"""TS-24.1 incremental integrity check; Python standard library only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_1_MANIFEST.json'
BASE = ROOT / 'TS_23_2_1_MANIFEST.json'


def main() -> int:
    if not BASE.is_file():
        print('ERROR: TS-23.2.1 base not detected. Install TS-23.2.1 before TS-24.1.')
        return 1
    try:
        payload = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if payload['save_graph_version'] != 12 or payload['base'] != 'TS-23.2.1':
            raise ValueError('incorrect release metadata')
        hashes = payload['sha256']
        if len(hashes) != payload['files'] or not hashes:
            raise ValueError('file count mismatch')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: missing or invalid TS-24.1 manifest: {exc}')
        return 1
    bad: list[str] = []
    for name, expected in hashes.items():
        target = (ROOT / name).resolve()
        if ROOT.resolve() not in target.parents or not target.is_file():
            bad.append(f'{name}: missing or unsafe path')
        elif not isinstance(expected, str) or len(expected) != 64:
            bad.append(f'{name}: invalid SHA-256 entry')
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            bad.append(f'{name}: SHA-256 mismatch')
    if bad:
        print('TS-24.1 verification FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-24.1 verified: {len(hashes)} files, all SHA-256 checks match.')
    print('Python only; no Node or npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

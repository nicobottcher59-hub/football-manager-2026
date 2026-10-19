"""TS-24.2 incremental package integrity verification (stdlib only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_2_MANIFEST.json'
BASE = ROOT / 'TS_24_1_MANIFEST.json'


def main() -> int:
    if not BASE.is_file():
        print('ERROR: TS-24.1 base missing. Install TS-24.1 before TS-24.2.')
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if data['base'] != 'TS-24.1' or data['save_graph_version'] != 13:
            raise ValueError('invalid TS-24.2 release metadata')
        hashes = data['sha256']
        if not isinstance(hashes, dict) or not hashes or data['files'] != len(hashes):
            raise ValueError('invalid package file count')
    except (OSError, KeyError, ValueError, TypeError) as exc:
        print(f'ERROR: invalid or missing TS-24.2 manifest: {exc}')
        return 1
    bad = []
    for rel, expected in hashes.items():
        path = (ROOT / rel).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            bad.append(f'{rel}: missing/unsafe file')
        elif not isinstance(expected, str) or len(expected) != 64:
            bad.append(f'{rel}: invalid hash')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            bad.append(f'{rel}: SHA-256 mismatch')
    if bad:
        print('FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-24.2 integrity OK: {len(hashes)} files, SHA-256 verified.')
    print('No Node or npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

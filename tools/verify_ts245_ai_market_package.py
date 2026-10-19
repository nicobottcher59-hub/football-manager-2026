"""Verify TS-24.5 incremental files (stdlib, no npm)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_5_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_4_MANIFEST.json').is_file():
        print('ERROR: install TS-24.4 first (base manifest missing).')
        return 1
    try:
        payload = json.loads(MANIFEST.read_text(encoding='utf-8'))
        checksums = payload['sha256']
        if not isinstance(checksums, dict) or not checksums:
            raise ValueError('empty manifest')
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: TS-24.5 manifest missing or invalid: {exc}')
        return 1
    bad = []
    for path, expected in checksums.items():
        target = (ROOT / path).resolve()
        if ROOT.resolve() not in target.parents or not target.is_file():
            bad.append(f'{path}: missing or invalid path')
        elif sha256(target.read_bytes()).hexdigest() != expected:
            bad.append(f'{path}: SHA-256 mismatch')
    if bad:
        print('TS-24.5 package FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-24.5 package OK: {len(checksums)} files; SHA-256 verified.')
    print('No Node or npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

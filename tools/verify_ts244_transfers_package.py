"""TS-24.4 incremental package verification (standard library only)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_4_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_3_1_MANIFEST.json').is_file():
        print('ERROR: TS-24.3.1 base is not installed.')
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: missing or invalid TS-24.4 manifest: {exc}')
        return 1
    bad = []
    for name, expected in data['sha256'].items():
        target=(ROOT/name).resolve()
        if ROOT.resolve() not in target.parents or not target.is_file():
            bad.append(f'{name}: missing or invalid path')
        elif sha256(target.read_bytes()).hexdigest()!=expected:
            bad.append(f'{name}: SHA-256 does not match')
    if bad:
        print('TS-24.4 package FAILED:', *bad, sep='\n - ')
        return 1
    print(f'TS-24.4 package OK: {len(data["sha256"])} files checked; SHA-256 verified.')
    print('No Node or npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

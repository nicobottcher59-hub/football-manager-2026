"""Verify TS-24.6 incremental files and SHA-256 digests. Stdlib only."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_6_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_5_MANIFEST.json').is_file():
        print('ERROR: TS-24.5 must be installed before TS-24.6.')
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: TS-24.6 manifest unavailable: {exc}')
        return 1
    failures = []
    for name, digest in data['sha256'].items():
        target = (ROOT / name).resolve()
        if ROOT.resolve() not in target.parents or not target.is_file():
            failures.append(name + ': absent or invalid path')
        elif sha256(target.read_bytes()).hexdigest() != digest:
            failures.append(name + ': SHA-256 differs')
    if failures:
        print('TS-24.6 verification FAILED:', *failures, sep='\n - ')
        return 1
    print(f'TS-24.6 package OK: {len(data["sha256"])} files verified (SHA-256).')
    print('Save format v16; Node/npm not required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

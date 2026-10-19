"""Check the TS-24.7 incremental package against SHA-256 hashes (stdlib)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_7_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_6_MANIFEST.json').is_file():
        print('ERROR: Install TS-24.6 before applying TS-24.7.')
        return 1
    try:
        document = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if document.get('base') != 'TS-24.6' or document.get('save_graph_version') != 16:
            raise ValueError('unexpected package metadata')
        files = document['sha256']
        if not isinstance(files, dict) or not files:
            raise ValueError('empty hash manifest')
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f'ERROR: Cannot read TS-24.7 manifest: {err}')
        return 1
    errors = []
    for name, expected in files.items():
        path = (ROOT / name).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            errors.append(f'{name}: missing/unsafe filename')
        elif sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'{name}: SHA-256 mismatch')
    if errors:
        print('TS-24.7 integrity check FAILED:', *errors, sep='\n  - ')
        return 1
    print(f'TS-24.7 verified: {len(files)} files (SHA-256); v16 save schema unchanged.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

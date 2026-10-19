"""Verify TS-25.2 incremental files from the installed game root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'TS_25_2_MANIFEST.json').read_text('utf-8'))
    if manifest.get('version') != 'TS-25.2':
        raise ValueError('Wrong TS-25.2 manifest')
    signatures = manifest['sha256']
    if len(signatures) < 9:
        raise ValueError('Incomplete TS-25.2 manifest')
    issues = []
    for relative, expected in sorted(signatures.items()):
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            issues.append(f'Missing/unsafe path: {relative}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            issues.append(f'Hash mismatch: {relative}')
    if issues:
        print('TS-25.2 package FAILED:')
        print('\n'.join(issues))
        return 1
    print(f'TS-25.2 package OK: {len(signatures)} files verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

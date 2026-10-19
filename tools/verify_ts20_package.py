"""Verify installed TS-20 payload hashes. Standard library only; no Node needed."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = root / 'TS_20_MANIFEST.json'
    try:
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        if payload.get('release') != 'TS-20 Player DNA & Dressing Room':
            raise ValueError('Unexpected release identifier')
        entries = payload['files']
        if not isinstance(entries, list) or not entries:
            raise ValueError('Empty or malformed file list')
        errors = []
        seen = set()
        for item in entries:
            name = item['path']
            file = (root / name).resolve()
            if file == root or root not in file.parents or name in seen:
                raise ValueError(f'Unsafe or repeated file entry: {name}')
            seen.add(name)
            if not file.is_file():
                errors.append(f'MISSING {name}')
                continue
            raw = file.read_bytes()
            if len(raw) != item['bytes'] or sha256(raw).hexdigest() != item['sha256']:
                errors.append(f'CHANGED {name}')
        if errors:
            print('\n'.join(errors), file=sys.stderr)
            print(f'FAILED: {len(errors)} file(s) differ from the TS-20 payload.', file=sys.stderr)
            return 1
        print(f'OK: {len(entries)} TS-20 payload files match their SHA-256 hashes.')
        print('This verifies installed files, not saved games or software correctness.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Cannot verify TS-20: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

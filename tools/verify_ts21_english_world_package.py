"""Verify the installed TS-21.1 incremental package using only Python stdlib."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='Project root (default: parent of this tools folder)')
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = root / 'TS_21_1_ENGLISH_WORLD_MANIFEST.json'
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if data.get('package') != 'TS-21.1-English-World' or data.get('manifest_version') != 1:
            raise ValueError('unsupported package manifest')
        problems = []
        seen = set()
        for entry in data['files']:
            name = entry['path']
            path = (root / name).resolve()
            if name in seen or not path.is_relative_to(root):
                raise ValueError('invalid or duplicate manifest path')
            seen.add(name)
            if not path.is_file():
                problems.append(f'MISSING: {name}')
                continue
            contents = path.read_bytes()
            if len(contents) != entry['bytes'] or hashlib.sha256(contents).hexdigest() != entry['sha256']:
                problems.append(f'MODIFIED: {name}')
        if problems:
            print('\n'.join(problems), file=sys.stderr)
            print('Package verification FAILED. Extract over the correct project root.', file=sys.stderr)
            return 1
        print(f'PASS: {len(seen)} installed files verified with SHA-256. No Node/npm required.')
        print('This checks package integrity, not football simulation behavior.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Package verification FAILED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

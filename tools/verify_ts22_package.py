"""Verify the TS-22 incremental installation. Python standard library only.

Checks exact installed bytes, not sporting correctness or personal save slots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

MANIFEST = 'TS_22_MANIFEST.json'
PACKAGE = 'TS-22-Squad-Match-Presentation'


def verify(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    data = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    if data.get('package') != PACKAGE or data.get('manifest_version') != 1:
        raise ValueError('unsupported package manifest')
    entries = data['files']
    if not isinstance(entries, list) or not entries or data.get('file_count') != len(entries) + 1:
        raise ValueError('invalid manifest file count')
    seen, problems = set(), []
    for entry in entries:
        name = entry['path']
        if not isinstance(name, str) or not name or '\\' in name or ':' in name:
            raise ValueError('invalid manifest path')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or name == MANIFEST or name in seen:
            raise ValueError('invalid or duplicate manifest path')
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('manifest path escapes project root')
        seen.add(name)
        expected = entry['sha256']
        if (not isinstance(expected, str) or len(expected) != 64
                or any(c not in '0123456789abcdef' for c in expected)
                or type(entry['bytes']) is not int or entry['bytes'] < 0):
            raise ValueError('invalid digest or file size')
        if not path.is_file():
            problems.append(f'MISSING: {name}')
            continue
        content = path.read_bytes()
        if len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != expected:
            problems.append(f'MODIFIED: {name}')
    for name, expected in data.get('base_dependencies', {}).items():
        relative = PurePosixPath(name)
        path = (root / name).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root):
            raise ValueError('invalid base dependency path')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(f'BASE DEPENDENCY: {name}; install TS-21.1.1 first')
    return len(seen), problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='Project root; defaults to the parent of tools/')
    args = parser.parse_args()
    try:
        count, problems = verify(args.root)
        if problems:
            print('\n'.join(problems), file=sys.stderr)
            print('FAIL: re-extract TS-22 over TS-21.1.1; keep your save backup.', file=sys.stderr)
            return 1
        print(f'PASS: {count} payload files verified with SHA-256; {count + 1} files including manifest.')
        print('Python only. This verifies package integrity, not simulation behavior.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

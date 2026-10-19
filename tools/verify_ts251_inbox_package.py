"""Verify exactly the TS-25.1 patch files after copying them to project root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'TS_25_1_MANIFEST.json').read_text('utf-8'))
    assert manifest['version'] == 'TS-25.1'
    files = manifest['sha256']
    assert isinstance(files, dict) and len(files) >= 25
    failures = []
    for name, expected in sorted(files.items()):
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(f'missing or unsafe path: {name}')
            continue
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != expected:
            failures.append(f'file changed: {name}')
    if failures:
        print('TS-25.1 verification FAILED:')
        print('\n'.join(failures))
        return 1
    print(f'TS-25.1 verification OK: {len(files)} files match the SHA-256 manifest')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

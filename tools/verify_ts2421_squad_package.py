"""Verify the installed TS-24.2.1 Squad hotfix files (stdlib only)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_2_1_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_2_MANIFEST.json').is_file():
        print('ERROR: TS-24.2 is required before installing TS-24.2.1.')
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'ERROR: TS-24.2.1 manifest missing or unreadable: {exc}')
        return 1
    errors = []
    for relpath, digest in manifest['sha256'].items():
        path = (ROOT / relpath).resolve()
        if ROOT.resolve() not in path.parents:
            errors.append(f'{relpath}: unsafe path')
        elif not path.is_file():
            errors.append(f'{relpath}: missing')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f'{relpath}: SHA-256 mismatch')
    if errors:
        print('TS-24.2.1 verification FAILED:', *errors, sep='\n- ')
        return 1
    print(f'TS-24.2.1 OK: {len(manifest["sha256"])} files, SHA-256 verified.')
    print('No Node/npm required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

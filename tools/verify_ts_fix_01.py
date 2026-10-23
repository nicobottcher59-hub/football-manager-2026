"""Verify the installed TS-FIX-01 patch files without changing any save."""
from pathlib import Path
import hashlib
import json
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = root / 'TS_FIX_01_PATCH_MANIFEST.json'
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        failures = []
        for item in data['files']:
            path = root / item['path']
            if not path.is_file():
                failures.append(f"MISSING: {item['path']}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                failures.append(f"CHANGED: {item['path']}")
        if failures:
            print('\n'.join(failures))
            print('Verification failed. Reapply the patch or review local edits.')
            return 1
        print(f"TS-FIX-01 verified: {len(data['files'])} payload files match the manifest.")
        print('Saves were not opened or modified.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Cannot verify patch: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

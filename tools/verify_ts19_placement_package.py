"""Verify the installed TS-19 placement / heatmap files without extra dependencies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    root=Path(__file__).resolve().parents[1]
    manifest=root/'TS_19_PLACEMENT_HEATMAP_MANIFEST.json'
    try:
        records=json.loads(manifest.read_text(encoding='utf-8'))['files']
        errors=[]
        for record in records:
            path=(root/record['path']).resolve()
            if not path.is_relative_to(root):
                errors.append('Invalid path in manifest')
            elif not path.is_file():
                errors.append('Missing: '+record['path'])
            elif hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
                errors.append('Modified: '+record['path'])
        if errors:
            print('\n'.join(errors));return 1
        print(f'TS-19 placement / heatmap: {len(records)} files verified (SHA-256).')
        return 0
    except (OSError,KeyError,ValueError,TypeError) as exc:
        print(f'Cannot verify TS-19 package: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())

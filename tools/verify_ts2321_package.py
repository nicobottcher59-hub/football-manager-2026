"""Verify installed TS-23.2.1 hotfix SHA-256 checksums (stdlib only)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'TS_23_2_1_MANIFEST.json'


def main()->int:
    if not (ROOT/'TS_23_2_MANIFEST.json').is_file():
        print('ERROR: TS-23.2 base not detected. Install TS-23.2 first.')
        return 1
    try:
        data=json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:
        print(f'ERROR: missing/invalid manifest: {exc}')
        return 1
    problems=[]
    for name,expected in data['sha256'].items():
        path=(ROOT/name).resolve()
        if ROOT.resolve() not in path.parents:
            problems.append(f'{name}: invalid path')
        elif not path.is_file():
            problems.append(f'{name}: missing')
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            problems.append(f'{name}: SHA-256 mismatch')
    if problems:
        for problem in problems:
            print('ERROR:',problem)
        return 1
    print(f'TS-23.2.1 package OK: {len(data["sha256"])} files verified; no Node/npm required.')
    return 0


if __name__=='__main__':
    sys.exit(main())

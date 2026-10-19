"""Validate the installed TS-24.3 incremental patch; Python stdlib only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_24_3_MANIFEST.json'


def main() -> int:
    if not (ROOT / 'TS_24_2_1_MANIFEST.json').is_file():
        print('ERROR: TS-24.2.1 is required before TS-24.3.')
        return 1
    try:
        data=json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:
        print(f'ERROR: missing/invalid TS-24.3 manifest: {exc}')
        return 1
    bad=[]
    for name, expected in data['sha256'].items():
        target=(ROOT/name).resolve()
        if ROOT.resolve() not in target.parents:
            bad.append(name+': path escapes project root')
        elif not target.is_file():
            bad.append(name+': missing')
        elif hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
            bad.append(name+': SHA-256 mismatch')
    if bad:
        print('TS-24.3 verification FAILED:',*bad,sep='\n - ')
        return 1
    print(f'TS-24.3 OK: {len(data["sha256"])} files verified via SHA-256.')
    print('No Node or npm required to play.')
    return 0


if __name__=='__main__':
    sys.exit(main())

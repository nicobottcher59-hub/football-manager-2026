"""Verify files copied from the TS-19 package; this command changes no files."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'TS_19_TACTICAL_STUDIO_MANIFEST.json'

def main() -> int:
    try:
        manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
        entries=manifest['files']
        if not isinstance(entries,list) or not entries:
            raise ValueError('manifest file list is missing')
    except (OSError,ValueError,KeyError) as exc:
        print(f'Cannot read TS-19 manifest: {exc}',file=sys.stderr)
        return 2
    failures=[]
    for entry in entries:
        relative=entry.get('path','')
        path=(ROOT/relative).resolve()
        if not relative or not path.is_relative_to(ROOT):
            failures.append(f'Invalid package path: {relative}')
            continue
        try:
            content=path.read_bytes()
        except OSError:
            failures.append(f'Missing: {relative}')
            continue
        if len(content)!=entry['size'] or hashlib.sha256(content).hexdigest()!=entry['sha256']:
            failures.append(f'Different content: {relative}')
    if failures:
        print('\n'.join(failures),file=sys.stderr)
        print('Files were not changed by this verifier.',file=sys.stderr)
        return 1
    print(f'{len(entries)} package files verified. SHA-256 matches.')
    return 0

if __name__=='__main__':raise SystemExit(main())

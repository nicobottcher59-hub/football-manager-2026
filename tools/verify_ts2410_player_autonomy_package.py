"""Validate TS-24.10 incremental extraction on TS-24.9 (SHA-256)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'TS_24_10_MANIFEST.json'

def main():
    meta=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if meta.get('version')!='TS-24.10' or meta.get('base')!='TS-24.9':
        raise SystemExit('Incorrect TS-24.10 package manifest')
    failures=[]
    for rel, expected in sorted(meta['sha256'].items()):
        dest=ROOT/rel
        if not dest.is_file():
            failures.append(f'MISSING {rel}')
        elif hashlib.sha256(dest.read_bytes()).hexdigest()!=expected:
            failures.append(f'SHA MISMATCH {rel}')
    if failures:
        raise SystemExit('\n'.join(failures))
    if not (ROOT/'INICIAR_INTERFAZ_WINDOWS.bat').exists():
        raise SystemExit('Expected Windows launcher at the project root')
    print('TS-24.10: OK,',len(meta['sha256']),'SHA-256 files verified, SQLite schema remains v16')

if __name__=='__main__':
    main()

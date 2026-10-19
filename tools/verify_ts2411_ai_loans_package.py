"""Verify TS-24.11 incremental patch integrity on TS-24.10 (SHA-256)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'TS_24_11_MANIFEST.json'

def main():
    meta=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if meta.get('version')!='TS-24.11' or meta.get('base')!='TS-24.10' or meta.get('save_graph_version')!=16:
        raise SystemExit('Incorrect TS-24.11 patch manifest')
    errors=[]
    for rel,digest in sorted(meta['sha256'].items()):
        path=ROOT/rel
        if not path.is_file():
            errors.append('MISSING '+rel)
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            errors.append('SHA MISMATCH '+rel)
    if errors:
        raise SystemExit('\n'.join(errors))
    if not (ROOT/'INICIAR_INTERFAZ_WINDOWS.bat').exists():
        raise SystemExit('Launcher absent at project root')
    print('TS-24.11: OK;',len(meta['sha256']),'files match SHA-256; SQLite v16')

if __name__=='__main__':main()

"""TS-24.12 immutable manifest integrity and base layout verification."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    meta=json.loads((ROOT/'TS_24_12_MANIFEST.json').read_text(encoding='utf-8'))
    if meta.get('version')!='TS-24.12' or meta.get('base')!='TS-24.11' or meta.get('save_graph_version')!=16:
        raise SystemExit('TS-24.12 patch manifest or base version invalid')
    if meta.get('files') != len(meta.get('sha256',{})):
        raise SystemExit('TS-24.12 manifest entry count mismatch')
    if not (ROOT/'INICIAR_INTERFAZ_WINDOWS.bat').is_file():
        raise SystemExit('Cannot locate project root / Windows launcher')
    errors=[]
    for rel,expected in sorted(meta['sha256'].items()):
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            errors.append('Missing/unsafe path: '+rel)
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            errors.append('SHA-256 mismatch: '+rel)
    if errors: raise SystemExit('\n'.join(errors))
    print(f"TS-24.12: OK; {len(meta['sha256'])} files match SHA-256; SQLite v16 unchanged")

if __name__=='__main__':main()

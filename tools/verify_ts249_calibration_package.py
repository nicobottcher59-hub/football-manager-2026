"""TS-24.9 incremental update verifier: SHA-256 of each included file."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]

def verify(root:Path=ROOT)->int:
    m=json.loads((root/'TS_24_9_MANIFEST.json').read_text(encoding='utf-8'))
    if m.get('version')!='TS-24.9' or m.get('base')!='TS-24.8' or m.get('save_graph_version')!=16:
        raise ValueError('wrong version, base or SQLite save schema')
    entries=m['sha256']
    if not entries or len(entries)!=m['files']:
        raise ValueError('manifest file count mismatch')
    for relative,digest in sorted(entries.items()):
        candidate=(root/relative).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
            raise ValueError('invalid file name or missing asset: '+relative)
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=digest:
            raise ValueError('SHA-256 mismatch: '+relative)
    print(f'TS-24.9 OK: {len(entries)} checked files, base TS-24.8, SQLite v16')
    return len(entries)

if __name__=='__main__': verify()

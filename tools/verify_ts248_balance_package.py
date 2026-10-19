"""Verify the TS-24.8 incremental package after applying to an existing tree."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'TS_24_8_MANIFEST.json'


def verify(root: Path = ROOT) -> int:
    manifest_path=root/'TS_24_8_MANIFEST.json'
    payload=json.loads(manifest_path.read_text(encoding='utf-8'))
    if payload.get('base')!='TS-24.7' or payload.get('save_graph_version')!=16:
        raise ValueError('unexpected base or save format')
    entries=payload['sha256']
    if len(entries)!=payload['files'] or not entries:
        raise ValueError('manifest file count mismatch')
    for relative,expected in sorted(entries.items()):
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f'missing or invalid patch file: {relative}')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=expected:
            raise ValueError(f'SHA-256 mismatch: {relative}')
    print(f'TS-24.8 OK: {len(entries)} SHA-256 files, base TS-24.7, save v16')
    return len(entries)


if __name__=='__main__':
    verify()

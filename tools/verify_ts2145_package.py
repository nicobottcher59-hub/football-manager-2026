"""Verify installed TS-21.4/21.5 files with SHA-256, using stdlib only."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'TS_21_4_5_MANIFEST.json'


def verify_files(root: Path, manifest: dict) -> int:
    items = manifest.get('files', {})
    if not isinstance(items, dict) or not items:
        raise ValueError('empty package manifest')
    wrong = []
    for name, expected in items.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or not isinstance(expected, str) or len(expected)!=64:
            raise ValueError(f'invalid manifest entry: {name}')
        path = root / rel
        if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=expected:
            wrong.append(name)
    if wrong:
        raise RuntimeError('Missing or modified files: ' + ', '.join(wrong))
    return len(items)


def verify_archive(archive: Path, manifest: dict) -> None:
    with ZipFile(archive) as file:
        assert file.testzip() is None, 'invalid archive CRC'
        names = set(file.namelist())
        expected=set(manifest['files']) | {MANIFEST}
        if names != expected:
            raise ValueError('ZIP entries differ from manifest')
        for name, digest in manifest['files'].items():
            if sha256(file.read(name)).hexdigest()!=digest:
                raise ValueError('ZIP hash mismatch: '+name)
        if file.read(MANIFEST)!=json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True).encode()+b'\n':
            raise ValueError('ZIP manifest mismatch')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',dest='zip_path',type=Path,help='optionally verify the ZIP too')
    args=parser.parse_args()
    if not (ROOT/'src/football_manager/domain/player_aging.py').is_file():
        raise RuntimeError('TS-21.3 base not present')
    manifest=json.loads((ROOT/MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('base')!='TS-21.3' or manifest.get('target_save_version')!=9:
        raise ValueError('unexpected incremental package version')
    number=verify_files(ROOT,manifest)
    if args.zip_path:
        verify_archive(args.zip_path,manifest)
    print(f'TS-21.4/21.5: {number} files SHA-256 OK; save version 9; no Node required.')

if __name__=='__main__':main()

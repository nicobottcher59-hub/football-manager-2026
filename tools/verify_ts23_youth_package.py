"""Verify the installed TS-23 patch against its SHA-256 manifest (stdlib only)."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'TS_23_MANIFEST.json'


def verify_files(root: Path, manifest: dict) -> int:
    checks=manifest.get('files',{})
    if manifest.get('base')!='TS-21.4/21.5' or manifest.get('target_save_version')!=10:
        raise ValueError('unexpected patch version')
    if not isinstance(checks,dict) or not checks:
        raise ValueError('empty manifest')
    wrong=[]
    for name,digest in checks.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or not isinstance(digest,str) or len(digest)!=64:
            raise ValueError(f'invalid manifest path or hash: {name}')
        candidate=root / rel
        if not candidate.is_file() or sha256(candidate.read_bytes()).hexdigest()!=digest:
            wrong.append(name)
    if wrong:
        raise RuntimeError('Missing or altered files: '+', '.join(wrong))
    return len(checks)


def verify_archive(path: Path, manifest: dict) -> None:
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('CRC error')
        expected=set(manifest['files'])|{MANIFEST}
        if set(archive.namelist())!=expected:
            raise ValueError('ZIP entries do not match manifest')
        for name,digest in manifest['files'].items():
            if sha256(archive.read(name)).hexdigest()!=digest:
                raise ValueError('ZIP hash mismatch: '+name)
        expected_bytes=(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8')
        if archive.read(MANIFEST)!=expected_bytes:
            raise ValueError('ZIP manifest mismatch')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',dest='zip_path',type=Path)
    args=parser.parse_args()
    if not (ROOT/'src/football_manager/services/youth_academy.py').is_file():
        raise ValueError('TS-23 files are absent')
    manifest=json.loads((ROOT/MANIFEST).read_text(encoding='utf-8'))
    n=verify_files(ROOT,manifest)
    if args.zip_path:
        verify_archive(args.zip_path,manifest)
    print(f'TS-23: {n} files SHA-256 OK; save version 10; Python only (no Node).')

if __name__=='__main__':main()

"""Verify the installed TS-UI-08.04 files against its included SHA-256 manifest."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'TS_UI_08_04_PATCH_MANIFEST.json'


def verify() -> None:
    meta = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if meta.get('patch') != 'TS-UI-08.04':
        raise SystemExit('Incorrect patch manifest')
    failures=[]
    for item in meta['files']:
        rel=Path(item['path'])
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            failures.append(f"MISSING {rel}")
            continue
        checksum=sha256(path.read_bytes()).hexdigest()
        if checksum!=item['sha256']:
            failures.append(f"CHANGED {rel}")
    if failures:
        raise SystemExit('TS-UI-08.04 verification failed:\n'+'\n'.join(failures))
    print(f"TS-UI-08.04: {len(meta['files'])} files match the manifest.")


if __name__ == '__main__':
    verify()

"""Verify a TS-24.13 incremental install by its manifest hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    meta = json.loads((ROOT / 'TS_24_13_MANIFEST.json').read_text(encoding='utf-8'))
    if (meta.get('version') != 'TS-24.13' or meta.get('base') != 'TS-24.12'
            or meta.get('save_graph_version') != 16):
        raise SystemExit('Wrong patch base or incompatible save version')
    files = meta.get('sha256', {})
    if meta.get('files') != len(files) or not files:
        raise SystemExit('Manifest count does not match listed files')
    if not (ROOT / 'INICIAR_INTERFAZ_WINDOWS.bat').is_file():
        raise SystemExit('Incorrect project root: launcher not found')
    errors = []
    for rel, digest in sorted(files.items()):
        target = (ROOT / rel).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            errors.append('Missing/unsafe path: ' + rel)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            errors.append('SHA-256 mismatch: ' + rel)
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'TS-24.13: OK ({len(files)} hashed files, SQLite v16 preserved)')


if __name__ == '__main__':
    main()

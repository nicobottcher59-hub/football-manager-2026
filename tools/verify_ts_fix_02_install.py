"""Verify the installed TS-FIX-02 files without changing any project/save file.

Run after extracting the incremental ZIP:
    python tools/verify_ts_fix_02_install.py
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / 'TS_FIX_02_PATCH_MANIFEST.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        entries = manifest['files']
        if not isinstance(entries, list):
            raise ValueError('Invalid manifest file list')
    except (OSError, ValueError, KeyError) as exc:
        print(f'Cannot read TS-FIX-02 manifest: {exc}')
        return 2
    failures = []
    for entry in entries:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            failures.append(f'Unsafe manifest entry: {relative}')
            continue
        path = root / relative
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            failures.append(f'Missing/unreadable: {relative}')
            continue
        if digest != entry['sha256']:
            failures.append(f'Different contents: {relative}')
    if failures:
        print('\n'.join(failures))
        print('A difference may be a later local edit; this verifier never overwrites it.')
        return 1
    print(f'PASS: {len(entries)} TS-FIX-02 payload files match the packaged SHA-256 manifest.')
    print('This verifies installed files, not your actual saved career or browser cache.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

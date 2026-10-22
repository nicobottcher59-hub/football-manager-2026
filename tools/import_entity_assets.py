#!/usr/bin/env python3
"""Build the global visual manifest from stable world IDs, without editing game data.

Layout (only IDs, never display names):
    source/players/PLAYER_ID.png
    source/clubs/CLUB_ID/crest.png
    source/clubs/CLUB_ID/home.png
    source/clubs/CLUB_ID/away.png
    source/clubs/CLUB_ID/goalkeeper.png
    source/clubs/CLUB_ID/hero.jpg
    source/clubs/CLUB_ID/medical.jpg
    source/competitions/COMPETITION_ID.png

Optional metadata JSON: {"clubs":{"ID":{"display_name":"...", "primary_color":"#RRGGBB"}}}
An absent photo remains a deterministic illustrated portrait, not another player's photo.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
RGB = re.compile(r"#[0-9a-fA-F]{6}\Z")
TYPES = {'.png', '.jpg', '.jpeg', '.webp'}
CLUB_TYPES = {
    'crest': 'crest', 'home': 'kit_image', 'away': 'away_kit_image',
    'goalkeeper': 'goalkeeper_kit_image', 'hero': 'hero_image',
    'medical': 'medical_image',
}


def valid_id(value: str) -> bool:
    return bool(ID.fullmatch(value)) and value not in {'..', '.', '__proto__', 'constructor', 'prototype'}


def validate_image(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 12 * 1024 * 1024:
        raise ValueError(f'Unsafe / oversized image: {path}')
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()
    except ImportError:
        # Basic magic-byte validation without third-party requirements.
        with path.open('rb') as f:
            header = f.read(16)
        formats = {'.png': header.startswith(b'\x89PNG\r\n\x1a\n'),
                   '.jpeg': header.startswith(b'\xff\xd8\xff'),
                   '.jpg': header.startswith(b'\xff\xd8\xff'),
                   '.webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP'}
        if not formats.get(path.suffix.lower()):
            raise ValueError(f'Not a valid image: {path}')
    except Exception as exc:
        raise ValueError(f'Invalid image {path}: {exc}') from exc


def import_assets(source: Path, destination: Path, metadata_path: Path | None = None,
                  dry_run: bool = False) -> dict:
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError('Source must be a directory')
    metadata = json.loads(metadata_path.read_text(encoding='utf8')) if metadata_path else {}
    if not isinstance(metadata, dict) or not isinstance(metadata.get('clubs', {}), dict):
        raise ValueError('Invalid club metadata')
    manifest = {'schema_version': 1, 'clubs': {}, 'players': {}, 'competitions': {}}

    def put(file: Path, key: str, name: str) -> str:
        if not valid_id(key) or file.suffix.lower() not in TYPES:
            raise ValueError(f'Unsupported ID or extension: {file}')
        validate_image(file)
        # ID and destination are both allowlisted. Never write outside /assets.
        relative = Path('assets/imported') / name / f'{key}{file.suffix.lower()}'
        target = destination / relative
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)
        return relative.as_posix()

    for file in sorted((source / 'players').glob('*')) if (source / 'players').is_dir() else ():
        if file.is_file() and file.suffix.lower() in TYPES:
            manifest['players'][file.stem] = {'photo': put(file, file.stem, 'players')}
    for file in sorted((source / 'competitions').glob('*')) if (source / 'competitions').is_dir() else ():
        if file.is_file() and file.suffix.lower() in TYPES:
            manifest['competitions'][file.stem] = {'logo': put(file, file.stem, 'competitions')}
    for club_dir in sorted((source / 'clubs').iterdir()) if (source / 'clubs').is_dir() else ():
        if not club_dir.is_dir() or club_dir.is_symlink():
            continue
        if not valid_id(club_dir.name):
            raise ValueError(f'Invalid club ID: {club_dir.name}')
        identity = manifest['clubs'].setdefault(club_dir.name, {})
        for file in sorted(club_dir.iterdir()):
            if file.suffix.lower() not in TYPES:
                continue
            field = CLUB_TYPES.get(file.stem)
            if not field:
                continue
            # Avoid collisions between home.jpg and home.png, etc.
            if field in identity:
                raise ValueError(f'Ambiguous {field} for {club_dir.name}')
            identity[field] = put(file, club_dir.name + '-' + file.stem, 'clubs')

    for cid, record in metadata.get('clubs', {}).items():
        if not valid_id(cid) or not isinstance(record, dict):
            raise ValueError(f'Invalid club identity: {cid}')
        fields = manifest['clubs'].setdefault(cid, {})
        for name in ('display_name', 'short_name'):
            value = record.get(name)
            if isinstance(value, str) and 0 < len(value) <= 160:
                fields[name] = value
        for name in ('primary_color', 'secondary_color', 'accent_color'):
            value = record.get(name)
            if isinstance(value, str) and RGB.fullmatch(value):
                fields[name] = value.lower()
    if not dry_run:
        output = destination / 'data/entity-assets.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, required=True, help='Directory with ID-named players/clubs/competitions')
    parser.add_argument('--destination', type=Path, default=Path(__file__).resolve().parents[1] / 'frontend/portable')
    parser.add_argument('--metadata', type=Path, help='Optional JSON of club names and colours keyed by club_id')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    result = import_assets(args.source, args.destination, args.metadata, args.dry_run)
    print('Validated assets:', ', '.join(f'{kind}={len(result[kind])}' for kind in ('clubs','players','competitions')))
    if args.dry_run:
        print('Dry run: no files written')
    else:
        print('Manifest:', args.destination / 'data/entity-assets.json')


if __name__ == '__main__':
    main()

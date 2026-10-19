"""Locate the *existing* portable UI without coupling the server to its source tree.

Editable checkout: use the repository frontend. A packaged wheel can include
an identical copy of the portable/public assets generated during packaging.
FM_FRONTEND_DIR may point to an external asset root, useful to local installers.
The HTTP adapter always checks containment to block path traversal.
"""
from __future__ import annotations

import os
from pathlib import Path


_SOURCE_FRONTEND = Path(__file__).resolve().parents[3] / 'frontend'
_PACKAGED_FRONTEND = Path(__file__).resolve().parent / 'web_assets'


def find_frontend_root(frontend_root: Path | None = None) -> Path:
    if frontend_root is not None:
        candidates = [Path(frontend_root)]
    elif os.environ.get('FM_FRONTEND_DIR'):
        candidates = [Path(os.environ['FM_FRONTEND_DIR']).expanduser()]
    else:
        candidates = [_SOURCE_FRONTEND, _PACKAGED_FRONTEND]
    for candidate in candidates:
        path = candidate.resolve()
        if (path / 'portable' / 'index.html').is_file() and \
                (path / 'public' / 'squad' / 'embed.html').is_file():
            return path
    raise FileNotFoundError('Frontend files not found; provide FM_FRONTEND_DIR or install assets')


def resolve_static_asset(path: str, frontend_root: Path) -> Path | None:
    if path == '/portable/':
        path = '/portable/index.html'
    if path.startswith('/portable/'):
        root, subpath = frontend_root / 'portable', path[len('/portable/'):]
    elif path.startswith('/public/squad/'):
        root, subpath = frontend_root / 'public' / 'squad', path[len('/public/squad/'):]
    elif path.startswith('/squad/'):
        root, subpath = frontend_root / 'public' / 'squad', path[len('/squad/'):]
    else:
        return None
    try:
        root = root.resolve()
        file = (root / subpath).resolve()
        if file.is_relative_to(root) and file.is_file():
            return file
    except (ValueError, OSError):
        pass
    return None

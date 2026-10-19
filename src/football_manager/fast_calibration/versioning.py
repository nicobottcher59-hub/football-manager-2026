from __future__ import annotations

import subprocess
from pathlib import Path


def _read_git_head(root: Path) -> str | None:
    git_dir = root / ".git"
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    value = head.read_text(encoding="utf-8").strip()
    if not value:
        return None
    if not value.startswith("ref: "):
        return value[:12]
    ref_name = value[5:].strip()
    ref_path = git_dir / ref_name
    if ref_path.is_file():
        return ref_path.read_text(encoding="utf-8").strip()[:12]
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            commit, _, name = line.partition(" ")
            if name == ref_name:
                return commit[:12]
    return None


def git_metadata(root: str | Path) -> tuple[str, bool]:
    path = Path(root)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit or "unknown", dirty
    except (OSError, subprocess.CalledProcessError):
        return _read_git_head(path) or "unknown", True

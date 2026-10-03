"""Normalize Google Photos zip layouts into /data/shared/<AlbumTitle>/."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

_SKIP_NAMES = {".DS_Store", "Thumbs.db", "__MACOSX"}


def discover_content_root(extract_dir: Path) -> Path:
    """If the zip dumped a single album folder, use that folder as the content root."""
    entries = [
        p
        for p in extract_dir.iterdir()
        if p.name not in _SKIP_NAMES and not p.name.startswith(".")
    ]
    files = [p for p in entries if p.is_file()]
    dirs = [p for p in entries if p.is_dir() and p.name != "__MACOSX"]
    if not files and len(dirs) == 1:
        return dirs[0]
    return extract_dir


def merge_into_album(
    source_root: Path,
    dest_dir: Path,
    skip_existing: bool = True,
) -> dict[str, int]:
    """Copy files into dest_dir. Skip same-name files when skip_existing is True."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stats = {"copied": 0, "skipped": 0, "overwritten": 0}
    content_root = discover_content_root(source_root)

    for src in content_root.rglob("*"):
        if not src.is_file():
            continue
        if src.name in _SKIP_NAMES or src.name.startswith("."):
            continue
        rel = src.relative_to(content_root)
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if skip_existing:
                stats["skipped"] += 1
                log.info("Skip existing file: %s", dest)
                continue
            dest.unlink()
            shutil.copy2(src, dest)
            stats["overwritten"] += 1
        else:
            shutil.copy2(src, dest)
            stats["copied"] += 1
    return stats

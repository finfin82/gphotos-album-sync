from __future__ import annotations

import re

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TITLE_SUFFIXES = (
    " – Google Fotos",
    " - Google Fotos",
    " – Google Photos",
    " - Google Photos",
    " – Google Foto",
    " - Google Foto",
)


def album_title_from_page(page_title: str) -> str:
    title = (page_title or "").strip()
    for suffix in _TITLE_SUFFIXES:
        if suffix in title:
            title = title.split(suffix)[0]
            break
    else:
        if " -" in title:
            title = title.split(" -")[0]
    return sanitize_album_name(title)


def sanitize_album_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(" .")
    cleaned = cleaned[:180].strip()
    return cleaned or "untitled-album"

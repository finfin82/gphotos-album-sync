from __future__ import annotations

import fcntl
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

SHARE_URL_RE = re.compile(
    r"^https?://(photos\.app\.goo\.gl/|photos\.google\.com/)",
    re.IGNORECASE,
)


def is_share_url(url: str) -> bool:
    return bool(SHARE_URL_RE.match((url or "").strip()))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AlbumQueue:
    def __init__(self, queue_dir: str | Path) -> None:
        self.dir = Path(queue_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.albums = self.dir / "albums.txt"
        self.done = self.dir / "done.txt"
        self.failed = self.dir / "failed.txt"
        self.lock_path = self.dir / ".queue.lock"
        for path in (self.albums, self.done, self.failed):
            if not path.exists():
                path.touch()

    @contextmanager
    def _lock(self):
        self.lock_path.touch(exist_ok=True)
        with open(self.lock_path, "a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _parse_pending(self, text: str) -> list[str]:
        urls: list[str] = []
        for raw in text.splitlines():
            line = raw.strip().lstrip("\ufeff").replace("\r", "")
            if not line or line.startswith("#"):
                continue
            urls.append(line)
        return urls

    def list_pending(self) -> list[str]:
        with self._lock():
            return self._parse_pending(self.albums.read_text(encoding="utf-8"))

    def enqueue(self, url: str) -> str:
        cleaned = url.strip()
        if not is_share_url(cleaned):
            raise ValueError(
                "Keine gültige Google-Photos-Share-URL "
                "(erwartet photos.app.goo.gl oder photos.google.com)."
            )
        with self._lock():
            pending = self._parse_pending(self.albums.read_text(encoding="utf-8"))
            pending.append(cleaned)
            self.albums.write_text(
                "".join(f"{item}\n" for item in pending), encoding="utf-8"
            )
        log.info("Queued %s", cleaned)
        return cleaned

    def take_next(self) -> str | None:
        with self._lock():
            pending = self._parse_pending(self.albums.read_text(encoding="utf-8"))
            if not pending:
                return None
            url = pending.pop(0)
            self.albums.write_text(
                "".join(f"{item}\n" for item in pending), encoding="utf-8"
            )
            return url

    def mark_done(self, url: str, album_title: str) -> None:
        line = f"{url}  # {album_title}  {utc_now()}\n"
        with self._lock():
            with self.done.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def mark_failed(self, url: str, reason: str) -> None:
        safe_reason = " ".join(reason.split())
        line = f"{url}  # {utc_now()}  {safe_reason}\n"
        with self._lock():
            with self.failed.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def snapshot(self) -> dict:
        with self._lock():
            pending = self._parse_pending(self.albums.read_text(encoding="utf-8"))
            done_lines = [
                line
                for line in self.done.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            failed_lines = [
                line
                for line in self.failed.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return {
            "pending": pending,
            "pending_count": len(pending),
            "done_count": len(done_lines),
            "failed_count": len(failed_lines),
            "done_tail": done_lines[-10:],
            "failed_tail": failed_lines[-10:],
        }

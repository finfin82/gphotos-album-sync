from __future__ import annotations

import logging
import threading
import time

from app.config import Settings
from app.downloader import DownloadError, download_shared_album
from app.queue_store import AlbumQueue

log = logging.getLogger(__name__)


class SyncWorker:
    def __init__(self, settings: Settings, queue: AlbumQueue) -> None:
        self.settings = settings
        self.queue = queue
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.busy = threading.Lock()
        self.last_error: str | None = None
        self.last_result: dict | None = None
        self.current_url: str | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="album-worker", daemon=True)
        self._thread.start()
        log.info("Worker started (poll=%ss)", self.settings.poll_seconds)

    def shutdown(self) -> None:
        self.stop.set()
        self.wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def kick(self) -> None:
        self.wake.set()

    def _loop(self) -> None:
        while not self.stop.is_set():
            url = self.queue.take_next()
            if url:
                self._process(url)
                continue
            self.wake.wait(timeout=self.settings.poll_seconds)
            self.wake.clear()

    def _process(self, url: str) -> None:
        with self.busy:
            self.current_url = url
            started = time.time()
            log.info("Processing %s", url)
            try:
                result = download_shared_album(url, self.settings)
                self.queue.mark_done(url, result.album_title)
                self.last_error = None
                self.last_result = {
                    "url": url,
                    "album_title": result.album_title,
                    "dest_dir": result.dest_dir,
                    "copied": result.copied,
                    "skipped": result.skipped,
                    "overwritten": result.overwritten,
                    "seconds": round(time.time() - started, 1),
                }
                log.info("Done: %s", self.last_result)
            except DownloadError as exc:
                reason = str(exc)
                self.last_error = reason
                self.queue.mark_failed(url, reason)
                log.error("Failed %s: %s", url, reason)
            except Exception as exc:  # noqa: BLE001
                reason = f"Unerwarteter Fehler: {exc}"
                self.last_error = reason
                self.queue.mark_failed(url, reason)
                log.exception("Failed %s", url)
            finally:
                self.current_url = None

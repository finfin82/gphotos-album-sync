import importlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.downloader import SyncResult


def test_health_and_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path / "shared"))
    monkeypatch.setenv("TEMP_DIR", str(tmp_path / "tmp"))
    monkeypatch.setenv("POLL_SECONDS", "120")

    def fake_download(url: str, settings) -> SyncResult:
        dest = Path(settings.output_root) / "TestduAlbum"
        dest.mkdir(parents=True, exist_ok=True)
        return SyncResult(
            url=url,
            album_title="TestduAlbum",
            dest_dir=str(dest),
            copied=1,
            skipped=0,
            overwritten=0,
            zip_name="album.zip",
        )

    import app.worker as worker_mod

    monkeypatch.setattr(worker_mod, "download_shared_album", fake_download)

    import app.main as main

    importlib.reload(main)

    with TestClient(main.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["ok"] is True
        assert body["google_lang"] == "de"
        assert body["output_root"] == str(tmp_path / "shared")

        page = client.get("/")
        assert page.status_code == 200
        assert "gphotos-album-sync" in page.text

        bad = client.post("/sync", json={"url": "https://example.com/nope"})
        assert bad.status_code == 400

        url = "https://photos.app.goo.gl/TestduAlbum123"
        ok = client.post("/sync", json={"url": url})
        assert ok.status_code == 200
        assert ok.json()["status"] == "queued"

        status = {}
        done = False
        for _ in range(80):
            status = client.get("/status").json()
            if any(url in line for line in status["done_tail"]):
                done = True
                break
            time.sleep(0.05)
        assert done, status
        assert status["last_result"]["album_title"] == "TestduAlbum"

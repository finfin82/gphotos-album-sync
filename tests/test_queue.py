from pathlib import Path

from app.queue_store import AlbumQueue


def test_enqueue_take_done_failed(tmp_path: Path):
    q = AlbumQueue(tmp_path)
    url = "https://photos.app.goo.gl/abc123"
    q.enqueue(url)
    q.enqueue("https://photos.google.com/share/xyz")
    assert q.list_pending()[0] == url

    taken = q.take_next()
    assert taken == url
    assert q.list_pending() == ["https://photos.google.com/share/xyz"]

    q.mark_done(url, "Strandtag")
    q.mark_failed("https://photos.app.goo.gl/bad", "timeout waiting for zip")

    done = (tmp_path / "done.txt").read_text(encoding="utf-8")
    failed = (tmp_path / "failed.txt").read_text(encoding="utf-8")
    assert "Strandtag" in done
    assert url in done
    assert "timeout waiting for zip" in failed

    snap = q.snapshot()
    assert snap["pending_count"] == 1
    assert snap["done_count"] == 1
    assert snap["failed_count"] == 1


def test_comments_and_windows_newlines(tmp_path: Path):
    q = AlbumQueue(tmp_path)
    (tmp_path / "albums.txt").write_bytes(
        b"# comment\r\n"
        b"https://photos.app.goo.gl/one\r\n"
        b"\r\n"
        b"https://photos.app.goo.gl/two\r\n"
    )
    assert q.take_next() == "https://photos.app.goo.gl/one"
    assert q.take_next() == "https://photos.app.goo.gl/two"
    assert q.take_next() is None


def test_reject_non_share_url(tmp_path: Path):
    q = AlbumQueue(tmp_path)
    try:
        q.enqueue("https://example.com")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Share-URL" in str(exc)

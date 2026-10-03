import zipfile
from pathlib import Path

from app.normalize import discover_content_root, merge_into_album


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_nested_album_folder_is_unwrapped(tmp_path: Path):
    extract = tmp_path / "extract"
    _write(extract / "GoogleAlbum" / "a.jpg")
    _write(extract / "GoogleAlbum" / "b.jpg")
    assert discover_content_root(extract).name == "GoogleAlbum"

    dest = tmp_path / "shared" / "Strandtag"
    stats = merge_into_album(extract, dest, skip_existing=True)
    assert stats["copied"] == 2
    assert (dest / "a.jpg").exists()
    assert (dest / "b.jpg").exists()
    assert not (dest / "GoogleAlbum").exists()


def test_flat_zip_files_land_in_album_title_folder(tmp_path: Path):
    extract = tmp_path / "extract"
    _write(extract / "a.jpg")
    _write(extract / "b.jpg")
    dest = tmp_path / "shared" / "FlatAlbum"
    stats = merge_into_album(extract, dest)
    assert stats["copied"] == 2
    assert (dest / "a.jpg").read_text() == "x"


def test_skip_existing_same_name(tmp_path: Path):
    extract = tmp_path / "extract"
    dest = tmp_path / "shared" / "Merge"
    _write(dest / "keep.jpg", "old")
    _write(extract / "keep.jpg", "new")
    _write(extract / "fresh.jpg", "fresh")
    stats = merge_into_album(extract, dest, skip_existing=True)
    assert stats["skipped"] == 1
    assert stats["copied"] == 1
    assert (dest / "keep.jpg").read_text() == "old"
    assert (dest / "fresh.jpg").read_text() == "fresh"


def test_overwrite_when_skip_disabled(tmp_path: Path):
    extract = tmp_path / "extract"
    dest = tmp_path / "shared" / "Merge"
    _write(dest / "keep.jpg", "old")
    _write(extract / "keep.jpg", "new")
    stats = merge_into_album(extract, dest, skip_existing=False)
    assert stats["overwritten"] == 1
    assert (dest / "keep.jpg").read_text() == "new"


def test_real_zip_nested_then_merge(tmp_path: Path):
    zip_path = tmp_path / "album.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Urlaub 2024/img1.jpg", "one")
        archive.writestr("Urlaub 2024/img2.jpg", "two")
    extract = tmp_path / "extract"
    extract.mkdir()
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract)
    dest = tmp_path / "shared" / "Urlaub 2024"
    merge_into_album(extract, dest)
    assert sorted(p.name for p in dest.iterdir()) == ["img1.jpg", "img2.jpg"]

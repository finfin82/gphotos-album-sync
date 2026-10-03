from app.labels import labels_for
from app.queue_store import is_share_url
from app.sanitize import album_title_from_page, sanitize_album_name


def test_sanitize_strips_unsafe_chars():
    assert sanitize_album_name('Urlaub: Italien? <2024>') == "Urlaub_ Italien_ _2024_"
    assert sanitize_album_name("  nested/path\\name  ") == "nested_path_name"
    assert sanitize_album_name("...") == "untitled-album"
    assert sanitize_album_name("") == "untitled-album"


def test_title_from_german_and_english_pages():
    assert album_title_from_page("Strandtag - Google Fotos") == "Strandtag"
    assert album_title_from_page("Strandtag – Google Fotos") == "Strandtag"
    assert album_title_from_page("Beach day - Google Photos") == "Beach day"
    assert album_title_from_page("Family - extras - Google Photos") == "Family - extras"


def test_share_url_validation():
    assert is_share_url("https://photos.app.goo.gl/abcDEF123")
    assert is_share_url("https://photos.google.com/share/AF1QipExample")
    assert is_share_url("https://photos.google.com/album/AF1QipExample")
    assert not is_share_url("https://example.com/album")
    assert not is_share_url("not a url")


def test_german_labels_include_download_all():
    download = labels_for("de", "download")
    options = labels_for("de", "options")
    assert "Alle herunterladen" in download
    assert "Download all" in download  # English fallback
    assert "Weitere Optionen" in options
    assert "More options" in options

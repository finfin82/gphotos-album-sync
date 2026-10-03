from app.config import Settings
from app.downloader import _xpath_aria, build_chrome_options
from pathlib import Path


def test_xpath_aria_quotes():
    xp = _xpath_aria(["Alle herunterladen", "Download all"], "button")
    assert "Alle herunterladen" in xp
    assert "Download all" in xp
    assert xp.startswith("//button[")


def test_chrome_options_headless_and_lang(tmp_path: Path):
    settings = Settings(
        google_lang="de",
        chrome_binary="",
        headless=True,
        use_chrome_profile=False,
        wsl_inside=True,
    )
    options = build_chrome_options(settings, tmp_path)
    args = options.arguments
    assert "--headless=new" in args
    assert "--no-sandbox" in args
    assert "--disable-dev-shm-usage" in args
    assert "--lang=de-DE" in args

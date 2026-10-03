"""Selenium download of a Google Photos shared album (gp-dl-style flow)."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.config import Settings
from app.labels import accept_languages, chrome_lang, labels_for
from app.normalize import merge_into_album
from app.sanitize import album_title_from_page

log = logging.getLogger(__name__)


class DownloadError(Exception):
    """Album download failed."""


@dataclass
class SyncResult:
    url: str
    album_title: str
    dest_dir: str
    copied: int
    skipped: int
    overwritten: int
    zip_name: str


def _xpath_aria(labels: list[str], tag: str = "*") -> str:
    clauses = " or ".join(
        f"@aria-label={_xpath_literal(label)}" for label in labels
    )
    return f"//{tag}[{clauses}]"


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def build_chrome_options(settings: Settings, download_dir: Path) -> Options:
    options = Options()
    binary = (settings.chrome_binary or "").strip()
    if binary and Path(binary).exists():
        options.binary_location = binary
        log.info("Using Chrome binary %s", binary)

    lang = chrome_lang(settings.google_lang)
    options.add_argument(f"--lang={lang}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-features=Translate,MediaRouter")
    options.add_argument(f"--accept-lang={accept_languages(settings.google_lang)}")

    if settings.headless:
        # gp-dl uses --headless=new when WSL_INSIDE is set; Docker needs the same.
        options.add_argument("--headless=new")

    if settings.use_chrome_profile:
        profile = Path(settings.profile_dir)
        profile.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile}")
        log.info("Using Chrome profile %s", profile)
    else:
        log.info("Shared-link mode (no Chrome profile / no Google login)")

    prefs = {
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "download.default_directory": str(download_dir),
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "intl.accept_languages": accept_languages(settings.google_lang),
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options


def create_driver(settings: Settings, download_dir: Path) -> webdriver.Chrome:
    options = build_chrome_options(settings, download_dir)
    driver_path = (settings.chromedriver_path or "").strip()
    if driver_path and Path(driver_path).exists():
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        log.warning("Chromedriver path %s missing; falling back to Selenium Manager", driver_path)
        driver = webdriver.Chrome(options=options)

    if settings.headless:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
    return driver


def _click_first(driver: webdriver.Chrome, xpaths: list[str], timeout: int, what: str):
    last_error: Exception | None = None
    deadline = time.time() + timeout
    remaining = timeout
    for xpath in xpaths:
        remaining = max(2, int(deadline - time.time()))
        if remaining <= 0:
            break
        try:
            element = WebDriverWait(driver, remaining).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            log.debug("Clicked %s via %s", what, xpath)
            return element
        except Exception as exc:  # noqa: BLE001 — try next selector
            last_error = exc
            continue
    raise DownloadError(f"Konnte „{what}“ nicht finden ({last_error})")


def _dismiss_cookies(driver: webdriver.Chrome, settings: Settings) -> None:
    labels = labels_for(settings.google_lang, "accept_cookies")
    xpaths = []
    for label in labels:
        lit = _xpath_literal(label)
        xpaths.append(f"//button[normalize-space()={lit}]")
        xpaths.append(f"//*[@aria-label={lit}]")
        xpaths.append(f"//button[.//span[normalize-space()={lit}]]")

    def try_in_current_context() -> bool:
        for xpath in xpaths:
            try:
                button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                log.info("Dismissed cookie banner")
                return True
            except TimeoutException:
                continue
            except WebDriverException:
                continue
        return False

    if try_in_current_context():
        return
    for frame in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(frame)
            found = try_in_current_context()
        except WebDriverException:
            found = False
        finally:
            driver.switch_to.default_content()
        if found:
            return


def _wait_for_zip(download_dir: Path, timeout: int) -> Path:
    deadline = time.time() + timeout
    last_size = -1
    stable_rounds = 0
    while time.time() < deadline:
        zips = sorted(download_dir.glob("*.zip"))
        partials = list(download_dir.glob("*.crdownload")) + list(
            download_dir.glob("*.tmp")
        )
        if zips and not partials:
            zip_path = zips[0]
            size = zip_path.stat().st_size
            if size == last_size and size > 0:
                stable_rounds += 1
                if stable_rounds >= 3:
                    return zip_path
            else:
                stable_rounds = 0
                last_size = size
        time.sleep(0.4)
    raise DownloadError(
        f"Timeout ({timeout}s): Google-ZIP wurde nicht fertig heruntergeladen."
    )


def _dump_debug(driver: webdriver.Chrome, settings: Settings, url: str) -> None:
    if not settings.debug_dumps:
        return
    debug_dir = Path(settings.queue_dir) / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time()))
    png = debug_dir / f"{stamp}.png"
    html = debug_dir / f"{stamp}.html"
    try:
        driver.save_screenshot(str(png))
        html.write_text(driver.page_source or "", encoding="utf-8")
        log.warning("Debug dump for %s → %s", url, png)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not write debug dump: %s", exc)


def download_shared_album(url: str, settings: Settings) -> SyncResult:
    output_root = Path(settings.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="gp-sync-", dir=settings.temp_dir))
    download_dir = work / "dl"
    extract_dir = work / "extract"
    download_dir.mkdir(parents=True)
    extract_dir.mkdir(parents=True)

    driver = None
    try:
        driver = create_driver(settings, download_dir)
        wait = max(5, settings.web_driver_wait)

        log.info("Opening %s (GOOGLE_LANG=%s)", url, settings.google_lang)
        driver.get(url)
        _dismiss_cookies(driver, settings)

        try:
            WebDriverWait(driver, wait).until(lambda d: (d.title or "").strip())
        except TimeoutException as exc:
            raise DownloadError("Albumseite hat keinen Titel geladen.") from exc

        album_title = album_title_from_page(driver.title)
        log.info("Album title: %s", album_title)

        option_labels = labels_for(settings.google_lang, "options")
        download_labels = labels_for(settings.google_lang, "download")

        option_xpaths = [
            _xpath_aria(option_labels, "button"),
            _xpath_aria(option_labels, "*"),
            "//button[@aria-haspopup='menu']",
        ]
        download_xpaths = [
            "//li[@role='menuitem' and ("
            + " or ".join(f"@aria-label={_xpath_literal(label)}" for label in download_labels)
            + ")]",
            _xpath_aria(download_labels, "*"),
            "//*[@role='menuitem' and ("
            + " or ".join(
                f"contains(normalize-space(.), {_xpath_literal(label)})"
                for label in download_labels
            )
            + ")]",
        ]

        try:
            _click_first(driver, option_xpaths, wait, option_labels[0])
        except DownloadError:
            log.info("More-options menu not found; trying a direct download control")

        try:
            _click_first(driver, download_xpaths, wait, download_labels[0])
        except DownloadError as exc:
            _dump_debug(driver, settings, url)
            raise DownloadError(
                "„Download all“ / „Alle herunterladen“ nicht gefunden. "
                "Ist der Link wirklich ein geteiltes Album? "
                f"GOOGLE_LANG={settings.google_lang}"
            ) from exc

        log.info("Waiting for Google to prepare the zip…")
        zip_path = _wait_for_zip(download_dir, settings.download_timeout)
        log.info("Downloaded %s (%s bytes)", zip_path.name, zip_path.stat().st_size)

        if zip_path.stat().st_size < 32:
            raise DownloadError("Heruntergeladene ZIP ist leer.")

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        dest_dir = output_root / album_title
        stats = merge_into_album(extract_dir, dest_dir, skip_existing=settings.skip_existing)
        if stats["copied"] + stats["skipped"] + stats["overwritten"] == 0:
            raise DownloadError("ZIP enthielt keine Dateien zum Entpacken.")

        log.info(
            "Synced %s → %s (copied=%s skipped=%s overwritten=%s)",
            album_title,
            dest_dir,
            stats["copied"],
            stats["skipped"],
            stats["overwritten"],
        )
        return SyncResult(
            url=url,
            album_title=album_title,
            dest_dir=str(dest_dir),
            copied=stats["copied"],
            skipped=stats["skipped"],
            overwritten=stats["overwritten"],
            zip_name=zip_path.name,
        )
    except DownloadError:
        if driver is not None:
            _dump_debug(driver, settings, url)
        raise
    except Exception as exc:
        if driver is not None:
            _dump_debug(driver, settings, url)
        raise DownloadError(str(exc)) from exc
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(work, ignore_errors=True)

from pathlib import Path
import os

_root = Path("/tmp/gphotos-album-sync-tests")
for name in ("queue", "data", "tmp", "profile"):
    (_root / name).mkdir(parents=True, exist_ok=True)

os.environ.setdefault("QUEUE_DIR", str(_root / "queue"))
os.environ.setdefault("OUTPUT_ROOT", str(_root / "data"))
os.environ.setdefault("TEMP_DIR", str(_root / "tmp"))
os.environ.setdefault("PROFILE_DIR", str(_root / "profile"))
os.environ.setdefault("POLL_SECONDS", "120")
os.environ.setdefault("GOOGLE_LANG", "de")
os.environ.setdefault("USE_CHROME_PROFILE", "false")

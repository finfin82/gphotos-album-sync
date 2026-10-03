from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app import __version__
from app.config import Settings, get_settings
from app.queue_store import AlbumQueue, is_share_url
from app.worker import SyncWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("gphotos-album-sync")

settings: Settings
queue: AlbumQueue
worker: SyncWorker


def _bootstrap() -> None:
    global settings, queue, worker
    settings = get_settings()
    Path(settings.output_root).mkdir(parents=True, exist_ok=True)
    Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)
    queue = AlbumQueue(settings.queue_dir)
    worker = SyncWorker(settings, queue)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    log.info(
        "gphotos-album-sync %s  GOOGLE_LANG=%s  OUTPUT_ROOT=%s",
        __version__,
        settings.google_lang,
        settings.output_root,
    )
    worker.start()
    yield
    worker.shutdown()


app = FastAPI(
    title="gphotos-album-sync",
    version=__version__,
    lifespan=lifespan,
)


class SyncRequest(BaseModel):
    url: str = Field(..., min_length=12, description="Google Photos share URL")


INDEX_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>gphotos-album-sync</title>
  <style>
    :root { color-scheme: dark light; }
    body { font-family: system-ui, sans-serif; margin: 0; background: #111814; color: #e8eee9; }
    main { max-width: 42rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
    h1 { font-size: 1.35rem; font-weight: 650; margin: 0 0 .25rem; }
    p.lead { color: #b7c4ba; margin: 0 0 1.25rem; }
    label { display: block; font-size: .85rem; margin-bottom: .35rem; }
    input[type=url] { width: 100%; box-sizing: border-box; padding: .7rem .8rem; border-radius: 8px;
      border: 1px solid #3a4a3e; background: #1a221c; color: inherit; font: inherit; }
    button { margin-top: .75rem; background: #3d8f5c; color: #fff; border: 0; padding: .65rem 1rem;
      border-radius: 8px; font: inherit; font-weight: 600; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    .card { background: #1a221c; border: 1px solid #2c3a30; border-radius: 12px; padding: 1rem; margin: 1rem 0; }
    .ok { color: #8fdf9a; } .err { color: #ff9b8a; } code { font-size: .9em; }
    ul { padding-left: 1.1rem; } li { margin: .2rem 0; word-break: break-all; }
    .muted { color: #8fa194; font-size: .9rem; }
    footer.bmc { margin-top: 2.5rem; text-align: center; font-size: .75rem; }
    footer.bmc a { color: #6a7a6e; text-decoration: none; }
    footer.bmc a:hover { color: #8fa194; text-decoration: underline; }
  </style>
</head>
<body>
<main>
  <h1>gphotos-album-sync</h1>
  <p class="lead">Geteilte Google-Fotos-Alben nach <code>shared/&lt;Albumname&gt;/</code> auf der NAS.</p>
  <form id="f">
    <label for="url">Share-Link</label>
    <input id="url" name="url" type="url" required placeholder="https://photos.app.goo.gl/…">
    <button type="submit">In die Queue legen</button>
  </form>
  <p id="msg" class="muted"></p>
  <div class="card" id="status">Lade Status…</div>
  <p class="muted">API: <code>GET /health</code> · <code>POST /sync</code> · Datei: <code>queue/albums.txt</code></p>
  <footer class="bmc"><a href="https://buymeacoffee.com/andyamber" target="_blank" rel="noopener">Buy me a coffee</a></footer>
</main>
<script>
async function load() {
  const r = await fetch('/status');
  const s = await r.json();
  const el = document.getElementById('status');
  el.innerHTML = `
    <p>Ausgabepfad: <code>${s.output_root}</code><br>
    Sprache: <code>${s.google_lang}</code> · Worker: ${s.current_url ? 'arbeitet' : 'wartet'}</p>
    <p><strong>Warteschlange (${s.pending_count})</strong></p>
    <ul>${(s.pending || []).map(u => `<li>${u}</li>`).join('') || '<li class="muted">leer</li>'}</ul>
    <p><strong>Zuletzt erfolgreich</strong></p>
    <ul>${(s.done_tail || []).slice().reverse().map(u => `<li>${u}</li>`).join('') || '<li class="muted">—</li>'}</ul>
    <p><strong>Fehler</strong></p>
    <ul>${(s.failed_tail || []).slice().reverse().map(u => `<li class="err">${u}</li>`).join('') || '<li class="muted">—</li>'}</ul>`;
}
document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  msg.textContent = '';
  try {
    const r = await fetch('/sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: document.getElementById('url').value})
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.statusText);
    msg.className = 'ok';
    msg.textContent = 'In der Queue: ' + data.url;
    document.getElementById('url').value = '';
    await load();
  } catch (err) {
    msg.className = 'err';
    msg.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});
load();
setInterval(load, 8000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/health")
def health() -> dict:
    snap = queue.snapshot()
    return {
        "ok": True,
        "version": __version__,
        "google_lang": settings.google_lang,
        "output_root": settings.output_root,
        "pending_count": snap["pending_count"],
        "current_url": worker.current_url,
        "busy": worker.busy.locked(),
    }


@app.get("/status")
def status() -> dict:
    snap = queue.snapshot()
    return {
        **snap,
        "google_lang": settings.google_lang,
        "output_root": settings.output_root,
        "skip_existing": settings.skip_existing,
        "current_url": worker.current_url,
        "last_result": worker.last_result,
        "last_error": worker.last_error,
    }


@app.post("/sync")
def sync(body: SyncRequest) -> dict:
    url = body.url.strip()
    if not is_share_url(url):
        raise HTTPException(
            status_code=400,
            detail="Keine gültige Google-Photos-Share-URL "
            "(photos.app.goo.gl oder photos.google.com).",
        )
    queued = queue.enqueue(url)
    worker.kick()
    return {"status": "queued", "url": queued}


def run() -> None:
    import uvicorn

    cfg = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=cfg.http_port,
        log_level="info",
    )


if __name__ == "__main__":
    run()

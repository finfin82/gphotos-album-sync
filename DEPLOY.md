# Deploy-Checkliste: gphotos-album-sync

Ziel auf der NAS: `<DATA_DIR>/shared/<Albumname>/` (beliebige Freigabe).

## Variante A — `docker compose` auf der NAS

1. Dieses Repo auf die NAS kopieren (oder git clone).
2. `cp .env.example .env`
3. In `.env` setzen:
   - `GOOGLE_LANG=de`
   - `DATA_DIR=/volume1/photos/gphotos-album-sync` (Synology; Pfad anpassen)
   - `HTTP_PORT=8090`
4. `docker compose config` — muss ohne Fehler durchlaufen.
5. `docker compose up -d --build`
6. Health: `curl -s http://127.0.0.1:8090/health`
7. Eine Share-URL in `queue/albums.txt` legen **oder** `POST /sync`.
8. Prüfen: `$DATA_DIR/shared/<Albumname>/` enthält die Fotos.
9. Logs: `docker compose logs -f gphotos-album-sync`

## Variante B — Portainer

1. Repo auf die NAS legen, damit der **Build-Kontext** (Dockerfile) erreichbar ist.
2. Portainer → Stacks → Add stack.
3. Compose-Datei aus diesem Repo einfügen (oder Git/Repo-Deploy, falls eingerichtet).
4. Environment in Portainer:
   - `GOOGLE_LANG=de`
   - `DATA_DIR=/volume1/photos/gphotos-album-sync`
   - `HTTP_PORT=8090`
5. Volume-Pfad kontrollieren: links NAS-`DATA_DIR`, rechts `/data`.
6. Deploy / Update the stack.
7. `shm_size: 2gb` muss erhalten bleiben (Chromium). Nicht löschen.
8. Health-Check wie oben, dann Test-Album syncen.

## Volume-Zuordnung

| Host (NAS) | Container | Inhalt |
|---|---|---|
| `…/photos/gphotos-album-sync` (Beispiel) | `/data` | `shared/<Album>/` landet hier |
| `./queue` | `/queue` | `albums.txt`, `done.txt`, `failed.txt` |
| `./profile` | `/profile` | optional, nur für private Alben |

Kein Google-Passwort in Compose eintragen. Standardmodus: **nur Share-Links**.

## Nach dem Start

```bash
# Queue
echo 'https://photos.app.goo.gl/…' >> queue/albums.txt

# oder API
curl -s -X POST http://NAS-IP:8090/sync \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://photos.app.goo.gl/…"}'
```

Andere Clients (Frames, Galerien, Scripts) lesen denselben Ordnerbaum unter `<DATA_DIR>/shared/` — Pfad dort ggf. anpassen.

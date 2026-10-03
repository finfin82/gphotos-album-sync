> English: see [README.md](README.md)

# gphotos-album-sync

Self-contained Docker-Compose-Stack: **geteilte Google-Fotos-Alben** (Share-Links) landen als Ordner auf der NAS — ein Ordner pro Album unter `shared/`.

```
<DATA_DIR>/shared/<Albumname>/…
```

Es gibt **keine** Immich-Anbindung, **keine** Google-Cloud-API-Keys und **keine** gespeicherten Google-Passwörter. Ein Service, Dateisystem only.

**Hinweis zur offiziellen API:** Die Google Photos Library API deckt Shared Albums für Drittanbieter nur eingeschränkt ab (kein vollwertiger, dokumentierter Ersatz für „Share-Link → alle Medien herunterladen“). Deshalb arbeitet dieses Tool bewusst über die Web-Oberfläche (wie ein Browser), nicht über API-Keys.

## Weboberfläche

![Queue-Seite: Share-Link-Formular, Beispielalben und Buy-me-a-coffee-Footer](docs/screenshot-ui.png)

*Lokale Seite unter `http://<host>:8090/`. Die Album-Links im Screenshot sind erfundene Beispiele, keine echten Alben.*

## So funktioniert es

1. Du legst eine Share-URL pro Zeile in `queue/albums.txt` **oder** schickst `POST /sync` mit JSON `{"url":"https://photos.app.goo.gl/…"}`.
2. Der Worker öffnet den Link in Chromium (Selenium, gleicher Ablauf wie gp-dl 0.4.x): Menü → **Alle herunterladen** → ZIP.
3. Die Dateien liegen unter `/data/shared/<AlbumTitle>/`. Der Titel kommt aus dem Seitentitel (unsichere Zeichen werden entfernt).
4. Erledigte URLs wandern nach `queue/done.txt`, Fehler nach `queue/failed.txt` (Grund steht in den Logs).
5. Denselben Link später nochmal einreihen = erneuter Sync. Vorhandene Dateien **gleichen Namens** werden übersprungen, neue Dateien dazugemischt.

Primärmodus: **nur öffentliche Share-Links**. Ein Google-Login ist dafür nicht nötig. Ein Chrome-Profil (`./profile` → `/profile`) ist vorbereitet, falls du später private Alben brauchst (`USE_CHROME_PROFILE=true`).

## Schnellstart auf der NAS

```bash
cp .env.example .env
# DATA_DIR auf die gewünschte NAS-Freigabe setzen, z. B.:
# DATA_DIR=/volume1/photos/gphotos-album-sync

docker compose up -d --build
curl -s http://127.0.0.1:8090/health
```

Kurz-Checkliste für Portainer: [DEPLOY.md](DEPLOY.md).

### Volume auf die NAS-Freigabe

In `.env` oder in `docker-compose.yml`:

| Host | Container | Bedeutung |
|---|---|---|
| Host-Freigabe (z. B. `/volume1/photos/gphotos-album-sync`) | `/data` | Sync-Wurzel; Alben unter `shared/` |
| `./queue` | `/queue` | URL-Queue |
| `./profile` | `/profile` | optional, Chrome-Profil |

Ergebnis auf der Platte:

```
/data/shared/<Albumname>/foto.jpg
→ <DATA_DIR>/shared/<Albumname>/foto.jpg  (NAS-Freigabe / SMB-Mount)
```

SMB-Beispiel (falls der Compose-Host nicht die Synology selbst ist): die Freigabe zuerst mounten, dann den Mountpunkt als `DATA_DIR` verwenden.

`shm_size: 2gb` nicht entfernen — Chromium braucht den Shared Memory.

## Einen Link hinzufügen

**Datei** (eine URL pro Zeile, `#` = Kommentar):

```bash
cp queue/albums.txt.example queue/albums.txt   # nur beim ersten Mal
echo 'https://photos.app.goo.gl/xxxxxxxxxxxxxxxxxxxxxx' >> queue/albums.txt
```

Der Worker liest die Datei alle `POLL_SECONDS` (Standard 30) und entfernt die URL nach dem Lauf.

**API:**

```bash
curl -s -X POST http://NAS-IP:8090/sync \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://photos.app.goo.gl/xxxxxxxxxxxxxxxxxxxxxx"}'
```

Antwort: `{"status":"queued","url":"…"}`. Fortschritt: `GET /status` oder die kleine Seite unter `http://NAS-IP:8090/`.

Health:

```bash
curl -s http://NAS-IP:8090/health
```

## Umgebungsvariablen

Siehe `.env.example`. Wichtig:

| Variable | Standard | Zweck |
|---|---|---|
| `GOOGLE_LANG` | **`de`** | UI-Sprache / aria-labels (`Weitere Optionen`, `Alle herunterladen`, `Teilen`). gp-dl 0.4.x nutzt dieselbe Variable. |
| `OUTPUT_ROOT` | `/data/shared` | Ziel im Container |
| `HTTP_PORT` | `8090` | Host-Port der API |
| `POLL_SECONDS` | `30` | Wie oft `albums.txt` gelesen wird |
| `WEB_DRIVER_WAIT` | `25` | Selenium-Timeout für Buttons |
| `DOWNLOAD_TIMEOUT` | `1800` | Max. Sekunden auf die ZIP warten |
| `SKIP_EXISTING` | `true` | Gleiche Dateinamen nicht überschreiben |
| `USE_CHROME_PROFILE` | `false` | Nur für private Alben |
| `CHROME_BINARY` | `/usr/bin/chromium` | wie bei gp-dl |
| `DEBUG_DUMPS` | `false` | Screenshot + HTML nach `queue/debug/` bei Fehlern |

`GOOGLE_LANG=de` setzt außerdem Chrome `--lang=de-DE`, damit die deutsche Fotos-Oberfläche (nicht die englischen Labels „More options“ / „Download all“) erscheint.

Weitere gp-dl-kompatible Variablen: `CHROME_BINARY`, `WEB_DRIVER_WAIT`, `WSL_INSIDE` (im Image auf `true`, damit Headless „new“ genutzt wird).

## Hinweise und Grenzen

- **Nutzungsbedingungen:** Das Tool steuert die Google-Fotos-Weboberfläche wie ein Browser (kein offizielles API). Das kann gegen Googles ToS verstoßen. Nur für Alben verwenden, die du besitzen oder die dir per Link geteilt wurden.
- **UI-Scraping ist zerbrechlich:** Google ändert Buttons und aria-labels. Dann schlägt der Klick auf „Alle herunterladen“ fehl — Logs und optional `DEBUG_DUMPS=true` prüfen, `GOOGLE_LANG` kontrollieren.
- **Share-Link ist Pflicht** (Standardmodus). Ein nicht geteiltes Album ohne eingeloggtes Chrome-Profil funktioniert nicht. Keine Passwörter in Compose speichern.
- **Große Alben / ZIP-Limits:** Google packt „Download all“ in eine ZIP; sehr große Alben können fehlschlagen, splitten oder sehr lange brauchen (`DOWNLOAD_TIMEOUT`). Videos und Originalqualität blähen die Archive auf.
- **Kein Login, keine API-Keys.** Private Alben später nur über ein bereits angemeldetes Chrome-Profil (`PROFILE_DIR` / `USE_CHROME_PROFILE`).
- Die HTTP-API hat **keine Authentifizierung** — nur im LAN nutzen, nicht ins Internet öffnen.
- Chromium läuft mit `--no-sandbox`, `--disable-dev-shm-usage`, `--headless=new`.

## Entwicklung / Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
docker compose config
```

Python 3.11+, ein Service, FastAPI (`GET /health`, `POST /sync`) plus Queue-Watcher.

## Verwandte Projekte / Related projects

Dieses Repo ist ein eigenständiger NAS-/Docker-Stack (Share-Link → shared album folder). Der Download-Ablauf
orientiert sich an bestehenden Open-Source-Tools — fair credit:

- [gp-dl](https://codeberg.org/csd4ni3l/gp-dl) — Selenium-/Chromium-Download von Google-Fotos-Alben (UI-Labels/`GOOGLE_LANG`-Idee).
- [gPhotos2Immich](https://github.com/warreth/gPhotos2Immich) — Pipeline Richtung Immich (anderes Ziel; hier **keine** Immich-Anbindung).

Lizenz dieses Projekts: **MIT** (siehe [LICENSE](LICENSE)).

## Buy me a beer

Wenn dir der Stack hilft und du etwas zurückgeben magst / If this helps and you want to say thanks:

**DE:** Ein virtuelles Bier freut mich: [buymeacoffee.com/andyamber](https://buymeacoffee.com/andyamber)  
**EN:** Happy to accept a virtual beer: [buymeacoffee.com/andyamber](https://buymeacoffee.com/andyamber)

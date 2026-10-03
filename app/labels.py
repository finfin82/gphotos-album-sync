"""Google Photos UI aria-labels (gp-dl 0.4.x locale keys + German)."""

from __future__ import annotations

# Keys match gp-dl locales (share / albums / download / options).
# Extra keys: cookie-consent buttons that often block the menu.
LABELS: dict[str, dict[str, list[str]]] = {
    "en": {
        "share": ["Share"],
        "albums": ["Albums"],
        "download": ["Download all"],
        "options": ["More options"],
        "accept_cookies": ["Accept all", "I agree", "Accept all cookies"],
    },
    "de": {
        "share": ["Teilen"],
        "albums": ["Alben"],
        "download": ["Alle herunterladen", "Gesamtes Album herunterladen"],
        "options": ["Weitere Optionen", "Mehr Optionen"],
        "accept_cookies": [
            "Alle akzeptieren",
            "Ich stimme zu",
            "Alle Cookies akzeptieren",
            "Accept all",
        ],
    },
    "fr": {
        "share": ["Partager"],
        "albums": ["Albums"],
        "download": ["Tout télécharger"],
        "options": ["Plus d'options"],
        "accept_cookies": ["Tout accepter", "J'accepte"],
    },
}


def labels_for(lang: str, key: str) -> list[str]:
    """Return label candidates for `lang`, then English, then German fallbacks."""
    ordered = []
    for loc in (lang.lower().split("-")[0], "en", "de"):
        for value in LABELS.get(loc, {}).get(key, []):
            if value not in ordered:
                ordered.append(value)
    return ordered


def chrome_lang(lang: str) -> str:
    base = lang.lower().split("-")[0]
    return {"de": "de-DE", "en": "en-US", "fr": "fr-FR"}.get(base, base)


def accept_languages(lang: str) -> str:
    base = lang.lower().split("-")[0]
    if base == "de":
        return "de-DE,de,en-US,en"
    if base == "fr":
        return "fr-FR,fr,en-US,en"
    return "en-US,en"

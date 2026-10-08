"""Area name -> coordinates, using the language pack's areas.json.

Owner: Radhakrishnan
"""
import json
import os
import re

PACKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packs")

_cache = {}


def load_areas(pack="en"):
    """Return the list of areas for a language pack (cached)."""
    if pack not in _cache:
        path = os.path.join(PACKS_DIR, pack, "areas.json")
        with open(path, encoding="utf-8") as f:
            _cache[pack] = json.load(f)["areas"]
    return _cache[pack]


def _norm(text):
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())


def locate(location_text, pack="en"):
    """Find the area mentioned in location_text.

    Returns {"area": name, "lat": float, "lon": float} or None if no known area matches.
    Longer aliases are checked first, so "north paravur" wins over "paravur".
    """
    if not location_text:
        return None
    text = " " + " ".join(_norm(location_text).split()) + " "
    candidates = []
    for area in load_areas(pack):
        for alias in area.get("aliases", []) + [area["name"]]:
            candidates.append((len(alias), alias.lower(), area))
    candidates.sort(key=lambda c: -c[0])
    for _, alias, area in candidates:
        if " " + " ".join(_norm(alias).split()) + " " in text:
            return {"area": area["name"], "lat": area["lat"], "lon": area["lon"]}
    return None


if __name__ == "__main__":
    # Ctrl+F5 quick check
    SAMPLES = ["near Pandanad church", "North Paravur", "Aluva Manappuram", "somewhere unknown", None]
    for s in SAMPLES:
        print(repr(s), "->", locate(s))

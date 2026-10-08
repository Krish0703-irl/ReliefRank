# server/api.py  (P3)
# The API the web page talks to. Fake cases for now; later these come from
# P2's pipeline and store.py.

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="ReliefRank")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "ReliefRank API"
    }
STATIC_DIR = Path(__file__).parent / "static"

# Same fields the team agreed on. Coordinates are placeholders until areas.json exists.
FAKE_CASES = [
    {
        "id": 1, "score": 92, "people_count": 6, "vulnerable": True, "trapped": True,
        "water_level": "roof", "location_text": "Near St. Mary's church, Chengannur",
        "phone": "98xxxxxx01", "confidence": 0.9, "missing": [],
        "reasons": ["Trapped on roof", "Elderly person present", "6 people"],
        "lat": 9.3180, "lng": 76.6110,
    },
    {
        "id": 2, "score": 64, "people_count": 3, "vulnerable": False, "trapped": False,
        "water_level": "waist", "location_text": "Aluva market road",
        "phone": "98xxxxxx02", "confidence": 0.8, "missing": [],
        "reasons": ["Water at waist level", "3 people"],
        "lat": 10.1004, "lng": 76.3570,
    },
    {
        "id": 3, "score": 38, "people_count": 2, "vulnerable": False, "trapped": False,
        "water_level": "ankle", "location_text": "Kakkanad, near the bus stop",
        "phone": "", "confidence": 0.6, "missing": ["phone"],
        "reasons": ["Water rising", "No phone number"],
        "lat": 10.0159, "lng": 76.3419,
    },
]


class PastedMessages(BaseModel):
    text: str


@app.get("/api/cases")
def get_cases():
    """All cases, highest score first."""
    return sorted(FAKE_CASES, key=lambda c: c["score"], reverse=True)


@app.post("/api/messages")
def post_messages(body: PastedMessages):
    """Receives pasted messages. Later: send each line through P2's pipeline."""
    lines = [line.strip() for line in body.text.splitlines() if line.strip()]
    return {"received": len(lines)}


# Serve index.html, app.js, style.css and Leaflet. Must come AFTER the /api routes.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
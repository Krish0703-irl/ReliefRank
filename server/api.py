"""The API the web page talks to. Started by run.py (Ctrl+F5).

Messages go through reliefrank.pipeline (extract -> validate -> geo -> dedupe ->
score -> store); this file only turns HTTP requests into pipeline/store calls.

    GET   /api/health            backend, model, language pack, online/offline
    POST  /api/messages          {"text": "one message per line"} -> cases touched
    GET   /api/cases?status=     cases, highest score first ("needs call" works too)
    GET   /api/cases/{case_id}   one case with reasons, messages and call script
    PATCH /api/cases/{case_id}   {"status": "assigned" | "resolved" | ...}
"""
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from reliefrank import pipeline, store
from reliefrank.models import STATUSES

try:
    from reliefrank.llm.base import backend_info
except ImportError:
    backend_info = None
try:
    from reliefrank.callscript import build_call_script
except ImportError:
    build_call_script = None

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ReliefRank")
store.init_db()


class PastedMessages(BaseModel):
    text: str


class StatusChange(BaseModel):
    status: str


def to_json(case, detail=False):
    """Case -> dict for the page. Adds 'id' and 'lng' (the map uses those names)."""
    d = case.to_dict()
    d["id"] = case.case_id
    d["lng"] = case.lon
    d["mapped"] = case.lat is not None and case.lon is not None
    if detail and build_call_script and case.missing:
        try:
            d["call_script"] = build_call_script(d, config.ACTIVE_PACK)
        except Exception as e:
            d["call_script"] = f"(call script unavailable: {e})"
    return d


def internet_up():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1).close()
        return True
    except OSError:
        return False


@app.get("/api/health")
def health():
    info = backend_info() if backend_info else {"backend": config.BACKEND}
    return {"status": "ok", "pack": config.ACTIVE_PACK, "online": internet_up(), **info}


@app.post("/api/messages")
def post_messages(body: PastedMessages):
    """One message per line. Each line goes through the full pipeline."""
    lines = [line.strip() for line in body.text.splitlines() if line.strip()]
    cases = pipeline.process_batch(lines)
    return {"received": len(lines), "cases": [to_json(c) for c in cases]}


@app.get("/api/cases")
def get_cases(status: str = None):
    """Highest score first. Waiting-time points are refreshed on every call."""
    pipeline.rescore_all()
    return [to_json(c) for c in store.list_cases(status)]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(404, f"No case {case_id}")
    return to_json(case, detail=True)


@app.patch("/api/cases/{case_id}")
def change_status(case_id: str, body: StatusChange):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {list(STATUSES)}")
    case = store.update_status(case_id, body.status)
    if case is None:
        raise HTTPException(404, f"No case {case_id}")
    return to_json(case, detail=True)


# Serve index.html, app.js, style.css and Leaflet. Must come AFTER the /api routes.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
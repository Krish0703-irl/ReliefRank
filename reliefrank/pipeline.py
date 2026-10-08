"""
End to end: one raw message -> one stored, scored case.

  text -> extract (Gemma) -> validate -> geo -> dedupe/merge -> score -> store

Gemma is called only inside extract. Everything after it is plain code.
"""
import inspect

import config
from reliefrank import store
from reliefrank.dedupe import find_duplicate, merge
from reliefrank.models import Case, Extraction, Message
from reliefrank.score import apply_score

# Teammates' modules. Imported defensively so one missing file does not stop the app.
try:
    from reliefrank import extract as _extract_mod
except ImportError:
    _extract_mod = None
try:
    from reliefrank import validate as _validate_mod
except ImportError:
    _validate_mod = None
try:
    from reliefrank import geo as _geo_mod
except ImportError:
    _geo_mod = None


def _call(fn, *args):
    """Call fn with as many of args as it accepts."""
    try:
        n = len([p for p in inspect.signature(fn).parameters.values()
                 if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
        has_var = any(p.kind == p.VAR_POSITIONAL for p in inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return fn(*args)
    return fn(*args) if has_var else fn(*args[:n])


def _find(mod, *names):
    for name in names:
        fn = getattr(mod, name, None) if mod else None
        if callable(fn):
            return fn
    return None


# ---------- steps ----------

def run_extract(text: str) -> dict:
    fn = _find(_extract_mod, "extract", "extract_message", "run")
    if fn is None:
        raise RuntimeError("reliefrank/extract.py has no extract() function yet")
    result = _call(fn, text, config.ACTIVE_PACK)
    if hasattr(result, "__dataclass_fields__"):
        result = result.__dict__
    return result or {}


def _fallback_validate(case: Case) -> None:
    """Used only when validate.py is missing: drop guessed values and flag gaps."""
    raw = " ".join(case.raw_texts).lower()
    if case.location_text and case.location_text.lower() not in raw:
        # keep it only if most of its words really appear in the message
        words = [w for w in case.location_text.lower().split() if len(w) > 2]
        if not words or sum(w in raw for w in words) / len(words) < 0.6:
            case.location_text = None
    digits_raw = "".join(ch for ch in raw if ch.isdigit())
    if case.phone:
        digits = "".join(ch for ch in case.phone if ch.isdigit())
        if len(digits) < 10 or digits[-10:] not in digits_raw:
            case.phone = None


def run_validate(case: Case) -> Case:
    fn = _find(_validate_mod, "validate", "validate_case", "run")
    if fn is not None:
        out = _call(fn, case, " ".join(case.raw_texts))
        if isinstance(out, Case):
            case = out
        elif isinstance(out, dict):
            for k, v in out.items():
                if k in Case.__dataclass_fields__:
                    setattr(case, k, v)
    else:
        _fallback_validate(case)

    # always recompute the gaps so the needs-call queue never loses a case
    missing = []
    conf = case.confidence or {}
    for f in config.REQUIRED_FIELDS:
        key = "location" if f == "location_text" else f
        value = getattr(case, f)
        try:
            low = conf.get(key) is not None and float(conf[key]) < config.MIN_CONFIDENCE
        except (TypeError, ValueError):
            low = False
        if not value or low:
            missing.append("location" if f == "location_text" else f)
    case.missing = sorted(set(case.missing or []) | set(missing))
    case.needs_call = bool(case.missing)
    if case.needs_call and case.status == "new":
        case.status = "needs call"
    elif not case.needs_call and case.status == "needs call":
        case.status = "new"
    return case


def run_geo(case: Case) -> Case:
    if case.lat is not None or not case.location_text:
        return case
    fn = _find(_geo_mod, "locate", "geocode", "lookup", "find_area")
    if fn is None:
        return case
    try:
        out = _call(fn, case.location_text, config.ACTIVE_PACK)
    except Exception:
        return case
    if isinstance(out, dict):
        case.area = out.get("area", case.area)
        case.lat = out.get("lat", case.lat)
        case.lon = out.get("lon", case.lon)
    elif isinstance(out, (tuple, list)) and len(out) >= 3:
        case.area, case.lat, case.lon = out[0], out[1], out[2]
    if case.area in ("unknown", ""):
        case.area = None
    return case


# ---------- public API ----------

def process_message(text: str, received_at: str = None, message_id: str = None) -> Case:
    """Turn one raw message into a stored, scored case (new or merged). Returns the case."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty message")
    msg = Message(message_id=message_id or store.new_message_id(),
                  text=text,
                  received_at=received_at or store.now_iso())

    try:
        extraction = Extraction.from_dict(run_extract(text))
        extract_error = None
    except Exception as e:                      # model down or bad JSON: keep the message anyway
        extraction = Extraction()
        extract_error = str(e)

    case = Case.from_message(store.new_case_id(), msg, extraction)
    if extract_error:
        case.gemma_note = f"Could not read automatically ({extract_error}). Please read the message."
    case = run_validate(case)
    case = run_geo(case)

    existing = find_duplicate(case, store.open_cases())
    if existing is not None:
        case = merge(existing, case)
        case = run_validate(case)
        case = run_geo(case)

    apply_score(case)
    return store.save_case(case)


def process_batch(texts: list) -> list:
    """Process pasted messages one by one. Blank lines are skipped. Returns the cases touched."""
    cases = []
    for t in texts:
        if t and str(t).strip():
            cases.append(process_message(str(t)))
    return cases


def rescore_all() -> list:
    """Refresh waiting-time points for every open case (call before listing)."""
    cases = store.open_cases()
    for c in cases:
        apply_score(c)
        store.save_case(c)
    return cases

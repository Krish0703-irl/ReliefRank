"""
Find and merge messages about the same case.
1. Same phone number (last 10 digits) -> same case.
2. Otherwise, very similar message text (optional, see config.USE_TEXT_DEDUPE).
"""
import re
from difflib import SequenceMatcher

import config
from reliefrank.models import Case

WATER_ORDER = ("unknown", "ankle", "knee", "waist", "chest", "roof")


def normalize_phone(phone) -> str:
    """'+91 98765-43210' -> '9876543210'. Returns '' when there are too few digits."""
    digits = re.sub(r"\D", "", str(phone or ""))
    return digits[-10:] if len(digits) >= 10 else ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def text_similarity(a: str, b: str) -> float:
    a, b = _clean(a), _clean(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_duplicate(new: Case, existing: list):
    """Return the existing Case that `new` belongs to, or None."""
    phone = normalize_phone(new.phone)
    if phone:
        for c in existing:
            if normalize_phone(c.phone) == phone:
                return c

    if config.USE_TEXT_DEDUPE and new.raw_texts:
        best, best_sim = None, 0.0
        for c in existing:
            # different known phones = different households, never merge
            other = normalize_phone(c.phone)
            if phone and other and phone != other:
                continue
            for t in c.raw_texts:
                sim = text_similarity(new.raw_texts[0], t)
                if sim > best_sim:
                    best, best_sim = c, sim
        if best_sim >= config.TEXT_SIMILARITY_THRESHOLD:
            return best
    return None


def merge(base: Case, new: Case) -> Case:
    """Fold `new` into `base`. Keeps the earliest time and the most urgent facts."""
    for mid, txt in zip(new.message_ids, new.raw_texts):
        if mid not in base.message_ids:
            base.message_ids.append(mid)
            base.raw_texts.append(txt)

    if new.received_at and (not base.received_at or new.received_at < base.received_at):
        base.received_at = new.received_at

    counts = [n for n in (base.people_count, new.people_count) if n]
    base.people_count = max(counts) if counts else None
    base.vulnerable = sorted(set(base.vulnerable or []) | set(new.vulnerable or []))

    for f in ("medical_need", "trapped"):
        a, b = getattr(base, f), getattr(new, f)
        setattr(base, f, True if (a or b) else (a if a is not None else b))

    if WATER_ORDER.index(new.water_level if new.water_level in WATER_ORDER else "unknown") > \
       WATER_ORDER.index(base.water_level if base.water_level in WATER_ORDER else "unknown"):
        base.water_level = new.water_level

    for f in ("location_text", "phone", "area", "lat", "lon"):
        if getattr(base, f) in (None, "") and getattr(new, f) not in (None, ""):
            setattr(base, f, getattr(new, f))

    for k, v in (new.confidence or {}).items():
        try:
            if v is not None and float(v) > float((base.confidence or {}).get(k, 0) or 0):
                base.confidence[k] = v
        except (TypeError, ValueError):
            pass

    if new.gemma_note:
        base.gemma_note = new.gemma_note       # latest message describes the latest situation
    return base

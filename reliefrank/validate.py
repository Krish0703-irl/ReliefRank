"""P1 - check Gemma's output against the original message before code trusts it.

    from reliefrank.validate import validate
    checked = validate(extract(msg), msg)

Returns:
    fields      cleaned fields (same keys as extract, minus _meta)
    confidence  per-field confidence after checks
    missing     fields still unknown, e.g. ["location_text", "phone"]  -> callscript.py
    issues      human-readable notes for the detail panel
    needs_call  True -> needs-a-call queue (no usable location, or extraction failed)
    reachable   True if we have a phone number to call
Key rule: a location or phone that does not appear in the message text is rejected,
so the model can never send a boat to a place it made up.
"""
import re

from reliefrank.llm.base import setting

CORE = ["location_text", "people_count", "water_level", "phone"]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def location_in_message(location: str, message: str) -> bool:
    loc, msg = _norm(location), _norm(message)
    if not loc:
        return False
    if loc in msg:
        return True
    words = [w for w in loc.split() if len(w) > 2]
    if not words:
        return False
    msg_words = set(msg.split())
    return sum(w in msg_words for w in words) / len(words) >= 0.7


def normalise_phone(phone: str):
    """Indian mobile -> 10 digits, or None if it is not a plausible number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def phone_in_message(phone10: str, message: str) -> bool:
    return phone10 in re.sub(r"\D", "", message or "")


def validate(extracted: dict, message: str) -> dict:
    min_conf = setting("MIN_FIELD_CONFIDENCE", 0.6)
    fields = {k: v for k, v in extracted.items() if k not in ("_meta", "confidence")}
    confidence = dict(extracted.get("confidence", {}))
    meta = extracted.get("_meta", {})
    issues = []

    if not meta.get("ok", True):
        issues.append(f"AI could not read this message ({meta.get('error')})")

    loc = fields.get("location_text")
    if loc and not location_in_message(loc, message):
        issues.append(f"Location '{loc}' not found in message text - removed")
        fields["location_text"], confidence["location_text"] = None, 0.0

    raw_phone = fields.get("phone")
    if raw_phone:
        phone10 = normalise_phone(raw_phone)
        if phone10 is None:
            issues.append(f"Phone '{raw_phone}' is not a valid mobile number - removed")
        elif not phone_in_message(phone10, message):
            issues.append(f"Phone '{raw_phone}' not found in message text - removed")
            phone10 = None
        fields["phone"] = phone10
        confidence["phone"] = 0.0 if phone10 is None else max(confidence.get("phone", 0), 0.95)

    count = fields.get("people_count")
    if count is not None and not (1 <= count <= 500):
        issues.append(f"People count {count} looks wrong - removed")
        fields["people_count"], confidence["people_count"] = None, 0.0

    missing = [f for f in CORE if fields.get(f) in (None, "unknown")]
    low_conf = [f for f in CORE if f not in missing and confidence.get(f, 0) < min_conf]
    for f in low_conf:
        issues.append(f"Low confidence on {f} ({confidence.get(f, 0):.2f}) - please confirm")

    needs_call = (not meta.get("ok", True)) or "location_text" in missing \
        or "location_text" in low_conf
    return {
        "fields": fields,
        "confidence": confidence,
        "missing": missing,
        "low_confidence": low_conf,
        "issues": issues,
        "needs_call": needs_call,
        "reachable": fields.get("phone") is not None,
    }

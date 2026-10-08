"""Check Gemma's output against the original message before code trusts it.

Why this file exists:
    A language model can "fill in" a plausible place or number that is not in the
    message. In rescue work that could send a boat to the wrong street. So every
    location and phone number is checked against the original text, low-confidence
    fields are flagged, and incomplete cases are routed to the "needs a call" queue.

How pipeline.py uses it:
    fields = validate(extract(text), text)
    # fields is flat and uses the data-model names, ready to merge into a Case:
    # people_count, vulnerable, medical_need, trapped, water_level, location_text,
    # phone, gemma_note, confidence, missing, needs_call
    # plus: issues (notes for the detail panel), extraction_ok, backend, model

Field meanings added here:
    missing     e.g. ["location", "phone"]; callscript.py asks for these
    needs_call  True when location or contact is missing or low-confidence,
                or Gemma could not read the message at all
    phone       normalised to 10 digits (Indian mobile) or None

Ctrl+F5 on this file runs the checks below without any model.
"""
if __name__ == "__main__":   # Ctrl+F5 on this file: make the repo root importable
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re

from reliefrank.llm.base import setting

CORE = ["location", "phone", "people_count", "water_level"]
CONTACT = ["location", "phone"]          # without these a volunteer cannot act


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def location_in_message(location, message):
    """True if the location's words really appear in the message."""
    loc, msg = _norm(location), _norm(message)
    if not loc:
        return False
    if f" {loc} " in f" {msg} ":
        return True
    words = [w for w in loc.split() if len(w) > 2]
    if not words:
        return False
    msg_words = set(msg.split())
    return sum(w in msg_words for w in words) / len(words) >= 0.7


def normalise_phone(phone):
    """Indian mobile number -> 10 digits, or None if it is not a plausible mobile."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


def phone_in_message(phone10, message):
    return phone10 in re.sub(r"\D", "", message or "")


def validate(extracted, message: str) -> dict:
    """extracted: the dict from extract(), or a Case/Extraction object from models.py."""
    if not isinstance(extracted, dict):
        if hasattr(extracted, "to_dict"):
            extracted = extracted.to_dict()
        else:
            from dataclasses import asdict
            extracted = asdict(extracted)
    min_conf = setting("MIN_CONFIDENCE", 0.6)
    meta = extracted.get("_meta", {"ok": True})
    out = {k: v for k, v in extracted.items() if k != "_meta"}
    conf = dict(out.get("confidence", {}))
    issues = []

    if not meta.get("ok", True):
        issues.append(f"Gemma could not read this message: {meta.get('error')}")

    # 1. Location must come from the message text
    loc = out.get("location_text")
    if loc and not location_in_message(loc, message):
        issues.append(f"Location '{loc}' is not in the message - removed")
        out["location_text"], conf["location"] = None, 0.0

    # 2. Phone must be a real mobile number that appears in the message
    raw_phone = out.get("phone")
    if raw_phone:
        phone10 = normalise_phone(raw_phone)
        if phone10 is None:
            issues.append(f"Phone '{raw_phone}' is not a valid mobile number - removed")
        elif not phone_in_message(phone10, message):
            issues.append(f"Phone '{raw_phone}' is not in the message - removed")
            phone10 = None
        out["phone"] = phone10
        # a number found by code in the text is certain, whatever Gemma said
        conf["phone"] = 0.0 if phone10 is None else max(conf.get("phone", 0.0), 0.95)

    # 3. People count must be sensible
    count = out.get("people_count")
    if count is not None and not 1 <= count <= 500:
        issues.append(f"People count {count} looks wrong - removed")
        out["people_count"], conf["people_count"] = None, 0.0

    # 4. Missing and low-confidence fields
    present = {"location": out.get("location_text") is not None,
               "phone": out.get("phone") is not None,
               "people_count": out.get("people_count") is not None,
               "water_level": out.get("water_level", "unknown") != "unknown"}
    missing = [f for f in CORE if not present[f]]
    low = [f for f in CORE if present[f] and conf.get(f, 0.0) < min_conf]
    for f in low:
        issues.append(f"Please confirm {f} (confidence {conf.get(f, 0.0):.2f})")

    # 5. Route: needs a call if Gemma failed, or location/contact missing or unsure
    needs_call = (not meta.get("ok", True)) or any(f in missing or f in low for f in CONTACT)

    out.update(confidence=conf, missing=missing, low_confidence=low, issues=issues,
               needs_call=needs_call, extraction_ok=bool(meta.get("ok", True)),
               backend=meta.get("backend"), model=meta.get("model"))
    return out


# ---------------- Ctrl+F5 self-test (no model needed) ----------------
if __name__ == "__main__":
    from reliefrank.extract import normalise

    def case(**fields):
        r = normalise(fields)
        r["_meta"] = {"ok": True}
        return r

    msg = "4 of us on terrace near St Marys church Pandanad, chest water, call 98470 12345"
    checks = []

    v = validate(case(people_count=4, location_text="near St Marys church Pandanad",
                      water_level="chest", phone="98470 12345",
                      confidence={"people_count": .9, "location": .9, "water_level": .9, "phone": .9}), msg)
    checks.append(("complete case is kept", v["needs_call"] is False and v["phone"] == "9847012345"))

    v = validate(case(location_text="Kochi", phone="98470 12345",
                      confidence={"location": .9, "phone": .9}), msg)
    checks.append(("invented location is removed", v["location_text"] is None and v["needs_call"]))

    v = validate(case(location_text="Pandanad", phone="9999988888",
                      confidence={"location": .9, "phone": .9}), msg)
    checks.append(("invented phone is removed", v["phone"] is None and "phone" in v["missing"]))

    v = validate(case(location_text="Pandanad", phone="12345",
                      confidence={"location": .9, "phone": .9}), msg)
    checks.append(("invalid phone is removed", v["phone"] is None))

    v = validate(case(location_text="Pandanad", phone="98470 12345",
                      confidence={"location": .3, "phone": .9}), msg)
    checks.append(("low-confidence location -> needs call", v["needs_call"] and "location" in v["low_confidence"]))

    v = validate(case(people_count=9000, location_text="Pandanad", phone="98470 12345",
                      confidence={"location": .9, "phone": .9, "people_count": .9}), msg)
    checks.append(("absurd people count is removed", v["people_count"] is None))

    failed = normalise({})
    failed["_meta"] = {"ok": False, "error": "timeout"}
    checks.append(("Gemma failure -> needs call", validate(failed, msg)["needs_call"]))

    for name, passed in checks:
        print(("PASS  " if passed else "FAIL  ") + name)
    print(f"\n{sum(p for _, p in checks)}/{len(checks)} checks passed")

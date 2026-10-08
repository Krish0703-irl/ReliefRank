"""Builds a phone-call script for cases in the needs-a-call queue.

It asks only for the details the case is missing, using the pack's call_script.txt.
Owner: Radhakrishnan
"""
import os
import re

PACKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packs")

# Order in which missing details are asked (most important first)
ASK_ORDER = ["location_text", "trapped", "vulnerable", "people_count", "water_level", "phone"]

_cache = {}


def load_template(pack="en"):
    """Parse call_script.txt into {section_name: text}."""
    if pack not in _cache:
        path = os.path.join(PACKS_DIR, pack, "call_script.txt")
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        sections = {}
        for name, body in re.findall(r"^\[([^\]]+)\]\s*\n(.*?)(?=^\[|\Z)", raw, flags=re.M | re.S):
            sections[name.strip()] = body.strip()
        _cache[pack] = sections
    return _cache[pack]


def missing_fields(case):
    """Use the case's own 'missing' list if present, otherwise any empty field."""
    if case.get("missing"):
        return list(case["missing"])
    return [f for f in ASK_ORDER if case.get(f) in (None, "", [])]


def build_call_script(case, pack="en"):
    """Return the call script text for one case (a dict using the models.py field names)."""
    t = load_template(pack)
    missing = missing_fields(case)
    about = ""
    if case.get("location_text") and "location_text" not in missing:
        about = f" from {case['location_text']}"
    lines = [t["opening"].format(about=about)]
    n = 1
    for field in ASK_ORDER:
        key = f"ask:{field}"
        if field in missing and key in t:
            lines.append(f"{n}. {t[key]}")
            n += 1
    if n == 1:
        lines.append("Please confirm your details are still correct and whether the situation has changed.")
    lines.append(t["closing"])
    return "\n\n".join(lines)


if __name__ == "__main__":
    # Ctrl+F5 quick check
    SAMPLE_CASE = {"people_count": 3, "vulnerable": True, "trapped": True, "water_level": "rising",
                   "location_text": None, "phone": "9847000104", "missing": ["location_text"]}
    print(build_call_script(SAMPLE_CASE))

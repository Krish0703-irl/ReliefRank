"""
Transparent urgency score. Every point comes with a visible reason,
so a volunteer or judge can see exactly why a case ranks where it does.
"""
from datetime import datetime

import config
from reliefrank.models import Case

W = config.WEIGHTS


def minutes_waiting(received_at: str, now: datetime = None) -> float:
    try:
        t = datetime.fromisoformat(received_at)
    except (TypeError, ValueError):
        return 0.0
    if now is None:
        now = datetime.now(t.tzinfo) if t.tzinfo else datetime.now()
    elif t.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=t.tzinfo)
    elif t.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    return max(0.0, (now - t).total_seconds() / 60)


def score_case(case: Case, now: datetime = None) -> tuple:
    """Return (score 0-100, list of reasons like 'trapped +25')."""
    parts = []

    def add(label, pts):
        if pts > 0:
            parts.append((label, pts))

    if case.trapped:
        add("trapped", W["trapped"])

    if case.water_level in ("chest", "roof"):
        add(f"water at {case.water_level}", W["water_high"])
    elif case.water_level == "waist":
        add("water at waist", W["water_waist"])

    if case.medical_need or "injured" in (case.vulnerable or []):
        add("medical need", W["medical"])

    vul = sorted(set(case.vulnerable or []))
    if vul:
        add(", ".join(vul), min(len(vul) * W["vulnerable_each"], W["vulnerable_cap"]))

    if case.people_count:
        add(f"{case.people_count} people",
            min(case.people_count * W["person_each"], W["people_cap"]))

    mins = minutes_waiting(case.received_at, now)
    add(f"waiting {int(mins)} min",
        min(int(mins // 10) * W["wait_per_10_min"], W["wait_cap"]))

    if len(case.message_ids) > 1:
        add(f"{len(case.message_ids)} messages", W["repeat_messages"])

    total = min(sum(p for _, p in parts), config.SCORE_CAP)
    return total, [f"{label} +{pts}" for label, pts in parts]


def apply_score(case: Case, now: datetime = None) -> Case:
    case.score, case.reasons = score_case(case, now)
    return case


def rank(cases: list) -> list:
    """Highest score first; ties go to the older case."""
    return sorted(cases, key=lambda c: (-c.score, c.received_at or ""))


def reasons_line(case: Case) -> str:
    """For the UI: 'trapped +25 · water at chest +20 = 45'."""
    if not case.reasons:
        return f"= {case.score}"
    return " · ".join(case.reasons) + f" = {case.score}"

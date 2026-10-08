"""
The shared case schema. Every module codes against these fields.
Change a field only after telling the whole team.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

VULNERABLE_TYPES = ("elderly", "infant", "child", "pregnant", "disabled", "injured", "ill")
WATER_LEVELS = ("ankle", "knee", "waist", "chest", "roof", "unknown")
STATUSES = ("new", "needs call", "assigned", "resolved")


def _to_bool(v):
    if isinstance(v, bool) or v is None:
        return v
    s = str(v).strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
        return False
    return None


@dataclass
class Message:
    """One raw incoming message, unchanged."""
    message_id: str
    text: str
    received_at: str                    # ISO time, e.g. "2026-10-08T12:05:00"


@dataclass
class Extraction:
    """Fields Gemma extracts from one message. None = not stated in the message."""
    people_count: Optional[int] = None
    vulnerable: list = field(default_factory=list)
    medical_need: Optional[bool] = None
    trapped: Optional[bool] = None
    water_level: str = "unknown"
    location_text: Optional[str] = None
    phone: Optional[str] = None
    confidence: dict = field(default_factory=dict)   # {"location": 0.6, ...}
    gemma_note: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Extraction":
        """Build from Gemma's JSON, dropping values outside the allowed lists."""
        d = d or {}
        people = d.get("people_count")
        try:
            people = int(people) if people not in (None, "") else None
            if people is not None and people < 0:
                people = None
        except (TypeError, ValueError):
            people = None
        vul = d.get("vulnerable") or []
        if isinstance(vul, str):
            vul = [vul]
        water = str(d.get("water_level") or "unknown").strip().lower()
        conf = d.get("confidence") if isinstance(d.get("confidence"), dict) else {}
        return cls(
            people_count=people,
            vulnerable=sorted({str(v).strip().lower() for v in vul} & set(VULNERABLE_TYPES)),
            medical_need=_to_bool(d.get("medical_need")),
            trapped=_to_bool(d.get("trapped")),
            water_level=water if water in WATER_LEVELS else "unknown",
            location_text=(str(d["location_text"]).strip() or None) if d.get("location_text") else None,
            phone=(str(d["phone"]).strip() or None) if d.get("phone") else None,
            confidence=conf,
            gemma_note=str(d.get("gemma_note") or ""),
        )


@dataclass
class Case:
    """One person or household needing help. May merge several messages."""
    case_id: str
    message_ids: list
    raw_texts: list
    received_at: str                    # time of the FIRST message
    # extracted by Gemma
    people_count: Optional[int] = None
    vulnerable: list = field(default_factory=list)
    medical_need: Optional[bool] = None
    trapped: Optional[bool] = None
    water_level: str = "unknown"
    location_text: Optional[str] = None
    phone: Optional[str] = None
    confidence: dict = field(default_factory=dict)
    gemma_note: str = ""
    # filled by code
    area: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    missing: list = field(default_factory=list)
    needs_call: bool = False
    score: int = 0
    reasons: list = field(default_factory=list)
    status: str = "new"

    @classmethod
    def from_message(cls, case_id: str, msg: Message, ex: Extraction) -> "Case":
        return cls(case_id=case_id, message_ids=[msg.message_id], raw_texts=[msg.text],
                   received_at=msg.received_at, **asdict(ex))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

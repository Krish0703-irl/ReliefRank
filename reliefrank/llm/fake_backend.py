"""P1 - no-model backend. Rough regex guesses in the same JSON shape as Gemma.

Use it when Ollama is not ready yet (P2/P3 can code against it) or as a
last-resort demo fallback. Set LLM_BACKEND = "fake" in config.py.
"""
import json
import re

from reliefrank.llm.base import Backend

WATER_WORDS = [("roof", "roof"), ("neck", "neck"), ("chest", "chest"), ("waist", "waist"),
               ("knee", "knee"), ("ankle", "ankle")]
VULNERABLE_WORDS = {"elderly": ["old", "elderly", "grandmother", "grandfather", "aged"],
                    "child": ["child", "baby", "kid", "infant", "children"],
                    "pregnant": ["pregnant"], "disabled": ["disabled", "wheelchair", "bedridden"],
                    "injured": ["injured", "bleeding", "hurt"],
                    "medical": ["dialysis", "insulin", "oxygen", "heart", "medicine"]}


class FakeBackend(Backend):
    name = "fake"
    model = "regex"

    def generate(self, prompt: str) -> str:
        # The message to extract is the text after the last "MESSAGE:" marker.
        text = prompt.rsplit("MESSAGE:", 1)[-1].split("JSON:", 1)[0].strip()
        low = text.lower()
        phone = re.search(r"(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}", text)
        people = re.search(r"(\d{1,3})\s*(?:people|persons|members|of us|ppl)", low)
        water = next((lvl for word, lvl in WATER_WORDS if word in low), "unknown")
        vulnerable = [k for k, words in VULNERABLE_WORDS.items() if any(w in low for w in words)]
        loc = re.search(r"(?:\bat|\bin|\bnear)\s+([A-Z][\w]*(?:\s+[A-Z][\w]*)*)", text)
        result = {
            "people_count": int(people.group(1)) if people else None,
            "location_text": loc.group(1) if loc else None,
            "water_level": water,
            "phone": phone.group(0) if phone else None,
            "vulnerable": vulnerable,
            "needs": ["rescue"] if water != "unknown" else [],
            "urgency_reason": "regex guess (fake backend)",
            "confidence": {"people_count": 0.7, "location_text": 0.7, "water_level": 0.7,
                           "phone": 0.9 if phone else 0.0},
        }
        return json.dumps(result)

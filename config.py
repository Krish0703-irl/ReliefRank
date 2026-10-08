"""
ReliefRank settings. Every option is a variable here (no command-line arguments),
so every script runs with Ctrl+F5. The only secret, GEMINI_API_KEY, is read from .env.
"""
import os
from pathlib import Path

# ---------- Paths ----------
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "reliefrank.db"
DEMO_MESSAGES_PATH = DATA_DIR / "demo_messages.json"
PACKS_DIR = ROOT_DIR / "packs"
ACTIVE_PACK = "en"                      # language pack folder name inside packs/


def _load_env_file(path: Path) -> None:
    """Read KEY=VALUE lines from .env into os.environ (no extra package needed)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(ROOT_DIR / ".env")

# ---------- Gemma backend ----------
BACKEND = "ollama"                      # "ollama" (offline) or "gemini" (API)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:e4b"             # switch to the E2B tag if E4B is slow
GEMINI_MODEL = "gemma-4"                # confirm exact model name
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")   # set in .env, never here
LLM_TIMEOUT_SECONDS = 60
LLM_RETRIES = 1                         # retry broken JSON once

# ---------- Server ----------
HOST = "127.0.0.1"
PORT = 8000
OPEN_BROWSER = True

# ---------- Validation ----------
MIN_CONFIDENCE = 0.5                    # below this, location/phone counts as missing
REQUIRED_FIELDS = ("location_text", "phone")   # missing either -> needs a call

# ---------- Scoring (starting weights, tune against the labelled demo set) ----------
WEIGHTS = {
    "trapped": 25,
    "water_high": 20,                   # chest or roof
    "water_waist": 10,
    "medical": 15,                      # medical need or injured person
    "vulnerable_each": 10,
    "vulnerable_cap": 30,
    "person_each": 2,
    "people_cap": 10,
    "wait_per_10_min": 1,
    "wait_cap": 10,
    "repeat_messages": 5,               # several messages about the same case
}
SCORE_CAP = 100

# ---------- Dedupe ----------
USE_TEXT_DEDUPE = True                  # set False to keep phone matching only
TEXT_SIMILARITY_THRESHOLD = 0.8         # 0-1, how alike two messages must be

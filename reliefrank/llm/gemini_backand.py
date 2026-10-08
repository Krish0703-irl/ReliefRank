"""P1 - Gemma 4 hosted on the Gemini API (needs internet; for prototyping/backup).

Key goes in secrets_local.py (gitignored), never in config.py:
    GEMINI_API_KEY = "your-key"
"""
import os

import requests

from reliefrank.llm.base import Backend, LLMError, setting

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiBackend(Backend):
    name = "gemini"

    def __init__(self, model=None):
        self.model = model or setting("GEMINI_MODEL", "gemma-4-26b-a4b-it")
        self.timeout = setting("LLM_TIMEOUT_S", 120)
        self.api_key = setting("GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise LLMError("No GEMINI_API_KEY. Create secrets_local.py with GEMINI_API_KEY = \"...\"")

    def generate(self, prompt: str) -> str:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        try:
            r = requests.post(API.format(model=self.model), json=body, timeout=self.timeout,
                              headers={"x-goog-api-key": self.api_key})
        except requests.RequestException as e:
            raise LLMError(f"Gemini API unreachable: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"Gemini API error {r.status_code}: {r.text[:300]}")
        data = r.json()
        candidates = data.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise LLMError(f"Gemini API returned no text: {str(data)[:300]}")
        return text

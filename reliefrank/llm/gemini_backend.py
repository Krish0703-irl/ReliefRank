"""The same Gemma 4 family, hosted on the Gemini API. Needs internet.

Why this file exists:
    A backup for laptops too slow to run Gemma locally, and fast prototyping.
    It uses the exact same prompt as the local backend, so results are comparable.

Key: put GEMINI_API_KEY=your-key in the repo's .env file (never in config.py,
never committed). Model: config.GEMINI_MODEL, default gemma-4-26b-a4b-it.
"""
import requests

from reliefrank.llm.base import Backend, LLMError, read_env, setting

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiBackend(Backend):
    name = "gemini_api"
    offline = False

    def __init__(self, model=None):
        self.model = model or setting("GEMINI_MODEL", "gemma-4-26b-a4b-it")
        if not self.model.startswith("gemma-4-"):   # e.g. a placeholder "gemma-4"
            self.model = "gemma-4-26b-a4b-it"
        self.timeout = setting("LLM_TIMEOUT_S", 120)
        self.api_key = read_env("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY not found. Add GEMINI_API_KEY=... to the .env file.")

    def generate(self, prompt: str, schema: dict = None) -> str:
        # schema is not sent: Gemma models on this API may reject it. extract.py
        # parses and cleans the reply instead.
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        try:
            r = requests.post(API_URL.format(model=self.model), json=body,
                              headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(f"Gemini API unreachable (no internet?): {e}") from e
        if r.status_code != 200:
            raise LLMError(f"Gemini API error {r.status_code}: {r.text[:300]}")
        data = r.json()
        candidates = data.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise LLMError(f"Gemini API returned no text: {str(data)[:300]}")
        return text

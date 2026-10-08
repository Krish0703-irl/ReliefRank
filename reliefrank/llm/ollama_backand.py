"""P1 - local Gemma 4 through Ollama (fully offline).

Setup once:  ollama pull gemma4:e4b   (and gemma4:e2b as the fast fallback)
"""
import requests

from reliefrank.llm.base import Backend, LLMError, setting


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model=None, url=None):
        self.model = model or setting("OLLAMA_MODEL", "gemma4:e4b")
        self.url = (url or setting("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = setting("LLM_TIMEOUT_S", 120)

    def _post(self, body):
        try:
            return requests.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        except requests.ConnectionError as e:
            raise LLMError(f"Ollama not reachable at {self.url}. Start it with: ollama serve") from e
        except requests.Timeout as e:
            raise LLMError(f"Ollama timed out after {self.timeout}s (try gemma4:e2b)") from e

    def generate(self, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",   # Ollama forces valid JSON output
            "think": False,     # no reasoning block: faster, cleaner output
            "options": {"temperature": 0, "num_ctx": setting("OLLAMA_NUM_CTX", 8192)},
        }
        r = self._post(body)
        if r.status_code == 400 and "think" in r.text.lower():
            body.pop("think")   # older Ollama versions: retry without the flag
            r = self._post(body)
        if r.status_code == 404:
            raise LLMError(f"Model '{self.model}' not pulled. Run: ollama pull {self.model}")
        if r.status_code != 200:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]

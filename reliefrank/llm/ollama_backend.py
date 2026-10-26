"""Gemma 4 running locally through Ollama. Works with Wi-Fi off.

Why this file exists:
    This is the backend the pitch is built on. Rescue messages hold phone numbers,
    home locations and medical details, and floods take the internet down, so the
    model has to run on the volunteer's own laptop.

One-time setup (terminal):
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull gemma4:e4b        # main model
    ollama pull gemma4:e2b        # smaller fallback for slow laptops
"""
import requests

from reliefrank.llm.base import Backend, LLMError, setting


class OllamaBackend(Backend):
    name = "ollama"
    offline = True

    def __init__(self, model=None, url=None):
        self.model = model or setting("MODEL", "gemma4:e4b")
        self.url = (url or setting("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = setting("LLM_TIMEOUT_S", 120)

    def _post(self, body):
        try:
            return requests.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        except requests.ConnectionError as e:
            raise LLMError(f"Ollama is not running at {self.url}. Start it: ollama serve") from e
        except requests.Timeout as e:
            raise LLMError(f"Ollama took over {self.timeout}s. Try MODEL = \"gemma4:e2b\"") from e

    def generate(self, prompt: str, schema: dict = None) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            # A JSON Schema makes Ollama return exactly our fields; "json" = any valid JSON.
            "format": schema or "json",
            "think": False,                      # skip the reasoning block: faster
            "options": {"temperature": 0, "num_ctx": setting("OLLAMA_NUM_CTX", 8192)},
            "keep_alive": "30m",                 # keep the model loaded between messages
        }
        r = self._post(body)
        if r.status_code == 400 and "think" in r.text.lower():
            body.pop("think")                    # older Ollama: retry without the flag
            r = self._post(body)
        if r.status_code in (400, 500) and isinstance(body["format"], dict):
            body["format"] = "json"              # schema not supported: plain JSON mode
            r = self._post(body)
        if r.status_code == 404:
            raise LLMError(f"Model '{self.model}' is not downloaded. Run: ollama pull {self.model}")
        if r.status_code != 200:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]

    def check(self) -> None:
        """Is Ollama running here, and is this model downloaded?"""
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=5)
        except requests.RequestException as e:
            raise LLMError(f"Ollama is not running at {self.url}. Start it: ollama serve") from e
        if r.status_code != 200:
            raise LLMError(f"Ollama error {r.status_code} at {self.url}")
        tags = [m.get("name", "") for m in (r.json().get("models") or [])]
        # "gemma4:e4b" should also match a tag listed as "gemma4:e4b-instruct-q4"
        if not any(t == self.model or t.startswith(self.model) for t in tags):
            have = ", ".join(tags) if tags else "no models at all"
            raise LLMError(f"Model '{self.model}' is not downloaded (Ollama has: {have}). "
                           f"Run: ollama pull {self.model}")

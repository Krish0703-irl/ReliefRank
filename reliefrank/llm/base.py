"""P1 - one interface for every Gemma backend.

Every backend has generate(prompt) -> raw text reply.
extract.py builds the prompt and parses the JSON; backends never know about cases.

Settings are read from config.py (P2's file) if it exists, else the defaults here.
Variables P2 should add to config.py:
    LLM_BACKEND = "ollama"          # "ollama" | "gemini" | "fake"
    OLLAMA_MODEL = "gemma4:e4b"     # or "gemma4:e2b" if e4b is too slow
    OLLAMA_URL = "http://localhost:11434"
    GEMINI_MODEL = "gemma-4-26b-a4b-it"
    LLM_TIMEOUT_S = 120
    MIN_FIELD_CONFIDENCE = 0.6
The Gemini API key does NOT go in config.py (public repo). Put it in
secrets_local.py (gitignored):  GEMINI_API_KEY = "..."
"""
import time


class LLMError(Exception):
    """Backend could not produce a reply (server down, bad key, timeout...)."""


def setting(name, default):
    """Read a setting: secrets_local.py first, then config.py, then default."""
    for module_name in ("secrets_local", "config"):
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        if hasattr(module, name):
            return getattr(module, name)
    return default


class Backend:
    name = "base"
    model = ""

    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def timed_generate(self, prompt: str):
        start = time.perf_counter()
        reply = self.generate(prompt)
        return reply, time.perf_counter() - start


def get_backend(name: str = None) -> Backend:
    name = (name or setting("LLM_BACKEND", "ollama")).lower()
    if name == "ollama":
        from reliefrank.llm.ollama_backend import OllamaBackend
        return OllamaBackend()
    if name == "gemini":
        from reliefrank.llm.gemini_backend import GeminiBackend
        return GeminiBackend()
    if name == "fake":
        from reliefrank.llm.fake_backend import FakeBackend
        return FakeBackend()
    raise ValueError(f"Unknown LLM_BACKEND '{name}'. Use ollama, gemini or fake.")

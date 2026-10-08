"""One interface for every Gemma 4 backend.

Why this file exists:
    extract.py must not care WHERE Gemma runs. Every backend (local Ollama or the
    Gemini API) has the same method, generate(prompt) -> reply text, so switching
    backends is one line in config.py and nothing else changes.

Settings come from config.py. Defaults are used if a name is missing:
    BACKEND  = "ollama"            # "ollama" (offline) or "gemini_api"
    MODEL    = "gemma4:e4b"        # Ollama tag; "gemma4:e2b" if laptops are slow
    LANGUAGE = "en"                # folder in packs/
Optional extras config.py may define:
    GEMINI_MODEL = "gemma-4-26b-a4b-it"
    OLLAMA_URL = "http://localhost:11434"
    LLM_TIMEOUT_S = 120
    MIN_CONFIDENCE = 0.6
GEMINI_API_KEY is never in config.py: it is read from the environment or from
the .env file in the repo root (see .env.example).
"""
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class LLMError(Exception):
    """The backend could not give a reply (server down, model missing, bad key, timeout)."""


def setting(name, default):
    """Read a variable from config.py, or return the default."""
    try:
        import config
    except ImportError:
        return default
    return getattr(config, name, default)


def read_env(name):
    """Read a secret from the environment, else from REPO_ROOT/.env (KEY=value lines)."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == name:
                    return value.strip().strip('"').strip("'")
    return ""


class Backend:
    """Every backend sets name, model, offline and implements generate()."""
    name = "base"
    model = ""
    offline = True

    def generate(self, prompt: str, schema: dict = None) -> str:
        """Return the model's reply text. schema (JSON Schema) is a hint that
        backends may use to force the output shape; others ignore it."""
        raise NotImplementedError

    def timed_generate(self, prompt: str, schema: dict = None):
        start = time.perf_counter()
        reply = self.generate(prompt, schema)
        return reply, time.perf_counter() - start


def get_backend(name: str = None) -> Backend:
    """Build the backend chosen in config.BACKEND (or the name passed in)."""
    name = (name or setting("BACKEND", "ollama")).lower()
    if name == "ollama":
        from reliefrank.llm.ollama_backend import OllamaBackend
        return OllamaBackend()
    if name in ("gemini_api", "gemini"):
        from reliefrank.llm.gemini_backend import GeminiBackend
        return GeminiBackend()
    raise ValueError(f"Unknown BACKEND '{name}'. Use \"ollama\" or \"gemini_api\".")


def backend_info(backend: Backend = None) -> dict:
    """For GET /api/health and the "Local Gemma / Gemini API" badge."""
    try:
        backend = backend or get_backend()
    except (LLMError, ValueError) as e:
        return {"backend": setting("BACKEND", "ollama"), "model": None,
                "offline": None, "ready": False, "error": str(e)}
    label = "Local Gemma" if backend.offline else "Gemini API"
    return {"backend": backend.name, "model": backend.model, "offline": backend.offline,
            "label": label, "ready": True, "error": None}

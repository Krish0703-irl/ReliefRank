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


# config.py may use either name for the same setting
ALIASES = {"MODEL": ["MODEL", "OLLAMA_MODEL"],
           "LLM_TIMEOUT_S": ["LLM_TIMEOUT_S", "LLM_TIMEOUT_SECONDS"],
           "LANGUAGE": ["LANGUAGE", "ACTIVE_PACK"]}


def setting(name, default):
    """Read a variable from config.py, or return the default."""
    try:
        import config
    except ImportError:
        return default
    for alias in ALIASES.get(name, [name]):
        if hasattr(config, alias):
            return getattr(config, alias)
    return default


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

    def check(self) -> None:
        """Raise LLMError if this backend cannot answer right now.

        Building a backend only reads settings, so it succeeds even when the model
        server is down. /api/health calls this so the badge on the page tells the
        truth before a volunteer pastes 200 messages.
        """
        return None


CLOUD_NAMES = ("cloud", "openai_compat", "nvidia", "groq",
               "openrouter", "together", "openai", "local")


def _auto_backend() -> "Backend":
    """Offline first, cloud second. Used when BACKEND = "auto".

    Tries local Ollama, because rescue data should stay on the laptop. If no model
    is running there, falls back to the hosted API so the app still works on a
    machine with no model downloaded.
    """
    problems = []
    for name in ("ollama", "cloud"):
        try:
            backend = get_backend(name)
            backend.check()
            return backend
        except (LLMError, ValueError) as e:
            problems.append(f"{name}: {e}")
    raise LLMError(
        "No working backend.\n  " + "\n  ".join(problems)
        + "\nEither run a local model (ollama serve) or add an API key to .env "
          "(see .env.example)."
    )


def get_backend(name: str = None) -> Backend:
    """Build the backend chosen in config.BACKEND (or the name passed in)."""
    name = (name or setting("BACKEND", "ollama")).lower()
    if name == "auto":
        return _auto_backend()
    if name == "ollama":
        from reliefrank.llm.ollama_backend import OllamaBackend
        return OllamaBackend()
    if name in ("gemini_api", "gemini"):
        from reliefrank.llm.gemini_backend import GeminiBackend
        return GeminiBackend()
    if name in CLOUD_NAMES:
        from reliefrank.llm.cloud_backend import CloudBackend
        # "cloud" means "whatever CLOUD_PROVIDER says"; a provider name pins it.
        provider = None if name in ("cloud", "openai_compat") else name
        return CloudBackend(provider=provider)
    raise ValueError(
        f"Unknown BACKEND '{name}'. Use \"auto\", \"ollama\", \"cloud\" "
        f"or a provider name ({', '.join(CLOUD_NAMES[2:])})."
    )


def label_for(backend: Backend) -> str:
    """Text for the badge on the page."""
    if backend.offline:
        return "Local Gemma" if backend.name == "ollama" else "Local model"
    if backend.name.startswith("cloud:"):
        return f"{backend.name.split(':', 1)[1].title()} cloud"
    return "Gemini API"


def backend_info(backend: Backend = None, verify: bool = False) -> dict:
    """For GET /api/health and the badge on the page.

    verify=True actually calls the model, so "ready" means ready. It costs one
    tiny request, so the page asks for it once on load, not on every poll.
    """
    chosen = setting("BACKEND", "ollama")
    try:
        backend = backend or get_backend()
    except (LLMError, ValueError) as e:
        return {"backend": chosen, "model": None, "offline": None, "label": "No model",
                "ready": False, "verified": False, "error": str(e)}

    info = {"backend": backend.name, "model": backend.model, "offline": backend.offline,
            "label": label_for(backend), "ready": True, "verified": False, "error": None}
    if verify:
        try:
            backend.check()
            info["verified"] = True
        except LLMError as e:
            info.update(ready=False, verified=True, error=str(e))
    return info

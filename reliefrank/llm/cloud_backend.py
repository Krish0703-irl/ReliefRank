"""Gemma 4 (or any chat model) through a hosted OpenAI-compatible API.

Why this file exists:
    Not every volunteer laptop can run Gemma locally, and not every demo machine
    has a model downloaded at all. Every major host (NVIDIA build.nvidia.com,
    Groq, OpenRouter, Together, OpenAI, and local servers like llama.cpp or
    LM Studio) speaks the same POST /chat/completions shape, so ONE backend
    covers all of them. Only the base URL, the key and the model name change.

    The offline Ollama backend is still the pitch. This is the fallback for
    "no model on this machine", and it uses the exact same prompt, so the
    extracted fields are comparable.

Setup (NVIDIA, the default):
    1. Get a free key at https://build.nvidia.com  (keys look like nvapi-...)
    2. Put it in the repo's .env file:   NVIDIA_API_KEY=nvapi-xxxxxxxx
    3. In config.py:                     BACKEND = "cloud"
    4. Run run.py as usual.

To check which model names your key can actually use:
    python -m reliefrank.llm.cloud_backend
"""
import json
import re

import requests

from reliefrank.llm.base import Backend, LLMError, read_env, setting

# Each preset is just: where to post, which key to read, which model to ask for.
# "key_env" is the name of the variable in .env. Add a provider by adding a row.
PROVIDERS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "model": "google/gemma-4-31b-it",
        "signup": "https://build.nvidia.com (free key, no card)",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "gemma2-9b-it",
        "signup": "https://console.groq.com/keys (free tier)",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "google/gemma-3-27b-it:free",
        "signup": "https://openrouter.ai/keys (has :free models)",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "model": "google/gemma-2-27b-it",
        "signup": "https://api.together.ai/settings/api-keys",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
        "signup": "https://platform.openai.com/api-keys (paid)",
    },
    # A model served on this machine or the LAN by llama.cpp, LM Studio, vLLM.
    # Still offline-safe: nothing leaves the network.
    "local": {
        "base_url": "http://localhost:8080/v1",
        "key_env": "LOCAL_API_KEY",
        "model": "local-model",
        "signup": "llama.cpp --server / LM Studio / vLLM on this machine",
    },
}

# Any provider accepts this as a fallback key name, so one .env line can drive all.
GENERIC_KEY_ENV = "CLOUD_API_KEY"

_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)


class CloudBackend(Backend):
    """One hosted chat model behind the same generate() every backend has."""

    name = "cloud"
    offline = False

    def __init__(self, provider=None, model=None, base_url=None, api_key=None):
        self.provider = (provider or setting("CLOUD_PROVIDER", "nvidia")).lower()
        if self.provider not in PROVIDERS:
            raise LLMError(
                f"Unknown CLOUD_PROVIDER '{self.provider}'. "
                f"Use one of: {', '.join(sorted(PROVIDERS))}."
            )
        preset = PROVIDERS[self.provider]

        # config.py may override any part of a preset; the preset fills the rest.
        self.base_url = (base_url or setting("CLOUD_BASE_URL", "")
                         or preset["base_url"]).rstrip("/")
        self.model = model or setting("CLOUD_MODEL", "") or preset["model"]
        self.timeout = setting("LLM_TIMEOUT_S", 120)
        self.key_env = preset["key_env"]
        self.name = f"cloud:{self.provider}"
        # A local server usually needs no key at all.
        self.needs_key = self.provider != "local"

        self.api_key = api_key or read_env(self.key_env) or read_env(GENERIC_KEY_ENV)
        if not self.api_key and self.needs_key:
            raise LLMError(
                f"{self.key_env} not found. Add this line to the repo's .env file:\n"
                f"    {self.key_env}=your-key-here\n"
                f"Get a key from: {preset['signup']}"
            )
        # Remembers whether this model accepted response_format, so we only
        # discover that once per run instead of on every message.
        self._json_mode = True

    # ---------------- HTTP ----------------
    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, body):
        try:
            return requests.post(f"{self.base_url}/chat/completions", json=body,
                                 headers=self._headers(), timeout=self.timeout)
        except requests.ConnectionError as e:
            raise LLMError(
                f"Cannot reach {self.base_url} (no internet, or the local server is not "
                f"running). The offline backend is BACKEND = \"ollama\"."
            ) from e
        except requests.Timeout as e:
            raise LLMError(
                f"{self.provider} took over {self.timeout}s. Raise LLM_TIMEOUT_SECONDS "
                f"in config.py, or pick a smaller model."
            ) from e
        except requests.RequestException as e:
            raise LLMError(f"{self.provider} request failed: {e}") from e

    def _explain(self, r):
        """Turn an HTTP error into a sentence a volunteer can act on."""
        snippet = (r.text or "")[:300]
        if r.status_code in (401, 403):
            return (f"{self.provider} rejected the key ({r.status_code}). Check {self.key_env} "
                    f"in .env — copy it again from {PROVIDERS[self.provider]['signup']}.")
        if r.status_code == 404:
            return (f"{self.provider} has no model called '{self.model}' ({r.status_code}). "
                    f"Run `python -m reliefrank.llm.cloud_backend` to list the names your "
                    f"key can use, then set CLOUD_MODEL in config.py.")
        if r.status_code == 429:
            return (f"{self.provider} rate limit reached (429). Wait a minute, or paste fewer "
                    f"messages at a time.")
        if r.status_code in (402, 413):
            return f"{self.provider} refused the request ({r.status_code}): {snippet}"
        return f"{self.provider} error {r.status_code}: {snippet}"

    # ---------------- the one method every backend has ----------------
    def generate(self, prompt: str, schema: dict = None) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,          # same as the Ollama backend: repeatable answers
            "max_tokens": 700,         # one small JSON record needs no more
            "stream": False,
        }
        # Ask the host to guarantee valid JSON when it supports that. Hosts that
        # do not just return normal text, which extract.py already cleans.
        if schema and self._json_mode:
            body["response_format"] = {"type": "json_object"}

        r = self._post(body)

        # Some models/hosts reject response_format. Drop it and never try again.
        if r.status_code in (400, 404, 422) and "response_format" in body:
            lowered = (r.text or "").lower()
            if "response_format" in lowered or "json" in lowered:
                self._json_mode = False
                body.pop("response_format")
                r = self._post(body)

        if r.status_code != 200:
            raise LLMError(self._explain(r))

        try:
            data = r.json()
        except ValueError as e:
            raise LLMError(f"{self.provider} sent a reply that is not JSON: {r.text[:200]}") from e

        if isinstance(data.get("error"), dict):     # some hosts answer 200 with an error body
            raise LLMError(f"{self.provider} error: {data['error'].get('message', data['error'])}")

        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"{self.provider} returned no choices: {str(data)[:300]}")
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        # Reasoning models put the answer in one field and their thinking in another.
        if not text.strip():
            text = message.get("reasoning_content") or ""
        text = _THINK_BLOCK.sub("", text)
        if not text.strip():
            raise LLMError(f"{self.provider} returned an empty reply: {str(data)[:300]}")
        return text

    # ---------------- used by /api/health ----------------
    def check(self) -> None:
        """Raise LLMError if this backend cannot answer right now."""
        self.generate('Reply with only this JSON: {"ok": true}', schema={})

    def list_models(self) -> list:
        """Model names this key is allowed to use (for confirming CLOUD_MODEL)."""
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(),
                             timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(f"Could not list models from {self.base_url}: {e}") from e
        if r.status_code != 200:
            raise LLMError(self._explain(r))
        return sorted(m.get("id", "") for m in (r.json().get("data") or []))


# ---------------- run this file directly to check a key and find model names ----------------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    try:
        b = CloudBackend()
    except LLMError as e:
        sys.exit(f"\n{e}\n")

    print(f"provider : {b.provider}")
    print(f"base_url : {b.base_url}")
    print(f"model    : {b.model}")
    print(f"key      : {b.key_env} = {'set' if b.api_key else 'MISSING'}\n")

    try:
        names = b.list_models()
        print(f"{len(names)} model(s) this key can use:")
        gemma = [n for n in names if "gemma" in n.lower()]
        for n in (gemma or names)[:40]:
            print(f"  {n}")
        if gemma:
            print(f"\n({len(names)} total; showing the Gemma ones. "
                  f"Set CLOUD_MODEL in config.py to one of these.)")
        if b.model not in names:
            print(f"\nWARNING: CLOUD_MODEL '{b.model}' is not in that list.")
    except LLMError as e:
        print(f"Could not list models: {e}")

    print("\nSending one test message...")
    try:
        print("Reply:", b.generate('Reply with only this JSON: {"ok": true}', schema={}).strip())
        print("\nBackend works. Set BACKEND = \"cloud\" in config.py.")
    except LLMError as e:
        sys.exit(f"\nTest call failed:\n{e}\n")

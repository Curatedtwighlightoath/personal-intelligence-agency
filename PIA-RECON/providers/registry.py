"""
Provider registry — loads department_config rows from SQLite and
instantiates the right LLMProvider.

Allow-list of providers is exported so api.py can validate PUT requests
without reaching into registry internals.
"""

import json
import os

from db import get_connection

from .base import LLMProvider, ProviderError

ALLOWED_PROVIDERS = ("anthropic", "openai", "ollama")


def _load_row(department: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM department_config WHERE department = ?", (department,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ProviderError(
            f"No department_config row for '{department}'. "
            f"Seed it via db.init_db() or set it via the API."
        )
    return {k: row[k] for k in row.keys()}


def _resolve_key(api_key_ref: str | None) -> str:
    if not api_key_ref:
        return ""
    value = os.environ.get(api_key_ref)
    if not value:
        raise ProviderError(
            f"Environment variable '{api_key_ref}' is unset. "
            f"Set it in the process environment before running."
        )
    return value


def get_provider(department: str = "watchdog") -> LLMProvider:
    """
    Instantiate the LLMProvider configured for `department`.

    Reads department_config, resolves api_key_ref against os.environ (NEVER
    stores secrets in the DB), and builds the right provider class.
    """
    row = _load_row(department)
    provider = row["provider"]
    model = row["model"]
    api_key = _resolve_key(row.get("api_key_ref"))
    base_url = row.get("base_url") or None

    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model, api_key=api_key, base_url=base_url)

    if provider in ("openai", "ollama"):
        # Ollama is an OpenAI-compatible endpoint; default its base_url if
        # caller left it blank but selected the 'ollama' provider name.
        if provider == "ollama" and not base_url:
            base_url = "http://localhost:11434/v1"
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(model=model, api_key=api_key, base_url=base_url)

    raise ProviderError(
        f"Unknown provider '{provider}'. Allowed: {ALLOWED_PROVIDERS}"
    )


def parse_extra(raw: str | None) -> dict:
    """department_config.extra is stored as JSON text; decode defensively."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

"""LLM provider abstraction — pluggable backends per department."""

from .base import LLMProvider, ProviderError
from .registry import get_provider, ALLOWED_PROVIDERS

__all__ = ["LLMProvider", "ProviderError", "get_provider", "ALLOWED_PROVIDERS"]

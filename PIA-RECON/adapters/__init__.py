"""
Source adapter registry.
Each adapter is a plain async function — no class hierarchy.
"""

from typing import Callable, Awaitable
from models import RawItem

# Type alias for adapter functions
AdapterFn = Callable[[dict], Awaitable[list[RawItem]]]

# Registry — adapters self-register at import time
ADAPTERS: dict[str, AdapterFn] = {}


def register_adapter(source_type: str):
    """Decorator to register a source adapter function."""
    def decorator(fn: AdapterFn) -> AdapterFn:
        ADAPTERS[source_type] = fn
        return fn
    return decorator


async def fetch_source(source_type: str, source_config: dict) -> list[RawItem]:
    """Fetch items from a source. Returns normalized raw items for LLM evaluation."""
    if source_type not in ADAPTERS:
        raise ValueError(f"No adapter registered for source type: {source_type}")
    adapter = ADAPTERS[source_type]
    return await adapter(source_config)


# Import adapters to trigger registration
from adapters import rss, github  # noqa: E402, F401

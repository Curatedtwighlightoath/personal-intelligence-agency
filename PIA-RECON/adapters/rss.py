"""
RSS/Atom feed adapter.

source_config schema:
{
    "feed_url": "https://blog.google/technology/ai/rss/",
    "max_items": 20  # optional, default 20
}
"""

import hashlib
from datetime import datetime, timezone

import feedparser
import httpx

from models import RawItem
from adapters import register_adapter


@register_adapter("rss")
async def fetch_rss(source_config: dict) -> list[RawItem]:
    """Fetch and parse an RSS/Atom feed, return normalized items."""
    feed_url = source_config.get("feed_url")
    if not feed_url:
        raise ValueError("source_config missing required field: feed_url")

    max_items = source_config.get("max_items", 20)

    # Fetch raw feed content over HTTP — feedparser can parse URLs directly
    # but using httpx gives us timeout control and async compatibility.
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(feed_url, follow_redirects=True)
        response.raise_for_status()

    feed = feedparser.parse(response.text)

    if feed.bozo and not feed.entries:
        # bozo flag means parse error — only bail if we got zero entries
        raise ValueError(f"Feed parse failed for {feed_url}: {feed.bozo_exception}")

    items = []
    for entry in feed.entries[:max_items]:
        # Extract the best available content
        content = _extract_content(entry)
        link = entry.get("link", "")
        title = entry.get("title", "Untitled")

        # Normalize published date
        published_at = _parse_date(entry)

        items.append(
            RawItem(
                source_url=link,
                title=title,
                content=content,
                published_at=published_at,
                item_hash=_hash_item(link, title),
                raw_data={
                    "feed_url": feed_url,
                    "entry_id": entry.get("id", link),
                    "author": entry.get("author"),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                },
            )
        )

    return items


def _extract_content(entry: dict) -> str:
    """Pull the richest text content from a feed entry.

    Priority: content > summary > description > title.
    Feeds are inconsistent — some stuff everything in summary,
    others use content:encoded, some have both.
    """
    # content:encoded (common in WordPress/full-text feeds)
    if "content" in entry and entry["content"]:
        # content is a list of dicts with 'value' keys
        parts = [c.get("value", "") for c in entry["content"] if c.get("value")]
        if parts:
            return _strip_html(parts[0])

    # summary / description (most common)
    if entry.get("summary"):
        return _strip_html(entry["summary"])

    if entry.get("description"):
        return _strip_html(entry["description"])

    return entry.get("title", "")


def _strip_html(text: str) -> str:
    """Quick and dirty HTML tag removal. Good enough for feed content
    destined for LLM evaluation — we don't need perfect parsing."""
    import re

    # Remove tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Decode common entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        clean = clean.replace(entity, char)
    return clean


def _parse_date(entry: dict) -> str | None:
    """Extract and normalize published date to ISO format."""
    # feedparser normalizes dates into *_parsed tuples
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                continue

    # Fallback: raw string fields
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            return raw  # Store as-is, better than nothing

    return None


def _hash_item(url: str, title: str) -> str:
    """Generate a dedup hash for an RSS item."""
    content = f"{url}|{title}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
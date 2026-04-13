"""
LLM-driven social post drafter.

Mirrors matcher.py: build a JSON-Schema tool, call the marketing
department's configured provider via call_structured, return a list of
{content, rationale} dicts. The caller persists them.
"""

import json
from typing import Optional

from providers import get_provider

from .platforms import PlatformSpec, get_spec


# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the marketing writer for a small product team.

Your job: draft social-media post variants for ONE platform, ONE topic, and
ONE product. Return exactly the number of variants requested, each a
genuinely different angle — not reworded versions of the same idea.

For every variant provide:
1. `content` — the final post text, ready to paste. Respect the platform's
   format rules and char limit. No meta commentary, no "Here is..." preface.
2. `rationale` — one sentence explaining the angle you took and why it fits
   the audience + tone.

Write like a human operator, not a press release. Favor specificity over
buzzwords. Do not invent product features or claims that aren't in the
product profile."""


DRAFT_TOOL = {
    "name": "submit_drafts",
    "description": "Submit N social-post variants for the requested platform and topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "description": "Ordered list of post variants.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The ready-to-paste post text.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "One-sentence rationale for this variant's angle.",
                        },
                    },
                    "required": ["content", "rationale"],
                },
            }
        },
        "required": ["variants"],
    },
}


# ── Prompt assembly ─────────────────────────────────────────────────────────

def _product_block(product: dict) -> str:
    """Render the product row into a prompt-friendly block."""
    key_messages = product.get("key_messages") or []
    if isinstance(key_messages, str):
        try:
            key_messages = json.loads(key_messages)
        except json.JSONDecodeError:
            key_messages = []

    links = product.get("links") or []
    if isinstance(links, str):
        try:
            links = json.loads(links)
        except json.JSONDecodeError:
            links = []

    lines = [
        f"Name: {product.get('name') or '(unset)'}",
        f"One-liner: {product.get('one_liner') or '(unset)'}",
        f"Audience: {product.get('audience') or '(unset)'}",
        f"Tone: {product.get('tone') or '(unset)'}",
    ]
    if key_messages:
        lines.append("Key messages:")
        for m in key_messages:
            lines.append(f"  - {m}")
    if links:
        lines.append("Links:")
        for link in links:
            if isinstance(link, dict):
                lines.append(f"  - {link.get('label', '')}: {link.get('url', '')}")
    return "\n".join(lines)


def _build_user_message(
    product: dict,
    platform: str,
    spec: PlatformSpec,
    topic: str,
    variants: int,
) -> str:
    limit_note = (
        f"Strict character limit: {spec.char_limit}. Count carefully."
        if spec.char_limit
        else "No hard character limit, but respect the target length in the format rules."
    )
    return (
        f"<platform>{spec.label}</platform>\n"
        f"<format_rules>{spec.format_rules}</format_rules>\n"
        f"<limit>{limit_note}</limit>\n\n"
        f"<product>\n{_product_block(product)}\n</product>\n\n"
        f"<topic>{topic}</topic>\n\n"
        f"Draft {variants} distinctly different post variant(s) for this "
        f"platform on this topic. Use the submit_drafts tool."
    )


# ── Core ─────────────────────────────────────────────────────────────────────

async def draft_posts(
    platform: str,
    topic: str,
    product: dict,
    variants: int = 3,
    department: str = "marketing",
) -> list[dict]:
    """
    Draft `variants` social posts for `platform` on `topic`, informed by
    `product`. Returns a list of {content, rationale, variant_index} dicts.

    Any Twitter variant over the char limit is re-asked once with an explicit
    shortening directive. If still over, we keep it but tag the rationale so
    the UI can surface the overrun.
    """
    if variants < 1 or variants > 10:
        raise ValueError("variants must be between 1 and 10")

    spec = get_spec(platform)
    provider = get_provider(department)

    tool_input = await provider.call_structured(
        system=SYSTEM_PROMPT,
        user=_build_user_message(product, platform, spec, topic, variants),
        tool_schema=DRAFT_TOOL["input_schema"],
        tool_name=DRAFT_TOOL["name"],
        max_tokens=2048,
    )

    raw_variants = (tool_input or {}).get("variants") or []
    if not raw_variants:
        raise RuntimeError(f"Drafter returned no variants: {tool_input!r}")

    drafts: list[dict] = []
    for idx, v in enumerate(raw_variants[:variants]):
        content = (v.get("content") or "").strip()
        rationale = (v.get("rationale") or "").strip()

        if spec.char_limit and len(content) > spec.char_limit:
            # One shortening retry per offending variant.
            content, rationale = await _reshorten(
                provider, spec, content, rationale
            )

        drafts.append({
            "content": content,
            "rationale": rationale,
            "variant_index": idx,
        })

    return drafts


async def _reshorten(
    provider,
    spec: PlatformSpec,
    content: str,
    rationale: str,
) -> tuple[str, str]:
    """Ask the provider once more to trim a single over-limit post."""
    tool = {
        "name": "submit_shortened",
        "description": "Return a shortened version under the char limit.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    }
    system = (
        f"You shorten social posts to fit the {spec.label} char limit of "
        f"{spec.char_limit}. Preserve meaning and tone. Return only the "
        f"trimmed post via the submit_shortened tool."
    )
    user = (
        f"Current post ({len(content)} chars, limit {spec.char_limit}):\n\n"
        f"{content}\n\n"
        f"Return a version under {spec.char_limit} characters."
    )
    try:
        out = await provider.call_structured(
            system=system,
            user=user,
            tool_schema=tool["input_schema"],
            tool_name=tool["name"],
            max_tokens=512,
        )
        shortened = (out or {}).get("content", "").strip()
    except Exception as e:
        return content, (rationale + f" [shorten retry failed: {e}]").strip()

    if shortened and len(shortened) <= spec.char_limit:
        return shortened, rationale
    # Still over — flag it in the rationale but keep the shorter of the two.
    final = shortened if shortened and len(shortened) < len(content) else content
    flag = f"[OVER LIMIT: {len(final)}/{spec.char_limit}]"
    return final, (rationale + " " + flag).strip()

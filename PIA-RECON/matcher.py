"""
LLM matching layer.
Takes raw items + match criteria, returns structured match results.
Uses Claude Sonnet for cost-effective high-frequency scoring.

Requires ANTHROPIC_API_KEY environment variable.
"""

import json
import os
from dataclasses import dataclass

import anthropic

from models import RawItem

# ── Config ───────────────────────────────────────────────────────────────────

# Max items per API call — keeps prompts focused and token usage predictable.
# RSS feeds with 20+ items get chunked into groups of this size.
BATCH_CHUNK_SIZE = 10

# Model choice — Sonnet for cost-effective high-frequency scoring.
# Haiku would be cheaper but less reliable on nuanced matching criteria.
MODEL = "claude-sonnet-4-20250514"

# ── Data ─────────────────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    matched: bool
    relevance_score: float  # 0.0 - 1.0
    reason: str
    summary: str


# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a matching engine for an intelligence monitoring system.

Your job: evaluate whether source items match the operator's watch criteria.

For EACH item provided, determine:
1. Whether it matches the criteria (boolean)
2. A relevance score from 0.0 to 1.0
3. A brief reason explaining why it does or doesn't match
4. A 1-2 sentence summary of the item's content

Scoring guide:
- 0.9-1.0: Direct, exact match to criteria
- 0.7-0.8: Strong match, clearly relevant
- 0.5-0.6: Tangentially related, might be of interest
- 0.2-0.4: Weak connection, probably not what the operator wants
- 0.0-0.1: No relevance

Be precise. The operator has defined specific criteria — don't over-match on vaguely related content.
A score >= 0.5 with matched=true means the item will be surfaced to the operator, so don't waste their attention."""

EVAL_TOOL = {
    "name": "report_matches",
    "description": "Report match evaluation results for all items.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evaluations": {
                "type": "array",
                "description": "One evaluation per item, in the same order as presented.",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_index": {
                            "type": "integer",
                            "description": "Zero-based index of the item being evaluated.",
                        },
                        "matched": {
                            "type": "boolean",
                            "description": "Whether this item matches the watch criteria.",
                        },
                        "relevance_score": {
                            "type": "number",
                            "description": "Relevance score from 0.0 to 1.0.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of match/non-match rationale.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "1-2 sentence summary of the item content.",
                        },
                    },
                    "required": ["item_index", "matched", "relevance_score", "reason", "summary"],
                },
            }
        },
        "required": ["evaluations"],
    },
}


def _build_user_message(items: list[RawItem], match_criteria: str) -> str:
    """Format items and criteria into the user prompt."""
    items_block = []
    for i, item in enumerate(items):
        # Truncate content to keep tokens reasonable — 500 chars is enough
        # for the LLM to assess relevance without blowing up the context.
        content_preview = item.content[:500]
        if len(item.content) > 500:
            content_preview += "..."

        items_block.append(
            f"<item index=\"{i}\">\n"
            f"  <title>{item.title}</title>\n"
            f"  <url>{item.source_url}</url>\n"
            f"  <content>{content_preview}</content>\n"
            f"  <published>{item.published_at or 'unknown'}</published>\n"
            f"</item>"
        )

    return (
        f"<watch_criteria>{match_criteria}</watch_criteria>\n\n"
        f"Evaluate these {len(items)} items against the watch criteria:\n\n"
        + "\n\n".join(items_block)
        + "\n\nUse the report_matches tool to submit your evaluations."
    )


# ── Core Functions ───────────────────────────────────────────────────────────

def _get_client() -> anthropic.AsyncAnthropic:
    """Get an async Anthropic client. Raises if API key not set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it before running the watchdog server."
        )
    return anthropic.AsyncAnthropic(api_key=api_key)


async def evaluate_item(item: RawItem, match_criteria: str) -> MatchResult:
    """
    Evaluate a single item against criteria.
    Convenience wrapper around _evaluate_chunk for one-off checks.
    """
    results = await _evaluate_chunk([item], match_criteria)
    if not results:
        return MatchResult(matched=False, relevance_score=0.0, reason="Evaluation returned no results", summary="")
    return results[0]


async def evaluate_batch(
    items: list[RawItem],
    match_criteria: str,
    score_threshold: float = 0.5,
) -> list[tuple[RawItem, MatchResult]]:
    """
    Evaluate a batch of items against criteria.
    Chunks large batches into groups of BATCH_CHUNK_SIZE for focused evaluation.
    Returns only items that meet the score threshold.
    """
    if not items:
        return []

    # Chunk items to keep prompts focused
    all_results: list[tuple[RawItem, MatchResult]] = []

    for chunk_start in range(0, len(items), BATCH_CHUNK_SIZE):
        chunk = items[chunk_start : chunk_start + BATCH_CHUNK_SIZE]

        try:
            match_results = await _evaluate_chunk(chunk, match_criteria)
        except Exception as e:
            # Log and skip the whole chunk on API failure
            print(f"[matcher] Chunk evaluation failed: {e}")
            continue

        for item, result in zip(chunk, match_results):
            if result.matched and result.relevance_score >= score_threshold:
                all_results.append((item, result))

    return all_results


async def _evaluate_chunk(items: list[RawItem], match_criteria: str) -> list[MatchResult]:
    """
    Send a chunk of items to Sonnet for evaluation via tool use.
    Returns one MatchResult per item, in order.
    """
    client = _get_client()

    response = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "report_matches"},
        messages=[
            {"role": "user", "content": _build_user_message(items, match_criteria)}
        ],
    )

    # Extract the tool use block
    tool_input = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "report_matches":
            tool_input = block.input
            break

    if not tool_input or "evaluations" not in tool_input:
        print(f"[matcher] Unexpected response structure: {response.content}")
        return [
            MatchResult(matched=False, relevance_score=0.0, reason="Evaluation failed — no tool response", summary="")
            for _ in items
        ]

    evaluations = tool_input["evaluations"]

    # Build results list — handle missing or out-of-order evaluations
    results: list[MatchResult] = []
    eval_by_index = {e["item_index"]: e for e in evaluations}

    for i in range(len(items)):
        e = eval_by_index.get(i)
        if e:
            results.append(
                MatchResult(
                    matched=bool(e.get("matched", False)),
                    relevance_score=float(e.get("relevance_score", 0.0)),
                    reason=e.get("reason", ""),
                    summary=e.get("summary", ""),
                )
            )
        else:
            # LLM skipped this item — treat as non-match
            print(f"[matcher] Warning: no evaluation returned for item {i} ('{items[i].title}')")
            results.append(
                MatchResult(matched=False, relevance_score=0.0, reason="Item not evaluated by LLM", summary="")
            )

    return results
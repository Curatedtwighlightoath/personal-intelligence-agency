"""
Fact extractor — pulls atomic claims out of free text via the R&D
department's configured LLM (see providers.registry / department_config).

A "fact" is a short subject + statement + confidence triple. We don't
commit to a (subject, predicate, object) shape yet because the access
pattern is unknown; the migration comment in 0003_memory_items.sql
spells out when to revisit.

Auto-extraction runs on every ingest (per the v0 product decision: "make
it loud and obvious what's wrong"). If the bill spikes, swap the call
site in rd.db.ingest to gate this behind an explicit flag.
"""

from dataclasses import dataclass

from providers import get_provider

DEPARTMENT = "rd"

# Cap so a single ingest can't spawn an unbounded fact list. The LLM is
# instructed to be selective; this is a defense-in-depth ceiling.
MAX_FACTS_PER_DOC = 50


@dataclass
class ExtractedFact:
    subject: str
    statement: str
    confidence: float


SYSTEM_PROMPT = """You are a fact-extraction engine for a personal knowledge base.

Read the provided document and emit the atomic, standalone claims it makes.

A good fact:
- Is a single assertion that stands on its own without surrounding context.
- Has a clear `subject` (a short noun phrase — the thing the fact is about).
- Has a `statement` rewritten as a complete sentence (don't just copy a phrase).
- Has a `confidence` from 0.0 to 1.0 reflecting how strongly the source asserts it.

Confidence guide:
- 0.9-1.0: Definitive assertion, clearly stated as fact.
- 0.7-0.8: Stated with mild hedging ("typically", "usually").
- 0.5-0.6: Speculative or attributed to a third party.
- Below 0.5: Don't emit — too weak to be useful.

Be selective. Prefer 5 strong, atomic facts over 30 vague restatements.
If the document is opinion, narrative, or contains no extractable claims,
return an empty list."""


EXTRACT_TOOL = {
    "name": "report_facts",
    "description": "Report atomic facts extracted from the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "description": "Atomic claims found in the document. May be empty.",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "Short noun phrase identifying what the fact is about.",
                        },
                        "statement": {
                            "type": "string",
                            "description": "The fact itself, as a complete standalone sentence.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "How strongly the source asserts this, 0.0 to 1.0.",
                        },
                    },
                    "required": ["subject", "statement", "confidence"],
                },
            }
        },
        "required": ["facts"],
    },
}


async def extract_facts(text: str) -> list[ExtractedFact]:
    """
    Run the R&D LLM over `text` and return its extracted facts.

    On provider failure, returns an empty list and logs — ingest still
    succeeds at the doc-chunk level. This matches matcher.py's
    fail-soft pattern: a flaky LLM should never lose user content.
    """
    if not text or not text.strip():
        return []

    provider = get_provider(DEPARTMENT)
    user_msg = (
        "<document>\n"
        f"{text}\n"
        "</document>\n\n"
        "Use the report_facts tool to emit atomic claims from this document."
    )

    try:
        tool_input = await provider.call_structured(
            system=SYSTEM_PROMPT,
            user=user_msg,
            tool_schema=EXTRACT_TOOL["input_schema"],
            tool_name=EXTRACT_TOOL["name"],
            max_tokens=4096,
        )
    except Exception as e:
        print(f"[rd.extractor] Provider call failed: {e}")
        return []

    raw = tool_input.get("facts") if isinstance(tool_input, dict) else None
    if not isinstance(raw, list):
        print(f"[rd.extractor] Unexpected tool output: {tool_input!r}")
        return []

    out: list[ExtractedFact] = []
    for f in raw[:MAX_FACTS_PER_DOC]:
        if not isinstance(f, dict):
            continue
        subject = str(f.get("subject", "")).strip()
        statement = str(f.get("statement", "")).strip()
        try:
            confidence = float(f.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if not subject or not statement:
            continue
        confidence = max(0.0, min(1.0, confidence))
        out.append(ExtractedFact(subject=subject, statement=statement, confidence=confidence))
    return out

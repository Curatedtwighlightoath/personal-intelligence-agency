"""
Seed the watchdog database with curated RSS watch targets.

Usage:
    py seed_targets.py          # Add all targets
    py seed_targets.py --list   # Just show what would be added
    py seed_targets.py --reset  # Clear all targets and hits, then re-seed

Targets are idempotent — running this multiple times won't create duplicates.
"""

import sys
from db import init_db, get_connection, now_utc
from models import WatchTarget


# ── Target Definitions ───────────────────────────────────────────────────────
#
# Criteria are written for "wide" matching — cast a broad net, then
# use the rating system to train your intuition on what's noise vs signal.
#
# Each target has a focused criteria string that tells the matcher
# what YOU care about, not just "anything from this source."

TARGETS = [
    # ── AI Models & Research ─────────────────────────────────────────────

    WatchTarget(
        name="OpenAI Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://openai.com/blog/rss.xml",
            "max_items": 15,
        },
        match_criteria=(
            "New model releases or updates (GPT, o-series, DALL-E, Sora, Codex). "
            "API changes, deprecations, or new endpoints. "
            "Agent frameworks, function calling improvements, or tool use updates. "
            "Significant research papers on reasoning, alignment, or safety. "
            "Ignore: hiring posts, corporate news, diversity reports, partnerships "
            "that don't involve technical changes."
        ),
        cadence="0 */6 * * *",
    ),

    WatchTarget(
        name="Google AI Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://blog.google/technology/ai/rss",
            "max_items": 15,
        },
        match_criteria=(
            "Gemini model releases, updates, or benchmark results. "
            "New AI tools, APIs, or developer platform changes. "
            "Significant research on reasoning, multimodal AI, or agents. "
            "Android/Pixel AI integration features relevant to on-device inference. "
            "Ignore: consumer product marketing, Google Workspace fluff, "
            "general corporate announcements."
        ),
        cadence="0 */6 * * *",
    ),

    WatchTarget(
        name="Google DeepMind Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://deepmind.google/blog/rss.xml",
            "max_items": 15,
        },
        match_criteria=(
            "New model architectures or training breakthroughs. "
            "Gemini-related research or capabilities. "
            "Agent and reasoning research (planning, tool use, multi-step). "
            "Reinforcement learning advances applicable to LLM agents. "
            "Ignore: protein folding, weather prediction, game-playing AI, "
            "and other domain-specific research unless it has clear implications "
            "for general-purpose AI agents."
        ),
        cadence="0 */12 * * *",
    ),

    WatchTarget(
        name="Google Research Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://research.google/blog/rss",
            "max_items": 15,
        },
        match_criteria=(
            "LLM research, reasoning, or agent capabilities. "
            "New model architectures or training techniques. "
            "Tool use, code generation, or multi-step planning research. "
            "On-device ML advances relevant to mobile inference. "
            "Ignore: quantum computing, hardware, networking, "
            "and other non-AI research unless directly applicable to LLM systems."
        ),
        cadence="0 */12 * * *",
    ),

    # ── Developer Tooling & Frameworks ───────────────────────────────────

    WatchTarget(
        name="LangChain Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://blog.langchain.com/rss/",
            "max_items": 15,
        },
        match_criteria=(
            "LangGraph updates, new features, or architecture patterns. "
            "Agent orchestration patterns, multi-agent designs. "
            "New integrations relevant to the Anthropic/Claude ecosystem. "
            "Production deployment patterns for agentic systems. "
            "Ignore: pure marketing, customer case studies without "
            "technical depth, hiring announcements."
        ),
        cadence="0 */6 * * *",
    ),

    WatchTarget(
        name="Hacker News (AI/LLM)",
        source_type="rss",
        source_config={
            "feed_url": "https://hnrss.org/newest?q=LLM+OR+Claude+OR+MCP+OR+%22language+model%22+OR+%22AI+agent%22",
            "max_items": 20,
        },
        match_criteria=(
            "Open-source agent frameworks or tools. "
            "MCP (Model Context Protocol) servers, clients, or ecosystem tools. "
            "Claude or Anthropic product launches, API changes, pricing updates. "
            "Novel LLM application patterns (RAG, tool use, multi-agent). "
            "Developer experience improvements for AI/LLM tooling. "
            "Ignore: AI hype pieces, opinion articles without technical substance, "
            "startup funding announcements, regulatory/policy discussions."
        ),
        cadence="0 */4 * * *",
    ),

    WatchTarget(
        name="Meta Engineering Blog",
        source_type="rss",
        source_config={
            "feed_url": "https://engineering.fb.com/feed/",
            "max_items": 15,
        },
        match_criteria=(
            "Llama model releases, fine-tuning guides, or benchmark results. "
            "Open-source AI tooling releases (PyTorch updates, inference optimizations). "
            "Agent or reasoning research from FAIR. "
            "Infrastructure insights relevant to self-hosted LLM deployment. "
            "Ignore: social media features, VR/metaverse, ads platform, "
            "content moderation that isn't AI-technique-focused."
        ),
        cadence="0 */12 * * *",
    ),

    WatchTarget(
        name="Meta Research",
        source_type="rss",
        source_config={
            "feed_url": "https://research.facebook.com/feed/",
            "max_items": 15,
        },
        match_criteria=(
            "LLM research, reasoning, or agent capabilities from FAIR. "
            "New open-weight model releases or training techniques. "
            "Tool use, code generation, or planning research. "
            "Ignore: computer vision for social media, AR/VR research, "
            "computational photography, and other non-LLM topics."
        ),
        cadence="0 */12 * * *",
    ),

    # ── Community-Generated Feeds (no native RSS) ────────────────────────

    WatchTarget(
        name="Anthropic News (via Olshansk)",
        source_type="rss",
        source_config={
            "feed_url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
            "max_items": 15,
        },
        match_criteria=(
            "Claude model releases, updates, or capability changes. "
            "MCP protocol updates or ecosystem announcements. "
            "API changes, new features, pricing updates. "
            "Agent-related tooling or framework releases. "
            "Safety research with practical implications for model behavior. "
            "Ignore: hiring, corporate governance, policy statements "
            "without technical substance."
        ),
        cadence="0 */4 * * *",
    ),

    WatchTarget(
        name="Anthropic Engineering (via Olshansk)",
        source_type="rss",
        source_config={
            "feed_url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
            "max_items": 15,
        },
        match_criteria=(
            "Infrastructure and systems engineering for LLM deployment. "
            "Prompt engineering techniques or best practices. "
            "Claude Code updates or developer tooling. "
            "MCP server development patterns. "
            "Anything relevant to building production systems with Claude. "
            "Ignore: general HR or culture posts."
        ),
        cadence="0 */6 * * *",
    ),

    WatchTarget(
        name="Anthropic Research (via Olshansk)",
        source_type="rss",
        source_config={
            "feed_url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
            "max_items": 15,
        },
        match_criteria=(
            "Constitutional AI or alignment research updates. "
            "Reasoning, planning, or agent capability research. "
            "Interpretability breakthroughs. "
            "Scaling laws or training methodology advances. "
            "Anything that signals upcoming Claude model capabilities. "
            "Ignore: policy papers without technical depth."
        ),
        cadence="0 */6 * * *",
    ),
    # ── GitHub Repos (releases) ────────────────────────────────────────

    WatchTarget(
        name="Claude Code Releases",
        source_type="github_api",
        source_config={
            "owner": "anthropics",
            "repo": "claude-code",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new release or pre-release. "
            "Focus on: MCP improvements, new commands, security changes, "
            "performance improvements, and breaking changes. "
            "All releases are relevant — this is a core tool."
        ),
        cadence="0 */4 * * *",
    ),

    WatchTarget(
        name="MCP Python SDK Releases",
        source_type="github_api",
        source_config={
            "owner": "modelcontextprotocol",
            "repo": "python-sdk",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new release. Focus on: new transport types, "
            "breaking API changes, new tool patterns, and server framework updates. "
            "All releases are relevant — this is PIA's foundation."
        ),
        cadence="0 */6 * * *",
    ),

    WatchTarget(
        name="MCP Spec Releases",
        source_type="github_api",
        source_config={
            "owner": "modelcontextprotocol",
            "repo": "specification",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new spec version. Protocol changes, new capability types, "
            "auth framework updates, or transport spec changes. "
            "All releases are relevant."
        ),
        cadence="0 */12 * * *",
    ),

    WatchTarget(
        name="MCP TypeScript SDK Releases",
        source_type="github_api",
        source_config={
            "owner": "modelcontextprotocol",
            "repo": "typescript-sdk",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new release. Client-side MCP changes, "
            "new transport implementations, or inspector tool updates. "
            "Relevant for understanding the MCP client ecosystem."
        ),
        cadence="0 */12 * * *",
    ),

    WatchTarget(
        name="LangGraph Releases",
        source_type="github_api",
        source_config={
            "owner": "langchain-ai",
            "repo": "langgraph",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new release. Focus on: new graph patterns, "
            "state management improvements, checkpointing changes, "
            "multi-agent orchestration features, and breaking changes."
        ),
        cadence="0 */12 * * *",
    ),

    WatchTarget(
        name="CrewAI Releases",
        source_type="github_api",
        source_config={
            "owner": "crewAIInc",
            "repo": "crewAI",
            "watch_type": "releases",
            "max_items": 10,
        },
        match_criteria=(
            "Any new release. Focus on: new crew patterns, "
            "tool integration changes, memory/knowledge improvements, "
            "multi-agent orchestration features, and breaking changes."
        ),
        cadence="0 */12 * * *",
    ),
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if "--list" in sys.argv:
        print(f"{'NAME':<40} {'TYPE':<12} {'CADENCE':<15} FEED URL")
        print("─" * 110)
        for t in TARGETS:
            url = t.source_config.get("feed_url", "")
            print(f"{t.name:<40} {t.source_type:<12} {t.cadence:<15} {url}")
        print(f"\n{len(TARGETS)} targets total")
        return

    init_db()
    conn = get_connection()

    if "--reset" in sys.argv:
        print("Resetting database...")
        conn.execute("DELETE FROM hits")
        conn.execute("DELETE FROM seen_items")
        conn.execute("DELETE FROM watch_targets")
        conn.commit()
        print("All targets, hits, and seen items cleared.\n")

    added = 0
    skipped = 0

    for target in TARGETS:
        existing = conn.execute(
            "SELECT id FROM watch_targets WHERE name = ?", (target.name,)
        ).fetchone()

        if existing:
            print(f"  SKIP  {target.name} (already exists)")
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO watch_targets 
               (id, name, source_type, source_config, match_criteria, cadence,
                enabled, last_checked_at, last_hit_at, consecutive_failures)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            target.to_row(),
        )
        print(f"  ADD   {target.name}")
        added += 1

    conn.commit()
    conn.close()

    print(f"\nDone: {added} added, {skipped} skipped")
    print(f"Total targets in DB: {added + skipped}")
    print(f"\nRun a check with:  py test_e2e.py")
    print(f"Or via MCP server: python server.py")


if __name__ == "__main__":
    main()
"""
Run checks on all enabled targets in the database.

Usage:
    set ANTHROPIC_API_KEY=sk-ant-...
    py run_checks.py              # Check all enabled targets
    py run_checks.py --target "OpenAI Blog"  # Check one target by name
    py run_checks.py --dry-run    # Fetch feeds but skip LLM scoring
"""

import asyncio
import sys
import os

from db import init_db, get_connection, DB_PATH
from models import WatchTarget
from server import _check_single_target


async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY first.")
        print('  PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        sys.exit(1)

    init_db()
    conn = get_connection()

    # Get targets
    target_filter = None
    if "--target" in sys.argv:
        idx = sys.argv.index("--target")
        if idx + 1 < len(sys.argv):
            target_filter = sys.argv[idx + 1]

    if target_filter:
        rows = conn.execute(
            "SELECT * FROM watch_targets WHERE name = ? AND enabled = TRUE",
            (target_filter,),
        ).fetchall()
        if not rows:
            print(f"No enabled target found with name: {target_filter}")
            sys.exit(1)
    else:
        rows = conn.execute(
            "SELECT * FROM watch_targets WHERE enabled = TRUE ORDER BY name"
        ).fetchall()

    targets = [WatchTarget.from_row(r) for r in rows]
    print(f"DB: {DB_PATH}")
    print(f"Targets to check: {len(targets)}\n")

    total_new_items = 0
    total_new_hits = 0
    errors = []

    for i, target in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {target.name}")
        print(f"  Source: {target.source_type} | {target.source_config.get('feed_url', 'N/A')[:60]}")

        result = await _check_single_target(target)
        status = result.get("status", "unknown")

        if status == "ok":
            new_items = result.get("new_items", 0)
            new_hits = result.get("new_hits", 0)
            total_new_items += new_items
            total_new_hits += new_hits
            print(f"  Result: {new_items} new items → {new_hits} hits")

            if result.get("hits"):
                for h in result["hits"]:
                    score = h["score"]
                    indicator = "■" if score >= 0.7 else "□"
                    print(f"    {indicator} [{score:.2f}] {h['title'][:70]}")
                    print(f"           {h['reason'][:80]}")
        elif status in ("adapter_not_implemented", "matcher_not_implemented"):
            print(f"  Result: {status} — {result.get('message', '')}")
        elif status == "fetch_error":
            err = result.get("error", "unknown")
            print(f"  Result: FETCH ERROR — {err[:80]}")
            errors.append((target.name, err))
        else:
            print(f"  Result: {status}")

        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Targets checked: {len(targets)}")
    print(f"  New items found: {total_new_items}")
    print(f"  New hits:        {total_new_hits}")
    if errors:
        print(f"  Errors:          {len(errors)}")
        for name, err in errors:
            print(f"    • {name}: {err[:60]}")

    # DB stats
    hit_count = conn.execute(
        "SELECT COUNT(*) as c FROM chunks WHERE kind = 'hit'"
    ).fetchone()["c"]
    unseen = conn.execute(
        "SELECT COUNT(*) as c FROM chunks WHERE kind = 'hit' AND seen = FALSE"
    ).fetchone()["c"]
    seen_items = conn.execute("SELECT COUNT(*) as c FROM seen_items").fetchone()["c"]
    print(f"\n  DB totals: {hit_count} hits ({unseen} unseen), {seen_items} seen items")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
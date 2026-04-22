"""
Department config CLI — writes directly to Postgres, no API dependency.

Usage:
    python -m providers.cli list
    python -m providers.cli get watchdog
    python -m providers.cli set watchdog \\
        --provider openai --model gpt-4o-mini \\
        --api-key-ref OPENAI_API_KEY
    python -m providers.cli test watchdog
"""

import argparse
import asyncio
import json
import sys

# Allow running as `python -m providers.cli` from PIA-RECON/
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from db import get_connection, init_db, now_utc
from providers import ALLOWED_PROVIDERS, get_provider
from providers.base import ProviderError


def _fmt(row) -> dict:
    updated_at = row["updated_at"]
    return {
        "department":  row["department"],
        "provider":    row["provider"],
        "model":       row["model"],
        "api_key_ref": row["api_key_ref"],
        "base_url":    row["base_url"],
        "extra":       row["extra"] or {},
        "updated_at":  updated_at.isoformat() if updated_at else None,
    }


def cmd_list(_args) -> int:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM department_config ORDER BY department"
        ).fetchall()
    finally:
        conn.close()
    print(json.dumps([_fmt(r) for r in rows], indent=2))
    return 0


def cmd_get(args) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM department_config WHERE department = %s",
            (args.department,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        print(f"No config for department '{args.department}'", file=sys.stderr)
        return 1
    print(json.dumps(_fmt(row), indent=2))
    return 0


def cmd_set(args) -> int:
    if args.provider not in ALLOWED_PROVIDERS:
        print(f"provider must be one of {ALLOWED_PROVIDERS}", file=sys.stderr)
        return 2

    extra = json.loads(args.extra) if args.extra else {}

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM department_config WHERE department = %s",
            (args.department,),
        ).fetchone()
        if exists:
            conn.execute(
                """UPDATE department_config
                   SET provider = %s, model = %s, api_key_ref = %s,
                       base_url = %s, extra = %s, updated_at = %s
                   WHERE department = %s""",
                (args.provider, args.model, args.api_key_ref, args.base_url,
                 extra, now_utc(), args.department),
            )
        else:
            conn.execute(
                """INSERT INTO department_config
                   (department, provider, model, api_key_ref, base_url, extra)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (args.department, args.provider, args.model, args.api_key_ref,
                 args.base_url, extra),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM department_config WHERE department = %s",
            (args.department,),
        ).fetchone()
    finally:
        conn.close()
    print(json.dumps(_fmt(row), indent=2))
    return 0


def cmd_test(args) -> int:
    from models import RawItem
    from matcher import _evaluate_chunk
    import time

    try:
        provider = get_provider(args.department)
    except ProviderError as e:
        print(f"ProviderError: {e}", file=sys.stderr)
        return 1

    dummy = RawItem(
        title="Anthropic releases Claude 4.6",
        source_url="https://example.com/x",
        content="Anthropic announced Claude 4.6 with improved reasoning.",
    )

    async def run():
        start = time.monotonic()
        res = await _evaluate_chunk([dummy], "AI model releases", provider)
        return res, int((time.monotonic() - start) * 1000)

    try:
        results, latency_ms = asyncio.run(run())
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    out = {
        "ok": True,
        "latency_ms": latency_ms,
        "sample": {
            "matched": results[0].matched,
            "score": results[0].relevance_score,
            "reason": results[0].reason,
        },
    }
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    init_db()

    parser = argparse.ArgumentParser(prog="providers.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all department configs")

    g = sub.add_parser("get", help="Show one department's config")
    g.add_argument("department")

    s = sub.add_parser("set", help="Create or update a department config")
    s.add_argument("department")
    s.add_argument("--provider", required=True, choices=ALLOWED_PROVIDERS)
    s.add_argument("--model", required=True)
    s.add_argument("--api-key-ref", default=None,
                   help="Name of env var to read (e.g. ANTHROPIC_API_KEY)")
    s.add_argument("--base-url", default=None)
    s.add_argument("--extra", default=None,
                   help="JSON string of extra options (temperature, etc.)")

    t = sub.add_parser("test", help="Round-trip a tiny prompt and report latency")
    t.add_argument("department")

    args = parser.parse_args(argv)
    return {
        "list": cmd_list, "get": cmd_get, "set": cmd_set, "test": cmd_test,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

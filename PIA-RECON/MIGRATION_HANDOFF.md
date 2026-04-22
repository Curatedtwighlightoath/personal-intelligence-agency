# Postgres + pgvector Migration — Handoff

Status as of session 2 (2026-04-21). All call-site work is **code-complete**;
nothing has been exercised against a live database yet. Delete this file
after the smoke test passes.

## Decisions locked in

| Topic | Choice | Reason |
|---|---|---|
| Driver | `psycopg[binary,pool]>=3.2.0` | Sync + async in one lib; `%s` placeholders are the minimum-change path from SQLite's `?` |
| Migration tool | Numbered SQL files + tiny Python runner | Fits existing "no ORM, just SQL" ethos |
| Schema types | `jsonb`, `boolean`, `timestamptz` | Proper Postgres types; drop manual `json.dumps/loads` and ISO-string helpers |
| Atomic unit | Single `memory_items` table with `kind` discriminator | Don't split facts vs chunks yet — R&D isn't built, access pattern unknown |
| Embedding | OpenAI `text-embedding-3-small`, dim **1536** | User pick; `model_ref` column gives clean swap path |
| Postgres host | Native Windows installer + pgvector extension | User pick |
| Legacy data | Throwaway, no migration script | User confirmed |

## Work completed (session 1)

- [x] `requirements.txt` — added `psycopg[binary,pool]>=3.2.0` and `pgvector>=0.3.0`
- [x] `.env.example` — added `DATABASE_URL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`
- [x] `migrations/__init__.py` — empty package marker
- [x] `migrations/0001_init.sql` — parity schema with jsonb/boolean/timestamptz
- [x] `migrations/0002_seeds.sql` — seed `department_config` + default product row
- [x] `migrations/0003_memory_items.sql` — pgvector extension + `memory_items` + HNSW cosine index
- [x] `migrations/runner.py` — `python -m migrations.runner [--status]`
- [x] `db.py` — psycopg3 rewrite. `get_connection()`/`init_db()`/`now_utc()` preserved. `DB_PATH` removed.
- [x] `models.py` — dropped `json.dumps/loads`, datetimes for timestamps.

## Work completed (session 2 — this session)

All eight pending call sites converted from sqlite3/`?` to psycopg3/`%s`,
plus jsonb cleanup. One additional file (`marketing/drafter.py`) was
discovered to have stale `json.loads` on `key_messages`/`links` that the
prior session's grep didn't catch — fixed in the same pass.

- [x] **`db.py`** — Added `psycopg.adapters.register_dumper(dict, JsonbDumper)`
      and the same for `list`. Without this, the docstring's promise that
      "callers should not `json.dumps()` them" was a lie for `list` params
      (psycopg3 default-adapts `list` → Postgres array, which doesn't fit
      a `jsonb` column). `JsonbDumper` import verified to exist in
      psycopg `3.3.3` installed locally.
- [x] **`marketing/db.py`** — `?` → `%s`, dropped `_row_to_product`'s
      `json.loads` branch (jsonb returns dict/list directly), dropped
      `json.dumps(km/ln)` at the upsert site. `import json` removed.
- [x] **`api.py`** — Docstring updated to Postgres. All 33 placeholders
      converted. `json.dumps(value)` for `source_config` in `update_target`
      removed. `json.loads(row["extra"] ...)` and `json.dumps(body.extra
      ...)` in the department config endpoints removed. `import json`
      removed (no remaining uses). Boolean comparisons use truthy semantics
      everywhere — no `== 1` patterns to fix.
- [x] **`server.py`** — Docstring/print updated. `from db import ...,
      DB_PATH` → dropped `DB_PATH`. The `print(f"DB: {DB_PATH}")` startup
      line removed. All 23 placeholders converted. `json.dumps(value)` in
      `update_watch_target` removed. `import json`, `from pathlib import
      Path` (was already unused) removed.
      **One non-trivial SQL change:** `INSERT OR IGNORE INTO seen_items
      ...` → `INSERT INTO seen_items ... ON CONFLICT (target_id,
      item_hash) DO NOTHING`. SQLite's `OR IGNORE` syntax has no Postgres
      equivalent; the conflict target had to be named explicitly.
- [x] **`scheduler.py`** — single placeholder swap.
- [x] **`run_checks.py`** — `from db import ..., DB_PATH` → dropped
      `DB_PATH`. `print(f"DB: {DB_PATH}")` removed. One placeholder.
- [x] **`seed_targets.py`** — three placeholders. (Note: line 125 has
      `?q=...` inside a feed URL string — that's a URL query string,
      not an SQL placeholder, intentionally left alone.)
- [x] **`providers/registry.py`** — placeholder swap, docstring update.
      Removed dead-code `parse_extra` helper (was never called outside
      its own module — verified by repo-wide grep). `import json` removed.
- [x] **`providers/cli.py`** — Docstring updated. All 7 placeholders
      converted. `json.dumps(extra)` in INSERT/UPDATE removed. `_fmt`
      now ISO-formats `updated_at` (datetime is no longer pre-stringified
      by the DB layer, so `json.dumps` of the formatted dict would
      otherwise raise `TypeError`). `import json` retained — still used
      legitimately to print CLI output and to parse the user-supplied
      `--extra` JSON string.
- [x] **`marketing/drafter.py`** *(extra, not in original handoff)* —
      Dropped two stale `if isinstance(..., str): json.loads(...)`
      branches in `_product_block`. Those existed for the SQLite path
      where `key_messages`/`links` came back as JSON-encoded text;
      under jsonb they're already dict/list, so the branches were dead
      code. `import json` removed.
- [x] **`README.md`** — Backend description updated to Postgres+pgvector.
      Added a full "Database setup" section with Windows-first
      instructions (native installer + pgvector DLL/build, with Docker
      Desktop + `pgvector/pgvector:pg16` called out as a fallback) and a
      shorter macOS/Linux note. Install section now includes
      `python -m migrations.runner`. Project layout entry for `db.py`
      retitled and `migrations/` added. Two stale "watchdog.db" /
      "SQLite" references in body text fixed.

## Verification done

- `python -m py_compile` over all twelve changed files → clean.
- `python -c "from psycopg.types.json import JsonbDumper"` → succeeds
  on the installed psycopg `3.3.3`. Adapter registration in `db.py`
  will work.
- Repo-wide greps for `\?` inside `execute(...)`, `json.loads`/`json.dumps`,
  `DB_PATH`, `INSERT OR`, and `LIKE '%...%'` all return either zero
  hits or only legitimate non-SQL hits (CLI output JSON, URL query
  strings, doc references). No remaining migration debt that I can
  see by static analysis.

## Verification NOT done

- **Live DB smoke test.** Postgres isn't running on this box and the
  user wasn't ready to bring it up this session. Nothing has been
  executed against a real database. The full smoke list from the
  prior handoff is therefore still pending — see "Smoke test" below.

## Smoke test — to run once Postgres + pgvector are up

```powershell
# From PIA-RECON/, with .env loaded and DATABASE_URL set:

python -m migrations.runner --status      # expect: 3 pending
python -m migrations.runner               # expect: applies 0001, 0002, 0003
python -m migrations.runner --status      # expect: 3 applied, 0 pending

# Boot the API and confirm the env-check banner prints:
uvicorn api:app --port 8000
# expect a "env check: ANTHROPIC_API_KEY=present|missing ..." line

# In another shell:
curl http://localhost:8000/api/departments
#   → JSON list of seeded department rows (watchdog/marketing/rd)

curl -X POST http://localhost:8000/api/import-seed
#   → {"status":"ok","added":<N>,"skipped":0}

# Marketing round-trip — exercises the jsonb adapter for list params:
curl -X PUT http://localhost:8000/api/marketing/product \
     -H "Content-Type: application/json" \
     -d '{"name":"PIA","key_messages":["a","b"],"links":[{"label":"x","url":"https://y"}]}'
curl http://localhost:8000/api/marketing/product
#   → key_messages/links come back as real arrays, not strings

# Manual hit run (requires ANTHROPIC_API_KEY in env for matcher):
curl -X POST http://localhost:8000/api/run-check
#   → exercises the seen_items ON CONFLICT path
```

## Gotchas to keep an eye on during the smoke test

1. **`JsonbDumper` registration is global.** `db.py` registers it for
   *all* `dict` and `list` parameters at import time. If anything in
   the codebase ever wants to send a Python `list` to a real Postgres
   array column (e.g. `text[]`), it will silently get sent as `jsonb`
   instead. There are no such columns today (verified by reading
   `0001_init.sql`), but if R&D adds one this is the first thing to
   revisit.
2. **`updated_at` in `providers/cli.py`.** Old DB returned ISO strings;
   new DB returns `datetime`. `_fmt` now ISO-formats it before printing.
   If you see `TypeError: Object of type datetime is not JSON
   serializable` from the CLI, that helper regressed.
3. **`%` in SQL strings.** No `LIKE '%foo%'` literals exist today, but
   psycopg3 will treat any literal `%` as a parameter marker if the
   query is parameterized. Add new ones as `%%`.
4. **Autocommit is off.** Read-only endpoints that don't `.commit()`
   leave a transaction open until `.close()` (which rolls back). Safe,
   but if `pg_stat_activity` shows `idle in transaction` under load,
   that's the cause.
5. **Boolean coercion.** Already audited — no surviving `== 1` /
   `== 0` checks against `enabled`/`seen`. `WatchTarget.from_row` and
   `Hit.from_row` keep the defensive `bool(...)` cast even though
   psycopg3 already returns real bools.
6. **`MarketingPanel.tsx` mentions SQLite** in two user-facing strings
   (lines 148, 429). Cosmetic, not functional — fix when next touching
   that file.

## Public surface of `db.py`

```python
from db import get_connection, init_db, now_utc

conn = get_connection()          # psycopg3 Connection, row_factory=dict_row
try:
    row = conn.execute("SELECT * FROM x WHERE id = %s", (xid,)).fetchone()
    conn.execute(
        "INSERT INTO y (cfg) VALUES (%s)",
        ({"a": 1, "b": [2, 3]},),  # dict/list adapt straight to jsonb
    )
    conn.commit()
finally:
    conn.close()

init_db()                         # delegates to migrations.runner.apply_pending()
ts = now_utc()                    # tz-aware datetime; psycopg3 → timestamptz
```

`DB_PATH` is gone — anything still importing it is a bug.

## File inventory

```
PIA-RECON/
├── db.py                         rewritten + jsonb adapter registration
├── models.py                     jsonb + datetime
├── migrations/
│   ├── __init__.py
│   ├── runner.py
│   ├── 0001_init.sql
│   ├── 0002_seeds.sql
│   └── 0003_memory_items.sql
├── api.py                        ✓ converted
├── server.py                     ✓ converted (incl. seen_items ON CONFLICT)
├── scheduler.py                  ✓ converted
├── run_checks.py                 ✓ converted
├── seed_targets.py               ✓ converted
├── providers/registry.py         ✓ converted (parse_extra removed)
├── providers/cli.py              ✓ converted (datetime serialization fix)
├── marketing/db.py               ✓ converted
├── marketing/drafter.py          ✓ stale json.loads removed
├── requirements.txt              psycopg[binary,pool], pgvector
└── .env.example                  DATABASE_URL, EMBEDDING_*
```

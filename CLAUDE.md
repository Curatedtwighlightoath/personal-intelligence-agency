# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo orientation

Personal Intelligence Agency (PIA) is a self-hosted, multi-department automation
platform. Three departments share one Postgres+pgvector database and one
provider abstraction:

- **Watchdog** — RSS/GitHub polling + LLM relevance matcher. *Implemented.*
- **Marketing** — singleton product profile + social-post drafter. *Implemented.*
- **R&D** — fact + doc memory over `memory_items`, exposed via MCP for use
  from coding agents like VS Code's Claude Code. *Implemented.*

All backend code lives under `PIA-RECON/`. The React 19 + Vite frontend lives
under `PIA-RECON/PIA/`. Setup instructions (DB, Python, Node, env vars) are in
the top-level `README.md`; do not duplicate them here.

## Big-picture architecture

The same Python package is loaded by three independent processes:

- **`api.py`** (`uvicorn api:app`) — HTTP API for the React UI. Owns the
  scheduler lifespan: APScheduler is started in `lifespan()` and runs enabled
  watch targets on cron. Migrations auto-apply on boot via `init_db()`.
- **`server.py`** (`python server.py`) — MCP stdio server. Same DB, same
  helpers; just a different transport. Tools from all three departments
  (watchdog, marketing, R&D) are registered on a single `FastMCP` instance.
- **`run_checks.py`** — one-shot CLI for cron use without uvicorn.

The shared seam is `db.get_connection()` and the per-department modules
(`marketing/`, `rd/`, plus watchdog's logic in `matcher.py` + `adapters/`).
Adding a feature usually means: new SQL helpers in a department module, then
wire them as both an HTTP route in `api.py` and an `@mcp.tool()` in `server.py`.

Provider calls go through `providers.registry.get_provider(department)`, which
reads `department_config` and resolves `api_key_ref` against `os.environ` at
call time. Secrets never live in the DB.

## R&D memory layer (`rd/`)

`memory_items` is a single table with a `kind` discriminator (`'doc'`, `'fact'`,
extensible). Facts and chunks deliberately share storage — split when access
patterns demand it (see `migrations/0003_memory_items.sql:4`).

- **Ingest pipeline** (`rd.db.ingest`): chunk text → embed → insert N
  `kind='doc'` rows → run extractor → insert M `kind='fact'` rows. Every row
  from one ingest call shares a `source_id` UUID stored in `metadata.source_id`
  (chunks) or `metadata.source_doc_id` (facts). This is metadata-only by design;
  promote to a real FK column when the join becomes hot.
- **Chunking** (`rd/chunker.py`) is structure-aware: paragraph splits first
  (blank-line delimited), sentence packing for oversize paragraphs, hard
  break only as a last resort. **Do not replace with fixed-length char/token
  windows** — the chunking strategy was chosen because vectors over coherent
  units rank better than vectors over arbitrary windows that straddle
  sentences.
- **Embeddings** (`rd/embeddings.py`) require `EMBEDDING_DIMENSION` to match
  the `vector(N)` column declared in migration 0003. Changing the embedding
  model to one with a different dimension requires a re-embed migration, not
  just an env-var swap.
- **Fact extraction runs automatically on every ingest** (`rd/extractor.py`).
  This is intentional — surface cost issues loudly. Pivot to manual-trigger
  if bills spike.
- **Search** is pure cosine via pgvector's `<=>` operator with the HNSW index.
  Hybrid (BM25 + vector) is not implemented yet.

## Postgres conventions that bite

- **Placeholders are `%s`, not `?`.** psycopg3 throws on `?`. The codebase
  was migrated from SQLite — assume any new code mirroring an old pattern
  may have stale `?` placeholders to fix.
- **`dict` and `list` adapt to `jsonb` globally** (registered in `db.py`).
  Callers do not `json.dumps()` jsonb params. *Exception:* `list[float]`
  for `vector` columns must be a `numpy.ndarray`, or it'll be sent as jsonb
  and fail the insert. `pgvector.psycopg.register_vector(conn)` is required
  per-connection for vector columns to work.
- **Autocommit is off.** Writes need explicit `.commit()`. Read-only callers
  that only `.close()` are safe (close rolls back any open transaction).
  An idle endpoint that forgets to commit will show as
  `idle in transaction` in `pg_stat_activity`.
- **`ON CONFLICT (cols) DO NOTHING`**, not SQLite's `INSERT OR IGNORE`. The
  conflict target must be named explicitly.
- **Literal `%` in SQL must be `%%`** in parameterized queries (e.g. inside
  `LIKE` patterns). No such literals exist today; add new ones with `%%`.
- **Booleans are real bools.** No `== 1` / `== 0` against `enabled`/`seen`.

## Provider + department conventions

- LLM calls are async (`AnthropicProvider`, `OpenAIProvider`). MCP tools that
  invoke providers must be `async def`; FastMCP supports both. See
  `server.py:179` for the pattern.
- All structured-output prompts use the same shape: a JSON-Schema "tool" passed
  to `provider.call_structured(...)`, returning the tool's input dict. Mirror
  `matcher.EVAL_TOOL` or `rd.extractor.EXTRACT_TOOL` when adding new ones.
- New department? Pattern is: `<dept>/db.py` (thin SQL helpers) + optional
  `<dept>/<feature>.py` (LLM logic) + a Pydantic-bodied block in `api.py`
  + an `@mcp.tool()` block at the bottom of `server.py`. `marketing/` is the
  cleanest template for a domain-table department; `rd/` is the template for
  a memory-layer department.

## Common commands

Run from `PIA-RECON/` with the venv active and `.env` exported
(`set -a; source .env; set +a`).

```bash
# Static check before committing — fast, no DB needed
python -m py_compile <files>

# Migration ledger — what's applied vs pending, no writes
python -m migrations.runner --status

# Apply pending migrations explicitly (otherwise auto-applied at API boot)
python -m migrations.runner

# API + scheduler (port 8000)
uvicorn api:app --reload --port 8000

# MCP server (stdio); for use from VS Code Claude Code or Claude Desktop
python server.py

# One-shot check of all enabled watch targets
python run_checks.py

# Frontend dev server (port 5173, CORS open)
cd PIA && npm run dev
```

There is no test suite yet. Verification is `py_compile` + the smoke tests
in `MIGRATION_HANDOFF.md`. When asked to "run tests," surface that gap rather
than inventing test commands.

## Docker / homelab deploy

`PIA-RECON/Dockerfile` + `PIA-RECON/docker-compose.yml` bring up `db`
(pgvector/pg16, named volume, healthcheck, loopback-bound) + `api`
(waits for db healthy). The MCP server is intentionally not in compose — it
speaks stdio and is launched by the operator's editor pointed at this
Postgres over Tailscale or an SSH tunnel.

```bash
cd PIA-RECON
cp .env.example .env   # edit values; DATABASE_URL host=db inside compose
docker compose up -d --build
docker compose logs -f api
```

Frontend is **not** built into the image — `.dockerignore` excludes `PIA/`.

## Branch model and commit hygiene

- `main` is stable. `test` is the integration branch. `claude/*` and other
  feature branches merge into `test` first.
- Do not force-push `main` or `test`.
- Enable the pre-commit secret scanner once per clone:
  ```bash
  git config core.hooksPath .githooks
  ```
  CI (`.github/workflows/secret-scan.yml`) runs the same scan; bypassing the
  hook with `--no-verify` will fail in CI.
- Never commit `.env` (only `.env.example`). The scanner rejects any staged
  path matching `.env*` except `.env.example`.

## Things deliberately deferred — don't "fix" without checking

- **Facts vs chunks in separate tables.** Single-table-with-`kind` was chosen
  intentionally; revisit when fact-shaped queries (e.g. `UNIQUE (subject, predicate)`,
  temporal supersession joins) become hot.
- **Hybrid (BM25 + vector) search.** Pure cosine is the v0 baseline.
- **MCP transport beyond stdio.** Streamable-HTTP transport with auth is
  deferred until a second user or device needs access.
- **Multi-worker uvicorn / gunicorn.** Single worker is intentional because
  `db.init_db()` runs in the lifespan and multiple workers race the migration
  ledger (idempotent, but ugly logs).
- **Frontend in Docker.** The React app is dev-server only for now; baking a
  built `dist/` into a static container is a future change.

## Gotchas log (from `MIGRATION_HANDOFF.md`)

1. The global `JsonbDumper` registration for `list` will hijack future
   `text[]` Postgres-array columns if any are added. None exist today.
2. `providers/cli.py:_fmt` ISO-formats `updated_at` because psycopg returns
   `datetime` (not strings). If you see "Object of type datetime is not
   JSON serializable" from the CLI, that helper regressed.
3. `MarketingPanel.tsx` has two stale "SQLite" references (lines 148, 429).
   Cosmetic; fix when next touching that file.

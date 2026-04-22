# Personal Intelligence Agency (PIA)

A self-hosted, multi-department automation platform. Three departments are
planned:

1. **Watchdog** — polls RSS feeds and the GitHub API on a cron schedule and
   uses an LLM to surface items matching user-defined criteria. *Implemented.*
2. **Marketing** — edits a singleton product profile and drafts social-media
   post variants for Twitter/X, LinkedIn, Instagram, and TikTok/Reels.
   *Implemented.*
3. **R&D** — codes against a target product repository on the user's behalf.
   *Planned.*

Backend: FastAPI + MCP (stdio) + Postgres (with pgvector), under
[`PIA-RECON/`](./PIA-RECON/). Frontend: React 19 + Vite, under
[`PIA-RECON/PIA/`](./PIA-RECON/PIA/).

## Vendor neutrality

Each department stores its own provider, model, and API-key *environment
variable name* in the `department_config` table. Swapping between
Anthropic, OpenAI, Ollama, or any OpenAI-compatible endpoint is a config
change, not a code change. Secrets themselves are never stored in the DB —
only the name of the env var the backend should read at call time.

## Requirements

- **Python 3.11+** (3.14 is what this was built against)
- **Node 20+** and **npm** (for the frontend)
- **PostgreSQL 14+** with the **pgvector** extension (see
  [Database setup](#database-setup) below)
- At least one LLM provider credential:
  - `ANTHROPIC_API_KEY` for Anthropic, or
  - `OPENAI_API_KEY` for OpenAI, or
  - a local [Ollama](https://ollama.ai/) install (no key needed)
- An **embedding** provider key — defaults to OpenAI
  `text-embedding-3-small` (1536-dim). See `.env.example`.

Optional:
- `GITHUB_TOKEN` — raises the GitHub API rate limit from 60/hr to 5000/hr.

## Database setup

The watchdog and marketing departments (and the planned R&D memory store)
all share a single Postgres database with the `vector` extension enabled.

### Windows

1. Download the official installer from
   <https://www.postgresql.org/download/windows/>. Run it and note the
   `postgres` superuser password you set.
2. Install **pgvector**. The path of least resistance on Windows is
   either (a) the prebuilt DLLs from the
   [pgvector releases page](https://github.com/pgvector/pgvector/releases),
   dropped into your Postgres `lib` and `share/extension` directories, or
   (b) building from source per the project's `README` using MSVC.
   - Fallback if either of the above bites: run Postgres in Docker
     Desktop instead — the `pgvector/pgvector:pg16` image bundles the
     extension, and a one-line `docker run` reproduces this same setup.
3. Create the database and enable the extension:
   ```powershell
   createdb -U postgres pia
   psql -U postgres -d pia -c "CREATE EXTENSION vector;"
   ```
4. Set `DATABASE_URL` (and the `EMBEDDING_*` vars) in `.env` — see
   `PIA-RECON/.env.example` for the format.
5. Apply the migrations:
   ```powershell
   cd PIA-RECON
   python -m migrations.runner
   ```
   `python -m migrations.runner --status` shows what's applied vs pending
   without touching the DB.

### macOS / Linux

Same flow, with whichever package manager owns Postgres on your box
(`brew install postgresql pgvector`, `apt install postgresql-16-pgvector`,
etc.). The `createdb`/`psql`/`migrations.runner` steps are identical.

## Install

```bash
git clone <this-repo-url> personal-intelligence-agency
cd personal-intelligence-agency

# ── Backend ─────────────────────────────────────────────────────
cd PIA-RECON
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy the env template and fill in whichever keys you'll use
cp .env.example .env
$EDITOR .env

# Apply database migrations (assumes Postgres is up and DATABASE_URL is set).
# See "Database setup" above if you haven't created the DB yet.
python -m migrations.runner

# ── Frontend ────────────────────────────────────────────────────
cd PIA
npm install
cd ..
```

The migration runner is idempotent — re-running it only applies anything
new. It also runs automatically the first time the API boots, so if
you've created the DB and set `DATABASE_URL` you can skip the explicit
step and just start uvicorn.

## Run

Open two terminals from inside `PIA-RECON/`, both with the virtualenv
activated and the `.env` file exported (see below).

**Terminal 1 — API + scheduler:**
```bash
# Export the env vars declared in .env (bash/zsh):
set -a; source .env; set +a

uvicorn api:app --reload --port 8000
```

This starts the FastAPI server *and* the in-process APScheduler that runs
enabled watch targets on their configured cron cadence.

**Terminal 2 — frontend:**
```bash
cd PIA
npm run dev
```

Vite prints a local URL (usually <http://localhost:5173>). Open it in a
browser. The sidebar gives you:

- **Dashboard** — quick stats
- **Watchdog** — add/edit/disable watch targets, trigger manual checks
- **Intel Feed** — hits the watchdog has surfaced, with ratings
- **Marketing** — edit the product profile, generate social-post drafts
- **Departments** — per-department provider/model/env-var-name config + test

## First-run checklist

1. Open **Departments**. Confirm each department (`watchdog`, `marketing`,
   `rd`) has a provider + model + `api_key_ref` that matches a key you set
   in `.env`. Click **Test** on at least one to confirm the provider
   round-trips.
2. (Optional) Seed the example watch targets:
   ```bash
   curl -X POST http://localhost:8000/api/import-seed
   ```
   Or use the **Watchdog** panel to add your own.
3. Trigger a manual check from the **Watchdog** panel, then look at
   **Intel Feed** for hits.
4. Open **Marketing**, fill in your product profile, and generate a few
   draft variants.

## Optional: MCP server

The watchdog and marketing departments also expose their tools over MCP
(stdio) for agentic clients. Run separately from the API:

```bash
cd PIA-RECON
python server.py
```

Point your MCP client (Claude Desktop, etc.) at this command. Both
processes share the same Postgres database (`DATABASE_URL`).

## Manual checks without the API

For a one-shot run of all enabled targets (e.g. from cron):

```bash
cd PIA-RECON
python run_checks.py
```

## Project layout

```
personal-intelligence-agency/
├── README.md                    ← you are here
└── PIA-RECON/
    ├── api.py                   FastAPI app + scheduler lifespan
    ├── server.py                MCP stdio server (same tool surface)
    ├── scheduler.py             APScheduler wiring
    ├── db.py                    psycopg3 connection + jsonb adapters
    ├── migrations/              Numbered .sql files + Python runner
    ├── matcher.py               LLM match engine (watchdog)
    ├── adapters/                RSS + GitHub source adapters
    ├── providers/               Anthropic / OpenAI / Ollama abstraction
    ├── marketing/               Product + social-post drafter
    ├── run_checks.py            One-shot check runner
    ├── seed_targets.py          Example watch targets
    ├── requirements.txt
    ├── .env.example
    └── PIA/                     React 19 + Vite frontend
        ├── src/App.tsx
        ├── src/DepartmentsPanel.tsx
        └── src/MarketingPanel.tsx
```

## Branch model

- `main` — stable. Only merge from `test` after verification.
- `test` — integration branch. Feature branches merge here first.
- `claude/*` and other feature branches — active development.

Do not force-push to `main` or `test`.

## Security

This repo is public. **Do not commit API keys.** The runtime is built around
that rule, and there are guardrails to enforce it:

- **Architecture.** `department_config.api_key_ref` stores the *name* of an
  environment variable (e.g. `ANTHROPIC_API_KEY`). The secret itself lives
  only in `.env` (gitignored) and your shell. `providers/registry._resolve_key`
  reads `os.environ[api_key_ref]` at call time and never writes it back
  to the database. See
  [`PIA-RECON/providers/registry.py`](./PIA-RECON/providers/registry.py).

- **Startup check.** On boot, `api.py` logs one line like
  `env check: ANTHROPIC_API_KEY=present OPENAI_API_KEY=missing` — names
  only, never values. If a referenced key is `missing`, that department will
  fail the first time it tries to call its provider.

- **Pre-commit hook.** A repo-tracked hook at `.githooks/pre-commit` scans
  staged changes for Anthropic, OpenAI, GitHub, Google, and Slack key
  patterns and blocks the commit on any match. Enable it once per clone:
  ```bash
  git config core.hooksPath .githooks
  ```

- **Manual scan.** Run `bash scripts/check-no-secrets.sh` at any time to
  scan the whole working tree. CI (`.github/workflows/secret-scan.yml`)
  runs the same script on every push and pull request.

- **`.env*` paths are blocked.** The scanner rejects any staged path
  matching `.env*` except `.env.example`. Put templates in `.env.example`;
  never commit a real `.env`.

### Rules

1. Never paste a live API key into chat logs, issue/PR descriptions, commit
   messages, or AI-assistant transcripts. Treat every channel outside your
   own shell as public.
2. If a key is exposed — even briefly — rotate it. Revocation is free;
   waiting is not.
3. To override the pre-commit hook, use `git commit --no-verify`. This is
   strongly discouraged and should only be used to unblock a clear false
   positive.

### Rotation checklist

If you ever paste a key somewhere it shouldn't be:

1. Anthropic → <https://console.anthropic.com/settings/keys> → revoke.
2. OpenAI → <https://platform.openai.com/api-keys> → revoke.
3. GitHub → <https://github.com/settings/tokens> → revoke.
4. Issue a new key, update your local `.env`, restart uvicorn, and confirm
   the startup `env check:` line shows `present` for the rotated var.

## Troubleshooting

- **`ModuleNotFoundError: feedparser`** — dependencies aren't installed in
  the active Python. Re-activate the venv and re-run
  `pip install -r requirements.txt`.
- **Departments → Test returns `error: ANTHROPIC_API_KEY is not set`** —
  the API process didn't inherit the env var. Make sure you ran
  `set -a; source .env; set +a` (bash/zsh) in the same shell that launched
  uvicorn.
- **Ollama** — configure the marketing (or any) department with
  `provider=openai`, `base_url=http://localhost:11434/v1`,
  `api_key_ref=OLLAMA_API_KEY`, and set `OLLAMA_API_KEY=ollama` in `.env`
  (the value is ignored but the SDK requires something non-empty).
- **Frontend can't reach the API** — the API binds to `:8000` and CORS is
  wide open in dev. If you changed the port, update the `fetch(...)` calls
  or run both behind the same proxy.

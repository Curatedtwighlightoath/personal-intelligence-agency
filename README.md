# Personal Intelligence Agency (PIA)

A multi-department automation platform:

1. **Watchdog** — tracks AI services, blog posts, GitHub releases, and other
   feeds, then uses an LLM to surface items matching user-defined criteria.
   *(Implemented.)*
2. **Marketing & content** — drafts marketing copy and product content.
   *(Planned.)*
3. **R&D** — codes against a target product repository on the user's behalf.
   *(Planned.)*

The backend lives under [`PIA-RECON/`](./PIA-RECON/) (FastAPI + MCP + SQLite)
and the frontend under [`PIA-RECON/PIA/`](./PIA-RECON/PIA/) (React 19 + Vite).
See [`PIA-RECON/README.md`](./PIA-RECON/PIA/README.md) for the Vite scaffold
notes.

## Vendor neutrality

Each department stores its own provider + model + API-key-env-var-name in the
`department_config` table, so swapping between Anthropic, OpenAI, Ollama, or
any OpenAI-compatible endpoint is a config change, not a code change. Secrets
are never stored in SQLite — only the *name* of the environment variable to
read.

## Branch model

- `main` — stable. Only merge from `test` after verification.
- `test` — integration branch. Feature branches merge here first.
- `claude/*` and other feature branches — active development.

Do not force-push to `main` or `test`.

## Running locally

```bash
cd PIA-RECON
pip install -r requirements.txt
cp .env.example .env   # fill in at least ANTHROPIC_API_KEY
python seed_targets.py # one-time seed of watch targets
uvicorn api:app --reload --port 8000
# In another terminal, for the UI:
cd PIA && npm install && npm run dev
```

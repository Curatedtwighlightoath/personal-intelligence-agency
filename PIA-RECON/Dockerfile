# Dockerfile for the PIA backend (API + MCP server share this image).
#
# Two-layer build: deps first, then source. `requirements.txt` changes
# rarely; source changes constantly — keeping them in separate layers
# means `docker compose build` reuses the deps layer on most rebuilds.
#
# Frontend (PIA/) is intentionally NOT included; .dockerignore excludes it.
# Serve the React app from a separate container or run Vite locally
# against the API.

FROM python:3.12-slim

# Run as a non-root user. uid/gid 1000 lines up with most homelab setups
# and avoids root-owned files if a volume is ever bind-mounted into /app.
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Install Python deps. psycopg[binary] ships its own libpq so no apt
# packages are needed at runtime — keep the image small.
COPY --chown=app:app requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app. Anything matched by .dockerignore is skipped.
COPY --chown=app:app . ./

USER app

EXPOSE 8000

# Default: run the HTTP API. The compose file overrides `command` for
# the MCP service (or you can `docker compose run api python server.py`).
# Single worker is intentional — db.init_db() runs in the lifespan and
# multiple workers would race on the migration ledger (idempotent, but
# still ugly in logs). Promote to gunicorn + multi-worker once the
# migration step moves out of the request lifecycle.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

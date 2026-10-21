#!/bin/bash
# API + ingestion worker + indexing worker in one container. If any of them exits, stop the
# container so the Space restarts it, rather than serving with half the system missing.
set -eu

alembic upgrade head

python -m app.worker ingestion &
python -m app.worker indexing &

# No --proxy-headers: Vercel's requests prove themselves with PROXY_SECRET instead
# (app/trusted_proxy.py), and nothing else may set the client address.
uvicorn app.main:app --host 0.0.0.0 --port 7860 --no-server-header &

wait -n
exit 1

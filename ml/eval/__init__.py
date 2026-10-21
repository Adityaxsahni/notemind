"""Offline evaluation of NoteMind's retrieval and answers (Phase 7).

Reuses the backend's own code (extraction, chunking, models, retriever, prompts) so the
numbers describe what the app actually does. Run from the repo root:

    uv run --project backend python -m ml.eval.run --help
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
# The backend is an application, not an installed package: make `import app` work.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

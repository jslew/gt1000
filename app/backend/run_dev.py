from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[1]
for path in (BACKEND_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gt1000_app.app import create_app  # noqa: E402
from gt1000_app.app_logging import setup_logging  # noqa: E402


if __name__ == "__main__":
    setup_logging()
    uvicorn.run(create_app(), host="127.0.0.1", port=38473, log_level="info")


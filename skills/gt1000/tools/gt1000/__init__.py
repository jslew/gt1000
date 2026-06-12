"""GT-1000 agent tooling."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _avoid_repo_pycache() -> None:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("PYTHONPYCACHEPREFIX", str(Path("/tmp") / "gt1000-skill-pycache"))
    try:
        sys.dont_write_bytecode = True
        sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
    except Exception:
        pass


_avoid_repo_pycache()

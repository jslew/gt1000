from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_pycache() -> None:
    # Tests and CLI runs should not leave generated __pycache__ artifacts in the repo.
    # Point bytecode caches to a temp directory and disable bytecode writes by default.
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.dont_write_bytecode = True
    try:
        prefix = os.environ.get("PYTHONPYCACHEPREFIX")
        if not prefix:
            prefix = str(Path("/tmp") / "gt1000-pycache")
            os.environ["PYTHONPYCACHEPREFIX"] = prefix
        sys.pycache_prefix = prefix
    except Exception:
        # If the interpreter does not support pycache_prefix, fall back to dont_write_bytecode.
        pass


_configure_pycache()


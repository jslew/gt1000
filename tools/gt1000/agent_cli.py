#!/usr/bin/env python3
"""Compatibility wrapper for the canonical GT-1000 skill CLI."""

import sys

from skills.gt1000.tools.gt1000 import agent_cli as _impl

main = _impl.main


if __name__ == "__main__":
    raise SystemExit(main())

sys.modules[__name__] = _impl

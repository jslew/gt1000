"""Compatibility wrapper for the canonical GT-1000 system edit helpers."""

import sys

from skills.gt1000.tools.gt1000 import system_edit as _impl

sys.modules[__name__] = _impl

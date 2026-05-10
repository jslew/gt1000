"""Compatibility wrapper for the canonical GT-1000 skill MIDI backend."""

import sys

from skills.gt1000.tools.gt1000 import live as _impl

sys.modules[__name__] = _impl

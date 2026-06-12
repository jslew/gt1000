"""Compatibility wrapper for GT-1000 audio CLI handlers."""

import sys

from skills.gt1000.tools.gt1000 import audio_cli as _impl

sys.modules[__name__] = _impl

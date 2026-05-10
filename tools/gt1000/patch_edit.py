"""Compatibility wrapper for the canonical GT-1000 skill patch editor."""

import sys

from skills.gt1000.tools.gt1000 import patch_edit as _impl

sys.modules[__name__] = _impl

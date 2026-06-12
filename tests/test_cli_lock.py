import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

from tools.gt1000.cli_lock import CliProcessLockError, cli_process_lock


class CliLockTests(unittest.TestCase):
    def test_second_acquire_fails_while_first_holds_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "cli.lock"
            os.environ["GT1000_CLI_LOCK"] = str(lock_path)
            try:
                with cli_process_lock():
                    with self.assertRaises(CliProcessLockError) as context:
                        with cli_process_lock():
                            pass
                self.assertIn("already running", str(context.exception))
            finally:
                os.environ.pop("GT1000_CLI_LOCK", None)

    def test_allow_concurrent_env_disables_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "cli.lock"
            os.environ["GT1000_CLI_LOCK"] = str(lock_path)
            os.environ["GT1000_ALLOW_CONCURRENT"] = "1"
            try:
                with cli_process_lock():
                    with cli_process_lock():
                        pass
            finally:
                os.environ.pop("GT1000_CLI_LOCK", None)
                os.environ.pop("GT1000_ALLOW_CONCURRENT", None)


if __name__ == "__main__":
    unittest.main()

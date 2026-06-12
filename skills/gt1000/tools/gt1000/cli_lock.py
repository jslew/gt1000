from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path

CLI_LOCK_ENV_DISABLE = "GT1000_ALLOW_CONCURRENT"
CLI_LOCK_PATH_ENV = "GT1000_CLI_LOCK"


class CliProcessLockError(Exception):
    def __init__(self, message: str, *, holder_pid: int | None = None, lock_path: Path | None = None) -> None:
        super().__init__(message)
        self.holder_pid = holder_pid
        self.lock_path = lock_path


def cli_lock_path() -> Path:
    override = os.environ.get(CLI_LOCK_PATH_ENV)
    if override:
        return Path(override).expanduser()
    agent_dir = Path(os.environ.get("GT1000_AGENT_DIR", Path.home() / ".gt1000-agent"))
    return agent_dir / "cli.lock"


@contextlib.contextmanager
def cli_process_lock(*, enabled: bool = True):
    if not enabled or os.environ.get(CLI_LOCK_ENV_DISABLE) == "1":
        yield
        return

    path = cli_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder_pid = _read_holder_pid(handle)
            raise CliProcessLockError(
                _lock_busy_message(path, holder_pid),
                holder_pid=holder_pid,
                lock_path=path,
            ) from None
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _read_holder_pid(handle) -> int | None:
    try:
        handle.seek(0)
        line = handle.read().strip()
        return int(line.split()[0]) if line else None
    except (OSError, ValueError):
        return None


def _lock_busy_message(path: Path, holder_pid: int | None) -> str:
    base = f"another gt1000-agent process is already running (lock: {path})"
    if holder_pid is not None:
        return f"{base}; holder pid {holder_pid}. Wait for it to finish before starting another command."
    return f"{base}. Wait for it to finish before starting another command."

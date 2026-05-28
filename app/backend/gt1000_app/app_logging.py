from __future__ import annotations

import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

LogSource = Literal["server", "client"]

_RING_SIZE = 2000
_ring_lock = Lock()
_rings: dict[LogSource, deque[dict[str, Any]]] = {
    "server": deque(maxlen=_RING_SIZE),
    "client": deque(maxlen=_RING_SIZE),
}
_file_lock = Lock()
_configured = False


def log_dir() -> Path:
    return Path(os.environ.get("GT1000_APP_LOG_DIR", Path.home() / ".gt1000-app" / "logs"))


def log_path(source: LogSource) -> Path:
    return log_dir() / f"{source}.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(source: LogSource, payload: dict[str, Any]) -> None:
    entry = dict(payload)
    entry.setdefault("ts", utc_now_iso())
    entry.setdefault("source", source)
    line = json.dumps(entry, default=str, ensure_ascii=False)
    path = log_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    with _ring_lock:
        _rings[source].append(entry)


def app_log(level: str, category: str, message: str, **fields: Any) -> None:
    payload = {
        "level": level.lower(),
        "category": category,
        "message": message,
        **fields,
    }
    append_log("server", payload)
    logger = logging.getLogger("gt1000_app")
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, "[%s] %s", category, message, extra={"fields": fields})


def ingest_client_logs(entries: list[dict[str, Any]]) -> int:
    count = 0
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        message = raw.get("message")
        if not isinstance(message, str) or not message.strip():
            continue
        payload = {
            "level": str(raw.get("level") or "info").lower(),
            "category": str(raw.get("category") or "client"),
            "message": message,
        }
        if isinstance(raw.get("ts"), str):
            payload["ts"] = raw["ts"]
        if isinstance(raw.get("data"), dict):
            payload["data"] = raw["data"]
        append_log("client", payload)
        count += 1
    return count


def tail_logs(source: LogSource, *, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    with _ring_lock:
        items = list(_rings[source])
    if len(items) >= limit:
        return items[-limit:]
    # Cold start: hydrate ring from disk tail.
    path = log_path(source)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    parsed: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    with _ring_lock:
        ring = _rings[source]
        for entry in parsed[-_RING_SIZE:]:
            ring.append(entry)
    return parsed[-limit:]


def log_paths() -> dict[str, str]:
    directory = log_dir()
    return {
        "directory": str(directory),
        "server": str(log_path("server")),
        "client": str(log_path("client")),
    }


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gt1000_app")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    logger.addHandler(console)
    app_log("info", "logging", "Server logging initialized", directory=str(directory))

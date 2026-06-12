"""Session directory layout for audio lab captures."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SESSION_ROOT = Path.home() / "gt1000-sessions"


def session_root() -> Path:
    raw = os.environ.get("GT1000_SESSION_DIR", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_SESSION_ROOT


def resolve_session_dir(name: str, *, create: bool = False) -> Path:
    if not name or name.strip() != name or "/" in name or name in {".", ".."}:
        raise ValueError("session name must be a single path segment without slashes")
    path = session_root() / name.strip()
    if create:
        path.mkdir(parents=True, exist_ok=True)
        (path / "renders").mkdir(exist_ok=True)
    return path


def default_dry_path(session_dir: Path) -> Path:
    return session_dir / "dry.wav"


def write_session_meta(session_dir: Path, payload: dict[str, Any]) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "renders").mkdir(exist_ok=True)
    path = session_dir / "meta.json"
    existing: dict[str, Any] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.update(payload)
    existing["updatedAt"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def append_session_event(session_dir: Path, event: dict[str, Any]) -> None:
    meta_path = session_dir / "meta.json"
    data: dict[str, Any] = {}
    if meta_path.exists():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    events = data.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        data["events"] = events
    events.append({**event, "at": datetime.now(timezone.utc).isoformat()})
    meta_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sanitize_label(label: str) -> str:
    text = label.strip()
    if not text:
        raise ValueError("render label must not be empty")
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text)
    safe = safe.strip("-")
    if not safe:
        raise ValueError("render label must contain at least one alphanumeric character")
    return safe


def device_snapshots_dir(session_dir: Path) -> Path:
    return session_dir / "deviceSnapshots"


def render_wet_path(session_dir: Path, label: str) -> Path:
    return session_dir / "renders" / f"{sanitize_label(label)}-wet.wav"


def render_patch_snapshot_path(session_dir: Path, label: str) -> Path:
    return session_dir / "renders" / f"{sanitize_label(label)}-patch.json"


def append_render_log(session_dir: Path, record: dict[str, Any]) -> None:
    meta_path = session_dir / "meta.json"
    data: dict[str, Any] = {}
    if meta_path.exists():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    renders = data.setdefault("renders", [])
    if not isinstance(renders, list):
        renders = []
        data["renders"] = renders
    renders.append({**record, "at": datetime.now(timezone.utc).isoformat()})
    meta_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

"""Live MIDI snapshots stored alongside audio lab sessions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from tools.gt1000 import live
except ModuleNotFoundError:
    import live

from .session import device_snapshots_dir


SYSTEM_INOUT_SIZE = [0x00, 0x00, 0x00, 0x60]


def _hash_reads(raw: dict[str, list[int]]) -> str:
    digest = hashlib.sha256()
    for key in sorted(raw):
        digest.update(key.encode("utf-8"))
        digest.update(bytes(raw[key]))
    return digest.hexdigest()[:16]


def capture_system_inout(timeout: float) -> dict[str, Any]:
    try:
        from tools.gt1000 import agent_cli
    except ModuleNotFoundError:
        import agent_cli

    raw = live.read_system_section(live.SYSTEM_IN_OUT, SYSTEM_INOUT_SIZE, timeout)
    data = raw.get(live.address_key(live.SYSTEM_IN_OUT), [])
    return {
        "address": live.hex_bytes(live.SYSTEM_IN_OUT),
        "dataHex": live.hex_string(data),
        "decoded": agent_cli.decode_system_inout(data),
    }


def capture_setup_efct(timeout: float) -> dict[str, Any]:
    try:
        from tools.gt1000.audio_lab.setup_efct import decode_setup_efct
    except ModuleNotFoundError:
        from .setup_efct import decode_setup_efct

    raw = live.read_system_section(live.SETUP_EFCT, live.SETUP_EFCT_SIZE, timeout)
    data = raw.get(live.address_key(live.SETUP_EFCT), [])
    return {
        "address": live.hex_bytes(live.SETUP_EFCT),
        "dataHex": live.hex_string(data),
        "decoded": decode_setup_efct(data),
    }


def capture_patch_snapshot(timeout: float) -> dict[str, Any]:
    try:
        from tools.gt1000 import agent_cli
    except ModuleNotFoundError:
        import agent_cli

    raw = live.read_data_sets(timeout=timeout, requests=live.INITIAL_READS)
    snapshot = agent_cli.snapshot_from_patch_records(live.INITIAL_READS, live.INITIAL_READS, raw)
    chain = agent_cli.chain_from_full(snapshot)
    return {
        "patchName": snapshot.get("patchName"),
        "bpm": snapshot.get("bpm"),
        "chain": chain,
        "readHash": _hash_reads(raw),
    }


def capture_live_snapshots(timeout: float) -> dict[str, Any]:
    return {
        "systemInOut": capture_system_inout(timeout),
        "setupEfct": capture_setup_efct(timeout),
        "patch": capture_patch_snapshot(timeout),
    }


def write_device_snapshots(session_dir: Path, snapshots: dict[str, Any]) -> dict[str, str]:
    root = device_snapshots_dir(session_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for key, payload in snapshots.items():
        path = root / f"{key}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths[key] = str(path)
    return paths


def write_render_patch_snapshot(session_dir: Path, label: str, snapshot: dict[str, Any]) -> Path:
    path = session_dir / "renders" / f"{label}-patch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

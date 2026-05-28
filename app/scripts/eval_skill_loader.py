#!/usr/bin/env python3
"""Live LLM eval for GT-1000 app skill loader (load_skill_reference).

Requires OPENAI_API_KEY. Optional: GT1000_EVAL_MODEL (default gpt-4o-mini).

Usage:
  app/backend/.venv/bin/python app/scripts/eval_skill_loader.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "app" / "backend"
for path in (BACKEND_DIR, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gt1000_app.agent import AgentService  # noqa: E402
from gt1000_app.config import AppConfig  # noqa: E402
from gt1000_app.device import DeviceService  # noqa: E402
from gt1000_app.events import EventBus  # noqa: E402
from gt1000_app.skill_context import load_skill_reference  # noqa: E402


MINI_CHAIN = {
    "overview": {"patchName": "Eval Patch", "masterBPM": 120, "masterPatchLevel": 50},
    "descriptionSignalChainSummary": "DIVIDER 1 -> BRANCH SPLIT1 -> MIXER 1",
    "routingElements": [
        {"displayName": "DIVIDER 1", "detailBlockID": "divider1", "position": 1},
        {"displayName": "BRANCH SPLIT1", "detailBlockID": "branchSplit1", "position": 2},
    ],
    "descriptionElements": [
        {"id": "c1", "displayName": "DIVIDER 1", "detailBlockID": "divider1", "includeInDescription": True},
        {"id": "c2", "displayName": "BRANCH SPLIT1", "detailBlockID": "branchSplit1", "includeInDescription": True},
        {"id": "c3", "displayName": "MIXER 1", "detailBlockID": "mixer1", "includeInDescription": True},
    ],
    "elements": [],
}


@dataclass
class EvalCase:
    id: str
    prompt: str
    expect_skill_docs: list[str] = field(default_factory=list)
    forbid_skill: bool = False
    allow_device_tools: bool = True
    note: str = ""


EVAL_CASES = [
    EvalCase(
        id="divider_routing",
        prompt="What is the difference between the two DIVIDER 1 branches on a GT-1000? Explain routing in musician terms.",
        expect_skill_docs=["midi-patch-effect", "skill-routing"],
        note="Should load routing reference; may also read patch chain.",
    ),
    EvalCase(
        id="assign_encoding",
        prompt="For GT-1000 Assign on/off targets, what min/max values should be used and why not raw 0 and 1?",
        expect_skill_docs=["midi-assigns"],
        note="Assign encoding is only in midi-assigns reference.",
    ),
    EvalCase(
        id="controls_cur_num",
        prompt="What does the CUR NUM footswitch do on the GT-1000 play screen?",
        expect_skill_docs=["midi-patch-controls", "wiki-owner-manual", "skill-routing"],
        note="Control mapping — patch-controls or owner-manual acceptable.",
    ),
    EvalCase(
        id="greeting_no_skill",
        prompt="Hi — what can you help me with on my GT-1000?",
        forbid_skill=True,
        allow_device_tools=False,
        note="Small talk should not pull large reference docs.",
    ),
]


@dataclass
class EvalResult:
    case_id: str
    ok: bool
    tools_called: list[str]
    skill_docs_loaded: list[str]
    answer_preview: str
    duration_s: float
    errors: list[str] = field(default_factory=list)


def _mock_device() -> DeviceService:
    device = DeviceService(EventBus())
    device.patch_chain = AsyncMock(return_value=MINI_CHAIN)  # type: ignore[method-assign]
    device.patch_preview = AsyncMock(return_value=MINI_CHAIN)  # type: ignore[method-assign]
    device.patch_overview = AsyncMock(return_value=MINI_CHAIN.get("overview"))  # type: ignore[method-assign]
    device.patch_musician_summary = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "patchName": "Eval Patch",
            "tone": "Main path: DIVIDER 1 -> BRANCH SPLIT1 -> MIXER 1.",
            "summary": ["Eval patch for skill-loader test."],
        }
    )
    device.patch_controls = AsyncMock(return_value={"controls": []})  # type: ignore[method-assign]
    device.ports = AsyncMock(return_value={"destinations": [], "sources": []})  # type: ignore[method-assign]
    return device


async def run_case(agent: AgentService, case: EvalCase) -> EvalResult:
    tools_called: list[str] = []
    skill_docs: list[str] = []
    answer = ""
    errors: list[str] = []
    started = time.monotonic()

    async for event in agent.stream_chat(case.prompt):
        if event.type == "tool.start":
            name = str(event.data.get("name") or "")
            tools_called.append(name)
            if name == "load_skill_reference":
                args = event.data.get("arguments") or {}
                doc_id = str(args.get("docId") or args.get("doc_id") or "")
                if doc_id:
                    skill_docs.append(doc_id)
        if event.type == "tool.error":
            errors.append(f"{event.data.get('name')}: {event.data.get('error')}")
        if event.type == "error":
            errors.append(str(event.data.get("message")))
        if event.type == "assistant.done":
            answer = str(event.data.get("content") or "")

    duration = time.monotonic() - started
    ok = True
    if case.forbid_skill and skill_docs:
        ok = False
        errors.append(f"unexpected skill loads: {skill_docs}")
    if case.expect_skill_docs and not skill_docs:
        ok = False
        errors.append(f"expected one of {case.expect_skill_docs}, got none")
    elif case.expect_skill_docs and skill_docs:
        if not any(doc in skill_docs for doc in case.expect_skill_docs):
            ok = False
            errors.append(f"expected one of {case.expect_skill_docs}, got {skill_docs}")
    if not case.allow_device_tools:
        device_tools = [t for t in tools_called if t != "load_skill_reference"]
        if device_tools:
            ok = False
            errors.append(f"unexpected device tools: {device_tools}")
    if "<tool_call>" in answer:
        ok = False
        errors.append("answer contains tool_call markup")
    if not answer.strip() and not errors:
        ok = False
        errors.append("empty answer")

    return EvalResult(
        case_id=case.id,
        ok=ok,
        tools_called=tools_called,
        skill_docs_loaded=skill_docs,
        answer_preview=answer.strip().replace("\n", " ")[:280],
        duration_s=round(duration, 2),
        errors=errors,
    )


async def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY is not set; cannot run live eval.", file=sys.stderr)
        return 2

    model = os.environ.get("GT1000_EVAL_MODEL", "gpt-4o-mini").strip()
    strict = os.environ.get("GT1000_EVAL_STRICT", "1").strip() not in {"0", "false", "no"}
    extra = ""
    if strict:
        extra = (
            "You MUST call load_skill_reference before answering questions about Assign encoding, "
            "divider/branch/mixer routing, footswitch functions, or SysEx/MIDI details. "
            "Do not answer those from general knowledge alone."
        )
    config = AppConfig(
        provider="openai",
        model=model,
        openai_api_key=api_key,
        system_prompt_extra=extra,
    )
    agent = AgentService(_mock_device(), config)
    if strict:
        print("Strict mode: ON (set GT1000_EVAL_STRICT=0 to test default prompt only)")

    print(f"Skill loader live eval — model={model}")
    print("Pre-flight: load_skill_reference('midi-patch-effect') …")
    pre = load_skill_reference("midi-patch-effect")
    if pre.get("error"):
        print(f"  FAIL: {pre['error']}", file=sys.stderr)
        return 1
    print(f"  OK ({pre.get('chars')} chars from {pre.get('path')})")
    print()

    results: list[EvalResult] = []
    for case in EVAL_CASES:
        print(f"Case: {case.id}")
        print(f"  Prompt: {case.prompt[:90]}…")
        result = await run_case(agent, case)
        results.append(result)
        status = "PASS" if result.ok else "FAIL"
        print(f"  {status} ({result.duration_s}s) tools={result.tools_called} skill={result.skill_docs_loaded}")
        if result.errors:
            for err in result.errors:
                print(f"    - {err}")
        if result.answer_preview:
            print(f"    answer: {result.answer_preview}…")
        print()

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    report = {
        "model": model,
        "passed": passed,
        "total": total,
        "results": [
            {
                "caseId": r.case_id,
                "ok": r.ok,
                "tools": r.tools_called,
                "skillDocs": r.skill_docs_loaded,
                "durationSeconds": r.duration_s,
                "errors": r.errors,
                "answerPreview": r.answer_preview,
            }
            for r in results
        ],
    }
    report_path = ROOT / "app" / "scripts" / "eval_skill_loader_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {passed}/{total} passed")
    print(f"Report: {report_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

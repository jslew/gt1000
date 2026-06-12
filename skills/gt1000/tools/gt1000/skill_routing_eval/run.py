"""Run agy against routing scenarios and score resulting chat JSONL."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .scenarios import default_scenarios_path, load_scenarios
from .scorer import score_trace
from .trace import trace_from_gemini_jsonl

# agy stores chats like Gemini CLI: ~/.gemini/tmp/<project-slug>/chats/session-*.jsonl
DEFAULT_GEMINI_TMP = Path.home() / ".gemini" / "tmp"
DEFAULT_AGY = Path.home() / ".local" / "bin" / "agy"
DEFAULT_WORKDIR = Path.home() / "proj" / "gt1000-scratch"
DEFAULT_SUITE = (
    "describe_current_patch",
    "describe_user_slot",
    "connection_timeouts",
)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "tests" / "skill_routing_eval" / "scenarios.json").is_file():
            return parent
    return here.parents[5]


def project_slug(workdir: Path) -> str:
    return workdir.name


def chats_dir(workdir: Path, gemini_tmp: Path = DEFAULT_GEMINI_TMP) -> Path:
    return gemini_tmp / project_slug(workdir) / "chats"


def list_session_jsonls(chats: Path) -> list[Path]:
    if not chats.is_dir():
        return []
    return sorted(chats.glob("session-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def newest_jsonl_after(chats: Path, since_mtime: float) -> Path | None:
    for path in list_session_jsonls(chats):
        if path.stat().st_mtime > since_mtime:
            return path
    return None


def build_agy_prompt(user_message: str, *, skill_prefix: str = "/gt1000") -> str:
    return (
        f"{skill_prefix} {user_message}\n\n"
        "Use the gt1000 skill routing card. Follow its Agent workflow: "
        "one authoritative CLI read first unless the summary is insufficient; "
        "do not grep or cat under references/ before the first gt1000-agent call; "
        "do not chain gt1000-agent with &&."
    )


def run_agy(
    prompt: str,
    *,
    workdir: Path,
    agy_bin: Path,
    print_timeout: str,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(agy_bin),
        "-p",
        prompt,
        "--dangerously-skip-permissions",
        "--print-timeout",
        print_timeout,
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )


def score_jsonl(jsonl: Path, scenario_id: str, scenarios_path: Path) -> tuple[bool, str, list[str]]:
    scenarios = load_scenarios(scenarios_path)
    if scenario_id not in scenarios:
        raise SystemExit(f"Unknown scenario {scenario_id!r}")
    trace = trace_from_gemini_jsonl(jsonl)
    result = score_trace(trace, scenarios[scenario_id])
    return result.passed, result.summary(), list(result.violations)


def run_scenario(
    scenario_id: str,
    *,
    scenarios_path: Path,
    workdir: Path,
    agy_bin: Path,
    gemini_tmp: Path,
    print_timeout: str,
    jsonl_override: Path | None = None,
    dry_run: bool = False,
) -> dict:
    scenarios = load_scenarios(scenarios_path)
    if scenario_id not in scenarios:
        raise SystemExit(f"Unknown scenario {scenario_id!r}")
    scenario = scenarios[scenario_id]
    if not scenario.user_messages:
        raise SystemExit(f"Scenario {scenario_id!r} has no user_messages")
    user_message = scenario.user_messages[0]
    prompt = build_agy_prompt(user_message)
    chats = chats_dir(workdir, gemini_tmp)

    out: dict = {
        "scenario_id": scenario_id,
        "user_message": user_message,
        "workdir": str(workdir),
        "chats_dir": str(chats),
        "prompt": prompt,
    }

    if jsonl_override is not None:
        out["jsonl"] = str(jsonl_override)
        passed, summary, violations = score_jsonl(jsonl_override, scenario_id, scenarios_path)
        out["passed"] = passed
        out["summary"] = summary
        out["violations"] = violations
        return out

    if dry_run:
        out["dry_run"] = True
        return out

    since = time.time()
    if chats.is_dir():
        existing = list_session_jsonls(chats)
        if existing:
            since = max(since, existing[0].stat().st_mtime)

    proc = run_agy(
        prompt,
        workdir=workdir,
        agy_bin=agy_bin,
        print_timeout=print_timeout,
    )
    out["agy_exit_code"] = proc.returncode
    if proc.stdout:
        out["agy_stdout_tail"] = proc.stdout[-2000:]
    if proc.stderr:
        out["agy_stderr_tail"] = proc.stderr[-2000:]

    jsonl = newest_jsonl_after(chats, since)
    if jsonl is None:
        out["passed"] = False
        out["error"] = f"No new session JSONL under {chats} after agy run"
        return out

    out["jsonl"] = str(jsonl)
    passed, summary, violations = score_jsonl(jsonl, scenario_id, scenarios_path)
    out["passed"] = passed
    out["summary"] = summary
    out["violations"] = violations
    return out


def run_suite(
    scenario_ids: list[str],
    *,
    scenarios_path: Path,
    workdir: Path,
    agy_bin: Path,
    gemini_tmp: Path,
    print_timeout: str,
    jsonl_overrides: dict[str, Path] | None = None,
    dry_run: bool = False,
) -> list[dict]:
    results = []
    for sid in scenario_ids:
        override = (jsonl_overrides or {}).get(sid)
        results.append(
            run_scenario(
                sid,
                scenarios_path=scenarios_path,
                workdir=workdir,
                agy_bin=agy_bin,
                gemini_tmp=gemini_tmp,
                print_timeout=print_timeout,
                jsonl_override=override,
                dry_run=dry_run,
            )
        )
    return results


def _print_table(results: list[dict]) -> None:
    print(f"{'scenario':<40} {'result':<6} top violations")
    print("-" * 90)
    for row in results:
        sid = row["scenario_id"]
        if row.get("dry_run"):
            print(f"{sid:<40} {'DRY':<6} (prompt only)")
            continue
        if row.get("error"):
            print(f"{sid:<40} {'ERROR':<6} {row['error'][:50]}")
            continue
        status = "PASS" if row.get("passed") else "FAIL"
        viol = row.get("violations") or []
        top = viol[0][:45] if viol else ""
        print(f"{sid:<40} {status:<6} {top}")


def main(argv: list[str] | None = None) -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Run agy routing eval scenarios")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=None,
        help="Path to scenarios.json",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path(os.environ.get("GT1000_ROUTING_EVAL_WORKDIR", str(DEFAULT_WORKDIR))),
        help="Project directory for agy (default: gt1000-scratch)",
    )
    parser.add_argument(
        "--agy",
        type=Path,
        default=Path(os.environ.get("GT1000_ROUTING_EVAL_AGY", str(DEFAULT_AGY))),
        help="agy binary path",
    )
    parser.add_argument(
        "--gemini-tmp",
        type=Path,
        default=Path(os.environ.get("GT1000_ROUTING_EVAL_GEMINI_TMP", str(DEFAULT_GEMINI_TMP))),
        help="~/.gemini/tmp root for chat JSONL discovery",
    )
    parser.add_argument(
        "--print-timeout",
        default=os.environ.get("GT1000_ROUTING_EVAL_TIMEOUT", "5m"),
        help="agy --print-timeout value",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompts only; do not invoke agy",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run one scenario through agy and score")
    run_p.add_argument("--scenario", required=True)
    run_p.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Score this JSONL instead of running agy (replay)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print prompt only; do not invoke agy",
    )

    suite_p = sub.add_parser("suite", help="Run a small scenario set")
    suite_p.add_argument(
        "--scenarios-list",
        default=os.environ.get("GT1000_ROUTING_EVAL_SUITE", ",".join(DEFAULT_SUITE)),
        help="Comma-separated scenario ids",
    )
    suite_p.add_argument(
        "--replay-jsonl",
        type=Path,
        default=None,
        help="Score this JSONL for every scenario (smoke test harness only)",
    )
    suite_p.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print prompts only; do not invoke agy",
    )

    sub.add_parser("discover", help="Show chats dir and newest session JSONL")

    args = parser.parse_args(argv)
    scenarios_path = args.scenarios or default_scenarios_path(root)
    workdir = args.workdir
    if args.command == "discover":
        wd = workdir
        chats = chats_dir(wd, args.gemini_tmp)
        print(f"workdir: {wd}")
        print(f"project_slug: {project_slug(wd)}")
        print(f"chats_dir: {chats}")
        files = list_session_jsonls(chats)
        if files:
            print(f"newest_jsonl: {files[0]}")
        else:
            print("newest_jsonl: (none)")
        return 0

    if args.command == "run":
        row = run_scenario(
            args.scenario,
            scenarios_path=scenarios_path,
            workdir=workdir,
            agy_bin=args.agy,
            gemini_tmp=args.gemini_tmp,
            print_timeout=args.print_timeout,
            jsonl_override=args.jsonl,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print(json.dumps(row, indent=2))
            return 0
        print(row.get("summary", row.get("error", "")))
        if row.get("jsonl"):
            print(f"jsonl: {row['jsonl']}")
        return 0 if row.get("passed") else 1

    ids = [s.strip() for s in args.scenarios_list.split(",") if s.strip()]
    overrides = {sid: args.replay_jsonl for sid in ids} if args.replay_jsonl else None
    results = run_suite(
        ids,
        scenarios_path=scenarios_path,
        workdir=workdir,
        agy_bin=args.agy,
        gemini_tmp=args.gemini_tmp,
        print_timeout=args.print_timeout,
        jsonl_overrides=overrides,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(json.dumps(results, indent=2))
        return 0
    _print_table(results)
    print()
    for row in results:
        if row.get("jsonl"):
            print(f"  {row['scenario_id']}: {row['jsonl']}")
    failed = sum(1 for r in results if not r.get("passed"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

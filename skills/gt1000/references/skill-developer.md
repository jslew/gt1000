## Skill developer notes (GT-1000)

This page is intentionally **developer-oriented**. Musicians should use the shorter CLI quick reference at `references/midi-reference/cli-usage.md`.

## Diagnostic logging

- Use `--diagnostic-log` before the command to write JSONL timing events.
- With no value, it writes to a generated file under `~/.gt1000-agent/diagnostics`.
- With an explicit value, use either `--diagnostic-log path.jsonl` or `--diagnostic-log=path.jsonl`.

```sh
$GT1000_AGENT --pretty --diagnostic-log patch master-set level 90 --user-slot U10-1 --live --verify --timeout 20
$GT1000_AGENT --pretty --diagnostic-log=/tmp/gt1000-master-set.jsonl patch master-set level 90 --user-slot U10-1 --live --verify --timeout 20
```

## Skill routing coverage

After adding or renaming any `references/**/*.md` file, update the **File registry** in `references/skill-routing-index.md` and run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_routing -q
```

## Skill routing eval (LLM traces)

After changing routing rules or `skill-routing-index.md` intents, update `tests/skill_routing_eval/scenarios.json` and golden traces, then:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_routing_eval -q
```

Score a Gemini/Cursor JSONL export:

```sh
scripts/gt1000-routing-eval score-jsonl --jsonl /path/to/session.jsonl --scenario describe_current_patch
scripts/gt1000-routing-eval-run suite   # live agy from gt1000-scratch (see skill-routing-eval.md)
```

See `references/skill-routing-eval.md`.

## Verification (tests)

Routine unit and read-only live checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill.LiveSkillReadTests tests.test_live_skill.LiveSkillSystemReadTests -q
```

The destructive live write suite requires `GT1000_LIVE_BACKUP_DIR`:

```sh
GT1000_LIVE=1 GT1000_ALLOW_DESTRUCTIVE=1 GT1000_LIVE_BACKUP_DIR=/tmp/gt1000-live-backups PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill -q
```

## Timeout selection

- `--timeout 8`: port inventory, `doctor` without write checks, and small system views
- `--timeout 15`: focused current-patch reads (chain/controls/performance/musician-summary)
- `--timeout 20`: fuller reads and normal verified temporary writes
- `--timeout 30`: persistent slot/preset/bank reads/writes and multi-record operations

## Encoding validation commands

These are for maintaining low-level encoding validation coverage, not for normal musician workflows:

- `patch encoding-status`
- `patch validate-encoding`
- `patch validate-encoding-batch`
- `patch validate-encoding-scope`

## Live connectivity / recovery notes (high level)

- If `ports --live` hangs or times out, stop live testing and recover CoreMIDI/the USB connection before continuing. Quit BOSS Tone Studio if it is open, then power-cycle or reconnect the GT-1000.
- Run live commands one at a time; avoid `&&` chaining of multiple `--live` reads. `gt1000-agent` holds an exclusive process lock (`~/.gt1000-agent/cli.lock`, exit code `75` on conflict). Test harnesses may set `GT1000_ALLOW_CONCURRENT=1` to bypass.

# Skill routing eval (LLM behavior)

Mechanical tests prove every reference file is registered (`tests/test_skill_routing.py`). **Routing eval** scores whether an agent’s **tool trace** follows the skill routing card: correct first CLI, no reference mining, no chained live MIDI, consent gates.

## CI (no LLM)

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_routing_eval -q
```

This runs:

- **Index coverage** — every row in `skill-routing-index.md` has a `scenarios.json` entry.
- **Golden traces** — good fixtures must pass; anti-pattern fixtures must fail rules.

## Score a saved transcript

```sh
scripts/gt1000-routing-eval score-jsonl \
  --jsonl ~/.gemini/tmp/gt1000-scratch/chats/session-....jsonl \
  --scenario describe_user_slot
```

Or a hand-written JSON trace:

```sh
scripts/gt1000-routing-eval score \
  --trace tests/skill_routing_eval/traces/good_describe_current_patch.json \
  --scenario describe_current_patch
```

Exit code **0** = pass, **1** = fail.

## Live agy runs

**agy** (non-interactive print mode) replaces Gemini CLI for routing eval. Chat logs use the same layout as Gemini:

`~/.gemini/tmp/<project-dir-name>/chats/session-<timestamp>-<id>.jsonl`

For the scratch workspace (`~/proj/gt1000-scratch`):

`~/.gemini/tmp/gt1000-scratch/chats/session-*.jsonl`

Run one scenario (from repo root):

```sh
scripts/gt1000-routing-eval-run run --scenario describe_current_patch
```

Small default suite (read-only / fast MIDI; no divider audio lab):

```sh
scripts/gt1000-routing-eval-run suite
```

Environment:

| Variable | Default |
|----------|---------|
| `GT1000_ROUTING_EVAL_WORKDIR` | `~/proj/gt1000-scratch` |
| `GT1000_ROUTING_EVAL_AGY` | `~/.local/bin/agy` |
| `GT1000_ROUTING_EVAL_TIMEOUT` | `5m` (`agy --print-timeout`) |
| `GT1000_ROUTING_EVAL_SUITE` | `describe_current_patch,describe_user_slot,connection_timeouts` |

**Requirements:** agy must be logged in and able to reach the model API. Use `--dangerously-skip-permissions` (the run script passes this). Do **not** pass `--sandbox` for live GT-1000 MIDI. Live MIDI needs a full-access host (Cursor/Terminal with CoreMIDI), same as `scripts/gt1000-agent --live`.

Discover chat path without running agy:

```sh
scripts/gt1000-routing-eval-run discover --workdir ~/proj/gt1000-scratch
```

Replay a saved JSONL without calling agy:

```sh
scripts/gt1000-routing-eval-run run --scenario describe_user_slot \
  --jsonl ~/.gemini/tmp/gt1000-scratch/chats/session-....jsonl
```

Opt-in unittest (runs agy; slow; needs hardware/API):

```sh
GT1000_ROUTING_EVAL_AGY=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest tests.test_skill_routing_eval.SkillRoutingEvalAgyLiveTests -q
```

## Add scenarios

1. Add a row to `tests/skill_routing_eval/scenarios.json` (`index_intent` must match `skill-routing-index.md` when applicable).
2. Add `tests/skill_routing_eval/traces/good_<id>.json` and/or `bad_*.json` with `"expect_fail": true`.
3. Run `tests.test_skill_routing_eval`.

Trace JSON shape:

```json
{
  "scenario_id": "describe_current_patch",
  "expect_fail": false,
  "events": [
    {"type": "user", "text": "What does my patch sound like?"},
    {"type": "shell", "command": "... gt1000-agent --pretty patch musician-summary --live --timeout 15"}
  ]
}
```

Event types: `user`, `harness`, `shell`, `reference_read` (grep/cat under `references/`).

## Related

- Routing card: `SKILL.md`
- Intent table: `skill-routing-index.md`
- Scorer implementation: `tools/gt1000/skill_routing_eval/`
- Run harness: `scripts/gt1000-routing-eval-run`

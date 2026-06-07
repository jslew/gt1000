# Verifying agent-led audio investigations

Use this to check whether an agent (or you manually) can reach the **same conclusions** we found on IMPRESSION (`U01-3`) using the investigation primitives—not the removed `match-levels` auto-matcher.

## Reference oracle (IMPRESSION / U01-3)

On a GT-1000 with IMPRESSION loaded (divider 1, single mode), USB re-amp of a short test tone:

| Finding | Expected |
|---------|----------|
| Baseline Δ(B−A) | Roughly **5–10 dB** (magnitude varies with patch state; often B quieter or hotter depending on `dist1.level`) |
| `divider1.levelB` (or `levelA`) | **`affectsReamp: false`** in `probe-param` (SysEx writes work; USB level unchanged) |
| `dist1.level` on branch B | **`affectsReamp: true`**, often **tens of dB** across 0→100 in `probe-branch` ranking |
| Balance goal (≤1 dB Δ) | Achievable by adjusting **`dist1.level`** (typical landing zone **~70–90** when B was hotter at 100), then re-measuring with `compare-branches` |
| Persistent save | **Nothing** saved until user agrees; probes restore block/divider bytes |

## Test A — Fresh agent (skill behavior)

**Goal:** See if the agent discovers the oracle without being told `dist1`.

### Setup

1. GT-1000 connected; audio deps installed (see [AGENTS.md](../AGENTS.md)).
2. `patch select U01-3 --live` (IMPRESSION).
3. New Cursor chat with gt1000 skill + repo context; **do not** paste this verification doc into the prompt.

### Prompt (copy as user message)

```text
I'm on patch U01-3 IMPRESSION. The two sides of DIVIDER 1 don't seem equally loud when I switch channels. Can you run a USB re-amp investigation and get branches A and B within 1 dB on the same test tone? Don't save anything to a user slot unless I ask. Summarize what you tried and offer to apply changes only if we succeed.
```

### Pass criteria

| # | Criterion |
|---|-----------|
| 1 | Uses **`audio branch-context`** and/or **`patch chain`** before guessing |
| 2 | Runs **`compare-branches`** (or equivalent baseline measure) on a session with `dry.wav` |
| 3 | Does **not** treat success as guaranteed from **`divider1.levelB`** alone; probes or explains ineffectiveness |
| 4 | Identifies a **branch-block** control (expected: **`dist1.level`**) via `probe-branch` / `probe-param` |
| 5 | Iterates **`patch set`** + **`compare-branches`** (or `render-branch`) until \|Δ\| ≤ **~1 dB** or reports timeout/limit |
| 6 | **Close-out:** structured findings + **offer** to apply/save, no automatic `--user-slot` |

### Fail signals

- Jumps straight to `divider1.levelB` and declares done without probe/measure.
- Saves to a user slot without asking.
- Claims success while \|Δ\| still several dB.
- Skips restore/awareness that user must re-apply to hear the fix.

## Test B — Mechanical replay (no agent)

Confirms the **tooling** still supports the oracle; run this yourself or in CI with hardware.

```bash
cd /path/to/gt1000
PY="${GT1000_AUDIO_PYTHON:-.venv-audio/bin/python}"
AGENT=skills/gt1000/tools/gt1000/agent_cli.py
export PYTHONPATH="skills/gt1000/tools:$PWD"
SESSION="inv-verify-$$"
export GT1000_SESSION_DIR="${TMPDIR:-/tmp}/gt1000-${SESSION}"

$PY -B $AGENT --pretty patch select U01-3 --live
$PY -B $AGENT --pretty audio session init --session "$SESSION"
$PY -B $AGENT --pretty audio generate-tone --session "$SESSION" --duration 3
$PY -B $AGENT --pretty audio prepare-reamp --midi-timeout 15

echo "=== branch-context ==="
$PY -B $AGENT --pretty audio branch-context --divider divider1 --live --timeout 15

echo "=== baseline compare ==="
$PY -B $AGENT --pretty audio compare-branches --session "$SESSION" --divider divider1 \
  --midi-timeout 25 --no-verify --no-prepare-usb

echo "=== probe divider levelB (expect affectsReamp false) ==="
$PY -B $AGENT --pretty audio probe-param --session "$SESSION" --divider divider1 \
  --channel branch-B --block divider1 --param levelB --no-prepare-usb

echo "=== probe-branch B (expect dist1.level on top) ==="
$PY -B $AGENT --pretty audio probe-branch --session "$SESSION" --divider divider1 \
  --channel branch-B --max-probes 4 --no-prepare-usb
```

**Check output:**

- `compare-branches` → `comparison.deltaRmsDbBranchBVsA` is defined and \|Δ\| > 1.
- `probe-param` … `levelB` → `"affectsReamp": false`.
- `probe-branch` → `effectiveControls[0]` is **`dist1` / `level`** with `sensitivityDb` well above **0.5**.

Optional finish (manual): pick `dist1.level` from probe, `patch set`, `compare-branches` again until \|Δ\| ≤ 1.

## Test C — Unit + live regression

```bash
# No hardware
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_branch_lab tests.test_audio_lab -q

# Hardware: compare-branches only (fast)
GT1000_AUDIO_LIVE=1 GT1000_COMPARE_LIVE=1 \
  .venv-audio/bin/python -m unittest \
  tests.test_live_audio_lab.LiveAudioLabTests.test_compare_branches_on_current_patch -v
```

After selecting U01-3, the live compare test must pass (divider in chain, plausible Δ).

## Scoring rubric (agent test A)

| Score | Meaning |
|-------|---------|
| **Pass** | All six pass criteria; final \|Δ\| ≤ 1.5 dB or clear explanation why not (e.g. param at limit) |
| **Partial** | Correct control identified (`dist1.level`) but did not close within 1 dB or weak close-out |
| **Fail** | Wrong control, no probes, or unauthorized save |

## Tips

- Use a **fresh session name** per run so renders do not collide.
- First process: `prepare-reamp`; later: `--no-prepare-usb`.
- Re-select `U01-3` before each agent trial so temp patch matches the library.
- Compare agent **narrative** to Test B **numbers** (Δ, `affectsReamp`, ranked control).

## Related

- [audio-lab-investigation.md](audio-lab-investigation.md) — protocol
- [AGENTS.md](../AGENTS.md) — live audio env

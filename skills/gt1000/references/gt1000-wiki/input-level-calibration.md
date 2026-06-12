# Agent Input Level Calibration Workflow

Musician-facing background: [Input Level and Gain Staging](input-level-gain-staging.md). This page is the **agent runbook** for calibrating a **global input preset** (MENU → IN/OUT SETTING → INPUT, slots 1–10) for a specific guitar and saving it.

## What audio lab can and cannot do

| Can help | Cannot replace |
|----------|----------------|
| Confirm USB capture works (`audio ports`, `audio probe`) | The unit’s **input meter** and limiter arrow (analog front-end + A/D) |
| Rough **relative** level on USB **main 1–2** or **dry 3–4** while the user plays hard | A direct read of “just below clip” on the INPUT screen |
| Short session clips (`audio record-dry --bus main`) for before/after comparison | Input gain staging **before** the digital chain—USB wet/dry is **after** input gain is applied |

**Honest rule:** Treat USB peak/RMS as a **secondary hint** only. Primary stop rule is the user watching the GT-1000 input meter (or hearing edge-of-limiter distortion), then backing off one step. Do not run re-amp loops to “find” input level; that optimizes the wrong stage.

## Preconditions

- GT-1000 connected; live MIDI works (`doctor --live`, `ports --live --timeout 8`).
- **Quiet room**; same cable and guitar you will gig with.
- **Effects off** on the temp patch for the test: `patch apply default --live --verify --timeout 20` (pass-through, switchable blocks off). User may also use a clean user slot they trust.
- Pick an **unused or dedicated** global input preset number (1–10) for this instrument; note current values with `system inputs --live --number N`.
- **Permission:** global/system writes require explicit user approval before `system inputs-set` (see skill permission gates).
- **Optional USB:** macOS microphone privacy for the host app; `pip install -r skills/gt1000/requirements-audio.txt` if using `audio probe` / `audio record-dry`.

## Workflow (numbered)

1. **Profile / intent** — Confirm guitar name, pickup type (passive vs active), and which input preset slot to use or create.
2. **Baseline read** — `system inputs --live --number N` → record `name`, `inputLevelDb`.
3. **Clean test patch** — `patch apply default --live --verify --timeout 20` on the **temporary** patch (try gate; not a user slot).
4. **Assign patch to preset (user or inspect)** — Patch MASTER → INPUT SETTING should follow **SYSTEM** or the chosen preset `N`. If unsure, `patch musician-summary --live` and confirm with the user which global preset the patch uses.
5. **Optional USB sanity** — `audio probe --duration 3` while the user plays **as hard as they would live**; note peaks on channels 1–2 (main) or 3–4 (dry). Use only to detect silence, wrong device, or gross level jumps between iterations—not as the clip target.
6. **Calibrate on the unit (primary)** — User plays hard; for passive/low output, raise level until the meter **just** touches limit, then back off slightly. For hot/active pickups, start near **0 dB** and reduce if needed. Agent coaches; user operates MENU if they prefer.
7. **Iterate via CLI (after persist approval)** — Adjust with verified writes, e.g. `system inputs-set N input-level 12 --live --verify --timeout 20`. That updates **both** the named preset slot and the **active** IN/OUT input level (what the front panel shows). Steps of **1 dB** are safe; re-read with `system inputs --live --number N` and `system inout --live` each round.
8. **Stop rules**
   - **Target:** hard playing sits **just below** the limiter arrow—not pegged, not barely moving.
   - If the user reports limiter/ harsh splatter → lower 1–3 dB and re-test.
   - If drives still feel weak after input is sane → stop input calibration; escalate to block gain staging ([input-level-gain-staging.md](input-level-gain-staging.md)).
9. **Name and save**
   - **Name:** `system inputs-set N name "TELE NKL" --live --verify --timeout 20` (≤16 ASCII chars), or user renames on the unit.
   - **Persist:** Input presets live in **system** memory; verified `inputs-set` writes are already stored on the device. Document the slot in the user profile (`gt1000-profile.md`) with guitar → preset number → final dB.
10. **Pair output path** — If tone into amp/PA/phones is still wrong, `system inout --live` (output select)—see gain-staging doc.

## CLI quick reference

```sh
# Read preset 3
$GT1000_AGENT --pretty system inputs --live --number 3 --timeout 8

# Set level + name (requires user approval for global write)
$GT1000_AGENT --pretty system inputs-set 3 input-level 12 --live --verify --timeout 20
$GT1000_AGENT --pretty system inputs-set 3 name "TELE" --live --verify --timeout 20

# Optional USB level check while playing (not a clip meter)
$GT1000_AGENT --pretty audio probe --duration 3

# Optional short main-bus clip for A/B between dB steps
$GT1000_AGENT --pretty audio record-dry --session input-cal --duration 4 --bus main
```

## Agent response style

- Describe results in musician terms (preset name, dB, “headroom below limiter”).
- Do not lead with SysEx or JSON; keep CLI names internal unless the user asked for tooling detail.
- After calibration, remind them to select that INPUT preset (or SYSTEM + active slot) when switching guitars.

## Escalation

- Per-patch MASTER INPUT SETTING override → `patch musician-summary` / block detail, not global preset.
- Wrong amp/loop feel → `system inout`, [parameter-guide.md](parameter-guide.md).
- Low-level addresses → [address-map.md](../midi-reference/address-map.md).

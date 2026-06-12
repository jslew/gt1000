# Input Level and Gain Staging

Paraphrased from BOSS setup guidance and community experience (see [Sources](sources.md)). Not a substitute for the official Parameter Guide.

## What “input level” is

- **Global presets:** MENU → IN/OUT SETTING → INPUT. The unit stores **ten named input-level presets** (roughly **−20 dB to +20 dB** offset). Use these when you change guitars or pickup types.
- **Per patch:** PATCH **MASTER** block → **INPUT SETTING** chooses **SYSTEM** (follow the global preset) or **preset 1–10** for that patch only.
- **Where it sits:** This is the **first gain stage** into the digital engine—before amp models, drives, and other blocks. It is **not** the same as per-block drive/level knobs or PATCH LEVEL on MASTER.

Do not confuse with **CONTROL ASSIGN INPUT SENS** on MASTER (performance sensitivity), or with **USB dry/FX mix** under IN/OUT (recording/re-amp paths).

## Why it matters

Amp sims, drives, fuzz, and compressors were designed expecting a sensible guitar level at the converter. Too low → models feel **thin, weak, or “digital”**; drives need extreme block levels; compressors seem inaudible; harmonics and sustain disappoint. Too high → **limiter** at the input meter arrow, then harsh clipping; headphone noise if you chase the arrow with volume cranked.

Community reports often describe a large improvement after calibrating input level **and** matching **output select** to the real rig (amp front, effects loop, PA, headphones).

## How to set it (on the unit)

BOSS’s recommended procedure (effects/amps **off** for the test):

1. Play as hard as you realistically would live.
2. **Lower-output / passive pickups:** raise input level until you **just** hear clipping or see the meter at the limit point, then back off slightly so it stays clean.
3. **Higher-output / active pickups:** start near **0 dB**; if clipping, turn down slightly.
4. Name and store presets per guitar (e.g. Tele vs humbucker). Community examples for **noiseless single-coils** often land around **+10 to +15 dB**; **humbuckers** often near **0 to +3 dB**—always verify on **your** guitar and playing dynamics, not by copying a number.

**Meter cue:** The target is **just below** the limit indicator when you play hard—not pegged at the arrow (limiter) and not barely moving.

## Typical symptoms and first checks

| Symptom | Likely cause | Inspect first (CLI) |
|--------|----------------|---------------------|
| Drives/amps weak, fuzzy lifeless, compressor “does nothing” | Input level too low | `system inputs --live --number N` for each guitar preset you use |
| Harsh, splattery, limiter pumping, very loud headphones | Input too high or output/volume stacked | `system inputs`; reduce input before cranking phones/main level |
| Clean “chirp” on pick, sounds like a mic’d amp into a guitar amp | Wrong **output select** for rig | `system inout --live` (main/sub output select) |
| Huge level jump when toggling a block | Per-block levels not gain-staged | `patch musician-summary --live` then `patch block <id> --live` on drives/preamps |
| 4CM / real amp still wrong after input OK | Loop vs main input, cab size in output name | `system inout`; confirm user’s amp path (RETURN vs MAIN INPUT) in wiki terms |
| USB recording only | Dry/monitor paths | `system inout` USB fields; see [USB Audio](usb-audio.md) |

## Relationship to pickups, 4CM, USB

- **Pickups:** Treat input presets as **guitar-dependent**, not patch-dependent, unless you deliberately assign INPUT SETTING per patch in MASTER.
- **4CM / external amp:** Input level still feeds the modeler; **output select** must match how audio returns to the amp (effects loop vs front input). Mismatch is a common “almost clean” or wrong-cab-feel report.
- **USB:** Input level affects what the unit processes; USB **DIR MON / mix / dry** settings affect what you **hear** while recording, not a substitute for calibrating INPUT presets.

## Per-patch gain staging (after input level)

Once input level is sane:

- Match **bypass vs engaged** level across blocks (community practice: only **preamp** or an intentional **boost** should raise level noticeably).
- If the guitar’s volume knob no longer cleans up gain after a big input boost, input may be too hot—back off slightly.

## Agent workflow

**Inspect / troubleshoot:** `system inputs --live --number N`; `system inout --live` for output-select pairing; `patch musician-summary --live` when block gain staging is suspect.

**Calibrate and save a global preset for one guitar:** follow [Input Level Calibration Workflow](input-level-calibration.md) (`system inputs-set … --live --verify` after explicit persist approval; optional `audio probe` only as a secondary USB hint).

Escalate parameter semantics: [parameter-guide.md](parameter-guide.md). Low-level addresses: [address-map.md](../midi-reference/address-map.md).

## Sources

- Official: BOSS GT-1000 Ultimate Guide “Setting the Input Level”; Parameter Guide IN/OUT → INPUT.
- Community: [r/guitarpedals discussion, Oct 2020](https://www.reddit.com/r/guitarpedals/comments/jeo4rh/input_level_make_the_gt1000_sound_1000_times/) — gain staging importance, symptom reports, output-select pairing; paraphrased only.

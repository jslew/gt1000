# GT-1000 skill detail

Load this file when the routing card (`SKILL.md`) or `references/skill-routing-index.md` points you here: workflows, timeout tables, command catalogs, progressive disclosure, and safety detail. Resolve `$GT1000_AGENT` per `SKILL.md` before running commands.

## Sequential live MIDI

**Read `SKILL.md` → One CLI at a time (critical)** before any live work.

The GT-1000 cannot safely serve overlapping SysEx sessions. One `gt1000-agent` process at a time, always — no parallel agent tool calls, no shell `&&` between CLI invocations. The CLI holds an exclusive lock at `~/.gt1000-agent/cli.lock` and exits `75` if another instance is running. When mirroring edits to a user slot, run each `--user-slot` write as its own completed command after the temp-patch step.

## Live Timeout Guidance

Choose timeouts that let the device finish normal SysEx reads before assuming the session is wedged:

- Use `--timeout 8` for `ports`, `doctor` without write checks, and small system views.
- Use `--timeout 15` for current-patch musician summaries, performance views, chains, controls, block details, and other focused single-patch reads.
- Use `--timeout 20` for full current-patch summaries, setlist/level audits, and verified temporary-patch writes.
- Use `--timeout 30` for persistent user-slot or preset musician summaries, bank reads, clone, import/export, exchange, insert, destructive recovery, or any operation that reads back persistent slots.

For commands spanning multiple slots, treat the timeout as the per-slot or per-read allowance and expect total wall-clock time to scale with the number of slots. **Still run only one live CLI invocation at a time** — multi-slot commands are sequential inside the tool; do not overlap them with another live command. If a command returns its own timeout error, do not immediately retry with a lower timeout; run `$GT1000_AGENT --pretty ports --live --timeout 8` once (alone), then follow the connection recovery path in `SKILL.md` if that fails.

## Progressive Disclosure Routing

Keep routine patch work on compact device summaries first. Do not load low-level MIDI tables, long manual extracts, or obscure parameter references unless the user request needs them, the device output is ambiguous, or a safe edit requires internal validation.

**Enforcement:** follow **Agent workflow** in `SKILL.md` (one authoritative read, no reference mining until CLI is insufficient, falsifiable hypotheses). The bullets below are **escalation paths**, not a checklist to run in full.

Use this routing:

- Patch description, "what is this sound?", "details of patch <slot>", or quick signal-chain review: load the user profile first, run onboarding if it is missing, then run `patch musician-summary` for a concise answer. Use `patch summary` only when the user asks for exhaustive block/type detail or the musician summary lacks a fact needed to answer. Do not open MIDI reference pages unless a decoded field is unclear.
- When the user asks what is "active", "in use", "currently shaping the tone", or "currently affecting the sound", account for **reachability** as a separate concept from on/off.
  - **Meaning**: a block can be present in the patch (and even have parameters and an on/off state) but still be **unreachable** in the current routing path (for example, on an inactive fixed divider branch). Unreachable blocks do not affect the audio until routing or control mappings make them reachable.
  - **How to interpret**: decide based on the question whether to report (a) what is affecting the sound *right now* vs (b) what is part of the patch's playable potential if routing/controls change. Use `patch chain` or `patch summary` and consult `chain.elements[].isUnreachable`, `unreachableReason`, and `unreachablePath` to explain the distinction when relevant.
- Patch comparison questions: use `patch diff <source> <target> --live` for user slots or `patch diff <before.json> <after.json>` for saved full patch dumps before opening lower-level views. Report the result as musical differences in sound, level, controls, routing, and library placement.
- Setlist readiness questions: use `patch setlist-audit <bank-or-slots> --live` to check patch-level jumps, tuner access, BPM mismatches, expression-pedal changes, and SYSTEM-preference controls.
- Patch loudness matching questions: use `patch level-audit <bank-or-slots> --live` before writing, then `patch normalize-levels <bank-or-slots> --target <level> --live --verify` when the user wants user-slot levels changed.
- Divider branch balance or “match the clean/drive level” on the same test tone: run a USB re-amp investigation internally (see `references/audio-lab-investigation.md`; verification checklist in `references/audio-lab-investigation-verification.md`). When finished, **present findings** in plain language—starting gap, what control actually worked, final loudness vs their goal. **Do not save** anything to a user slot automatically. If the goal was met (or they accept a partial fix), **offer** to apply the same block changes to the current patch for them to try by ear, or to save to a named user slot only if they say so. Remind them that measurement restores the patch after each probe, so nothing is stored until they agree.
- Reference-tone matching/chasing: treat this as an agent-facilitated audio lab workflow, not a user-facing CLI recipe. Ask for an isolated reference WAV and either use an existing dry-take session or create one. Internally run reference profiling, bounded candidate planning, and the temp-patch render/rank loop. Present the result as: reference used, dry take/session, baseline rank/score, top candidate(s), what changed musically, render paths available for audition, and whether temp edits were restored. Make clear that scoring is approximate and not a guarantee of a perceptual match. **Do not persist** a winning candidate; offer to re-apply it temporarily for listening or save it to a named user slot only after explicit approval.
- Common musician edit requests such as solo boost, tap tempo, delay toggle, tuner-on-control, or expression-volume setup: use `patch intent <intent> --live --verify` before dropping to lower-level control editors.
- Switch/control questions: run `patch performance` first for stage-use questions and `patch controls` for raw control/Assign details. Open `references/midi-reference/patch-controls.md` only if a raw/unknown function appears or the user asks how a physical control is encoded.
- Assign behavior, MIDI CC, tuner control, or assigned-off-block reachability: run `patch controls` or `patch summary` first. Open `references/midi-reference/assigns.md` only for source IDs, target min/max encoding, target table caveats, or write planning.
- Installing tuner control: use `patch tuner-assign --live --verify` to install the supported tuner control mapping. Ask before writing it persistently with `--user-slot`.
- Sending a MIDI CC for a known Assign source: use `midi cc <controller> <value> --channel N --live` only after confirming the mapped source and RX channel. Do not send raw MIDI bytes.
- Sending a Program Change directly: prefer `patch select <slot>` for user-slot selection; use `midi pc <program> --channel N --live` only when the user explicitly asks for Program Change numbers or after checking `system pcmap`.
- Sending Bank Select: use `midi bank-select <msb> [lsb] --channel N --live` only when the user explicitly needs bank-select/channel-voice behavior; follow it with `midi pc` if selecting via an external-style bank/program sequence. For selecting the GT-1000 itself, prefer `patch select` unless the user is deliberately testing Bank Select.
- Signal-chain routing, divider/mixer behavior, chain element values, or reserved elements: run `patch chain` or `patch summary` first. Open `references/midi-reference/patch-effect.md` only when raw chain/routing details matter.
- STOMPBOX questions: explain the user-facing caution from `references/gt1000-wiki/owner-manual.md`; use `patch stompbox --live` when the user asks whether a patch is using shared STOMPBOX slots.
- System/global MIDI, IN/OUT, or control preference questions: use the relevant `system` CLI view first. Open `references/midi-reference/README.md` or address-map notes only when addresses, sizes, or SysEx behavior need explanation.
- Connectivity or intermittent-timeout diagnosis: use `doctor --live` first. Report user-actionable device connection findings first; include protocol/tooling details only if the user asks or they are needed for recovery.
- System metronome BPM questions: use `system common` first. Open address-map notes only if the user asks about the underlying System Common address or BPM nibble encoding.
- Manual-mode switch questions: use `system manual` first. Open address-map notes only if the user asks how manual-mode NUM functions are encoded.
- Program Change mapping questions: use `system pcmap --bank N` first for a focused bank read, or omit `--bank` only when comparing the full map. Open address-map notes only if the user asks about storage layout or patch-value encoding.
- Input-setting questions: use `system inputs --number N` first for one named input setting, or omit `--number` only when comparing all ten.
- Calibrating/saving a global input preset for one guitar: open `references/gt1000-wiki/input-level-calibration.md`; use `system inputs-set <N> input-level <dB> --live --verify` only after explicit persist approval.
- Parameter meaning or musical interpretation: use CLI block detail first, then load only the relevant manual/wiki page from `references/gt1000-wiki/`.
- Turning decoded blocks on or off: use `patch enable <block>` or `patch disable <block> --live --verify --timeout 20`, which routes through the validated block `sw` parameter. Open `references/midi-reference/cli-usage.md` only if the command surface or persistent-slot guardrails need explanation.
- Changing a decoded effect type: use `patch type <block> <type> --live --verify --timeout 20`, which routes through the validated block `type` parameter. Use `patch block <block>` first if you need the current type or decoded options.
- Moving decoded signal-chain blocks: use `patch move <block> --before <block>` or `patch move <block> --after <block> --live --verify --timeout 20`. Run `patch chain` first if the requested relative order is ambiguous.
- Patch cleanup (tidy unreachable blocks): use `patch cleanup --live --verify --timeout 20` to move blocks/branch segments that are currently unreachable (fixed inactive divider subchain, or off-and-unassigned blocks) to the end of the chain without changing block settings. Use `--user-slot <slot> --timeout 30` to make it persistent.
- Mapping a decoded target to MIDI CC: use `patch assign-cc <number> <block> <parameter> --cc <n> --mode <toggle|moment> --live --verify --timeout 20`. Open `references/midi-reference/assigns.md` only when source IDs, target min/max offset encoding, or target-table quirks matter.
- Patch BPM edits: use `patch set-bpm <bpm> --live --verify --timeout 20` for tempo changes. Open `references/midi-reference/patch-effect.md` only if the user asks about the four-nibble `BPM * 10` encoding.
- Writes: build a CLI `patch plan` or typed `patch set` intent first. Open low-level references only to validate address/range/model quirks before changing the validator.

## Live Patch Inspection

Use these commands internally for live patch and library inspection. The musician-facing answer should describe the patch, controls, routing, levels, or user-slot/library behavior rather than the command output.

```sh
$GT1000_AGENT --pretty ports --live --timeout 8
$GT1000_AGENT --pretty doctor --live --timeout 8
$GT1000_AGENT --pretty patch summary --live --timeout 20
$GT1000_AGENT --pretty patch overview --live --timeout 8
$GT1000_AGENT --pretty patch chain --live --timeout 15
$GT1000_AGENT --pretty patch controls --live --timeout 15
$GT1000_AGENT --pretty patch performance --live --timeout 15
$GT1000_AGENT --pretty patch musician-summary --live --timeout 15
$GT1000_AGENT --pretty patch slot U01-1 --live --view musician-summary --timeout 30
$GT1000_AGENT --pretty patch bank U01 --live --view musician-summary --timeout 30
$GT1000_AGENT --pretty patch diff U10-1 U10-2 --live --timeout 30
$GT1000_AGENT --pretty patch setlist-audit U10 --live --timeout 20
$GT1000_AGENT --pretty patch level-audit U10-1 U10-2 --live --timeout 20
$GT1000_AGENT --pretty patch normalize-levels U10-1 U10-2 --target 90 --live --verify --timeout 20
$GT1000_AGENT --pretty patch intent solo-boost --control ctl4 --amount 10 --live --verify --timeout 20
$GT1000_AGENT --pretty patch block delay1 --user-slot U01-1 --timeout 20
$GT1000_AGENT --pretty patch clone U10-1 U10-2 --live --verify --timeout 30
$GT1000_AGENT --pretty midi cc 80 127 --channel 1 --live
$GT1000_AGENT --pretty midi bank-select 0 --channel 1 --live
$GT1000_AGENT --pretty midi pc 1 --channel 1 --live
$GT1000_AGENT --pretty system common --live --timeout 8
$GT1000_AGENT --pretty system midi --live --timeout 8
$GT1000_AGENT --pretty system pcmap --live --bank 1 --timeout 8
$GT1000_AGENT --pretty system inputs --live --number 1 --timeout 8
$GT1000_AGENT --pretty system inputs-set 3 input-level 12 --live --verify --timeout 20
$GT1000_AGENT --pretty system inout --live --timeout 8
$GT1000_AGENT --pretty system effects --live --timeout 8
$GT1000_AGENT --pretty system pitch --live --timeout 8
$GT1000_AGENT --pretty system controls --live --timeout 8
$GT1000_AGENT --pretty system manual --live --timeout 8
$GT1000_AGENT --pretty patch block delay1 --live --timeout 15
$GT1000_AGENT --pretty patch stompbox --live --timeout 15
```

Use `musician-summary` first for concise human patch descriptions. Do not follow it with `summary` for ordinary "details" requests; use `summary` only when full metadata, typed signal-chain data, and controls are explicitly needed.
Use `performance` first for stage-use questions about what the physical controls do while playing.
Use `slot` or `bank` for persistent user patch inspection; these read user patch memory directly and do not select the patch on the unit.
Use `patch block --user-slot` for targeted persistent-slot block inspection.

## Safe Edit Workflow

Build plans before writing:

```sh
$GT1000_AGENT --pretty patch plan default
$GT1000_AGENT --pretty patch plan 4cm-template
```

Temporary patch writes through validated CLI plans should be read-back verified internally:

```sh
$GT1000_AGENT --pretty patch apply default --live --verify --timeout 20
$GT1000_AGENT --pretty patch apply 4cm-template --live --verify --timeout 20
```

Persistent patch writes may target any valid user slot. For global settings, MIDI settings, or unsupported edit intents, use or add a typed command that validates internally:

- target memory area and patch/global address
- parameter range and encoding
- model-specific quirks
- read-back verification

Examples of currently implemented verified writes:

```sh
$GT1000_AGENT --pretty patch apply default --live --user-slot U10-1 --verify --timeout 30
$GT1000_AGENT --pretty patch clone U10-1 U10-2 --live --verify --timeout 30
$GT1000_AGENT --pretty patch set delay1 time 380 --live --user-slot U10-3 --verify --timeout 30
$GT1000_AGENT --pretty patch enable delay1 --live --verify --timeout 20
$GT1000_AGENT --pretty patch type dist1 T-SCREAM --live --verify --timeout 20
$GT1000_AGENT --pretty patch move delay1 --before chorus --live --verify --timeout 20
$GT1000_AGENT --pretty patch assign-cc 3 delay1 sw --cc 80 --mode moment --live --verify --timeout 20
$GT1000_AGENT --pretty patch set-bpm 120.0 --live --verify --timeout 20
$GT1000_AGENT --pretty patch tuner-assign --live --verify --timeout 20
$GT1000_AGENT --pretty patch normalize-levels U10-1 U10-2 --target 90 --live --verify --timeout 20
$GT1000_AGENT --pretty patch intent delay-toggle --control ctl2 --block delay1 --live --verify --timeout 20
```

Persistent operations require an explicit user decision per **Permission gates** in `SKILL.md`—not a harness continuation alone.

## Reference Tone Chase Workflow

Use `references/audio-lab-reference-tone.md` for reference-tone matching/chasing. It owns the agent-run audio lab loop, candidate verification rule, reporting shape, and persistence gate.

## Description Workflow

For a human patch description:

1. Load the user profile memory; if it does not exist, complete onboarding and create it before reading the patch.
2. Run `patch musician-summary` (current patch) or `patch slot <slot> --view musician-summary` (user slot).
3. Use `descriptionSignalChainSummary` and `descriptionElements` as the default human-facing chain.
4. Mention only the audible/playable chain first.
5. Mention switched-off blocks if assigned to a physical control, because they are part of the patch's playable potential.
6. Read individual block details only when needed to explain specific settings.
7. If a patch slot reports an unexpected name after selection, trust the live patch name and say so briefly.

For an initialized or sparse patch, keep the answer short and avoid listing dormant off blocks unless asked.

## Controls Workflow

For physical switch mapping:

1. Load the user profile memory; if it does not exist, complete onboarding and create it before reading controls.
2. Use `$GT1000_AGENT --pretty patch performance --live --timeout 15` for musician-facing stage behavior.
3. Use `$GT1000_AGENT --pretty patch controls --live --timeout 15` when raw control/Assign details are needed.
4. For direct controls, reason from canonical control fields: `functionId`, `functionKind`, `functionTargetRef`, and `canEnableBlock`; use `functionDisplayName` only for musician-facing labels.
5. If output is ambiguous, consult `references/midi-reference/patch-controls.md` and `references/midi-reference/assigns.md`.
6. Report direct switch functions plus active Assign overlays.

## Safety Rules

- The normal endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Follow **Permission gates** in `SKILL.md` before changing user patches, global/system settings, patch order, initialize/exchange operations, Assigns, or anything persistent.
- SysEx writes are not gated the same way as Channel Voice messages; verify MIDI RX channel when CCs do not work.
- Use supported, validated intents for every write.

---
name: gt1000
description: "GT-1000 v4+ musician-facing interface for conversing with a connected BOSS/Roland device: patch inspection, signal-chain explanation, physical controls, performance behavior, patch library/user-slot workflows, and safe validated musical edits. Use when working on GT-1000 or GT-1000CORE sounds, controls, routing, patch libraries, manual concepts, parameter meanings, live patch descriptions, or edit planning. Discuss CLI, SysEx, MIDI internals, or implementation details only when directly asked or when needed internally to keep an edit safe."
---

# GT-1000 Musician Interface

## Scope

Use the bundled GT-1000 references and CLI internally to help a musician inspect, understand, organize, and safely edit a connected BOSS/Roland GT-1000 or GT-1000CORE.

Do not send arbitrary low-level writes. Use supported, validated commands and intents.

The user-facing scope is the GT-1000 as a musical device: sounds, signal chains, routing, blocks, patch/user-slot libraries, Assigns, physical controls, MIDI-facing performance behavior, and global/system settings. A narrow helper command is not a conceptual device boundary. If a requested edit is not supported by the current tooling, do not fake it or send arbitrary low-level data; explain the limitation or ask to extend the toolchain.

## Response Style

Default to musician-facing language. Talk about what the patch sounds like, where blocks sit in the signal chain, what switches and pedals do, how user slots/banks/libraries behave, and what an edit will change while playing.

Do not mention CLI commands, JSON fields, raw MIDI/SysEx addresses, encoded values, parser behavior, or implementation files in normal answers. Use those details internally, and surface them only when the user directly asks how the tooling works, asks for debugging details, or needs enough technical context to approve a potentially persistent or risky change.

For edits, describe the musical intent and safety boundary first: what will change, whether it affects the temporary patch or a user slot/global setting, and whether verification/read-back succeeded. Keep protocol details out of the answer unless requested.

## Runtime Resources

Resolve every bundled resource relative to this `SKILL.md` file, not relative to the user's current working directory or a repo root. Before running any GT-1000 command, locate the actual filesystem directory containing the loaded `gt1000` skill's `SKILL.md`. Use the skill path provided by the active harness when available, or the exact path of the `SKILL.md` you just opened. Then set:

```sh
GT1000_AGENT="<skill-dir>/scripts/gt1000-agent"
```

`<skill-dir>` is a placeholder for the real installed skill directory; do not run it literally. If the current project has `.agents/skills/gt1000/SKILL.md`, treat that as the active installed skill for this project and prefer `.agents/skills/gt1000/scripts/gt1000-agent` over any source-repo or global copy. Do not substitute another matching wrapper from a development checkout after loading a project-installed skill.

If the harness does not expose the skill path, resolve the bundled wrapper with project-installed copies first:

```sh
GT1000_AGENT=""
for candidate in \
  "$PWD/.agents/skills/gt1000/scripts/gt1000-agent" \
  "$PWD/skills/gt1000/scripts/gt1000-agent"
do
  if [ -x "$candidate" ]; then GT1000_AGENT="$candidate"; break; fi
done
if [ -z "$GT1000_AGENT" ]; then
  GT1000_AGENT="$(find "$PWD/.agents/skills" "$PWD" "$HOME/.agents/skills" "$HOME/.codex/skills" -path '*/gt1000/scripts/gt1000-agent' -type f -perm -111 2>/dev/null | head -n 1)"
fi
test -n "$GT1000_AGENT" || { echo "gt1000-agent wrapper not found" >&2; exit 1; }
```

Use `$GT1000_AGENT ...` for all CLI examples below. Do not try `scripts/gt1000-agent` from the user's current directory unless the current directory is the skill directory. If a bundled reference page shows `scripts/gt1000-agent`, interpret it as `$GT1000_AGENT` after resolving the skill directory. When multiple wrappers exist, the correct one is the wrapper bundled with the loaded skill, not merely the first path that exists elsewhere under the user's home directory.

Other bundled resources:

- Manual/wiki references: `references/gt1000-wiki/`
- MIDI/SysEx references: `references/midi-reference/`
- User profile onboarding: `references/user-profile-onboarding.md`

## Operational Principles

- Always check for the user profile first, before live reads, summaries, edit planning, or reference lookups. If no profile exists, run the onboarding flow in `references/user-profile-onboarding.md` before continuing with the GT-1000 task.
- Always use the bundled CLI and markdown internally to interact with the device.
- Live GT-1000 MIDI reads/writes require a harness process that can access macOS CoreMIDI. In Codex CLI, normal workspace/read-only sandbox mode can block CoreMIDI and cause misleading live timeouts; use yolo/`--dangerously-bypass-approvals-and-sandbox` or `-s danger-full-access` for live device interactions. The CLI fast-fails when it detects this sandbox block.
- For any musician-facing request to read or describe the current patch, run exactly `$GT1000_AGENT --pretty patch musician-summary --live --timeout 15` as the first live command. Answer from that result when it covers the request. Do not start with `overview`, `performance`, `chain`, or multiple commands; use those only when the user explicitly asks for deeper structured detail or the musician summary lacks a fact needed to answer.
- For persistent user-slot descriptions, use `$GT1000_AGENT --pretty patch slot <slot> --live --view musician-summary --timeout 30` first. Answer from that result for normal "details", "describe this patch", or "what is this sound?" requests. Do not run a follow-up `--view summary` just to enrich a concise answer; use it only when the user explicitly asks for exhaustive block/type detail or when the first result is missing a required fact.
- Run live reads sequentially. Do not chain multiple live reads with `&&` or start a second read while one is active. Separate processes can interleave GT-1000 replies on the same MIDI source.
- If a live read is interrupted or `$GT1000_AGENT --pretty ports --live --timeout 8` times out, stop additional live reads and report the connection recovery path: verify other MIDI apps such as BOSS Tone Studio are closed, reconnect or power-cycle the GT-1000, and restart macOS only if CoreMIDI endpoint enumeration still hangs. Do not assume Tone Studio is open; if the user says it was closed, treat the current agent session as stale or the Python/CoreMIDI path as transiently wedged.

## Live Timeout Guidance

Choose timeouts that let the device finish normal SysEx reads before assuming the session is wedged:

- Use `--timeout 8` for `ports`, `doctor` without write checks, and small system views.
- Use `--timeout 15` for current-patch musician summaries, performance views, chains, controls, block details, and other focused single-patch reads.
- Use `--timeout 20` for full current-patch summaries, setlist/level audits, and verified temporary-patch writes.
- Use `--timeout 30` for persistent user-slot or preset musician summaries, bank reads, clone, import/export, exchange, insert, destructive recovery, or any operation that reads back persistent slots.

For commands spanning multiple slots, treat the timeout as the per-slot or per-read allowance and expect total wall-clock time to scale with the number of slots. Do not start another live command while one is still running. If a command returns its own timeout error, do not immediately retry with a lower timeout; run `$GT1000_AGENT --pretty ports --live --timeout 8` once, then follow the connection recovery path if that fails.

## User Profile Memory

At the start of every GT-1000 skill interaction, before any device read, answer, edit plan, or reference lookup, check for a user-local profile. Do not tie this lookup to a specific LLM harness. Resolve the profile path in this order:

1. A profile path explicitly provided by the user.
2. `$GT1000_PROFILE_PATH`.
3. `$GT1000_PROFILE_DIR/gt1000-profile.md`.
4. A harness-provided persistent user memory/config directory, if the active agent environment exposes one, using `gt1000-profile.md` inside it.
5. `$XDG_CONFIG_HOME/gt1000/gt1000-profile.md`, or `~/.config/gt1000/gt1000-profile.md` when `XDG_CONFIG_HOME` is unset.
6. Legacy fallback only: `$CODEX_HOME/memories/gt1000-profile.md` or `~/.codex/memories/gt1000-profile.md`. If a legacy profile is found, load it and copy it to the first usable harness-neutral path before continuing.

If present, load it before doing anything else. If absent, do not proceed with generic guidance; use `references/user-profile-onboarding.md` to run a compact onboarding interview and create the profile first. If the user provides enough profile context unprompted, write the profile from that context and ask only for missing details that materially affect the immediate task.

Some harnesses restrict file-reading tools to the workspace even when shell commands can access user config paths. Gemini CLI is one such environment: do not use its workspace-limited file reader for `~/.config/gt1000/gt1000-profile.md`; use a shell check/read for the resolved profile path when permitted. If a profile read is blocked by the harness file tool, do not keep retrying the same inaccessible read. Use shell access, or ask the user to provide/copy the profile context into an accessible profile path such as `$GT1000_PROFILE_PATH` before continuing. Treat a tool-permission denial as "profile inaccessible", not as "no profile exists".

Use the profile as preference context, not device truth. Live CLI reads and current patch data remain authoritative.

## Start Here

Load only the reference needed for the task:

- CLI usage: `references/midi-reference/cli-usage.md`
- User-facing manual/wiki overview: `references/gt1000-wiki/README.md`
- Owner Manual extraction: `references/gt1000-wiki/owner-manual.md`
- Parameter Guide extraction: `references/gt1000-wiki/parameter-guide.md`
- Sound List extraction: `references/gt1000-wiki/sound-list.md`
- Live agent workflows: `references/gt1000-wiki/agent-workflows.md`
- Low-level MIDI/SysEx index: `references/midi-reference/README.md`
- Patch physical controls: `references/midi-reference/patch-controls.md`
- Assign encoding: `references/midi-reference/assigns.md`
- PatchEfct chain/routing: `references/midi-reference/patch-effect.md`


## Progressive Disclosure Routing

Keep routine patch work on compact device summaries first. Do not load low-level MIDI tables, long manual extracts, or obscure parameter references unless the user request needs them, the device output is ambiguous, or a safe edit requires internal validation.

Use this routing:

- Patch description, "what is this sound?", "details of patch <slot>", or quick signal-chain review: load the user profile first, run onboarding if it is missing, then run `patch musician-summary` for a concise answer. Use `patch summary` only when the user asks for exhaustive block/type detail or the musician summary lacks a fact needed to answer. Do not open MIDI reference pages unless a decoded field is unclear.
- Patch comparison questions: use `patch diff <source> <target> --live` for user slots or `patch diff <before.json> <after.json>` for saved full patch dumps before opening lower-level views. Report the result as musical differences in sound, level, controls, routing, and library placement.
- Setlist readiness questions: use `patch setlist-audit <bank-or-slots> --live` to check patch-level jumps, tuner access, BPM mismatches, expression-pedal changes, and SYSTEM-preference controls.
- Patch loudness matching questions: use `patch level-audit <bank-or-slots> --live` before writing, then `patch normalize-levels <bank-or-slots> --target <level> --live --verify` when the user wants user-slot levels changed.
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
- Parameter meaning or musical interpretation: use CLI block detail first, then load only the relevant manual/wiki page from `references/gt1000-wiki/`.
- Turning decoded blocks on or off: use `patch enable <block>` or `patch disable <block> --live --verify --timeout 20`, which routes through the validated block `sw` parameter. Open `references/midi-reference/cli-usage.md` only if the command surface or persistent-slot guardrails need explanation.
- Changing a decoded effect type: use `patch type <block> <type> --live --verify --timeout 20`, which routes through the validated block `type` parameter. Use `patch block <block>` first if you need the current type or decoded options.
- Moving decoded signal-chain blocks: use `patch move <block> --before <block>` or `patch move <block> --after <block> --live --verify --timeout 20`. Run `patch chain` first if the requested relative order is ambiguous.
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

Ask before persistent operations such as patch write, exchange, initialize, or insert.

## Description Workflow

For a human patch description:

1. Load the user profile memory; if it does not exist, complete onboarding and create it before reading the patch.
2. Read `summary`.
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
4. If output is ambiguous, consult `references/midi-reference/patch-controls.md` and `references/midi-reference/assigns.md`.
5. Report direct switch functions plus active Assign overlays.

## Safety Rules

- The normal endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Ask before changing user patches, global/system settings, patch order, initialize/exchange operations, Assigns, or anything persistent.
- SysEx writes are not gated the same way as Channel Voice messages; verify MIDI RX channel when CCs do not work.
- Use supported, validated intents for every write.

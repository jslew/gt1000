---
name: gt1000
description: GT-1000 v4+ domain knowledge and bundled Python CLI for BOSS/Roland patch inspection, signal-chain explanation, physical switch/control mapping, Assign decoding, MIDI/SysEx reference lookup, and safe validated patch edits. Use when working on GT-1000 or GT-1000CORE behavior, manuals, parameter meanings, live patch descriptions, control assignments, or validated edit planning.
---

# GT-1000 Knowledge And CLI

## Scope

Use the bundled GT-1000 references and CLI to inspect, explain, and safely edit a connected BOSS/Roland GT-1000 or GT-1000CORE.

Do not emit arbitrary SysEx for writes. Use structured CLI commands and typed/validated builders.

The skill scope is the GT-1000 as a whole: current patch buffer, user patches, Assigns, physical controls, MIDI behavior, and global/system settings. A narrow helper command is an implementation limitation, not a conceptual product boundary. When the current CLI cannot perform a requested edit, add or use a typed validator before writing instead of falling back to raw byte arrays.

## Skill Layout

Resolve paths relative to this `SKILL.md` file:

- CLI wrapper: `scripts/gt1000-agent`
- Python CLI implementation: `tools/gt1000/agent_cli.py`
- Manual/wiki references: `references/gt1000-wiki/`
- MIDI/SysEx references: `references/midi-reference/`
- User profile onboarding: `references/user-profile-onboarding.md`
- Manual refresh helper: `scripts/fetch-current-manuals.sh`

## Operational Principles

- Prefer the bundled CLI and markdown references over model memory.
- Use `scripts/gt1000-agent --pretty patch summary --live` as the default live read for patch descriptions.
- Do not inspect `tools/gt1000/*.py` unless the CLI fails, returns ambiguous output, or the user asks to modify the toolchain.
- Run live reads sequentially. Separate processes can interleave GT-1000 replies on the same MIDI source.

## User Profile Memory

At the start of patch description, signal-chain advice, edit planning, or control-mapping work, check for a user-local profile at:

- `$CODEX_HOME/memories/gt1000-profile.md`
- `~/.codex/memories/gt1000-profile.md`

If present, load it before making rig-specific judgments. If absent, proceed with generic guidance unless the missing preference would materially affect the answer. For onboarding or profile updates, use `references/user-profile-onboarding.md`.

Use the profile as preference context, not device truth. Live CLI reads and current patch data remain authoritative.

## Start Here

Load only the reference needed for the task:

- User-facing manual/wiki overview: `references/gt1000-wiki/README.md`
- Owner Manual extraction: `references/gt1000-wiki/owner-manual.md`
- Parameter Guide extraction: `references/gt1000-wiki/parameter-guide.md`
- Sound List extraction: `references/gt1000-wiki/sound-list.md`
- Live agent workflows: `references/gt1000-wiki/agent-workflows.md`
- Low-level MIDI/SysEx index: `references/midi-reference/README.md`
- Patch physical controls: `references/midi-reference/patch-controls.md`
- Assign encoding: `references/midi-reference/assigns.md`
- PatchEfct chain/routing: `references/midi-reference/patch-effect.md`
- CLI usage: `references/midi-reference/cli-usage.md`

## Progressive Disclosure Routing

Keep routine patch work on the compact CLI outputs first. Do not load low-level MIDI tables, long manual extracts, or obscure parameter references unless the user request needs them or the CLI output is ambiguous.

Use this routing:

- Patch description, "what is this sound?", or quick signal-chain review: load the optional user profile, run `patch summary`, and use `descriptionSignalChainSummary`, `descriptionElements`, `controls`, and `activeAssigns`. Do not open MIDI reference pages unless a decoded field is unclear.
- Switch/control questions: run `patch controls` first. Open `references/midi-reference/patch-controls.md` only if a raw/unknown function appears or the user asks how a physical control is encoded.
- Assign behavior, MIDI CC, tuner control, or assigned-off-block reachability: run `patch controls` or `patch summary` first. Open `references/midi-reference/assigns.md` only for source IDs, target min/max encoding, target table caveats, or write planning.
- Sending a MIDI CC for a known Assign source: use `midi cc <controller> <value> --channel N --live` only after confirming the mapped source and RX channel. Do not send raw MIDI bytes.
- Sending a Program Change directly: prefer `patch select <slot>` for user-slot selection; use `midi pc <program> --channel N --live` only when the user explicitly asks for Program Change numbers or after checking `system pcmap`.
- Sending Bank Select: use `midi bank-select <msb> [lsb] --channel N --live` only when the user explicitly needs bank-select/channel-voice behavior; follow it with `midi pc` if selecting via an external-style bank/program sequence.
- Signal-chain routing, divider/mixer behavior, chain element values, or reserved elements: run `patch chain` or `patch summary` first. Open `references/midi-reference/patch-effect.md` only when raw chain/routing details matter.
- System/global MIDI, IN/OUT, or control preference questions: use the relevant `system` CLI view first. Open `references/midi-reference/README.md` or address-map notes only when addresses, sizes, or SysEx behavior need explanation.
- Manual-mode switch questions: use `system manual` first. Open address-map notes only if the user asks how manual-mode NUM functions are encoded.
- Program Change mapping questions: use `system pcmap --bank N` first for a focused bank read, or omit `--bank` only when comparing the full map. Open address-map notes only if the user asks about storage layout or patch-value encoding.
- Input-setting questions: use `system inputs --number N` first for one named input setting, or omit `--number` only when comparing all ten.
- Parameter meaning or musical interpretation: use CLI block detail first, then load only the relevant manual/wiki page from `references/gt1000-wiki/`.
- Writes: build a CLI `patch plan` or typed `patch set` intent first. Open low-level references only to validate address/range/model quirks before changing the validator.

## Live Patch Inspection

These commands read the current/temporary patch buffer (`10 00 00 00`) unless a command explicitly targets a user slot.

```sh
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch summary --live --timeout 8
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
scripts/gt1000-agent --pretty patch controls --live --timeout 8
scripts/gt1000-agent --pretty patch slot U01-1 --live --view summary --timeout 15
scripts/gt1000-agent --pretty patch bank U01 --live --view summary --timeout 15
scripts/gt1000-agent --pretty patch block delay1 --user-slot U01-1
scripts/gt1000-agent --pretty midi cc 80 127 --channel 1 --live
scripts/gt1000-agent --pretty midi bank-select 0 --channel 1 --live
scripts/gt1000-agent --pretty midi pc 1 --channel 1 --live
scripts/gt1000-agent --pretty system midi --live --timeout 8
scripts/gt1000-agent --pretty system pcmap --live --bank 1 --timeout 8
scripts/gt1000-agent --pretty system inputs --live --number 1 --timeout 8
scripts/gt1000-agent --pretty system inout --live --timeout 8
scripts/gt1000-agent --pretty system effects --live --timeout 8
scripts/gt1000-agent --pretty system pitch --live --timeout 8
scripts/gt1000-agent --pretty system controls --live --timeout 8
scripts/gt1000-agent --pretty system manual --live --timeout 8
scripts/gt1000-agent --pretty patch block delay1 --live --timeout 8
```

Use `summary` first for human patch descriptions because it includes metadata, typed signal-chain data, and controls.
Use `slot` or `bank` for persistent user patch inspection; these read user patch memory directly and do not select the patch on the unit.
Use `patch block --user-slot` for targeted persistent-slot block inspection.

## Safe Edit Workflow

Build plans before writing:

```sh
scripts/gt1000-agent --pretty patch plan default
scripts/gt1000-agent --pretty patch plan 4cm-template
```

Temporary patch writes through validated CLI plans should be read-back verified:

```sh
scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20
```

Some currently bundled helper commands only expose a narrow persistent write sandbox. Treat that as a temporary safety guardrail in this implementation, not as a GT-1000 skill rule. For other user patches, global settings, MIDI settings, or Assign edits, use or add a typed command that validates:

- target memory area and patch/global address
- parameter range and encoding
- model-specific quirks
- read-back verification

Examples of currently implemented verified writes:

```sh
scripts/gt1000-agent --pretty patch apply default --live --user-slot U03-1 --verify --timeout 20
scripts/gt1000-agent --pretty patch set delay1 time 380 --live --user-slot U03-2 --verify
```

Ask before persistent operations such as patch write, exchange, initialize, or insert.

## Description Workflow

For a human patch description:

1. Load the optional user profile memory if it exists.
2. Read `summary`.
3. Use `descriptionSignalChainSummary` and `descriptionElements` as the default human-facing chain.
4. Mention only the audible/playable chain first.
5. Mention switched-off blocks if assigned to a physical control, because they are part of the patch's playable potential.
6. Read individual block details only when needed to explain specific settings.
7. If a patch slot reports an unexpected name after selection, trust the live patch name and say so briefly.

For an initialized or sparse patch, keep the answer short and avoid listing dormant off blocks unless asked.

## Controls Workflow

For physical switch mapping:

1. Load the optional user profile memory if it exists.
2. Use `scripts/gt1000-agent --pretty patch controls --live --timeout 8`.
3. If output is ambiguous, consult `references/midi-reference/patch-controls.md` and `references/midi-reference/assigns.md`.
4. Report direct switch functions plus active Assign overlays.

## Wiki Updates

For reference updates:

1. Refresh official manuals into scratch space with `scripts/fetch-current-manuals.sh`.
2. Search extracted text with `rg`.
3. Add concise paraphrased entries to `references/gt1000-wiki` or `references/midi-reference`.
4. Do not commit downloaded PDFs or full extracted manual text.

## Safety Rules

- The normal endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Ask before changing user patches, global/system settings, patch order, initialize/exchange operations, Assigns, or anything persistent.
- SysEx writes are not gated the same way as Channel Voice messages; verify MIDI RX channel when CCs do not work.
- Prefer typed intents and validators over raw byte arrays for every write.
- Preserve tests that assert exact SysEx byte output when changing builders.
- GT-1000/GT-1000CORE SysEx model ID is `00 00 00 4F`.
- Roland/BOSS DT1/RQ1 checksums are calculated over address plus data/size only.
- BPM values are encoded as four 4-bit nibbles of `BPM * 10`.

---
name: gt1000
description: GT-1000 v4+ domain knowledge and bundled Python CLI for BOSS/Roland patch inspection, signal-chain explanation, physical switch/control mapping, Assign decoding, MIDI/SysEx reference lookup, and safe validated patch edits. Use when working on GT-1000 or GT-1000CORE behavior, manuals, parameter meanings, live patch descriptions, control assignments, or validated edit planning.
---

# GT-1000 Knowledge And CLI

## Scope

Use the bundled GT-1000 references and CLI to inspect, explain, and safely edit a connected BOSS/Roland GT-1000 or GT-1000CORE.

Do not emit arbitrary SysEx for writes. Use structured CLI commands and typed/validated builders.

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

## Live Patch Inspection

These commands read the current/temporary patch buffer (`10 00 00 00`) unless a command explicitly targets a user slot.

```sh
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch summary --live --timeout 8
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
scripts/gt1000-agent --pretty patch controls --live --timeout 8
scripts/gt1000-agent --pretty patch block delay1 --live --timeout 8
```

Use `summary` first for human patch descriptions because it includes metadata, typed signal-chain data, and controls.

## Safe Edit Workflow

Build plans before writing:

```sh
scripts/gt1000-agent --pretty patch plan default
scripts/gt1000-agent --pretty patch plan 4cm-template
```

Temporary patch writes are allowed through validated CLI plans and should be read-back verified:

```sh
scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20
```

Persistent writes are restricted to `U03-1` through `U03-5`:

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
- SysEx writes are not gated the same way as Channel Voice messages; verify MIDI RX channel when CCs do not work.
- Preserve tests that assert exact SysEx byte output when changing builders.
- GT-1000/GT-1000CORE SysEx model ID is `00 00 00 4F`.
- Roland/BOSS DT1/RQ1 checksums are calculated over address plus data/size only.
- BPM values are encoded as four 4-bit nibbles of `BPM * 10`.

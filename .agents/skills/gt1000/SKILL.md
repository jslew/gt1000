---
name: gt1000
description: GT-1000 v4+ domain knowledge for BOSS/Roland patch inspection, signal-chain explanation, physical switch/control mapping, Assign decoding, MIDI/SysEx reference lookup, and use of the local agent-facing CLI. Use when working on GT-1000 or GT-1000CORE behavior, manuals, parameter meanings, patch descriptions, control assignments, or safe validated edit planning.
---

# GT-1000 Knowledge

## Scope

Use current GT-1000 v4+ documentation and live CLI inspection to answer questions about patches, signal chains, physical controls, Assigns, MIDI/SysEx details, and safe edit plans.

Prefer current repo references over memory. Do not emit arbitrary SysEx for writes; use structured intents and existing typed builders when implementing edits.

## User Profile Memory

Treat rig setup, musical goals, and editing preferences as optional plugged-in context that can differ by skill user.

At the start of patch description, signal-chain advice, edit planning, or control-mapping work, check for a user-local profile at:

- `$CODEX_HOME/memories/gt1000-profile.md`
- `~/.codex/memories/gt1000-profile.md`

If present, load it before making user-specific judgments such as whether amp/cab emulation should be enabled, where send/return belongs, which outputs matter, or which controls should be prioritized. If absent, proceed with generic GT-1000 guidance and avoid inventing preferences.

If no profile exists and the task depends on user rig/preferences, run the onboarding flow in `references/user-profile-onboarding.md`. Do not block simple factual answers on onboarding; offer or ask only when the missing context would materially affect the answer. If the user asks to create, update, remember, or onboard preferences, use that flow immediately.

Use the profile as preference context, not device truth. Live CLI reads and current patch data still win for factual patch state. If the profile conflicts with the live patch or requested operation, call out the conflict briefly and ask before persistent writes.

## Start Here

Load only the reference needed for the task:

- User-facing manual/wiki overview: `docs/gt1000-wiki/README.md`
- Owner Manual extraction: `docs/gt1000-wiki/owner-manual.md`
- Parameter Guide extraction: `docs/gt1000-wiki/parameter-guide.md`
- Sound List extraction: `docs/gt1000-wiki/sound-list.md`
- Live agent workflows: `docs/gt1000-wiki/agent-workflows.md`
- User profile onboarding: `.agents/skills/gt1000/references/user-profile-onboarding.md`
- Low-level MIDI/SysEx index: `docs/midi-reference/README.md`
- Patch physical controls: `docs/midi-reference/patch-controls.md`
- Assign encoding: `docs/midi-reference/assigns.md`
- PatchEfct chain/routing: `docs/midi-reference/patch-effect.md`
- CLI usage: `docs/midi-reference/cli-usage.md`

## Live Patch Inspection

Use progressive disclosure:

```sh
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
scripts/gt1000-agent --pretty patch block preamp1 --live --timeout 12
```

Use `patch dump` only for diagnostics. Avoid showing users the full JSON unless they ask for raw details.

Run live patch reads sequentially. Do not start multiple `patch block --live` commands in parallel; the current SwiftPM/CoreMIDI path can contend on the build directory and time out. Prefer `overview` plus `chain` first, then read at most one or two specific blocks if the chain view is not enough.

Inspect saved full patch dumps offline with:

```sh
scripts/gt1000-agent --pretty patch overview --file patch.json
scripts/gt1000-agent --pretty patch chain --file patch.json
scripts/gt1000-agent --pretty patch block preamp1 --file patch.json
```

## Common Workflows

For a human patch description:

0. Load the optional user profile memory if it exists.
1. Read `overview`.
2. Read `chain`.
3. Use `descriptionSignalChainSummary` / `descriptionElements` as the default human-facing chain.
4. Mention only the audible/playable chain in the first answer. Do not name switched-off blocks that have no decoded hardware/control assignment unless the user asks for raw chain, hidden blocks, or dormant/off blocks.
5. Do mention switched-off blocks that are assigned to a physical control, because they are part of the patch's playable potential.
6. Read individual block details only when needed to explain an audible/playable block's type or important settings.
7. If a patch slot reports an unexpected name after selection, trust the live patch name and say so briefly. For example, selecting `01-1` may land on user slot `INIT PATCH`, not factory `P01-1 Premium Drive`.
8. Explain musically and structurally, noting split/mixer routing when it remains in the description chain. Apply the user profile only to interpretation and recommendations, for example flagging amp/cab simulation as likely undesirable for a 4-cable-method tube-amp rig.

For an initialized or sparse patch, keep the answer short. Example shape: "`01-1` is `INIT PATCH`. Audibly, it is a mostly blank initialized patch: input compression, send/return, noise suppression, foot volume, looper, reverb, then speaker/output routing to main and sub outs." Do not append a list of dormant off blocks.

For physical switch mapping:

0. Load the optional user profile memory if it exists.
1. Prefer a future `--view controls` CLI when available.
2. Until then, read/decode PatchCommon, SystemControl, and Assign 1-16 using `docs/midi-reference/patch-controls.md` and `docs/midi-reference/assigns.md`.
3. Report direct switch functions plus active Assign overlays.

For wiki updates:

1. Refresh current official manuals into scratch space with `scripts/fetch-current-manuals.sh`.
2. Search extracted text with `rg`.
3. Add concise paraphrased entries to `docs/gt1000-wiki` or `docs/midi-reference`.
4. Do not commit downloaded PDFs or full extracted manual text.

For wiki/documentation search, use `rg` over the local wiki/manual extracts from this skill. Do not route documentation search through the device CLI.

## Safety Rules

- The normal endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL`.
- Channel Voice messages depend on RX channel; SysEx reads/writes do not behave the same way.
- Ask before persistent operations such as patch write, exchange, initialize, or insert.
- Preserve tests that assert exact SysEx byte output.

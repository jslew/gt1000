# GT-1000 Agent Skill

An installable agent skill that lets a coding agent inspect, explain, and safely edit a connected BOSS/Roland GT-1000 or GT-1000CORE.

The goal is not for people to use a MIDI CLI directly. The goal is for an agent to understand your GT-1000 well enough to answer practical questions and make validated edits from natural-language requests.

## What This Enables

After installing the skill, you can ask an agent things like:

- "What patch is currently loaded, and what is the signal chain doing?"
- "Explain what the footswitches and expression pedal do on this patch."
- "Which blocks are actually audible, and which ones are just sitting in the chain turned off?"
- "Make a simple default patch in a safe user slot and verify the write."
- "Create a 4-cable-method template in `U03-2`."
- "Set Delay 1 time to 420 ms in `U03-2` and verify it."
- "Why is this MIDI CC not toggling the tuner?"
- "Decode this patch's Assigns and tell me what is mapped to physical controls."
- "Use my rig preferences when explaining whether amp/cab simulation should be on."

The skill gives the agent:

- GT-1000 v4+ manual-derived reference notes.
- MIDI/SysEx address, checksum, Assign, and control-mapping notes.
- A bundled Python CoreMIDI backend for live device reads and validated writes.
- Safety rules that steer agents away from arbitrary SysEx and unsafe user-slot writes.
- Optional user-profile memory for rig-specific advice.

## Install

Install from this GitHub repo into an agent project:

```sh
npx skills add jslew/gt1000 --skill gt1000 --agent codex
```

Or install from the full URL:

```sh
npx skills add https://github.com/jslew/gt1000 --skill gt1000 --agent codex
```

From a local checkout:

```sh
npx skills add . --skill gt1000 --agent codex --copy -y
```

List available skills in the repo:

```sh
npx skills add . --list
```

Restart or reload your agent environment after installation if it does not pick up new skills automatically.

## Requirements

- macOS, because the bundled live backend uses CoreMIDI through Python `ctypes`.
- Python 3.
- A GT-1000 or GT-1000CORE connected over USB/MIDI.
- The normal MIDI endpoint should appear as `GT-1000`. Avoid `GT-1000 DAW CTRL` unless you deliberately want DAW-control behavior.

## Safety Model

The skill is intentionally conservative.

- Agents are instructed not to emit arbitrary SysEx for writes.
- Writes use typed, validated builders and read-back verification.
- Persistent user-slot writes are restricted to `U03-1` through `U03-5`.
- `U01` and `U02` are intentionally blocked.
- Global settings are not write targets for the packaged edit flows.
- Live reads run sequentially to avoid interleaving GT-1000 replies across concurrent MIDI clients.
- Destructive live tests are gated by explicit environment variables.

If you care about existing patches in `U03`, back them up before asking an agent to write there.

## How To Work With An Agent

Ask naturally. The skill tells the agent which local references to load and which bundled command surface to use.

Examples:

```text
Use the GT-1000 skill. Inspect my current patch and explain it musically.
```

```text
Use the GT-1000 skill. Tell me what CTL 1, CTL 2, CTL 3, and EXP 1 do on the current patch.
```

```text
Use the GT-1000 skill. Create a verified 4CM template in U03-2. Do not touch any other bank.
```

```text
Use the GT-1000 skill. Set Delay 1 time to 420 ms in U03-2 and verify the readback.
```

```text
Use the GT-1000 skill. Help me understand why CC#80 is not toggling the tuner.
```

## Optional Rig Profile

The skill can use a local profile so advice is grounded in your setup rather than generic GT-1000 assumptions.

Agents look for:

```text
$CODEX_HOME/memories/gt1000-profile.md
~/.codex/memories/gt1000-profile.md
```

You can ask:

```text
Use the GT-1000 skill. Create a profile for my normal rig: 4-cable method into a tube amp, main outs matter, speaker simulation usually off.
```

The profile is user-specific memory. It is not stored in this repo or inside the reusable skill package.

## What Is In This Repo

The installable skill lives at:

```text
skills/gt1000/
```

That directory is self-contained:

- `SKILL.md` describes how agents should use the skill.
- `references/` contains GT-1000 manual/wiki and MIDI reference notes.
- `scripts/` contains thin helpers the agent can call.
- `tools/gt1000/` contains the bundled Python implementation for live reads, validated plans, and read-back verification.

The top-level `tools/`, `docs/`, and `tests/` directories are for maintaining and validating the skill package.

## Maintainer Checks

Default tests are non-destructive. Live tests are skipped unless explicitly enabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
```

Run the comprehensive live skill suite against a connected GT-1000. This destructively writes and verifies only `U03-1` and `U03-2`:

```sh
GT1000_LIVE=1 GT1000_ALLOW_U03_DESTRUCTIVE=1 python3 -m unittest tests.test_live_skill -q
```

Validate skill discovery:

```sh
npx skills add . --list
```

Validate the packaged skill's offline read path:

```sh
skills/gt1000/scripts/gt1000-agent --pretty patch inspect tests/fixtures/full_patch.json --view chain
```

## Current Limits

- The packaged live backend targets macOS/CoreMIDI.
- The safe edit surface is intentionally small: default patch plan, 4CM template plan, and selected validated parameter edits.
- Persistent writes are limited to `U03-*` by design.
- Broader patch editing should be added as typed intents and validators, not as raw SysEx snippets.

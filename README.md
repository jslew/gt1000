# GT-1000 Agent Skill

An installable agent skill for musicians who use a BOSS/Roland GT-1000 or GT-1000CORE for live performance, recording, practice, MIDI control, direct rigs, amp rigs, and hybrid setups.

NOTE: This version has only been tested on MacOS, using Antigravity/Gemini and Codex CLI AI harnesses.  It may not work on Windows/Linux.

This is not meant to be a tool you operate by memorizing MIDI commands. It gives an agent enough GT-1000 knowledge and safe device access to work with you conversationally:

```text
Use the GT-1000 skill. Look at the current patch and explain how I would use it on stage.
```

```text
Use the GT-1000 skill. I am recording direct tonight. Check whether this patch is set up like an amp/cab direct tone or like a 4CM amp-rig patch.
```

```text
Use the GT-1000 skill. My external MIDI controller is supposed to toggle the tuner. Figure out why it is not working.
```

## Why This Exists

GT-1000 patches are deep. A patch can include multiple parallel paths, speaker simulation, send/return loops, direct and assign-based footswitch behavior, MIDI CC mappings, global MIDI settings, and hidden blocks that may or may not affect the sound.

That complexity is useful, but it is hard to inspect quickly when you are:

- building a live set
- adapting patches between FRFR/direct and real amps
- checking a 4-cable-method rig before a show
- preparing direct recording tones
- mapping CTL switches and expression pedals
- debugging MIDI controllers
- making sure a patch does not accidentally depend on global settings you forgot about

This skill is designed to let an agent act like a GT-1000-aware tech: read the device, explain the patch in plain musical terms, identify risks, and make validated edits when you ask.

## What You Can Ask

Patch and tone understanding:

- "What patch is loaded right now?"
- "Explain the signal chain like I am about to play it live."
- "Which blocks are actually audible?"
- "Is this patch intended for direct/FRFR, headphones, 4CM, or the front of an amp?"
- "Are amp and speaker simulation active?"
- "What is the wet/dry or parallel routing doing?"

Live-performance prep:

- "Tell me what every footswitch and expression pedal does."
- "Which controls are direct patch controls, and which are Assign overlays?"
- "Find anything that could surprise me on stage."
- "Make CTL 3 a tuner switch if that is safe for this patch."
- "Set this patch up so Delay 1 can be toggled from a footswitch."

Recording workflow:

- "Check whether this patch is safe to record direct."
- "Make a version of this patch with cab simulation enabled for interface recording."
- "Compare this patch against my live amp-rig preferences."
- "Help me build a clean direct patch with delay and reverb."

Amp and hybrid rigs:

- "I am using 4CM with a tube amp. Does this patch route send/return correctly?"
- "Make a 4CM template in the user patch slot I choose."
- "Explain whether the GT-1000 preamps should be on or off for this rig."
- "Check whether the main/sub outputs make sense for my stage setup."

MIDI and system behavior:

- "What MIDI channel is the GT-1000 listening on?"
- "Why does this CC work over SysEx but not as a normal controller message?"
- "Decode the active Assigns."
- "Show me a validated plan before changing a global MIDI setting."

## Install

To install this skill, you can use the `skills` package manager. You can target all installed agents or specify a particular environment like Antigravity, Gemini, Claude, Codex, or ChatGPT.

### Install for all agents on your system
The easiest way is to install the skill for all detected agent environments at once:
```sh
npx skills add jslew/gt1000 --all
```

### Install for specific agents
You can also target specific agent platforms using the `--agent` (or `-a`) flag:

* **Antigravity**:
  ```sh
  npx skills add jslew/gt1000 --agent antigravity
  ```
* **Gemini**:
  ```sh
  npx skills add jslew/gt1000 --agent gemini
  ```
* **Claude / Claude Code**:
  ```sh
  npx skills add jslew/gt1000 --agent claude-code
  ```
* **Codex**:
  ```sh
  npx skills add jslew/gt1000 --agent codex
  ```
* **ChatGPT**:
  ```sh
  npx skills add jslew/gt1000 --agent chatgpt
  ```
* **Cursor**:
  ```sh
  npx skills add jslew/gt1000 --agent cursor
  ```

### Install from a local checkout
If you have cloned the repository locally and want to install/link it:
```sh
npx skills add . --skill gt1000 --agent * --copy -y
```

List the available skills in a directory or repository without installing:
```sh
npx skills add jslew/gt1000 --list
```

Restart or reload your agent environment after installation if it does not pick up new skills automatically.

### Alternative Installer Options

#### GitHub CLI (`gh skill`)
If you use the GitHub CLI, you can use the native `gh skill` extension to install the skill for your agents:
```sh
gh skill install jslew/gt1000 --agent antigravity
```

#### Manual / Direct Installation
If you prefer not to use a CLI tool, you can copy the `skills/gt1000` directory directly into your project's local `.agents/skills/` directory. Most IDE-based agents (like Cursor, Cline, or Antigravity) will automatically discover and load the skill from there.



## Requirements

- macOS for the bundled live backend, which uses CoreMIDI through Python `ctypes`.
- Python 3.
- A GT-1000 or GT-1000CORE connected over USB/MIDI.
- The normal MIDI endpoint should appear as `GT-1000`. Avoid `GT-1000 DAW CTRL` unless you deliberately want DAW-control behavior.

## Working With Your Rig

The same patch can be good or wrong depending on how you connect the GT-1000.

For direct/FRFR, headphones, or interface recording, an agent may care about:

- GT-1000 preamp and speaker/cab simulation
- main and sub output routing
- stereo effects and wet/dry paths
- output levels and patch level

For 4-cable method or real-amp rigs, an agent may care about:

- send/return placement
- whether GT-1000 preamps are bypassed or intentionally used
- whether speaker simulation should be off for amp outputs
- whether time effects are before or after the amp loop

For live performance, an agent may care about:

- what CTL switches do
- whether the current number switch has a special function
- tap tempo, tuner, solo boosts, and expression pedal behavior
- whether Assign ranges match the physical MIDI/control source

For recording, an agent may care about:

- whether the patch produces a complete direct tone
- whether global output settings could change the recorded result
- whether the sound depends on an external amp or send/return loop

## Optional Rig Profile

The skill can use a local profile so advice is grounded in your setup instead of generic GT-1000 assumptions.

Agents look for a local profile using a harness-neutral path order:

```text
GT1000_PROFILE_PATH
GT1000_PROFILE_DIR/gt1000-profile.md
$XDG_CONFIG_HOME/gt1000/gt1000-profile.md
~/.config/gt1000/gt1000-profile.md
```

Harness-specific memory directories may also be used when the active agent environment exposes one. Older Codex-local profile paths are treated as legacy fallback locations and should be migrated to one of the neutral paths.

You can ask:

```text
Use the GT-1000 skill. Remember that I usually run 4CM into a tube amp live, but record direct through an interface at home.
```

Or:

```text
Use the GT-1000 skill. My main live output is to a real amp, but the sub outs go direct to front of house with cab simulation.
```

The profile is user-specific memory. It is not stored in this repo or inside the reusable skill package.

## Safety Model

This skill should help an agent make better decisions, not bypass judgment.

- The agent should ask before changing user patches, patch order, global/system settings, MIDI settings, Assigns, or anything persistent.
- The agent should show the intended target and edit plan before destructive writes.
- Writes should use typed, validated builders and read-back verification.
- The agent should not emit arbitrary SysEx blobs as the answer.
- If the current bundled command surface cannot safely perform a requested edit, the right next step is to add or use a typed validator, not guess bytes.
- Live reads should run sequentially to avoid interleaving GT-1000 replies across concurrent MIDI clients.

## What Is In This Repo

The installable skill lives at:

```text
skills/gt1000/
```

That directory is self-contained:

- `SKILL.md` describes how agents should use the skill.
- `references/` contains GT-1000 manual/wiki and MIDI reference notes.
- `scripts/` contains helpers the agent can call.
- `tools/gt1000/` contains the bundled Python implementation for live reads, validated plans, and read-back verification.

The top-level `tools/`, `docs/`, and `tests/` directories are for maintaining and validating the skill package.

## Maintainer Checks

Default tests are non-destructive. Live tests are skipped unless explicitly enabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
```

Run the comprehensive live skill suite against a connected GT-1000. The current maintainer suite uses `U03-1` and `U03-2` as disposable sandbox slots:

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

## Current Implementation State

The skill is meant to support the whole GT-1000: current patch buffer, user patches, global settings, MIDI behavior, Assigns, physical controls, and validated edits through natural language.

The bundled live backend currently targets macOS/CoreMIDI, and the current write helpers are intentionally narrow. Broader patch and global-setting edits should be added as typed intents and validators so an agent can keep working conversationally without falling back to raw SysEx.

## License and Disclaimer

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

**Disclaimer:** This software is an independent open-source project and is **not** affiliated with, authorized, maintained, sponsored, or endorsed by Roland Corporation, BOSS, or any of their affiliates or subsidiaries. Using this software to read/write to your device via MIDI SysEx is done at your own risk. See the [DISCLAIMER.md](DISCLAIMER.md) file for more details.


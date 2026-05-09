# GT-1000 Python Agent Tools

Python tooling for inspecting and safely editing a connected BOSS/Roland GT-1000.

## Install As An Agent Skill

This repo exposes a self-contained skill at `skills/gt1000`. The installed skill includes the Python CLI, GT-1000 references, and helper scripts, so it does not require this source checkout after installation.

Install from GitHub into the current agent project:

```sh
npx skills add <owner>/<repo> --skill gt1000 --agent codex
```

You can also install from a full GitHub URL:

```sh
npx skills add https://github.com/<owner>/<repo> --skill gt1000 --agent codex
```

For Codex from a local checkout:

```sh
npx skills add . --skill gt1000 --agent codex --copy -y
```

List the skill without installing:

```sh
npx skills add . --list
```

The packaged skill entrypoint is relative to the installed skill directory:

```sh
scripts/gt1000-agent
```

The main entrypoint is:

```sh
scripts/gt1000-agent
```

## Project Shape

```text
.
├── tools/gt1000/              # Python CoreMIDI backend, CLI, patch plans, and validators
├── scripts/                   # Thin command wrappers and live patch helper scripts
├── skills/gt1000/             # Self-contained installable agent skill package
├── tests/                     # Python unit tests
├── docs/midi-reference/       # Local GT-1000 SysEx/control/address notes
└── docs/gt1000-wiki/          # Manual-derived working notes for agents
```

## Common Commands

Inspect the connected device:

```sh
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch summary --live --timeout 8
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
scripts/gt1000-agent --pretty patch controls --live --timeout 8
scripts/gt1000-agent --pretty patch block delay1 --live --timeout 8
```

Build validated write plans without sending MIDI:

```sh
scripts/gt1000-agent --pretty patch plan default
scripts/gt1000-agent --pretty patch plan 4cm-template
```

Apply and verify temporary-patch writes:

```sh
scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20
```

Persistent writes are intentionally restricted to U03 user slots:

```sh
scripts/gt1000-agent --pretty patch apply default --live --user-slot U03-1 --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --user-slot U03-2 --verify --timeout 20
```

Set a validated parameter:

```sh
scripts/gt1000-agent --pretty patch set delay1 time 380 --live --user-slot U03-2 --verify
```

Run tests:

```sh
python3 -m unittest discover -s tests -q
```

Run live smoke checks against a connected GT-1000:

```sh
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch summary --live --timeout 8
scripts/gt1000-agent --pretty patch plan default
scripts/gt1000-agent --pretty patch plan 4cm-template
```

Run the comprehensive live skill suite. This destructively writes and verifies only `U03-1` and `U03-2`:

```sh
GT1000_LIVE=1 GT1000_ALLOW_U03_DESTRUCTIVE=1 python3 -m unittest tests.test_live_skill -q
```

Validate the packaged skill:

```sh
npx skills add . --list
skills/gt1000/scripts/gt1000-agent --pretty patch inspect tests/fixtures/full_patch.json --view chain
```

## Safety Notes

- U01 and U02 are not write targets for the Python CLI.
- The normal MIDI endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Writes use typed/validated builders and read-back verification instead of arbitrary SysEx blobs.
- Persistent writes are intentionally restricted to `U03-1` through `U03-5`.
- See `docs/midi-reference/README.md` before changing SysEx, Assign, or chain behavior.

# GT-1000 Python Agent Tools

Python tooling for inspecting and safely editing a connected BOSS/Roland GT-1000.

The main entrypoint is:

```sh
scripts/gt1000-agent
```

## Project Shape

```text
.
├── tools/gt1000/              # Python CoreMIDI backend, CLI, patch plans, and validators
├── scripts/                   # Thin command wrappers and live patch helper scripts
├── tests/                     # Python unit tests
├── docs/midi-reference/       # Local GT-1000 SysEx/control/address notes
└── docs/gt1000-wiki/          # Manual-derived working notes for agents
```

## Common Commands

Inspect the connected device:

```sh
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
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

## Safety Notes

- U01 and U02 are not write targets for the Python CLI.
- The normal MIDI endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Writes use typed/validated builders and read-back verification instead of arbitrary SysEx blobs.
- See `docs/midi-reference/README.md` before changing SysEx, Assign, or chain behavior.

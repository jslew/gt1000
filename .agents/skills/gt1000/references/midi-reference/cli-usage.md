# CLI Usage

The agent-facing CLI is wrapped by:

```sh
scripts/gt1000-agent
```

This is a Python command surface for agents and skills. Live MIDI reads use the Python CoreMIDI backend in `tools/gt1000/live.py`, and saved full patch JSON dumps can be inspected offline.

## Core Commands

### `ports`
List available MIDI ports.
```sh
scripts/gt1000-agent --pretty ports --live
```
- `--live`: Required for MIDI port discovery.

## Patch Inspection Commands

All patch commands support `--live` for the connected device or `--file <path>` for a saved JSON dump.

### `patch summary`
The most efficient command for a complete overview. Aggregates metadata, signal chain, and foot-switch assignments in a single bulk read.
```sh
scripts/gt1000-agent --pretty patch summary --live --timeout 15
```

### `patch overview`
Show compact patch metadata (name, BPM, level, key).
```sh
scripts/gt1000-agent --pretty patch overview --live
```

### `patch chain`
Show the signal chain with block types (e.g., `T-SCREAM`) but without detailed parameters.
```sh
scripts/gt1000-agent --pretty patch chain --live
```

### `patch controls`
Show physical foot-switch mappings (NUM 1-5, CTL 1-3, etc.) and active Assign overlays.
```sh
scripts/gt1000-agent --pretty patch controls --live --timeout 15
```

### `patch block`
Show detailed parameters for a single block.
```sh
scripts/gt1000-agent --pretty patch block preamp1 --live
scripts/gt1000-agent --pretty patch block ds1 --live
scripts/gt1000-agent --pretty patch block --position 8 --live
```
- Supports normalized IDs (`preamp1`) and aliases (`ds1`, `sr1`).
- Use `--position <n>` to target a block by its 1-indexed position in the raw chain.

### `patch dump`
Read the entire current patch state into a JSON object.
```sh
scripts/gt1000-agent --pretty patch dump --live --timeout 10
scripts/gt1000-agent --pretty patch dump --live --output my_patch.json
```

### `patch inspect`
Analyze a saved JSON dump file.
```sh
scripts/gt1000-agent --pretty patch inspect my_patch.json --view chain
```
- `--view`: `overview` (default), `chain`, or `full`.

## Patch Modification Commands

### `patch set`
Change a single parameter on the connected device.
```sh
scripts/gt1000-agent --pretty patch set delay1 time 380 --live --verify
```
- `--verify`: Re-reads the parameter to confirm the write succeeded.
- `--user-slot U03-1`: Persist the change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.

### `patch plan`
Build a validated write plan (multiple parameters) without sending MIDI.
```sh
scripts/gt1000-agent --pretty patch plan 4cm-template --name "My 4CM Patch"
```

### `patch apply`
Apply a validated write plan to the device.
```sh
scripts/gt1000-agent --pretty patch apply default --live --verify
```
- `--user-slot U03-1`: Persist the plan to a specific user slot.

## Timeout and Port Selection

- `--timeout <seconds>`: Adjust the timeout for live reads (default is 8.0s).
- The CLI automatically targets the `GT-1000` port. It avoids `GT-1000 DAW CTRL`.

## Wiki Search Boundary

Search the local documentation wiki from the skill or shell with `rg`; do not add wiki search commands to the live-device CLI. The CLI should expose product state and validated device operations, while the skill owns documentation retrieval and interpretation.

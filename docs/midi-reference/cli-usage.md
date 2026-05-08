# CLI Usage

The agent-facing CLI is wrapped by:

```sh
scripts/gt1000-agent
```

This is a Python command surface for agents and skills. Live MIDI reads use the Python CoreMIDI backend in `tools/gt1000/live.py`, and saved full patch JSON dumps can be inspected offline.

## Progressive Patch Views

Overview, compact patch-level metadata:

```sh
scripts/gt1000-agent --pretty patch overview --live --timeout 8
```

Chain, no parameters:

```sh
scripts/gt1000-agent --pretty patch chain --live --timeout 8
```

The chain view includes both the raw chain order in `elements` and the human-description projection in `descriptionElements` / `descriptionSignalChainSummary`. The description projection omits reserved entries and switched-off blocks unless a decoded hardware/control assignment marks them as playable from a physical control.

Use `descriptionSignalChainSummary` for normal human answers. Use `elements` only for raw inspection or when the user asks about hidden/dormant/off blocks.

One block detail by block id:

```sh
scripts/gt1000-agent --pretty patch block preamp1 --live --timeout 8
```

Run live block-detail reads sequentially. The Python live backend transacts one request at a time to avoid stale GT-1000 reply backlog, but parallel CLI processes can still interleave reads on the same MIDI source.

One block detail by chain position:

```sh
scripts/gt1000-agent --pretty patch block --position 8 --live --timeout 8
```

Full diagnostic dump:

```sh
scripts/gt1000-agent --pretty patch dump --live --timeout 8
```

Full diagnostic dumps read every summary block and may need a longer timeout than overview, chain, or single-block reads.

Saved dump inspection:

```sh
scripts/gt1000-agent --pretty patch overview --file patch.json
scripts/gt1000-agent --pretty patch chain --file patch.json
scripts/gt1000-agent --pretty patch block preamp1 --file patch.json
```

## Validated Patch Writes

Build a write plan without sending MIDI:

```sh
scripts/gt1000-agent --pretty patch plan default
scripts/gt1000-agent --pretty patch plan 4cm-template
```

Apply and verify a temporary patch plan:

```sh
scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20
```

Persistent user-slot writes are restricted to U03:

```sh
scripts/gt1000-agent --pretty patch apply default --live --user-slot U03-1 --verify --timeout 20
scripts/gt1000-agent --pretty patch apply 4cm-template --live --user-slot U03-2 --verify --timeout 20
```

Set a single validated parameter and verify the exact bytes:

```sh
scripts/gt1000-agent --pretty patch set delay1 time 380 --live --user-slot U03-2 --verify --timeout 12
```

Do not write U01 or U02. The CLI rejects persistent slots outside `U03-1` through `U03-5`.

## MIDI Ports

```sh
scripts/gt1000-agent --pretty ports --live
```

Use the default endpoint named `GT-1000`. Avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.

## Wiki Search Boundary

Search the local documentation wiki from the skill or shell with `rg`; do not add wiki search commands to the live-device CLI. The CLI should expose product state and validated device operations, while the skill owns documentation retrieval and interpretation.

## Current Gap

The CLI does not yet expose a first-class `controls` view. For now, physical control mapping requires direct reads of:

- `PatchCommon` at `10 00 00 00`, size `00 00 00 7E`.
- `SystemControl` at `00 00 10 00`, size `00 00 00 36`.
- Assign 1-16 at `10 00 03 00` through `10 00 0A 40`, size `00 00 00 2C`.

The next useful CLI addition is:

```sh
scripts/gt1000-agent --pretty patch controls --live
```

That view should report effective physical switch mappings and active Assign overlays.

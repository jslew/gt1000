# CLI Usage

The agent-facing CLI is wrapped by:

```sh
scripts/gt1000-cli.sh
```

## Progressive Patch Views

Overview, compact patch-level metadata:

```sh
scripts/gt1000-cli.sh read current-patch --view overview --format json --pretty --timeout 8
```

Chain, no parameters:

```sh
scripts/gt1000-cli.sh read current-patch --view chain --format json --pretty --timeout 8
```

One block detail by block id:

```sh
scripts/gt1000-cli.sh read current-patch --view block --block preamp1 --format json --pretty --timeout 8
```

One block detail by chain position:

```sh
scripts/gt1000-cli.sh read current-patch --view block --position 8 --format json --pretty --timeout 8
```

Full diagnostic dump:

```sh
scripts/gt1000-cli.sh read current-patch --view full --format json --pretty --timeout 8
```

## MIDI Ports

```sh
scripts/gt1000-cli.sh list-ports --format json --pretty
```

Use the default endpoint named `GT-1000`. Avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.

## Current Gap

The CLI does not yet expose a first-class `controls` view. For now, physical control mapping requires direct reads of:

- `PatchCommon` at `10 00 00 00`, size `00 00 00 7E`.
- `SystemControl` at `00 00 10 00`, size `00 00 00 36`.
- Assign 1-16 at `10 00 03 00` through `10 00 0A 40`, size `00 00 00 2C`.

The next useful CLI addition is:

```sh
scripts/gt1000-cli.sh read current-patch --view controls --format json
```

That view should report effective physical switch mappings and active Assign overlays.

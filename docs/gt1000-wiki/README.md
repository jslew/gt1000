# GT-1000 v4+ Knowledge Wiki

This wiki is a local, agent-oriented extraction from current official BOSS/Roland GT-1000 v4+ documentation. It complements the lower-level [MIDI reference wiki](../midi-reference/README.md).

Do not treat this as a complete copy of the manuals. It is a navigable working index for agents that need to inspect a connected GT-1000, explain patch behavior, and map user-facing concepts to CLI/MIDI data.

## Scope

- Focus on GT-1000 version 4+ era documentation.
- Prefer current official BOSS/Roland PDFs listed in [Sources](sources.md).
- Distinguish user-facing concepts from low-level MIDI implementation details.
- Use the CLI for live patch truth when hardware is connected.

## Pages

- [Sources](sources.md): official PDFs and local refresh process.
- [Owner Manual Extraction](owner-manual.md): hardware, play modes, editing workflow, external control, USB/MIDI, looper.
- [Parameter Guide Extraction](parameter-guide.md): effect blocks, menu sections, control/assign, in/out, MIDI, hardware settings.
- [Sound List Extraction](sound-list.md): preset patch list shape and physical control columns.
- [Agent Workflows](agent-workflows.md): how to combine wiki knowledge with CLI reads.

## Relationship To The CLI

For live patch inspection, start with:

```sh
scripts/gt1000-cli.sh read current-patch --view overview --format json --pretty --timeout 8
scripts/gt1000-cli.sh read current-patch --view chain --format json --pretty --timeout 8
scripts/gt1000-cli.sh read current-patch --view block --block preamp1 --format json --pretty --timeout 8
```

The next planned CLI view is `--view controls`, which should expose PatchCommon/SystemControl/Assign-derived switch mappings.


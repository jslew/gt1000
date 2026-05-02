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
scripts/gt1000-agent --pretty patch overview --live --timeout 8
scripts/gt1000-agent --pretty patch chain --live --timeout 8
scripts/gt1000-agent --pretty patch block preamp1 --live --timeout 8
```

The Python agent CLI delegates live MIDI work to the Swift backend and can inspect saved full patch JSON dumps offline. Search this wiki directly with `rg`; wiki search belongs to the skill/docs layer, not to the device CLI.

The next planned CLI view is `patch controls`, which should expose PatchCommon/SystemControl/Assign-derived switch mappings.

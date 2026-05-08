# GT-1000 Knowledge Repo Map

Use these project references with the `gt1000` skill.

## User-Facing v4+ Manual Wiki

- `docs/gt1000-wiki/README.md`
- `docs/gt1000-wiki/sources.md`
- `docs/gt1000-wiki/owner-manual.md`
- `docs/gt1000-wiki/parameter-guide.md`
- `docs/gt1000-wiki/sound-list.md`
- `docs/gt1000-wiki/agent-workflows.md`

## Low-Level MIDI Wiki

- `docs/midi-reference/README.md`
- `docs/midi-reference/address-map.md`
- `docs/midi-reference/patch-controls.md`
- `docs/midi-reference/assigns.md`
- `docs/midi-reference/patch-effect.md`
- `docs/midi-reference/cli-usage.md`

## Source Code Entry Points

- Agent CLI wrapper: `scripts/gt1000-agent`
- Agent CLI implementation: `tools/gt1000/agent_cli.py`
- Swift live CLI backend: `GT1000AppPackage/Sources/GT1000PatchDump/main.swift`
- SysEx helpers: `GT1000AppPackage/Sources/GT1000AppFeature/GT1000SysEx.swift`
- Snapshot decoder/reports: `GT1000AppPackage/Sources/GT1000AppFeature/GT1000PatchSnapshot.swift`
- MIDI manager: `GT1000AppPackage/Sources/GT1000AppFeature/MIDIManager.swift`

## Verification

```sh
xcodebuildmcp swift-package test --package-path GT1000AppPackage
python3 -m unittest discover -s tests
scripts/gt1000-agent --pretty ports --live
scripts/gt1000-agent --pretty patch overview --live --timeout 8
```

# GT1000App Agent Notes

## Project Shape
- This is a macOS SwiftUI app with most code in the local Swift package at `GT1000AppPackage/Sources/GT1000AppFeature`.
- Build the app through `GT1000App.xcworkspace`, not `GT1000App.xcodeproj`; the local package product is resolved by the workspace.
- Useful checks:
  - `xcodebuildmcp swift-package test --package-path GT1000AppPackage`
  - `xcodebuild -workspace GT1000App.xcworkspace -scheme GT1000App -configuration Debug -destination 'platform=macOS,arch=arm64' build`
  - `xcodebuildmcp macos build-and-run --workspace-path GT1000App.xcworkspace --scheme GT1000App --arch arm64`

## GT-1000 MIDI Details
- Local MIDI reference wiki: start at `docs/midi-reference/README.md` before changing SysEx, control/assign decoding, or CLI patch inspection behavior.
- Local GT-1000 v4+ knowledge skill: `.agents/skills/gt1000-knowledge/SKILL.md`; use it for manual/parameter-guide lookups, patch explanations, controls, and wiki updates.
- The GT-1000/GT-1000CORE SysEx model ID is `00 00 00 4F`.
- Roland/BOSS DT1/RQ1 checksums are calculated over address plus data/size only.
- GT-1000 BPM values are encoded as four 4-bit nibbles of `BPM * 10`; for example 120.0 BPM is `00 04 0B 00`.
- Temporary patch MASTER:BPM address currently used by the app is `10 00 10 61`.
- System metronome BPM address currently used by the app is `00 00 00 09`.
- Do not write random "tuner" SysEx addresses. `00 00 00 06` is not tuner on/off in the GT-1000 MIDI implementation. The app maps temporary Assign 16 to target `987` (TUNER ON/OFF on tested GT-1000 firmware with Bass Mode off), source CC#80, then sends CC#80 values.
- The official GT-1000 v4.01 MIDI implementation PDF contains two Assign target tables and can be misleading: one table lists `991 | TUNER | ON OFF`, but the tested GT-1000 v4 unit with Bass Mode off responds to `987 | TUNER | ON OFF`.
- Assign target min/max values are 4-nibble values offset by `32768`. For an on/off target, encode OFF/ON as `32768` and `32769`, not raw `0` and `1`.
- Assign active range for a MIDI CC source should match the incoming CC value range. For CC#80, use ACT RANGE LO/HI `0...127`; using `0...16383` makes CC value `127` map near the bottom and can leave the target effectively off.
- CC source IDs are not the same as MIDI CC numbers. CC#80 is source byte `0x45` in the Assign SOURCE field, while the outbound MIDI control change still sends controller byte `0x50`.
- GT-1000 Channel Voice messages are gated by `MENU:MIDI:MIDI SETTING:RX CHANNEL`, while SysEx writes are not. If a CC does not appear to work but SysEx does, verify channel handling before assuming the Assign write failed.
- The normal endpoint is named `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Prefer typed enums/builders for SysEx payloads instead of naked byte arrays with comments. Preserve tests that assert exact byte output for any builder.

## CoreMIDI And Swift Concurrency
- `MIDIManager` is `@MainActor` because it is observed by SwiftUI, but CoreMIDI callbacks run on CoreMIDI-owned threads.
- Do not let CoreMIDI callback closures be inferred as main-actor isolated. Parse/copy packet data in a nonisolated closure, then hop to `MainActor`.
- A bad callback isolation setup crashes on incoming GT-1000 replies with a libdispatch assertion similar to "Block was expected to execute on queue com.apple.main-thread".
- Identity request is a good live crash test: launch the app with the GT-1000 connected and click `Identify`; the app should stay alive when the unit replies.

## Local Verification Notes
- A quick endpoint inventory can be done with Python `ctypes` against CoreMIDI if needed. Expected connected endpoints are usually:
  - Destination: `GT-1000`
  - Destination: `GT-1000 DAW CTRL`
  - Source: `GT-1000`
  - Source: `GT-1000 DAW CTRL`
- UI automation via `osascript` may need accessibility permissions. In the current SwiftUI hierarchy, Identify has been reachable as `button 3 of group 1 of window 1`.

## Agent-Control Direction
- The long-term goal is to let an agent inspect and edit the GT-1000 safely from natural-language requests.
- Build toward this in layers: typed SysEx protocol definitions, decoded patch snapshots, human-readable signal-chain summaries, validated edit commands, then agent planning.
- The agent should not emit arbitrary SysEx directly. It should produce structured intents such as "set delay 1 time" or "enable tuner assign"; the app should validate ranges, addresses, and model-specific quirks before sending MIDI.
- The next useful milestone is read-only patch inspection: request the temporary patch, decode chain elements/effect blocks/assigns, and render a signal-chain summary before adding broader write operations.

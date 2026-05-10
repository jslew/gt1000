# GT-1000 Agent Notes

## Project Shape

- This is a Python-based GT-1000 inspection/editing repo.
- Main code lives in `skills/gt1000/tools/gt1000`.
- Top-level `tools/gt1000` files are compatibility wrappers only.
- Main command surface is `scripts/gt1000-agent`.
- Useful checks:
  - `python3 -m unittest discover -s tests -q`
  - `scripts/gt1000-agent --pretty ports --live`
  - `scripts/gt1000-agent --pretty patch overview --live --timeout 8`
  - `scripts/gt1000-agent --pretty patch chain --live --timeout 8`
  - `scripts/gt1000-agent --pretty patch plan default`
  - `scripts/gt1000-agent --pretty patch plan 4cm-template`

## GT-1000 MIDI Details

- Local MIDI reference wiki: start at `skills/gt1000/references/midi-reference/README.md` before changing SysEx, control/assign decoding, CLI patch inspection, or write behavior.
- Local GT-1000 v4+ knowledge skill: `skills/gt1000/SKILL.md`; use it for manual/parameter-guide lookups, patch explanations, controls, and wiki updates.
- The GT-1000/GT-1000CORE SysEx model ID is `00 00 00 4F`.
- Roland/BOSS DT1/RQ1 checksums are calculated over address plus data/size only.
- GT-1000 BPM values are encoded as four 4-bit nibbles of `BPM * 10`; for example 120.0 BPM is `00 04 0B 00`.
- Temporary patch MASTER:BPM address is `10 00 10 61`.
- Temporary patch PatchEfct address is `10 00 10 00`.
- System metronome BPM address is `00 00 00 09`.
- Do not write random "tuner" SysEx addresses. `00 00 00 06` is not tuner on/off in the GT-1000 MIDI implementation.
- The tested tuner path maps an Assign target `987` (TUNER ON/OFF on tested GT-1000 firmware with Bass Mode off), source CC#80, then sends CC#80 values.
- The official GT-1000 v4.01 MIDI implementation PDF contains two Assign target tables and can be misleading: one table lists `991 | TUNER | ON OFF`, but the tested GT-1000 v4 unit with Bass Mode off responds to `987 | TUNER | ON OFF`.
- Assign target min/max values are 4-nibble values offset by `32768`. For an on/off target, encode OFF/ON as `32768` and `32769`, not raw `0` and `1`.
- Assign active range for a MIDI CC source should match the incoming CC value range. For CC#80, use ACT RANGE LO/HI `0...127`; using `0...16383` makes CC value `127` map near the bottom and can leave the target effectively off.
- CC source IDs are not the same as MIDI CC numbers. CC#80 is source byte `0x45` in the Assign SOURCE field, while the outbound MIDI control change still sends controller byte `0x50`.
- GT-1000 Channel Voice messages are gated by `MENU:MIDI:MIDI SETTING:RX CHANNEL`, while SysEx writes are not. If a CC does not appear to work but SysEx does, verify channel handling before assuming the Assign write failed.
- The normal endpoint is named `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Prefer typed enums/builders for SysEx payloads instead of naked byte arrays with comments. Preserve tests that assert exact byte output for any builder.

## Python Live MIDI Notes

- `skills/gt1000/tools/gt1000/live.py` uses Python `ctypes` against CoreMIDI.
- CoreMIDI callbacks run on CoreMIDI-owned threads. Copy packet bytes in the callback, then update guarded Python state.
- Run live patch reads sequentially. Separate CLI processes can interleave GT-1000 replies on the same MIDI source.
- A quick endpoint inventory should usually show:
  - Destination: `GT-1000`
  - Destination: `GT-1000 DAW CTRL`
  - Source: `GT-1000`
  - Source: `GT-1000 DAW CTRL`

## Write Safety

- Temporary patch writes are allowed through validated CLI plans and should be read-back verified.
- Persistent user-slot writes are restricted to `U03-1` through `U03-5`; do not touch U01 or U02.
- Use `--verify` for live write commands so every written range is re-read and compared.
- Current proven commands:
  - `scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch apply default --live --user-slot U03-1 --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch apply 4cm-template --live --user-slot U03-2 --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch set delay1 time 380 --live --user-slot U03-2 --verify`

## Agent-Control Direction

- The long-term goal is to let an agent inspect and edit the GT-1000 safely from natural-language requests.
- Build toward this in layers: typed SysEx protocol definitions, decoded patch snapshots, human-readable signal-chain summaries, validated edit commands, then agent planning.
- The agent should not emit arbitrary SysEx directly. It should produce structured intents such as "set delay 1 time" or "enable tuner assign"; the Python CLI should validate ranges, addresses, and model-specific quirks before sending MIDI.

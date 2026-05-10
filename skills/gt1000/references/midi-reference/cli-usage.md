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

## MIDI Send Commands

Typed channel-voice send commands are intentionally narrow. Use them for validated workflows such as exercising a known Assign source; do not emit raw arbitrary MIDI bytes.

### `midi cc`
Send a MIDI Control Change message.
```sh
scripts/gt1000-agent --pretty midi cc 80 127 --channel 1 --live
scripts/gt1000-agent --pretty midi cc 80 0 --channel 1 --live
```
- `controller`: CC number `0`...`127`.
- `value`: CC value `0`...`127`.
- `--channel`: 1-based MIDI channel. Channel Voice messages are gated by the GT-1000 RX channel.

### `midi pc`
Send a MIDI Program Change message by 1-based program number.
```sh
scripts/gt1000-agent --pretty midi pc 1 --channel 1 --live
scripts/gt1000-agent --pretty midi pc 128 --channel 1 --live
```
- `program`: Program Change number `1`...`128`; the MIDI payload is zero-based `0`...`127`.
- Program Change messages are gated by the GT-1000 RX channel and resolved through the active Program Map.

### `midi bank-select`
Send MIDI Bank Select MSB/LSB messages.
```sh
scripts/gt1000-agent --pretty midi bank-select 0 --channel 1 --live
scripts/gt1000-agent --pretty midi bank-select 2 0 --channel 1 --live
```
- `msb`: Bank Select MSB `0`...`127`.
- `lsb`: optional Bank Select LSB `0`...`127`, default `0`.
- Bank Select is normally followed by Program Change.
- For GT-1000 patch selection specifically, the MIDI implementation documents received Bank Select MSB `0`...`2` and LSB `0`; broader values are allowed here because Assign/Patch MIDI transmit settings can target external devices.

## System Inspection Commands

System commands are read-only SysEx views of global settings.

### `system common`
Read common global settings with the known metronome BPM field decoded.
```sh
scripts/gt1000-agent --pretty system common --live --timeout 8
```

### `system midi`
Read global MIDI settings as raw bytes with light decoding for common channel fields.
```sh
scripts/gt1000-agent --pretty system midi --live --timeout 8
```

### `system pcmap`
Read MIDI Program Change map banks.
```sh
scripts/gt1000-agent --pretty system pcmap --live --bank 1 --timeout 8
scripts/gt1000-agent --pretty system pcmap --live --timeout 8
```
- `--bank`: optional bank `1`...`4`; omit to read all four banks sequentially.
- Each entry decodes a Program Change number to its configured user or preset patch target.

### `system inputs`
Read named system input-level settings.
```sh
scripts/gt1000-agent --pretty system inputs --live --number 1 --timeout 8
scripts/gt1000-agent --pretty system inputs --live --timeout 8
```
- `--number`: optional input setting `1`...`10`; omit to read all ten sequentially.

### `system inout`
Read global input/output settings as raw bytes with light decoding for common level/output-select fields.
```sh
scripts/gt1000-agent --pretty system inout --live --timeout 8
```

### `system effects`
Read global effects settings such as phrase-loop mode, metronome level, and metronome output routing.
```sh
scripts/gt1000-agent --pretty system effects --live --timeout 8
```

### `system pitch`
Read global pitch/tuner settings such as reference pitch, poly-tuner type/offset, and tuner output mode.
```sh
scripts/gt1000-agent --pretty system pitch --live --timeout 8
```

### `system controls`
Read global control functions, modes, and patch/system preference settings.
```sh
scripts/gt1000-agent --pretty system controls --live --timeout 8
```

### `system manual`
Read global manual-mode NUM switch functions, modes, and patch/system preferences.
```sh
scripts/gt1000-agent --pretty system manual --live --timeout 8
```

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
- Reads Assign blocks and direct physical-control mappings so switched-off blocks can still be marked as description candidates when a decoded control can enable them.
- Chain elements include `activeAssigns` and `directControls` when those mappings target the element's block.

### `patch controls`
Show physical foot-switch mappings (NUM 1-5, CTL 1-3, etc.) and active Assign overlays.
```sh
scripts/gt1000-agent --pretty patch controls --live --timeout 15
```
- Direct switch functions expose raw function bytes plus decoded target metadata: `functionTargetBlockId`, `functionTargetParameterId`, and `functionCanEnableBlock`.
- Active Assigns expose decoded target metadata: `targetCategory`, `targetBlockId`, `targetParameterId`, and `targetIsOnOff`.

### `patch slot`
Read a persistent user patch slot directly by SysEx without selecting it on the unit.
```sh
scripts/gt1000-agent --pretty patch slot U01-1 --live --view summary --timeout 15
```
- `slot`: User slot `U01-1` through `U50-5`.
- `--view`: `overview`, `chain`, `controls`, `summary`, or `full`.

### `patch bank`
Read all five persistent user patch slots in a bank sequentially.
```sh
scripts/gt1000-agent --pretty patch bank U01 --live --view summary --timeout 15
```
- `bank`: User bank `U01` through `U50`.
- Reads are sequential to avoid interleaving GT-1000 MIDI replies.
- Use this for comparing patch names, master patch levels, chains, controls, and switchable-path level parameters across a bank.

### `patch select`
Select a user slot using typed MIDI Bank Select and Program Change messages.
```sh
scripts/gt1000-agent --pretty patch select U01-1 --live --channel 1
scripts/gt1000-agent --pretty patch select U50-5 --live --channel 1
```
- Uses documented GT-1000 received Bank Select MSB `0`...`2`, LSB `0`, followed by Program Change.
- Bank Select and Program Change are subject to the GT-1000 MIDI RX channel and program-map settings.
- Direct `patch slot` / `patch bank` reads are safer for inspection because they do not change the selected patch.

### `patch block`
Show detailed parameters for a single block.
```sh
scripts/gt1000-agent --pretty patch block preamp1 --live
scripts/gt1000-agent --pretty patch block ds1 --live
scripts/gt1000-agent --pretty patch block --position 8 --live
scripts/gt1000-agent --pretty patch block delay1 --user-slot U01-2
```
- Supports normalized IDs (`preamp1`) and aliases (`ds1`, `sr1`).
- Use `--position <n>` to target a block by its 1-indexed position in the raw chain.
- Use `--user-slot Uxx-y` to inspect a block from persistent user patch memory without selecting the patch.

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

### `patch enable` / `patch disable`
Turn a switchable block on or off through the validated block `sw` parameter.
```sh
scripts/gt1000-agent --pretty patch enable delay1 --live --verify
scripts/gt1000-agent --pretty patch disable dist1 --live --verify
```
- Supports normalized IDs (`delay1`, `dist1`) and aliases (`ds1`, `sr1`).
- `--verify`: Re-reads the block switch address to confirm the write succeeded.
- `--user-slot U03-1`: Persist the switch change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.
- If a block has no decoded `sw` parameter, use `patch block` to inspect it and add a typed validator before writing.

### `patch type`
Change a decoded block's effect type through the validated `type` parameter.
```sh
scripts/gt1000-agent --pretty patch type dist1 T-SCREAM --live --verify
scripts/gt1000-agent --pretty patch type preamp1 "TWIN COMBO" --live --verify
```
- Supports exact decoded type names where available; raw 0...127 type numbers are accepted for decoded byte-type blocks.
- Supports normalized IDs (`preamp1`) and aliases (`ds1`, `sr1`).
- `--verify`: Re-reads the type address to confirm the write succeeded.
- `--user-slot U03-1`: Persist the type change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.

### `patch move`
Move a decoded block in the current signal chain by reading the existing chain, reordering one element, and writing the validated full 49-element chain back.
```sh
scripts/gt1000-agent --pretty patch move delay1 --before chorus --live --verify
scripts/gt1000-agent --pretty patch move dist1 --after preamp1 --live --verify
```
- Exactly one of `--before <block>` or `--after <block>` is required.
- Supports decoded block IDs and aliases (`ds1`, `sr1`).
- `--verify`: Re-reads the full chain and compares the exact 49 bytes.
- `--user-slot U03-1`: Move within a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.
- This command preserves all other current chain elements and refuses malformed or unknown chain data.

### `patch assign-cc`
Map one Assign block to a decoded target from a MIDI CC source.
```sh
scripts/gt1000-agent --pretty patch assign-cc 3 delay1 sw --cc 80 --mode moment --live --verify
scripts/gt1000-agent --pretty patch assign-cc 4 delay1 effectLevel --cc 81 --mode moment --min 20 --max 70 --live --verify
```
- Assign number must be `1`...`16`.
- `--cc` supports GT-1000 Assign MIDI CC sources `1`...`31` and `64`...`95`.
- `--mode` is required and must be `toggle` or `moment`.
- On/off targets default to logical min/max `0` and `1`; other targets require explicit `--min` and `--max`.
- Target min/max are encoded with the GT-1000 Assign `+32768` offset rule.
- `--active-min` / `--active-max` default to the full CC value range `0`...`127`.
- `--user-slot U03-1`: Persist the Assign change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.

### `patch set-bpm`
Change the patch master BPM using the validated four-nibble `BPM * 10` encoding.
```sh
scripts/gt1000-agent --pretty patch set-bpm 120.0 --live --verify
```
- `bpm`: `40.0`...`250.0`, with at most one decimal place.
- `--verify`: Re-reads the BPM address to confirm the write succeeded.
- `--user-slot U03-1`: Persist the BPM change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.

### `patch tuner-assign`
Install the tested Assign 16 mapping that toggles TUNER ON/OFF from MIDI CC#80.
```sh
scripts/gt1000-agent --pretty patch tuner-assign --live --verify
```
- Writes Assign 16 to target `987` (`TUNER ON/OFF` on the tested GT-1000 v4 unit with Bass Mode off), source CC#80, active range `0`...`127`.
- After installing, send values with `midi cc 80 127 --channel N --live` and `midi cc 80 0 --channel N --live`.
- `--user-slot U03-1`: Persist the Assign change to a specific user slot instead of the temporary patch. Valid slots: `U03-1` through `U03-5`.

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

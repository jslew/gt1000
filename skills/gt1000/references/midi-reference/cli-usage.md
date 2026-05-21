# CLI Usage

The agent-facing CLI is wrapped by:

```sh
scripts/gt1000-agent
```

This is a Python command surface for agents and skills. Live MIDI reads use the Python CoreMIDI backend in `tools/gt1000/live.py`, and saved full patch JSON dumps can be inspected offline.

## Verification

Routine unit and read-only live checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill.LiveSkillReadTests tests.test_live_skill.LiveSkillSystemReadTests -q
```

The destructive live write suite requires `GT1000_LIVE_BACKUP_DIR`, performs persistent writes, backs up `U10-1` through `U11-2` plus the System Control section, and restores them after the run. It also exercises MIDI CC, Bank Select, Program Change, and `patch select`; that command group ends by selecting `U10-1`. Keep the persistent backup directory so the slot liveset backup and System Control JSON backup remain available if the run is interrupted:

```sh
GT1000_LIVE=1 GT1000_ALLOW_DESTRUCTIVE=1 GT1000_LIVE_BACKUP_DIR=/tmp/gt1000-live-backups PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill -q
```

If `ports --live` itself hangs or times out, stop live testing and recover CoreMIDI/the USB connection before continuing. Quit BOSS Tone Studio if it is open, then power-cycle or reconnect the GT-1000.

If macOS USB inventory still shows `GT-1000` from `BOSS` but `ports --live` times out, the hang can be inside CoreMIDI endpoint enumeration before the CLI reaches any GT-1000-specific code. Restarting `coreaudiod`, `com.apple.midiserver`, or the user `MIDIServer` process may help, but if `MIDIGetNumberOfDestinations()` still hangs, do a full Mac restart before any more live GT-1000 verification.

If `ports --live` still lists the normal `GT-1000` endpoints but known-good SysEx reads such as `system controls --live` time out, stop live write testing and power-cycle or reconnect the GT-1000 before continuing. The tested unit can remain visible to CoreMIDI while no longer replying to SysEx after repeated large reads.

If small live reads pass but full persistent-slot operations such as `patch export U10-1 --live` fail with `No GT-1000 MIDI destination found` or a `timed out after ...s` SysEx-read error, do not start destructive write tests. First get a fresh backup export to complete, or use known-good `GT1000_LIVE_BACKUP_FILE` and `GT1000_LIVE_SYSTEM_CONTROL_BACKUP_FILE` values from a prior verified backup. Persistent-slot clone/export/exchange/insert reads are wrapped in process-level timeouts so this failure should return cleanly rather than leaving a stuck CLI process.

If a fresh backup export succeeds but verified write commands fail with endpoint or read-timeout errors, stop the destructive suite and exact-verify the protected slots against the backup before trying more writes. Endpoint lookup and write/read verification include retries, so repeated failures usually indicate a live CoreMIDI/device stability issue rather than a parser or schema problem. If the cleanup import runs but a post-cleanup exact export cannot complete, leave live write testing stopped until a reconnect or power-cycle restores known-good `patch summary --live` and protected-slot export behavior.

Large read commands are paced between RQ1 messages to avoid overrunning the tested unit. Set `GT1000_REQUEST_DELAY` to tune the inter-request delay if a device needs more spacing than the default. Multi-slot librarian reads also pause between slots; set `GT1000_SLOT_READ_DELAY` to tune that delay.

After recovering a wedged CoreMIDI/USB connection, resume live verification in this order:

```sh
PYTHONDONTWRITEBYTECODE=1 scripts/gt1000-agent --pretty ports --live --timeout 8
GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 caffeinate -dimsu scripts/gt1000-agent --pretty patch summary --live --timeout 20
GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 caffeinate -dimsu scripts/gt1000-agent --pretty patch chain --live --timeout 20
GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 caffeinate -dimsu python3 -m unittest tests.test_live_skill.LiveSkillReadTests tests.test_live_skill.LiveSkillSystemReadTests -q
```

If the tested unit cannot complete a fresh full backup export but a verified backup already exists, the destructive suite can restore from that existing backup by setting `GT1000_LIVE_BACKUP_FILE` and `GT1000_LIVE_SYSTEM_CONTROL_BACKUP_FILE`:

```sh
GT1000_LIVE=1 GT1000_ALLOW_DESTRUCTIVE=1 GT1000_LIVE_BACKUP_DIR=/tmp/gt1000-live-backups GT1000_LIVE_BACKUP_FILE=/tmp/gt1000-live-backups/live-write-slot-backup-<timestamp>.json GT1000_LIVE_SYSTEM_CONTROL_BACKUP_FILE=/tmp/gt1000-live-backups/live-write-system-control-backup-<timestamp>.json PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill -q
```

If a destructive run is interrupted, restore the slot backup with the normal verified liveset importer:

```sh
scripts/gt1000-agent --pretty patch import /tmp/gt1000-live-backups/live-write-slot-backup-<timestamp>.json --destination-start U10-1 --live --verify --timeout 20
```

The System Control backup is written as JSON with a `dataHex` field. Until a first-class system restore CLI exists, restore it with the live helper:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import json
from pathlib import Path
from tools.gt1000 import live

backup = json.loads(Path("/tmp/gt1000-live-backups/live-write-system-control-backup-<timestamp>.json").read_text())
data = [int(byte, 16) for byte in backup["dataHex"].split()]
live.write_data_sets([live.PatchWrite("Restore System Control", live.SYSTEM_CONTROL, data)])
PY
```

## Core Commands

### `ports`
List available MIDI ports.
```sh
scripts/gt1000-agent --pretty ports --live --timeout 8
```
- `--live`: Required for MIDI port discovery.
- `--timeout`: CoreMIDI port inventory timeout in seconds. If this times out, quit other MIDI clients such as BOSS Tone Studio, then power-cycle or reconnect the GT-1000.

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

### `patch performance`
Show the current patch as a stage-performance control layout.
```sh
scripts/gt1000-agent --pretty patch performance --live --timeout 15
```
- Includes each NUM/CTL/EXP control, whether it uses PATCH or SYSTEM preference, its direct function, and any active Assign overlays sourced by that control.
- Reports tuner availability from decoded direct controls and active Assign targets.
- Adds practical notes for SYSTEM-preference controls, active Assign overlays, and controls with no patch-specific action.

### `patch musician-summary`
Describe the current patch in concise musician-facing language.
```sh
scripts/gt1000-agent --pretty patch musician-summary --live --timeout 15
```
- Focuses on the main sound path, live-use basics such as patch level/BPM/tuner access, and playable NUM/CTL/EXP actions.
- Uses the same resilient live reader as `patch performance`, with core patch data required and Assign overlays read leniently.
- Avoids raw bytes and low-level record data.

### `patch slot`
Read a persistent user patch slot directly by SysEx without selecting it on the unit.
```sh
scripts/gt1000-agent --pretty patch slot U01-1 --live --view summary --timeout 15
```
- `slot`: User slot `U01-1` through `U50-5`.
- `--view`: `overview`, `chain`, `controls`, `performance`, `musician-summary`, `summary`, or `full`.

### `patch preset`
Read a preset patch's documented primary records directly by SysEx without selecting it on the unit.
```sh
scripts/gt1000-agent --pretty patch preset P01-1 --live --view summary --timeout 15
```
- `slot`: Preset slot `P01-1` through `P50-5`.
- `--view`: `overview`, `chain`, `controls`, `performance`, `musician-summary`, `summary`, or `full`.
- Preset extra STOMPBOX records are not read because their preset address bases are not documented in the local MIDI reference.
- During destructive live validation on the tested GT-1000, direct preset-memory reads at `30 00 00 00` did not reply. Treat this command as requiring renewed live validation before relying on it for factory-preset recovery.

### `patch bank`
Read all five persistent user patch slots in a bank sequentially.
```sh
scripts/gt1000-agent --pretty patch bank U01 --live --view summary --timeout 15
```
- `bank`: User bank `U01` through `U50`.
- `--view`: `overview`, `chain`, `controls`, `performance`, `musician-summary`, `summary`, or `full`.
- Reads are sequential to avoid interleaving GT-1000 MIDI replies.
- Use this for comparing patch names, master patch levels, chains, controls, and switchable-path level parameters across a bank.

### `patch diff`
Compare two patches in musician-facing terms.
```sh
scripts/gt1000-agent --pretty patch diff U10-1 U10-2 --live --timeout 15
scripts/gt1000-agent --pretty patch diff before.json after.json
```
- With `--live`, `source` and `target` are user patch slots read directly without selecting them.
- Without `--live`, `source` and `target` are full patch JSON dump files.
- Reports overview changes, signal-chain changes, block on/off/type changes, control changes, and active Assign changes.

### `patch setlist-audit`
Audit live-use risks across a bank or explicit slot list.
```sh
scripts/gt1000-agent --pretty patch setlist-audit U10 --live --timeout 15
scripts/gt1000-agent --pretty patch setlist-audit U10-1 U10-2 U10-3 --live --timeout 15
```
- Flags patch-level jumps, missing tuner access, mixed BPM values, expression-pedal behavior changes, and SYSTEM-preference controls.
- A single bank argument such as `U10` expands to all five slots in that bank.

### `patch level-audit`
Compare patch master levels and loudness-related performance controls across a bank or slot list.
```sh
scripts/gt1000-agent --pretty patch level-audit U10-1 U10-2 --target 90 --live --timeout 15
scripts/gt1000-agent --pretty patch level-audit U10 --live --timeout 15
```
- Reports each slot's decoded master patch level, delta from the explicit target, or delta from the median decoded level when `--target` is omitted.
- Flags large level offsets and playable controls or Assigns that mention level, volume, gain, or boost.

### `patch normalize-levels`
Set several user-slot patch master levels while preserving the rest of each Patch Effect record.
```sh
scripts/gt1000-agent --pretty patch normalize-levels U10-1 U10-2 --target 90 --live --verify --timeout 20
scripts/gt1000-agent --pretty patch normalize-levels U10 --target 90 --dry-run --live --timeout 20
```
- `--target`: patch master level `0`...`200`.
- `--dry-run`: read and report intended changes without writing.
- `--verify`: re-read each written Patch Effect record and compare exact bytes.
- This is a persistent write to the selected user slots; inspect and back up slots first when their contents matter.

### `patch undo-last`
Restore the latest automatic restore point created before a CLI write.
```sh
scripts/gt1000-agent --pretty patch undo-last --live --verify --timeout 20
```
- Restore points are written before `apply_plan_cli` sends any write data.
- The default restore directory is `~/.gt1000-agent/restore-points`; set `GT1000_RESTORE_DIR` to override it.
- `undo-last` writes the captured previous bytes back to their original addresses and can read-back verify them.

### `patch schema`
Show the editable parameter schema for decoded blocks.
```sh
scripts/gt1000-agent --pretty patch schema
scripts/gt1000-agent --pretty patch schema fx1
scripts/gt1000-agent --pretty patch schema fx1Chorus
scripts/gt1000-agent --pretty patch schema fx2PitchShift
scripts/gt1000-agent --pretty patch schema fx4Chorus
scripts/gt1000-agent --pretty patch schema eq1
scripts/gt1000-agent --pretty patch schema sendReturn1
scripts/gt1000-agent --pretty patch schema master
scripts/gt1000-agent --pretty patch schema controls
scripts/gt1000-agent --pretty patch schema assign
scripts/gt1000-agent --pretty patch schema led
scripts/gt1000-agent --pretty patch schema delay1 --raw
```
- Lists named parameters that can be edited with `patch set`, including documented PEQ/GEQ fields for EQ blocks and FX1-FX4 algorithm-specific records such as `fx1Chorus`, `fx2PitchShift`, or `fx4Chorus`.
- `patch schema master` lists patch-level fields editable with `patch master-set`.
- `patch schema controls`, `patch schema assign`, and `patch schema led` list supported editor ids, value ranges, and command templates for CTL/EXP, Assign/Patch MIDI, and PatchLed editing.
- Shows the bounded raw-editable allocation for `patch raw-set`; FX1-FX4 algorithm records are also exposed as named schema blocks.
- `--raw` enumerates every bounded raw-editable offset for a selected block and marks offsets already covered by a named parameter.

### `patch select`
Select a user slot using typed MIDI Bank Select and Program Change messages.
```sh
scripts/gt1000-agent --pretty patch select U01-1 --live --channel 1
scripts/gt1000-agent --pretty patch select U50-5 --live --channel 1
```
- Uses documented GT-1000 received Bank Select MSB `0`...`2`, LSB `0`, followed by Program Change.
- Bank Select and Program Change are subject to the GT-1000 MIDI RX channel and program-map settings.
- Direct `patch slot` / `patch bank` reads are safer for inspection because they do not change the selected patch.

### `patch clone`
Clone one persistent user patch slot to another by reading the source records and writing them to the destination slot.
```sh
scripts/gt1000-agent --pretty patch clone U10-1 U10-2 --live --verify --timeout 20
scripts/gt1000-agent --pretty patch copy U10-1 U10-2 --live --verify --timeout 20
```
- `source_slot` / `destination_slot`: User slots `U01-1` through `U50-5`; they must be different.
- `--verify`: Re-reads every written clone record and compares exact bytes.
- Copies the compact current-state record set used by the CLI: PatchCommon, PatchStompBox, PatchLed, Assign 1...16, PatchEfct, decoded effect selector records, PatchStompBox2, PatchStompBox3, and only the FX1-FX4 algorithm records selected by the patch's current FX type bytes. Non-responding optional records are skipped instead of retried indefinitely.
- This is a persistent write to the destination user slot; inspect the source and destination first when slot contents matter.

### `patch exchange`
Exchange two persistent user patch slots by reading both slots and writing each slot's known records to the other.
```sh
scripts/gt1000-agent --pretty patch exchange U10-1 U10-2 --live --verify --timeout 20
```
- Uses the same known patch record set as `patch clone` / `patch copy`.
- This overwrites both slots; inspect both slots first when slot contents matter.

### `patch insert`
Insert one patch into a bounded destination range, shifting the existing destination range down by one slot.
```sh
scripts/gt1000-agent --pretty patch insert U10-1 U11-1 --range-end U11-3 --live --verify --timeout 20
```
- Reads the source slot and every destination slot from `destination_slot` through `--range-end`.
- Writes the source into `destination_slot` and shifts the previous destination contents down one slot.
- The last slot in the range is overwritten.

### `patch batch-copy`
Copy multiple user patch slots to a consecutive destination range.
```sh
scripts/gt1000-agent --pretty patch batch-copy U10-1 U10-2 --destination-start U11-1 --live --verify --timeout 20
```
- Sources are copied in the order provided.
- The destination range is computed from `--destination-start`.
- This is a persistent write to every destination slot.

### `patch export` / `patch import`
Export user patch slots to a CLI JSON liveset file and import that file into consecutive user slots.
```sh
scripts/gt1000-agent --pretty patch export U10-1 U10-2 --output my-liveset.json --live --timeout 20
scripts/gt1000-agent --pretty patch import my-liveset.json --destination-start U11-1 --live --verify --timeout 20
```
- The file format is `gt1000-agent-liveset-v1`, a repo-native JSON format for the same compact current-state record set used by `patch clone`.
- Import validates record labels, sizes, 7-bit data bytes, and the destination range before building the write plan.
- This is intended as a safe backup/restore and CLI librarian interchange format. Use `patch tsl-export` when a JSON `.tsl` envelope is needed.
- `patch import` is a persistent write to every destination slot; use `--verify` for read-back comparison.

### `patch tsl-export` / `patch tsl-list` / `patch tsl-import`
Wrap CLI JSON livesets in a JSON `.tsl` envelope, inspect JSON `.tsl` patch metadata, and import supported GT-1000 `.tsl` records.
```sh
scripts/gt1000-agent --pretty patch tsl-export my-liveset.json --output my-liveset.tsl --name "MY LIVESET"
scripts/gt1000-agent --pretty patch tsl-list my-liveset.tsl
scripts/gt1000-agent --pretty patch tsl-import my-liveset.tsl --destination-start U11-1 --live --verify --timeout 20
```
- `patch tsl-export` validates a `gt1000-agent-liveset-v1` file and writes a `gt1000-agent-tsl-json-v1` JSON `.tsl` envelope with the same known patch records embedded under each patch.
- `patch tsl-list` accepts JSON files with `liveSetData.patchList`, top-level `patchList`, or Tone Studio-style nested `data` patch entries. For `data` entries, it can extract names from `paramSet.UserPatch%PatchName` or the first 16 bytes of `paramSet.User_patch%common`.
- `patch tsl-import` imports `.tsl` envelopes that contain embedded `gt1000-agent-liveset-v1` records produced by `patch tsl-export`, and GT-1000 Tone Studio `data` / `paramSet` records whose keys map to known user-patch records.
- For GT-1000 `paramSet` files, unsupported keys are reported by `patch tsl-list` as `unsupportedParamSetKeys`; `patch tsl-import` refuses the file until those keys are mapped to verified user-memory addresses.
- Unsupported or non-GT-1000 proprietary Tone Studio `.tsl` payloads may be listable when they are JSON and expose patch metadata, but they are not imported unless their patch entries contain supported GT-1000 records.
- `patch tsl-import` is a persistent write to every destination slot; use `--verify` for read-back comparison.

### `patch liveset-list` / `patch liveset-move` / `patch liveset-copy` / `patch liveset-rename` / `patch liveset-remove`
Inspect and reorder CLI JSON liveset files without touching the connected GT-1000.
```sh
scripts/gt1000-agent --pretty patch liveset-list my-liveset.json
scripts/gt1000-agent --pretty patch liveset-move my-liveset.json 2 1 --output reordered.json
scripts/gt1000-agent --pretty patch liveset-copy my-liveset.json 1 2 --output duplicated.json
scripts/gt1000-agent --pretty patch liveset-rename my-liveset.json 1 "NEW NAME" --output renamed.json
scripts/gt1000-agent --pretty patch liveset-remove my-liveset.json 3 --output trimmed.json
```
- Indexes are 1-based and match the order shown by `patch liveset-list`.
- Mutating operations validate the liveset format and require `--output`; they do not silently overwrite the source file.
- These commands operate on the repo-native `gt1000-agent-liveset-v1` format. Use the `patch tsl-*` commands for JSON `.tsl` envelopes.

### `patch restore-preset`
Restore a preset patch's documented primary records into a user patch slot.
```sh
scripts/gt1000-agent --pretty patch restore-preset P01-1 U10-1 --live --verify --timeout 20
```
- Reads from the documented preset patch base (`P01-1` starts at `30 00 00 00`) and writes to the destination user slot.
- Copies PatchCommon, PatchStompBox, PatchLed, Assign 1...16, PatchEfct, and decoded effect block records.
- Does not copy preset extra STOMPBOX records because their preset address bases are not documented in the local MIDI reference. On the tested GT-1000, preset memory does not consistently answer FX4 algorithm-record addresses with the same sizes as user-patch memory, so FX4 algorithm records are skipped for preset restore.
- During destructive live validation on the tested GT-1000, direct preset-memory reads at `30 00 00 00` did not reply. Treat this command as implemented but not yet proven live until preset-memory reads are validated after the unit resumes SysEx replies.
- This is a persistent write to the destination user slot; use `--verify` for read-back comparison.

### `patch rename`
Rename the current temporary patch or a persistent user patch slot.
```sh
scripts/gt1000-agent --pretty patch rename "MY PATCH" --live --verify
scripts/gt1000-agent --pretty patch rename "MY PATCH" --live --user-slot U10-1 --verify
```
- Names are encoded into the GT-1000 16-byte ASCII patch-name field and truncated/padded as needed.

### `patch initialize`
Initialize the current temporary patch or a persistent user patch slot using the validated default plan.
```sh
scripts/gt1000-agent --pretty patch initialize --name "INIT PATCH" --live --verify
scripts/gt1000-agent --pretty patch initialize --name "INIT PATCH" --live --user-slot U10-1 --verify
```
- This uses the same safe default plan as `patch apply default`.

### `patch clear`
Alias for the validated default initializer, intended for Tone Studio-style clear workflows.
```sh
scripts/gt1000-agent --pretty patch clear --name "EMPTY" --live --user-slot U10-1 --verify
```

### `patch batch-initialize`
Initialize multiple user patch slots using the validated default plan.
```sh
scripts/gt1000-agent --pretty patch batch-initialize U10-1 U10-2 --name-prefix "INIT" --live --verify --timeout 20
```
- Slot-specific suffixes are appended to the name prefix when more than one slot is initialized.
- This is a persistent write to every listed slot.

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

### `patch stompbox`
Read and decode the known PatchStompBox selection records.
```sh
scripts/gt1000-agent --pretty patch stompbox --live --timeout 8
scripts/gt1000-agent --pretty patch stompbox --live --user-slot U03-2 --timeout 8
```
- Addresses: temporary `10 00 01 00`, `10 01 00 00`, and `10 02 00 00`; user-slot reads remap these into the selected user patch records.
- Sizes: `00 00 00 68`, `00 00 00 11`, and `00 00 00 25`.
- Each byte decodes one documented STOMPBOX selection. Raw `0` means no shared STOMPBOX; raw `1`...`10` selects that block category's STOMPBOX slot.

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
scripts/gt1000-agent --pretty patch set sendReturn1 sendLevel 100 --live --verify
```
- `--verify`: Re-reads the parameter to confirm the write succeeded.
- `--user-slot Uxx-y`: Persist the change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.

### `patch raw-set`
Change one validated raw byte or nibble field within a decoded block record.
```sh
scripts/gt1000-agent --pretty patch raw-set fx1 12 64 --live --verify
scripts/gt1000-agent --pretty patch raw-set sendReturn1 2 100 --width nibbles2 --live --verify
```
- `block_id`: any decoded main or resident block.
- `offset`: zero-based byte offset within that block's record.
- `--width`: `byte`, `nibbles2`, or `nibbles4`.
- Use this only when the exact parameter name has not yet been promoted into the typed schema. The command still validates official block allocation bounds, value range, memory target, and read-back verification.

### `patch enable` / `patch disable`
Turn a switchable block on or off through the validated block `sw` parameter.
```sh
scripts/gt1000-agent --pretty patch enable delay1 --live --verify
scripts/gt1000-agent --pretty patch disable dist1 --live --verify
```
- Supports normalized IDs (`delay1`, `dist1`) and aliases (`ds1`, `sr1`).
- `--verify`: Re-reads the block switch address to confirm the write succeeded.
- `--user-slot Uxx-y`: Persist the switch change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.
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
- `--user-slot Uxx-y`: Persist the type change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.

### `patch move`
Move a decoded block in the current signal chain by reading the existing chain, reordering one element, and writing the validated full 49-element chain back.
```sh
scripts/gt1000-agent --pretty patch move delay1 --before chorus --live --verify
scripts/gt1000-agent --pretty patch move dist1 --after preamp1 --live --verify
```
- Exactly one of `--before <block>` or `--after <block>` is required.
- Supports decoded block IDs and aliases (`ds1`, `sr1`).
- `--verify`: Re-reads the full chain and compares the exact 49 bytes.
- `--user-slot Uxx-y`: Move within any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.
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
- `--user-slot Uxx-y`: Persist the Assign change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.

### `patch control-set`
Set one patch-local NUM/BANK/CTL/EXP control function.
```sh
scripts/gt1000-agent --pretty patch control-set ctl1 dist1 --mode toggle --live --verify
scripts/gt1000-agent --pretty patch control-set exp1 foot-volume-pedal-fx --live --verify
```
- Supports direct controls from PatchCommon: `num1`...`num5`, `bank-down`, `bank-up`, `ctl1`...`ctl7`, `cur-num`, `exp1-sw`, `exp1`, `exp2`, and `exp3`.
- Function names are normalized command ids such as `off`, `tuner`, `dist1`, `delay1-tap`, `divider1-channel-select`, `foot-volume`, and `foot-volume-pedal-fx`.
- Writes patch-local functions only. Use `patch controls` afterward to see whether the effective preference is PATCH or SYSTEM.

### `patch system-control-set`
Set one global/system NUM/BANK/CTL/EXP control function.
```sh
scripts/gt1000-agent --pretty patch system-control-set ctl1 dist1 --mode toggle --live --verify
scripts/gt1000-agent --pretty patch system-control-set exp1 foot-volume-pedal-fx --live --verify
```
- Uses the same control ids and function ids as `patch control-set`.
- This writes the SystemControl function/mode field. It is a global/system write; inspect `system controls` first.

### `patch control-preference-set`
Set whether one control uses its patch-local mapping or the global/system mapping.
```sh
scripts/gt1000-agent --pretty patch control-preference-set ctl1 patch --live --verify
scripts/gt1000-agent --pretty patch control-preference-set ctl1 system --live --verify
```
- This writes the SystemControl preference byte for the selected control.
- It is a global/system write; inspect `system controls` and `patch controls` before changing preferences.

### `patch led-set`
Set one patch-local control LED color.
```sh
scripts/gt1000-agent --pretty patch led-set ctl1 on auto-cyan --live --verify
scripts/gt1000-agent --pretty patch led-set ctl1 off blue --live --verify
```
- Supports `num1`...`num5`, `bank-down`, `bank-up`, `ctl1`...`ctl3`, and `exp1-sw`.
- Off-state colors support `off`, `red`, `blue`, `light-blue`, `orange`, `green`, `yellow`, `white`, `purple`, `pink`, and `cyan`.
- On-state colors additionally support `auto` and `auto-<color>`.

### `patch assign-set`
Set one Assign block from raw validated fields, including Patch MIDI fields.
```sh
scripts/gt1000-agent --pretty patch assign-set 2 --target 987 --min 0 --max 1 --source 19 --mode toggle --live --verify
scripts/gt1000-agent --pretty patch assign-set 2 --target tuner --min 0 --max 1 --source internal-pedal --mode toggle --live --verify
scripts/gt1000-agent --pretty patch assign-set 3 --target delay1.sw --min 0 --max 1 --source cc80 --mode moment --live --verify
scripts/gt1000-agent --pretty patch assign-set 3 --target 987 --min 0 --max 1 --source 19 --mode toggle --midi-channel 1 --midi-cc 80 --midi-cc-min 0 --midi-cc-max 127 --live --verify
```
- This is the general Assign editor. Prefer `patch assign-cc` when mapping a decoded block parameter to a MIDI CC source.
- `--target` accepts raw target numbers, `block.parameter` references for decoded Assign target ranges, and exact aliases such as `tuner`, `divider1-channel-select`, `divider2-channel-select`, and `divider3-channel-select`.
- FX algorithm-specific targets can be referenced by schema id, for example `fx1Chorus.effectLevel2` or `fx2PitchShift.ps1PreDelay`.
- `--source` accepts raw source numbers, `num1`...`num5`, `cur-num`, `bank-down`, `bank-up`, `ctl1`...`ctl7`, `exp1-sw`, `exp1`, `exp2`, `exp3`, `internal-pedal`, `wave-pedal`, `input-level`, and supported MIDI CC aliases like `cc1`...`cc31` or `cc64`...`cc95`.
- Target min/max are provided as logical values and encoded with the GT-1000 Assign `+32768` offset rule.
- MIDI CC source aliases are converted to Assign source IDs; the Assign source ID is not the same byte as the outbound MIDI CC number.

### `patch set-bpm`
Change the patch master BPM using the validated four-nibble `BPM * 10` encoding.
```sh
scripts/gt1000-agent --pretty patch set-bpm 120.0 --live --verify
```
- `bpm`: `40.0`...`250.0`, with at most one decimal place.
- `--verify`: Re-reads the BPM address to confirm the write succeeded.
- `--user-slot Uxx-y`: Persist the BPM change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.

### `patch master-set`
Change one validated patch master field in the PatchEfct record.
```sh
scripts/gt1000-agent --pretty patch master-set level 95 --live --verify
scripts/gt1000-agent --pretty patch master-set key "Db(Bbm)" --live --verify
scripts/gt1000-agent --pretty patch master-set carryover on --live --user-slot U10-1 --verify
```
- Supported fields: `level`, `key`, `amp-ctl1`, `amp-ctl2`, `carryover`, `tempo-hold`, and `input-sensitivity`.
- Boolean fields accept `on`/`off`; key accepts raw `0`...`11` or names such as `C(Am)` and `Db(Bbm)`.
- `--user-slot Uxx-y`: Persist the change to any valid user slot instead of the temporary patch.

### `patch tuner-assign`
Install the tested Assign 16 mapping that toggles TUNER ON/OFF from MIDI CC#80.
```sh
scripts/gt1000-agent --pretty patch tuner-assign --live --verify
```
- Writes Assign 16 to target `987` (`TUNER ON/OFF` on the tested GT-1000 v4 unit with Bass Mode off), source CC#80, active range `0`...`127`.
- After installing, send values with `midi cc 80 127 --channel N --live` and `midi cc 80 0 --channel N --live`.
- `--user-slot Uxx-y`: Persist the Assign change to any valid user slot (`U01-1` through `U50-5`) instead of the temporary patch.

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
- `--user-slot Uxx-y`: Persist the plan to any valid user slot (`U01-1` through `U50-5`).

## Timeout and Port Selection

- `--timeout <seconds>`: Adjust the timeout for live reads (default is 8.0s).
- The CLI automatically targets the `GT-1000` port. It avoids `GT-1000 DAW CTRL`.

## Wiki Search Boundary

Search the local documentation wiki from the skill or shell with `rg`; do not add wiki search commands to the live-device CLI. The CLI should expose product state and validated device operations, while the skill owns documentation retrieval and interpretation.

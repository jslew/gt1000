# Address Map

## Top-Level Documents

| Address | Meaning |
|---|---|
| `00 00 00 00` | System common |
| `00 00 10 00` | System control |
| `00 00 30 00` | System MIDI |
| `00 00 40 00` | System input/output |
| `00 00 50 00` | System effects |
| `00 00 60 00` | System pitch/tuner |
| `00 00 70 00` | System manual-mode control |
| `00 01 00 00` | System input setting 1 |
| `00 01 01 00` | System input setting 2 |
| `00 01 09 00` | System input setting 10 |
| `00 10 00 00` | Program Change map bank 1 |
| `00 10 04 00` | Program Change map bank 2 |
| `00 10 08 00` | Program Change map bank 3 |
| `00 10 0C 00` | Program Change map bank 4 |
| `10 00 00 00` | Temporary/current patch |
| `20 00 00 00` | User patch 1 |
| `20 01 00 00` | User patch 2 |
| `21 79 00 00` | User patch 250 |
| `30 00 00 00` | Preset patch 1, read-only |

User patch addresses advance by Roland 7-bit address arithmetic, not simple 8-bit addition.

## Temporary Patch Subrecords

All offsets below are relative to temporary patch base `10 00 00 00`.

| Offset | Address | Record | Notes |
|---|---|---|---|
| `00 00 00` | `10 00 00 00` | PatchCommon | Name plus patch-level control functions |
| `00 01 00` | `10 00 01 00` | PatchStompBox | Stompbox selections |
| `00 02 00` | `10 00 02 00` | PatchLed | LED color/state data |
| `00 03 00` | `10 00 03 00` | Assign 1 | Assign size `00 00 00 2C` |
| `00 03 40` | `10 00 03 40` | Assign 2 | Assign blocks are spaced by `0x40` in 7-bit address space |
| `00 0A 40` | `10 00 0A 40` | Assign 16 | Last assign block |
| `00 10 00` | `10 00 10 00` | PatchEfct | Master/routing/chain, size `00 00 01 1C` |
| `00 12 00` | `10 00 12 00` | Compressor | Effect block summary address |
| `00 13 00` | `10 00 13 00` | Distortion 1 | Effect block summary address |
| `00 14 00` | `10 00 14 00` | Distortion 2 | Effect block summary address |
| `00 15 00` | `10 00 15 00` | AIRD Preamp 1 | Effect block summary address |
| `00 16 00` | `10 00 16 00` | AIRD Preamp 2 | Effect block summary address |
| `00 17 00` | `10 00 17 00` | Noise Suppressor 1 | Effect block summary address |
| `00 18 00` | `10 00 18 00` | Noise Suppressor 2 | Effect block summary address |
| `00 19 00` | `10 00 19 00` | Equalizer 1 | Effect block summary address |
| `00 1A 00` | `10 00 1A 00` | Equalizer 2 | Effect block summary address |
| `00 1B 00` | `10 00 1B 00` | Equalizer 3 | Effect block summary address |
| `00 1C 00` | `10 00 1C 00` | Equalizer 4 | Effect block summary address |
| `00 1D 00` | `10 00 1D 00` | Delay 1 | Effect block summary address |
| `00 1E 00` | `10 00 1E 00` | Delay 2 | Effect block summary address |
| `00 1F 00` | `10 00 1F 00` | Delay 3 | Effect block summary address |
| `00 20 00` | `10 00 20 00` | Delay 4 | Effect block summary address |
| `00 21 00` | `10 00 21 00` | Master Delay | Effect block summary address |
| `00 22 00` | `10 00 22 00` | Chorus | Effect block summary address |
| `00 23 00` | `10 00 23 00` | FX 1 | Effect block summary address |
| `00 3E 00` | `10 00 3E 00` | FX 2 | Effect block summary address |
| `00 59 00` | `10 00 59 00` | FX 3 | Effect block summary address |
| `00 74 00` | `10 00 74 00` | Reverb | Effect block summary address |
| `00 75 00` | `10 00 75 00` | Pedal FX | Effect block summary address |

## Current CLI Read Plan

`scripts/gt1000-agent patch dump --live` reads:

- `PatchCommon` name range.
- `PatchEfct` master/routing/chain range.
- Major effect block summaries listed above.

Physical control mappings require extra reads of `PatchCommon`, `SystemControl`, and Assign blocks. See [Patch Controls](patch-controls.md).

## System MIDI Known Offsets

Offsets below are relative to `System MIDI` address `00 00 30 00`.

| Offset | Field | Decoding |
|---:|---|---|
| `00` | RX channel | `0`...`15` = Ch.1...Ch.16 |
| `01` | Omni mode | `0` off, `1` on |
| `02` | TX channel | `0`...`15` = Ch.1...Ch.16, `16` = RX |
| `03` | Sync clock | `0` auto, `1` internal, `2` MIDI(auto), `3` USB(auto) |
| `04` | MIDI IN thru | `0` off, `1` MIDI out, `2` USB out, `3` USB/MIDI |
| `05` | USB IN thru | `0` off, `1` MIDI out, `2` USB out, `3` USB/MIDI |
| `06` | Clock out | `0` off, `1` on |
| `07` | Fixed value | `0` |
| `08` | Map select | `0` fixed, `1` program |
| `09`...`0D` | NUM1...NUM5 CC# | `0` off, `1`...`31` = CC#1...CC#31, `32`...`63` = CC#64...CC#95 |
| `0E`...`0F` | BANK DOWN/UP CC# | same CC encoding |
| `10`...`16` | CTL1...CTL7 CC# | same CC encoding |
| `17`...`1A` | EXP1 SW, EXP1, EXP2, EXP3 CC# | same CC encoding |

The MIDI implementation defines `System MIDI` total size as `00 00 00 1B`; the CLI reads a larger range for compatibility but decodes only the documented offsets above.

## Program Change Map

Program map banks are `PcmapPc` records:

| Bank | Address | Program Change numbers |
|---:|---|---|
| 1 | `00 10 00 00` | 1...128 |
| 2 | `00 10 04 00` | 129...256 |
| 3 | `00 10 08 00` | 257...384 |
| 4 | `00 10 0C 00` | 385...512 |

Each bank is size `00 00 04 00` and contains 128 four-nibble patch values. Values `0`...`249` map to `U01-1`...`U50-5`; values `250`...`499` map to `P01-1`...`P50-5`.

## System Input Settings

There are ten `SystemInputSetting` records:

| Setting | Address |
|---:|---|
| 1 | `00 01 00 00` |
| 2 | `00 01 01 00` |
| 10 | `00 01 09 00` |

Each setting is size `00 00 00 11`: offsets `00`...`0F` are a 16-byte ASCII name and offset `10` is input level, raw `12`...`52` = `-20`...`+20 dB`.

## System IN/OUT Known Offsets

Offsets below are relative to `System IN/OUT` address `00 00 40 00`.

| Offset | Field | Decoding |
|---:|---|---|
| `00` | Input level | raw `12`...`52` = `-20`...`+20 dB` |
| `01` | Main L AIRD output select | `0`...`39` output-select enum |
| `02` | Main R AIRD output select | `0`...`39` output-select enum |
| `11` | Sub L AIRD output select | `0`...`39` output-select enum |
| `12` | Sub R AIRD output select | `0`...`39` output-select enum |

The output-select enum is shared across main/sub L/R and includes line/recording, Roland/BOSS amp return/input choices, user slots, and the v3.11 MkII power-amp-in choices. The CLI decodes the documented `00`...`42` fields in this section: output selection, EQ gains/cutoffs, phones routing, total NS/reverb, USB levels, stereo links, and output levels.

## System Effects Known Offsets

Offsets below are relative to `System Effects` address `00 00 50 00`.

| Offset | Field | Decoding |
|---:|---|---|
| `00` | Phrase loop mode | `0` mono, `1` stereo |
| `01` | Phrase loop rec action | `0` REC>PLAY>DUB, `1` REC>DUB>PLAY |
| `02` | Metronome level | `0`...`100` |
| `03` | Main ground lift | raw `0`...`5` = `1`...`6` |
| `04` | Total metronome out | `0` main out, `1` sub out, `2` main+sub |
| `05`...`06` | Fixed values | `0`, `0` |

## System Pitch Known Offsets

Offsets below are relative to `System Pitch` address `00 00 60 00`.

| Offset | Field | Decoding |
|---:|---|---|
| `00`...`03` | Reference pitch | four nibbles, `435`...`445 Hz` |
| `04` | Poly tuner type | `6-REGULAR`, `6-DROP D`, `7-REGULAR`, `7-DROP A`, `4-B REGULAR`, `5-B REGULAR` |
| `05` | Poly tuner offset | raw `11`...`16` = `-5`...`----` |
| `06` | Tuner output | `0` mute, `1` bypass, `2` thru |

## System Manual Control Known Offsets

Offsets below are relative to `System Manual Control` address `00 00 70 00`.

| Offset | Field | Decoding |
|---:|---|---|
| `00`, `02`, `04`, `06`, `08` | Manual NUM1...NUM5 function | Manual-mode function enum |
| `01`, `03`, `05`, `07`, `09` | Manual NUM1...NUM5 mode | `0` toggle, `1` moment |
| `0A`...`0E` | Manual NUM1...NUM5 preference | `0` patch, `1` system |

Manual-mode function values are similar to patch control functions but use their own compact enum: raw `1` starts at `LEVEL +10`, raw `11` is `TUNER/MANUAL`, raw `55`...`57` are tuner/manual variants, and raw `58`...`59` are FX4/FX4 trigger on firmware that exposes FX4.

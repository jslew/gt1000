# Address Map

## Top-Level Documents

| Address | Meaning |
|---|---|
| `00 00 00 00` | System common |
| `00 00 10 00` | System control |
| `00 00 30 00` | System MIDI |
| `00 00 40 00` | System input/output |
| `00 00 50 00` | System effects |
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

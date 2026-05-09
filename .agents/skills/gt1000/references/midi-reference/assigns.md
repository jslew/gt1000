# Assigns

Assign blocks let physical controls, internal pedals, wave pedals, input level, or MIDI CC messages control arbitrary targets.

Temporary patch Assign 1 starts at `10 00 03 00`. Each Assign block is spaced by `0x40` in Roland 7-bit address space:

| Assign | Address |
|---:|---|
| 1 | `10 00 03 00` |
| 2 | `10 00 03 40` |
| 16 | `10 00 0A 40` |

Assign block size: `00 00 00 2C`.

## Assign Block Layout

Offsets are relative to the Assign address.

| Offset | Field | Encoding |
|---:|---|---|
| `00` | SW | byte, `0` off, `1` on |
| `01`...`04` | Target | four nibbles |
| `05`...`08` | Target min | four nibbles |
| `09`...`0C` | Target max | four nibbles |
| `0D` | Source | byte |
| `0E` | Mode | byte, `0` toggle, `1` moment |
| `0F` | Wave rate | byte |
| `10` | Waveform | byte: saw, triangle, sine |
| `11` | Internal pedal trigger | byte |
| `12` | Internal pedal time | byte |
| `13` | Internal pedal curve | byte |
| `14`...`17` | Active range low | four nibbles |
| `18`...`1B` | Active range high | four nibbles |
| `1C` | MIDI channel | byte, `0` system, `1`...`16` |
| `1D` | MIDI CC number | byte |
| `1E`...`21` | MIDI CC value min | four nibbles |
| `22`...`25` | MIDI CC value max | four nibbles |
| `27` | MIDI PC number | byte |
| `28`...`29` | MIDI bank MSB | two nibbles |
| `2A`...`2B` | MIDI bank LSB | two nibbles |

## Source Values

Common source IDs:

| Raw | Source |
|---:|---|
| `0`...`4` | NUM1...NUM5 |
| `5` | Current Number |
| `6` | BANK DOWN |
| `7` | BANK UP |
| `8`...`14` | CTL1...CTL7 |
| `15` | EXP1 switch |
| `16` | EXP1 pedal |
| `17` | EXP2 pedal |
| `18` | EXP3 pedal |
| `19` | Internal pedal |
| `20` | Wave pedal |
| `21` | Input |
| `22`...`52` | CC#1...CC#31 |
| `53`...`84` | CC#64...CC#95 |

Important: Assign source IDs are not MIDI CC numbers. For example, CC#80 is source byte `0x45` (`69` decimal), while the outbound MIDI control change controller byte is `0x50`.

## Target Min/Max Offset Rule

For most assign targets, encode min/max values as `value + 32768`, split into four nibbles.

For on/off targets:

| Logical value | Encoded integer | Four nibbles |
|---|---:|---|
| Off | `32768` | `08 00 00 00` |
| On | `32769` | `08 00 00 01` |

## Tuner Notes

- Do not write random tuner SysEx addresses.
- `00 00 00 06` is not tuner on/off in the GT-1000 MIDI implementation.
- On the tested GT-1000 v4 unit with Bass Mode off, tuner on/off responds to Assign target `987`.
- The official PDF contains two Assign target tables and can be misleading; one table lists `991 | TUNER | ON OFF`, but the tested unit responds to `987`.
- The app maps temporary Assign 16 to target `987`, source CC#80, active range `0...127`, then sends CC#80 values.
- Channel Voice messages are gated by `MENU:MIDI:MIDI SETTING:RX CHANNEL`; SysEx writes are not.

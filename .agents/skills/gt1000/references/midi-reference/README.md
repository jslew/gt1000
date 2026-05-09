# GT-1000 MIDI Reference Wiki

This is a local, agent-oriented reference distilled from the official BOSS/Roland GT-1000/GT-1000CORE MIDI Implementation PDF.

Source PDF:
https://static.roland.com/assets/media/pdf/GT-1000-MIDI-Implementation.pdf

Use this wiki for implementation notes, address lookup, and decoder behavior. It is intentionally not a full copy of the vendor manual.

## Pages

- [Address Map](address-map.md): top-level SysEx address structure and temporary/current patch subrecords.
- [Patch Controls](patch-controls.md): physical NUM/BANK/CTL/EXP switch mappings, patch vs system preference, and function enums.
- [Assigns](assigns.md): Assign block layout, source encoding, target range encoding, and tuner-specific notes.
- [Patch Effect](patch-effect.md): PatchEfct master settings, chain element table, and routing offsets.
- [CLI Usage](cli-usage.md): agent-facing CLI views and example read commands.

## Core SysEx Facts

- Manufacturer ID: `41`
- GT-1000/GT-1000CORE model ID: `00 00 00 4F`
- RQ1 command: `11`
- DT1 command: `12`
- Roland/BOSS checksums are calculated over address plus data/size only.
- Addresses and sizes use four 7-bit bytes, not normal 8-bit hex integers.
- Temporary/current patch base: `10 00 00 00`
- The normal MIDI endpoint is `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.

## Address Arithmetic

Roland address bytes are 7-bit. To add an offset:

1. Convert the four address bytes to an integer by shifting left 7 bits per byte.
2. Add the offset.
3. Re-split into four 7-bit bytes.

This matters across `0x7F` boundaries. For example, temporary PatchEfct chain element 40 is at `10 00 11 0F`, not `10 00 10 8F`.

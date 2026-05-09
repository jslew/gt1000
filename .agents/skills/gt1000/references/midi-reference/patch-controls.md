# Patch Controls

Physical switch behavior is split between system preferences and patch-local functions.

To answer "what do the switches do in this patch?", read:

- `PatchCommon` at `10 00 00 00`, size `00 00 00 7E`.
- `SystemControl` at `00 00 10 00`, size `00 00 00 36`.
- Assign blocks if you need layered behavior beyond the direct control functions.

## Effective Mapping Rule

`SystemControl` contains preference bytes for each physical control:

| Raw | Meaning |
|---:|---|
| `0` | Use patch-local mapping from PatchCommon |
| `1` | Use global/system mapping from SystemControl |

When a preference is `PATCH`, decode the corresponding PatchCommon function/mode. When it is `SYSTEM`, decode the corresponding SystemControl function/mode.

## PatchCommon Control Offsets

Offsets below are relative to `PatchCommon` address `10 00 00 00`.

| Offset | Field |
|---:|---|
| `00`...`0F` | Patch name, 16 ASCII bytes |
| `23` | NUM1 function |
| `24` | NUM1 mode |
| `25` | NUM2 function |
| `26` | NUM2 mode |
| `27` | NUM3 function |
| `28` | NUM3 mode |
| `29` | NUM4 function |
| `2A` | NUM4 mode |
| `2B` | NUM5 function |
| `2C` | NUM5 mode |
| `2D` | BANK DOWN function |
| `2E` | BANK DOWN mode |
| `2F` | BANK UP function |
| `30` | BANK UP mode |
| `31` | CTL1 function |
| `32` | CTL1 mode |
| `33` | CTL2 function |
| `34` | CTL2 mode |
| `35` | CTL3 function |
| `36` | CTL3 mode |
| `37` | CTL4 function |
| `38` | CTL4 mode |
| `39` | CTL5 function |
| `3A` | CTL5 mode |
| `3B` | CTL6 function |
| `3C` | CTL6 mode |
| `3D` | CTL7 function |
| `3E` | CTL7 mode |
| `3F` | Current Number function |
| `40` | Current Number mode |
| `41` | EXP1 switch function |
| `42` | EXP1 switch mode |
| `43` | EXP1 pedal function |
| `44` | EXP2 pedal function |
| `45` | EXP3 pedal function |

Modes:

| Raw | Meaning |
|---:|---|
| `0` | Toggle |
| `1` | Moment |

EXP pedal functions:

| Raw | Meaning |
|---:|---|
| `0` | Off |
| `1` | Foot Volume |
| `2` | Pedal FX |
| `3` | Foot Volume + Pedal FX |

## SystemControl Offsets

Offsets below are relative to `SystemControl` address `00 00 10 00`.

| Offset | Field |
|---:|---|
| `00`...`0D` | Global NUM/BANK functions and modes |
| `0E`...`22` | Global CTL/CNum/EXP functions and modes |
| `23` | NUM1 preference |
| `24` | NUM2 preference |
| `25` | NUM3 preference |
| `26` | NUM4 preference |
| `27` | NUM5 preference |
| `28` | BANK DOWN preference |
| `29` | BANK UP preference |
| `2A` | CTL1 preference |
| `2B` | CTL2 preference |
| `2C` | CTL3 preference |
| `2D` | CTL4 preference |
| `2E` | CTL5 preference |
| `2F` | CTL6 preference |
| `30` | CTL7 preference |
| `31` | Current Number preference |
| `32` | EXP1 switch preference |
| `33` | EXP1 preference |
| `34` | EXP2 preference |
| `35` | EXP3 preference |

## CTL/BANK Function Values

These apply to CTL1-CTL7, BANK switches, Current Number, and EXP1 switch. NUM1-NUM5 have similar values, except raw `1` means the matching number switch instead of BANK UP.

| Raw | Meaning |
|---:|---|
| `0` | Off |
| `1` | Bank up |
| `2` | Bank down |
| `3` | Patch +1 |
| `4` | Patch -1 |
| `5` | Level +10 |
| `6` | Level +20 |
| `7` | Level -10 |
| `8` | Level -20 |
| `9` | BPM tap |
| `10` | Delay 1 tap |
| `11` | Delay 2 tap |
| `12` | Delay 3 tap |
| `13` | Delay 4 tap |
| `14` | Master Delay tap |
| `15` | Tuner |
| `16` | Amp CTL1 |
| `17` | Amp CTL2 |
| `18` | Compressor on/off |
| `19` | Distortion 1 on/off |
| `20` | Distortion 1 solo |
| `21` | Distortion 2 on/off |
| `22` | Distortion 2 solo |
| `23` | AIRD Preamp 1 on/off |
| `24` | AIRD Preamp 1 solo |
| `25` | AIRD Preamp 2 on/off |
| `26` | AIRD Preamp 2 solo |
| `27` | Noise Suppressor 1 |
| `28` | Noise Suppressor 2 |
| `29` | Equalizer 1 |
| `30` | Equalizer 2 |
| `31` | Equalizer 3 |
| `32` | Equalizer 4 |
| `33` | Delay 1 |
| `34` | Delay 2 |
| `35` | Delay 3 |
| `36` | Delay 4 |
| `37` | Master Delay |
| `38` | Chorus |
| `39` | FX1 |
| `40` | FX2 |
| `41` | FX3 |
| `42` | FX1 trigger |
| `43` | FX2 trigger |
| `44` | FX3 trigger |
| `45` | Reverb |
| `46` | Pedal FX |
| `47` | Divider 1 channel select |
| `48` | Divider 2 channel select |
| `49` | Divider 3 channel select |
| `50` | Send/Return 1 |
| `51` | Send/Return 2 |
| `52` | Looper |
| `53` | Looper stop |
| `54` | Looper clear |
| `55` | Metronome |
| `56` | MIDI start |
| `57` | MMC play |
| `58` | Master Delay trigger |

## Example: Patch `01-2`, "Chunky Clean"

Observed on the live unit:

- All SystemControl preferences read as `PATCH`.
- CTL1 = Distortion 1, Toggle.
- CTL2 = Master Delay, Toggle.
- CTL3 = Tuner, Toggle.
- CTL4-CTL7 = Off.
- EXP1 switch = Pedal FX, Toggle.
- EXP1 pedal = Foot Volume + Pedal FX.
- EXP2 and EXP3 = Off.
- Assign 1-16 all read `SW = OFF`, so no active Assign layer was present.

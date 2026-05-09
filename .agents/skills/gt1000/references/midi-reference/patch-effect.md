# Patch Effect

PatchEfct is the temporary patch section containing master settings, routing, output simulator settings, and the signal-chain element list.

Address: `10 00 10 00`

Size: `00 00 01 1C` in Roland 7-bit address space, which is 156 bytes of data.

## Key Offsets

Offsets are relative to PatchEfct.

| Offset | Field |
|---:|---|
| `00`...`0C` | Foot Volume min/max/pedal position/curve |
| `0D`...`16` | Divider 1 |
| `17`...`19` | Mixer 1 |
| `1A`...`23` | Divider 2 |
| `24`...`26` | Mixer 2 |
| `27`...`30` | Divider 3 |
| `31`...`33` | Mixer 3 |
| `34` | Send/Return 1/2 stereo link |
| `35`...`3B` | Send/Return 1 |
| `3C`...`42` | Send/Return 2 |
| `44` | Looper play level |
| `45`...`51` | Main speaker simulator L/R |
| `52`...`5E` | Sub speaker simulator L/R |
| `60` | Master patch level |
| `61`...`64` | Master BPM, four nibbles of `BPM * 10` |
| `65` | Master key |
| `66` | Master Amp CTL1 |
| `67` | Master Amp CTL2 |
| `68`...`01 18` | Chain elements 1...49 |
| `01 19` | Master carryover |
| `01 1A` | Control/Assign tempo hold |
| `01 1B` | Control/Assign input sens |

## Chain Element Values

| Raw | Element |
|---:|---|
| `0` | Compressor |
| `1` | Distortion 1 |
| `2` | Distortion 2 |
| `3` | AIRD Preamp 1 |
| `4` | AIRD Preamp 2 |
| `5` | Noise Suppressor 1 |
| `6` | Noise Suppressor 2 |
| `7` | FX1 |
| `8` | FX2 |
| `9` | FX3 |
| `10` | Equalizer 1 |
| `11` | Equalizer 2 |
| `12` | Equalizer 3 |
| `13` | Equalizer 4 |
| `14` | Chorus |
| `15` | Delay 1 |
| `16` | Delay 2 |
| `17` | Delay 3 |
| `18` | Delay 4 |
| `19` | Master Delay |
| `20` | Reserved |
| `21` | Reverb |
| `22` | Foot Volume |
| `23` | Pedal FX |
| `24` | Send/Return 1 |
| `25` | Send/Return 2 |
| `26` | Looper |
| `27` | Sub Speaker Simulator L |
| `28` | Sub Speaker Simulator R |
| `29` | Main Speaker Simulator L |
| `30` | Main Speaker Simulator R |
| `31`...`34` | Reserved |
| `35` | Divider 1 |
| `36` | Branch Split 1 |
| `37` | Mixer 1 |
| `38` | Divider 2 |
| `39` | Branch Split 2 |
| `40` | Mixer 2 |
| `41` | Divider 3 |
| `42` | Branch Split 3 |
| `43` | Mixer 3 |
| `44` | Reserved |
| `45` | Sub Out L |
| `46` | Sub Out R |
| `47` | Main Out L |
| `48` | Main Out R |

## BPM Encoding

GT-1000 BPM values are four 4-bit nibbles of `BPM * 10`.

Example: `120.0 BPM` becomes decimal `1200`, encoded as:

```text
00 04 0B 00
```

## Chain Address Example

Chain element 1:

```text
10 00 10 68
```

Chain element 40:

```text
10 00 11 0F
```

The jump is caused by Roland 7-bit address arithmetic.

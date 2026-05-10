# Parameter Guide Extraction

Source: current official GT-1000 Parameter Guide `GT-1000_parameter_eng13_W.pdf`.

## What The Parameter Guide Covers

The Parameter Guide is the main semantic reference for effect types, parameters, menu settings, control assignment, MIDI behavior, in/out settings, hardware settings, tuner/metronome, and patch write operations.

Use it to understand what a decoded parameter means in musical/user terms. Use the MIDI Implementation for exact SysEx addresses and byte encodings.

## Effect Chain Model

The GT-1000 has a movable effect chain containing effect blocks, output blocks, send/return blocks, and routing blocks.

Agent mapping:

- Chain layout: `scripts/gt1000-agent patch chain --live`
- One block detail: `scripts/gt1000-agent patch block <id> --live`
- Low-level chain table: [Patch Effect](../midi-reference/patch-effect.md)

## Core Effect Blocks

The Parameter Guide defines dedicated sections for:

| Block | Notes for agent descriptions |
|---|---|
| Compressor | Dynamics control before/within the chain |
| Distortion 1, 2 | Drive/boost/fuzz/distortion types |
| AIRD Preamp 1, 2 | Amp model, gain, EQ, level, solo, speaker-related tone behavior |
| Noise Suppressor 1, 2 | Noise reduction/gating |
| Equalizer 1-4 | Tone shaping and level |
| Delay 1-4 | Individual delay blocks |
| Master Delay | Global/primary delay block with multiple delay types |
| Chorus | Dedicated chorus block |
| FX1-FX3 | Multi-effect slots with many effect algorithms |
| Reverb | Space/ambience |
| Pedal FX | Wah/pedal-controlled effects |
| Foot Volume | Volume pedal point in the chain |
| Divider 1-3 | Splits signal paths |
| Mixer 1-3 | Recombines/balances split paths |
| Send/Return 1, 2 | External loop integration |
| Looper | Phrase loop block |
| Main/Sub Speaker Simulators | Output speaker/mic simulation |
| Master | Patch-level BPM, key, level, amp control |

## FX Slot Algorithms

FX slots include many algorithms. The current v4+ Parameter Guide table of contents includes:

- Acoustic Guitar Simulator
- AC Resonance
- Auto Wah
- Chorus and Chorus Bass
- Classic-Vibe
- Compressor
- Defretter and Defretter Bass
- Distortion
- Feedbacker
- Flanger and Flanger Bass
- Harmonist
- Humanizer
- Mastering FX
- Octave and Octave Bass
- Overtone
- Pan
- Phaser
- Pitch Shifter
- Ring Mod
- Rotary
- Sitar Sim
- Slicer
- Slow Gear and Slow Gear Bass
- Sound Hold
- S-Bend
- Touch Wah and Touch Wah Bass
- Tremolo
- Vibrato

When the CLI reports an FX block with only raw type values, improve the decoder before making strong claims about the algorithm.

## MENU Sections

Important menu areas:

| Menu | Purpose |
|---|---|
| CONTROL MODE | Performance switch behavior mode |
| CONTROL ASSIGN | Physical control functions and Assign settings |
| IN/OUT SETTING | Input level, output select, phones, total EQ/NS/reverb, USB audio settings |
| PLAY OPTION | Patch/bank selection behavior |
| MIDI | RX/TX channels, sync, MIDI thru, program map, bulk dump |
| HARDWARE SETTING | Knobs, amp control, expression hold, ground lift, calibration, auto off |
| TUNER | Tuning and tuner behavior |
| METRONOME | Tempo/metronome settings |
| WRITE | Patch write/exchange/initialize/insert operations |

## Control Assign

The Parameter Guide's Control Assign section explains:

- Direct control functions for NUM/BANK/CTL/EXP controls.
- Assign settings for mapping sources to targets.
- Virtual expression systems: internal pedal and wave pedal.
- Input-level-driven control.
- Patch MIDI messages.
- LED color.
- Tempo hold.

Agent mapping:

- Direct physical switch mappings: [Patch Controls](../midi-reference/patch-controls.md)
- Assign blocks and target/source encodings: [Assigns](../midi-reference/assigns.md)

## In/Out Setting

In/out settings are critical to tone description. The same patch can sound very different depending on output select and routing.

Important areas:

- Input level.
- Main out and sub out output select.
- Phones setting.
- Total settings such as total noise suppressor and total reverb level.
- USB audio routing and levels.

The current CLI does not yet read system in/out settings. Avoid overconfident claims about final sound into a specific amp/PA unless those settings are decoded.

## MIDI

The Parameter Guide covers MIDI setting concepts such as RX channel, TX channel, sync clock, MIDI thru, program map, and bulk dump.

Agent caution:

- GT-1000 Channel Voice messages are gated by RX channel.
- SysEx reads/writes are not gated the same way.
- When a CC-driven Assign seems inactive, check RX channel and CC source encoding.

## Write Operations

Patch write/exchange/initialize/insert are persistent operations. The agent should not perform these without explicit user confirmation.

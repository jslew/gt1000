# Sound List Extraction

Source: current official GT-1000 Sound List `GT-1000_sound_eng05_W.pdf`.

## What The Sound List Covers

The Sound List maps preset patch numbers to patch names and the default performance controls shown in columns:

- Patch number
- Patch name
- CTL1
- CTL2
- CTL3
- EXP1 SW
- EXP1

This is useful for understanding factory preset intent, but live user patches may differ.

## Preset Control Pattern

Many factory presets follow a common performance pattern:

- CTL3 is often tuner/manual.
- EXP1 SW is often Pedal FX.
- EXP1 is often Foot Volume/Pedal FX.
- CTL1 and CTL2 vary by patch and often toggle drive, divider channel select, master delay, chorus, or special triggers.

## Example Rows

Examples from the v4+ sound list:

| Preset | Name | CTL1 | CTL2 | CTL3 | EXP1 SW | EXP1 |
|---|---|---|---|---|---|---|
| P01-1 | Premium Drive | Divider 1 channel select / Distortion 1 | Master Delay / Distortion 1 Solo | Tuner/Manual | Pedal FX | Foot Volume/Pedal FX |
| P01-5 | Multiband Crunch | Compressor / FX1 Classic Vibe | Master Delay / Chorus | Tuner/Manual | Pedal FX | Foot Volume/Pedal FX |
| P06-3 | Clean Cho/Dly | FX1 Chorus | Master Delay | Tuner/Manual | Pedal FX | Foot Volume/Pedal FX |
| P12-3 | Wild Stereo | BPM Tap | Master Delay | Tuner/Manual | Chorus | Master Delay effect level |
| P13-1 | Gig Ready | Divider 1 channel select | Master Delay | Tuner/Manual | AIRD Preamp 2 Solo | AIRD Preamp 2 Gain |

## Agent Caution

- Do not assume a user patch matches the sound list.
- Prefer live CLI/physical control reads for the connected unit.
- Use the sound list to explain factory preset design intent or compare a user patch to a known preset.


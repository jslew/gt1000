# USB Audio and Re-Amp (manual paraphrase)

Sources: GT-1000 Owner's Manual and Parameter Guide (fetched via `scripts/fetch-current-manuals.sh`). Do not treat this page as a full manual substitute.

## Role of USB

With a USB cable on **USB COMPUTER**, the GT-1000 is a **6-in / 6-out** audio interface plus MIDI. The Owner's Manual defers signal-flow detail to the Parameter Guide **MENU → IN/OUT SETTING → USB AUDIO**.

Install the **BOSS GT-1000 USB driver** for your OS (see [boss.info support](https://www.boss.info/support/)); the archive **Readme.htm** documents channel names and macOS/Windows quirks.

## Channel map (to computer)

| USB channels | Parameter Guide name | Content |
|--------------|----------------------|---------|
| 1–2 | MAIN | Effected sound from **MAIN OUT** path (`EFX OUT` level) |
| 3–4 | DRY | Dry guitar; unaffected by patch blocks |
| 5–6 | SUB | Effected sound from **SUB OUT** path |

CLI `system inout` maps the level knobs to: `usbMainEfxOut`, `usbMainMixLevel`, `usbDryOut`, `usbDryToEfx`, `usbSubEfxOut`, `usbSubMixLevel`.

## Signal flow (recording)

- **MAIN / SUB**: guitar through the patch → USB out; computer playback can be **mixed at the final stage** of MAIN/SUB (`MIX LEVEL`).
- **DRY**: always dry guitar to USB; computer return is **not** mixed on the DRY bus itself.

## Re-amping (playback dry, capture wet)

Parameter Guide (USB DRY diagram):

1. Computer audio enters **USB IN**.
2. **`DRY OUT`** sends a copy unchanged.
3. **`TO EFX`** feeds the **beginning of the effect chain** (this is the re-amp path).
4. Processed result goes to USB **MAIN** (and/or SUB) via **`EFX OUT`**.

Official wording: you can record dry on DRY, then **play it back** and pass it through the GT-1000 effect chain again to remake the tone.

For the audio lab:

- **Play back to the DRY USB path** (channels 3–4 on a 6-channel device).
- **Capture MAIN** (channels 1–2) for the processed re-amp result.
- Keep **`TO EFX`** and **`EFX OUT`** high enough (your unit already shows 100%).

## DIR MON (critical for computer use)

Under **USB MAIN** (and similarly **USB SUB**), **DIR MON** (direct monitor):

| DIR MON | Use when |
|---------|----------|
| **OFF** | Audio is routed **through the computer** (DAW re-amp, multi-track workflow). |
| **ON** | Using the GT-1000 **without** a computer; local monitoring from the unit. |

**Cannot be saved** — it returns **ON at power-on**. For unattended USB re-amp tests, set **USB MAIN → DIR MON → OFF** on the hardware after each power cycle.

If DIR MON stays ON, USB playback may not appear on the MAIN USB capture bus even when levels look correct in SysEx.

## PHONES / local monitoring

With DIR MON OFF and computer pass-through, you may **not hear** re-amp output on headphones unless the computer monitors the return track (“set computer to through” per Parameter Guide).

## Agent / CLI notes

- Prefer the **BOSS driver** and the documented **MAIN / DRY / SUB** routing over ad-hoc Core Audio devices when possible.
- `audio reamp` upmixes playback to USB channels 3–4; verify **DIR MON OFF** if wet capture stays silent.
- Phase 2: decode/write **DIR MON** if a SysEx address is confirmed; until then, treat it as a **manual preflight** step.

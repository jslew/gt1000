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

**SysEx address:** `SetupEfct` at `00 20 01 00`, size 4 bytes (GT-1000 MIDI Implementation).

| Offset | Field | Values |
|--------|-------|--------|
| `00` | (fixed) | `1` |
| `01` | MAIN:DIR MON | `0` OFF, `1` ON |
| `02` | SUB:DIR MON | `0` OFF, `1` ON |
| `03` | (fixed) | `1` |

CLI:

```sh
scripts/gt1000-agent --pretty system setup-efct --live --timeout 8
scripts/gt1000-agent --pretty audio prepare-reamp --midi-timeout 8
```

`audio reamp` runs **prepare-reamp** automatically unless `--no-prepare-usb` is passed.

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
- **DIR MON** is writable at runtime via `audio prepare-reamp` even though the Parameter Guide says it cannot be **saved** across power cycles.

### macOS USB audio (sounddevice)

`gt1000-agent` uses **sounddevice** (PortAudio) for capture and playback — the same class of API GarageBand uses. **ffmpeg is not used.**

```sh
pip install -r skills/gt1000/requirements-audio.txt
scripts/gt1000-agent --pretty audio ports
scripts/gt1000-agent --pretty audio probe
```

**Device index** for `--device-index` is the **PortAudio** index from `audio ports` → `gt1000Inputs` / `gt1000Outputs`.

### Troubleshooting

1. **Quit the DAW** if it holds exclusive USB access.
2. **Microphone privacy** for Cursor/Terminal.
3. **Play during capture** (probe is ~3–5 s).
4. **Bus mismatch:** default `record-dry` saves **USB 3–4**; use `--bus main` or `--bus both` for **1–2**.

```sh
scripts/gt1000-agent --pretty audio record-dry --session my-take --bus both --duration 5
```

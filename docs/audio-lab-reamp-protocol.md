# Audio Lab Re-amp Protocol

Checklist for repeatable GT-1000 USB re-amp renders (Phase 2). Implementation: `audio session render` and `audio reamp` share the same `reamp_capture` path in `audio_lab/orchestrator.py`.

## Before the first render

1. **Connect** GT-1000 USB audio + MIDI (`GT-1000`, not `GT-1000 DAW CTRL`).
2. **Install** `pip install -r skills/gt1000/requirements-audio.txt` on the host running the CLI.
3. **Quit** other apps using GT-1000 USB audio (GarageBand, Logic, etc.).
4. **macOS privacy:** allow Microphone for Terminal/Cursor (USB capture uses the same permission path).
5. **Session dry file:** `audio generate-tone`, `audio record-dry`, or copy a known dry WAV into the session as `dry.wav`.
6. **Optional init snapshot:** `audio session init --session <name> --live` stores `deviceSnapshots/systemInOut.json`, `setupEfct.json`, and `patch.json`.

## Per render

1. **USB DIR MON OFF** — `audio prepare-reamp` (or leave default; `session render` / `reamp` call this unless `--no-prepare-usb`). SetupEfct DIR MON is runtime-only and resets at power-on.
2. **Playback** — dry stereo is sent to GT-1000 USB playback (dry role → channels 3–4 in the 6-ch file). Use the **MAIN** USB playback device on firmware 1.20+ when the driver exposes it.
3. **Capture** — duplex playback + record on the same PortAudio device; extract USB **1–2** (main/processed) to the wet WAV.
4. **Settle** — after any patch SysEx writes, wait ≥0.25 s before render (`--settle-seconds` on `session render`).
5. **Metadata** — each `session render --label <name>` writes:
   - `renders/<label>-wet.wav`
   - `renders/<label>-patch.json` (temporary patch name, chain, read hash)
   - append to `meta.json` → `renders[]` log

## USB mix levels (persistent)

Read: `system inout --live`

Write (typed, verified): `system inout-set <field> <value> --live --verify`

Fields: `usbDryOut`, `usbDryToEfx`, `usbMainEfxOut`, `usbMainMixLevel`, `usbSubEfxOut`, `usbSubMixLevel` (0…200). Kebab aliases accepted (`usb-dry-out`, etc.).

Re-read after writes and confirm values appear in the next `session init --live` snapshot.

## Stability target (Phase 2 exit)

Two `session render` passes with the **same patch** and **same dry.wav** should land within **0.5 dB RMS** of each other on the wet file (broadcast LUFS optional later).

## Troubleshooting

See [skills/gt1000/references/gt1000-wiki/usb-audio.md](../skills/gt1000/references/gt1000-wiki/usb-audio.md) and `audio probe`.

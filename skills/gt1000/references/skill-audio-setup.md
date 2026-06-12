# USB audio lab — first-time setup

MIDI-only commands (`patch`, `ports`, `system`, etc.) need **no extra Python packages**. USB **audio lab** (`audio generate-tone`, `compare-branches`, `probe-param`, …) needs **sounddevice** and **numpy** once per Python environment. Installing the skill copies files only; it does **not** run `pip` for you.

**Before the first audio lab command**, install into the Python environment that will run `$GT1000_AGENT`.
Prefer a project or agent venv instead of system Python:

```sh
python3 -m venv .venv                    # if the project has no venv yet
.venv/bin/pip install -r "<skill-dir>/requirements-audio.txt"
```

In the source checkout, `<skill-dir>` is usually `skills/gt1000`, so the direct command is:

```sh
python3 -m pip install -r skills/gt1000/requirements-audio.txt
```

Use only that requirements file (`sounddevice`, `numpy`). **Do not** install `soundfile` or other extras unless another tool in the project needs them—the audio lab uses the stdlib `wave` module for WAV files.

If an audio command fails with `ModuleNotFoundError: No module named 'numpy'` or `No module named 'sounddevice'`, install the requirements above and retry the failed audio command once. Do not keep retrying the live command before fixing the Python environment.

Confirm audio works:

```sh
$GT1000_AGENT --pretty audio ports
$GT1000_AGENT --pretty audio probe --duration 3
```

Use the same interpreter for later audio commands (project `.venv/bin/python` behind the wrapper, or set `GT1000_AUDIO_PYTHON` when developing the gt1000 repo).

## Operational recovery notes

- If `audio compare-branches` or `audio render-branch` fails with `No GT-1000 MIDI destination found`, stop the investigation and run exactly one `$GT1000_AGENT --pretty ports --live --timeout 8`.
- If ports are missing or port enumeration hangs, quit BOSS Tone Studio/DAWs, reconnect or power-cycle the GT-1000, then check ports again before any write or render.
- If ports are visible but a known small write/read still fails, do not keep issuing temporary divider writes. Re-select the slot after recovery so the temporary patch returns to a known state, then restart the measurement step.
- For repeated branch renders in one investigation, run `audio prepare-reamp` once, then pass `--no-prepare-usb` on later render/compare commands to reduce extra CoreMIDI traffic.

## Tell the user what macOS will ask for

Explain this **once**, in plain language, before the first capture or re-amp—not on every command.

| What | Why |
|------|-----|
| **Microphone access** | System Settings → Privacy & Security → **Microphone** → allow the app running the agent (**Cursor**, **Terminal**, **iTerm**, **Gemini CLI**, etc.). USB capture from the GT-1000 is treated like microphone input. If capture is silent, check this before blaming the patch. |
| **Full-access / sandbox off** | Same as live MIDI: the agent shell must reach **CoreMIDI** and **PortAudio**. Read-only or sandboxed agent modes can block USB audio and look like device failures. |
| **Quit other apps on the GT-1000 USB driver** | **BOSS Tone Studio**, **GarageBand**, or a DAW may hold exclusive USB access. Only one app should use the interface during probe/record. |
| **BOSS GT-1000 USB driver** | Required once per Mac ([boss.info support](https://www.boss.info/support/)). Without it, `audio ports` may not list sensible GT-1000 inputs/outputs. |
| **DIR MON on the unit (not a macOS dialog)** | For computer re-amp, **USB MAIN → DIR MON** should be **OFF** (Parameter Guide: defaults ON after power-on). `audio prepare-reamp` sets this over MIDI for the session; mention it if wet USB stays silent. See `references/gt1000-wiki/usb-audio.md`. |

**Permissions note:** `pip install -r …/requirements-audio.txt` inside a **project `.venv`** is the preferred approach—isolated from Homebrew/system Python and does not need `sudo`. Avoid `pip install --break-system-packages` on the system interpreter.

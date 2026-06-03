# GT-1000 Agent Notes

## Git and Remotes

- Never run `git push` (or equivalent remote-update commands) unless the user explicitly asks you to push in this conversation.
- Treat push permission as time-bounded: an earlier "go ahead and push" does not carry forward after a later push or after a new session. Only honor a push request made since the more recent of (a) the last successful push in this repo during the current session, or (b) the start of the current agent session.
- Commits are fine when requested; pushing is a separate, explicit step.

## Project Shape

- This is a Python-based GT-1000 inspection/editing repo.
- Main code lives in `skills/gt1000/tools/gt1000`.
- Top-level `tools/gt1000` files are compatibility wrappers only.
- Main command surface is `scripts/gt1000-agent`.
- The runtime skill at `skills/gt1000/SKILL.md` is a musician-facing interface. Keep CLI development, maintenance, and testing guidance in this `AGENTS.md` file or deeper implementation references, not in the skill, unless the detail directly guides a musician-facing device interaction.
- Every CLI command should have unit test coverage and an explicit live test verification path. For commands that write, the live verification must use the command's validated/read-back verification flow where practical.
- **Agents: after adding or changing MIDI/audio CLI behavior, run the relevant live tests before finishing** (do not treat unit tests alone as sufficient when hardware is available). Audio lab: `GT1000_AUDIO_LIVE=1` + `tests/test_live_audio_lab.py`. Broader MIDI: `GT1000_LIVE=1` + `tests/test_live_skill.py`.
- Skill routing: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_routing tests.test_skill_routing_eval -q` (registry coverage + LLM trace rubric). Score a transcript: `scripts/gt1000-routing-eval score-jsonl --jsonl <path> --scenario <id>`. Live agy suite: `scripts/gt1000-routing-eval-run suite` from `gt1000-scratch` (chat JSONL under `~/.gemini/tmp/gt1000-scratch/chats/`; needs agy auth + full-access for `--live` MIDI — see `skills/gt1000/references/skill-routing-eval.md`).
- Useful checks:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q`
  - `GT1000_LIVE=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill -q`
  - `GT1000_LIVE=1 GT1000_ALLOW_DESTRUCTIVE=1 GT1000_LIVE_BACKUP_DIR=/tmp/gt1000-live-backups GT1000_LIVE_SKIP_SLOT_RESTORE=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_skill -q`
  - Slow extended destructive coverage: add `GT1000_DESTRUCTIVE_EXTENDED=1`
  - Global/System Control destructive coverage: add `GT1000_ALLOW_GLOBAL_SETTINGS=1` only when intentionally testing global setting writes
  - `scripts/gt1000-agent --pretty ports --live --timeout 8`
  - `scripts/gt1000-agent --pretty patch overview --live --timeout 8`
  - `scripts/gt1000-agent --pretty patch chain --live --timeout 15`
  - `scripts/gt1000-agent --pretty patch musician-summary --live --timeout 15`
  - `scripts/gt1000-agent --pretty patch slot U01-1 --live --view musician-summary --timeout 30`
  - `scripts/gt1000-agent --pretty patch plan default`
  - `scripts/gt1000-agent --pretty patch plan 4cm-template`
  - `scripts/gt1000-agent --pretty audio ports`
  - `scripts/gt1000-agent --pretty audio generate-tone --session <name>`
  - `scripts/gt1000-agent --pretty audio record-dry --session <name> --duration 5`
  - `scripts/gt1000-agent --pretty audio reamp --session <name>`
  - `scripts/gt1000-agent --pretty audio analyze <a.wav> <b.wav>`
  - `GT1000_AUDIO_LIVE=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_live_audio_lab -q` (requires `pip install -r skills/gt1000/requirements-audio.txt`; optional `GT1000_AUDIO_PYTHON` if not using the same interpreter). **Run this after every audio-lab change** when the GT-1000 is connected.
  - Divider A/B live test is opt-in (slow): `GT1000_AUDIO_LIVE=1 GT1000_COMPARE_LIVE=1 python3 -m unittest tests.test_live_audio_lab.LiveAudioLabTests.test_compare_branches_on_current_patch -v`

## Audio Lab (USB record / re-amp)

- Phase 1 lives under `skills/gt1000/tools/gt1000/audio_lab/` with CLI group `audio`. Roadmap: [docs/audio-lab-roadmap.md](docs/audio-lab-roadmap.md).
- **USB audio (macOS):** `pip install -r skills/gt1000/requirements-audio.txt` (`sounddevice` + `numpy`). Capture and playback both use PortAudio/Core Audio (no ffmpeg). Sessions: `~/gt1000-sessions/` or `GT1000_SESSION_DIR`.
- USB channel map: 1–2 main, 3–4 dry, 5–6 sub. `record-dry` (default `--bus dry`) captures six channels and extracts 3–4; `--bus main` or `--bus both` for 1–2. `audio probe` reports per-channel peaks.
- Live audio needs full-access environment + Microphone privacy for the host app (Cursor/Terminal).
- If `reamp` wet levels stay silent, verify USB DIR MON / routing on the unit (see `audio prepare-reamp`, wiki `usb-audio.md`).
- Phase 2: `audio session init`, `audio session render --label <name>`, `system inout-set <field> <value> --live --verify`. Protocol: [docs/audio-lab-reamp-protocol.md](docs/audio-lab-reamp-protocol.md).
- Example session flow:
  - `scripts/gt1000-agent --pretty audio session init --session div1-test --live --midi-timeout 20`
  - `scripts/gt1000-agent --pretty audio generate-tone --session div1-test --duration 3`
  - `scripts/gt1000-agent --pretty audio session render --session div1-test --label baseline`
  - Chained renders from separate CLI processes: add `--no-prepare-usb` after the first `prepare-reamp`, and `--no-patch-snapshot` on follow-up renders to avoid CoreMIDI churn.
- Phase 3 (agent-guided quantitative experiments): primitives `audio branch-context`, `compare-branches`, `probe-branch`, `probe-param`, `render-branch`, `analyze-trimmed`. **Agent** runs inspect → hypothesize → test loops (see [docs/audio-lab-investigation.md](docs/audio-lab-investigation.md)); default ~5 min budget unless user specifies. Divider LEVEL A/B often do not affect single-mode USB re-amp—use probe/render to verify. **Close-out:** present findings (baseline, what worked, final metric); if successful, **offer** temp-patch apply or `--user-slot` save only when the user agrees—probes restore bytes, so re-apply winning `patch set` before they hear or save. **Verification:** [docs/audio-lab-investigation-verification.md](docs/audio-lab-investigation-verification.md) (IMPRESSION oracle + fresh-agent test prompt).
  - `scripts/gt1000-agent --pretty system inout-set usb-main-mix-level 100 --live --verify --timeout 20`
  - `scripts/gt1000-agent --pretty system inputs-set 3 input-level 12 --live --verify --timeout 20`

## Skill Maintenance

- Keep `skills/gt1000/SKILL.md` focused on musician-facing conversational behavior: sounds, signal chains, routing, controls, user slots/banks/libraries, and safe musical edits.
- Do not put unit-test commands, destructive live-test recovery, CLI implementation notes, or package-maintenance workflow in the runtime skill.
- Inspect `skills/gt1000/tools/gt1000/*.py` when developing or debugging the CLI, but avoid pulling implementation details into normal musician-facing answers unless directly asked.
- If the current CLI cannot perform a requested musical edit, add or use a typed validator in the CLI rather than placing raw SysEx, naked byte arrays, or implementation workarounds in the skill.
- For reference/wiki updates, refresh official manuals into scratch space with `skills/gt1000/scripts/fetch-current-manuals.sh`, search extracted text with `rg`, then add concise paraphrased entries to `skills/gt1000/references/gt1000-wiki` or `skills/gt1000/references/midi-reference`.
- Do not commit downloaded PDFs or full extracted manual text.

## GT-1000 MIDI Details

- Local MIDI reference wiki: start at `skills/gt1000/references/midi-reference/README.md` before changing SysEx, control/assign decoding, CLI patch inspection, or write behavior.
- Local GT-1000 v4+ knowledge skill: `skills/gt1000/SKILL.md`; use it for musician-facing manual/parameter-guide lookups, patch explanations, controls, and device workflows.
- The GT-1000/GT-1000CORE SysEx model ID is `00 00 00 4F`.
- Roland/BOSS DT1/RQ1 checksums are calculated over address plus data/size only.
- GT-1000 BPM values are encoded as four 4-bit nibbles of `BPM * 10`; for example 120.0 BPM is `00 04 0B 00`.
- Temporary patch MASTER:BPM address is `10 00 10 61`.
- Temporary patch PatchEfct address is `10 00 10 00`.
- System metronome BPM address is `00 00 00 09`.
- Do not write random "tuner" SysEx addresses. `00 00 00 06` is not tuner on/off in the GT-1000 MIDI implementation.
- The tested tuner path maps an Assign target `987` (TUNER ON/OFF on tested GT-1000 firmware with Bass Mode off), source CC#80, then sends CC#80 values.
- The official GT-1000 v4.01 MIDI implementation PDF contains two Assign target tables and can be misleading: one table lists `991 | TUNER | ON OFF`, but the tested GT-1000 v4 unit with Bass Mode off responds to `987 | TUNER | ON OFF`.
- Assign target min/max values are 4-nibble values offset by `32768`. For an on/off target, encode OFF/ON as `32768` and `32769`, not raw `0` and `1`.
- Assign active range for a MIDI CC source should match the incoming CC value range. For CC#80, use ACT RANGE LO/HI `0...127`; using `0...16383` makes CC value `127` map near the bottom and can leave the target effectively off.
- CC source IDs are not the same as MIDI CC numbers. CC#80 is source byte `0x45` in the Assign SOURCE field, while the outbound MIDI control change still sends controller byte `0x50`.
- GT-1000 Channel Voice messages are gated by `MENU:MIDI:MIDI SETTING:RX CHANNEL`, while SysEx writes are not. If a CC does not appear to work but SysEx does, verify channel handling before assuming the Assign write failed.
- The normal endpoint is named `GT-1000`; avoid `GT-1000 DAW CTRL` unless deliberately targeting DAW control.
- Prefer typed enums/builders for SysEx payloads instead of naked byte arrays with comments. Preserve tests that assert exact byte output for any builder.

## Python Live MIDI Notes

- `skills/gt1000/tools/gt1000/live.py` uses Python `ctypes` against CoreMIDI.
- Codex CLI live MIDI verification must run outside the normal workspace/read-only sandbox, for example with yolo/`--dangerously-bypass-approvals-and-sandbox` or `-s danger-full-access`. The normal sandbox can deny CoreMIDI Mach service access and look like a GT-1000 timeout; the CLI includes a fast-fail sandbox/CoreMIDI preflight for live commands.
- CoreMIDI callbacks run on CoreMIDI-owned threads. Copy packet bytes in the callback, then update guarded Python state.
- Run live patch reads sequentially. Separate CLI processes can interleave GT-1000 replies on the same MIDI source. `gt1000-agent` enforces one process at a time via `~/.gt1000-agent/cli.lock` (exit `75` if another instance is running).
- If `ports --live` itself hangs or times out, stop live testing and recover CoreMIDI/the USB connection before continuing. Quit BOSS Tone Studio if it is open, then power-cycle or reconnect the GT-1000. If USB still shows `GT-1000` but CoreMIDI `MIDIGetNumberOfDestinations()` hangs, restart macOS before more live verification.
- If `ports --live` still lists the normal `GT-1000` endpoints but known-good SysEx reads such as `system controls --live` time out, stop live write testing and power-cycle or reconnect the GT-1000 before continuing. Repeated large reads can leave the tested unit visible to CoreMIDI but not replying to SysEx.
- A quick endpoint inventory should usually show:
  - Destination: `GT-1000`
  - Destination: `GT-1000 DAW CTRL`
  - Source: `GT-1000`
  - Source: `GT-1000 DAW CTRL`

## Write Safety

- Temporary patch writes are allowed through validated CLI plans and should be read-back verified.
- While developing the skill, agent-run user-slot writes are restricted to `U10-1` through `U11-5`; do not touch the lower banks unless explicitly instructed. The skill/CLI itself should support any valid user slot.
- Use `--verify` for live write commands so every written range is re-read and compared.
- The default destructive live test suite writes only the allowed user-slot range and MIDI channel voice messages; it does not write System Control/global settings. Set `GT1000_LIVE_SKIP_SLOT_RESTORE=1` when U10/U11 restoration is not needed. Set `GT1000_DESTRUCTIVE_EXTENDED=1` for slow multi-command/multi-slot patch-management coverage. Set `GT1000_ALLOW_GLOBAL_SETTINGS=1` only when intentionally testing System Control/global setting writes, in which case the suite backs up and restores System Control.
- Current proven commands:
  - `scripts/gt1000-agent --pretty patch apply default --live --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch apply 4cm-template --live --verify --timeout 20`
  - `scripts/gt1000-agent --pretty patch apply default --live --user-slot U10-1 --verify --timeout 30`
  - `scripts/gt1000-agent --pretty patch apply 4cm-template --live --user-slot U10-2 --verify --timeout 30`
  - `scripts/gt1000-agent --pretty patch set delay1 time 380 --live --user-slot U10-3 --verify --timeout 30`
  - `scripts/gt1000-agent --pretty patch clone U10-4 U11-1 --live --verify --timeout 30`

## Agent-Control Direction

- The long-term goal is to let an agent inspect and edit the GT-1000 safely from natural-language requests.
- Build toward this in layers: typed SysEx protocol definitions, decoded patch snapshots, human-readable signal-chain summaries, validated edit commands, then agent planning.
- The agent should not emit arbitrary SysEx directly. It should produce structured intents such as "set delay 1 time" or "enable tuner assign"; the Python CLI should validate ranges, addresses, and model-specific quirks before sending MIDI.

# MIDI / SysEx CLI Roadmap

Implementation and correctness plan for the non-audio GT-1000 CLI: CoreMIDI transport, SysEx assembly, patch/system reads, validated writes, and read-back verification. Audio lab builds on this layer ([audio-lab-roadmap.md](audio-lab-roadmap.md)).

**Status:** Gap-closure sprint **complete** (commit `ad23dd0`, 2026-06-10). Unit tests and live MIDI verification passed on connected hardware; audio live tests require the Python environment in [AGENTS.md](../AGENTS.md) → **Python Environment**.

**Related:** [agent-control-plan.md](agent-control-plan.md), [AGENTS.md](../AGENTS.md), [midi-reference/README.md](../skills/gt1000/references/midi-reference/README.md)

## Design principles

1. **Writes are validated before send** — typed builders in `patch_edit.py` / `system_edit.py`; no naked byte arrays from agents.
2. **Read-back verification is device-state confirmation** — `--verify` re-reads what landed on the unit; it is not a substitute for unit tests of encoders.
3. **Verification must be honest** — sampling or permissive compare rules are opt-in and reported in the result payload.
4. **Lenient reads report gaps** — partial snapshots must not look complete when required records failed.
5. **One CLI process** — `cli.lock` + sequential live MIDI; see AGENTS.md.

## Gap-closure sprint (2026-06-10)

Prioritized findings from a full CLI/MIDI review. All items below shipped in `ad23dd0` unless noted.

### P1 — Verification semantics (correctness)

| Item | Problem | Resolution |
|------|---------|------------|
| Assign verify sampling | `verify_plan_with_timeout` silently verified only two disabled-Assign edges on large templates | Verify **every** write by default; opt-in sampling via `GT1000_VERIFY_SAMPLE_ASSIGNS=1` with `sampledAssignVerification` in the result |
| Chain verify | Set-equality tail compare could accept wrong element counts | Multiset equality on utility-tail only; named `CHAIN_UTILITY_TAIL_VALUES`; `is_chain_write` matches `CHAIN_START` and user-slot remaps |
| Doctor write-check | Compared decoded patch level, not written bytes | Uses `apply_plan_cli(..., verify=True, exact_verify=True)` |
| Lenient slot reads | Required-record `CLIError` swallowed in `read_mapped_patch_snapshot_lenient` | Records `missingRequiredRecords`; `setlist-audit` surfaces **error** findings |

### P2 — Transport and decode (correctness)

| Item | Problem | Resolution |
|------|---------|------------|
| SysExAssembler | Real-time bytes (0xF8–0xFF) appended to SysEx buffer → checksum failures | Skip bytes `>= 0xF8` during assembly |
| `parse_data_set` | No device-ID check | Reject replies where `message[2] != DEVICE_ID` |
| Resident `isNamed` | Absolute Patch Effect offsets compared to slice-relative `rawParameters` | Rebase named offsets by `ResidentBlockDefinition.offset` |
| Env parsing | `GT1000_REQUEST_DELAY` / `GT1000_REQUEST_RETRIES` could throw | Safe fallbacks to defaults |
| `nibbles_for` | No overflow guard | Raise when value does not fit `byte_count` |
| Block lookup | Linear scan in hot path | `BLOCKS_BY_ADDRESS_KEY` map |

### P3 — Builders and record sizes (correctness)

| Item | Problem | Resolution |
|------|---------|------------|
| Assign active range | CC sources validated to 0…16383; device expects 0…127 | `is_midi_cc_assign_source()` limits ACT RANGE for CC source bytes 22…84 |
| Assign `isOnOff` | Encode/decode sets disagreed (`trigger`, `preampSw`) | Shared `ASSIGN_ON_OFF_PARAMETER_IDS` |
| Patch rename | Non-ASCII silently stripped | `validate_patch_name()` before `build_rename_plan()` |
| `inputs-set` level | Missing -20…+20 check in CLI coercion | `_coerce_inputs_set_value` range validation |
| PatchLed TSL import | Tone Studio may send 0x20 bytes; device record is 0x1E | `TSL_DEVICE_WRITE_SIZES` clamp on import |
| Master Delay size | `live.py` block size 28 vs parameters through offset 43 | Size **44** (0x2C per MIDI implementation; hardware-validated read) |
| Patch Effect size | Literal `[0x00,0x00,0x01,0x1C]` duplicated | `TEMPORARY_PATCH_EFFECT_SIZE` constant |
| EQ `geqLevel` | Same offset as `level` (0x0D) | Documented intentional alias per official PatchEq record |

**Assign target min/max:** inverted ranges (`target_min > target_max`) remain allowed — parameter guide documents reversed response.

**Assign switch on:** enabling still writes the 1-byte SW field only (preserves existing mapping); disabling writes full `DISABLED_ASSIGN_DATA`. Documented in `assign_switch_writes()`.

### P4 — Efficiency (non-blocking)

| Item | Problem | Resolution |
|------|---------|------------|
| Quiet wait | Fixed ~0.5s on silent bus before every read | `wait_for_quiet_input` early-exit after `initial_grace` when no packet seen |
| `system inputs` | One CoreMIDI session per input (×10) | Single `read_patch_records_with_timeout` batch |
| `level-audit` | Per-record sessions per slot | One lenient batch + Patch Effect retry only if missing |

### Agent environment (docs)

| Item | Problem | Resolution |
|------|---------|------------|
| Audio deps forgotten | Agents run `python3` without `sounddevice`/`numpy`; live tests skip and look green | **Python Environment** section in AGENTS.md + README Requirements pointer |

## Verification matrix

| Check | Command | When |
|-------|---------|------|
| Unit | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q` | Every MIDI/CLI change |
| Live MIDI | `GT1000_LIVE=1 … tests.test_live_skill -q` | Hardware connected; after transport/verify changes |
| Doctor | `scripts/gt1000-agent --pretty doctor --live --write-check --timeout 10` | After write/verify path changes |
| Audio live | See AGENTS.md **Python Environment**; `GT1000_AUDIO_LIVE=1` + `tests.test_live_audio_lab` | After audio-lab *or* shared `live.py` changes |

## Open / follow-up

| Priority | Item | Notes |
|----------|------|-------|
| P2 | More system/global typed writes | `common-set`, `midi-set`, `effects-set`, `pitch-set`, `setup-efct-set`, expanded `inout-set` shipped after `ad23dd0`; still open: manual-control-set, pcmap-set, MIDI CC assignment bytes, output EQ channel fields |
| P2 | STOMPBOX / `.stx` shared data | Musician-cli backlog |
| P3 | Further read batching (e.g. multi-slot export) | Profile before changing; large RQ1 pages still risky |
| P3 | Assign PDF alternate target table (991 vs 987) | Document and live-test per firmware; do not assume PDF-only table |
| Maint | Encoding evidence validation log | exact-read gate; expand hardware-validated field inventory |

## Implementation order (sprints)

| Sprint | Focus | Status |
|--------|-------|--------|
| A | P1 verification semantics | **done** (`ad23dd0`) |
| B | P2 transport + decode | **done** (`ad23dd0`) |
| C | P3 builders + record sizes | **done** (`ad23dd0`) |
| D | P4 read efficiency + agent Python env docs | **done** (`ad23dd0`) |

---

*Last updated: 2026-06-10*

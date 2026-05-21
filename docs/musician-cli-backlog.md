# Musician-Facing CLI Backlog

Build these in order. Prefer commands that answer practical rehearsal and gigging questions in musician language before exposing lower-level patch data.

1. [x] `patch performance`
   - One-screen performance layout for the current patch or saved patch data.
   - Show NUM/CTL/EXP actions, direct control functions, Assign overlays, tuner availability, and practical notes.

2. [x] `patch diff`
   - Compare two slots or files and explain meaningful musical differences.
   - Prioritize amp/effect type changes, block on/off state, delay/reverb/modulation settings, control assignments, BPM, and patch level.

3. [x] Automatic restore points and `patch undo-last`
   - Save a small restore point before every verified write.
   - Provide a direct undo command that restores and verifies the last changed ranges.

4. [x] Setlist audit
   - Read a bank or slot range and flag live-use risks: patch level jumps, BPM mismatches, missing tuner access, inconsistent EXP behavior, and unusual CTL mappings.

5. [x] Musician summary mode
   - Add a concise narrative description focused on tone, playable controls, and live-use intent.
   - Avoid raw data unless explicitly requested.

6. [ ] Patch level normalization helpers
   - Compare and adjust patch/master levels across slots with read-back verification.
   - Surface boosts and gain-stage changes that may affect perceived loudness.

7. [ ] Intent-based edits
   - Add commands such as solo boost, tap tempo, delay toggle, tuner mapping, and expression-volume setup.
   - Keep writes typed, validated, and read-back verified.

8. [ ] `doctor --live`
   - Report endpoint health, SysEx responsiveness, patch read health, user-slot read health, MIDI RX channel, and optional write/verify capability.

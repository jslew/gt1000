# GT-1000 User Profile Onboarding

Use this whenever `gt1000-profile.md` is missing, before any GT-1000 device read, patch summary, control explanation, recommendation, or edit planning. Also use it when the user asks to create/update remembered GT-1000 context.

## Profile Path

The profile location must be independent of any specific LLM harness. Read/write user-specific memory at the first usable path:

1. A profile path explicitly provided by the user.
2. `$GT1000_PROFILE_PATH`.
3. `$GT1000_PROFILE_DIR/gt1000-profile.md`.
4. A harness-provided persistent user memory/config directory, if the active agent environment exposes one, using `gt1000-profile.md` inside it.
5. `$XDG_CONFIG_HOME/gt1000/gt1000-profile.md`, or `~/.config/gt1000/gt1000-profile.md` when `XDG_CONFIG_HOME` is unset.
6. Legacy fallback only: `$CODEX_HOME/memories/gt1000-profile.md` or `~/.codex/memories/gt1000-profile.md`.

Create the parent directory if needed. Do not store this profile inside the reusable skill directory. If a legacy harness-specific profile is found, load it and copy it to the first usable harness-neutral path before continuing.

## When To Ask

Ask onboarding questions whenever no profile exists. Do not answer from generic assumptions first; establish the profile, write it locally, then continue with the user's GT-1000 request.

If the user provides enough profile context unprompted, skip the full interview and write a concise profile from what they gave. Ask only for missing details that materially affect the immediate task.

## Questions

Ask one compact set of questions, not a long interview:

1. How are you normally using the GT-1000: direct/FRFR, 4-cable method with an amp, in front of an amp, studio/interface, headphones, or mixed?
2. What amp, cab, monitors, or interface are usually connected, and which GT-1000 outputs matter most?
3. Should GT-1000 amp/cab/speaker simulation usually be on, off, or patch-dependent?
4. What are your main use cases and sounds: live, recording, practice, bass mode, clean platform, high gain, ambient, MIDI control, etc.?
5. What control preferences should patches respect: expression pedal, CTL switches, tuner access, tap tempo, external MIDI, looper, or anything to avoid?

## Write Format

Keep the profile short and factual. Use this shape:

```markdown
# GT-1000 User Profile

This is user-specific context for the `gt1000` skill. Treat it as plugged-in preference memory, not as general GT-1000 truth.

## Rig

- ...

## Output And Routing

- ...

## Tone And Patch Preferences

- ...

## Controls

- ...

## Default Advice Bias

- ...
```

## Update Rules

- Ask before overwriting an existing profile unless the user explicitly requested the update.
- Preserve existing details that do not conflict with the new information.
- If new information conflicts with old information, summarize the conflict and ask which should win.
- Treat the profile as preference context only; live patch/device state remains authoritative.

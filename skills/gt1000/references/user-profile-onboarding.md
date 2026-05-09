# GT-1000 User Profile Onboarding

Use this when `gt1000-profile.md` is missing or when the user asks to create/update remembered GT-1000 context.

## Profile Path

Write user-specific memory to the first usable path:

1. `$CODEX_HOME/memories/gt1000-profile.md`
2. `~/.codex/memories/gt1000-profile.md`

Create the `memories` directory if needed. Do not store this profile inside the reusable skill directory.

## When To Ask

Ask onboarding questions before rig-dependent recommendations, patch edit planning, or control-layout advice if no profile exists. For simple factual reads, answer first and offer onboarding only if it would improve future answers.

If the user provides enough profile context unprompted, skip questions and write a concise profile from what they gave. Ask only for missing details that materially affect the immediate task.

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

# Agent Workflows

Use this page when answering user questions about a connected GT-1000 v4+ unit.

## Describe A Patch

1. Read overview:

   ```sh
   scripts/gt1000-cli.sh read current-patch --view overview --format json --pretty --timeout 8
   ```

2. Read chain:

   ```sh
   scripts/gt1000-cli.sh read current-patch --view chain --format json --pretty --timeout 8
   ```

3. Read details only for blocks that matter to the question:

   ```sh
   scripts/gt1000-cli.sh read current-patch --view block --block delay1 --format json --pretty --timeout 8
   ```

4. Explain in human terms. Avoid listing every parameter unless asked.

## Explain Physical Switches

Current gap: there is not yet a first-class CLI controls view.

For now:

1. Read `PatchCommon`, `SystemControl`, and Assign 1-16 by direct SysEx or add CLI support.
2. Decode using [Patch Controls](../midi-reference/patch-controls.md).
3. Check Assign `SW` values using [Assigns](../midi-reference/assigns.md).
4. Explain direct control functions plus active Assign overlays.

## Plan A Patch Edit

1. Inspect current state progressively.
2. Identify the exact block and parameter.
3. Validate the requested value against the Parameter Guide and MIDI range.
4. Prefer structured intents such as `setEffectEnabled`, `setParameter`, or `setAssign`.
5. Do not emit arbitrary SysEx directly.
6. Ask before persistent patch write.

## Update The Wiki

1. Refresh scratch manuals:

   ```sh
   .agents/skills/gt1000-knowledge/scripts/fetch-current-manuals.sh /tmp/gt1000-manuals
   ```

2. Search extracted text:

   ```sh
   rg -n "SEARCH TERM" /tmp/gt1000-manuals/*.txt
   ```

3. Add concise, paraphrased wiki entries.
4. Link user-facing concepts to MIDI/CLI implementation paths.
5. Do not commit downloaded PDFs or full extracted manual text.


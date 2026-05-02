# Agent Workflows

Use this page when answering user questions about a connected GT-1000 v4+ unit.

## Describe A Patch

1. Read overview:

   ```sh
   scripts/gt1000-agent --pretty patch overview --live --timeout 8
   ```

2. Read chain:

   ```sh
   scripts/gt1000-agent --pretty patch chain --live --timeout 8
   ```

3. Read details only for blocks that matter to the question:

   ```sh
   scripts/gt1000-agent --pretty patch block delay1 --live --timeout 12
   ```

4. Explain `descriptionSignalChainSummary` in human terms. Avoid listing every parameter unless asked.

For human descriptions, omit switched-off blocks that have no decoded hardware/control assignment. They are still present in `elements` for raw inspection, but they are effectively absent from the playable signal chain. Include switched-off blocks when the chain data says they have a hardware/control assignment, because the player can bring them into the live sound. Do not name dormant blocks in the same answer unless the user asks for raw chain contents.

Run live reads sequentially. Avoid parallel `patch block --live` calls; the current SwiftPM/CoreMIDI execution path can contend on `.build` and time out. Start with `overview` and `chain`, then read only one or two block details if required.

When selecting a patch slot, verify the result by reading `overview`. Trust the live `patchName` over factory sound-list expectations; user slots can contain initialized or edited patches.

For an initialized/sparse patch, a good answer is concise: identify the live patch name, describe the audible/playable chain, and stop. Do not follow with a catalogue of off blocks.

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

Keep wiki/documentation search in this skill workflow. The CLI should report connected-device state and validated operations, not duplicate documentation retrieval.

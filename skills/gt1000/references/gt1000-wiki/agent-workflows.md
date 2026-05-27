# Agent Workflows

Use this page when answering user questions about a connected GT-1000 v4+ unit.

Command examples assume you have already resolved the bundled CLI wrapper as `$GT1000_AGENT` from the loaded skill directory. In installed skills, prefer the current project's `.agents/skills/gt1000/scripts/gt1000-agent` when it exists, and do not substitute a development checkout or repo-root wrapper after loading the project-installed skill. Do not run `scripts/gt1000-agent` relative to the user's current project unless that project is the skill directory.

## Describe A Patch

1. For a musician-facing current-patch description, read the compact musician summary first:

   ```sh
   $GT1000_AGENT --pretty patch musician-summary --live --timeout 15
   ```

2. For a persistent user slot, prefer the musician summary view first:

   ```sh
   $GT1000_AGENT --pretty patch slot U01-1 --live --view musician-summary --timeout 30
   ```

3. Read details only for blocks that matter to the question:

   ```sh
   $GT1000_AGENT --pretty patch block delay1 --live --timeout 15
   ```

4. Explain `descriptionSignalChainSummary` in human terms. Avoid listing every parameter unless asked.

For human descriptions, omit switched-off blocks that have no decoded hardware/control assignment. They are still present in `elements` for raw inspection, but they are effectively absent from the playable signal chain. Include switched-off blocks when the chain data says they have a hardware/control assignment, because the player can bring them into the live sound. Do not name dormant blocks in the same answer unless the user asks for raw chain contents.

Run live reads sequentially. Avoid parallel `patch block --live` calls and do not chain multiple live reads in one shell command, because separate processes can interleave GT-1000 replies on the same MIDI source. In Codex CLI, live reads must run outside the normal workspace/read-only sandbox because CoreMIDI can be blocked there; use yolo/`--dangerously-bypass-approvals-and-sandbox` or `-s danger-full-access`. For routine patch descriptions and normal "details of patch" requests, start with `musician-summary` only and answer from that result. Read `summary`, `chain`, or one or two block details afterward only when the user explicitly asks for deeper block/type detail or the first result lacks a fact needed to answer.

Use timeouts that match the scope of the read. `--timeout 8` is enough for port inventory and small system views, `--timeout 15` is the normal floor for focused current-patch reads, `--timeout 20` gives full current-patch summaries, audits, and normal temporary writes room to complete, and `--timeout 30` is appropriate for persistent slot/preset/bank summaries, clone/import/export/exchange/insert, or verified persistent writes. For bank and audit commands, the timeout is the per-slot or per-read allowance; total wall-clock time scales with the number of slots.

When selecting a patch slot, verify the result by reading `overview`. Trust the live `patchName` over factory sound-list expectations; user slots can contain initialized or edited patches.

For persistent user-slot inspection, prefer direct slot reads over program-change selection:

```sh
$GT1000_AGENT --pretty patch slot U01-1 --live --view musician-summary --timeout 30
$GT1000_AGENT --pretty patch bank U01 --live --view musician-summary --timeout 30
$GT1000_AGENT --pretty patch block delay1 --user-slot U01-1 --timeout 20
```

These commands read user patch memory by SysEx and do not change the selected patch. Use `patch bank` when comparing levels across U01...U50 banks.

For an initialized/sparse patch, a good answer is concise: identify the live patch name, describe the audible/playable chain, and stop. Do not follow with a catalogue of off blocks.

## Explain Physical Switches

1. Read `patch controls`, which includes direct PatchCommon/SystemControl functions and Assign 1-16 overlays.
2. Use [Patch Controls](../midi-reference/patch-controls.md) only if a raw function value is unclear.
3. Use [Assigns](../midi-reference/assigns.md) only if source IDs, target min/max encoding, or target-table caveats matter.
4. Explain direct control functions plus active Assign overlays.

For global troubleshooting, use the read-only system views:

```sh
$GT1000_AGENT --pretty system midi --live --timeout 8
$GT1000_AGENT --pretty system inout --live --timeout 8
$GT1000_AGENT --pretty system controls --live --timeout 8
```

## Plan A Patch Edit

1. Inspect current state progressively.
2. Identify the exact block and parameter.
3. Validate the requested value against the Parameter Guide and MIDI range.
4. Prefer structured CLI intents such as `patch enable`, `patch disable`, `patch set`, `patch type`, `patch move`, `patch assign-cc`, `patch set-bpm`, or `patch tuner-assign`.
5. Do not emit arbitrary SysEx directly.
6. Ask before persistent patch write.

## Update The Wiki

1. Refresh scratch manuals:

   ```sh
   scripts/fetch-current-manuals.sh /tmp/gt1000-manuals
   ```

2. Search extracted text:

   ```sh
   rg -n "SEARCH TERM" /tmp/gt1000-manuals/*.txt
   ```

3. Add concise, paraphrased wiki entries.
4. Link user-facing concepts to MIDI/CLI implementation paths.
5. Do not commit downloaded PDFs or full extracted manual text.

Keep wiki/documentation search in this skill workflow. The CLI should report connected-device state and validated operations, not duplicate documentation retrieval.

# CLI Usage (musician-facing quick reference)

This page is intentionally short and musician-oriented: it’s a quick reference to **what you can inspect and change** on a GT-1000 using the skill’s bundled CLI.

Developer / maintenance notes (diagnostics, test suites, encoding validation, recovery workflows) live in [`skills/gt1000/references/skill-developer.md`](../skill-developer.md).

The CLI is wrapped by:

```sh
$GT1000_AGENT
```

## Quick start (most common)

```sh
scripts/gt1000-agent --pretty ports --live --timeout 8
scripts/gt1000-agent --pretty patch musician-summary --live --timeout 15
scripts/gt1000-agent --pretty patch performance --live --timeout 15
scripts/gt1000-agent --pretty patch chain --live --timeout 15
```

## Timeouts (rule of thumb)

- `--timeout 8`: ports/system reads
- `--timeout 15`: focused current-patch reads (chain/controls/performance/musician-summary)
- `--timeout 20`: bigger current-patch reads + verified temporary edits
- `--timeout 30`: user-slot reads/writes + multi-slot librarian operations

## Musician workflows

### Understand what a patch does

```sh
scripts/gt1000-agent --pretty patch musician-summary --live --timeout 15
scripts/gt1000-agent --pretty patch performance --live --timeout 15
scripts/gt1000-agent --pretty patch chain --live --timeout 15
scripts/gt1000-agent --pretty patch controls --live --timeout 15
```

### Compare / audit patches (setlist prep)

```sh
scripts/gt1000-agent --pretty patch diff U10-1 U10-2 --live --timeout 30
scripts/gt1000-agent --pretty patch setlist-audit U10 --live --timeout 20
scripts/gt1000-agent --pretty patch level-audit U10 --live --timeout 20
```

### Safe “tidy” chain edit

```sh
scripts/gt1000-agent --pretty patch cleanup --live --verify --timeout 20
scripts/gt1000-agent --pretty patch cleanup --live --user-slot U10-1 --verify --timeout 30
```

### Common edits (temporary or persistent)

```sh
scripts/gt1000-agent --pretty patch enable delay1 --live --verify --timeout 20
scripts/gt1000-agent --pretty patch disable dist1 --live --verify --timeout 20
scripts/gt1000-agent --pretty patch move delay1 --before chorus --live --verify --timeout 20
scripts/gt1000-agent --pretty patch set-bpm 120.0 --live --verify --timeout 20
scripts/gt1000-agent --pretty patch master-set level 95 --live --verify --timeout 20
```

Add `--user-slot Uxx-y --timeout 30` to make the change persistent.

## Complete command surface (advanced)

This section exists so the repo can sanity-check that the command surface is documented; most musicians can ignore it.

- `ports`
- `audio ports`, `audio generate-tone`, `audio record-dry`, `audio reamp`, `audio analyze`, `audio analyze-trimmed`, `audio session init`, `audio session render`, `audio branch-context`, `audio compare-branches`, `audio probe-branch`, `audio probe-param`, `audio render-branch`
- `doctor`
- `midi cc`, `midi pc`, `midi bank-select`
- `system common`, `system midi`, `system pcmap`, `system inputs`, `system inout`, `system inout-set`, `system effects`, `system pitch`, `system controls`, `system manual`
- `patch overview`, `patch musician-summary`, `patch performance`, `patch chain`, `patch controls`, `patch summary`
- `patch slot`, `patch bank`, `patch preset`
- `patch diff`, `patch setlist-audit`, `patch level-audit`
- `patch normalize-levels`
- `patch select`
- `patch block`, `patch stompbox`, `patch dump`, `patch inspect`
- `patch initialize`, `patch clear`, `patch batch-initialize`, `patch rename`
- `patch move`, `patch cleanup`
- `patch enable`, `patch disable`, `patch type`, `patch set`, `patch raw-set`, `patch set-bpm`, `patch master-set`
- `patch control-set`, `patch system-control-set`, `patch control-preference-set`, `patch led-set`
- `patch assign-cc`, `patch assign-set`, `patch tuner-assign`
- `patch intent`
- `patch plan`, `patch apply`
- `patch undo-last`
- `patch clone`, `patch copy`, `patch exchange`, `patch insert`, `patch batch-copy`
- `patch export`, `patch import`
- `patch tsl-export`, `patch tsl-list`, `patch tsl-import`
- `patch liveset-list`, `patch liveset-move`, `patch liveset-copy`, `patch liveset-rename`, `patch liveset-remove`
- `patch restore-preset`
- `patch schema`, `patch encoding-status`, `patch validate-encoding`, `patch validate-encoding-batch`, `patch validate-encoding-scope`

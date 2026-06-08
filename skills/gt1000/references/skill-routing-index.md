# GT-1000 skill routing index

Canonical map from **user intent** → **first CLI** → **reference file**. The routing card is `SKILL.md` (always loaded on skill activation). Load other files only when this index or the card says to.

**Do not** `grep`/`cat` reference trees; open the one file named here.

**Live MIDI:** before any `--live` CLI, read `SKILL.md` → **One CLI at a time (critical)**. Never run two `gt1000-agent` processes concurrently; the CLI enforces this with a process lock.

## File registry

Every bundled reference markdown file is listed below. `tests/test_skill_routing.py` fails if a new file under `references/` is not registered.

| File | Load when |
|------|-----------|
| `references/skill-routing-index.md` | Task routing and this registry (you are here) |
| `references/skill-detail.md` | Timeouts, progressive disclosure, command catalogs, edit/description/controls workflows, expanded safety |
| `references/skill-audio-setup.md` | Before the first USB audio lab command in an environment |
| `references/skill-routing-eval.md` | Scoring agent traces against routing scenarios (CI + transcript replay) |
| `references/skill-developer.md` | Maintaining the CLI/skill: diagnostics, encoding validation, test commands (not musician tasks) |
| `references/user-profile-onboarding.md` | No `gt1000-profile.md` yet; creating or updating profile memory |
| `references/audio-lab-investigation.md` | USB re-amp quantitative experiments (agent-owned loop) |
| `references/audio-lab-investigation-verification.md` | Verifying investigation behavior / regression checklist |
| `references/gt1000-wiki/README.md` | Wiki overview; which manual extract to open next |
| `references/gt1000-wiki/owner-manual.md` | Owner-manual concepts (STOMPBOX caution, divider behavior, device UI) |
| `references/gt1000-wiki/parameter-guide.md` | Parameter meaning, block categories, in/out and USB menu context |
| `references/gt1000-wiki/input-level-gain-staging.md` | Input level presets, gain staging, thin/weak/harsh tone vs pickups and output select |
| `references/gt1000-wiki/input-level-calibration.md` | Agent workflow: calibrate global input preset for an instrument and save/name it |
| `references/gt1000-wiki/sound-list.md` | Factory/model sound names and categories |
| `references/gt1000-wiki/agent-workflows.md` | Multi-step agent examples beyond one-shot patch Q&A |
| `references/gt1000-wiki/usb-audio.md` | USB channel map, routing, re-amp troubleshooting beyond setup |
| `references/gt1000-wiki/sources.md` | Wiki provenance and manual versions |
| `references/midi-reference/README.md` | SysEx/MIDI index; which low-level page to open |
| `references/midi-reference/cli-usage.md` | CLI surface, flags, write guardrails |
| `references/midi-reference/patch-effect.md` | PatchEfct chain, routing offsets, BPM encoding |
| `references/midi-reference/patch-controls.md` | Physical control and Assign decoding |
| `references/midi-reference/assigns.md` | Assign source IDs, target encoding, tuner/CC quirks |
| `references/midi-reference/address-map.md` | System/patch addresses, sizes, encoding validation |

## Intent routing (first CLI → escalate)

| User intent | First authoritative CLI | Escalate reference |
|-------------|---------------------------|-------------------|
| Describe current patch | `patch musician-summary --live --timeout 15` | `skill-detail.md`; then `patch chain` / `patch summary` if gap remains |
| Describe user slot | `patch slot <slot> --live --view musician-summary --timeout 30` | `skill-detail.md`; `patch block` for one block |
| What is active / reachable now | `patch chain --live --timeout 15` | `midi-reference/patch-effect.md` if raw routing unclear |
| Compare patches | `patch diff <a> <b> --live --timeout 30` | `skill-detail.md` |
| Setlist readiness | `patch setlist-audit <slots> --live --timeout 20` | — |
| Patch level across slots | `patch level-audit` then `patch normalize-levels` | `skill-detail.md` |
| Divider / branch measurable balance | `audio branch-context`; then investigation doc | `audio-lab-investigation.md` |
| Reference tone match / tone chase | Audio lab reference workflow; agent runs profile, plan, render/rank internally | `skill-detail.md` |
| Solo boost, delay toggle, tuner, etc. | `patch intent <name> --live --verify` | `midi-reference/cli-usage.md` |
| Switches / stage behavior | `patch performance --live --timeout 15` | `patch-controls.md` |
| Assign / CC / tuner encoding | `patch controls --live --timeout 15` | `assigns.md` |
| Install tuner on control | `patch tuner-assign --live --verify` | `assigns.md` |
| Select user slot on unit | `patch select <slot>` | `midi pc` only if user asks PC numbers |
| Signal chain / divider / mixer detail | `patch chain` or `patch summary` | `patch-effect.md` |
| STOMPBOX shared slots | `patch stompbox --live` | `owner-manual.md` |
| System MIDI / global | `system midi`, `system inout`, etc. | `midi-reference/README.md`, `address-map.md` |
| Connection / timeouts | `doctor --live`; then `ports --live --timeout 8` | `skill-detail.md` recovery |
| Metronome BPM (system) | `system common --live` | `address-map.md` |
| Manual-mode switches | `system manual --live` | `address-map.md` |
| Program Change map | `system pcmap --live --bank N` | `address-map.md` |
| Input level, gain staging, thin/weak/harsh tone | `system inputs --live --number N`; then `system inout --live`; `patch musician-summary --live` if block levels suspect | `gt1000-wiki/input-level-gain-staging.md` |
| Calibrate / save global input preset for a guitar | `system inputs --live --number N`; then workflow doc (`inputs-set` after persist approval) | `gt1000-wiki/input-level-calibration.md` |
| Input settings (compare all ten presets) | `system inputs --live` | `input-level-gain-staging.md` |
| Wrong output into amp/PA/phones | `system inout --live` | `input-level-gain-staging.md`; `parameter-guide.md` |
| Parameter meaning | `patch block <id> --live` | One `gt1000-wiki/` page from README |
| Block on/off | `patch enable` / `patch disable --verify` | `cli-usage.md` |
| Effect type change | `patch type <block> <type> --verify` | — |
| Move block in chain | `patch move` (after `patch chain` if order unclear) | `patch-effect.md` |
| Cleanup unreachable blocks | `patch cleanup --live --verify` | — |
| Map parameter to CC | `patch assign-cc … --verify` | `assigns.md` |
| Patch BPM | `patch set-bpm --verify` | `patch-effect.md` if encoding asked |
| Validated plan / template write | `patch plan` then `patch apply --verify` | `skill-detail.md` |
| Typed parameter write | `patch set <block> <param> <value> --verify` | `address-map.md` for validator gaps |
| USB audio first use | `skill-audio-setup.md` then `audio ports` | `usb-audio.md` |
| CLI maintenance / tests | `skill-developer.md` | Repo `AGENTS.md` |

Full escalation bullets: `references/skill-detail.md` § Progressive Disclosure Routing.

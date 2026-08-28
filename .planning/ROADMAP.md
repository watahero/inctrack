# Roadmap: inctrack v1.2.0 — correctness and cost

## Overview

This is a quality milestone on shipped code (v1.1.0), not a build. The addon
works and is in daily use; an audit found three defects visible in the code as
written, a set of fragile paths, and a per-line cost paid on every chat line the
client receives. The ordering is deliberate and is the whole argument of the
milestone: **all three defects survived a fully green test suite**, so the net is
built first (Phase 1), the defects are then killed with tests that were red
before them (Phase 2), the fragile paths are hardened once there is coverage to
notice a mistake (Phase 3), and only then is the hot path made cheaper and the
project's own documents brought back into agreement with what ships (Phase 4).

"Done" for every phase means `python test/run_tests.py <chatlogs>` passes against
the author's 126 logs. There is no build step and no package manager; install is
a folder copy.

## Standing guarantee (whole milestone)

Every phase must leave these true, and each phase's verification restates them:

- The full suite is green against the author's chatlogs at
  `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs` — baseline 2026-08-28 is
  **12,841 checks, 8 suites, 2,943,169 chat lines from 126 logs**. Check counts
  may only go up.
- Suite 2 still holds: **no generic-tier pattern matches anything in today's
  logs.** A generic hit means a specific pattern regressed.
- The purity boundary holds: `parser.lua` and `state.lua` gain no Ashita
  dependency. Stubs live in the harness, never in the addon.
- No instance, boss, mob, objective or difficulty name appears in any Lua file.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: The Net** - Bring `ui.lua` and `inctrack.lua` under test behind stubs, and turn each confirmed defect into a named failing test
- [ ] **Phase 2: The Three Defects** - Kill the double-counted phase, the un-aged restore and the dead close path, flipping Phase 1's red tests green
- [ ] **Phase 3: Fragile Paths** - Make the render path un-crashable and stop the parser and restore path from admitting things the server never said
- [ ] **Phase 4: Cost and Record** - Reject an irrelevant chat line before paying for it, get settings writes off the chat thread, and make the docs describe the addon that ships

## Phase Details

### Phase 1: The Net
**Goal**: The suite can reach the two files it has never reached, and each confirmed defect is visible as a named failing test rather than a claim in an audit document.
**Depends on**: Nothing (first phase)
**Requirements**: COVR-01, COVR-02, COVR-03, COVR-04
**Success Criteria** (what must be TRUE):
  1. `python test/run_tests.py` loads the shipped `inctrack/ui.lua` against an ImGui stub in the harness and asserts, for a given run record, the draw calls, colours and text produced — including the pure helpers (`clock_str`, `right_text`, `wrapped`, `bar`, `urgency`, `replace_plain`, `shorten`) and the longest-phrase-first ordering contract of `STAT_SHORT`.
  2. The same run loads the shipped `inctrack/inctrack.lua` against an Ashita stub (`addon`, `ashita.events`, `AshitaCore`, `settings`, `common`, `chat`, `json`) and exercises event registration, the `text_in` handler and its `pcall` boundary, settings load/save and the `MUST_SAVE` throttle, the `/incursion` command with `reset` / `lock` / `auto` / bare toggle / usage, `visible()`'s override-vs-auto logic, and the profile-switch handler.
  3. On a machine with **no chatlogs directory and no Ashita install**, `python test/run_tests.py` runs the two new suites to completion and reports a non-zero check count for each — the report header still reads `chatlogs: none`, and coverage of shipped behaviour is not gated on private data.
  4. The failure list from a full run is **exactly three entries**, one each for FIX-01, FIX-02 and FIX-03, each named in user terms (e.g. "counted a bonus payout as a cleared phase"). No previously-green suite regresses, and the pre-existing check count does not fall.
  5. The addon source is unchanged by this phase — `git diff` over `inctrack/` is empty.
**Plans**: TBD (3 expected)

### Phase 2: The Three Defects
**Goal**: The three faults visible in the code as written are gone, and the tests that were red before them are green — demonstrated, not asserted.
**Depends on**: Phase 1 (the three regression tests must exist and be red first)
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):
  1. The three regression tests written in Phase 1 now pass **without their assertions being edited** — a diff of `test/run_tests.py` over this phase touches no assertion text written in Phase 1.
  2. A points award that was not caused by a boss kill — a bonus payout, a chest, a completion bonus — leaves `Phases cleared` unchanged; a boss kill raises it by exactly one. `phases_cleared` has a single author in `state.lua`, not the two at `:198-202` and `:358-365`.
  3. A serialise/restore round trip across a simulated 10-minute gap shows `time_left`, elapsed and the bonus countdown all moved by that gap: `time_left` is 600s lower, and a bonus with under 600s remaining is dropped rather than shown. `saved_at` is the correction term.
  4. In game: `/addon reload inctrack` mid-run leaves the instance clock agreeing with the next `You have N minutes remaining` line the server sends, instead of being optimistic by the downtime.
  5. No unreachable close affordance remains — either clicking a close control hides the window, or `grep` finds no `ARG_OPEN` plumbing in `ui.lua` and no `shown == false` branch in `inctrack.lua`.
**Plans**: TBD (2 expected)

**Coverage note carried into planning:** suite 3 currently asserts
`phases_cleared == number of points events`, an independent recomputation that
encodes the very defect FIX-01 removes. Fixing FIX-01 will make suite 3 fail
until its recomputation is re-derived from boss kills rather than points awards.
That re-derivation is part of this phase, not a regression.

### Phase 3: Fragile Paths
**Goal**: The window cannot take the frame down, and neither the parser nor the restore path can put on screen something the server never said.
**Depends on**: Phase 1 (the ImGui and Ashita stubs)
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04, HARD-05, HARD-06
**Success Criteria** (what must be TRUE):
  1. A run record that errors mid-render — a non-string in `objective.mobs`, a `%` in a server-supplied instance name — leaves the ImGui stack balanced: the stub records equal `Begin`/`End` and `PushStyleVar`/`PopStyleVar` counts. The failure is reported once and the window disables itself, rather than recurring sixty times a second inside `d3d_present`.
  2. A boss objective naming a mob whose own name contains " at " parses with the full name intact and the parenthesised location separate; a mob list containing a comma-bearing name yields one mob, not two phantom entries.
  3. An ordinary buff line is never claimed as a boon — a line without the `(<glyph>): <stats>` tail produces no boon event — while suite 4's existing boon assertions (recognition, dedup, other players ignored, cleared by a new run) all still pass.
  4. A structurally malformed saved session — a string where `kills_max` belongs, a number inside `objective.mobs` — is discarded whole: `restore()` returns falsy and leaves no run behind, so nothing of that shape ever reaches arithmetic in `ui.lua`.
  5. `/incursion reset` within 30 seconds of a `You have N minutes remaining` line does not seed the next run's clock — `pending_time` is nil after `reset()`.
**Plans**: TBD (3 expected)

### Phase 4: Cost and Record
**Goal**: A chat line the addon does not care about costs measurably less than it did, saving no longer blocks the chat thread, and the project's own documents describe the addon that actually ships.
**Depends on**: Phase 3 (the benchmark baseline must be taken against final parser behaviour, and `docs/design.md` can only be corrected once behaviour is settled)
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):
  1. The harness prints a per-line cost figure — lines/second through the reject path over a fixed corpus — for a recorded pre-change baseline and for the post-change code, and the post-change figure is lower. The improvement is a printed number in the test report, not a claim.
  2. A chat line that is not Incursion-related is rejected before any string is allocated for it: the Ashita stub records zero `strip_colors` calls for such lines, `trim` does not run, and the timestamp loop does not run unless the line starts with `[`.
  3. A burst of `MUST_SAVE` events performs no `settings.save` inline on the chat thread — the stub records the writes happening from the per-frame flush instead — and no run data is lost across a simulated unload immediately after such a burst.
  4. `shorten()`'s memo cache stops growing at a stated bound when fed a stream of distinct server stat strings, and holds nothing from a previous run after a reset or character switch.
  5. `docs/design.md` states what the code does: `AlwaysAutoResize` plus a fixed-width spacer, `NoTitleBar`, the actual stats layout (points tracked, not displayed), the boons row, and the `elapsed_final` / `desynced` / `recovered` / `points_partial` / `bonus.loc` run-record fields. `CHANGELOG.md` has a 1.2.0 entry naming what changed, and `addon.version` in `inctrack/inctrack.lua` reads `'1.2.0'`.
**Plans**: TBD (3 expected)

## Requirement Coverage

| Requirement | Phase |
|-------------|-------|
| COVR-01 | Phase 1 |
| COVR-02 | Phase 1 |
| COVR-03 | Phase 1 |
| COVR-04 | Phase 1 |
| FIX-01 | Phase 2 |
| FIX-02 | Phase 2 |
| FIX-03 | Phase 2 |
| HARD-01 | Phase 3 |
| HARD-02 | Phase 3 |
| HARD-03 | Phase 3 |
| HARD-04 | Phase 3 |
| HARD-05 | Phase 3 |
| HARD-06 | Phase 3 |
| PERF-01 | Phase 4 |
| PERF-02 | Phase 4 |
| PERF-03 | Phase 4 |
| PERF-04 | Phase 4 |
| DOC-01 | Phase 4 |
| DOC-02 | Phase 4 |

**19 of 19 v1 requirements mapped. No orphans, no duplicates.**

## Notes

**No UI hint on any phase.** Phases 1 and 3 touch `ui.lua` and ImGui, but no
phase changes what the window looks like — new HUD features are explicitly out of
scope for this milestone, and the UI work here is test coverage (Phase 1) and
error containment (Phase 3). A UI design contract would have nothing to specify.

**Verification environment** (required for any phase's exit check):
- Chatlogs: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs` (126 logs)
- Ashita `json.lua`: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\json.lua` (suite 8)
- `lupa` 2.8 on Python 3.14.5
- Live deployment at `...\Ashita\addons\inctrack\` for in-game checks

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. The Net | 0/TBD | Not started | - |
| 2. The Three Defects | 0/TBD | Not started | - |
| 3. Fragile Paths | 0/TBD | Not started | - |
| 4. Cost and Record | 0/TBD | Not started | - |

---
*Roadmap created: 2026-08-29*

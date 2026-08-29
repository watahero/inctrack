---
gsd_state_version: 1.0
milestone: v1.2.0
milestone_name: correctness and cost
current_phase: 3
current_phase_name: Fragile Paths
status: executing
stopped_at: Completed 03-01-PLAN.md -- HARD-01 closed, 13,037 checks over 127 logs, zero known defects
last_updated: "2026-08-29T05:03:41.420Z"
last_activity: 2026-08-29
last_activity_desc: "02-01 complete: FIX-01 and FIX-02 fixed in state.lua; one xfail (FIX-03) remains"
state_head: 6508d0b47a7830dc337ba20f2074e56755ca7b4f
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 8
  completed_plans: 6
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-28)

**Core value:** What the window shows is either true, or visibly marked as unconfirmed — never quietly wrong.
**Current focus:** Phase 3 — Fragile Paths

## Current Position

Phase: 3 of 4 (Fragile Paths)
Plan: 1 of 3 in current phase
Status: 03-01 complete (HARD-01) — 03-02 (HARD-02/03/04) is next
Last activity: 2026-08-29 — 03-01 complete: ui.render is contained in d3d_present with a conditional stack repair, a report-once latch and two recovery paths; addon suite 83 → 112 checks, both negative controls demonstrated

Progress: [███░░░░░░░] 33% of phase 3 (1 of 3 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 23min | 3 tasks | 2 files |
| Phase 01 P02 | 21min | 3 tasks | 1 files |
| Phase 01 P03 | 16min | 3 tasks | 1 files |
| Phase 02 P01 | 16min | 3 tasks | 2 files |
| Phase 02 P02 | 22min | 3 tasks | 3 files |
| Phase 03 P01 | 29min | 3 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Milestone: Coverage before fixes — all three confirmed defects survived a fully green suite, so without new tests a fix can only be asserted, never demonstrated
- Milestone: Scope is code plus test coverage; CI, linter and release artifact deferred to v2 (PROC-01..04)
- Roadmap: No UI hint on any phase — `ui.lua` work is coverage and error containment, not visual change
- [Phase 1]: 01-01: make_host() builds a fresh lupa runtime per call; make_lua()'s shared runtime and the eight existing suites are left untouched
- [Phase 1]: 01-01: addon file-scope locals are reached by upvalue reflection (lua_locals), never by exporting them from the addon
- [Phase 1]: 01-01: report markers 'XFAIL ' and 'NOW PASSING ' are a cross-plan contract grepped from stdout; nothing else the harness prints may contain either substring
- [Phase 1]: 01-01: the stubbed json decoder scans character by character and never evaluates its input, so {a=1} raises (T-01-01)
- [Phase 1]: 01-02: ui.lua helper tests read CONTENT_W and origin_x through lua_locals rather than copying them, so right-alignment assertions keep tracking the addon
- [Phase 1]: 01-02: defect assertions are disjunctions over observable call shape, so FIX-03 goes green under either Phase-2 fix without the assertion being edited
- [Phase 1]: 01-02: whole-window snapshots are inline expected strings reviewed against ui.lua's own layout comment before being pasted in — a captured-but-unreviewed snapshot only pins what the code happens to do
- [Phase 1]: 01-03: the addon-shell suite drives inctrack.lua only through its registered handlers; host.addon is used to read file-scope state, never as an entry point
- [Phase 1]: 01-03: the text_in pcall boundary is forced with a Lua table as e.message — a number coerces through the string metatable and the test would assert nothing
- [Phase 1]: 01-03: FIX-01 and FIX-02 are written as deltas and tolerances, never absolute expected values, so Phase 2 flips all three xfails green without editing an assertion
- [Phase 1]: 01-03: EXPECTED_XFAILS plus a main() guard summed across every suite; the guard's own output contains neither report marker, and it was proven by flipping the constant to 2 (exit 1)
- [Phase 2]: 02-01: the phase line and the completion are the only authors of phases_cleared; the points handler advances a new awards_seen counter instead
- [Phase 2]: 02-01: points_partial is judged against awards actually witnessed, not against whether the count moved -- the count now moves on every ordinary phase transition
- [Phase 2]: 02-01: restore()'s wall-clock gap is clamped at zero, so a saved_at stamped in the future is inert rather than generous (T-02-01)
- [Phase 2]: 02-01: byte-identity of a converted xfail is proven by /tmp/inctrack-assert-integrity.py against baseline b8a19fa, with a negative control run before the verdict is trusted
- [Phase 2]: The close plumbing was removed rather than the title bar restored -- the compact 1.1.0 layout is a shipped feature, and the ImGui stub has only the fourteen entry points ui.lua already uses
- [Phase 2]: ui.render keeps returning opts.visible unconditionally; two untouchable Phase-1 assertions read that return value
- [Phase 2]: A disjunctive red line is retired with a companion check pinning which branch the fix took, so the other branch cannot satisfy it later
- [Phase 2]: The recorder's close switch stays although it can no longer fire: it is the subject of the FIX-03 regression check, not dead weight
- [Phase 3]: 03-01: the pcall goes in inctrack.lua's frame handler; ui.lua is not edited at all -- the host boundary lives beside the text_in pcall
- [Phase 3]: 03-01: the ImGui stack repair is conditional on render_ok (the render shape having run end to end on this host once) -- three statements run before Begin, so an unconditional End is an unmatched close and on a real host the second error of the frame
- [Phase 3]: 03-01: the style colour stack is deliberately not repaired (its only push/pop bracket one ImGui call with no raise site between); the suite asserts all three stacks anyway so a future change goes red rather than being papered over
- [Phase 3]: 03-01: the bare /incursion while render_off is a re-enable and a return to automatic visibility, not a toggle -- toggling against a window that is not drawn reads as 'hide it'
- [Phase 3]: 03-01: the recorder's fault injector models the consequence of a raising ImGui binding on demand and never asserts the cause; off by default, disarmed by reset(), and stack-moving entry points raise before they are logged

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: RESOLVED in 02-01. Suite 3's cross-check is re-derived from the raw log's highest `Phase #N` plus the completion (degenerate no-phase-line case reads 1), computed from `active` alone. All 888 verified runs pass; the check count did not move.
- [All phases]: The deep suites need the author's private chatlogs and a local Ashita install. A green run without the `chatlogs:` header line is partial, not passing.
- [Phase 1]: Stubs for ImGui and the Ashita host must live in `test/`, never in the addon — the purity boundary is what makes the suite reach the code at all.
- [Phase 1]: the 12,841-check baseline is stale by 20. The full run now reports 12,821 from 127 logs; the UNMODIFIED pre-plan harness gives the identical per-suite counts on the same data, so this is chatlog input drift, not a regression. Hold per-suite counts constant rather than the sum. (01-02: the sum is now 12,874 — above the literal figure again — with all eight pre-existing per-suite counts unchanged. Keep reading the criterion as "no suite went down".)
- [Phase 2]: FIX-01 and FIX-02 are done (02-01) — both converted to `res.check` with their Phase-1 condition and message bytes proven identical by `/tmp/inctrack-assert-integrity.py` (source reproduced verbatim in 02-01-SUMMARY.md; add "FIX-03" to its `AUDITED` tuple in 02-02). One expected failure is left: FIX-03, in the ui suite. `EXPECTED_XFAILS` is 1 and `EXPECTED_DEFECTS` is `{"FIX-03"}`; 02-02's fix must update both in the same commit or the guard fails the run.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-08-29T05:03:41.221Z
Stopped at: Completed 03-01-PLAN.md -- HARD-01 closed, 13,037 checks over 127 logs, zero known defects
Resume file: None

## Deferred Verification

Both items are in-game checks no test suite can close. The user chose to carry on
to Phases 3-4 rather than pause; neither blocks that work.

| Phase | State | Resume |
|-------|-------|--------|
| 2 | verification_deferred_human | /gsd-verify-work 2 |

- **Criterion 4 - the reload clock.** In an Incursion: note the window's clock,
  `/addon reload inctrack`, stay unloaded ~2 min, reload and read the clock, then
  wait for the server's next `You have N minutes remaining` line. PASS if they
  agree within a minute. FAIL if the clock came back unchanged, or jumps down by
  roughly the downtime when the server's line arrives.

- **CR-01 - the window frame.** Same session: no title bar and no close control;
  not resizable by dragging an edge; height still auto-fits as content changes;
  `/incursion lock` still prevents dragging; `/incursion` still toggles. FAIL on
  any title bar, any resize handle, a clipped or padded fixed height, or a
  per-frame console error mentioning `bad argument #2` / `Begin`.

  This one exists because CR-01's fix rests on Ashita's SDK header and a survey of
  220 `imgui.Begin(` call sites, not on an observed frame. The compiled binding's
  type handling cannot be inspected, so only a rendered window proves the flags land.

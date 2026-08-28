---
gsd_state_version: 1.0
milestone: v1.2.0
milestone_name: correctness and cost
current_phase: 1
current_phase_name: The Net
status: planning
stopped_at: Completed 01-03-PLAN.md
last_updated: "2026-08-28T21:48:41.571Z"
last_activity: 2026-08-29
last_activity_desc: Roadmap created; 19 v1 requirements mapped across 4 phases
state_head: 103c2f3aa954b4e07ca3aa9d14f19b451f4c6e78
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 3
  completed_plans: 3
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-28)

**Core value:** What the window shows is either true, or visibly marked as unconfirmed — never quietly wrong.
**Current focus:** Phase 1 — The Net

## Current Position

Phase: 1 of 4 (The Net)
Plan: 3 of 3 in current phase
Status: Ready for verification — all 3 plans of phase 1 complete
Last activity: 2026-08-29 — 01-03 complete: addon shell suite (81 checks), FIX-01 and FIX-02 xfails, the exactly-three guard

Progress: [██████████] 100% of phase 1 (3 of 3 plans)

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: Suite 3 asserts `phases_cleared == number of points events`, which encodes the FIX-01 defect. Fixing FIX-01 makes suite 3 red until its independent recomputation is re-derived from boss kills. Expected, not a regression.
- [All phases]: The deep suites need the author's private chatlogs and a local Ashita install. A green run without the `chatlogs:` header line is partial, not passing.
- [Phase 1]: Stubs for ImGui and the Ashita host must live in `test/`, never in the addon — the purity boundary is what makes the suite reach the code at all.
- [Phase 1]: the 12,841-check baseline is stale by 20. The full run now reports 12,821 from 127 logs; the UNMODIFIED pre-plan harness gives the identical per-suite counts on the same data, so this is chatlog input drift, not a regression. Hold per-suite counts constant rather than the sum. (01-02: the sum is now 12,874 — above the literal figure again — with all eight pre-existing per-suite counts unchanged. Keep reading the criterion as "no suite went down".)
- [Phase 2]: all three expected failures must be flipped green WITHOUT editing their res.xfail conditions or messages; each fix must also decrement EXPECTED_XFAILS in the same commit or the guard fails the run. Locations: test/run_tests.py:654 (FIX-01), :707 (FIX-02), :1773 (FIX-03).

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-08-28T21:48:26.020Z
Stopped at: Completed 01-03-PLAN.md
Resume file: None

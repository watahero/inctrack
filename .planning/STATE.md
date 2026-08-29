---
gsd_state_version: 1.0
milestone: v1.2.0
milestone_name: correctness and cost
current_phase: 4
current_phase_name: Cost and Record
status: executing
stopped_at: Completed 04-01-PLAN.md
last_updated: "2026-08-29T08:35:00.639Z"
last_activity: 2026-08-29
last_activity_desc: "04-01 complete: parser.relevant gates the hot path before any allocation (needle derivation re-derived and checked over 2.95M lines, zero parsed lines gated out); reject path 3.5-5x with zero allocations; parse-error line got a report-once latch; three negative controls recorded"
state_head: 6b60dc48111e1d03a6afdc2d943ea89aba9fc0d6
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 11
  completed_plans: 9
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-28)

**Core value:** What the window shows is either true, or visibly marked as unconfirmed — never quietly wrong.
**Current focus:** Phase 4 — Cost and Record

## Current Position

Phase: 4 of 4 (Cost and Record)
Plan: 1 of 3 in current phase
Status: 04-01 complete (PERF-01, PERF-04) — 04-02 (PERF-02, PERF-03) is next
Last activity: 2026-08-29 — 04-01 complete: PERF-01's cheap gate lands before strip_colors (seven plain needles, each a literal every matcher requires under every alternation and optional group, re-derived from parser.lua and checked over 2,951,129 log lines with zero parsed lines gated out); a colour-code marker byte makes the gate decline to judge, so a false negative is impossible; PERF-04's benchmark prints the head-of-phase baseline (285,562 lines/s, 3.502 us/line) beside the shipped figure every run; adaptability 42 → 119, addon 143 → 160, parser still exactly 11819 and generic exactly 1; three negative controls recorded

Progress: [███░░░░░░░] 25% of phase 4 (1 of 3 plans)

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
| Phase 3 P02 | 1h | 3 tasks | 2 files |
| Phase 03 P03 | 16min | 3 tasks | 2 files |
| Phase 04 P01 | 40min | 3 tasks | 4 files |

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
- [Phase 3]: HARD-02: the location is the anchor, not the name -- a parenthesised trailing group is structurally identifiable and the name is whatever precedes it, so no list of names is needed
- [Phase 3]: HARD-02 keeps the 1.1.0 shape as a fallback at all three call sites; HARD-03 and HARD-04 keep none and rest on the survey plus the exact-11819 and exact-1 pins
- [Phase 3]: Families 2 and 3 of the corpus over-reach guard cannot bite on today's corpus and are recorded as guarding future lines, not present ones
- [Phase 3]: HARD-05: a file-local structural validator runs after the version gate and before any field is read for its value; it rejects rather than coerces and discards a malformed session whole rather than half-applying it
- [Phase 3]: The validator checks shapes only -- objective.kind must be a string but is never matched against a list of known kinds, so a kind the server adds later survives
- [Phase 3]: array_key tests k >= 1 and k % 1 == 0 rather than an integer subtype, because a JSON-decoded number is a float and a tonumber-derived one may be an integer; the luajit21 run proves it
- [Phase 3]: restore() rebuilds objective and next_boss field by field instead of adopting them by reference, closing review finding IN-01 rather than narrowing it
- [Phase 3]: HARD-06: reset() clears pending_time; the thirty-second staleness guard at begin is untouched because it answers a different question, and a counter-pin keeps the hold the bridge exists for
- [Phase 3]: The right_text right-alignment finding is accepted as intended behaviour -- pinned by two existing suite locations, not deferred to Phase 4, and not counted as a seventh fragility
- [Phase 4]: 04-01: the remaining-minutes needle is the plural-free 'remaining inside this Incursion' -- it begins after the optional plural, so the one-minute warning is not silently dropped
- [Phase 4]: 04-01: the cheap gate answers yes unconditionally to any line carrying a colour-code marker byte, so a code sitting inside a needle cannot produce a false negative; a coloured irrelevant line costs no more than it did (in fact 2 gsubs instead of 5)
- [Phase 4]: 04-01: both gates stay -- the pre-gate saves the allocation on raw text, the anchored rejection keeps the precision on trimmed text, so the only new risk is a pre-gate false negative
- [Phase 4]: 04-01: parser.relevant has no type guard, so it stays the handler's first raising string method call and the Phase-1 pcall boundary check keeps proving what it was written to prove
- [Phase 4]: 04-01: the gsub counter is opt-in and never installed on a timed host; counting and timing are separate passes on separate hosts
- [Phase 4]: 04-01: no rate is an acceptance threshold -- the one wall-clock assertion is a same-run same-corpus ratio with a 1.2x noise margin, which earned its keep at 1.96x on a busy run against 3.63x on a quiet one
- [Phase 4]: 04-01: superset checks are written as an implication over fixtures, one per distinct SHAPE a matcher accepts, never as a copied list of expected booleans

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

Last session: 2026-08-29T08:35:00.344Z
Stopped at: Completed 04-01-PLAN.md
Resume file: None

## Deferred Verification

Both items are in-game checks no test suite can close. The user chose to carry on
to Phases 3-4 rather than pause; neither blocks that work.

| Phase | State | Resume |
|-------|-------|--------|
| 2 | verification_deferred_human | /gsd-verify-work 2 |
| 3 | verification_deferred_human (1 prudence item) | /gsd-verify-work 3 |

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

- **Phase 3 item D8 (prudence, not a defect).** The repair does
  `pcall(function () imgui.End(); end)`, which reaches Ashita's GuiManager
  through a metatable `__index`. The stub models that shape but cannot execute
  it. Criterion 1 is written against the stub, so this is beyond the contract —
  it would be closed by the same in-game session as the Phase 2 items.

# Phase 2: The Three Defects - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase changes the addon source for the first time in the milestone, and it
changes it only where one of the three confirmed defects lives. Phase 1 built
the net; this phase is the first thing caught in it.

Requirements: FIX-01, FIX-02, FIX-03.

**The binding rule of this phase:** the three expected failures written in
Phase 1 must go green **without their assertion text being edited**. They sit at
`test/run_tests.py:654` (FIX-01), `:707` (FIX-02) and `:1937`/`:1773` region
(FIX-03). Each was deliberately written as a delta, a tolerance window, or a
disjunction over both legitimate fixes, precisely so that a correct fix satisfies
it untouched. Editing an assertion to make it pass would destroy the ordering
guarantee the whole milestone is built on. Each fix must also decrement
`EXPECTED_XFAILS` / update `EXPECTED_DEFECTS` in the same commit, or the guard
fails the run.

Hardening (HARD-01…06) and performance (PERF-01…04) are NOT in this phase. If a
fix here brushes against one of them, note it for Phase 3 or 4 rather than
widening scope.

</domain>

<decisions>
## Implementation Decisions

### FIX-01 — who owns `phases_cleared`

- **The phase line is the sole author.** `Incursion [X] Phase #N` is stated
  outright by the server and is unambiguous. A points award is not exclusively a
  boss kill — bonus payouts and chests award points too, which is precisely the
  defect. The `points` handler at `state.lua:358-365` stops authoring the count;
  the inference at `:198-202` survives as the single writer.
- **`complete` closes the final phase.** The last phase's boss kill never
  produces a new phase line — the run simply ends — so without this the count is
  short by one on every completed run. The `complete` event increments once.
- **Points remain tracked, they just stop authoring.** `points_partial` and the
  reconnect lower-bound logic keep reading points. Removing points tracking
  entirely would break the desync inference, which is a different mechanism
  serving a different purpose.
- **Suite 3's cross-check is re-derived, not deleted.** It currently asserts
  `phases_cleared == number of points events` — an "independent" recomputation
  that encodes the very defect being removed. It must be re-derived from the
  phase-number sequence plus the completion, computed independently from the raw
  log so it remains a genuine cross-check rather than a restatement of the
  implementation. This is expected to go red mid-phase and is not a regression;
  the ROADMAP records it as a carried-in coverage note.

### FIX-02 — how restore ages the clocks

- **All three visible values age by the gap:** `time_left` down, elapsed up,
  bonus expiry down. Ageing one and not the others produces a window that
  contradicts itself — a clock that moved next to an elapsed counter that did
  not.
- **`saved_at` is wall clock (`os.time()`).** It has to survive process death,
  which a monotonic clock does not. On restore the gap is computed from it and
  used to re-seed the monotonic `os.clock` base that drives ticking.
- **A bonus whose timer lapsed during the downtime is dropped**, not shown at
  `0:00` — the same rule the addon already applies to a bonus that lapses while
  running. Consistency with existing behaviour beats a special case.
- **The run stays marked desynced.** Ageing corrects the *clock*; it restores no
  knowledge of what the party did while the addon was gone. The two are
  orthogonal, and clearing the desync marking here would present stale kill
  counts as fact — exactly what the project's core value forbids.

### FIX-03 — how the dead close path dies

- **Remove the plumbing.** `NoTitleBar` is a deliberate 1.1.0 decision — the
  compact layout the changelog sells as roughly half the previous height. The
  window already auto-hides 30 seconds after a run ends and `/incursion` toggles
  it manually, so removing the `ARG_OPEN` plumbing loses nothing but dead code.
  Restoring the title bar to make the close button appear would undo a shipped
  feature to fix a bug that has no user-visible symptom.
- **`/incursion` (and `/inc`) remains the only manual dismiss**, which is what
  the README already documents. No user-facing behaviour changes in this fix.
- **The dead `shown == false` branch at `inctrack.lua:219-222` goes with it**, so
  a `grep` finds no residue. Success criterion 5 is written as a literal grep,
  and leaving the branch would fail it.
- **The six render snapshots will need re-pasting** because removing the
  plumbing changes the recorded `Begin` call shape. That is expected, not a
  regression. The FIX-03 xfail is a disjunction written to survive either
  legitimate fix, so it flips green without being edited.

### Claude's Discretion

- The exact shape of the `complete`-closes-the-final-phase increment, and where
  the wall-clock gap is applied inside `restore()`.
- How suite 3's re-derivation is computed, provided it stays independent of the
  implementation rather than mirroring it.
- Commit sequencing, provided each defect's fix and its `EXPECTED_DEFECTS`
  update land together.

</decisions>

<code_context>
## Existing Code Insights

### The three defects, located

- **FIX-01** — `state.lua:198-202` (phase-line inference: `if e.phase and e.phase - 1 > run.phases_cleared`) and `state.lua:358-365` (points handler). Two authors, one count.
- **FIX-02** — `state.lua:600-634` is `restore()`; `saved_at` is written at `state.lua:556`/`:597` and never read back.
- **FIX-03** — `ui.lua:399` passes the close box to `Begin`; `inctrack.lua:219-222` holds the unreachable `shown == false` branch. `NoTitleBar` is set at `ui.lua:408`'s `Begin` call site.

### The net that will catch this work

- `test/stubs.py` — recording ImGui stub and Ashita host fakes, built in Phase 1. `PADDING` is 11.0 (deliberately not `ui.lua`'s `origin_x` default of 8, so the assignment at `ui.lua:408` is observable).
- `test/run_tests.py` — ten suites. Post-Phase-1 per-suite floor: parser 11819, generic 1, replay 888, state 38, adaptability 20, disconnect 23, timers 21, persistence 25, ui 55, addon 83.
- `Result.xfail(cond, msg, defect_id)` plus `EXPECTED_DEFECTS` as a set and `EXPECTED_XFAILS` as a count. A defect that stops failing without its id being removed fails the run — so a fix cannot land silently.
- The suite is green under seven Lua backends including `luajit21`, the dialect Ashita actually embeds. `INCTRACK_LUA` pins the backend.

### Carried forward from Phase 1's review, relevant here

- The ImGui stub implements exactly the fourteen entry points `ui.lua` uses today. A fix that draws a *new* ImGui control would hit a nil call — it surfaces as a reported suite failure rather than a silent pass, but it means "draw a manual close button" is more expensive than it looks. This informs the FIX-03 decision above.
- Removing `NoTitleBar` would invalidate all six window snapshots' `flags=` lines. Not relevant given the chosen fix, but worth knowing if Q1 is ever revisited.

</code_context>

<specifics>
## Specific Ideas

- Criterion 4 is an **in-game** check: `/addon reload inctrack` mid-run, then confirm the instance clock agrees with the next `You have N minutes remaining` line the server sends rather than being optimistic by the downtime. The addon is deployed live at `...\Ashita\addons\inctrack\`, so this is checkable — but it needs a human in an Incursion, and cannot be closed by the test suite alone.
- Criterion 1 is mechanically checkable and should be enforced as such: a diff of `test/run_tests.py` across this phase must touch no assertion text written in Phase 1.

</specifics>

<deferred>
## Deferred Ideas

- The `right_text` finding from Phase 1: `Complete 48m 44s` stops right-aligning once the instance name plus difficulty runs past the target x, because the do-not-overprint branch fires. Correct as written, but a conscious Phase 3 decision.
- The seven-row-stale layout comment at `ui.lua:15-26`, and the wider `docs/design.md` drift — both belong to Phase 4's DOC-01.
- IN-06 from the Phase 1 review: Ashita's json writes `"boons":[]` where the stub writes `"boons":{}` for an empty table. Informational; not load-bearing for these fixes.

</deferred>

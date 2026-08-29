# Phase 4: Cost and Record - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Phase Boundary

The last phase of v1.2.0. Two halves that share nothing technically but belong
together at the end: make the hot path cheaper, and make the project's own
documents describe the addon that actually ships.

Requirements: PERF-01, PERF-02, PERF-03, PERF-04, DOC-01, DOC-02.

The performance half touches code that runs on **every chat line the client
receives** and **every frame**. The documentation half touches no runtime
behaviour at all — except the one comment inside `ui.lua`, which is a comment.

This phase closes the milestone. After it, `/gsd-audit-milestone` runs.

</domain>

<decisions>
## Implementation Decisions

### Performance

- **PERF-04's measurement lives in the harness and prints in the test report** —
  lines per second through the reject path over a fixed corpus, for a recorded
  pre-change baseline and for the post-change code. A number in the report is
  checkable by anyone later; a number in a summary is a claim. Take the baseline
  at the head of this phase, against the parser as Phase 3 left it — a figure
  recorded earlier would be measuring different code.
- **PERF-01 is a single anchored prefix test before any allocation.** A line that
  cannot be Incursion-related must cost no `strip_colors`, no `trim`, and no
  timestamp loop. Phase 1's Ashita stub already records `strip_colors` calls, so
  "zero calls for an irrelevant line" is assertable rather than assertable-in-
  principle. Reordering patterns alone would leave the allocation cost, which is
  the part that is paid on every line.
- **PERF-02 marks dirty on the chat thread and flushes from the existing
  per-frame handler.** The frame handler already exists and already runs every
  frame, so this adds no new timer and no new mechanism. Ashita has no async
  write primitive; inventing one would be a larger change than the problem.
  A run must not lose data across an unload immediately after a burst — the
  flush has to be reachable on the unload path too.
- **PERF-03 caps the memo cache and drops the whole cache when the cap is
  exceeded**, plus clears on run reset. Boon stat strings are few and repeat
  heavily, so LRU eviction is more code for no measurable gain on real traffic.

### Documentation

- **DOC-01 goes further than the original drift list.** `docs/design.md` is
  corrected to describe what ships — window sizing (`AlwaysAutoResize` plus a
  fixed-width spacer, not fixed width), `NoTitleBar`, the stats layout (points
  tracked but not displayed), the boons row, and the run-record fields
  (`elapsed_final`, `desynced`, `recovered`, `points_partial`, `bonus.loc`) —
  **and** gains what this milestone changed: the `awards_seen` counter and the
  single-author rule for `phases_cleared`, schema `version = 2` with its
  version-1 migration, the structural restore validator and its
  "what shape is this, never is this informative" rule, and the render
  containment with its `render_ok` / `render_off` latches. The design doc is the
  project's ground-truth record of the server message stream; leaving it
  half-true is worse than the drift it started with.
- **The stale `ui.lua:15-26` layout comment is fixed.** It is seven rows out of
  date. This is a comment-only change and the last chance before the milestone
  closes.
- **This ships as 1.2.0.** No new features, so not 1.3.0; far more than a patch,
  so not 1.1.1. The changelog names the defects fixed and the hardening in the
  user-facing terms the Phase-1 xfails were written in — "counted a bonus
  objective payout as a cleared phase", not "double increment in state.lua".
- **The README is corrected too**, folded into DOC-02. It documents a close
  button and a title bar the addon no longer has. A README describing a control
  that does not exist is the same class of error as the design-doc drift, and
  this is the phase for it.

### Claude's Discretion

- The exact corpus and shape of the PERF-04 benchmark, provided the figure is
  printed in the report and both sides are measured the same way.
- The cap value for the memo cache.
- How the design-doc rewrite is structured, provided every claim in it is true
  of the shipped code.

</decisions>

<code_context>
## Existing Code Insights

### State entering this phase

- Suite floor: parser 11819 (exact), generic 1 (exact), tightened 1, replay 888, state 105, adaptability 42, disconnect 23, timers 31, persistence 40, ui 65, addon 143.
- Zero known defects. Green on Lua 5.5 and `luajit21` against 127 logs.
- `inctrack/ui.lua` was not edited in Phase 3 at all; the render path was made un-crashable from outside it.
- Deployed build at `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` is byte-identical to the repo.

### The nine carry-forwards this phase inherits

Listed in `03-03-SUMMARY.md`. The ones that are this phase's business:

- The **per-frame options table** allocated sixty times a second in the frame handler — deliberately not hoisted during Phase 3's rewrite of that handler.
- The unrate-limited **`parse error:` chat line** — now the only chat output with no report-once guard, after Phase 3 added one to the render path.
- The `coverage` message's **cp1252 exposure**: Phase 3 routed its six new failure messages through `ascii()` because a boon line's glyph bytes become `U+FFFD` and a cp1252 console then raises inside `Result.report()`. The pre-existing `coverage` message has the same exposure and was left alone under the scope fence. It is in scope now.

### Two superseded summaries — read the notes

`03-02-SUMMARY.md` and `03-03-SUMMARY.md` each open with a **SUPERSEDED** note.
The code review reversed two decisions after they were written: the boon glyph
group is `%([^)]*%)` (may be empty), and `full_string` no longer exists in the
validator. DOC-01 must describe the shipped code, not those summaries' original
text.

</code_context>

<specifics>
## Specific Ideas

- PERF-02's success criterion is specific: a burst of `MUST_SAVE` events performs no `settings.save` inline on the chat thread — the stub records the writes happening from the per-frame flush instead — and no run data is lost across a simulated unload immediately after such a burst.
- PERF-01's is likewise concrete: zero `strip_colors` calls for a non-Incursion line, `trim` does not run, and the timestamp loop does not run unless the line starts with `[`.
- DOC-02 wants `addon.version` in `inctrack/inctrack.lua` reading `'1.2.0'`, and a CHANGELOG entry naming what changed.

</specifics>

<deferred>
## Deferred Ideas

- CI, luacheck, a versioned release artifact, and a public chatlog fixture — PROC-01…04, deliberately v2 and out of this milestone.
- IN-05 from the Phase 3 review (NaN/±inf in `opt_number`): if picked up later it wants **re-deciding**, not applying as written. CR-01 reversed the proportionality argument it was based on — rejecting a whole live run over a NaN is exactly the trade that was just reversed.
- The three in-game human checks still open (Phase 2's reload clock and window frame, Phase 3's D8 `imgui.End` metatable lookup). They are not this phase's work but should be surfaced at milestone close.

</deferred>

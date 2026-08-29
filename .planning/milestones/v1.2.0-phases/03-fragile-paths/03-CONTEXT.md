# Phase 3: Fragile Paths - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Six fragilities that have not yet been observed to fail. Unlike Phase 2's
defects, none of these is visibly wrong today — they are places where the code
would break, or would quietly show something the server never said, under input
it has not yet received.

Requirements: HARD-01, HARD-02, HARD-03, HARD-04, HARD-05, HARD-06.

**The over-reach risk defines this phase.** Three of the six (HARD-02/03/04)
tighten parser patterns. A pattern tightened past what the server actually sends
would silently drop a real line — turning a hypothetical fragility into an actual
defect, which is strictly worse than leaving it alone. Suite 1 (every structural
line in 127 logs parses) and suite 2 (the generic tier matches nothing) are the
guard, and both must be run against the full chatlog corpus before any tightening
is accepted.

Performance and documentation (PERF-01…04, DOC-01/02) are Phase 4. If a change
here brushes against one, note it rather than widening scope.

</domain>

<decisions>
## Implementation Decisions

### HARD-01 — containing an error inside `d3d_present`

- **The `pcall` goes in `inctrack.lua`'s frame handler, not inside `ui.render`.**
  `ui.lua` stays a pure draw function; the host boundary belongs in the
  host-facing module, which is also where the existing `text_in` `pcall` lives.
  One pattern, one place.
- **The ImGui stack is repaired on a caught error**, not left for ImGui to sort
  out — it does not, it compounds across frames. `End()` is called and anything
  pushed is popped before returning. The Phase-1 stub already counts `Begin`/`End`
  and push/pop pairs, so this is assertable.
- **Report once, then disable the window for the session.** The real failure mode
  is sixty identical errors a second, which is unusable. A single chat line says
  what happened and names `/incursion` as the way back. Silently swallowing is
  not an option — a HUD that vanishes with no explanation is exactly the quiet
  wrongness the project's core value forbids.
- **`/incursion` (and `/incursion reset`) clears the disabled state and tries
  again**, so the player recovers without `/addon reload`.

### HARD-02/03/04 — tightening the patterns without inventing content

- **HARD-02 (boss name containing " at ")**: anchor on the **last** ` at (`
  preceding the trailing coordinate group, not the first ` at `. The coordinate
  group is structurally identifiable; the name is simply whatever precedes it.
  Maintaining a list of names containing " at " is forbidden outright — it would
  be hardcoded content.
- **HARD-03 (mob name containing a comma)**: split on `, ` (comma-space) only.
  The server's list separator is always comma-space; a name's internal comma
  would not be followed by one. This must be verified against all 127 logs before
  it ships, not assumed.
- **HARD-04 (boon matcher)**: require the full `(<glyph>): <stats>` tail — glyph
  group present, colon, non-empty stats. An ordinary `gains the effect of
  Protect.` has no such tail and must produce no boon event. Do **not** also
  require the player name to match; that would break on a name the addon has not
  learned yet.
- **The guard against over-reach is suites 1 and 2**, run against the full 127-log
  corpus. A tightening that reaches too far surfaces either as a generic-tier hit
  (suite 2) or as a drop in the structural parse count (suite 1). Neither may
  move. "It looked right" is not evidence.

### HARD-05 and HARD-06

- **HARD-05**: a restored session is validated structurally before it is applied
  — field types and shapes checked, not merely that the JSON parsed — and a
  malformed one is discarded whole rather than half-applied. Note that Phase 2
  already added schema `version = 2` with a version-1 migration path; this
  builds on that rather than replacing it.
- **HARD-06**: `reset()` clears `pending_time`, so a held timer sync cannot leak
  into an unrelated later run.

### Claude's Discretion

- The exact mechanism for disabling and re-enabling the window after a render
  error, and the wording of the chat line.
- The shape of the structural validator for HARD-05, provided it rejects rather
  than coerces.
- Whether the three pattern tightenings land as one plan or separately.

</decisions>

<code_context>
## Existing Code Insights

### State after Phase 2

- Suite floor: parser 11819, generic 1, replay 888, state 53, adaptability 20, disconnect 23, timers 25, persistence 31, ui 65, addon 83. Total 13,008 checks over 127 logs.
- Zero known defects; `EXPECTED_DEFECTS` is empty and the guard handles the empty set (proven in Phase 2 with a throwaway `FIX-99`).
- Green under seven Lua backends including `luajit21`, the dialect Ashita embeds. `INCTRACK_LUA` pins it.
- `test/stubs.py`'s ImGui recorder is now **strictly positional**, matching Ashita's real `Begin(name, p_open, flags)` signature. A slot-2 flags regression fails 14 checks.
- `ui.lua:416` is `imgui.Begin('inctrack###incursion_window', nil, flags)`.
- Persisted blob is schema `version = 2`; `restore()` accepts 1 or 2 and refuses anything else.

### Where the six live

- **HARD-01** — `inctrack.lua`'s `d3d_present` handler calls `ui.render` unprotected.
- **HARD-02** — `parser.lua`'s `objective_boss` pattern splits on the first ` at `.
- **HARD-03** — the mob-list split assumes names contain no commas.
- **HARD-04** — the boon matcher is the loosest pattern in `parser.lua`.
- **HARD-05** — `state.lua`'s `restore()` trusts the parsed blob structurally.
- **HARD-06** — `pending_time` outlives `reset()`.

### Carried in from earlier phases

- **The `right_text` finding (Phase 1).** `Complete 48m 44s` stops right-aligning once the instance name plus difficulty runs past the target x, because `right_text`'s do-not-overprint branch fires. Correct as written. This phase is where a conscious decision was meant to be made — either accept it as intended behaviour and say so, or treat it as a Phase 4 layout item. It is **not** a defect and must not be counted as one.
- **Two in-game checks from Phase 2 remain open** (the reload clock, and the window frame after CR-01). They do not block this phase.

</code_context>

<specifics>
## Specific Ideas

- HARD-01's success criterion names concrete triggers: a non-string in `objective.mobs`, and a `%` in a server-supplied instance name. Both are reachable through the generic parser tier, which passes server text through verbatim — so these are not hypothetical.
- The stub records equal `Begin`/`End` and `PushStyleVar`/`PopStyleVar` counts, which is how "the stack is balanced after an error" becomes assertable rather than asserted.

</specifics>

<deferred>
## Deferred Ideas

- Per-chat-line cost, settings writes on the chat thread, and the unbounded memo cache — PERF-01…03, Phase 4.
- `docs/design.md` drift, the stale `ui.lua:15-26` layout comment, and the CHANGELOG/version bump — DOC-01/02, Phase 4.
- The per-frame options table allocated sixty times a second in the frame handler, noted during Phase 2 — Phase 4.
- IN-07 from the Phase 2 review: integer-vs-float on `data.phase - 1` through the version-1 migration path.

</deferred>

# Milestones

## v1.2.0 correctness and cost (Shipped: 2026-08-29)

**Phases completed:** 4 phases, 11 plans, 30 tasks

**Closeout:** `override_closeout` — 3 newly acknowledged verification overrides,
0 carried forward from a prior close (see STATE.md Deferred Items). Phases 2, 3
and 4 each verified `human_needed`: four in-game checks require a rendered frame
in a live Incursion and were not run. They are not claimed as passed.

**Key accomplishments:**

- A recording ImGui stub, in-memory Ashita fakes and a pure-Lua json that let the suite load and run all 734 previously-unreachable lines of `ui.lua` and `inctrack.lua`, plus `make_host()`, upvalue reflection into the addon's file-scope locals, and an expected-failure mechanism that reports distinctly without turning the run red.
- `ui.lua`'s seven pure helpers, its `STAT_SHORT` ordering contract and six whole-window renders are now asserted directly against the recording ImGui stub — 53 checks where there were none — and the dead close-button path is one named expected failure that either Phase-2 fix turns green.
- `inctrack.lua` — 301 lines at zero automated coverage — now runs outside the game across 81 checks covering registration, the `text_in` pcall boundary, the `MUST_SAVE` write policy, the resume round trip, player-name resolution, the profile switch, every `/incursion` subcommand and both sides of the render gate; and the phase closes with exactly three named, red, player-legible defect lines and a guard that fails the run on any other number.
- `phases_cleared` now has one author -- the phase line, plus the completion closing the final phase -- and `restore()` ages the instance clock, the elapsed counter and the bonus expiry by the wall-clock gap it always had on disk; both Phase-1 expected failures went green with their assertion bytes provably untouched.
- The window stopped asking ImGui for a close control it can never draw and the addon shell stopped waiting for a click on it; the six render snapshots moved by one substring each, FIX-03 went green with its Phase-1 bytes untouched, and the milestone's known-defect count is now zero on both backends.
- `ui.render` now runs inside a `pcall` in `d3d_present`, with a stack repair that is conditional on the render shape having already run clean once on this host — so a raise before `Begin` closes nothing — a report-once latch naming `/incursion` as the way back, and 29 new addon checks pinning all of it.
- A saved session of the wrong shape is now refused whole before a single field is read for its value — 27 one-field-broken rejection cases, each proving falsy return, no run left behind and nothing raised — with the objective and boss preview rebuilt from validated values instead of adopted by reference, the boon loop no longer skipping malformed members, and `reset()` clearing the held timer sync so a `/incursion reset` cannot seed the next run's clock.
- A chat line the addon ignores is now rejected before anything is built for it — no copy, no colour stripping, no pattern run, no trim, no timestamp loop — behind a seven-needle superset gate whose safety argument is written out in `parser.lua`, with the before-and-after printed in the test report every run. About 3.5x cheaper on the reject path, measured over a corpus that is three quarters uncoloured; a coloured line still pays for its stripping, because the gate deliberately refuses to judge a line it has not yet uncoloured.
- The settings write left the game thread — `text_in` now marks the run as owed a write and `d3d_present` performs it above both of its early returns — and `shorten()`'s memo cache stopped being able to grow for a whole play session.
- inctrack ships as 1.2.0 with a changelog the harness holds the version to, a design record rewritten from the source rather than from two summaries the code review reversed, a `ui.lua` layout comment naming all nine rows, and the milestone closed green on both backends against 127 logs and redeployed to the live install.

---

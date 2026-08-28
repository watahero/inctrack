---
phase: 02-the-three-defects
plan: 01
subsystem: state
tags: [lua, state-machine, persistence, wall-clock, regression-testing, xfail]

# Dependency graph
requires:
  - phase: 01-the-net
    provides: "the ten-suite harness, the res.xfail/EXPECTED_DEFECTS mechanism, and the FIX-01 and FIX-02 red lines written as deltas and tolerance windows so a correct fix satisfies them untouched"
provides:
  - "phases_cleared has exactly one author: the phase line's N-1 inference, plus the completion closing the final phase"
  - "run.awards_seen -- our own points awards actually witnessed -- as the yardstick for the points-are-a-lower-bound marking"
  - "restore() ages time_left, elapsed and the bonus expiry by the wall-clock gap, clamped so a future stamp cannot add time"
  - "suite 3's cleared-phase cross-check re-derived from the raw log's phase-number sequence instead of its points-event count"
  - "/tmp/inctrack-assert-integrity.py -- a mechanical audit that the Phase-1 assertion bytes were not edited"
affects: [02-02, 03-hardening, 04-cost-and-docs]

actuals:
  tokens: 33951
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "a defect's fix and its EXPECTED_DEFECTS retirement land in one commit, so the run is never green on a stale expectation"
    - "an expected failure is converted by swapping the ten-character callee token and dropping the trailing defect id -- nothing else -- and the byte-identity is then audited mechanically rather than by eye"
    - "a cross-check over real data is re-derived from the raw text, never restated from the implementation it is meant to check"

key-files:
  created: []
  modified:
    - inctrack/state.lua
    - test/run_tests.py

key-decisions:
  - "The phase line and the completion are the only authors of phases_cleared; the points handler advances awards_seen instead"
  - "points_partial is judged against awards witnessed, not against whether the count moved -- the count now moves on every ordinary transition"
  - "restore()'s wall-clock gap is clamped at zero, so a stamp from the future is inert rather than generous (T-02-01)"
  - "A bonus that lapsed during the downtime is dropped by State:bonus()'s existing expiry rule rather than by a special case in restore()"
  - "The two persistence clock comparisons gain one second of tolerance, because restore now subtracts a real wall-clock gap that can tick over mid-round-trip"

patterns-established:
  - "Byte-identity of a converted assertion is proven by a paren-scanning audit script against the Phase-1 baseline commit, with a negative control run before the verdict is trusted"
  - "A run-record counter added for an inference is carried through serialise/restore with a fallback that reads an older blob correctly"

requirements-completed: [FIX-01, FIX-02]

coverage:
  - id: D1
    description: "A points award that was not caused by a phase boss dying leaves Phases cleared unchanged"
    requirement: FIX-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'counted a bonus objective payout as a cleared phase' (the converted FIX-01 check)"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'a payout with no phase boundary behind it was counted as a cleared phase'"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'a points award moved the count of cleared phases on its own'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Reaching phase N reads as N-1 cleared, and the completion closes the final phase, so a finished run's count equals the highest phase the server announced"
    requirement: FIX-01
    verification:
      - kind: integration
        ref: "test/run_tests.py#state: run reconstruction -- 888 checks over 127 real chatlogs, cleared count re-derived from the raw phase-number sequence"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'a two-phase run watched from Begins! to Complete!'"
        status: pass
    human_judgment: false
  - id: D3
    description: "A run watched from Begins! through Complete! is never flagged as having missed points, while a run joined late still is"
    requirement: FIX-01
    verification:
      - kind: integration
        ref: "test/run_tests.py#state: run reconstruction -- 'clean run flagged as having missed points', 888 real runs"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'joining on phase 4 having watched no award left the points total unmarked'"
        status: pass
    human_judgment: false
  - id: D4
    description: "A run that comes back after ten minutes away shows time_left 600s lower, elapsed 600s higher, and a lapsed bonus gone rather than sitting at 0:00"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'clock was optimistic by the reload gap after a reconnect' (the converted FIX-02 check)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A bonus with plenty of time left survives the gap with its countdown moved down by it, not reset"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'a surviving bonus countdown was not moved down by the reload gap'"
        status: pass
    human_judgment: false
  - id: D6
    description: "A saved run stamped in the future cannot add time to the clock, and a restored run stays marked out of sync"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: objectives, bonus, recovery -- 'a save stamped ten minutes in the future moved the clock' and 'ageing the clock cleared the out-of-sync marking'"
        status: pass
    human_judgment: false
  - id: D7
    description: "Both fixes hold on LuaJIT 2.1, the dialect Ashita actually embeds, with identical per-suite counts"
    verification:
      - kind: integration
        ref: "INCTRACK_LUA=luajit21 python test/run_tests.py \"C:\\Games\\CatsEyeXI\\catseyexi-client\\Ashita\\chatlogs\""
        status: pass
    human_judgment: false
  - id: D8
    description: "The Phase-1 FIX-01 and FIX-02 assertion text came through the conversion byte-identical"
    verification:
      - kind: other
        ref: "python /tmp/inctrack-assert-integrity.py (exit 0; negative control confirmed it exits 1 on a one-character edit)"
        status: pass
    human_judgment: false
  - id: D9
    description: "In-game confirmation that a mid-run /addon reload comes back with an instance clock that agrees with the server's next 'You have N minutes remaining' line"
    verification: []
    human_judgment: true
    rationale: "Phase criterion 4 needs a human inside a live Incursion on CatsEyeXI. No test suite can produce a real reload against a real server clock; the harness can only prove the arithmetic."

duration: 16min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 01: The Two Defects in state.lua Summary

**`phases_cleared` now has one author -- the phase line, plus the completion closing the final phase -- and `restore()` ages the instance clock, the elapsed counter and the bonus expiry by the wall-clock gap it always had on disk; both Phase-1 expected failures went green with their assertion bytes provably untouched.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-28T23:07:00Z
- **Completed:** 2026-08-28T23:23:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- **FIX-01.** The points handler stopped authoring the cleared-phase count. A bonus payout, a chest, any award that was not a phase boss dying, now leaves `Phases cleared` where it was. The phase line's `reaching phase N means N-1 cleared` inference is the single writer during a run, and `complete` closes the final phase -- whose boss kill never produces a phase line, so without it every finished run was short by one.
- **The lower-bound marking was re-based, not removed.** `points_partial` was previously set by the *same* `if` that raised the count, and stayed quiet on a watched run only because the points handler had already advanced the count past `e.phase - 1`. With the points handler out of that business, the old coupling would have fired on every ordinary transition and turned ~890 checks red. A new run-record field `awards_seen` counts our own awards actually witnessed, and the marking is now `e.phase - 1 > run.awards_seen`. It reproduces the old flagging set exactly on all 127 chatlogs.
- **FIX-02.** `restore()` computes the wall-clock gap from the `saved_at` stamp every save already carried, and moves all three visible quantities by it: `time_left` down (floored at zero), `started` back so `elapsed` comes up, and the bonus expiry down. A bonus whose expiry lands in the past is dropped by `State:bonus()`'s existing rule rather than by a new special case, which keeps the record in place so a later server progress line can revive it. `run.desynced` stays unconditionally true -- ageing corrects the clock, not our knowledge of what the party did.
- **A future stamp is inert.** The gap is clamped at zero, so a hand-edited settings file or a skewed system clock cannot add time to the run (T-02-01).
- **Suite 3's cross-check stopped restating the defect.** It asserted `phases_cleared == number of points events`, which was the bug written down as an expectation. It is re-derived from the raw text -- the highest `Phase #N` the log shows for that instance, with the degenerate no-phase-line case reading 1 -- and passes on all 888 verified runs. The check count did not move.
- **The binding rule was proven mechanically.** `/tmp/inctrack-assert-integrity.py` extracts each Phase-1 `res.xfail` body from `b8a19fa` with a string-aware paren scanner and requires it verbatim inside a `res.check(...)` in the working tree. FIX-01: 225 bytes intact. FIX-02: 559 bytes intact. A negative control (one added full stop) was run first and made it exit 1, so the exit-0 verdict is not vacuous.
- **Green on both backends** with identical per-suite counts, including LuaJIT 2.1 -- the dialect Ashita embeds. Exactly one XFAIL remains, FIX-03, which is plan 02-02's.

## Task Commits

1. **Task 1: One author for the cleared-phase count, and the three assertions that encoded the second one** — `4d678c6` (fix)
2. **Task 2: `restore()` ages the clock, the elapsed counter and the bonus by the time spent unloaded** — `75515c8` (fix)
3. **Task 3: Prove both fixes on the backend Ashita embeds, and prove the two assertions were not edited** — no repository files modified by design; its artefacts are the two verbatim reports, the classification table and the audit script reproduced below.

## Files Created/Modified

- `inctrack/state.lua` — `awards_seen` added to the run record, serialised and restored; the points branch advances it instead of `phases_cleared`; the phase branch separates the N-1 inference from the lower-bound marking; `complete` closes the final phase; `restore()` computes and applies a clamped wall-clock gap to `started`, `time_left` and the bonus expiry.
- `test/run_tests.py` — FIX-01 and FIX-02 converted from `res.xfail` to `res.check`; nine new fixtures; three pre-Phase-1 assertions re-derived; two persistence comparisons given one second of tolerance; `WINDOW_FINISHED` re-pasted; `EXPECTED_XFAILS`/`EXPECTED_DEFECTS` reduced to FIX-03.
- `/tmp/inctrack-assert-integrity.py` — deliberately outside the repository, so it never enters a commit. Reproduced verbatim below so the byte-identity claim survives the scratch file.

## Decisions Made

Every decision locked in `02-CONTEXT.md` was honoured without re-opening. Beyond those, three choices were Claude's discretion under the plan:

- **The `complete` increment is guarded on `not run.finished`** and placed before `run.finished` is set. A second `Complete!` inside the 30-second linger window is still absorbed by `apply`, and without the guard it would count the final phase twice.
- **`restore()`'s gap is computed once at the top and the staleness rejection reads that value**, rather than calling `os.time()` twice. A future stamp clamps to zero, which is also what the old negative-difference arithmetic did for the staleness test, so that behaviour is unchanged.
- **Suite 3's re-derivation is `max(active["phases"])`, falling back to 1** when the log shows no phase line at all. It is computed purely from `active` -- the raw-text facts -- and touches nothing the state machine produced.

## Deviations from Plan

None — plan executed exactly as written. No auto-fix rule was invoked; no architectural question arose.

## Both Full-Run Reports, Verbatim

Command 1 — default backend:

```
$ python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"
inctrack tests
  lua: Lua 5.5
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2944071 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               49 checks  ok
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             21 checks  ok
  persistence: json round trip                     25 checks  ok
  ui: helpers, layout contract, render             55 checks  ok (1 known defects)
      XFAIL the window asks for a close button and then ignores it -- clicking close leaves the window on screen
  addon: load, chat, settings, commands            83 checks  ok

  1 known defects (expected until Phase 2)

PASS
=== exit: 0 ===
FAILED lines: 0
NOW PASSING lines: 0
XFAIL lines: 1
```

Command 2 — the backend Ashita embeds:

```
$ INCTRACK_LUA=luajit21 python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"
inctrack tests
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2944071 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               49 checks  ok
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             21 checks  ok
  persistence: json round trip                     25 checks  ok
  ui: helpers, layout contract, render             55 checks  ok (1 known defects)
      XFAIL the window asks for a close button and then ignores it -- clicking close leaves the window on screen
  addon: load, chat, settings, commands            83 checks  ok

  1 known defects (expected until Phase 2)

PASS
=== exit: 0 ===
FAILED lines: 0
NOW PASSING lines: 0
XFAIL lines: 1
```

### Per-suite counts against the Phase-1 floor

| Suite | Phase-1 floor | Default backend | luajit21 | Verdict |
|---|---|---|---|---|
| parser: structural lines all parse | 11819 | 11819 | 11819 | held |
| parser: generic tier matches nothing today | 1 | 1 | 1 | held |
| state: run reconstruction | 888 | 888 | 888 | held |
| state: objectives, bonus, recovery | 38 | 49 | 49 | rose by 11 |
| adaptability: unseen content still tracked | 20 | 20 | 20 | held |
| disconnect: stale progress is not trusted | 23 | 23 | 23 | held |
| timers: countdown, linger, staleness | 21 | 21 | 21 | held |
| persistence: json round trip | 25 | 25 | 25 | held |
| ui: helpers, layout contract, render | 55 | 55 | 55 | held |
| addon: load, chat, settings, commands | 83 | 83 | 83 | held |

No suite fell, on either backend, and the two backends agree line for line. The state-units suite rose by eleven: six FIX-01 fixtures (two on the end-to-end run, one on the bare payout, two on the late join, and the extra `phases_cleared` read the late-join fixture needs) and five FIX-02 fixtures (restore accepted, bonus kept, countdown moved, still desynced, future stamp accepted and inert).

## Hunk-by-Hunk Classification of `git diff -U0 b8a19fa -- test/run_tests.py`

`git diff -U0 b8a19fa -- test/run_tests.py | grep -c "^@@"` reports **17**. Every one is on the allowed list; no row is unclassified.

| # | Hunk | Lines | Classification |
|---|---|---|---|
| 1 | `@@ -322,2 +322 @@` | the "Three, exactly" comment opener | bookkeeping constants' comment |
| 2 | `@@ -325,2 +323,0 @@` | the two fixed defects dropped from the comment's list | bookkeeping constants' comment |
| 3 | `@@ -329 +326,5 @@` | "A fourth" → "A second", plus the note that FIX-01 and FIX-02 are now ordinary checks | bookkeeping constants' comment |
| 4 | `@@ -332 +333 @@` | `EXPECTED_XFAILS = 3` → `1` | bookkeeping constant |
| 5 | `@@ -340 +341 @@` | `EXPECTED_DEFECTS = {"FIX-01","FIX-02","FIX-03"}` → `{"FIX-03"}` | bookkeeping constant |
| 6 | `@@ -499 +500,8 @@` | `verify_run`'s cleared-count condition, plus its derivation comment | re-derivation of a pre-Phase-1 assertion (1 of 3) |
| 7 | `@@ -501 +509 @@` | that same check's failure message naming `want_cleared` | re-derivation of a pre-Phase-1 assertion (1 of 3, continued) |
| 8 | `@@ -594 +602,2 @@` | the points-are-ours-only fixture's cleared count `1` → `0` | re-derivation of a pre-Phase-1 assertion (2 of 3) |
| 9 | `@@ -720 +729 @@` | `res.xfail(` → `res.check(` on the FIX-01 line | callee swap (FIX-01) |
| 10 | `@@ -723,2 +732 @@` | the trailing `"FIX-01"` argument dropped | dropped defect id (FIX-01) |
| 11 | `@@ -733,0 +742,45 @@` | the end-to-end run, the bare payout, and the late join | new fixtures after the converted FIX-01 check |
| 12 | `@@ -782 +835 @@` | `res.xfail(` → `res.check(` on the FIX-02 line | callee swap (FIX-02) |
| 13 | `@@ -790,2 +843,54 @@` | the trailing `"FIX-02"` argument dropped, then the surviving bonus, the still-desynced assertion and the future stamp | dropped defect id (FIX-02) + new fixtures after the converted FIX-02 check |
| 14 | `@@ -1036 +1141,3 @@` | back-while-the-boss-is-up: `3` → `2`, message rewritten | re-derivation of a pre-Phase-1 assertion (3 of 3) |
| 15 | `@@ -1250 +1357,4 @@` | bonus-expiry equality → `<= 1`, with its reason | persistence tolerance (1 of 2) |
| 16 | `@@ -1252 +1362,2 @@` | time-left equality → `<= 1` | persistence tolerance (2 of 2) |
| 17 | `@@ -1567 +1678 @@` | `WINDOW_FINISHED`'s `TextColored text '0'` → `'1'` | the single-character window value |

Hunk 13 carries two allowed changes because `-U0` merges the dropped defect id with the fixtures that immediately follow it; both are on the list.

`git diff --quiet -- inctrack/ui.lua inctrack/inctrack.lua inctrack/parser.lua` exits 0. Under `inctrack/`, this plan changed `state.lua` and nothing else.

## Pre-Phase-1 Assertions Re-Derived

All three predate Phase 1 (confirmed against `86356f0~1`), so editing them does not breach the binding rule, which protects only assertion text *written* in Phase 1. Each is recorded here with its old and new form.

### 1. `verify_run`, suite 3 (`test/run_tests.py:499` before, `:500` after)

Old:

```python
    res.check(int(run["phases_cleared"]) == active["point_events"],
              "%s: phases %d != %d"
              % (tag, int(run["phases_cleared"]), active["point_events"]))
```

New:

```python
    # Re-derived from the raw text, never from anything the state machine
    # produced: reaching 'Phase #N' means N-1 phases were cleared, and the
    # completion closes the Nth, so the highest phase number the log shows is
    # the count. A completed run whose log carries no phase line at all is the
    # degenerate case -- the completion is then the only phase boundary, so
    # exactly one phase was cleared.
    want_cleared = max(active["phases"]) if active["phases"] else 1
    res.check(int(run["phases_cleared"]) == want_cleared,
              "%s: phases %d != %d"
              % (tag, int(run["phases_cleared"]), want_cleared))
```

**Why.** `active["point_events"]` counts every points line in the raw text, bonus payouts included. Comparing the cleared count against it was not an independent cross-check at all -- it was the FIX-01 defect written down as an expectation, and it is exactly why 888 real runs went green over a count that was wrong. `active["phases"]` is collected from the same raw text, from the `Phase #N` lines the server itself sends, and never touches the state machine. Still one check per verified run, so suite 3's 888 is unmoved.

### 2. Points-are-ours-only fixture, `test_state_units` (`:594` before, `:602` after)

Old:

```python
    res.check(int(run["phases_cleared"]) == 1, "phases_cleared wrong")
```

New:

```python
    res.check(int(run["phases_cleared"]) == 0,
              "a points award moved the count of cleared phases on its own")
```

**Why.** The fixture is `Begins!` plus our award plus a foreign player's award. There is no phase line in it, so no phase was cleared; the `1` it expected was the defect. The `points == 84` assertion beside it is untouched and still proves the foreign award was rejected. The message was rewritten because "phases_cleared wrong" says nothing about what went wrong.

### 3. Back-while-the-boss-is-up, disconnect suite (`:1036` before, `:1141` after)

Old:

```python
    res.check(int(run["phases_cleared"]) == 3, "phases cleared wrong after a boss kill")
```

New:

```python
    res.check(int(run["phases_cleared"]) == 2,
              "a points award moved the count of cleared phases -- only the "
              "next phase line does that")
```

**Why.** `mid_phase()` reaches `Phase #3`, which establishes two cleared phases; the fixture then reconnects and takes a points award. Under one author the count stays where the last phase line put it, and only the *next* phase line will move it. The `3` encoded the removed author. The message now states the new intent rather than asserting a number is "wrong".

### Two further pre-Phase-1 assertions widened (persistence round trip, `:1250` and `:1252`)

Old:

```python
    res.check(int(s2.bonus_remaining(s2)) == int(s.bonus_remaining(s)),
              "bonus expiry lost")
    res.check(int(s2.time_left(s2)) == int(s.time_left(s)), "time left lost")
```

New:

```python
    # One second of tolerance on both: restore subtracts a real wall-clock gap
    # now, and the os.time() second can tick over between the encode and the
    # decode. A one-second move here is the ageing working, not a value lost.
    res.check(abs(int(s2.bonus_remaining(s2)) - int(s.bonus_remaining(s))) <= 1,
              "bonus expiry lost")
    res.check(abs(int(s2.time_left(s2)) - int(s.time_left(s))) <= 1,
              "time left lost")
```

**Why.** These compared a value across a round trip for exact equality. `restore()` now subtracts a genuine wall-clock gap, and the `os.time()` second can tick over between `serialise` and `restore` in the same test — a one-second difference is the ageing working correctly, not a lost value, and without the tolerance the suite would flake roughly once per second of wall-clock alignment. The check count is unchanged at two.

### One window snapshot re-pasted

`WINDOW_FINISHED`'s `TextColored text '0'` became `'1'`. Its fixture is `Begins!` followed immediately by `Complete!` with **no phase line at all**, so the `1` it now shows is the completion closing the run's only phase — the precise behaviour FIX-01 added. One character; nothing else in that literal or in any of the other five snapshots moved. FIX-03's six `Begin` lines are plan 02-02's business.

## The Audit Script, Verbatim

Written to `/tmp/inctrack-assert-integrity.py` — a fixed path outside the repository, so it never enters a commit and plan 02-02 can extend it by adding `"FIX-03"` to `AUDITED`.

**Its verdict on this plan's working tree:**

```
$ python /tmp/inctrack-assert-integrity.py; echo "audit exit: $?"
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  INTACT -- 225 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
VERDICT: all 2 audited assertions intact.
audit exit: 0
```

**Negative control**, run before that verdict was trusted — a single full stop added to the FIX-01 message, then reverted with `git checkout -- test/run_tests.py`:

```
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  EDITED -- the Phase-1 assertion text is no longer in test/run_tests.py
    --- FIX-01 (phase 1)
    +++ FIX-01 (working tree)
    @@ -1,4 +1,4 @@
     after_bonus - after_boss == 0,
                   "counted a bonus objective payout as a cleared phase -- the "
    -              "window went from %d cleared to %d without a phase boss dying"
    +              "window went from %d cleared to %d without a phase boss dying."
                   % (after_boss, after_bonus)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
VERDICT: 1 of 2 audited assertions were edited. The binding rule of Phase 2 is broken.
audit exit: 1
```

An exit-0 verdict from a script that cannot fail proves nothing, which is why the control was run first.

**Source:**

```python
#!/usr/bin/env python3
"""
Prove that Phase 2 flipped the Phase-1 expected failures green WITHOUT editing
a byte of their assertion text.

That is the binding rule of the milestone: the three red lines written in
Phase 1 were deliberately shaped as deltas, tolerance windows and disjunctions
so that a *correct* fix satisfies them untouched. An assertion edited to make
it pass would destroy the ordering guarantee the whole milestone rests on, and
"I did not edit it" is exactly the claim a reader cannot verify by eye across a
three-hundred-line diff. So it is verified mechanically, here, and this
script's exit code is the verdict.

Method: take test/run_tests.py as it stood at the end of Phase 1, find each
`res.xfail(...)` call by scanning forward from the callee token with a paren
counter that is string-literal and comment aware, strip the callee token from
the front and the trailing defect-id argument from the back, and require what
is left -- the condition expression and the message expression, whitespace,
line breaks and continuation indentation included -- to occur verbatim in the
current working tree, wrapped in `res.check(` ... `)`.

`res.xfail(` and `res.check(` are both exactly ten characters, so a correct
conversion needs no re-wrapping and no re-indentation: the bytes come through
untouched or they do not come through at all.

Run from anywhere inside the repository:

    python /tmp/inctrack-assert-integrity.py

Exit 0 means every audited assertion is intact. Exit non-zero prints a unified
diff of the Phase-1 text against the nearest thing now in the file.

Plan 02-02 extends this by adding "FIX-03" to AUDITED once that defect's fix
lands; nothing else needs to change.
"""

import difflib
import subprocess
import sys

BASELINE = "b8a19fa"
BASELINE_SUBJECT = "docs(01): mark Phase 1 complete"
TARGET = "test/run_tests.py"

XFAIL = "res.xfail("
CHECK = "res.check("

# The defects whose Phase-1 assertion text this run audits. FIX-03 is plan
# 02-02's and is deliberately absent until its fix lands.
AUDITED = ("FIX-01", "FIX-02")


def git(*args):
    """git, decoded latin-1.

    Byte-exact and total: the harness carries raw high bytes (a shift-jis boon
    glyph in a fixture), and this audit is a claim about bytes, so it must not
    go through a codec that can fail or normalise.
    """
    out = subprocess.run(["git"] + list(args), capture_output=True)
    if out.returncode != 0:
        sys.stderr.write("git %s failed: %s\n"
                         % (" ".join(args), out.stderr.decode("latin-1")))
        sys.exit(2)
    return out.stdout.decode("latin-1")


def scan_call(src, start):
    """Source of the call whose callee token begins at `start`.

    Walks forward from the opening paren with a depth counter, skipping over
    string literals and comments so a paren or a quote inside a message cannot
    close the call early. Returns the full call text, opening callee token and
    closing paren included.
    """
    i = src.index("(", start)
    depth = 0
    quote = None
    while i < len(src):
        c = src[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if src.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            i += 1
            continue
        if c in "\"'":
            for q in ('"""', "'''", '"', "'"):
                if src.startswith(q, i):
                    quote = q
                    i += len(q)
                    break
            continue
        if c == "#":
            i = src.find("\n", i)
            if i < 0:
                break
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError("unterminated call at offset %d" % start)


def calls(src, token):
    """Every call to `token` in `src`, as (offset, source) pairs."""
    out = []
    at = src.find(token)
    while at >= 0:
        out.append((at, scan_call(src, at)))
        at = src.find(token, at + 1)
    return out


def split_last_arg(body):
    """Split a call's argument text at its last top-level comma."""
    depth = 0
    quote = None
    cut = -1
    i = 0
    while i < len(body):
        c = body[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if body.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            i += 1
            continue
        if c in "\"'":
            for q in ('"""', "'''", '"', "'"):
                if body.startswith(q, i):
                    quote = q
                    i += len(q)
                    break
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            cut = i
        i += 1
    if cut < 0:
        return body, ""
    return body[:cut], body[cut + 1:].strip()


def baseline_bodies():
    """The Phase-1 condition-and-message text of each audited xfail."""
    src = git("show", "%s:%s" % (BASELINE, TARGET))
    found = {}
    for _, call in calls(src, XFAIL):
        body = call[len(XFAIL):-1]
        kept, last = split_last_arg(body)
        ident = last.strip("\"'")
        if ident in AUDITED:
            found[ident] = kept
    return found


def nearest(current, want):
    """The call in `current` most like `want`, for the failure diff."""
    best, score = "", -1.0
    for token in (CHECK, XFAIL):
        for _, call in calls(current, token):
            body = call[len(token):-1]
            r = difflib.SequenceMatcher(None, body, want).ratio()
            if r > score:
                best, score = body, r
    return best


def main():
    subject = git("log", "-1", "--format=%s", BASELINE).strip()
    if subject != BASELINE_SUBJECT:
        print("baseline %s is not the end of Phase 1: %r" % (BASELINE, subject))
        return 2
    print("baseline %s  %s" % (BASELINE, subject))

    bodies = baseline_bodies()
    with open(git("rev-parse", "--show-toplevel").strip() + "/" + TARGET,
              "rb") as fh:
        current = fh.read().decode("latin-1")

    bad = 0
    for ident in AUDITED:
        want = bodies.get(ident)
        if want is None:
            print("%s  MISSING -- no such expected failure in the baseline"
                  % ident)
            bad += 1
            continue
        at = current.find(want)
        if at < 0:
            print("%s  EDITED -- the Phase-1 assertion text is no longer in "
                  "%s" % (ident, TARGET))
            for line in difflib.unified_diff(
                    want.splitlines(), nearest(current, want).splitlines(),
                    fromfile="%s (phase 1)" % ident,
                    tofile="%s (working tree)" % ident, lineterm=""):
                print("    " + line)
            bad += 1
            continue
        before = current[max(0, at - len(CHECK)):at]
        after = current[at + len(want):at + len(want) + 1]
        if before != CHECK or after != ")":
            print("%s  MISPLACED -- the text survives but is not an ordinary "
                  "res.check(...) call: preceded by %r, followed by %r"
                  % (ident, before, after))
            bad += 1
            continue
        print("%s  INTACT -- %d bytes of condition and message, byte-identical "
              "to Phase 1, now inside res.check(...)" % (ident, len(want)))

    if bad:
        print("VERDICT: %d of %d audited assertions were edited. The binding "
              "rule of Phase 2 is broken." % (bad, len(AUDITED)))
        return 1
    print("VERDICT: all %d audited assertions intact." % len(AUDITED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Verification Evidence

| Plan verification step | Result |
|---|---|
| 1. `python test/run_tests.py` | `PASS`, exit 0, `1 known defects`, one `XFAIL ` line, no `NOW PASSING` |
| 2. Full run against the chatlogs | `PASS`, exit 0, `FAILED` lines: 0, every per-suite count at or above the Phase-1 floor |
| 3. `INCTRACK_LUA=luajit21` full run | identical verdict, identical per-suite counts |
| 4. `python /tmp/inctrack-assert-integrity.py` | FIX-01 and FIX-02 intact, exit 0 (negative control exits 1) |
| 5. `git diff --quiet -- inctrack/ui.lua inctrack/inctrack.lua inctrack/parser.lua` | exit 0 |
| 6. Content-name grep over `inctrack/` | `state.lua` returns nothing. The hits are pre-existing message-shape examples in `parser.lua` and `ui.lua` header comments, untouched by this plan and present since before the milestone |

Task-level greps:

| Grep | Expected | Actual |
|---|---|---|
| `phases_cleared` in the points branch, comments filtered | 0 | 0 |
| `run.phases_cleared = run.phases_cleared + 1` in `state.lua` | 1, in the complete branch | 1, at `state.lua:414` inside `if t == 'complete'` |
| `awards_seen` in `state.lua` | at least 5 | 5 — declaration, increment, phase comparison, serialise, restore |
| `saved_at` in `state.lua` | at least 3 | 4 — written in `serialise`, read for the gap, read twice for the staleness judgement |

## Issues Encountered

- **The audit script died on a raw high byte.** `test/run_tests.py` carries a shift-jis boon glyph (`\x81\x98`) as literal bytes, and Python's default Windows codec (`cp1252`) cannot decode it, so both `git show` and the working-tree read raised. Fixed by decoding everything `latin-1`, which round-trips bytes exactly — appropriate for an audit whose whole claim is about bytes.
- **Nothing else.** The re-derived suite-3 cross-check passed on all 888 real runs on the first attempt, which is the strongest evidence that `awards_seen` reproduces the old flagging set exactly rather than approximately.

## Carried Forward — Noted, Not Acted On

### Phase 3 (hardening)

- **HARD-05, structural validation of a restored blob.** `restore()` now performs arithmetic on `data.saved_at`, `data.elapsed`, `data.time_left` and `data.bonus.remaining` without type-checking any of them. This is **not new exposure** — every one of those dereferences was already there and unvalidated (registered as T-02-02, disposition `transfer`) — but the gap arithmetic makes the settings file a slightly wider lever: a non-numeric `saved_at` raises inside `restore` rather than merely producing a wrong number. Phase 3 should validate the blob's shape once, at entry, rather than scattering guards.
- **T-02-04 stands as accepted.** A forged `awards_seen` in a hand-edited settings file can only suppress the points-are-a-lower-bound marking, which is not displayed and gates nothing.

### Phase 4 (cost and docs)

- **DOC-01 must now list the `awards_seen` run-record field.** It joins `points` and `phases_cleared` in the run record and is carried through `serialise`/`restore`; `docs/design.md`'s description of the run record is now incomplete without it. The version-1 blob gained one optional key, with a documented 1.1.0 fallback (`data.awards_seen or data.phases_cleared or 0`) — that compatibility rule belongs in the docs too.
- **DOC-01 should also correct the cleared-phase story.** Any prose saying a points award advances `Phases cleared` now describes removed behaviour.
- No per-line cost was added to the hot path: the points branch swapped one increment for another, and the phase branch's extra comparison runs only on phase lines, which arrive a handful of times per run.

## Next Phase Readiness

- **Plan 02-02 is unblocked.** `EXPECTED_XFAILS` is 1 and `EXPECTED_DEFECTS` is `{"FIX-03"}`; the guard will fail the run the moment FIX-03 flips without that set being updated, exactly as designed.
- **`/tmp/inctrack-assert-integrity.py` is ready to extend** — plan 02-02 adds `"FIX-03"` to `AUDITED` and nothing else. Its source is reproduced above in full, so the scratch file being swept costs nothing.
- **`inctrack/ui.lua` and `inctrack/inctrack.lua` are untouched** and are plan 02-02's alone, as are the six window snapshots' `Begin` lines. `WINDOW_FINISHED`'s cleared-phase value moved here; its `Begin` line did not.
- **Phase criterion 4 remains open and is not closeable by this plan.** It needs a human inside a live Incursion to `/addon reload inctrack` mid-run and confirm the clock agrees with the server's next `You have N minutes remaining` line. The arithmetic is proven; the deployment is not.

---
*Phase: 02-the-three-defects*
*Completed: 2026-08-29*

## Self-Check: PASSED

- `inctrack/state.lua`, `test/run_tests.py` and this SUMMARY all exist on disk.
- `/tmp/inctrack-assert-integrity.py` exists and exits 0; its source is reproduced above in full.
- Commits `4d678c6`, `75515c8` and `e074697` all present in `git log`.
- No commit in this plan deleted a tracked file.
- The two untracked paths in the working tree (`.claude/settings.local.json`, `.gsd/`) are harness runtime output, predate this plan and are outside its `files_modified`; left untouched rather than widening scope.

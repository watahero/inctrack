---
phase: 01-the-net
plan: 03
subsystem: testing
tags: [lua, lupa, ashita, imgui, json, test-harness, stubs, upvalues, xfail, guard]

# Dependency graph
requires:
  - phase: 01-the-net plan 01
    provides: "make_host(), the Ashita host fakes, the stubbed pure-Lua json, lua_locals(), Result.xfail and the 'XFAIL ' / 'NOW PASSING ' markers"
  - phase: 01-the-net plan 02
    provides: "test_ui() (suite 9) and the FIX-03 expected failure — the first of the three the guard counts"
provides:
  - "test/run_tests.py — test_addon_shell(), suite 10, title 'addon: load, chat, settings, commands'"
  - "loaded_host(), shell_state(), shell_run(), begins(), phase_line() — the addon-shell fixture verbs"
  - "The FIX-01 expected failure, written as deltas in the cleared-phase count"
  - "The FIX-02 expected failure, written as a wall-clock gap applied to a saved run"
  - "EXPECTED_XFAILS and the main() guard that fails the run on any count but three"
affects: [02-the-fixes, 03-hardening, 04-performance]

actuals:
  tokens: 7382
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Defect assertions written as deltas and tolerances, never absolute expected values, so a fix satisfies them unedited"
    - "A phase-wide guard on the expected-failure count, summed across every suite in main()"
    - "The addon shell driven entirely through its registered handlers — no helper is called directly that the game would not call"

key-files:
  created: []
  modified:
    - test/run_tests.py

key-decisions:
  - "The addon-shell suite drives inctrack.lua only through its five handlers and the profile callback; file-scope state is read through host.addon but never used as an entry point"
  - "loaded_host() bundles require + tick(0) + fire('load'), because the shell does nothing at require time except register handlers"
  - "The pcall boundary is forced with a Lua table as e.message — a number coerces through the string metatable and would silently assert nothing"
  - "FIX-01 measures phases_cleared as three deltas rather than three absolute values, so any single-author scheme Phase 2 chooses satisfies it"
  - "FIX-01's first phase fixture is Phase #1 on purpose: reaching phase N means N-1 cleared, so Phase #2 would legitimately read 1"
  - "FIX-02 simulates the reload gap by moving the wall-clock stamp the save already carries, which is the only signal the addon could ever use"
  - "The guard sums xfails across all suites in main() rather than per suite, so it reads the same with and without chatlogs"
  - "Neither line the guard prints contains 'XFAIL' or 'FAILED', because the phase criteria count those substrings in this output"

patterns-established:
  - "loaded_host(player, profile): one call gives a fully booted addon with its load handler fired"
  - "Save-policy assertions read the host's save counter and recorded session strings, never the filesystem"
  - "A resume test round-trips through two hosts: one persists, a second is seeded with that exact string"

requirements-completed: [COVR-02, COVR-03, COVR-04]

coverage:
  - id: D1
    description: "inctrack.lua's load path — handler registration, the build banner, player-name resolution and resuming a run saved by a previous session — is asserted against the shipped addon behind the Ashita stub"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_addon_shell — registration, banner, resume round trip, corrupt-session discard, deferred player-name fetch"
        status: pass
    human_judgment: false
  - id: D2
    description: "The text_in pcall boundary is proven from outside the addon: an unreadable message produces exactly one complaint, propagates nothing, starts no run, and the event table comes back unmodified and unblocked"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_addon_shell — Lua table as e.message; 'parse error' count, lua_type(e.message), e.blocked, run unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "The MUST_SAVE policy — the only thing between a mid-run reload and a blank window for a whole phase — is driven by the injected clock and asserted at every step: 1 write after the run begins, still 1 for a kill count inside the throttle, 2 past it, 3 for a boon"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_addon_shell — save counter across begin / phase / phase+6s / boon, plus the decoded session string"
        status: pass
    human_judgment: false
  - id: D4
    description: "The profile-switch handler is asserted: a character change drops the old run, clears the old name, adopts the new settings table and restores that character's own saved run; a switch carrying no table saves and changes nothing"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_addon_shell — switch_profile() with a second character's session, then profile_callback(None)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every /incursion subcommand (bare toggle, reset, lock, auto, usage), the /inc alias, a command that is not ours, all five outcomes of visible(), and the render gate from both sides"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_addon_shell — the command surface, visible() across run/auto/override, d3d_present with visible() false and true"
        status: pass
    human_judgment: false
  - id: D6
    description: "FIX-01 and FIX-02 are two named expected failures inside the state suite, phrased in user terms and written so Phase 2 flips them green without editing the assertions"
    requirement: COVR-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#test_state_units — res.xfail on the cleared-phase delta and on the restored clock/elapsed/bonus triple"
        status: pass
      - kind: manual_procedural
        ref: "PLAN 01-03 Task 3 <human-check> — each of the three reported lines read as a sentence a player would recognise, with no file name, identifier or line number"
        status: pass
    human_judgment: true
    rationale: "Whether a defect line is legible to a reader who has never opened the source is a judgment about English, not a property a test can check. The automated block only proves the absence of banned code terms."
  - id: D7
    description: "The failure list is exactly three entries and the run says so; a fourth or a missing one fails the run, while expected failures alone still exit 0"
    requirement: COVR-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#main — EXPECTED_XFAILS summed across suites; '3 known defects (expected until Phase 2)'"
        status: pass
      - kind: manual_procedural
        ref: "EXPECTED_XFAILS temporarily set to 2: guard line printed, exit code 1; restored to 3, exit 0"
        status: pass
    human_judgment: false
  - id: D8
    description: "Both new suites report non-zero check counts with no chatlogs and no Ashita install, closing COVR-04"
    requirement: COVR-04
    verification:
      - kind: unit
        ref: "python test/run_tests.py — header reads 'chatlogs: none', ui reports 53 checks, addon reports 81 checks, PASS, exit 0"
        status: pass
    human_judgment: false
  - id: D9
    description: "The addon source is byte-identical and no pre-existing suite lost a check"
    verification:
      - kind: unit
        ref: "git diff --quiet -- inctrack/ && git diff --cached --quiet -- inctrack/"
        status: pass
      - kind: unit
        ref: "python test/run_tests.py <chatlogs> — 12961 checks, 0 FAILED lines, exactly 3 XFAIL lines, exit 0"
        status: pass
    human_judgment: false

# Metrics
duration: 16min
completed: 2026-08-29
status: complete
---

# Phase 1 Plan 03: The Net Summary

**`inctrack.lua` — 301 lines at zero automated coverage — now runs outside the game across 81 checks covering registration, the `text_in` pcall boundary, the `MUST_SAVE` write policy, the resume round trip, player-name resolution, the profile switch, every `/incursion` subcommand and both sides of the render gate; and the phase closes with exactly three named, red, player-legible defect lines and a guard that fails the run on any other number.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-29T01:30:00Z
- **Completed:** 2026-08-29T01:46:00Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- **The second total coverage gap is closed.** The addon shell had never been executed by a test. Suite 10 reports **81 checks** and reads no chatlogs and needs no Ashita install — which, together with the ui suite's 53, is what closes COVR-04.
- **The two paths most likely to lie to the player are pinned.** The profile-switch handler now provably drops the old character's run and name and restores the new character's own saved run; the `MUST_SAVE` policy now provably writes a run's start, its objectives and its boons the moment they land, and throttles only the kill counts that arrive constantly.
- **The `text_in` read-only guarantee is tested for the first time.** `inctrack.lua:156` promises the message is never modified or blocked and that a parse failure never takes the chat handler down. All three halves of that promise are now assertions, with the failure forced from outside the addon by a Lua table as `e.message`.
- **The phase's three confirmed defects are three red lines**, each a sentence a player would recognise, and `main()` prints `3 known defects (expected until Phase 2)` and fails the run on any other count. The run still exits 0.
- **`inctrack/` is byte-identical.** `git diff --quiet -- inctrack/` and `--cached` both exit 0 after every commit.

## Task Commits

1. **Task 1: The addon-shell suite — load, text_in, persistence, profiles** — `26f9420` (test)
2. **Task 2: The command surface, visible(), and the render gate** — `1efcaed` (test)
3. **Task 3: FIX-01 and FIX-02 as named expected failures, and the exactly-three guard** — `e7efb4f` (test)

## Files Created/Modified

- `test/run_tests.py` (+598 / -5) — `SHELL_INSTANCE` / `SHELL_OTHER` / `SHELL_BOON`, `begins()`, `phase_line()`, `loaded_host()`, `shell_state()`, `shell_run()`, `test_addon_shell()`, the two `res.xfail` entries in `test_state_units`, `EXPECTED_XFAILS`, the `main()` guard, the `main()` wiring for suite 10, and an updated module docstring.

---

## What this plan produced, for Phase 2

### The check count, both run modes

With no chatlogs and no Ashita install:

```
  state: objectives, bonus, recovery               35 checks  ok (2 known defects)
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             21 checks  ok
  persistence: json round trip                      0 checks  ok      (skipped)
  ui: helpers, layout contract, render             53 checks  ok (1 known defects)
  addon: load, chat, settings, commands            81 checks  ok

  3 known defects (expected until Phase 2)
```

The full run, against **127 logs / 2,943,937 chat lines**:

```
  parser: structural lines all parse            11819 checks  ok
  parser: generic tier matches nothing today        1 checks  ok
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               35 checks  ok (2 known defects)
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             21 checks  ok
  persistence: json round trip                     20 checks  ok
  ui: helpers, layout contract, render             53 checks  ok (1 known defects)
  addon: load, chat, settings, commands            81 checks  ok
```

**12,961 checks summed, 0 `FAILED` lines, exactly 3 `XFAIL` lines, exit 0.** Every
pre-existing per-suite count is exactly the figure plan 01-01 recorded; the state
suite is the one that moved, from 29 to 35, and only upward — four regular checks
and the two expected failures this plan added.

### The three known-defect messages, verbatim

The whole `Result.xfails` entry in each case. The report prints them after a
six-space indent and the `XFAIL ` marker pinned by plan 01-01. None contains a
file name, a line number or an identifier from the source.

1. `counted a bonus objective payout as a cleared phase -- the window went from 1 cleared to 2 without a phase boss dying`
2. `clock was optimistic by the reload gap after a reconnect -- ten minutes away and the window came back claiming 5280 seconds left instead of 4680, 120 seconds elapsed instead of 720, and a bonus objective that had already run out`
3. `the window asks for a close button and then ignores it -- clicking close leaves the window on screen`  *(plan 01-02's)*

The numbers in messages 1 and 2 are computed from the run, so when a Phase-2 fix
moves them the message moves with them.

### Where each expected failure lives, and the rule about editing it

| Defect | File | Line (at `e7efb4f`) | Suite | Owner |
|---|---|---|---|---|
| FIX-01 — a bonus payout counted as a cleared phase | `test/run_tests.py` | `654` (`res.xfail`) | `state: objectives, bonus, recovery` | this plan |
| FIX-02 — the clock not aged by the reload gap | `test/run_tests.py` | `707` (`res.xfail`) | `state: objectives, bonus, recovery` | this plan |
| FIX-03 — the close button that does nothing | `test/run_tests.py` | `1773` (`res.xfail`) | `ui: helpers, layout contract, render` | plan 01-02 |

**Phase 2 must flip all three green without editing a character of any
`res.xfail(...)` condition or message.** That is the entire point of the
coverage-first ordering: an assertion that is adjusted while the fix is written
proves the assertion was adjustable, not that the fix works. Each was written for
that constraint:

- **FIX-01** measures `phases_cleared` as **three deltas**, not three absolute
  numbers: 0 at the first phase line, +1 across a boss kill, **+0 across a bonus
  payout**. Any scheme that makes a single writer the author of the count
  satisfies it. A regular `check` on the points total (114) sits alongside, so a
  "fix" that simply stops applying the second award is caught rather than
  mistaken for the real thing.
- **FIX-02** applies the ten-minute gap by moving `saved_at` — the wall-clock
  stamp the addon already writes at `state.lua:556` and already reads for the
  staleness check at `:597`, and which is precisely the correction term the
  restore path never applies. The entry asserts all three consequences together:
  time left 600 lower, elapsed 600 higher, and the bonus that had 300 seconds
  left at save time gone rather than shown. Both clock comparisons carry a
  **two-second tolerance**, because `saved_at` is real wall time and a second can
  tick between serialise and restore.
- **FIX-03** is a disjunction over the recorded `Begin` call shape; see
  `01-02-SUMMARY.md`.

### The guard, and what trips it

`EXPECTED_XFAILS = 3` sits next to the report markers with a comment naming all
three defects. `main()` sums `len(s.xfails)` across every suite after they have
reported, prints

```
  3 known defects (expected until Phase 2)
```

and, when the total is anything else, prints a second line naming both numbers
and sets the exit code to 1. Neither line contains `XFAIL` or `FAILED`, so the
phase's own grep-based criteria are unaffected by the guard's own output.

**Demonstrated, not asserted:** with the constant temporarily set to 2 the run
printed `guard: this phase closes on exactly 2 known defects; the run reported 3`
and exited **1**; restored to 3 it exits **0** and prints `PASS`.

All three entries live in suites that always execute, so the guard reads
identically with and without chatlogs.

### Fixture verbs the next plan inherits

| Verb | What it gives you |
|---|---|
| `loaded_host(player=PLAYER, profile=None)` | a host with `inctrack.lua` required, the clock at 0 and `load` fired — a fully booted addon |
| `shell_state(host)` / `shell_run(host)` | the shell's `State` instance, and its current run record |
| `begins(instance)` / `phase_line(n, cur, mx, instance)` | the two chat lines every scenario starts from |
| `SHELL_INSTANCE` / `SHELL_OTHER` / `SHELL_BOON` | invented content in the server's established wording |

---

## Decisions Made

- **The shell is driven only through its handlers.** `host.addon` is used to
  *read* `incursion`, `visible` and the settings table, and to set `override`
  where a scenario needs a pre-existing manual hide — but no test calls
  `reset()` or `persist()` directly. Everything that could happen in game
  happens through `fire('load')`, `fire('text_in')`, `fire('command')`,
  `fire('d3d_present')`, `fire('unload')` and the profile callback.
- **A Lua table, not a number, is the pcall fixture.** Numbers share the string
  metatable in Lua, so `(5):strip_colors()` coerces and succeeds; the handler
  would then run to completion, `parser.parse` would return nil, and no
  `parse error:` line would ever be produced — the test would pass while
  asserting nothing. The reason is commented in the suite so a future reader
  does not "simplify" it back.
- **`Phase #1` is load-bearing in the FIX-01 fixture.** `state.lua:198` reads
  `if e.phase and e.phase - 1 > run.phases_cleared`, so `Phase #2` would set the
  count to 1 and turn the opening regular `check` red against a *correct*
  implementation — which under this plan's hard rule 2 would have meant halting
  and reporting a fourth defect that does not exist.
- **The unknown-player acceptance window is deliberately unasserted.**
  `state.lua:360-363` accepts any player's points while the name is unknown.
  That is a recorded risk with no v1 requirement, so the suite asserts only that
  the name resolves and that once it is known a foreign player's award is
  rejected. Asserting it in either direction would have blessed or condemned
  behaviour this milestone has not decided about.
- **Structurally-invalid restore is left alone.** The suite proves a non-json
  session is discarded whole. Well-formed json of the wrong shape reaching
  arithmetic is HARD-05 and belongs to Phase 3; a test for it here would have
  been a fourth red line and would have broken the guard.
- **The guard sums across suites rather than checking each suite's count.** Per-
  suite expectations would have to be rewritten every time a defect moved
  between suites; the total is the thing the phase criterion actually states.
- **The shared injected clock is set and restored around the FIX-02 block.**
  `test_state_units` runs before the timer suites on the same runtime, so the
  block sets `__clock` explicitly and returns it to 0 — the convention those
  suites already follow. This is why their check counts are unchanged.

## Deviations from Plan

None — plan executed as written.

Two points where the plan's prose and the shipped code differ slightly were
resolved in the code's favour, and neither weakened an assertion:

- The plan says an unrecognised subcommand "prints the four usage lines and
  nothing else". The handler prints a `Usage:` header **and** four command
  lines, five in total (`inctrack.lua:268-272`). The suite asserts five lines,
  that the first is the header, that the other four each name the command, and
  — the substantive half of the criterion — that nothing else happened: no
  reset, no setting changed, no disk write, run intact.
- The plan's precondition names 126 `*.log` files. The directory holds **127**;
  the author's chatlog corpus keeps growing, which is the drift plan 01-01
  recorded. The precondition is met in substance — the directory exists and the
  full run is a real one — and the check count is read as "no pre-existing suite
  went down", not as a literal constant.

## Issues Encountered

**None.** Every regular check written for this plan was green on its first run,
so no fourth defect was found and no assertion had to be reconsidered. The three
red lines are the three intended ones.

The check-count question raised by plan 01-01 is settled for the phase: the sum
is now **12,961**, comfortably above the ROADMAP's literal 12,841, but the
per-suite reading remains the correct one — the sum is a property of a private,
still-growing chatlog corpus and will keep drifting every time the author plays.

## Requirement status

- **COVR-01** (`ui.lua` asserted under a stubbed ImGui) — completed by plan 01-02.
- **COVR-02** (`inctrack.lua` asserted under a stubbed Ashita host) — **complete.**
  Every item `01-CONTEXT.md` lists is asserted: event registration, the `text_in`
  handler and its `pcall` boundary, settings load/save and the `MUST_SAVE`
  throttle, load-time resume, player-name resolution, every `/incursion`
  subcommand, `visible()`'s override-vs-auto logic, the render gate and the
  profile-switch handler.
- **COVR-03** (a regression test per confirmed defect) — **complete.** All three
  exist, each in the suite it belongs to, each red, each named in user terms, and
  the count is guarded.
- **COVR-04** (the new suites run with no chatlogs) — **complete.** `ui:` reports
  53 checks and `addon:` reports 81 on a machine with neither chatlogs nor an
  Ashita install; the header still reads `chatlogs: none`.

## Verification

This is the phase's closing verification. All five hold.

| # | Check | Result |
|---|---|---|
| 1 | `python test/run_tests.py` | `PASS`, exit 0, header `chatlogs: none (...)`, `ui:` 53 checks, `addon:` 81 checks |
| 2 | `python test/run_tests.py "<chatlogs>"` | `PASS`, exit 0 |
| 3 | summed checks / `grep -c FAILED` | **12961** (≥ 12841) / **0**; suite 2 still reports every real line handled by a specific pattern |
| 4 | `grep -c XFAIL` / `grep -c "3 known defects (expected until Phase 2)"` | **3** / **1** |
| 5 | `git diff --quiet -- inctrack/` and `--cached` | both exit 0 |

Additionally: `grep -c "\.xfail(" test/run_tests.py` is **3**; the three messages
are distinct and contain no file name, line number or source identifier; and
setting `EXPECTED_XFAILS` to 2 makes the run print a guard failure and exit 1.

## Known Stubs

None. Nothing in this plan is a placeholder: every check asserts against the
shipped Lua through the host stubs, and the three red lines are intended
expected failures with the guard that keeps them honest, not unfinished work.

## User Setup Required

None — no external service configuration required. Both new suites deliberately
need neither the author's chatlogs nor a local Ashita install; the deep replay
suites need them exactly as before.

## Next Phase Readiness

**Phase 2 is unblocked, and the net it was ordered before is now in place.**

- **The one rule Phase 2 must honour:** flip all three expected failures green
  **without editing their assertions**. Locations, and why each survives a
  legitimate fix, are in the table above.
- **A known consequence, already recorded as a blocker:** suite 3
  (`state: run reconstruction`, 888 checks) asserts `phases_cleared == number of
  points events`, which encodes the FIX-01 defect. Fixing FIX-01 turns suite 3
  red until its independent recomputation is re-derived from boss kills. That is
  expected, not a regression, and it is Phase 2's work.
- **`EXPECTED_XFAILS` is the knob Phase 2 turns down.** Each fix moves an entry
  from `xfails` to `fixed`, which prints on a `NOW PASSING ` line — carrying
  neither `XFAIL` nor `FAILED` — and the guard then fails the run until the
  constant is decremented to match. That is deliberate: it forces the fix and the
  bookkeeping into the same commit.
- **The addon-shell suite is the harness Phase 4 needs.**
  `host.strip_colors_calls` is already counted by the stub, so PERF-01's
  "cheap rejection before any per-line cost" can be measured through
  `fire('text_in')` without new machinery. Phase 3's HARD-01 can likewise drive
  `fire('d3d_present')` and read `host.imgui.balance()` after an induced error.
- **The layout comment at `ui.lua:15-26` is still seven rows out of date**
  (table in `01-02-SUMMARY.md`). It is a documentation change to a file this
  phase may not touch; it belongs to Phase 2 or later.

---
*Phase: 01-the-net*
*Completed: 2026-08-29*

## Self-Check: PASSED

Every file this summary claims exists on disk (`test/run_tests.py`,
`.planning/phases/01-the-net/01-03-SUMMARY.md`) and all three task commit
hashes resolve in `git log` (`26f9420`, `1efcaed`, `e7efb4f`).

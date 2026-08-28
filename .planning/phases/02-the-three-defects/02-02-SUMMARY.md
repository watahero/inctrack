---
phase: 02-the-three-defects
plan: 02
subsystem: ui
tags: [lua, imgui, dead-code, render-snapshots, regression-testing, xfail, deployment]

# Dependency graph
requires:
  - phase: 01-the-net
    provides: "the ten-suite harness, the six whole-window render snapshots, the recording ImGui stub with its honest close switch, and the FIX-03 red line written as a disjunction over both legitimate fixes plus the precondition that stops a blank frame satisfying it"
  - phase: 02-the-three-defects
    plan: 01
    provides: "FIX-01 and FIX-02 converted, EXPECTED_XFAILS already down to 1, and /tmp/inctrack-assert-integrity.py -- the paren-scanning byte-identity audit this plan extends to all four protected assertions"
provides:
  - "ui.render calls Begin with the window title and the flags -- no close box asked for, none waited on"
  - "the six render snapshots re-pasted for the two-argument Begin call shape"
  - "a pin check that fixes FIX-03's disjunction to its first term, so the plumbing cannot quietly return"
  - "EXPECTED_XFAILS at 0 and EXPECTED_DEFECTS empty, with the guard proven to reject a non-empty set"
  - "/tmp/inctrack-assert-integrity.py covering FIX-01, FIX-02, FIX-03 and the FIX-03 precondition"
  - "the fixed addon deployed byte-identical to the live Ashita install"
affects: [03-hardening, 04-cost-and-docs]

actuals:
  tokens: 41000
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "a dead affordance is removed, not completed -- the shipped layout decision outranks a docs description of a control that was never drawn"
    - "a disjunctive red line is retired with a companion check that pins which branch the fix took, so the other branch cannot satisfy it later"
    - "an empty EXPECTED_DEFECTS is proven live with a throwaway xfail rather than assumed to still guard"

key-files:
  created: []
  modified:
    - inctrack/ui.lua
    - inctrack/inctrack.lua
    - test/run_tests.py

key-decisions:
  - "The plumbing was removed rather than the title bar restored -- the compact 1.1.0 layout is a shipped feature and the ImGui stub has only the fourteen entry points ui.lua already uses"
  - "render keeps returning opts.visible unconditionally; two untouchable Phase-1 assertions read that return value"
  - "The recorder's close switch stays even though it can no longer fire: it is what the FIX-03 regression check arms"
  - "The guard's empty-set failure message reads 'empty' rather than an empty string, so a future non-empty set produces a legible line"

patterns-established:
  - "The negative control is run before the verdict is trusted, once per newly audited item, not once per script"
  - "A live-install deploy is preceded by a divergence diff against the baseline the install was copied from, so an author's hand edit is discovered rather than overwritten"

requirements-completed: [FIX-03]

coverage:
  - id: D10
    description: "A frame drawn with the recorder's close switch armed leaves the window on screen, because the window asks for no close control at all"
    requirement: FIX-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui: helpers, layout contract, render -- 'the window asks for a close button and then ignores it -- clicking close leaves the window on screen' (the converted FIX-03 check)"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#ui: helpers, layout contract, render -- 'the close-button case drew no window at all, so nothing was proved about the close button either way' (the precondition)"
        status: pass
    human_judgment: false
  - id: D11
    description: "The disjunction is satisfied by its first term and pinned there, so reinstating the close box and hiding on the click cannot satisfy the original assertion through its other branch"
    requirement: FIX-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui: helpers, layout contract, render -- 'the window asks for a close control it can never show -- it is drawn without a title bar, so the player has nothing to click'"
        status: pass
    human_judgment: false
  - id: D12
    description: "All six windows render exactly as before apart from the Begin line, the ImGui stacks stay balanced, and render still returns the visibility it was given"
    requirement: FIX-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui -- six 'is not the one the layout contract describes' checks, six stack-balance checks, six 'hid itself although nobody asked it to' checks, and 'the window changed its own visibility with no run to show' for both True and False"
        status: pass
      - kind: other
        ref: "extraction diff of the six expected_window literals between b8a19fa and the working tree -- old-side changed: 7, new-side changed: 7"
        status: pass
    human_judgment: false
  - id: D13
    description: "The run reports zero known defects, zero XFAIL lines and zero NOW PASSING lines, and still exits 0, on the default backend and on luajit21"
    verification:
      - kind: integration
        ref: "python test/run_tests.py \"C:\\Games\\CatsEyeXI\\catseyexi-client\\Ashita\\chatlogs\" and the same under INCTRACK_LUA=luajit21"
        status: pass
    human_judgment: false
  - id: D14
    description: "The empty EXPECTED_DEFECTS guard rejects a defect appearing rather than silently passing"
    verification:
      - kind: other
        ref: "negative control -- a throwaway res.xfail(False, ..., \"FIX-99\") made the run print both guard lines and exit 1"
        status: pass
    human_judgment: false
  - id: D15
    description: "All four protected Phase-1 assertions are byte-identical to what Phase 1 wrote"
    verification:
      - kind: other
        ref: "python /tmp/inctrack-assert-integrity.py (exit 0; two negative controls, one per newly audited item, each made it exit 1)"
        status: pass
    human_judgment: false
  - id: D9
    description: "In-game confirmation that a mid-run /addon reload comes back with an instance clock that agrees with the server's next 'You have N minutes remaining' line"
    verification: []
    human_judgment: true
    rationale: "Phase criterion 4 needs a human inside a live Incursion on CatsEyeXI. The suite can prove the arithmetic against a simulated gap; only a real reload against a real server clock exercises the two clocks the addon mixes. The fixed build is deployed to the live install so the check is runnable."

duration: 22min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 02: The Dead Close Path Summary

**The window stopped asking ImGui for a close control it can never draw and the addon shell stopped waiting for a click on it; the six render snapshots moved by one substring each, FIX-03 went green with its Phase-1 bytes untouched, and the milestone's known-defect count is now zero on both backends.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-28T23:13:00Z
- **Completed:** 2026-08-28T23:35:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **FIX-03.** `ui.lua` no longer hoists a one-element boolean box, no longer re-seeds it each frame, no longer passes it to `Begin`, and no longer inspects it after `End`. `Begin` now takes the window title and the flags — the second of the two call shapes the recorder already knew — and `render` returns `opts.visible` unconditionally, exactly as it always did on the no-run path.
- **The dead branch went with it.** `inctrack.lua`'s frame handler calls `render` for its effect; the `shown == false` branch that treated a close click as a manual hide is gone, along with the comment above it. `visible()` and the override logic were not touched.
- **Nothing in game changed, which was the point.** The flag sum is still `NoFocusOnAppearing + AlwaysAutoResize + NoScrollbar + NoTitleBar` plus `NoMove` when locked; the tight item spacing, the width spacer and the `GetCursorPosX` left edge are byte-for-byte what they were. No new ImGui entry point is called — the stub implements exactly fourteen and an unknown one raises inside `render` (IN-09).
- **Exactly seven snapshot lines moved across the whole phase.** Six `Begin` lines lost `p_open=[true]`; the seventh is `WINDOW_FINISHED`'s `TextColored text '0'` → `'1'`, which plan 02-01 landed. The extraction diff reports `old-side changed: 7  new-side changed: 7` — equal counts, so every one was a substitution and nothing was added or removed. Every other line of all six literals is unchanged, and `NoTitleBar` still appears on each.
- **The disjunction is pinned to the branch the fix took.** FIX-03 was written as `(not offered_close) or still_shown is False`, deliberately true under either legitimate fix. A new check asserts `not offered_close` on its own, so a later change that reinstated the close box and then hid the window on the click would satisfy the original line while failing the new one. That check was written first and confirmed red before the fix landed.
- **The bookkeeping went to zero in the same commit as the fix**, and the empty set was proven to still guard: a throwaway `res.xfail(False, ..., "FIX-99")` made the run print `guard: this phase closes on exactly 0 known defects; the run reported 1` and `guard: the failure list must be exactly empty; it is FIX-99`, and exit 1. `EXPECTED_DEFECTS = set()` is not a slack expectation — `main()` compares sorted lists, so any name at all mismatches `[]`.
- **The binding rule of the phase is proven for all four protected assertions.** The audit script now covers FIX-01, FIX-02, FIX-03 and FIX-03's precondition, and exits 0. Two negative controls were run first, one per newly audited item.
- **Green on both backends** with identical per-suite counts, zero `XFAIL` lines, zero `NOW PASSING` lines and zero `FAILED` lines.
- **The fixed addon is deployed** to `...\Ashita\addons\inctrack\`, byte-identical to the repository, so the one criterion the suite cannot close is runnable by a human.

## Task Commits

1. **Task 1 (RED): pin that the window offers no close control at all** — `373d2f8` (test). Written before the implementation and confirmed failing: `ui: helpers, layout contract, render  56 checks  FAILED (1)`.
2. **Task 1 (GREEN): stop asking for a close control the window can never draw** — `459f3ef` (fix). The two Lua files, the six re-pasted literals, the FIX-03 conversion and both bookkeeping constants, in one commit.
3. **Task 2: the phase-closing audit** — no repository files modified, by design. Its artefacts are the two verbatim reports, the whole-phase hunk classification and the extended audit script, all reproduced below.
4. **Task 3: deploy and record the in-game check** — no repository files modified. The four `.lua` files were copied to the live Ashita install; the open human-verification item is recorded below.

No REFACTOR commit: the GREEN change is a deletion, and there was nothing left to clean up.

## Files Created/Modified

- `inctrack/ui.lua` — the hoisted close box, its per-frame reseed, its position in the `Begin` argument list and the branch that read it after `End` are all gone; the `ui.render` doc comment rewritten to say what is now true. Net −6 lines.
- `inctrack/inctrack.lua` — the frame handler no longer captures the render result, and the unreachable manual-hide branch and its comment are gone. Net −5 lines.
- `test/run_tests.py` — six window literals re-pasted; FIX-03 converted to `res.check` with its condition and message byte-identical; the pin check added; `EXPECTED_XFAILS` 1 → 0 and `EXPECTED_DEFECTS` → `set()`; the guard's printed line, its empty-set message, the constants' comment and the module docstring brought up to date.
- `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\*.lua` — the four repository files copied over. Not a repository path; nothing under `inctrack/` was modified by the deploy.
- `/tmp/inctrack-assert-integrity.py` — extended from two audited items to four. Deliberately outside the repository, so it never enters a commit; reproduced verbatim below.

## Decisions Made

Every decision locked in `02-CONTEXT.md` was honoured without re-opening. Beyond those, three were Claude's discretion under the plan:

- **The pin check reads `not offered_close` alone**, placed directly after the converted check and phrased as what the player would face: *"the window asks for a close control it can never show — it is drawn without a title bar, so the player has nothing to click."* It is the assertion the recorder's close switch now exists to serve.
- **The guard's failure message gained `or "empty"` on the expected side.** With `EXPECTED_DEFECTS` empty, `", ".join(sorted(...))` renders as nothing, and the line would have read *"the failure list must be exactly ; it is FIX-99"*. The negative control is what surfaced this; the fix makes the line legible for whoever trips it next.
- **The `render` doc comment names no deleted identifier.** The acceptance grep for `ARG_OPEN` is unfiltered, so a mention in prose would have failed it. The comment states the return contract, the absence of a close affordance and the slash-command dismiss without naming the table that used to carry it.

## Deviations from Plan

None — plan executed exactly as written. No auto-fix rule was invoked; no architectural question arose.

Two incidental notes, neither a deviation:

- The plan's Task 3 precondition asked for a pre-copy divergence check. The live install turned out to use CRLF line endings while the repository uses LF, so a plain `diff -r` reported every line of every file as changed. Stripping trailing CR showed all four files identical to `b8a19fa` — the live folder is a faithful copy of the end-of-Phase-1 source, not a divergent working copy, and no author hand-edit was overwritten. The deploy normalised the live files to LF; Lua reads both.
- The audit script lives at Git Bash's `/tmp`, which is `C:\Users\badr\AppData\Local\Temp`. Invoking it as `python /tmp/inctrack-assert-integrity.py` works because the shell rewrites the argument; a Python string literal `/tmp/...` does not resolve.

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
  ui: helpers, layout contract, render             56 checks  ok
  addon: load, chat, settings, commands            83 checks  ok

  0 known defects

PASS
=== exit: 0 ===
FAILED lines: 0
NOW PASSING lines: 0
XFAIL lines: 0
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
  ui: helpers, layout contract, render             56 checks  ok
  addon: load, chat, settings, commands            83 checks  ok

  0 known defects

PASS
=== exit: 0 ===
FAILED lines: 0
NOW PASSING lines: 0
XFAIL lines: 0
```

`diff` of the two reports' `checks` lines is empty: the backends agree line for line.

### Per-suite counts against the Phase-1 floor

| Suite | Phase-1 floor | Default backend | luajit21 | Verdict |
|---|---|---|---|---|
| parser: structural lines all parse | 11819 | 11819 | 11819 | held |
| parser: generic tier matches nothing today | 1 | 1 | 1 | held |
| state: run reconstruction | 888 | 888 | 888 | held |
| state: objectives, bonus, recovery | 38 | 49 | 49 | rose by 11 (plan 02-01) |
| adaptability: unseen content still tracked | 20 | 20 | 20 | held |
| disconnect: stale progress is not trusted | 23 | 23 | 23 | held |
| timers: countdown, linger, staleness | 21 | 21 | 21 | held |
| persistence: json round trip | 25 | 25 | 25 | held |
| ui: helpers, layout contract, render | 55 | 56 | 56 | rose by 1 (the pin check) |
| addon: load, chat, settings, commands | 83 | 83 | 83 | held |

No suite fell, on either backend. The generic tier still reports `all real lines handled by a specific pattern` — nothing in today's 2,944,071 chat lines fell through to a generic pattern, which is the same verdict Phase 1 recorded.

**Zero content knowledge.** A grep over `inctrack/` for instance, boss, mob, objective and difficulty names returns only pre-existing hits: message-shape examples in `parser.lua`'s pattern comments, the layout sketch in `ui.lua`'s file header, and the identifier `difficulty` as a run-record field name. This plan's Lua diff added four lines — the rewritten doc comment and the two-argument `Begin` call — and none of them names any content.

## Hunk-by-Hunk Classification of `git diff -U0 b8a19fa -- test/run_tests.py`

The whole phase, superseding plan 02-01's own table. `git diff -U0 b8a19fa -- test/run_tests.py | grep -c "^@@"` reports **32**. Every one is on the allowed list; no row reads "unclassified".

| # | Hunk | What changed | Classification |
|---|---|---|---|
| 1 | `@@ -36 +36 @@` | "are recorded" → "were recorded" | module docstring |
| 2 | `@@ -38,13 +38,16 @@` | the three defects restated as fixed, the byte-identity rule stated, the guards described as empty | module docstring |
| 3 | `@@ -322,2 +325,3 @@` | "Three, exactly" → "None are left" | bookkeeping constants' comment |
| 4 | `@@ -325,3 +329,3 @@` | the three list entries gain their defect ids | bookkeeping constants' comment |
| 5 | `@@ -329,4 +333,5 @@` | "A fourth" → "Zero is the answer from here on"; `EXPECTED_XFAILS = 3` → `0` | bookkeeping constant |
| 6 | `@@ -339,2 +344,3 @@` | `EXPECTED_DEFECTS = {"FIX-01","FIX-02","FIX-03"}` → `set()`, with the note that an empty set is not a slack one | bookkeeping constant |
| 7 | `@@ -499 +505,8 @@` | `verify_run`'s cleared-count condition, plus its derivation comment | re-derivation of a pre-Phase-1 assertion (1 of 3) |
| 8 | `@@ -501 +514 @@` | that same check's failure message naming `want_cleared` | re-derivation of a pre-Phase-1 assertion (1 of 3, continued) |
| 9 | `@@ -594 +607,2 @@` | the points-are-ours-only fixture's cleared count `1` → `0` | re-derivation of a pre-Phase-1 assertion (2 of 3) |
| 10 | `@@ -720 +734 @@` | `res.xfail(` → `res.check(` on the FIX-01 line | callee swap (FIX-01) |
| 11 | `@@ -723,2 +737 @@` | the trailing `"FIX-01"` argument dropped | dropped defect id (FIX-01) |
| 12 | `@@ -733,0 +747,45 @@` | the end-to-end run, the bare payout, and the late join | new fixtures after the converted FIX-01 check |
| 13 | `@@ -782 +840 @@` | `res.xfail(` → `res.check(` on the FIX-02 line | callee swap (FIX-02) |
| 14 | `@@ -790,2 +848,54 @@` | the trailing `"FIX-02"` argument dropped, then the surviving bonus, the still-desynced assertion and the future stamp | dropped defect id (FIX-02) + new fixtures after the converted FIX-02 check |
| 15 | `@@ -1036 +1146,3 @@` | back-while-the-boss-is-up: `3` → `2`, message rewritten | re-derivation of a pre-Phase-1 assertion (3 of 3) |
| 16 | `@@ -1250 +1362,4 @@` | bonus-expiry equality → `<= 1`, with its reason | persistence tolerance (1 of 2) |
| 17 | `@@ -1252 +1367,2 @@` | time-left equality → `<= 1` | persistence tolerance (2 of 2) |
| 18 | `@@ -1416 +1532 @@` | `WINDOW_MID_PHASE`'s `Begin` line loses `p_open=[true]` | one of the six `Begin` lines |
| 19 | `@@ -1450 +1566 @@` | `WINDOW_BOSS_UP`'s `Begin` line | one of the six `Begin` lines |
| 20 | `@@ -1477 +1593 @@` | `WINDOW_BONUS`'s `Begin` line | one of the six `Begin` lines |
| 21 | `@@ -1526 +1642 @@` | `WINDOW_RECONNECTED`'s `Begin` line | one of the six `Begin` lines |
| 22 | `@@ -1558 +1674 @@` | `WINDOW_FINISHED`'s `Begin` line | one of the six `Begin` lines |
| 23 | `@@ -1567 +1683 @@` | `WINDOW_FINISHED`'s `TextColored text '0'` → `'1'` | the single-character window value (plan 02-01) |
| 24 | `@@ -1582 +1698 @@` | `WINDOW_PERCENT`'s `Begin` line | one of the six `Begin` lines |
| 25 | `@@ -1904 +2020 @@` | section heading "as an expected failure" → "fixed" | comment above the converted check |
| 26 | `@@ -1906,6 +2022,7 @@` | the disjunction's rationale rewritten in the past tense, recording which branch the fix took | comment above the converted check |
| 27 | `@@ -1934,4 +2051,4 @@` | "The xfail below" → "The disjunction below" | comment above the precondition (the precondition itself is untouched) |
| 28 | `@@ -1942 +2059 @@` | `res.xfail(` → `res.check(` on the FIX-03 line | callee swap (FIX-03) |
| 29 | `@@ -1944,2 +2061,11 @@` | the trailing `"FIX-03"` argument dropped, then the pin check | dropped defect id (FIX-03) + the new fixture after the converted check |
| 30 | `@@ -2493,3 +2619,3 @@` | the guard's rationale comment, "these three" → "these, and the set is now empty" | the guard's comment |
| 31 | `@@ -2502 +2628 @@` | `"  %d known defects (expected until Phase 2)"` → `"  %d known defects"` | the guard's printed line |
| 32 | `@@ -2509 +2635 @@` | the expected side of the mismatch message gains `or "empty"` | the guard's failure line |

Hunks 14 and 29 each carry two allowed changes because `-U0` merges a dropped defect id with the fixture that immediately follows it; both are on the list.

`git diff --quiet b8a19fa -- inctrack/parser.lua` exits 0 — the parser was never touched in this phase. `git diff --quiet b8a19fa -- test/stubs.py` also exits 0: the recording stub is exactly what Phase 1 built, including its honest close switch.

Under `inctrack/`, the phase changed `state.lua` (plan 02-01), `ui.lua` and `inctrack.lua` (this plan), and nothing else.

## The Audit Verdict — All Four Protected Assertions

```
$ python /tmp/inctrack-assert-integrity.py; echo "audit exit: $?"
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  INTACT -- 225 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03  INTACT -- 178 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03-precondition  INTACT -- 147 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
VERDICT: all 4 audited assertions intact.
audit exit: 0
```

### The negative controls, run before that verdict was trusted

Two items are newly audited by this plan, so two controls were run — one each — and each was reverted with `git checkout -- test/run_tests.py` before the next.

**Control A** — one full stop added to the FIX-03 message:

```
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  INTACT -- 225 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03  EDITED -- the Phase-1 assertion text is no longer in test/run_tests.py
    --- FIX-03 (phase 1)
    +++ FIX-03 (working tree)
    @@ -1,3 +1,3 @@
     (not offered_close) or still_shown is False,
                   "the window asks for a close button and then ignores it -- "
    -              "clicking close leaves the window on screen"
    +              "clicking close leaves the window on screen."
FIX-03-precondition  INTACT -- 147 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
VERDICT: 1 of 4 audited assertions were edited. The binding rule of Phase 2 is broken.
audit exit: 1
```

**Control B** — one character changed in the FIX-03 precondition's message, which is audited by a different code path (it was never an expected failure, so it has no defect id to strip and its whole body is required):

```
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  INTACT -- 225 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03  INTACT -- 178 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03-precondition  EDITED -- the Phase-1 assertion text is no longer in test/run_tests.py
    --- FIX-03-precondition (phase 1)
    +++ FIX-03-precondition (working tree)
    @@ -1,3 +1,3 @@
     bool(begins),
                   "the close-button case drew no window at all, so nothing was "
    -              "proved about the close button either way"
    +              "proved about the close button either way!"
VERDICT: 1 of 4 audited assertions were edited. The binding rule of Phase 2 is broken.
audit exit: 1
```

An exit-0 verdict from a script that cannot fail proves nothing. Each newly audited item was made to fail on its own before the clean run was believed.

### The extended script, verbatim

At `/tmp/inctrack-assert-integrity.py` — Git Bash's `/tmp`, which resolves to `C:\Users\badr\AppData\Local\Temp`. Deliberately outside the repository, so it never enters a commit. Plan 02-01 wrote it for two items; this plan extended it to four by adding `FIX-03` to `AUDITED` and teaching `baseline_bodies()` a second extraction path for assertions that were ordinary checks in the baseline.

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

One audited item was never an expected failure. FIX-03's assertion is a
disjunction whose first term holds whenever no window was drawn at all, so a
frame that drew nothing would report the defect fixed; Phase 1 guarded that
with an ordinary `res.check(...)` precondition immediately above it. That
precondition is load-bearing for FIX-03's verdict and is audited on the same
terms -- except that nothing about it was permitted to change, so its whole
call body, callee token aside, must come through verbatim.

Run from anywhere inside the repository:

    python /tmp/inctrack-assert-integrity.py

Exit 0 means every audited assertion is intact. Exit non-zero prints a unified
diff of the Phase-1 text against the nearest thing now in the file.

All four items are audited as of plan 02-02, which is the whole of Phase 2.
"""

import difflib
import subprocess
import sys

BASELINE = "b8a19fa"
BASELINE_SUBJECT = "docs(01): mark Phase 1 complete"
TARGET = "test/run_tests.py"

XFAIL = "res.xfail("
CHECK = "res.check("

# The Phase-1 assertion text this run audits -- the whole of it. The three
# expected failures, one per confirmed defect, plus the ordinary check that
# stops FIX-03's disjunction being satisfied by a frame that drew nothing.
AUDITED = ("FIX-01", "FIX-02", "FIX-03", "FIX-03-precondition")

# Items that were plain `res.check(...)` calls in the baseline rather than
# expected failures, keyed by a substring of their Phase-1 message that
# identifies them uniquely in that file. These have no trailing defect id to
# drop, so the whole call body is required verbatim.
PRECONDITIONS = {
    "FIX-03-precondition":
        "the close-button case drew no window at all",
}


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
    """The Phase-1 condition-and-message text of every audited item.

    Expected failures give up their trailing defect-id argument, because a
    correct conversion drops it. Preconditions give up nothing: they were
    ordinary checks in the baseline and had to stay ordinary checks, so the
    whole body is required.
    """
    src = git("show", "%s:%s" % (BASELINE, TARGET))
    found = {}
    for _, call in calls(src, XFAIL):
        body = call[len(XFAIL):-1]
        kept, last = split_last_arg(body)
        ident = last.strip("\"'")
        if ident in AUDITED:
            found[ident] = kept
    for ident, needle in PRECONDITIONS.items():
        if ident not in AUDITED:
            continue
        hits = [call for _, call in calls(src, CHECK) if needle in call]
        if len(hits) != 1:
            print("%s: %d baseline checks match %r; the needle must "
                  "identify exactly one"
                  % (ident, len(hits), needle), file=sys.stderr)
            sys.exit(2)
        found[ident] = hits[0][len(CHECK):-1]
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
            print("%s  MISSING -- no such assertion in the baseline" % ident)
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

## The Seven Changed Snapshot Lines, Across the Whole Phase

```
$ git show b8a19fa:test/run_tests.py \
    | sed -n '/^WINDOW_.*expected_window("""/,/^""")/p' > /tmp/win_base.txt
$ sed -n '/^WINDOW_.*expected_window("""/,/^""")/p' test/run_tests.py > /tmp/win_cur.txt
$ diff /tmp/win_base.txt /tmp/win_cur.txt
3c3
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
34c34
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
56c56
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
100c100
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
126c126
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
135c135
<   TextColored text '0'
---
>   TextColored text '1'
144c144
< Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
---
> Begin 'inctrack###incursion_window' flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar

old-side changed: 7  new-side changed: 7
```

Seven lines, all `c` (substitution) and none `a` or `d`, with equal counts on both sides: the literals had lines swapped, never added or removed. Six are the `Begin` lines this plan changed; the seventh is `WINDOW_FINISHED`'s cleared-phase value, which plan 02-01 changed. `NoTitleBar` survives on every one of the six.

## OPEN — Human Verification Required (Phase 2 success criterion 4)

**This has not been run. It cannot be closed by the test suite.** It needs a human inside a live Incursion on CatsEyeXI. The fixed build is deployed to `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` so that it can be run.

> In game, in an Incursion, with the deployed build loaded:
>
> 1. Wait for a `You have N minutes remaining inside this Incursion.` line and note the time left the window shows.
> 2. `/addon reload inctrack`. Leave it a couple of minutes if the run allows.
> 3. Read the window's clock, then wait for the next `You have N minutes remaining` line.
>
> **PASS** when the window's clock agrees with that line to within a minute — the granularity the server reports.
> **FAIL** if the window is optimistic by roughly the downtime, which is the behaviour this phase removed.
>
> Also note, on the same reload: `Phases cleared` comes back at the value it had, and the window shows the reconnected warning.

The automated FIX-02 coverage from plan 02-01 stands on its own regardless — it proves the arithmetic against a simulated ten-minute gap, a surviving bonus and a future-stamped save. This check proves the same arithmetic against a real reload with a real server clock, which is the only place the two clocks the addon mixes can actually disagree.

## Deployment

The live install at `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` now holds the four repository `.lua` files.

**Pre-copy divergence check.** A plain `diff -r` reported every line of all four files as changed, because the live install used CRLF line endings and the repository uses LF. Compared with trailing carriage returns stripped, all four were **identical to `b8a19fa:inctrack/*.lua`** — the end-of-Phase-1 source. The live folder is a faithful copy of what was shipped, not a divergent working copy, and no author hand-edit was overwritten. The CRLF/LF difference is an artefact of how the files were originally copied; the deploy normalised them to LF, which Lua reads identically.

**Post-copy.** `diff -r` between `inctrack/` and the live install, excluding Ashita's own `config` and `settings` directories, reports no differences and exits 0. The directory listing is unchanged before and after — the same four `.lua` files, nothing added and nothing removed.

## Verification Evidence

| Plan verification step | Result |
|---|---|
| 1. `python test/run_tests.py` | `PASS`, exit 0, `  0 known defects`, zero `XFAIL` lines, zero `NOW PASSING` lines |
| 2. Full run against the chatlogs | `PASS`, exit 0, `FAILED` lines 0, every per-suite count at or above the Phase-1 floor |
| 3. `INCTRACK_LUA=luajit21` full run | identical verdict, identical per-suite counts |
| 4. `grep -c "ARG_OPEN" inctrack/ui.lua \|\| true` | `0` (was `4`) |
| 4. `grep -c "shown == false" inctrack/inctrack.lua \|\| true` | `0` (was `1`) |
| 4. `grep -c "p_open" test/run_tests.py \|\| true` | `0` (was `6`) |
| 4. `grep -c "NoTitleBar" inctrack/ui.lua` | `1` — the flag is still set |
| 5. `python /tmp/inctrack-assert-integrity.py` | FIX-01, FIX-02, FIX-03 and the FIX-03 precondition all intact, exit 0; two negative controls each exit 1 |
| 6. `git diff --quiet b8a19fa -- inctrack/parser.lua` | exit 0 |
| 7. In-game check | recorded above as OPEN, human-only, with its pass and fail conditions. **Not claimed as passed.** |

Task-level evidence:

| Check | Expected | Actual |
|---|---|---|
| `git diff --stat` for `459f3ef` | exactly the three planned files | `inctrack/inctrack.lua`, `inctrack/ui.lua`, `test/run_tests.py` |
| snapshot extraction diff | `old-side changed: 7  new-side changed: 7` | exactly that |
| `ui` suite check count | at least 55 | 56 |
| `addon` suite check count | at least 83 | 83 |
| RED gate before the fix | the pin check fails | `ui: helpers, layout contract, render  56 checks  FAILED (1)` |
| empty-set guard live | a new xfail fails the run | both guard lines printed, exit 1 |
| `git diff --quiet b8a19fa -- test/stubs.py` | exit 0 — the recorder is Phase 1's | exit 0 |

## TDD Gate Compliance

Task 1 was `tdd="true"` and the gate sequence is in the log:

- **RED** — `373d2f8` `test(02-02): pin that the window offers no close control at all`. Run before the fix: the ui suite reported `FAILED (1)` on the new check. The test did not pass unexpectedly.
- **GREEN** — `459f3ef` `fix(02-02): stop asking for a close control the window can never draw`. The suite returned to `ok` at 56 checks.
- **REFACTOR** — none. The implementation is a deletion; there was nothing to clean up, so no empty commit was made.

## Issues Encountered

- **Git Bash's `/tmp` is not Python's `/tmp`.** `python /tmp/inctrack-assert-integrity.py` works because MSYS rewrites the argument to `C:\Users\badr\AppData\Local\Temp\...`; a `/tmp/...` string literal inside a Python script resolves against the current drive and does not exist. Editing the script needed the Windows path; running it did not.
- **Nothing else.** The six windows matched on the first run after the substitution, which is the strongest evidence available that removing the plumbing changed the recorded call shape and nothing else about what the window draws.

## Carried Forward — Noted, Not Acted On

### Phase 3 (hardening)

- **HARD-01, containment of an error raised inside `render`.** T-02-05 stands as `transfer`. This plan only removed statements from `render` and added no call, so the raise surface strictly shrank — but an error raised mid-render still escapes into `d3d_present` with the ImGui window and style-var stacks unbalanced, and every frame drawn after it is corrupted. The six stack-balance assertions in the ui suite are the net that will catch a fix here.
- **The `right_text` finding.** `Complete 48m 44s` stops right-aligning once the instance name plus difficulty runs past the target x, because the do-not-overprint branch fires. Correct as written; a conscious Phase 3 decision.

### Phase 4 (cost and docs)

- **DOC-01: `docs/design.md` describes a title-bar close button driving visibility.** That description is now false in two ways — the window has had no title bar since 1.1.0, and as of this plan it does not even ask for the box. The docs should say what is true: the window auto-hides thirty seconds after a run ends, and `/incursion` (or `/inc`) is the manual dismiss.
- **DOC-01: the stale layout comment at `ui.lua:15-26`.** Seven rows out of date, per the Phase-1 review. Untouched here; the doc comment this plan rewrote is `ui.render`'s, further down the file.
- **The per-frame options table.** `inctrack.lua`'s frame handler still builds `{ visible = ..., locked = ... }` fresh on every `d3d_present`, sixty times a second. This plan removed the local that captured the return value but left the table allocation, which is out of scope here and is exactly the kind of thing PERF is for.

### The recorder's close switch

`stubs.imgui.arm_close()` can no longer fire: it writes `false` into the `p_open` box only when the recorded flags omit `NoTitleBar`, and the window now passes no box at all. It is **not** dead weight — it is the subject of the FIX-03 regression check. Arming it is what makes `offered_close` a meaningful observation: the assertion says "with the player clicking close this frame, the window is still there", and it stays true only because nothing was offered to click. If a future change reinstates the box, the switch starts firing again and both the converted check and the pin check are there to judge it.

## Self-Check: PASSED

- `inctrack/ui.lua`, `inctrack/inctrack.lua`, `test/run_tests.py` and `.planning/phases/02-the-three-defects/02-02-SUMMARY.md` all exist on disk.
- Commits `373d2f8` (RED) and `459f3ef` (GREEN) are both in `git log --all`.
- The live install at `...\Ashita\addons\inctrack\` is byte-identical to the repository's `inctrack/`.

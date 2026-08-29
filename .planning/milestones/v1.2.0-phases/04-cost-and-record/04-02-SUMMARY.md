---
phase: 04-cost-and-record
plan: 02
subsystem: performance
tags: [lua, ashita, imgui, hot-path, persistence, allocation, memoisation]

requires:
  - phase: 01-coverage
    provides: the stubbed Ashita host with its save counter and session recorder, the ImGui recorder, the addon-shell suite, and lua_locals upvalue reflection
  - phase: 02-defects-and-contracts
    provides: the strictly-positional Begin(name, nil, flags) contract the drag-lock check reads its flags through, and schema version 2
  - phase: 03-fragile-paths
    provides: the render_off / render_ok latches and the two early returns in d3d_present that the flush must sit above
  - phase: 04-cost-and-record
    plan: 01
    provides: the suite floor this plan's table continues from, and the reject-path benchmark that must not move
provides:
  - "incursion.save_due: the chat thread decides whether a write is owed and marks it; the frame handler performs it"
  - "the flush at the top of d3d_present, above both early returns, so a hidden or latched-off window still writes the run down"
  - "the unload path's unconditional write, now pinned by a check that can tell it from a conditional one"
  - "FRAME_OPTS: one hoisted render-arguments table rewritten in place instead of allocated sixty times a second"
  - "SHORT_CACHE_MAX = 64 on shorten()'s memo cache, the whole cache dropped past it, emptied in place and never replaced"
  - "ui.forget(): the second thing ui.lua exports, called from reset() and the profile-switch callback"
affects: [04-03, milestone-close]

actuals:
  tokens: 71422
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "deferred write: the hot handler decides and marks, the per-frame handler performs, and the flag is consumed before the write so a raise cannot retry it every frame"
    - "flush above the early returns: a side effect that has nothing to do with drawing is placed above every reason the draw handler returns, with the reason written in the source"
    - "bounded memo: a stated cap far above real traffic, the whole cache dropped past it, and cleared in place so upvalue reflection keeps measuring the live table"

key-files:
  created: []
  modified:
    - inctrack/inctrack.lua
    - inctrack/ui.lua
    - test/run_tests.py

key-decisions:
  - "The throttle decision stays in text_in -- it is arithmetic on a number, not I/O -- so the write policy the player experiences is unchanged and only the write moved"
  - "The flush sits above both early returns in d3d_present, and says so in the source: a window latched off after a render error, or hidden with automatic show/hide off, is still a run that has to be written down"
  - "The flag is consumed before persist() runs, so a raise inside the write cannot leave it set and retry sixty times a second"
  - "The unload handler stays unconditional and does not consult the flag; that is what makes deferring every other write safe"
  - "SHORT_CACHE_MAX = 64: a run's boons are a handful, so the drop can only fire on input the server never sent"
  - "The whole cache is dropped rather than one entry evicted: an LRU would be more code, on the render path, for no gain on real traffic"
  - "The cache is emptied in place and never replaced, so a handle taken by upvalue reflection stays live"
  - "The plan's second negative control as written does not discriminate; a check that does was added (a throttled kill count outstanding at unload)"

patterns-established:
  - "Assert a moved side effect twice: nothing on the line that caused it, then present after the handler that performs it"
  - "Count a cache over pairs on the table itself, never off a bookkeeping counter, so a counter that has drifted is caught"
  - "A negative control that does not go red is a finding about the check, not about the code: fix the check"

requirements-completed: [PERF-02, PERF-03]

coverage:
  - id: D1
    description: "A burst of MUST_SAVE events performs no settings.save inline on the chat thread; the writes are recorded happening from the per-frame flush"
    requirement: PERF-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the write policy -- decided here, written from the frame (PERF-02)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The write policy the player experiences is unchanged: an event the server never repeats is written on the next frame, a kill count still rides the five-second throttle"
    requirement: PERF-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the throttle window, measured across frames"
        status: pass
    human_judgment: false
  - id: D3
    description: "The flush runs on frames that draw nothing -- automatic show/hide off, and a window latched off after a render error"
    requirement: PERF-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the flush runs on frames that draw nothing (PERF-02)"
        status: pass
      - kind: other
        ref: "negative control 1: flush moved below the visibility return -- 3 checks red, everything else green"
        status: pass
    human_judgment: false
  - id: D4
    description: "No run data is lost across an unload immediately after a burst, and the unload writes unconditionally even with nothing owed"
    requirement: PERF-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: an unload straight after a burst loses nothing"
        status: pass
      - kind: other
        ref: "negative control 2: unload made conditional on the flag -- 2 checks red, everything else green"
        status: pass
    human_judgment: false
  - id: D5
    description: "The frame handler allocates no options table, and /incursion lock still reaches Begin as NoMove"
    requirement: PERF-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the frame handler allocates nothing (PERF-02)"
        status: pass
    human_judgment: false
  - id: D6
    description: "shorten()'s memo cache stops growing at 64 entries over 512 distinct stat strings, really drops, and still returns the right answer for a string the drop evicted"
    requirement: PERF-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui: and the memoisation stops growing (PERF-03)"
        status: pass
      - kind: other
        ref: "negative control 3: cap check removed -- 3 checks red, correctness-after-drop green"
        status: pass
    human_judgment: false
  - id: D7
    description: "The cache is cleared in place rather than replaced, and holds nothing from a previous run after /incursion reset or a character change"
    requirement: PERF-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui: and it is cleared in place, not replaced"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: the boon memo goes when the run does (PERF-03)"
        status: pass
      - kind: other
        ref: "negative control 4: clearing helper replaces the table -- 4 ui and 2 addon checks red"
        status: pass
    human_judgment: false
  - id: D8
    description: "Green on both backends against 127 logs with no pre-existing suite's count fallen, parser exactly 11819 and generic exactly 1, and all six whole-window snapshots byte-identical"
    verification:
      - kind: integration
        ref: "python test/run_tests.py \"C:\\Games\\CatsEyeXI\\catseyexi-client\\Ashita\\chatlogs\""
        status: pass
      - kind: integration
        ref: "INCTRACK_LUA=luajit21 python test/run_tests.py \"C:\\Games\\CatsEyeXI\\catseyexi-client\\Ashita\\chatlogs\""
        status: pass
    human_judgment: false
  - id: D9
    description: "The one-frame residual PERF-02 opens: a crash between a chat line and the next frame loses that one event"
    verification: []
    human_judgment: true
    rationale: "Nothing offline can observe a client crash inside a one-frame window. What is checkable -- that the unload path writes unconditionally and that the flush sits above both early returns -- is pinned by D3 and D4; the residual itself is a stated trade for a human to accept, and plan 04-03 puts it in the design document."

duration: 15min
completed: 2026-08-29
status: complete
---

> **SUPERSEDED IN PART BY THE PHASE-4 CODE REVIEW (finding CR-02).** This
> summary was written before review. It describes the move of `persist()` out
> of `text_in` and onto the frame handler — "only the write moved" — and that
> is the half of it that shipped. What it does not describe is the containment
> the move turned out to need, and which the frame handler now has.
>
> `persist()` calls `state:serialise()` and Ashita's synchronous
> `settings.save()`; only the encode inside it was ever protected. Inside
> `text_in` the whole call had been covered by that handler's `pcall`. As the
> first statement of `d3d_present` it had nothing around it, so a raise from a
> refused write escaped onto the game thread every addon in the process shares
> — the exact failure the render `pcall` below it exists to prevent — and took
> the owed write with it, flag already cleared, with nobody told.
>
> What ships is the flush wrapped in `pcall(persist)`; on a raise `save_due` is
> **re-armed** rather than lost and `save_retry_at` is set to `now() +
> SAVE_RETRY_SECONDS` (5.0), so the retry is throttled instead of running every
> frame; and a `save_told` latch reports the failure **once** a session — with
> the error text passed as an argument and never as a format string — cleared
> by `reset()` and by the profile switch. Pinned by 24 addon-suite checks
> against a stub whose `settings.save()` can be made to raise. Commit
> `9d85dc5`; see `04-REVIEW.md` and `04-REVIEW-FIX.md`.
>


# Phase 4 Plan 2: Off the Chat Thread, and a Bound on the Cache Summary

**The settings write left the game thread — `text_in` now marks the run as owed a write and `d3d_present` performs it above both of its early returns — and `shorten()`'s memo cache stopped being able to grow for a whole play session.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-29T12:35:00+04:00
- **Completed:** 2026-08-29T12:50:00+04:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **PERF-02.** `persist()` serialises the run, encodes it as JSON and calls `settings.save()`. Until this plan all of that ran inside `text_in`, on the game thread, on the line that triggered it — every boon, every objective, every boss hint, every phase boundary, in the middle of combat chat. The *decision* has not moved and is not changed: `MUST_SAVE[event.t]` or past the five-second window, `save_at` still updated. Only the write moved, onto the frame handler that already runs every frame.
- **The flush is above both early returns, and the source says why.** `d3d_present` returns when the window latched off after a render error, and again when it is simply not on screen. A player with automatic show/hide off is still playing the run. Both are pinned by checks, and negative control 1 shows exactly those checks going red when the flush moves below the visibility return.
- **The unload path stays unconditional** and now has a check that can tell that from a conditional one — see the deviation below, because the control the plan specified could not.
- **PERF-02's per-frame allocation is gone.** One hoisted `FRAME_OPTS` table with `visible` fixed true (the handler has already returned when the window is not on screen) and `locked` rewritten each frame, in the shape `ui.lua` already uses for its own `ARG_*` tables. `/incursion lock` is pinned through the flags that actually reached `Begin`, both directions.
- **PERF-03.** `SHORT_CACHE_MAX = 64`, the whole cache dropped past it, emptied **in place** and never replaced, plus `ui.forget()` — the second thing `ui.lua` has ever exported — called from `reset()` and from the profile-switch callback. Bounded, dropped and cleared are each pinned, and each has a negative control.
- **Zero known defects, green on both backends against 127 logs**, `parser` exactly 11819, `generic` exactly 1, no pre-existing suite's count fallen, all six whole-window snapshots byte-identical.

## Task Commits

1. **Task 1: the write leaves the chat thread, and the frame stops allocating (PERF-02)**
   - `9f640ef` (test) — the RED tests: every site asserted twice, both early returns, the unload, the two clearing sites, the hoisted table
   - `10693c7` (feat) — `save_due`, the flush above both returns, the two clearing sites, `FRAME_OPTS`
   - `2591ac5` (test) — the discriminating unload pin, plus a guard so a misplaced flush goes red instead of raising
2. **Task 2: a bound on the memo cache, and a clear when the run goes (PERF-03)**
   - `e0a6cae` (test) — the RED tests: cap, drop, correctness-after-drop, clear-in-place, and the two shell clearing routes
   - `8ed8797` (feat) — `SHORT_CACHE_MAX`, `short_clear()`, `ui.forget()`, and the two call sites in the shell
3. **Task 3: the plan's closing run, on both backends against 127 logs**
   - `59c4e68` (docs) — the harness's module docstring now states the write policy it tests

**Plan metadata:** see the final commit of this plan.

## Files Created/Modified

- `inctrack/inctrack.lua` — `incursion.save_due` with its comment on why the frame handler is the mechanism; the mark in `text_in` where the inline `persist()` used to be; the flush at the very top of `d3d_present`, above both early returns, with the residual stated in the comment; the unconditional unload write with the flag cleared beside it; the flag and the memo cleared in `reset()` and in the profile-switch callback; the hoisted `FRAME_OPTS`.
- `inctrack/ui.lua` — `SHORT_CACHE_MAX`, `short_held`, `short_clear()` and the cap check in `shorten()`, with all three judgements written out; `ui.forget()`, the module's second export, documented as what the shell calls when the run the cache was built for is gone.
- `test/run_tests.py` — the rewritten write-policy block asserting nothing-then-a-frame at every site; the not-visible, latched-off, unload-without-a-frame, throttled-unload, reset and profile-switch cases; the hoisted-table and drag-lock cases; the ui suite's cap, drop, correctness and clear-in-place cases; `table_entries()`; a corrected module docstring.

## Run reports, verbatim

### 1. `python test/run_tests.py` (no logs, default backend)

```
inctrack tests
  lua: Lua 5.5
  chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)

  state: objectives, bonus, recovery              105 checks  ok
  adaptability: unseen content still tracked      119 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                      0 checks  ok
      skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)
  ui: helpers, layout contract, render             74 checks  ok
  addon: load, chat, settings, commands           189 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 286,958 lines/s, 3.485 us/line
      new shape (shipped):  1,058,702 lines/s, 0.945 us/line
      new/old: 3.69x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

### 2. `python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"`

```
inctrack tests
  lua: Lua 5.5
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2951129 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery              105 checks  ok
  adaptability: unseen content still tracked      119 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                     40 checks  ok
  ui: helpers, layout contract, render             74 checks  ok
  addon: load, chat, settings, commands           189 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 282,904 lines/s, 3.535 us/line
      new shape (shipped):  1,064,206 lines/s, 0.940 us/line
      new/old: 3.76x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

### 3. `INCTRACK_LUA=luajit21 python test/run_tests.py "...\chatlogs"`

```
inctrack tests
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2951129 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery              105 checks  ok
  adaptability: unseen content still tracked      119 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                     40 checks  ok
  ui: helpers, layout contract, render             74 checks  ok
  addon: load, chat, settings, commands           189 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
      old shape (Phase 3): 562,810 lines/s, 1.777 us/line
      new shape (shipped):  2,752,999 lines/s, 0.363 us/line
      new/old: 4.89x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

The two 127-log runs report **identical per-suite check counts to each other**, and identical to the no-logs run for every suite the no-logs run has.

## The per-suite table, from the head of the phase to here

| Suite | Phase floor (03 close) | After 04-01 | After 04-02 | Movement |
|---|---|---|---|---|
| `parser: structural lines all parse` | 11819 | 11819 | **11819** | flat, as required |
| `parser: generic tier matches nothing today` | 1 | 1 | **1** | flat, as required |
| `parser: tightened patterns keep every line whole` | 1 | 1 | **1** | flat |
| `state: run reconstruction` (replay) | 888 | 888 | **888** | flat |
| `state: objectives, bonus, recovery` | 105 | 105 | **105** | flat |
| `adaptability` | 42 | 119 | **119** | +77 in 04-01, flat here |
| `disconnect` | 23 | 23 | **23** | flat |
| `timers` | 31 | 31 | **31** | flat |
| `persistence` | 40 | 40 | **40** | flat, and running not skipping in both 127-log runs |
| `ui` | 65 | 65 | **74** | **+9 here** (cap, drop, correctness, in-place clear, identity, and their counter-pins) |
| `addon` | 143 | 160 | **189** | +17 in 04-01, **+29 here** |
| `cost: the non-Incursion reject path` | — | 6 | **6** | flat |

Every row is non-decreasing from the phase floor. `ui` >= 70 and `addon` >= 167, both criteria met with room. No suite fell on either backend.

## Negative controls

All four were run, and each is recorded with what went red and what stayed green.

### 1. The flush moved *below* the visibility early return (PERF-02, placement)

Removed the flush block from the top of `d3d_present` and re-inserted it immediately after `if not visible() then return; end`.

| | |
|---|---|
| **Went red** | `addon`, 3 of 181: *"a player with automatic show/hide off never has their run written down: the window is off screen, the frame returned before the flush, and the whole Incursion is lost on a reload"*, *"the frame that drew no window wrote nothing, or wrote an empty run over the Incursion in progress: []"*, and *"a window that switched itself off after a render error stopped writing the run down too, so one render fault quietly became a lost Incursion"* |
| **Stayed green** | everything else — `state` 105, `adaptability` 119, `disconnect` 23, `timers` 31, `ui` 65, `cost` 6, and the other 178 `addon` checks, including every marked-then-flushed case, the throttle policy and the unload |

That is what says those checks measure the **placement** and not the mechanism: the flush still worked, on every frame that drew a window.

### 2. The unload path made conditional on the flag (PERF-02, unconditionality)

Wrapped the unload handler's `persist()` in `if incursion.save_due then ... end`.

| | |
|---|---|
| **Went red** | `addon`, 2 of 184: *"unloading with a throttled kill count outstanding wrote nothing at all (0 writes)"* and *"the run came back to the kill count it had five seconds earlier: the unload wrote only what a frame had already written, so everything the throttle was holding is gone"* — the second printing the written session, `"kills_cur":7` where the run held 11 |
| **Stayed green** | everything else, including the burst-then-unload case, which cannot tell the two apart (see the deviation below) |

### 3. The cap check removed from `shorten()` (PERF-03, the bound)

Deleted the `if short_held >= SHORT_CACHE_MAX then short_clear(); end` guard, leaving the constant declared but unreferenced.

| | |
|---|---|
| **Went red** | `ui`, 3 of 74: *"shorten()'s memo cache has no stated bound, so it grows for as long as the client is running"* (the constant stops being an upvalue once nothing references it, so reflection can no longer see it), *"the memo cache reached 512 entries against a stated bound of 0"*, and *"512 distinct stat strings never made the cache drop anything"* |
| **Stayed green** | the correctness-after-drop case — *"a stat string the drop had evicted came back shortened wrongly"* stayed green, which is the point: an unbounded cache is still correct. `addon` 189, and every other suite |

### 4. The clearing helper replacing the table instead of emptying it (PERF-03, in place)

Changed `short_clear()` to `short_cache = {}`.

| | |
|---|---|
| **Went red** | `ui`, 4 of 74 — *"the clearing helper replaced the cache table instead of emptying it, so the handle the harness holds is an orphan and what it measures is not the cache the addon is using"*, *"the table the addon memoises into is not the one the harness reads"*, plus the start-empty and never-dropped cases, all of them reading the orphaned handle. And `addon`, 2 of 189: *"the boon text of a run the player cleared is still held in memory"* and *"one character's boon text was still in memory after they logged out and another character logged in"* |
| **Stayed green** | the cap and correctness cases — the live cache was still bounded and still right. Every other suite |

That is what says the harness is measuring the **live** cache: the only handle it can hold on a file-scope local is the one it took by reflection, and a replaced table silently turns every one of those measurements into a measurement of nothing.

## The one-frame residual, stated plainly

Between a chat line arriving and the next frame running, there is a window of roughly one frame — about 16 ms at 60fps — in which the run is **not on disk**. A hard client crash inside that window loses that one event: the boon just picked, the objective just announced, the phase just entered.

**Why the trade was taken.** The alternative is what shipped until now: a synchronous serialise, JSON encode and disk write on the game thread, on every chat line that changes the run. In a crowded zone during a phase that is a steady stream of them, and each one is paid while the client is trying to draw a frame. Ashita exposes no asynchronous write primitive to addons, so the choice is between a synchronous write on the hot path and a deferral of about one frame. One frame of exposure to a hard crash is a smaller cost than a disk write in every combat message.

**Two things bound it, and both are pinned:**

1. **The unload handler writes unconditionally.** It does not consult the flag — it cannot, because there will be no further frame. That covers every orderly departure: `/addon unload`, a reload, a logout, a zone change that takes the addon with it. Negative control 2 shows what removing this costs.
2. **The flush sits above both early returns.** A window that is off screen or latched off after a render error is not a run that stopped mattering, and a flush below either return would have narrowed the residual from "one frame" to "forever" for those players. Negative control 1 shows what moving it costs.

Plan 04-03 puts this in the design document.

## The cap value and the names

- **The cap is 64**, declared as `SHORT_CACHE_MAX` in `inctrack/ui.lua`. A run's boons are a handful and their stat strings repeat every frame; 64 is far above any run the 127-log corpus contains, so the drop can only ever fire on input the server never sent. A bound reached in ordinary play would be trading a real cost for a hypothetical one. The reasoning is in the comment, not just the number.
- **The whole cache is dropped**, not one entry evicted. Boon stat strings are few and repeat every frame, so an LRU is more code — code on the render path — for no measurable gain on real traffic. A drop costs one re-shorten per live string on the next frame that draws it.
- **Names are exactly the ones the acceptance criteria name.** `incursion.save_due`, `FRAME_OPTS`, `SHORT_CACHE_MAX`, `ui.forget`. No substitutions.

## Acceptance greps

| Command | Expected | Got |
|---|---|---|
| `grep -c "incursion.save_due" inctrack/inctrack.lua` | >= 6 | **6** |
| `grep -c "FRAME_OPTS" inctrack/inctrack.lua` | >= 3 | **3** |
| `grep -c "SHORT_CACHE_MAX" inctrack/ui.lua` | >= 2 | **3** |
| `grep -c "ui.forget" inctrack/inctrack.lua` | exactly 2 | **2** |
| `grep -cF "counted a bonus objective payout as a cleared phase" test/run_tests.py` | 1 | **1** |
| `grep -cF "clock was optimistic by the reload gap after a reconnect" test/run_tests.py` | 1 | **1** |
| `grep -cF "the window asks for a close button and then ignores it" test/run_tests.py` | 1 | **1** |
| `git diff --name-only 1c2df83..HEAD` | the three files | **`inctrack/inctrack.lua`, `inctrack/ui.lua`, `test/run_tests.py`** |

On `incursion.save_due` reaching exactly 6: the field's **declaration** inside the `incursion = T{...}` table reads `save_due = false,` and does not carry the `incursion.` prefix, so it is not one of the six. The six are the mark in `text_in`, the two lines of the consume in `d3d_present`, and the three clearing sites (unload, `reset`, profile switch). The criterion's intent — declared once, marked once, consumed once, cleared in three places — holds; the arithmetic reaches it by a different route than the criterion assumed. Same class as the already-logged `render_off = false` item.

`grep -c "render_off = false" inctrack/inctrack.lua` still prints **4**, and `grep -c "incursion.render_off = false"` prints **3**. That is `.planning/WINDOWS.md` item **1**, already open against this phase from 04-01; this plan changed neither number and no second ledger entry was filed for the same fact.

## The reject-path benchmark did not move

PERF-02 defers a *write*; a rejected line never reaches the write policy at all, so the reject-path figure must not move. The part of that figure the criteria actually rest on is deterministic, and it is byte-identical before and after:

| | 04-01 (post-change) | 04-02 (this plan) |
|---|---|---|
| per colour-free rejected line, new shape | **0.00** `strip_colors`, **0.00** `gsub` | **0.00** `strip_colors`, **0.00** `gsub` |
| per coloured rejected line, new shape | **1.00** `strip_colors`, **2.00** `gsub` | **1.00** `strip_colors`, **2.00** `gsub` |
| per colour-free rejected line, old shape | 1.00, 5.33 | 1.00, 5.33 |
| per coloured rejected line, old shape | 1.00, 5.00 | 1.00, 5.00 |

Identical in all six runs across both plans and both backends. Not a single allocation moved.

The wall-clock figures beside them, side by side (they are printed as provenance, not as thresholds, and the harness's only wall-clock assertion is the same-run ratio):

| Run | 04-01 new shape | 04-02 new shape | same-run new/old |
|---|---|---|---|
| no logs, Lua 5.5 | 1,046,338 lines/s, 0.956 us | 1,058,702 lines/s, 0.945 us | 3.63x -> 3.69x |
| 127 logs, Lua 5.5 | 528,092 lines/s, 1.894 us | 1,064,206 lines/s, 0.940 us | 1.96x -> 3.76x |
| 127 logs, LuaJIT 2.1 | 2,822,511 lines/s, 0.354 us | 2,752,999 lines/s, 0.363 us | 5.29x -> 4.89x |

Stated honestly: the two LuaJIT figures and the two no-logs figures are within ordinary run-to-run wobble (1% and 2.5%), and the 127-log Lua 5.5 pair differs by 2x in **04-01's** favour being the slower — that row was measured on a loaded machine and its same-run ratio of 1.96x, against 3.63x on the identical code minutes earlier, says so. This plan's figure is faster, not slower, in every comparison where it differs. Nothing here moved the wrong way, and the deterministic counters — which is what "the figure did not move" actually means — did not move at all.

## Decisions Made

All of the plan's locked decisions were honoured without reopening any of them. The decisions made *during* execution:

- **The discriminating unload check.** The plan's second negative control could not fail (see Deviations). The check that replaced it drives a throttled kill count — nothing owed, disk copy up to five seconds stale — through the unload and asserts on the `kills_cur` in the written session.
- **The docstring correction became a docstring addition.** The plan expected to find an out-of-date description of the write policy in `test/run_tests.py`'s module docstring. There was none to correct; one was added, in the two-to-three lines the plan allotted.
- **The hidden-window session read is guarded.** `hidden_run.sessions[-1]` raises `IndexError` when nothing was ever written, which is precisely the state negative control 1 produces. A check that cannot go red about the thing it is checking is not a check.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] The plan's second negative control could not discriminate, so a check that can was added**

- **Found during:** Task 1 (the settings write leaves the chat thread)
- **Issue:** The plan specifies: *"with the unload path made conditional on the flag, the unload-without-a-frame case goes red."* It does not. In the burst-then-unload scenario the flag **is** set — the burst set it and no frame consumed it — so a conditional `persist()` and an unconditional one behave identically and the control ran fully green. The unload path's unconditionality was therefore **unpinned**: nothing in the suite would have noticed it being made conditional, which is a real gap given that this write is the only thing standing between a throttled kill count and a lost five seconds of run.
- **Fix:** Added a case that does discriminate. A run, a frame (which flushes), then a kill count *inside* the throttle window — nothing owed, save_due false, and the copy on disk now up to five seconds behind the run the player is watching — then an unload. Asserted on the write count and on `kills_cur` in the session that was actually written.
- **Files modified:** `test/run_tests.py`
- **Verification:** With the unload made conditional, the two new checks go red (`0 writes`, and `"kills_cur":7` where the run held 11) and everything else stays green. Restored, all 184 addon checks pass on both backends.
- **Committed in:** `2591ac5`

**2. [Rule 1 — Bug] A check that raised instead of going red**

- **Found during:** Task 1, running negative control 1
- **Issue:** `res.check(hidden_run.sessions[-1] != "", ...)` raises `IndexError` when the flush never ran, which is exactly the state the negative control creates. The suite aborted at that line and reported *"the suite stopped early and proved nothing past that point"* instead of the two red lines that were the whole point of the control.
- **Fix:** Guarded the index — `bool(hidden_run.sessions) and hidden_run.sessions[-1] != ""` — and folded the empty case into the failure message.
- **Files modified:** `test/run_tests.py`
- **Verification:** Negative control 1 re-run: 3 clean red lines, suite completes, everything else green.
- **Committed in:** `2591ac5`

**3. [Rule 3 — Blocking] The docstring the plan asked to correct did not exist**

- **Found during:** Task 3
- **Issue:** The plan directs: *"The module docstring at the head of `test/run_tests.py` describes the write policy in the words of the code before this plan… Correct it."* The docstring describes the suites, the fixtures, the chatlog and libs requirements, and the three retired xfails. It says nothing about the write policy at all, so there was nothing to correct. Applying the instruction literally would have meant editing prose that is not there.
- **Fix:** Added the description instead, in the two-to-three lines the plan allots, stating what is now true: the chat thread decides and marks, the frame flushes above both early returns, the unload path writes unconditionally, and every save is asserted twice.
- **Files modified:** `test/run_tests.py`
- **Verification:** `python test/run_tests.py` PASS; the docstring's claims are each an assertion in suite 10.
- **Committed in:** `59c4e68`

**4. [Record, not a fix] `grep -c "incursion.save_due"` reaches 6 by a different route than the criterion assumed**

- **Found during:** Task 1
- **Issue:** The criterion enumerates six sites including "the declaration". The declaration lives inside the `incursion = T{...}` table and reads `save_due = false,` — no `incursion.` prefix — so it does not match. The count still prints 6 because the consume in `d3d_present` spans two matching lines.
- **Fix:** None needed; the criterion's *intent* (declared once, marked once, consumed once, cleared in three places) is satisfied and verified by reading the source. Recorded here rather than silently accepted.
- **Related:** the same class of arithmetic slip as `.planning/WINDOWS.md` item 1 (`render_off = false` printing 4). No new ledger entry was filed — nothing is left open, and item 1 already carries the pattern for this phase.

---

**Total deviations:** 3 auto-fixed (1 missing critical assertion, 1 harness bug, 1 blocking plan/reality mismatch) + 1 recorded observation.
**Impact on plan:** No scope creep — every change is inside the three files the plan names. Deviation 1 closed a genuine coverage hole the plan's own control would have hidden; the remaining two were mechanical.

## Issues Encountered

- **Negative control 2 ran green on the first attempt**, which was the finding rather than a pass. Treated as a statement about the check, not about the code — see deviation 1. This is the pattern worth carrying forward: a negative control that will not go red has not validated anything.
- **Upvalue reflection stops seeing a constant nothing references.** In negative control 3, removing the cap check made `SHORT_CACHE_MAX` invisible to `lua_locals` — Lua only keeps an upvalue that some reachable closure actually reads. The extra red line is correct and honest; noted so a future reader does not mistake it for a harness fault.

## Purity, content and scope

- `inctrack/parser.lua` and `inctrack/state.lua` were **not touched**. `ui.lua` gained no dependency beyond `imgui`. `State.dirty` is untouched and the shell still drives persistence off `apply()`'s boolean return.
- **Zero content knowledge**: no instance, boss, mob, objective or difficulty name entered any Lua file. `STAT_SHORT` is unchanged and still passes unknown phrases through untouched.
- **Nothing from a prior phase was undone**: `imgui.Begin(name, nil, flags)` and the strictly-positional stub, schema `version = 2` and its v1 migration, the `render_ok`/`render_off` latches and their three clearing sites, `override`'s deliberate non-clearing, the closure-wrapped repair calls, `resume()` and its finished-run exemption, the validator's `is_string` rule, the three parser tightenings, and 04-01's gate with its colour fall-through are all in place and all still asserted.
- **Scope fence held**: `docs/design.md`, `README.md`, `CHANGELOG.md` and `addon.version` were not edited. IN-05 was not applied.

## User Setup Required

None — no external service configuration required. The 127-log runs need the author's private chatlog directory and Ashita's `json.lua`, both of which were present (127 logs, `addons/libs/json.lua` found, `persistence` running at 40 checks rather than skipping).

## Next Phase Readiness

**What is left for plan 04-03 (DOC-01, DOC-02):**

1. **`docs/design.md`** — the drift list from `04-CONTEXT.md` (window sizing, `NoTitleBar`, the stats layout, the boons row, the run-record fields) *plus* what this milestone changed: `awards_seen`, the single-author rule for `phases_cleared`, schema `version = 2` and its migration, the structural restore validator, the render containment and its latches, PERF-01's cheap gate — **and the write policy this plan changed, including the one-frame residual stated above**.
2. **`inctrack/ui.lua:15-26`** — the layout comment, seven rows out of date. Comment-only, and the last chance before the milestone closes.
3. **`CHANGELOG.md` and `addon.version`** — 1.2.0, with the defects named in the user-facing terms the Phase-1 xfails were written in.
4. **`README.md`** — it documents a close button and a title bar the addon no longer has.

**Three in-game human checks remain open** and no suite can close them: Phase 2's reload clock and window frame, and Phase 3's D8 `imgui.End` metatable lookup. They should be surfaced at milestone close, not in 04-03.

**One thing 04-03 should know:** the deployed build at `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` is no longer byte-identical to the repo — this plan changed `inctrack.lua` and `ui.lua` and nothing was copied across. That is expected mid-milestone and is the milestone-close step's business.

---
*Phase: 04-cost-and-record*
*Completed: 2026-08-29*

## Self-Check: PASSED

All four artifacts exist on disk and all six task commits are present in the repository.

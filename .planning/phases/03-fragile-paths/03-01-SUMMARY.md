---
phase: 03-fragile-paths
plan: 01
subsystem: ui
tags: [lua, ashita, imgui, error-handling, pcall, fault-injection, testing]

requires:
  - phase: 01-the-net
    provides: the recording ImGui stub with Begin/End and push/pop counting, the
      stubbed Ashita host, and upvalue reflection into inctrack.lua's file-scope
      locals -- without all three, none of this is assertable
  - phase: 02-the-three-defects
    provides: the strictly positional imgui.Begin(name, p_open, flags) recorder
      (CR-01), which the fault injector had to leave untouched
provides:
  - a d3d_present handler that calls ui.render through a pcall
  - a conditional ImGui stack repair, gated on the render shape having run end
    to end on this host at least once (render_ok)
  - a session-long render_off latch, so a systematic failure is reported once
    rather than sixty times a second
  - two recovery paths -- /incursion re-enables, /incursion reset clears both
    the run and the latch -- plus a profile switch that starts clean
  - a one-shot ImGui fault injector in the recorder, off by default, which is
    what makes the percent-sign trigger expressible at all
affects: [03-02, 03-03, phase-04-performance, phase-04-docs]

actuals:
  tokens: 6263
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Host-boundary containment lives in inctrack.lua, never in the pure
       modules -- one pattern, one place, beside the text_in pcall"
    - "A stack repair is conditional on evidence, not reflexive: repair only
       what the shell can prove was owed"
    - "The harness models the consequence of a hostile host on demand, and
       never asserts the cause by default"

key-files:
  created: []
  modified:
    - inctrack/inctrack.lua
    - test/stubs.py
    - test/run_tests.py

key-decisions:
  - "The pcall goes in inctrack.lua's frame handler; ui.lua is not edited at all"
  - "The repair is conditional on render_ok -- a raise before Begin closes nothing"
  - "The style colour stack is deliberately not repaired, and the suite asserts it anyway"
  - "The bare /incursion while disabled is a re-enable, not a toggle"
  - "render_ok is never cleared by reset(): it is a fact about the host, not the run"
  - "The fault injector is off by default and disarmed by reset()"

patterns-established:
  - "Conditional repair: the shell repairs an ImGui stack only when it holds
     evidence the stack was actually moved; an unmatched close would become the
     second error of the frame, which is the failure being prevented"
  - "Report-once-and-latch for anything on a per-frame path: one chat line that
     names the way back, then silence"
  - "Fault injection with an ordering carve-out: stack-moving entry points raise
     before they are logged, so the log says what the stack did rather than what
     was attempted"

requirements-completed: [HARD-01]

coverage:
  - id: D1
    description: "An error raised inside ui.render is caught in d3d_present and
      cannot escape into the game thread every addon shares"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: a bad value in the mob list threw out of d3d_present"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: a percent sign in a name the server sent threw out of d3d_present"
        status: pass
    human_judgment: false
  - id: D2
    description: "After a caught render error the window and style-var stacks
      come back balanced, for both triggers the phase brief names"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the ImGui stacks were left unbalanced after a render error"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: the ImGui stacks were left unbalanced after a raise from a draw call"
        status: pass
    human_judgment: false
  - id: D3
    description: "A raise that precedes the window's opening is contained without
      the repair closing anything -- no End and no PopStyleVar are emitted"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the shell closed a window that was never opened"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: the shell popped a style var that was never pushed"
        status: pass
      - kind: unit
        ref: "negative control: repair made unconditional -> exactly these 3 checks fail"
        status: pass
    human_judgment: false
  - id: D4
    description: "The failure is reported exactly once, in one chat line naming
      /incursion, and the next sixty frames draw nothing and say nothing"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: one render failure produced N chat lines"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: a window that took itself off screen kept drawing anyway"
        status: pass
    human_judgment: false
  - id: D5
    description: "/incursion and /incursion reset both clear the disabled state,
      and a repaired run draws again on the very next frame"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: /incursion did not bring the window back"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: /incursion reset left the window switched off"
        status: pass
    human_judgment: false
  - id: D6
    description: "The addon is not dead, only the window: chat keeps driving the
      run while the HUD is disabled"
    requirement: HARD-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: chat stopped driving the run once the window switched itself off"
        status: pass
    human_judgment: false
  - id: D7
    description: "The one-shot fault injector is inert until armed -- every
      pre-existing suite count is unmoved by its addition"
    verification:
      - kind: integration
        ref: "python test/run_tests.py (after Task 1): state 53, adaptability 20, disconnect 23, timers 25, ui 65, addon 83 -- all unchanged"
        status: pass
    human_judgment: false
  - id: D8
    description: "The containment behaves the same in game as it does in the
      harness -- the real Ashita ImGui binding accepts the repair calls"
    verification: []
    human_judgment: true
    rationale: "pcall(imgui.End) and pcall(imgui.PopStyleVar, 1) reach Ashita's
      GuiManager through a metatable __index, not through a Lua wrapper. The
      stub models that shape but cannot execute it. Carried alongside the two
      in-game checks already open from Phase 2."

duration: 29min
completed: 2026-08-29
status: complete
---

# Phase 3 Plan 01: Error Containment in the Render Path Summary

**`ui.render` now runs inside a `pcall` in `d3d_present`, with a stack repair that is conditional on the render shape having already run clean once on this host — so a raise before `Begin` closes nothing — a report-once latch naming `/incursion` as the way back, and 29 new addon checks pinning all of it.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-29T04:36:00Z
- **Completed:** 2026-08-29T05:05:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **The frame handler contains what `ui.render` raises.** `d3d_present` calls
  `pcall(ui.render, ...)`. `ui.lua` is not edited by a single byte: the host
  boundary lives in the host-facing file, beside the `pcall` that has protected
  `text_in` since 1.0.0.
- **The repair is conditional, and the conditionality is load-bearing.**
  `render_ok` latches the first time the protected call returns cleanly *with a
  run to draw*. Only then is `End()` and `PopStyleVar(1)` owed. Trigger C proves
  a raise from `PushStyleVar` — before the window is ever opened — emits no
  `End` and no pop.
- **Reported once, then silent.** `render_off` latches; the next sixty frames
  produce no ImGui call and no chat line. The one line carries the error text as
  a `%s` argument (never as part of the format string) and names `/incursion`.
- **Two ways back, plus a clean character change.** `/incursion` re-enables (it
  does not toggle), `/incursion reset` clears the latch with the run, and a
  profile switch no longer hands a new character a HUD disabled by a failure
  they never saw.
- **The recorder can now be told to raise.** A one-shot fault injector, off by
  default, disarmed by `reset()`, with an ordering carve-out on the stack-moving
  entry points. Without it the percent-sign trigger could not be expressed at
  all.
- **Both negative controls demonstrated**, in both directions.

## Task Commits

1. **Task 1: A one-shot fault injector in the ImGui recorder, off by default** — `d35235c` (test)
2. **Task 2: Catch the render error, repair the stacks, report once, disable the window** — `08bf3c2` (test, RED) then `6508d0b` (feat, GREEN)
3. **Task 3: Prove it against the full corpus and both backends** — no files modified; verification and recording only, carried in this SUMMARY

**Plan metadata:** see the `docs(03-01)` commit.

## Files Created/Modified

- `inctrack/inctrack.lua` — requires `imgui`; two new fields on the `incursion`
  table (`render_off`, `render_ok`); the rewritten `d3d_present` handler with the
  protected call, the conditional repair, the latch and the one-line report;
  `render_off` cleared in `reset()`, in the bare `/incursion` branch and in the
  profile-switch callback.
- `test/stubs.py` — `S.fault`, `S.arm_fault(name, contains)`, the `STACK_MOVING`
  ordering carve-out inside `record()`, `S.reset()` disarming, and
  `ImGuiRecorder.arm_fault()` with the docstring that says what the injector is
  and is not.
- `test/run_tests.py` — three new fixtures (`SHELL_PERCENT`, `SHELL_MOBS`,
  `SHELL_FIRST_MOB`) and a new block at the end of the addon suite covering all
  three triggers, the balance after each, the single report, the sixty silent
  frames, chat still driving the run and both recovery paths; plus one check in
  the character-change block.

## The three run reports, verbatim

### Run 1 — no chatlogs (the log-independent floor)

```
inctrack tests
  lua: Lua 5.5
  chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)

  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                      0 checks  ok
      skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

### Run 2 — the author's 127 logs, default backend

```
inctrack tests
  lua: Lua 5.5
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945035 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                     31 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

### Run 3 — the same 127 logs under `INCTRACK_LUA=luajit21`

```
inctrack tests
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945039 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                     31 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

All three exit 0. The two corpus runs carry the `chatlogs:` header and report
127 logs. The grep for `FAILED`, `XFAIL ` and `NOW PASSING ` over a corpus run
prints `0` (the `|| true` is load-bearing — zero is the passing answer and
`grep -c` exits 1 on it).

Both corpus runs read one more chat line under `luajit21` than under Lua 5.5
(2,945,039 vs 2,945,035). That difference predates this plan — it is the
harness reading the live chatlog directory, which the author's client is still
appending to — and no per-suite count moves with it.

### Per-suite counts against the Phase-2 floor

| Suite | Phase-2 floor | Run 1 (no logs) | Run 2 (127 logs) | Run 3 (luajit21) | Verdict |
|---|---|---|---|---|---|
| parser: structural | 11819 | — (skipped) | 11819 | 11819 | at floor |
| parser: generic tier | 1 | — (skipped) | 1 | 1 | at floor |
| replay: run reconstruction | 888 | — (skipped) | 888 | 888 | at floor |
| state | 53 | 53 | 53 | 53 | at floor |
| adaptability | 20 | 20 | 20 | 20 | at floor |
| disconnect | 23 | 23 | 23 | 23 | at floor |
| timers | 25 | 25 | 25 | 25 | at floor |
| persistence | 31 | — (skipped) | 31 | 31 | at floor |
| ui | 65 | 65 | 65 | 65 | **exactly 65** — `ui.lua` untouched |
| addon | 83 | 112 | 112 | 112 | **+29**, well above the required ≥ 98 |

No suite fell, on either backend. `ui` is exactly 65, which is the check that
`ui.lua` really was left alone and that the recorder still behaves as it did.

## Both negative controls

A containment test that passes against the uncontained code proves nothing, and
a conditionality check that passes against an unconditional repair is
decoration. Both were run.

### Negative control 1 — the containment removed

This is what the RED commit (`08bf3c2`) *is*: the 28 checks were written and run
against the frame handler as it stood, with the bare `ui.render(...)` call.

**Result: `addon` 111 checks, 16 FAILED.** In order:

1. an ordinary frame took the window off screen for the rest of the session by itself
2. a bad value in the mob list threw out of d3d_present and into the game thread every addon shares
3. the ImGui stacks were left unbalanced after a render error (`{'window': 1, 'style_var': 1, 'style_color': 0}`)
4. one render failure produced 0 chat lines
5. the window vanished and nothing said how to get it back
6. a window that took itself off screen kept drawing anyway
7. /incursion did not bring the window back
8. a percent sign in a name the server sent threw out of d3d_present
9. the ImGui stacks were left unbalanced after a raise from a draw call (`{'window': 1, 'style_var': 1, 'style_color': 0}`)
10. the player was not told once, in one line naming /incursion, what happened (trigger B)
11. a raise before the window opened threw out of d3d_present
12. a failure before the window opened was not latched, so it will happen again on every frame
13. the player was not told once, in one line naming /incursion, what happened (trigger C)
14. /incursion did not bring back a window disabled by a failure that happened before it was ever opened
15. the failure was not latched, so it will repeat every frame
16. /incursion reset left the window switched off

The twelve that passed uncontained are the ones that hold trivially without a
containment: the two clean-frame `Begin` assertions, the two "a `Begin` was
recorded in the failing frame" assertions, "chat still drives the run", "the run
was cleared", and — pointedly — trigger C's `End`-absent and `PopStyleVar`-absent
checks, which pass when nothing repairs at all. Those two are the ones the
*second* control exists to exercise.

### Negative control 2 — the repair made unconditional

The `if incursion.render_ok then` guard was replaced with a bare `do` block, so
`End` and the pop always run. Nothing else changed.

**Result: `addon` 112 checks, exactly 3 FAILED — all three of them trigger C's:**

1. the stacks did not come back level from a frame that opened nothing
2. the shell closed a window that was never opened — on a real host that is an ImGui assert, so the repair became the second error of the frame
3. the shell popped a style var that was never pushed

Every other check, including both of the balance assertions for triggers A and
B, still passed. That is the shape the control had to have: the conditionality is
exercised by exactly the case it exists for, and by nothing else. The guard was
restored and the suite re-run green before the GREEN commit landed.

## The two bounds, stated

### Bound 1 — the style colour stack is not repaired

Considered and declined, not overlooked. `PushStyleColor`/`PopStyleColor` appear
exactly once in `ui.lua`, inside `bar()` (`ui.lua:112-119`), bracketing a single
`imgui.ProgressBar` call. There is no data-driven raise site between the push and
the pop, so nothing can stop between them, and repairing a stack that cannot be
left unbalanced would be a guess dressed as a fix.

What makes that safe to rely on rather than merely believed: the addon suite
asserts **all three** stacks after every trigger, colour included. If a later
change puts a raise site between that push and that pop, the balance checks go
red and say so — rather than the imbalance escaping quietly, or a reflexive
`PopStyleColor` here papering over it.

### Bound 2 — the repair is conditional on `render_ok`, and what that does not buy

`ui.render`'s shape is fixed and short, and **three statements run before
`Begin`**: `state:snapshot()` with its early return, the flags arithmetic, and
the single `PushStyleVar`. A raise from any of them leaves nothing open and
nothing pushed. An unconditional `End()` there is an unmatched close — on a real
host an ImGui assert — which would make the repair *the second error of the
frame*, which is precisely the failure this whole plan exists to prevent.

`render_ok` is the one fact the shell can hold honestly: the render shape has run
end to end on this host at least once, so the constants are good, the push is
good, the `Begin` is good, and what raised afterwards is inside the window. The
latch additionally requires that there was a run to draw — a frame that took
`render`'s early return proves nothing about the window. It is never cleared by
`reset()`, because it is a fact about the host, not about the run.

- **What it buys:** an unmatched close is impossible on the first failing frame.
  Trigger C pins it: no `End`, no `PopStyleVar`, all three stacks at zero, and
  negative control 2 shows those three checks are the only ones that notice.
- **What it does not buy — the one residual, stated and unguarded:** the flags
  arithmetic reads `opts.locked`. A nil ImGui constant reached *only* on the
  locked path could therefore raise before `Begin` on a host where an unlocked
  frame has already drawn clean — and there the repair would over-close by one
  window. Nothing data-driven reaches that path, and no check here can provoke
  it. It is recorded as a bound, not carried as a defect.

## What the fault injector is, and is not

`ImGuiRecorder.arm_fault(name, contains=None)` arms a single raise from a
nominated ImGui entry point, optionally only when one of the call's string
arguments holds `contains` as a plain literal (a `find` with the plain-text flag
— the substrings the tests use contain a percent sign, so a pattern match would
be wrong).

**It is a fault injector.** It puts a raise at a chosen point in the render tree
so the shell's containment is testable at all. Without it, the phase brief's
second named trigger — a percent sign in a server-supplied instance name — could
not be expressed, because the stub does not treat drawn text as a format string
and **must not start claiming that it does**.

**It is not a claim about Ashita's binding.** The audit's percent-sign hazard is
that the real binding *may* treat drawn text as a format string. That cannot be
inspected from here, and blessing an unverified host assumption is exactly what
Phase 2's CR-01 was about. So the recorder models the *consequence* on demand and
never asserts the *cause* by default. `T-03-04` in the plan's threat register
carries this as **transfer**, not mitigate, for the same reason.

**Off by default, and proven inert.** After Task 1 and before any other change,
the six log-independent suites reported `state 53, adaptability 20, disconnect
23, timers 25, ui 65, addon 83` on both backends — every number identical to the
Phase-2 floor. An injector that changed a single check would have changed every
window snapshot in the `ui` suite.

**The ordering carve-out, and the one-off check that proves it.** On the
stack-moving entry points — `Begin`, `End`, `PushStyleVar`, `PopStyleVar` — the
raise happens *before* the call is logged and counted; everywhere else it happens
after. This is the same rule stated twice, not two rules: the log says what the
stack **did**, not what was attempted. A host that refuses a push has not pushed.
Logging the attempt would put a phantom into `balance()`'s arithmetic and make
the harness demand a repair no real host is owed.

Verified directly in-session before Task 2 was written: with `PushStyleVar` armed
and one frame driven through the recorder, `balance()` returned
`{'window': 0, 'style_var': 0, 'style_color': 0}` and `calls` was `[]` — nothing
from the refused push in the log, and nothing owed. That is the fact trigger C
rests on. The complementary ordering was checked too: with `TextColored` armed on
an instance name containing `%`, the call *is* logged and the balance reads
`{'window': 1, 'style_var': 1, 'style_color': 0}` — exactly the one window and
one style var a repair then owes.

## Decisions Made

All the substantive ones were locked by `03-CONTEXT.md` and honoured as written.
The discretionary ones, now fixed:

- The flag is `incursion.render_off`; the evidence latch is `incursion.render_ok`.
- The bare `/incursion` while disabled is a **re-enable and a return to automatic
  visibility**, not a toggle. Toggling against a window that is not being drawn
  would read as "hide it", which is the opposite of what was asked.
- The chat line is a single line carrying the error text: `Render error, window
  disabled: <err> -- /incursion to try again.` The error text is a `%s` argument
  and never part of the format string, which is the whole point of trigger B.
- Each repair call is wrapped in its own `pcall`, for the same reason the repair
  is conditional: neither may become the second error of the frame either.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `render_off` cleared on a character change**

- **Found during:** Task 2
- **Issue:** The plan's action text says clearing `render_off` in `reset()` "also
  means a profile switch that goes through the same path starts the new character
  clean." It does not: the `settings.register` callback at `inctrack.lua:276-295`
  inlines its own clearing (`state:reset()`, `override = nil`, `set_player(nil)`)
  rather than calling the shell's `reset()` local. Implementing the letter of the
  plan would have left a new character with a HUD disabled by a render failure
  they never saw and were never told about — recoverable only by typing
  `/incursion` they had no reason to type.
- **Fix:** `incursion.render_off = false;` added to the profile-switch callback,
  beside the `override` clear it already does, with a comment saying plainly that
  the callback does not route through `reset()`. One check added to the existing
  character-change block so the behaviour is asserted rather than merely present.
- **Files modified:** `inctrack/inctrack.lua`, `test/run_tests.py`
- **Verification:** `addon` 111 → 112 checks; suite green on both backends. The
  comment in `reset()` was also worded to claim only what is true (that it gives
  `/incursion reset` its recovery), rather than repeating the plan's incorrect
  assumption about the profile path.
- **Committed in:** `6508d0b` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** None on scope. It is one line in a branch the plan already
named, plus the check that makes it honest. `grep -c "render_off"` reads 7 rather
than the 4-or-more the plan required, and `grep -c "render_ok"` reads 6 rather
than 3-or-more; both are above their floors. No file outside the plan's three was
touched.

## Issues Encountered

None. The plan's `read_first` pointers were accurate, the RED run failed in
exactly the shape predicted, and both negative controls produced exactly the
failures the plan said they should.

## Carry-forwards — recorded, not acted on

Noted while working in the files, deliberately left alone per the plan's scope
fence:

- **The per-frame options table** (`inctrack.lua`, the `{ visible = ..., locked =
  ... }` literal handed to `ui.render`) is still allocated sixty times a second.
  It was directly under the hands during the frame-handler rewrite and was
  deliberately not hoisted, not reshaped, and still passes `visible = true` —
  two Phase-1 assertions read what `render` returns for that value. **Phase 4,
  PERF.**
- **The `parse error: %s` line from the `text_in` handler is unrate-limited**, and
  after this plan it is now **the only chat output in the addon with no
  report-once guard**. A systematically malformed line would flood chat exactly
  the way a render failure used to. **Phase 4.**
- **`docs/design.md` drift and the stale `ui.lua:15-26` layout comment** —
  **DOC-01/02, Phase 4.**
- Also unchanged and still open from earlier phases: the `right_text`
  right-alignment finding from Phase 1 (correct as written, not a defect), and
  Phase 2's two in-game checks.

**Nothing was deployed to the live install by this plan.** The whole of HARD-01 is
assertable in the harness. The one thing that is not — that Ashita's real ImGui
binding accepts `pcall(imgui.End)` and `pcall(imgui.PopStyleVar, 1)` reached
through its `__index` metatable — is carried as coverage item D8 alongside the two
in-game checks already open from Phase 2.

## Next Phase Readiness

- **HARD-01 is closed.** `03-02` (HARD-02/03/04, the parser tightenings) and
  `03-03` (HARD-05/06, restore validation and `pending_time`) are unblocked and
  independent of this work: neither touches `inctrack.lua`, `ui.lua` or the
  frame path.
- **New capability available to later plans:** the recorder's `arm_fault` can put
  a raise anywhere in the render tree. Nothing else needs it yet, and it stays
  off unless armed.
- **The standing guarantee holds**: 13,037 checks over 127 logs, zero known
  defects, green on both backends, no suite below its floor.

---
*Phase: 03-fragile-paths*
*Completed: 2026-08-29*

## Self-Check: PASSED

- Files claimed created/modified all exist on disk: `03-01-SUMMARY.md`,
  `inctrack/inctrack.lua`, `test/stubs.py`, `test/run_tests.py`.
- All three task commits resolve in git history: `d35235c`, `08bf3c2`, `6508d0b`.
- `git status --porcelain inctrack/` is clean; `git diff --name-only` over the
  plan's commits lists exactly `inctrack/inctrack.lua`, `test/run_tests.py` and
  `test/stubs.py` — `ui.lua`, `parser.lua` and `state.lua` untouched.
- Phase 2's CR-01 is intact: `ui.lua:416` is still
  `imgui.Begin('inctrack###incursion_window', nil, flags)` and the recorder's
  `Begin` is still strictly positional.

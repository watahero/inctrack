---
phase: 02-the-three-defects
verified: 2026-08-29T00:21:40Z
status: human_needed
score: 4/5 must-haves verified
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
behavior_unverified_items:

  - truth: "In game: `/addon reload inctrack` mid-run leaves the instance clock agreeing with the server's next `You have N minutes remaining` line, instead of being optimistic by the downtime."
    test: >-
      In an Incursion on CatsEyeXI with the deployed build loaded: (1) note the
      instance clock the window shows and the wall-clock time; (2) run
      `/addon reload inctrack` and leave the addon unloaded for a measurable
      gap -- two minutes or more, if the run allows; (3) reload and read the
      instance clock the moment the window returns; (4) wait for the server's
      next `You have N minutes remaining inside this Incursion.` line.
    expected: >-
      At step 3 the restored clock is lower than the pre-reload value by
      approximately the downtime, and the elapsed counter is higher by the same
      amount. At step 4 the server's N minutes agrees with what the window was
      already showing, to within a minute (the server reports whole minutes).
      FAIL if the window comes back showing the pre-reload time_left unchanged,
      or if the server's line forces the clock to jump down by roughly the
      downtime when it arrives.
    why_human: >-
      Only a real reload against a real server clock exercises the two clocks
      the addon mixes -- os.time() across process death and the injected
      monotonic os.clock. The suite can only simulate the gap by rewriting
      saved_at, which is exactly the term under test.
human_verification:

  - test: >-
      In an Incursion on CatsEyeXI with the deployed build loaded: (1) note the
      instance clock the window shows and the wall-clock time; (2) run
      `/addon reload inctrack` and leave the addon unloaded for two minutes or
      more if the run allows; (3) reload and read the instance clock the moment
      the window returns; (4) wait for the server's next
      `You have N minutes remaining inside this Incursion.` line.
    expected: >-
      Step 3: restored clock lower by ~the downtime, elapsed higher by the same.
      Step 4: the server's N agrees with the window to within a minute. FAIL if
      the clock came back unchanged, or if the server's line makes it jump down
      by roughly the downtime.
    why_human: >-
      ROADMAP success criterion 4. Needs a human inside a live Incursion; the
      suite can only simulate the gap by rewriting the very field under test.

  - test: >-
      Same session, immediately after the reload above: look at the window and
      try to interact with its frame. (1) Is there a title bar or a close [x]?
      (2) Drag the window's right or bottom edge -- does it resize? (3) Let the
      content change height (a bonus objective appearing or expiring, an
      objective line appearing) -- does the window auto-fit rather than clip or
      leave dead space? (4) `/incursion lock`, then try to drag the window.
      (5) `/incursion` -- does it still toggle the window away and back?
    expected: >-
      No title bar and no close control. Not resizable by dragging. Height
      auto-fits the content (AlwaysAutoResize). Locked, the window cannot be
      dragged (NoMove). `/incursion` still toggles. FAIL on any title bar
      appearing, any resize handle, a fixed height that clips or pads content,
      `/incursion lock` no longer preventing a drag, or a per-frame Lua error
      in the Ashita console mentioning `bad argument #2` / `Begin`.
    why_human: >-
      Code review CR-01 changed the live render call from
      `imgui.Begin(name, flags)` to `imgui.Begin(name, nil, flags)` on the
      strength of Ashita's SDK header and a survey of other addons, not on an
      observed frame. The window flags reach the compiled binding, whose own
      type handling cannot be inspected (no source ships with the install), so
      the only proof the flags actually land is a rendered window. The suite
      pins the call's argument positions against a stub, which is a claim about
      the host rather than a fact derived from it.
audit_acknowledged:
  milestone: v1.2.0
  at: 2026-08-29
  status: human_needed
---

# Phase 2: The Three Defects — Verification Report

**Phase Goal:** The three faults visible in the code as written are gone, and the tests that were red before them are green — demonstrated, not asserted.
**Verified:** 2026-08-29T00:21:40Z
**Status:** human_needed
**Re-verification:** No — initial verification
**Verified against:** `9b8594e` (working tree clean for all tracked files)

---

## Method

The SUMMARY files were read for orientation and then set aside. Every verdict
below rests on a command I ran, an observation I made in the code, or a
mutation I introduced and watched the suite catch.

Mutation testing was done in a **local clone** at
`<scratch>/clone`, created with `git clone --local --no-hardlinks`. The real
checkout at `C:\Users\badr\inctrack` was never modified — `git status` reports
no changes to any tracked file, before or after.

Fourteen mutations were applied. Each reverts one specific fix or guard and
asks whether the suite notices. A fix nobody can break is a fix nobody has
proved.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The three Phase-1 regression tests pass **without their assertions being edited** | ✓ VERIFIED | Two independent audits, both negative-controlled. See SC1 below. |
| 2 | A non-boss points award leaves `Phases cleared` unchanged; a boss kill raises it by exactly one; `phases_cleared` has a single author | ✓ VERIFIED | Direct behavioural probe of the shipped `state.lua` + mutations M1/M2. See SC2. |
| 3 | Serialise/restore across a simulated 10-minute gap moves `time_left`, elapsed and the bonus countdown by that gap; `saved_at` is the correction term | ✓ VERIFIED | Direct behavioural probe: −600 / +600 / bonus dropped + mutations M3/M4/M5. See SC3. |
| 4 | In game: `/addon reload inctrack` mid-run leaves the instance clock agreeing with the server's next `You have N minutes remaining` line | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Arithmetic proven under a simulated gap; the two-clock mix across real process death is not exercisable here. Build is deployed and byte-identical, so the check is runnable. |
| 5 | No unreachable close affordance remains — grep finds no `ARG_OPEN` in `ui.lua` and no `shown == false` in `inctrack.lua` | ✓ VERIFIED | Grep clean; mutation M7 reinstating the defect re-reddens the byte-identical Phase-1 FIX-03 assertion. See SC5. |

**Score:** 4/5 truths verified (1 present, behaviour-unverified)

---

## SC1 — The assertions were not edited

**Status: ✓ VERIFIED**

### The four audited items

`b8a19fa` (`docs(01): mark Phase 1 complete`) is the baseline. Phase 1 wrote
three `res.xfail(...)` calls plus one ordinary `res.check(...)` precondition
that stops FIX-03's disjunction being satisfied by a frame that drew nothing.
All four survive at HEAD with their **condition and message byte-identical**;
the only change is the callee, `res.xfail(` → `res.check(`, and the dropped
trailing defect-id argument. That conversion is forced by the mechanism, not a
convenience: `Result.xfail` routes a condition that *holds* into `fixed`, which
`main()` turns red — a fixed defect cannot stay an xfail.

### Audit 1 — the project's own script

```
$ cd C:/Users/badr/inctrack && python /tmp/inctrack-assert-integrity.py
baseline b8a19fa  docs(01): mark Phase 1 complete
FIX-01  INTACT -- 225 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-02  INTACT -- 559 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03  INTACT -- 178 bytes of condition and message, byte-identical to Phase 1, now inside res.check(...)
FIX-03-precondition  INTACT -- 147 bytes ...
VERDICT: all 4 audited assertions intact.
audit exit: 0
```

I read the script before trusting it. It scans forward from the callee token
with a string- and comment-aware paren counter, decodes latin-1 so the
shift-jis boon glyph in a fixture cannot be normalised away, and additionally
requires the surviving text to be *preceded by* `res.check(` and *followed by*
`)` — so smuggling the bytes into a comment or a dead branch reports MISPLACED
rather than INTACT.

### Audit 2 — my own, by a different mechanism

An exit-0 from one script is one script's opinion. I wrote an independent audit
that parses both revisions with Python's own `ast` module and compares
`ast.dump()` of the condition and message arguments — insensitive to the paren
scanner's correctness, sensitive to any semantic change:

```
FIX-01             INTACT   baseline=res.xfail -> now=res.check ; cond AST equal ; msg AST equal
FIX-02             INTACT   baseline=res.xfail -> now=res.check ; cond AST equal ; msg AST equal
FIX-03             INTACT   baseline=res.xfail -> now=res.check ; cond AST equal ; msg AST equal
FIX-03-pre         INTACT   baseline=res.check -> now=res.check ; cond AST equal ; msg AST equal
VERDICT: 4/4 intact
```

### Negative control — both audits, four separate one-item mutations

Run in the clone, restoring between each. An exit-0 verdict from an audit that
cannot fail is worthless, so this establishes that it can:

| Mutation | Their audit | My audit |
|---|---|---|
| FIX-01 condition `== 0` → `>= 0` | exit 1, `1 of 4 ... edited` + diff | exit 1, `cond_same=False` |
| FIX-02 tolerance `<= 2` → `<= 700` | exit 1 + diff | exit 1, `cond_same=False` |
| FIX-03 message: one added full stop | exit 1 + unified diff of the string | exit 1, `msg_same=False` |
| FIX-03-precondition: `window` → `windows` | exit 1 + unified diff | exit 1, `MISSING` |
| *(unmutated clone, control)* | exit 0, all 4 INTACT | exit 0, 4/4 |

Both audits caught all four. The exit-0 verdict on the real tree is not vacuous.

### The assertions that *were* changed — and why this is still a pass

Enumerating every removed `res.check(` line across the whole
`b8a19fa..HEAD` diff of `test/run_tests.py` gives exactly five, and nothing
else:

| Removed | Replaced by | Assessment |
|---|---|---|
| `phases_cleared == active["point_events"]` (suite 3 cross-check) | `phases_cleared == want_cleared`, re-derived from the phase-number sequence in the raw log text | **Explicitly sanctioned.** ROADMAP lines 105-109 carry this as a coverage note: the old assertion "encodes the very defect FIX-01 removes", and its re-derivation "is part of this phase, not a regression". |
| `phases_cleared == 1` (fixture: `Begins!` + two points awards, no phase line) | `== 0`, message now `"a points award moved the count of cleared phases on its own"` | Same class — the old value *was* the defect. Stronger: the message now names the rule instead of saying "wrong". |
| `phases_cleared == 3` (after a boss kill in phase 3) | `== 2`, `"a points award during phase 3 was counted as a fourth cleared phase..."` | Same class, same reasoning. |
| `int(s2.bonus_remaining) == int(s.bonus_remaining)` | `abs(...) <= 1` | A genuine widening, of one second, **causally forced by FIX-02**: `restore()` now subtracts a real `os.time()` gap, so the wall-clock second can tick between encode and decode. One is the exact maximum. |
| `int(s2.time_left) == int(s.time_left)` | `abs(...) <= 1` | Same. |

Read at its narrowest, criterion 1 is about "the three regression tests written
in Phase 1" and is met byte-for-byte. Read at its broadest — *no* Phase-1
assertion text touched anywhere in the file — five lines were touched, but four
of the five are the ROADMAP's own sanctioned re-derivation class and the fifth
pair is a one-second consequence of the fix under test. I record this as
verified with the deviation named rather than hidden.

**Not counted here:** 35 net new checks were added across five suites. Adding
coverage is not editing an assertion.

---

## SC2 — `Phases cleared` has one author

**Status: ✓ VERIFIED**

### Direct behavioural observation

I drove the shipped `parser.lua` + `state.lua` through the harness bootstrap and
printed `phases_cleared` after every line — asserting nothing the suite asserts:

```
  run begins                             cleared=0  awards_seen=0  delta=+0
  phase 1 announced                      cleared=0  awards_seen=0  delta=+0
  objective                              cleared=0  awards_seen=0  delta=+0
  PHASE BOSS kill payout                 cleared=0  awards_seen=1  delta=+0
  phase 2 announced                      cleared=1  awards_seen=1  delta=+1
  bonus offered                          cleared=1  awards_seen=1  delta=+0
  BONUS payout (not a boss)              cleared=1  awards_seen=1  delta=+0
    ...its points award                  cleared=1  awards_seen=2  delta=+0
  CHEST-shaped extra payout (not a boss) cleared=1  awards_seen=3  delta=+0
  phase 3 announced                      cleared=2  awards_seen=3  delta=+1
  PHASE BOSS kill payout                 cleared=2  awards_seen=4  delta=+0
  run completes                          cleared=3  awards_seen=4  delta=+1
```

A bonus payout: +0. A chest-shaped extra payout: +0. Three phases announced,
three cleared. Each boss kill nets exactly one, delivered by the phase line it
causes (and by the completion for the final phase, whose kill produces no phase
line).

### The authors, enumerated

```
$ grep -n "phases_cleared\s*=" inctrack/state.lua
 77:        phases_cleared = 0,              -- initialisation
202:            run.phases_cleared = e.phase - 1;    <- the phase line
429:            run.phases_cleared = closing;        <- the completion
585:        phases_cleared = run.phases_cleared,     -- serialise
699/702:    run.phases_cleared = ...                 -- restore
```

The points handler at the old `:358-365` no longer authors it — it now writes
only `awards_seen`. The two writers criterion 2 names as the defect are down to
one, plus the completion, which `02-CONTEXT.md` and the ROADMAP's own 02-01
plan bullet both name explicitly ("the phase line, plus the completion closing
the final phase").

### Mutations the suite caught

| # | Mutation | Result |
|---|---|---|
| M1 | Reinstate `run.phases_cleared = run.phases_cleared + 1` in the points handler | **4 failures** across two suites, including the byte-identical Phase-1 FIX-01 assertion firing verbatim: *"counted a bonus objective payout as a cleared phase -- the window went from 1 cleared to 2 without a phase boss dying"* |
| M2 | Delete the `complete`-closes-the-final-phase assign | **5 failures** across three suites (state, persistence, ui snapshot) |
| M8 | Import a version-1 blob's count verbatim (revert WR-02) | 2 failures: *"the window says 5 cleared phases on a run the server only ever put at phase 3"* |
| M9 | `awards_seen` falls back to the legacy `phases_cleared` | 1 failure naming the silenced lower-bound marking |
| M10 | Schema back to `version = 1` | 1 failure: `awards_seen lost` |

### The version-1 migration, probed directly (a user *will* hit this)

A blob shaped exactly as shipped 1.1.0 wrote it — `phase = 3`,
`phases_cleared = 5` (award-authored, true count 2):

```
restore(v1 blob) -> ok=True
  cleared=2 awards=0 phase=3 points=300 desync=True recovered=True
then "Complete!" -> cleared=3        (not 6 -- the completion assigns, not adds)
v1 blob with no phase at all -> ok=True, cleared=0
version 3 (unknown future)   -> ok=False, NO RUN
version 2 blob               -> ok=True, cleared=2 awards=4 (own fields kept)
```

The migration is sound in the direction that matters: the cleared count is
re-derived from `phase`, the one field a 1.1.0 blob carries that the server
authored outright; `awards_seen` resets to 0, which *marks* rather than hides
(an over-stated award count would silence `points_partial` for the rest of the
run); an unknown future version is refused rather than half-applied; and points,
boons, bonus and elapsed are preserved rather than the whole live run being
discarded.

### WR-01, probed directly

```
cold "Complete!" only            -> cleared=0   (nothing invented)
"Begins!" -> "Complete!"         -> cleared=1   (a run we watched begin cleared one)
```

### Real-log cross-check

Suite 3 (`state: run reconstruction`, 888 checks over 127 logs) recomputes the
expected cleared count from the phase-number sequence in raw log text and
compares it to what `state.lua` produced. Green.

---

## SC3 — `restore()` ages the clocks by the gap

**Status: ✓ VERIFIED**

### Direct behavioural observation

Serialise two minutes into a 90-minute instance with a bonus holding 6 minutes,
push `saved_at` back 600 seconds, reset the monotonic clock to simulate a fresh
process, restore:

```
saved:    time_left=5280  elapsed=120  bonus_remaining=360
restored: ok=True  time_left=4680  elapsed=720  bonus=dropped
  time_left moved by  -600 s   (criterion wants -600)
  elapsed   moved by  +600 s   (criterion wants +600)
  bonus had 360 s left (< 600) -> dropped
```

A bonus with time to spare across the same gap is **moved, not reset and not
dropped**:

```
bonus_remaining 1740 -> 1140   (moved -600); kept=True
```

`saved_at` is the correction term: with the stamp removed from the blob, the
restore performs no ageing at all.

### Mutations the suite caught

| # | Mutation | Result |
|---|---|---|
| M3 | `time_left` not aged | Phase-1 FIX-02 assertion fires verbatim: *"...came back claiming 5280 seconds left instead of 4680..."* |
| M4 | `started` re-seed drops the gap (elapsed not aged) | *"...720 seconds elapsed instead of 720..."* → observed 120 |
| M5 | Bonus expiry not aged | 2 failures, incl. *"a surviving bonus countdown was not moved down by the reload gap: 1200 seconds left, expected 600"* |
| M11 | Drop the WR-04 expired-instance guard | 2 failures: *"restore resumed a run the instance clock proves ended during the gap"* and *"a refused restore left a half-applied run behind"* |

### WR-04 guard, probed directly

```
2h away, 10m was left   -> ok=False  NO RUN      (refused, nothing half-applied)
90s away, 10m was left  -> ok=True   run resumed (not a second staleness window)
11m away, 10m was left  -> ok=True   (gap 660 > 600+60 is false -- the documented
                                      60s slack; the server reports whole minutes)
```

---

## SC4 — the in-game reload check

**Status: ⚠️ PRESENT_BEHAVIOR_UNVERIFIED — routed to human verification**

The arithmetic is proven (SC3). What is not proven here is the behaviour across
a *real* process boundary, where `os.time()` survives and the injected
`os.clock` may or may not restart. The suite simulates the gap by rewriting
`saved_at`, which is the very term under test — the simulation cannot falsify
the mechanism it assumes.

Preconditions for the human check are satisfied:

```
$ diff --strip-trailing-cr inctrack/<f> "C:/Games/.../Ashita/addons/inctrack/<f>"
  inctrack.lua  IDENTICAL
  state.lua     IDENTICAL
  ui.lua        IDENTICAL
  parser.lua    IDENTICAL

$ grep -n imgui.Begin "C:/Games/.../Ashita/addons/inctrack/ui.lua"
416:    if imgui.Begin('inctrack###incursion_window', nil, flags) then
```

The deployed build carries the CR-01 fix, so both human items below are
runnable in one session. **Not claimed as passed.** Procedures are in the
frontmatter `human_verification` list.

---

## SC5 — the dead close path is gone

**Status: ✓ VERIFIED**

The criterion is written as a literal grep, and the grep branch is satisfied:

```
$ grep -c ARG_OPEN inctrack/ui.lua              -> 0
$ grep -c shown    inctrack/inctrack.lua        -> 0
$ grep -rn "ARG_OPEN\|shown == false" inctrack/ -> exit 1 (no match)
```

Nothing reachable was lost with it. `incursion.override` — the manual dismiss
the removed branch wrote to — still has five live writers (`inctrack.lua:98,
186, 236, 257, 281`), so `/incursion`, `/incursion reset`, the profile switch
and the run-start auto-show all still work. The addon suite holds at 83 checks.

### Mutation M7 — reinstate the defect

Adding `local ARG_OPEN = { true };` back and calling
`imgui.Begin(name, ARG_OPEN, flags)` without honouring the box produces
**9 failures**, including the byte-identical Phase-1 FIX-03 assertion firing
verbatim:

```
FAIL the window asks for a close button and then ignores it -- clicking close leaves the window on screen
FAIL the window asks for a close control it can never show -- it is drawn without a title bar, so the player has nothing to click
FAIL Begin's slot 2 is <Lua table ...>, not nil -- ...
```

### CR-01, verified as instructed

The code review's Critical finding — FIX-03 had changed
`Begin(name, close_box, flags)` to `Begin(name, flags)`, a shape no other addon
in the install uses and which Ashita's SDK header does not declare — **is
really fixed**. `ui.lua:416` reads `imgui.Begin('inctrack###incursion_window',
nil, flags)`, and the same line is in the live install.

**The stub genuinely catches a reversion.** M6 (revert to `Begin(name, flags)`)
produces **14 failures**, all six window snapshots plus four explicit
positional pins:

```
FAIL ... drew "Begin '...' p_open=4169 flags=none", expected "... p_open=nil flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar"
FAIL Begin was called with 2 arguments -- the host's signature is Begin(name, p_open, flags), so a shorter call leaves the flags behind entirely
FAIL a number reached Begin's slot 2, which is p_open and not flags -- in game every flag ui.render computed would be dropped
FAIL Begin's slot 2 is 4173, not nil -- ...
FAIL Begin's slot 3 holds None rather than a flags number -- ...
```

`test/stubs.py` is now strictly positional (`local _, p_open, flags = ...`),
with the type-sniff removed, and `ImGuiRecorder._begin_line` renders by slot
rather than by type.

**And the guard survives the stub being re-softened.** M12 reinstated the
numeric-slot-2 sniff in the stub alone — the suite still passes, because the
shipped code passes `nil` there, so the leniency is dormant. The load-bearing
question is the combination, so M13 applied *both* the softened stub and the
CR-01 call shape: still **14 failures**. The explicit positional `res.check`
pins read the raw recorded arguments, so they hold even if the stub's `Begin`
body were made permissive again. The guard is not single-point.

---

## Standing Guarantees (milestone-wide)

| Guarantee | Status | Evidence |
|---|---|---|
| Full suite green against the author's chatlogs; no pre-existing suite's count may fall | ✓ HELD | See the table below. 13,008 checks over 2,944,071 lines from 127 logs; PASS, exit 0. |
| Same, on `luajit21` — the backend Ashita embeds | ✓ HELD | `INCTRACK_LUA=luajit21` → identical counts, PASS, exit 0. |
| Suite 2: no generic-tier pattern matches anything in today's logs | ✓ HELD | `parser: generic tier matches nothing today  1 checks  ok` / `all real lines handled by a specific pattern` |
| Purity boundary: `parser.lua` / `state.lua` gain no Ashita dependency | ✓ HELD | `grep -nE "ashita\|AshitaCore\|imgui\|require\(" inctrack/parser.lua inctrack/state.lua` → no match. Stub changes are confined to `test/stubs.py`. |
| No instance/boss/mob/objective/difficulty name in any Lua file | ✓ HELD (no regression) | No added Lua line in `b8a19fa..HEAD` contains one. Pre-existing occurrences are pattern-example *comments* in `parser.lua` and the stale layout comment at `ui.lua:15-26`, both untouched by this phase and the latter already owned by Phase 4 / DOC-01. |

### Per-suite counts against the Phase-1 floor

| Suite | Phase-1 floor | Observed | |
|---|---|---|---|
| parser: structural | 11819 | 11819 | = |
| parser: generic tier | 1 | 1 | = |
| state: run reconstruction | 888 | 888 | = |
| state: objectives, bonus, recovery | 38 | 53 | +15 |
| adaptability | 20 | 20 | = |
| disconnect | 23 | 23 | = |
| timers | 21 | 25 | +4 |
| persistence | 25 | 31 | +6 |
| ui | 55 | 65 | +10 |
| addon | 83 | 83 | = |
| **total** | 12,973 | **13,008** | +35 |

No suite fell. The `0 known defects` line and the empty
`EXPECTED_XFAILS` / `EXPECTED_DEFECTS` guards both hold.

---

## Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|---|---|---|---|
| Full suite, no chatlogs | `python test/run_tests.py` | PASS, exit 0 | ✓ PASS |
| Full suite, 127 chatlogs | `python test/run_tests.py "<Ashita>\chatlogs"` | PASS, exit 0, 2,944,071 lines / 127 logs, 13,008 checks | ✓ PASS |
| Full suite, shipped backend | `INCTRACK_LUA=luajit21 python test/run_tests.py "<Ashita>\chatlogs"` | PASS, exit 0, identical counts | ✓ PASS |
| Assertion integrity (project script) | `python /tmp/inctrack-assert-integrity.py` | all 4 INTACT, exit 0 | ✓ PASS |
| Assertion integrity (independent, AST) | `python <scratch>/independent_audit.py test/run_tests.py` | 4/4 intact, exit 0 | ✓ PASS |
| Assertion integrity — negative control | 4 one-item mutations, both scripts | both exit 1 on every mutation | ✓ PASS |
| Criterion 2 behaviour | direct probe of shipped Lua | bonus +0, chest +0, phase line +1, completion +1 | ✓ PASS |
| Criterion 3 behaviour | direct probe of shipped Lua | −600 / +600 / bonus dropped; spare bonus moved −600 | ✓ PASS |
| v1 → v2 migration | direct probe with a 1.1.0-shaped blob | 5 → 2, completion → 3 not 6; v3 refused | ✓ PASS |
| Deployment parity | `diff --strip-trailing-cr` × 4 files | all IDENTICAL | ✓ PASS |
| Criterion 4 (in game) | needs a live Incursion | — | ? SKIP → human |
| CR-01 window shape (in game) | needs a rendered frame | — | ? SKIP → human |

## Mutation Testing

All in the clone; the real checkout was never modified.

| # | Mutation | Suite reaction |
|---|---|---|
| M1 | FIX-01: points handler authors `phases_cleared` again | 4 failures (state, disconnect) — Phase-1 FIX-01 assertion fires |
| M2 | FIX-01: `complete` no longer closes the final phase | 5 failures (state, persistence, ui) |
| M3 | FIX-02: `time_left` not aged | 1 failure — Phase-1 FIX-02 assertion fires |
| M4 | FIX-02: elapsed not aged | 1 failure — same assertion |
| M5 | FIX-02: bonus expiry not aged | 2 failures |
| M6 | CR-01: `Begin(name, flags)` | 14 failures (ui) |
| M7 | FIX-03: reinstate the unreachable close box | 9 failures — Phase-1 FIX-03 assertion fires |
| M8 | WR-02: import the v1 count verbatim | 2 failures (persistence) |
| M9 | WR-02: `awards_seen` inherits the legacy count | 1 failure |
| M10 | WR-02: schema back to `version = 1` | 1 failure |
| M11 | WR-04: drop the expired-instance guard | 2 failures (timers) |
| M12 | Stub: reinstate the numeric-slot-2 sniff, alone | PASS — dormant (see M13) |
| M13 | Stub sniff **plus** the CR-01 call shape | 14 failures — guard is not single-point |
| A1-A4 | One-character edits to each audited assertion | both audits exit 1 |

Twelve of the fourteen mutations were caught. M12 passing is correct and
explained: the leniency it restores is unreachable while the code passes `nil`,
and M13 proves the combination is still caught.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| FIX-01 | 02-01 | A boss kill increments `phases_cleared` exactly once; the count has a single author | ✓ SATISFIED | SC2 — direct probe, `grep` on the writers, M1/M2 |
| FIX-02 | 02-01 | After unload/reload, `time_left` and the bonus expiry reflect the elapsed downtime via `saved_at` | ✓ SATISFIED (arithmetic) / ? NEEDS HUMAN (in game) | SC3 probe + M3/M4/M5; criterion 4 open |
| FIX-03 | 02-02 | No unreachable close path remains | ✓ SATISFIED | SC5 — grep clean, M7; CR-01 window shape needs a human eye |

No orphaned requirements: `REQUIREMENTS.md` maps FIX-01/02/03 to Phase 2 and
all three are claimed by the phase's plans.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | `TBD` / `FIXME` / `XXX` / `TODO` / `HACK` / `PLACEHOLDER` in any phase-modified file | — | **None found.** Scanned `state.lua`, `ui.lua`, `inctrack.lua`, `run_tests.py`, `stubs.py`. |

The one `placeholder` hit (`run_tests.py:1916`) is an assertion *message* about
`clock_str(None)` returning a real string rather than a placeholder — the
opposite of a stub marker.

---

## Informational — recorded so a later reader does not re-litigate it

1. **`phases_cleared` briefly under-reports between a boss kill and the next
   phase line.** With the phase line as sole author, the HUD sits one low for
   the seconds between the kill and the server's announcement. This is the
   design decision recorded in `02-CONTEXT.md` ("The phase line is the sole
   author... a points award is not exclusively a boss kill"), it errs in the
   safe direction, and the completion closes the final phase so a finished run
   is never short. In scope, decided, not a gap.

2. **IN-07 confirmed harmless on the shipped backend, still a test blind spot.**
   I checked the two backends directly: `luajit21` renders `tostring(2.0)` as
   `"2"`, so a restored float count cannot show as `2.0` in game; the test
   backend (Lua 5.5) renders `"2.0"`, and no test renders a *restored* run. The
   review left IN-07 open deliberately. Not a Phase-2 criterion; a Phase-4
   candidate alongside DOC-01.

3. **The WR-04 guard's boundary is inclusive of the slack.** `gap > time_left
   + 60`, so a gap of exactly `time_left + 60` resumes. Documented in the code
   comment and deliberate (erring toward keeping a run that might still be
   live). Observed: 11 minutes away with 10 minutes left resumes.

4. **IN-01 through IN-07 remain open** and are correctly scoped out: IN-01 is
   Phase 3 / HARD-05, IN-03 and IN-06 are Phase 4, and IN-02/04/05/07 are
   unclaimed. IN-01 in particular notes that FIX-02 *enlarged* the surface
   HARD-05 must cover (`data.time_left - gap` now does arithmetic on an
   unvalidated field, outside any `pcall`). Phase 3 should not lose sight of it.

---

## Gaps Summary

**No gaps.** Every artifact this phase promised exists, is substantive, is
wired, and — where it changes runtime behaviour — was proven by reverting it
and watching the suite go red.

The single open item is ROADMAP success criterion 4, which is written as an
in-game check and is not closeable by any test suite. Alongside it, the code
review's CR-01 fix changed the live render call on the strength of a header and
a survey rather than a rendered frame, so the window's shape wants one human
look. Both are runnable in a single Incursion; the deployed build is
byte-identical to the repository.

Status is `human_needed`, not `passed`, and deliberately so.

---

_Verified: 2026-08-29T00:21:40Z_
_Verifier: Claude (gsd-verifier)_

---
phase: 01-the-net
verified: 2026-08-29T03:05:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification — no prior 01-VERIFICATION.md existed
---

# Phase 1: The Net — Verification Report

**Phase Goal:** The suite can reach the two files it has never reached, and each
confirmed defect is visible as a named failing test rather than a claim in an
audit document.

**Verified:** 2026-08-29
**Status:** passed
**Re-verification:** No — initial verification
**Method:** every command below was run in this verifier's own process against
the working tree. Where an assertion's *substance* was in question, it was
tested by mutation: the addon was copied to a scratch tree, a regression was
introduced into the copy, and the suite was re-run to see whether it went red.
`inctrack/` in the repository was never touched.

## Goal Achievement

### Observable Truths (the five ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ui.lua` loads against an ImGui stub; draw calls, colours and text asserted, including the seven pure helpers and the `STAT_SHORT` ordering contract | ✓ VERIFIED | `ui` suite reports **55 checks**. All seven helpers directly asserted (`run_tests.py:1652-1789`). Mutation-proved (M1/M3/M4 below). |
| 2 | `inctrack.lua` loads against an Ashita stub; registration, `text_in` + `pcall`, settings/`MUST_SAVE`, all `/incursion` subcommands, `visible()`, profile switch | ✓ VERIFIED | `addon` suite reports **83 checks**, every named item present (`run_tests.py:2012-2413`). Mutation-proved (M6/M7b/M8 below). |
| 3 | With no chatlogs and no Ashita install the run completes, both new suites report non-zero checks, header reads `chatlogs: none` | ✓ VERIFIED | Run performed; header `chatlogs: none`, `ui` 55, `addon` 83, exit 0. Structurally guaranteed: `test_ui()` / `test_addon_shell()` take no arguments (`run_tests.py:2486-2487`) and `stubs.py` performs no filesystem access. |
| 4 | The failure list is exactly three entries, one per FIX-01/02/03, named in user terms; no previously-green suite regresses and its check count does not fall | ✓ VERIFIED | Full run: exactly 3 `XFAIL` lines with the correct three ids. Pre-phase harness re-run for a true side-by-side: no suite fell, two rose (+152 total). |
| 5 | The addon source is unchanged — `git diff` over `inctrack/` is empty | ✓ VERIFIED | `git diff --stat 7ec9559 HEAD -- inctrack/` → empty. `git diff --name-only 7ec9559 HEAD` lists only `test/*` and `.planning/*`. |

**Score:** 5/5 truths verified (0 present, behaviour-unverified)

---

## Evidence

### Criterion 3 — the no-chatlogs, no-Ashita run

```
$ env -u INCURSION_CHATLOGS -u INCURSION_ASHITA_LIBS python test/run_tests.py
inctrack tests
  lua: Lua 5.5
  chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)

  state: objectives, bonus, recovery               38 checks  ok (2 known defects)
      XFAIL counted a bonus objective payout as a cleared phase -- ...
      XFAIL clock was optimistic by the reload gap after a reconnect -- ...
  adaptability: unseen content still tracked       20 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             21 checks  ok
  persistence: json round trip                      0 checks  ok
      skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)
  ui: helpers, layout contract, render             55 checks  ok (1 known defects)
      XFAIL the window asks for a close button and then ignores it -- ...
  addon: load, chat, settings, commands            83 checks  ok

  3 known defects (expected until Phase 2)

PASS
EXIT=0
```

`persistence` degrading to 0 checks with a printed skip reason is the correct
"no Ashita install" behaviour: `find_ashita_libs(None)` returns `None`
(`run_tests.py:82-90`), and only that suite consumes it. The two new suites
receive no path argument at all, so they cannot be gated on private data.

The same result was reproduced from a scratch tree containing only `inctrack/`
and `test/`, with no Ashita install anywhere on its path — `ui` 55, `addon` 83,
`PASS`.

### Criterion 4 — the full run, and the pre/post check-count comparison

```
$ python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2944063 chat lines from 127 logs, character Godwen
  ...
  3 known defects (expected until Phase 2)
PASS   (EXIT=0)
```

To avoid taking the SUMMARY's word for "no regression", the pre-phase harness
was extracted (`git show c5ec5bb:test/run_tests.py`) and run against the same
127 logs in this verifier's process:

| Suite | Pre-phase (c5ec5bb) | Now (HEAD) | Δ |
|---|---|---|---|
| parser: structural lines all parse | 11819 | 11819 | 0 |
| parser: generic tier matches nothing today | 1 | 1 | 0 |
| state: run reconstruction | 888 | 888 | 0 |
| state: objectives, bonus, recovery | 29 | 38 | **+9** |
| adaptability | 20 | 20 | 0 |
| disconnect | 23 | 23 | 0 |
| timers | 21 | 21 | 0 |
| persistence: json round trip | 20 | 25 | **+5** |
| ui (new) | — | 55 | +55 |
| addon (new) | — | 83 | +83 |
| **Total** | **12,821** | **12,973** | **+152** |

No pre-existing suite's count fell. Suite 2 (generic tier) still matches nothing
in today's logs. The three failures are exactly FIX-01, FIX-02, FIX-03, each
phrased in user terms ("counted a bonus objective payout as a cleared phase",
"clock was optimistic by the reload gap after a reconnect", "the window asks for
a close button and then ignores it").

Exit code behaviour confirmed both directions: `0` with the three expected
failures, `1` when a real check fails.

### Cross-backend

`INCTRACK_LUA=luajit21 python test/run_tests.py` — the backend Ashita actually
embeds — produces identical counts (`ui` 55, `addon` 83) and `PASS`. CR-01 is
genuinely closed; the six window snapshots are no longer pinned to Lua 5.5.

---

## Substance check: do the assertions actually catch regressions?

Presence of an assertion is not evidence that it constrains anything. Seven
regressions were introduced into an isolated copy of the addon and the suite
re-run. Six were caught; the seventh was an invalid mutation on the verifier's
part, not a test gap.

| # | Regression introduced | Suite result | Verdict |
|---|---|---|---|
| M1 | `urgency`: `seconds <= warn_at` → `seconds < warn_at` | `ui` FAILED (1) — *"a timer entering its last five minutes stayed in the ordinary colour (300 seconds)"* | ✓ caught, boundary is real |
| M2 | `STAT_SHORT`: `Damage taken` moved above `Physical dmg taken` | PASS | **not a defect** — `Damage taken` is not a substring of `Physical dmg taken`, so the reorder is genuinely harmless and `shorten()` is unaffected. Invalid mutation. |
| M3 | Deleted `origin_x = imgui.GetCursorPosX()` (`ui.lua:408`) | `ui` FAILED (7) — all six windows plus *"the window did not take its left edge from ImGui … 8.0, not 11.0"* | ✓ caught; WR-03 closed |
| M4 | `STAT_SHORT`: `Accuracy` moved above `WS Accuracy` (a **true** substring pair) | `ui` FAILED (2) — including *"'Accuracy' is listed before 'WS Accuracy', which contains it, so the longer phrase can never match whole"* | ✓ caught; the ordering contract is real |
| M5 | `ui.render` returns before drawing anything | `ui` FAILED (8) + three `guard:` lines | ✓ caught four ways — see below |
| M6 | `MUST_SAVE` ignored; every event rides the 5s throttle | `addon` FAILED (4) — all four throttle assertions, with write counts named | ✓ caught |
| M7b | `command` registered under an event name the game never fires | `addon` FAILED — suite reported red via the crash-containment path | ✓ caught (run fails; see IN-01 below) |
| M8 | `/incursion lock` changes the setting but skips `settings.save()` | `addon` FAILED (1) — *"the lock setting was changed without being written to disk"* | ✓ caught |

### The FIX-03 trivial-green guard (the item flagged for specific attention)

The code review's concern was that `(not offered_close) or still_shown is False`
is vacuously true when no `Begin` was recorded, so a Phase 2 change that stops
the window rendering would turn the defect test green. **The guard is real and
it fires.** `run_tests.py:1937-1940` places a plain `res.check(bool(begins), …)`
— a hard failure, not an xfail — immediately before the disjunction.

M5 output:

```
  ui: helpers, layout contract, render             55 checks  FAILED (8)
      NOW PASSING the window asks for a close button and then ignores it -- ...
      FAIL the close-button case drew no window at all, so nothing was proved
           about the close button either way
      FAIL a frame during a live run drew no window: []
  2 known defects (expected until Phase 2)
  guard: this phase closes on exactly 3 known defects; the run reported 2
  guard: the failure list must be exactly FIX-01, FIX-02, FIX-03; it is FIX-01, FIX-02
  guard: FIX-03 stopped failing before its fix was written, so the red line that
         was meant to prove the fix never ran
FAIL
```

Four independent mechanisms catch it: the precondition check, the render-gate
check, the `EXPECTED_DEFECTS` identity guard, and the `fixed_ids` "stopped
failing early" guard. A degenerate green is not reachable.

### Are all three xfails durable — can Phase 2 flip them without editing them?

- **FIX-01** (`run_tests.py:720`) — stated as a *delta*
  (`after_bonus - after_boss == 0`), not an absolute. Any single-author fix
  (derive from phase numbers, suppress the increment after `bonus_done`) turns
  it green untouched. A companion `check` asserts both points awards still sum
  to 114, so a fix that simply drops the second award is caught rather than
  mistaken for the real thing. **Durable.**
- **FIX-02** (`run_tests.py:782`) — a three-term conjunction over `time_left`,
  `elapsed` and bonus expiry, with a ±2s tolerance and `saved_at` as the
  correction term. Applying the gap in `restore()` satisfies all three.
  Nil-guarded (`if restored else 0.0 / False`) so a state regression records a
  failure instead of raising. **Durable.**
- **FIX-03** (`run_tests.py:1942`) — a disjunction over the two legitimate
  fixes. Confirmed against the stub's honest close-button model
  (`stubs.py:223-246`: `Begin` writes `false` into the `p_open` box only when
  the flags omit `NoTitleBar`): dropping `p_open` satisfies term 1; dropping
  `NoTitleBar` satisfies term 2. Now guarded against the degenerate case.
  **Durable.**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `test/stubs.py` | Recording ImGui stub, Ashita host fakes, pure-Lua json | ✓ VERIFIED | 1,107 lines. `ImGuiRecorder` (calls/counts/padding/balance/snapshot/arm_close), `AshitaHost` (events, settings, chat, saves, sessions, profile). No filesystem access. |
| `test/run_tests.py` | `Result.xfail`, `make_host`, `lua_locals`, `test_ui`, `test_addon_shell`, the exactly-three guard | ✓ VERIFIED | 2,524 lines (from 956). All named entry points present and wired into `main()`. |
| `inctrack/*.lua` | **unchanged** | ✓ VERIFIED | Empty diff across the whole phase range. |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `test/run_tests.py` | `test/stubs.py` | `import stubs` (`:69`), `class Host(stubs.AshitaHost)` (`:205`) | ✓ WIRED |
| `test/stubs.py` | `inctrack/ui.lua` | `package.loaded['imgui']` pre-populated before `require('ui')` | ✓ WIRED — proven by M1/M3/M4 reaching real `ui.lua` code |
| `test/stubs.py` | `inctrack/inctrack.lua` | `addon`/`ashita.events`/`AshitaCore`/`settings`/`common`/`chat`/`json` injected | ✓ WIRED — proven by M6/M7b/M8 |
| `test_ui` / `test_addon_shell` | `main()` | `run_suite(...)` at `:2486-2487` | ✓ WIRED — both appear in every run's report |
| xfail sites | `main()` guards | `Result.xfail_ids` / `fixed_ids` → `EXPECTED_XFAILS` + `EXPECTED_DEFECTS` | ✓ WIRED — proven by M5 firing all three guards |

### Data-Flow Trace (Level 4)

| Artifact | Value | Source | Real data | Status |
|---|---|---|---|---|
| `ui` snapshots | window text/colours | shipped `ui.lua` driven through the recording stub | yes | ✓ FLOWING |
| `addon` assertions | saves, chat, settings, run record | shipped `inctrack.lua` under host fakes | yes | ✓ FLOWING |
| `L = lua_locals(...)` helpers | `clock_str`, `bar`, `STAT_SHORT`, … | upvalue reflection on the shipped `ui.render` | yes, not reimplementations | ✓ FLOWING |
| fixtures | chat lines | hand-written in `run_tests.py` | intentional (COVR-04) | ✓ by design |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|---|---|---|---|
| Unit-only run completes, both new suites non-zero | `env -u INCURSION_CHATLOGS -u INCURSION_ASHITA_LIBS python test/run_tests.py` | `PASS`, exit 0, ui 55 / addon 83 | ✓ PASS |
| Full run green against 127 logs | `python test/run_tests.py "…\chatlogs"` | `PASS`, exit 0, 12,973 checks | ✓ PASS |
| Runs on the backend Ashita embeds | `INCTRACK_LUA=luajit21 python test/run_tests.py` | `PASS`, identical counts | ✓ PASS |
| Pre-existing counts did not fall | pre-phase harness vs HEAD, same logs | 12,821 → 12,973, no suite down | ✓ PASS |
| Non-zero exit on a genuine failure | mutated copy | exit 1 | ✓ PASS |
| Isolated tree (no Ashita anywhere) | scratch copy of `inctrack/` + `test/` | `PASS`, ui 55 / addon 83 | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist in this project and none are declared by
any plan. The project's single entry point *is* `python test/run_tests.py`,
which was executed above in four configurations. Not applicable.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| COVR-01 | `ui.lua` renders under a stubbed ImGui; draw calls, colours, text assertable | ✓ SATISFIED | `ui` suite, 55 checks; M1/M3/M4 prove the assertions bind |
| COVR-02 | `inctrack.lua` runs under a stubbed Ashita host across registration, `text_in`, settings, commands, visibility | ✓ SATISFIED | `addon` suite, 83 checks; M6/M7b/M8 prove the assertions bind |
| COVR-03 | Every Defect has a regression test that fails today and passes after its fix | ✓ SATISFIED | Three xfails, red today, each traced as flippable-without-edit. The "passes after its fix" half is Phase 2's to demonstrate; Phase 1 owns "fails today", which holds. |
| COVR-04 | New suites run to completion with no chatlogs present | ✓ SATISFIED | Criterion 3 evidence; structurally guaranteed by the zero-argument suite signatures |

No orphaned requirements: `REQUIREMENTS.md` maps exactly COVR-01…04 to Phase 1,
and all four are claimed by the phase's plans.

### Standing Guarantees (milestone-wide)

| Guarantee | Status | Evidence |
|---|---|---|
| Full suite green against the author's chatlogs; check counts only go up | ✓ HELD | 12,973 vs 12,821 pre-phase; no suite fell |
| Suite 2: no generic-tier pattern matches anything in today's logs | ✓ HELD | `parser: generic tier matches nothing today  1 checks  ok` |
| Purity boundary: `parser.lua` / `state.lua` gain no Ashita dependency; stubs live in the harness | ✓ HELD | Neither file changed; grep finds only *comments* mentioning Ashita, no `require` |
| No instance/boss/mob/objective/difficulty name in any Lua file | ✓ HELD | No Lua file changed. The Lua chunks inside `stubs.py` contain no such names (grep clean); fixtures live in Python, per D-12 |

### Anti-Patterns Found

| File | Pattern | Severity | Result |
|---|---|---|---|
| `test/run_tests.py`, `test/stubs.py` | `TBD` / `FIXME` / `XXX` | Blocker if present | **none found** |
| `test/run_tests.py`, `test/stubs.py` | `TODO` / `HACK` / `PLACEHOLDER` / "not yet implemented" | Warning if present | **none found** |
| — | stub returns, hollow props, hardcoded empties | — | none; every suite drives shipped Lua |

No debt markers. Completion is auditable.

### Code Review Closure

`01-REVIEW.md` records 1 critical + 8 warnings, `status: fixed` across nine
commits. The three findings the review itself called load-bearing were
re-verified independently here rather than taken on trust:

- **CR-01** (snapshots pinned to one Lua backend) — closed; `luajit21` run is green.
- **WR-01** (FIX-03 satisfiable by drawing nothing) — closed; M5 proves four guards fire.
- **WR-03** (`origin_x` capture uncovered) — closed; M3 produces a named failure.
- **WR-05/06/07/08** — confirmed present in code: `balance()` includes
  `style_color` and the snapshot loop asserts all three stacks
  (`run_tests.py:1857`); `first_diff` compares unstripped
  (`run_tests.py:1389-1402`); the stubbed and real json are cross-checked both
  ways (`run_tests.py:1260-1311`, the +5 persistence checks); `run_suite`
  converts a suite crash into a reported red suite (`run_tests.py:2423-2450`,
  demonstrated by M7b).

### Human Verification Required

None. Every criterion was resolvable by running the suite and by mutation
testing; nothing in this phase is visual, real-time, or dependent on a live game
client. (Criterion 4's in-game sibling belongs to Phase 2, not here.)

### Gaps Summary

No gaps. All five success criteria hold, all four requirements are satisfied,
all four standing guarantees hold, and the addon source is provably untouched.

---

## Notes (informational, non-blocking)

- **IN-01 — a registration regression reports as a dead suite, not as the named
  check.** M7b showed that breaking `ashita.events.register('command', …)` makes
  the `addon` suite die at the first `fire("command")` and report as *"the suite
  did not finish"*, discarding the more precise *"the addon never asked the game
  for the command event"* failure that had already been recorded. The run still
  goes red, so nothing is missed — this is the documented tradeoff in
  `run_suite`'s docstring, and it is a diagnostic-quality point, not a coverage
  gap.
- **The ROADMAP's baseline paragraph is stale.** It cites "12,841 checks,
  8 suites, 2,943,169 chat lines from 126 logs". The author's chatlog directory
  has since grown to 127 logs / 2,944,063 lines, and the *unmodified* pre-phase
  harness now yields 12,821. Already adjudicated before this verification: the
  contract is "no pre-existing suite's count went down", and it was verified that
  way. Refreshing the ROADMAP text is cosmetic and out of Phase 1's scope.
- **Phase 1 deliberately ends with three expected failures and exit 0.** This is
  by design and is what keeps the milestone-wide "the suite is green" guarantee
  answerable at every point.
- No CI and no linter is a recorded milestone scope decision (PROC-01/02,
  deferred to v2). Not raised as a finding.

---

_Verified: 2026-08-29_
_Verifier: Claude (gsd-verifier)_

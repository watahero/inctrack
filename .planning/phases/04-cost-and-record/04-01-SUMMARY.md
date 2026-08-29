---
phase: 04-cost-and-record
plan: 01
subsystem: performance
tags: [lua, ashita, parser, hot-path, benchmark, allocation, cp1252]

requires:
  - phase: 01-coverage
    provides: the stubbed Ashita host, its strip_colors call counter, and the addon-shell suite that drives text_in through registered handlers
  - phase: 03-fragile-paths
    provides: the render_off / render_ok report-once latches this plan copies, the three tightened parser matchers the gate must not narrow, and the ascii() escaping this plan finishes
provides:
  - "parser.relevant: an allocation-free superset gate over the raw chat line, with an unconditional fall-through for any line carrying a colour-code marker byte"
  - "the shell asking that gate before strip_colors, which is the only place the allocation is actually avoidable"
  - "the timestamp loop gated on a leading '['"
  - "a reject-path benchmark printing the head-of-phase baseline and the post-change figure in the test report, every run"
  - "an opt-in string.gsub counter on the stubbed host, so 'this line allocated nothing' is assertable"
  - "a report-once latch on the parse-error chat line, cleared by /incursion reset and by a character change"
  - "at(): one console-safe helper for every log-derived failure message in the harness"
affects: [04-02, 04-03, milestone-close]

actuals:
  tokens: 77922
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "superset gate: a pre-allocation filter whose needles are literals every matcher requires under every alternation and optional group, with an unconditional fall-through for input it is not entitled to judge"
    - "report-once latch: one field beside render_off, cleared by /incursion reset and by a character change"
    - "benchmark-as-suite: two shapes over one fixed corpus in one run, deterministic counters as the checks and a same-run ratio as the only wall-clock assertion"

key-files:
  created: []
  modified:
    - inctrack/parser.lua
    - inctrack/inctrack.lua
    - test/run_tests.py
    - test/stubs.py

key-decisions:
  - "The remaining-minutes needle is the plural-free 'remaining inside this Incursion' -- it begins after the optional plural, so the one-minute warning is not silently dropped"
  - "A line carrying a colour-code marker byte gets an unconditional yes, so a false negative is impossible rather than unlikely; a coloured irrelevant line costs no more than it did"
  - "The boon needle is the phrase 'gains the effect of ', knowingly the loosest of the seven: it admits every ordinary buff line, which is the right side to be wrong on"
  - "Both gates stay -- the pre-gate saves the allocation on raw text, the anchored rejection keeps the precision on normalised text"
  - "parser.relevant has no type guard, so it stays the handler's first raising string method call and the pcall boundary check keeps proving what it was written to prove"
  - "The gsub counter is opt-in and never installed on a timed host; the counting pass and the timing pass are separate passes on separate hosts"
  - "No rate is an acceptance threshold; the one wall-clock assertion is a same-run, same-corpus ratio with a 1.2x noise margin rather than a bare '>'"
  - "The baseline was taken at the head of the phase against a transcribed copy of the Phase-3 reject path, and Task 1 changed no byte under inctrack/"

patterns-established:
  - "Superset checks are written as an implication over fixtures, never as a copied list of expected booleans, so a matcher added later is covered by adding one fixture"
  - "One fixture per distinct SHAPE a matcher accepts, not one per matcher: every branch of every alternation and every optional group gets its own line"
  - "Every log-derived string in a failure message goes through at(), so a message added later is escaped by using the helper rather than by remembering to"

requirements-completed: [PERF-01, PERF-04]

coverage:
  - id: D1
    description: "A colour-free chat line that is not Incursion-related is rejected before any string is allocated for it: zero strip_colors calls, zero gsub calls, no trim, no timestamp loop"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: PERF-01 -- and 'nothing' now means no allocation either"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#cost: the non-Incursion reject path (strip_colors and gsub counters over the colour-free corpus)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The cheap gate is a proven superset of the matchers: every distinct shape any specific or generic matcher accepts passes it, including the singular-minute warning"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: PERF-01 -- the cheap gate is a superset of the matchers"
        status: pass
      - kind: integration
        ref: "python test/run_tests.py \"C:\\Games\\CatsEyeXI\\catseyexi-client\\Ashita\\chatlogs\" -- parser exactly 11819, generic exactly 1 over 2.95M lines"
        status: pass
    human_judgment: false
  - id: D3
    description: "A line carrying a colour-code marker byte falls through the gate unjudged, so a code sitting inside a needle cannot lose the line"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: a colour code makes the gate decline to judge"
        status: pass
    human_judgment: false
  - id: D4
    description: "The timestamp loop does not run unless the trimmed line starts with '['"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: the timestamp loop only runs for a line that carries a stamp"
        status: pass
    human_judgment: false
  - id: D5
    description: "The test report prints a per-line cost for the non-Incursion reject path -- a head-of-phase baseline and the post-change figure, measured the same way over the same corpus in the same run"
    requirement: PERF-04
    verification:
      - kind: unit
        ref: "test/run_tests.py#cost: the non-Incursion reject path (corpus-is-all-rejects pin, and the 1.2x same-run ratio)"
        status: pass
      - kind: other
        ref: "python test/run_tests.py 2>&1 | grep -ci \"lines/s\" -- prints 3"
        status: pass
    human_judgment: false
  - id: D6
    description: "The 'parse error:' chat line is reported once per session and then silent, with /incursion reset and a character change as the ways back"
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: and it says it once"
        status: pass
    human_judgment: false
  - id: D7
    description: "A failure message from a log-driven suite survives a cp1252 console: the raw log text goes through ascii() before it reaches a Result"
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: the failure message survives the console it is printed on"
        status: pass
    human_judgment: false
  - id: D8
    description: "The cheap gate behaves in the live client as it does against the stubbed host -- a real Ashita colour code on a real Incursion line still starts a run, and no Incursion message stops reaching the window"
    verification: []
    human_judgment: true
    rationale: "The colour-code fall-through is the one rule with no corpus behind it: Ashita's chatlog writer strips colour codes, so all 2.95M recorded lines are colour-free and every coloured fixture in the suite is invented. Only a live session sends a real code."

duration: 40min
completed: 2026-08-29
status: complete
---

# Phase 4 Plan 01: Cost and Record Summary

**A chat line the addon ignores now costs nothing at all — zero `strip_colors`, zero `gsub`, no trim and no timestamp loop, on 97.5% of real chat traffic — behind a seven-needle superset gate whose safety argument is written out below, with the before-and-after printed in the test report every run.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-29T11:50Z (approx)
- **Completed:** 2026-08-29T12:29:46+04:00
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- **PERF-01.** `parser.relevant` answers "could this line possibly be ours?" from seven plain substring searches over the raw message, before anything is allocated for it. The shell asks it before `strip_colors`; `parse` asks it again before `trim`; the timestamp loop now runs only when the trimmed line's first byte is `[`. Five allocations a line became none.
- **PERF-04.** The test report prints, every run, the reject path's cost for two shapes measured side by side on one fixed corpus: the parser as Phase 3 left it, and the parser as it now ships. The head-of-phase baseline is recorded in the harness with its date, commit, backend and Python version.
- **The safety argument is written down, not asserted.** Every needle is a literal the corresponding matcher cannot match without under *every* alternation and *every* optional group in its pattern. The derivation table is below; it was re-derived from `parser.lua` rather than taken from the plan, and then checked empirically over 2,951,129 log lines: **zero** lines the parser accepts, and **zero** `MUST_PARSE` lines, fall outside the gate.
- **A dropped line is now the one thing that cannot happen quietly.** The gate declines to judge any line carrying a colour-code marker byte, and the superset table carries both `You have 90 minutes remaining inside this Incursion.` and `You have 1 minute remaining inside this Incursion.` Three negative controls, all run and recorded, show each of those guards actually holding something up.
- **Two carry-forwards closed.** The `parse error:` chat line — the last chat output in the addon with no report-once guard — got one, in the shape 03-01 established. Every log-derived failure message in the harness now goes through one shared `ascii()`-safe helper, and that helper is unit-tested on a U+FFFD byte in a suite that runs on machines the messages it protects never reach.

## Task Commits

1. **Task 1: the reject-path benchmark and the head-of-phase baseline (PERF-04)** — `d033000` (test)
2. **Task 2: the cheap gate, before any allocation (PERF-01)** — `b296232` (test, RED) → `c3b877e` (feat, GREEN)
3. **Task 3: the last chat output with no report-once guard** — `6b60dc4` (fix)

No refactor commit: the GREEN implementation is nine lines of Lua in `relevant`, one call site in `parse`, one conditional around an existing loop and one early return in the shell. There was nothing to clean up that would not have been cleaning up the thing itself.

## Files Created/Modified

- `inctrack/parser.lua` — `parser.relevant`, the allocation-free superset gate with its colour-marker fall-through and its derivation written out in the comment above it; `parse` calling it before `trim`; the timestamp loop conditional on a leading `[`; the `LBRACKET` constant that keeps the byte comparison from being a magic number.
- `inctrack/inctrack.lua` — the gate called in `text_in` before `strip_colors`; `incursion.parse_told`, the report-once latch on the parse-error line, cleared in `reset()` and in the profile-switch callback.
- `test/run_tests.py` — the reject-path corpus and the two Lua shapes; the recorded baseline constant; the new `cost:` suite; the superset and rejection tables in the adaptability suite plus the `drive()`/`ev()` recorders that hold every invented line the suite already drives to the same implication; the counter, colour and timestamp-loop checks and the report-once checks in the addon suite; the shared `at()` helper with its own cp1252 unit check.
- `test/stubs.py` — `GSUB_COUNTER_CHUNK`, `AshitaHost.count_gsub()` and `AshitaHost.gsub_calls`, documented beside `strip_colors_calls`.

---

## The needle derivation

This table is the superset argument, and it is the only thing standing between PERF-01 and a silently dropped line. One row per **distinct shape** a matcher can accept — one per branch of every alternation and every optional group, not one per matcher. The last column is what makes a row an argument rather than a sample.

Lua patterns have no `|`, so the only alternations in `parser.lua` are the three two-attempt fallback idioms (`objective_boss`, `boss_hint`, the named-NM bonus). The only optional groups are `minutes?` at `:229`, `Minutes?` at `:189`, `:201`, `:214` and `:217`, and the `[^)]*` glyph group at `:269`. All of them are enumerated below.

| # | Matcher (`parser.lua`) | Shape accepted | Literal that shape cannot match without | Needle | Alternations / optional groups the needle survives |
|---|---|---|---|---|---|
| 1 | `:83` begin | `^Incursion %[…%] Begins! %(…%)$` | `Incursion [` at position 1 | `Incursion [` | none in this matcher |
| 2 | `:91` recover | `^Incursion %[…%] Recovering session` | `Incursion [` | `Incursion [` | none |
| 3 | `:99` complete | `^Incursion %[…%] Complete! %(…%) Time: …` | `Incursion [` | `Incursion [` | none |
| 4 | `:111` bonus_done | `^Incursion %[…%] Bonus Objective Complete!` | `Incursion [` | `Incursion [` | none |
| 5 | `:119` bonus_progress | `^Incursion %[…%] Bonus Objective: … N/M$` | `Incursion [` | `Incursion [` | none |
| 6 | `:131` phase | `^Incursion %[…%] Phase #N C/M$` | `Incursion [` | `Incursion [` | none |
| 7 | `:143` objective_kills | `^New Objective: Defeat N enemies %(…%)$` | `New Objective: ` | `New Objective: ` | none |
| 8a | `:166` objective_boss, precise | location is a parenthesised group | `New Objective: ` | `New Objective: ` | **both branches** of the `:166`/`:168` fallback — the needle is the fixed prefix shared by the two patterns |
| 8b | `:168` objective_boss, 1.1.0 fallback | location is anything before `!` | `New Objective: ` | `New Objective: ` | as above |
| 9a | `:178` boss_hint, precise | location is a parenthesised group | `(Boss: ` | `(Boss: ` | **both branches** of the `:178`/`:180` fallback |
| 9b | `:180` boss_hint, 1.1.0 fallback | location is anything before `)` | `(Boss: ` | `(Boss: ` | as above |
| 10a | `:189` chest bonus | `… (Expires in N Minutes)` | `Bonus Objective: ` at position 1 | `Bonus Objective: ` | **both branches** of `Minutes?` — the needle is at the head of the line and the optional `s` is at the tail, so they do not overlap |
| 10b | `:189` chest bonus | `… (Expires in 1 Minute)` | `Bonus Objective: ` | `Bonus Objective: ` | as above |
| 11a | `:199` count bonus | `… Minutes)` | `Bonus Objective: ` | `Bonus Objective: ` | **both branches** of `Minutes?`, same reason |
| 11b | `:199` count bonus | `… Minute)` | `Bonus Objective: ` | `Bonus Objective: ` | as above |
| 12a | `:214` named-NM bonus, precise | parenthesised location, `Minutes` | `Bonus Objective: ` | `Bonus Objective: ` | **all four** combinations of the `:214`/`:217` fallback and `Minutes?` |
| 12b | `:214` named-NM bonus, precise | parenthesised location, `Minute` | `Bonus Objective: ` | `Bonus Objective: ` | as above |
| 12c | `:217` named-NM bonus, fallback | unparenthesised location, `Minutes` | `Bonus Objective: ` | `Bonus Objective: ` | as above |
| 12d | `:217` named-NM bonus, fallback | unparenthesised location, `Minute` | `Bonus Objective: ` | `Bonus Objective: ` | as above |
| **13a** | **`:228` time** | **`You have 90 minutes remaining inside this Incursion.`** | ` remaining inside this Incursion.` | **`remaining inside this Incursion`** | **both branches of `minutes?` — the needle begins *after* the optional plural** |
| **13b** | **`:228` time** | **`You have 1 minute remaining inside this Incursion.`** | ` remaining inside this Incursion.` | **`remaining inside this Incursion`** | **as above; this is the row the plural-free needle exists for** |
| 14 | `:236` points | `^%S+ gains N incursion points%.$` | ` incursion points.` | `incursion points.` | none |
| 15a | `:268` boon | glyph group non-empty | ` gains the effect of ` | `gains the effect of ` | **both branches** of the `[^)]*` glyph group — the needle is before it |
| 15b | `:268` boon | glyph group empty (`()`), the WR-04 allowance | ` gains the effect of ` | `gains the effect of ` | as above |
| 16 | `:285` generic_counter | `^Incursion %[…%] … N/M$` | `Incursion [` | `Incursion [` | none |
| 17 | `:297` generic_done | `^Incursion %[…%] … Complete!$` | `Incursion [` | `Incursion [` | none |
| 18 | `:308` generic_note | `^Incursion %[…%] …$` | `Incursion [` | `Incursion [` | none |
| 19 | `:319` objective_text | `^New Objective: …$` | `New Objective: ` | `New Objective: ` | none |
| 20 | `:327` generic bonus_new | `^Bonus Objective: …$` | `Bonus Objective: ` | `Bonus Objective: ` | none |

Seven distinct needles, then: `Incursion [`, `New Objective: `, `Bonus Objective: `, `(Boss: `, `remaining inside this Incursion`, `incursion points.`, `gains the effect of `.

**Three things this table settles.**

1. **Row 13 is the one that bites.** `parser.lua:229` is `^You have (%d+) minutes? remaining inside this Incursion%.$`. The example line above it says `90 minutes`, and a needle written from that example — `' minutes remaining'` — answers **no** to the one-minute warning. `text_in` would return before `strip_colors`, the line would never reach `parse`, and the instance clock would freeze at the moment the player most needs it, with no error and no symptom. The needle begins after the optional plural for exactly that reason. Both rows name the same needle, and both lines are fixtures in the adaptability suite (`grep -cF "1 minute remaining inside this Incursion" test/run_tests.py` prints 1).
2. **The plan's claim about the Bonus Objective forms was re-checked, not taken on trust, and holds.** Rows 10-12 carry a `Minutes?` too, but their needle is the seventeen-character `Bonus Objective: ` prefix anchored at position 1, and the optional `s` sits at the far end of the line. There is no overlap, so the needle is indifferent to which branch the line takes. Row 13 is the only matcher in the file whose covering needle would otherwise land inside an optional region.
3. **The boon needle is knowingly the loosest of the seven.** A boon carries no `Incursion [`, `New Objective: ` or `(Boss: ` anchor to be recognised by, so the only literal available is the phrase itself — which every ordinary buff line carries as well. Over 127 logs it admits 61,188 lines against 351 real boons, i.e. 84% of everything the gate lets through. Each of those pays one wasted `strip_colors` and is then turned away by the anchored rejection underneath. That is the right side to be wrong on: a false positive costs one colour strip, a false negative costs a line the server sent.

### The empirical check behind the table

The derivation is the argument; this is the corroboration. All 2,951,129 lines from 127 logs were passed through the seven needles in Python, independently of the Lua:

| Question | Answer |
|---|---|
| Lines the shipped parser accepts that the gate would reject | **0** |
| `MUST_PARSE` lines the gate would reject | **0** |
| Lines the gate admits | 72,657 of 2,950,234 (**2.463%**) — so 97.5% of real chat traffic is now free |
| Lines carrying a colour-code marker byte | **0** — Ashita's chatlog writer strips them, which is why the fall-through has no corpus behind it and is guarded by invented fixtures only |

Per-needle admissions: `gains the effect of ` 61,188 · `Incursion [` 8,692 · `New Objective: ` 936 · `Bonus Objective: ` 705 · `remaining inside this Incursion` 576 · `(Boss: ` 469 · `incursion points.` 467.

---

## The colour-marker decision, stated plainly

The gate runs on the **raw** message, before `strip_colors`. Ashita's colour codes are a marker byte (`\30` or `\31`) plus one arbitrary payload byte, and that pair can land *anywhere* — including between two characters of one of the seven needles. An anchored or plain test on raw text would then answer "no" to a line the server really did send.

So the gate answers **yes** unconditionally to any line carrying either marker byte, before it looks at anything else.

- **What it costs:** a coloured line that is not Incursion-related pays one `strip_colors`, exactly as it does today. In practice it now costs *less* than it did — the strip happens, `parse` re-asks the gate on the stripped text, and the trim and timestamp loop are skipped: 5.00 gsubs a line became 2.00. The guarantee promised was "never more"; the measurement is "somewhat less".
- **What it buys:** a false negative becomes **impossible** rather than unlikely. There is no line, coloured or not, that the gate can reject and a matcher would have accepted.

The suite's safety pin for this is a `Begins!` line with a marker byte planted five characters into `Incursion `, checked first to confirm the fixture really does hide all four prefix needles, and then fired through `text_in`: it must still start a run. Negative control 1 below shows that check going red the moment the fall-through is removed.

---

## The benchmark, verbatim from the three closing runs

**Head-of-phase baseline, taken in Task 1 against `a6a3577` with `inctrack/` byte-identical to what Phase 3 shipped.** At that point the two shapes are the same code, and they agree — which is what says the transcribed copy is faithful:

```
  cost: the non-Incursion reject path               1 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 285,562 lines/s, 3.502 us/line
      new shape (shipped):  283,307 lines/s, 3.530 us/line
      new/old: 0.99x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 1.00 strip_colors, 5.33 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 5.00 gsub
```

0.99x, well inside the plan's "within a factor of two" requirement.

**Run 1 — `python test/run_tests.py` (no chatlogs, Lua 5.5):**

```
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 288,284 lines/s, 3.469 us/line
      new shape (shipped):  1,046,338 lines/s, 0.956 us/line
      new/old: 3.63x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold
```

**Run 2 — `python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"` (127 logs, Lua 5.5):**

```
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 268,807 lines/s, 3.720 us/line
      new shape (shipped):  528,092 lines/s, 1.894 us/line
      new/old: 1.96x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold
```

**Run 3 — the same, under `INCTRACK_LUA=luajit21` (the dialect Ashita actually embeds):**

```
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
      old shape (Phase 3): 533,503 lines/s, 1.874 us/line
      new shape (shipped):  2,822,511 lines/s, 0.354 us/line
      new/old: 5.29x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold
```

**The deterministic part, which is what the checks are about, is identical in all three and on both backends:** a colour-free rejected line costs **0.00** `strip_colors` and **0.00** `gsub`, against 1.00 and 5.33 for the shape Phase 3 shipped. The 5.33 is exact: twelve unstamped lines at five gsubs each (two in `strip_colors`, two in `trim`, one in the timestamp loop) plus six stamped lines at six, over eighteen lines.

**Observed ratios, and why the margin is 1.2 and not a bare `>`.** Across the runs recorded here the ratio ranged from **1.96x to 5.29x**, with 3.63x and 3.79x in between. Run 2's 1.96x is the low end and it is instructive: it was measured immediately after a 2.95M-line replay, on a machine still under load, and it is the reason the assertion carries a noise margin instead of comparing two best-of-three figures with `>`. Everything above 1.2 is a pass and nothing about a rate travels between machines.

---

## The three negative controls

Each was applied to a green tree, run, and reverted. Each names what went red and what stayed green — the second column is the point, because a control that reddens everything proves nothing about which check was doing the work.

### 1. The colour-marker fall-through removed

Deleted the four lines of rule 1 from `parser.relevant`, leaving the seven needles.

| | |
|---|---|
| **Went red** | `addon`, 2 of 160: *"a coloured line was judged on its raw bytes instead of being let through, which is how a real line gets dropped for a code sitting inside a needle"* and *"a colour code landing inside one of the gate's needles lost the line that starts a run — silently, with the window simply never appearing"* |
| **Stayed green** | everything else — `state` 105, `adaptability` 119 (the whole superset and rejection tables), `disconnect` 23, `timers` 31, `ui` 65, `cost` 6. The other 158 addon checks. |

That is the whole design in one line: with the fall-through gone, the *only* thing that breaks is a real Incursion line carrying a colour code — which is precisely the failure the rule exists to make impossible, and which no other check in the suite would have caught.

### 2. The shell's early return removed

Deleted the three-line `if not parser.relevant(line) then return; end` from `text_in`, leaving `parse`'s own pre-gate in place.

| | |
|---|---|
| **Went red** | `addon`, 2 of 160 — *"a chat line that is none of the addon's business still paid for a colour strip"* and *"…still ran 4 gsub(s)"*; `cost`, 2 of 6 — the same two claims measured over the corpus (`new: 1.00 strip_colors, 2.00 gsub`) |
| **Stayed green** | `adaptability` 119 in full, the colour cases, the timestamp-loop check, the counter-pin that a relevant line still costs what it must, and the 1.2x ratio — which still read **2.40x**, because `parse`'s own gate goes on saving the trim and the loop |

This is what says those four checks are measuring the **shell** and not the parser. `strip_colors` is `text_in`'s own call; no reordering inside `parser.lua` can decline to make it, and the 2.40x that survives is exactly the part of the win the parser can claim on its own.

### 3. The report-once latch removed

Reverted the parse-error report to the unguarded `if not ok then printf(...) end`.

| | |
|---|---|
| **Went red** | `addon`, 1 of 160: *"a second unreadable line complained again, so a malformed shape arriving on every line would bury the player's chat"*, with both duplicate lines quoted in the message |
| **Stayed green** | the first-report check (`exactly one complaint`), the read-only guarantees on `message` / `message_modified` / `blocked`, the `/incursion reset` and character-change recovery checks, and every other suite |

The first-report check staying green is the counter-pin: the guard cannot become a way of losing the first report, which would be a worse bug than the flood it prevents.

That run also incidentally confirmed hard rule 7 from the other side. The quoted error text is `parser.lua:402: attempt to call a nil value (method 'find')` — the addon suite's `pcall` boundary check now raises inside `parser.relevant`, which is the handler's first real string method call. A type guard there would have turned that into a silent early return, and the check would have gone red for the wrong reason.

---

## The per-suite table

Every row non-decreasing; `parser` and `generic` flat, which is what says the gate reached nothing real. Measured over 127 logs (2,951,129 lines) on both backends, identical counts.

| Suite | Floor (`a6a3577`) | After Task 1 | After Task 2 | After Task 3 | Δ |
|---|---|---|---|---|---|
| `parser: structural lines all parse` | 11819 | 11819 | 11819 | **11819** | flat (exact) |
| `parser: generic tier matches nothing today` | 1 | 1 | 1 | **1** | flat (exact) |
| `parser: tightened patterns keep every line whole` | 1 | 1 | 1 | **1** | flat |
| `state: run reconstruction` | 888 | 888 | 888 | **888** | flat (exact) |
| `state: objectives, bonus, recovery` | 105 | 105 | 105 | **105** | flat |
| `adaptability: unseen content still tracked` | 42 | 43 | 119 | **119** | +77 |
| `disconnect: stale progress is not trusted` | 23 | 23 | 23 | **23** | flat |
| `timers: countdown, linger, staleness` | 31 | 31 | 31 | **31** | flat |
| `persistence: json round trip` | 40 | 40 | 40 | **40** | flat, non-zero |
| `ui: helpers, layout contract, render` | 65 | 65 | 65 | **65** | flat |
| `addon: load, chat, settings, commands` | 143 | 143 | 154 | **160** | +17 |
| `cost: the non-Incursion reject path` | — | 1 | 6 | **6** | new |
| **Total** | 13158 | 13159 | 13251 | **13258** | +100 |

Against the plan's acceptance figures: `adaptability` ≥ 50 → **119**; `addon` ≥ 155 → **160**; `parser` exactly 11819 ✓; `generic` exactly 1 ✓; `replay` exactly 888 ✓; `persistence` 40 and non-zero ✓; `state`/`disconnect`/`timers`/`ui` unmoved at 105/23/31/65 ✓.

Zero known defects, zero `XFAIL` lines, zero `NOW PASSING` lines, exit 0, on all three runs.

## Verification commands and their answers

| Command | Required | Got |
|---|---|---|
| `python test/run_tests.py` | PASS, exit 0, 0 known defects | PASS, exit 0, 0 ✓ |
| `python test/run_tests.py "…\chatlogs"` | PASS, 127 logs, counts above | PASS, 127 logs ✓ |
| `INCTRACK_LUA=luajit21 python test/run_tests.py "…\chatlogs"` | identical verdict and counts | identical ✓ |
| `grep -c "function parser.relevant" inctrack/parser.lua` | 1 | **1** ✓ |
| `grep -c "parser.relevant" inctrack/inctrack.lua` | 1 | **1** ✓ |
| `grep -cF "%([^)]*%)" inctrack/parser.lua` | 1 | **1** ✓ (WR-04's empty-glyph allowance intact) |
| `grep -cF "1 minute remaining inside this Incursion" test/run_tests.py` | ≥ 1 | **1** ✓ |
| `python test/run_tests.py 2>&1 \| grep -ci "lines/s"` | ≥ 2 | **3** ✓ |
| `grep -c "render_off = false" inctrack/inctrack.lua` | plan said 3 | **4** — see deviation 1 |
| `git diff --name-only a6a3577` | exactly the four files | exactly the four ✓ |

## Decisions Made

All the load-bearing ones are in the frontmatter. Three worth spelling out:

- **Both gates stay.** The pre-gate saves the allocation on raw text; the anchored rejection inside `parse` keeps the precision on text that has been trimmed and destamped. Keeping both means the only new risk this change introduces is a pre-gate false negative — which the derivation and the colour fall-through are built to make impossible — rather than a change in what the parser accepts.
- **The colour test is two plain `find`s rather than one `[\30\31]` character class.** A character class would be one pass instead of two, but this is the branch every line pays and this is the safety-critical function in the plan: a plain search is the one shape that visibly cannot allocate or backtrack, and a reader should not have to reason about a pattern to be sure of it. The second scan only happens when the first misses, on a short string.
- **The stamped-line guard is `s:byte(1) == LBRACKET`, with `LBRACKET` resolved once at file scope.** `s:sub(1, 1) == '['` would allocate a one-character string on every line, which is the thing being removed; a bare `91` would be a magic number in the one place it matters.

## Deviations from Plan

### 1. [Rule 1 — plan arithmetic] `grep -c "render_off = false"` prints 4, not the 3 the plan asserts

- **Found during:** Task 3, running the plan's closing verification.
- **Issue:** The plan's acceptance criterion reads *"`grep -c "render_off = false" inctrack/inctrack.lua` prints `3` — 03-01's three clearing sites are all still there and none was repurposed."* The count is **4**, and it was 4 at `a6a3577` before this plan touched anything: the pattern also matches the field's own declaration in the `incursion` table, alongside the three clearing sites. At `a6a3577` those were `inctrack.lua:59` (declaration) and `:114`, `:377`, `:451` (sites); at HEAD they are `:59` and `:123`, `:410`, `:485`. The criterion was arithmetically wrong when written, not broken by this plan.
- **Fix:** The criterion's *intent* — that 03-01's three clearing sites survive — is verified with the unambiguous form instead: `grep -c "incursion.render_off = false" inctrack/inctrack.lua` prints **3**, matching the three sites exactly (`reset()`, the bare `/incursion` re-enable, and the profile-switch callback). No source was changed to satisfy either form; changing code to make a miscounted grep come out at 3 would have been exactly the wrong move.
- **Files modified:** none.
- **Verification:** `grep -c "render_off = false"` → 4 (unchanged from `a6a3577`); `grep -c "incursion.render_off = false"` → 3; `grep -c "incursion.parse_told = false"` → 2, the two clearing sites this plan added.
- **Committed in:** n/a — a verification-method correction, not a code change.

### 2. [Rule 3 — blocking] The plan's Task 1 leaves the ascii() helper's unit check homeless

- **Found during:** Task 1, section F.
- **Issue:** The plan requires the `at()` helper to be "unit-tested… in a suite that runs without chatlogs" but names no suite, while separately fixing Task 1's benchmark suite at exactly one check (the corpus-is-all-rejects pin). There was no obviously-correct home.
- **Fix:** Placed in the adaptability suite, at its head, with a comment stating why it lives there: it is the suite that runs on every machine, and the messages the helper protects only ever print on machines that *have* chatlogs — which are the machines with the cp1252 console and the boon glyph. The check is one line and it moved `adaptability` 42 → 43.
- **Files modified:** `test/run_tests.py`.
- **Verification:** negative control — removing `ascii()` from `at()` turns that single check red (*"a failure message carrying a boon glyph cannot be printed on a cp1252 console…"*) with everything else green; restoring it returns the suite to `ok`.
- **Committed in:** `d033000`.

### 3. [Rule 2 — missing critical] The adaptability suite's own fixtures were not reachable by the superset check

- **Found during:** Task 2, part D.
- **Issue:** The plan requires the gate to be held to "every invented-future-content line the adaptability suite already drives", but those lines are literals inside thirteen `feed(...)` calls and a local `ev(...)` helper, reachable only by copying them into a second list — which would go stale the first time either list changed, silently reducing the coverage the criterion asks for.
- **Fix:** Replaced the suite's `feed(sN, parser, [...])` calls with a local `drive(sN, [...])` and its bare `ev(line)` with a recording one, both appending to a `driven` list that the superset loop then consumes. Mechanical, confined to one function, and it makes a fixture written for some other reason covered for free.
- **Files modified:** `test/run_tests.py`.
- **Verification:** the 13 rewritten call sites and the 119-check adaptability suite are green on both backends; the suite's original 42 checks all still pass unchanged.
- **Committed in:** `b296232` (RED) / `c3b877e` (GREEN).

---

**Total deviations:** 3 (1 plan-arithmetic correction, 1 blocking placement decision, 1 missing-coverage fix)
**Impact on plan:** None on scope. Deviation 1 is a correction to how a criterion is checked, not to what it checks. Deviations 2 and 3 both increase coverage. No requirement was narrowed, no locked decision reopened, and nothing under `docs/`, `README.md`, `CHANGELOG.md`, `inctrack/ui.lua` or `inctrack/state.lua` was touched.

## Issues Encountered

- **The coloured group got *cheaper*, not merely no dearer.** A coloured irrelevant line now costs 2.00 gsubs where it cost 5.00: the gate lets it through, `strip_colors` runs, and then `parse` re-asks the gate on the *stripped* text and returns before `trim`. The plan's guarantee was "never more"; the measurement is "somewhat less". No action — this is the two-gate design working as intended — but it is worth knowing that the second gate is doing real work on coloured traffic, not just standing behind the first.
- **The 1.2x margin earned its keep on the very first 127-log run.** Run 2 measured 1.96x against 3.63x on the same code with no chatlogs, purely because the benchmark ran immediately after a 2.95M-line replay. A bare `>` would have passed, but the run makes the case concretely: the spread between the quietest and busiest measurement of identical code was a factor of 2.7, and the margin is what keeps the one wall-clock assertion in the suite from being the one thing able to flake.
- **The chatlog corpus grew mid-execution** (2,949,424 lines at the first baseline run, 2,951,129 at the last) — the author's client is live. Every per-suite count held exactly through it, which is itself a small piece of evidence that the counts are pinned to structure rather than to volume.

## Carry-forwards, restated

Untouched by this plan and still owed:

- **04-02 (PERF-02, PERF-03):** the deferred settings write off the chat thread; the per-frame options table allocated sixty times a second in the frame handler; the bounded memo cache.
- **04-03 (DOC-01, DOC-02):** the `docs/design.md` correction, the stale `ui.lua:15-26` layout comment, `addon.version = '1.2.0'`, the changelog, and the README's non-existent close button and title bar.
- **v2 (PROC-01..04):** CI, luacheck, a versioned release artifact, a public chatlog fixture.
- **IN-05** (NaN/±inf in `opt_number`) stays deferred and wants **re-deciding** rather than applying as written.
- **Three in-game human checks** remain open — Phase 2's reload clock and window frame, Phase 3's D8 `imgui.End` metatable lookup — and this plan adds a fourth (D8 in the coverage block above): the colour-code fall-through has no corpus behind it, because Ashita's chatlog writer strips colour codes and all 2.95M recorded lines are colour-free. Every coloured fixture in the suite is invented. Only a live session sends a real code, so a single Incursion run with the addon loaded would close it.

## Next Phase Readiness

- **PERF-01 and PERF-04 are done and measured.** The hot path is 3.5-5x on the reject case with the deterministic counters at zero, and the number prints in the report every run rather than living in this document.
- **04-02 is unblocked and independent.** It touches `inctrack.lua`'s frame handler and persistence, not the chat handler or `parser.lua`, so it does not intersect this plan's diff.
- **The benchmark is a fixture 04-02 can reuse.** `bench_host()`, `count_gsub()` and the counting/timing split are general; a per-frame allocation figure would be the same shape.
- **The deployed build at `…\Ashita\addons\inctrack\` is now behind the repo** by two files (`parser.lua`, `inctrack.lua`). It was byte-identical entering this phase; the milestone-close copy should account for that.

## Self-Check: PASSED

- All five claimed files exist on disk.
- All four claimed commits exist in `git log`: `d033000`, `b296232`, `c3b877e`, `6b60dc4`.
- Every `parser.lua` line reference in the needle derivation table was re-read from the file and resolves to the construct named.
- Both sets of `render_off = false` line numbers in deviation 1 were read from `a6a3577` and from HEAD respectively.
- Every benchmark block quoted above was copied from the run output verbatim, not retyped.

## Known Stubs

None. No hardcoded empty value, placeholder string, `TODO` or `FIXME` was introduced by this plan, and no component was left without its data source. `parser.relevant` is the whole of what PERF-01 asked for; the benchmark measures the shipped handler rather than a stand-in.

---
*Phase: 04-cost-and-record*
*Completed: 2026-08-29*

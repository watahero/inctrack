---
phase: 03-fragile-paths
plan: 02
subsystem: testing
tags: [lua, lua-patterns, parser, corpus-evidence, over-reach, regression-guard]

requires:
  - phase: 01-the-net
    provides: the lupa harness, the 127-log corpus replay, and suites 1 and 2 --
      the structural parse count and the dormant generic tier, which are the
      only instruments that can see an over-reaching pattern
  - phase: 02-the-three-defects
    provides: the zero-known-defects floor and the seven-backend green, so a
      count that moves in this plan is attributable to this plan
  - phase: 03-fragile-paths
    plan: 01
    provides: the addon suite at 112 checks, which this plan's floor inherits
provides:
  - a boss objective, a boss hint and a named-NM bonus that anchor their split
    on the last ' at ' preceding the coordinate group, each with the shipped
    1.1.0 shape kept as a fallback
  - a mob list split on comma-space by plain-text scan, with no fallback
  - a boon tail requiring a non-empty glyph group and a non-blank name, with no
    fallback
  - a recorded corpus survey over 127 logs whose eight invariants are all zero
  - twenty-one new adaptability checks covering all three tightenings, both what
    they must get right and what they must now decline
  - a third parser Result that re-derives every boss split, every mob list and
    every gains-the-effect line from the raw text in Python across 127 logs
affects: [03-03, phase-04-performance, phase-04-docs]

actuals:
  tokens: 5561        # chars/4 over the realized diff (22,243 chars)
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A narrowing ships only on recorded corpus evidence: the survey runs
       first, its invariants must be zero, and its output goes in the record"
    - "Precise-form-first with the shipped form as a fallback, where the shape
       admits it -- over-reach then becomes structurally impossible rather than
       merely unlikely"
    - "A guard that re-derives the answer from the raw input in Python, so the
       parser and the harness cannot drift the same way and both be wrong"

key-files:
  created: []
  modified:
    - inctrack/parser.lua
    - test/run_tests.py

key-decisions:
  - "The location is the anchor, not the name: a parenthesised trailing group is structurally identifiable and the name is whatever precedes it -- the only way to be right about a name the addon has never seen without holding a list of names"
  - "HARD-02 keeps the 1.1.0 shape as a fallback at all three call sites; HARD-03 and HARD-04 keep none, and rest on the survey plus the exact-11819 and exact-1 pins"
  - "split_mobs drops a piece that is empty once trimmed, which the 1.1.0 form did not -- it kept a whitespace-only run as a blank row"
  - "The boon's player name is deliberately not required to match, so a name the addon has not learned yet still produces a boon"
  - "The new guard's failure messages go through ascii(), because a boon line carries the glyph's raw high bytes and a report that dies encoding its own failure text is a traceback where a red line was owed"
  - "The cheap-rejection guard's broad boon clause was left alone on purpose: narrowing it is PERF-01, Phase 4, and doing it here would confound this plan's corpus comparison"

patterns-established:
  - "Survey before tightening: eight invariants, all required zero, with a
     non-zero one halting the plan for re-argument rather than being worked
     around"
  - "Independent recomputation as a guard: the reference is derived from the
     raw text, never from the code under test, and is written out in full
     rather than shared, so the two cannot be edited into agreement"
  - "Negative controls in both directions: remove the insurance and watch the
     corpus stay green; remove the mechanism and watch the synthetic checks
     fail"

requirements-completed: [HARD-02, HARD-03, HARD-04]

coverage:
  - id: D1
    description: "A boss objective naming a mob whose own name contains ' at '
      parses with the full name intact and the parenthesised coordinate group
      separate, because the split is anchored on the last ' at (' and not the
      first ' at '"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: a boss whose own name contains ' at ' was shown truncated"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: part of the boss's name was folded into its coordinates"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: the boss waiting at the end of the phase was named wrong (boss hint)"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: the bonus NM was shown under a truncated name (named-NM bonus)"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#parser: tightened patterns keep every line whole -- 1050 splits over 127 logs, families 1 and 2"
        status: pass
    human_judgment: false
  - id: D2
    description: "The 1.1.0 shape still answers at all three sites, so a boss
      objective whose trailing text is not parenthesised parses exactly as it
      does today"
    requirement: HARD-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: a boss objective with no coordinates vanished from the window entirely"
        status: pass
      - kind: unit
        ref: "negative control A: fallback removed -> corpus stays at 11819/1, exactly these 2 checks fail"
        status: pass
      - kind: unit
        ref: "negative control B: precise form removed -> exactly the 2 truncation checks fail"
        status: pass
    human_judgment: false
  - id: D3
    description: "A mob list containing a comma-bearing name yields one mob, not
      two phantom entries: the list separator is comma-space"
    requirement: HARD-03
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: a mob whose name contains a comma was split into two mobs that do not exist"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: the mob list picked up an empty or untrimmed entry"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#parser: tightened patterns keep every line whole -- 469 mob lists re-derived, family 3"
        status: pass
      - kind: unit
        ref: "negative control C: bare-comma split restored -> 3 adaptability checks fail; family 3 does NOT bite (recorded limit)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A line without the (glyph): stats tail produces no boon event,
      and neither does one whose glyph group is empty or whose name is blank"
    requirement: HARD-04
    verification:
      - kind: unit
        ref: "test/run_tests.py#adaptability: a line with an empty glyph group was listed as a boon"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: a boon with no name was listed, so the window would draw a blank row"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#adaptability: an ordinary buff was listed among the boons picked this run"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#parser: tightened patterns keep every line whole -- 351 boon tails, family 4, both directions"
        status: pass
      - kind: unit
        ref: "negative control F: glyph group over-tightened to one character -> family 4 fails 351 times"
        status: pass
    human_judgment: false
  - id: D5
    description: "Nothing the server has actually sent stopped parsing: the
      structural parse count over 127 logs did not fall and the generic tier
      still matches nothing"
    requirement: HARD-02
    verification:
      - kind: integration
        ref: "test/run_tests.py#parser: structural lines all parse -- exactly 11819, both backends"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#parser: generic tier matches nothing today -- exactly 1, both backends"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every tightening was accepted on recorded corpus evidence, not
      on inspection -- the survey figures are in this SUMMARY and its eight
      invariants are all zero"
    requirement: HARD-03
    verification:
      - kind: other
        ref: "the survey output below, reproduced verbatim; 8/8 invariants zero"
        status: pass
    human_judgment: false

status: complete
---

> **SUPERSEDED BY THE PHASE-3 CODE REVIEW (finding WR-04).** This summary was
> written before review. The shipped boon tail is `%([^)]*%)` — the glyph group
> may be **empty**. The non-empty rule was removed because it narrowed only
> against the server: the tail plus a non-blank name already discriminates
> ordinary buffs, and with no fallback tier a `(): ` glyph group would have
> silently and permanently dropped a boon. The `)`-exclusion was kept. The
> adaptability check named below now asserts the opposite of what its name
> suggests. See `03-REVIEW.md`.



# Phase 3 Plan 02: The Parser Tightenings (HARD-02/03/04) Summary

Three parser patterns narrowed so the window cannot show something the server
never said — the boss split anchored on the last ` at ` before the coordinate
group, the mob list split on comma-space, the boon tail required to carry a
non-empty glyph and a non-blank name — each accepted only after a survey of all
127 logs returned zero on every invariant, and all of it pinned by a structural
parse count that stayed at exactly 11819 and a generic tier that stayed silent.

## What was built

The defining hazard of this plan was over-reach: a pattern tightened past what
the server actually sends drops a real line silently, which is strictly worse
than leaving the code alone. Nothing here was accepted on inspection.

**The survey ran first, before `parser.lua` was touched.** All eight invariants
printed zero and every figure reproduced the plan-time record exactly. Only then
were the patterns changed.

**HARD-02 is additive.** At each of the three ` at ` sites the precise form is
tried first — the name captured greedily, the location required to be a
parenthesised group, which puts the split on the *last* ` at ` — and if it
declines, the shape shipped in 1.1.0 answers unchanged. Over-reach at those
sites is therefore structurally impossible rather than merely unlikely.

**HARD-03 and HARD-04 replace their forms outright and keep no fallback.** Their
guard is the survey plus the two pins. Both held.

**A third parser Result** now re-derives every boss split, every mob list and
every gains-the-effect line from the raw text in Python across 127 logs. It
catches the half of the failure mode that suite 1 cannot see: a line that still
parses but comes back mangled.

## The survey (Task 1) — verbatim

Read-only, from a throwaway script in the session scratchpad; nothing entered
the repository (`git status --porcelain` clean of it throughout). The logs were
read exactly as the harness reads them: utf-8 with `errors="replace"`, timestamp
prefixes stripped, whitespace trimmed.

```
survey of 127 logs, 2945126 chat lines
  dir: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs

Q1. trailing locations (greedy name capture -> split on the LAST ' at ')
  boss-objective + boss-hint lines ........................ 936
  of those, trailing location not parenthesised ........... 0  [INVARIANT]
  named-NM bonus lines .................................... 114
  of those, trailing location not parenthesised ........... 0  [INVARIANT]

Q2. names carrying the substring
  bodies holding more than one ' at ' ..................... 0  (report only)

Q3. list separators
  kill-objective lines ................................... 469
  of those, bare-comma split differs from comma-space ..... 0  [INVARIANT]
  of those, body holds a comma not followed by a space .... 0  [INVARIANT]

Q4. the boon tail
  lines BEGINNING with '<name> gains the effect of' ....... 44856
  of those, matching the full tail the matcher requires ... 351
  of those, empty glyph group ............................. 0  [INVARIANT]
  of those, blank name once trimmed ....................... 0  [INVARIANT]
  of those, blank stats once trimmed ...................... 0  [INVARIANT]

Q5. what a glyph is
  distinct glyph groups .................................. 3
         135  '\ufffd\ufffd'   (6 bytes as utf-8)
         110  '\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd'   (18 bytes as utf-8)
         106  '\ufffd\ufffd\ufffd\ufffd'   (12 bytes as utf-8)
  distinct boon names .................................... 28
  boon names holding a space then an opening parenthesis .. 0  [INVARIANT]

INVARIANTS (8)
  Q1 boss/hint location not parenthesised        0  OK
  Q1 named-NM location not parenthesised         0  OK
  Q3 bare-comma split differs                    0  OK
  Q3 comma not followed by a space               0  OK
  Q4 empty glyph group                           0  OK
  Q4 blank name                                  0  OK
  Q4 blank stats                                 0  OK
  Q5 boon name holds ' ('                        0  OK

VERDICT: all invariants zero
```

**Against the plan-time record, every figure reproduced exactly:** 936/0,
114/0, 469/0/0, 44856/351/0/0/0, three glyph groups at 135/110/106, 28 distinct
boon names, 0 with a space-then-parenthesis. The glyph groups render as
replacement characters because the harness reads with `errors="replace"`; the
underlying bytes are the raw high-byte runs a real log carries, of 2, 6 and 4
codepoints after replacement.

Question 4's anchored wording mattered. `^\S+ gains the effect of ` gives 44856.
The unanchored substring count over the same corpus is much larger, and reading
that figure instead would make the 351 look wrong by roughly a third.

**Q2 is zero, and that is the honest position on HARD-02:** no mob name in 127
logs contains ` at `. The tightening is prophylactic. It is worth having anyway
because the coordinate group makes the split derivable without any content
knowledge, and the alternative — a list of names — is forbidden outright.

## Run reports

Three runs, and a fourth (`luajit21` without the corpus) for completeness.

### 1. `python test/run_tests.py` — no chatlogs

```
  lua: Lua 5.5
  chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)

  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                      0 checks  ok
      skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

### 2. `python test/run_tests.py "<chatlogs>"` — 127 logs

```
  lua: Lua 5.5
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945220 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                     31 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

Eleven suite lines with a corpus present, as required. The guard's tallies
reconcile with the survey exactly: 1050 = 936 + 114, all 1050 parenthesised;
469 mob lists; 351 boon tails.

### 3. `INCTRACK_LUA=luajit21 python test/run_tests.py "<chatlogs>"`

```
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945220 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
  parser: generic tier matches nothing today        1 checks  ok
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               53 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             25 checks  ok
  persistence: json round trip                     31 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           112 checks  ok

  0 known defects

PASS
```

Identical verdict, identical per-suite counts. This mattered more than usual
here: Lua patterns are byte-based and the glyph group carries raw high bytes, so
a dialect difference in `[^)]+` over those bytes would have shown up as a corpus
count divergence. It did not.

`INCTRACK_LUA=luajit21 python test/run_tests.py` without the corpus is likewise
`PASS`, `0 known defects`, with the same per-suite counts as run 1.

### Per-suite table, against the Phase-2 floor as amended by plan 03-01

| Suite | Floor | After 03-02 | Requirement | Verdict |
|---|---|---|---|---|
| `parser: structural lines all parse` | 11819 | **11819** | exactly | met |
| `parser: generic tier matches nothing today` | 1 | **1** | exactly | met |
| `parser: tightened patterns keep every line whole` | — | 1 | new | added |
| `state: run reconstruction` | 888 | 888 | exactly | met |
| `state: objectives, bonus, recovery` | 53 | 53 | exactly | met |
| `adaptability: unseen content still tracked` | 20 | 41 | ≥ 34 | met |
| `disconnect: stale progress is not trusted` | 23 | 23 | exactly | met |
| `timers: countdown, linger, staleness` | 25 | 25 | exactly | met |
| `persistence: json round trip` | 31 | 31 | at or above | met |
| `ui: helpers, layout contract, render` | 65 | 65 | exactly | met |
| `addon: load, chat, settings, commands` | 112 | 112 | at or above | met |

Total over 127 logs: **13,059** checks, up from 13,037. `parser` and `generic`
are exact matches, not "at or above" — the whole point of them is that they do
not move. No suite fell. Zero `XFAIL`, zero `NOW PASSING`, zero `FAILED`;
`grep -c` over a corpus run for those three markers prints `0`.

## Negative controls

Four were run. The plan required two; the two extra exist because the required
family-3 control did not bite and the plan asks for that to be recorded together
with which family does.

### A — HARD-02's fallback removed (boss objective)

The fallback branch deleted, the precise form left alone.

- Corpus: `parser: structural lines all parse` **11819**, `generic` **1** — unmoved.
- Synthetic: `adaptability` FAILED (2):
  - `a boss objective with no coordinates vanished from the window entirely: 'objective_text'`
  - `a boss objective with no coordinates lost its location: None`

**Reading:** the fallback does no work on any line the server has actually sent
— every one of the 936 + 114 real lines carries a parenthesised location, so the
precise form claims them all. It is insurance against wording the server does
not send today, and without it such a line would drop out of the specific tier
into the generic `objective_text` catch-all. Insurance, not the mechanism.

### B — HARD-02's precise form removed (boss objective)

Only the shipped 1.1.0 shape left.

- `adaptability` FAILED (2):
  - `a boss whose own name contains ' at ' was shown truncated: 'Warden'`
  - `part of the boss's name was folded into its coordinates: 'the Ninth Gate at (K-7) (Map #4)'`

**Reading:** the precise form is the thing doing the work. A and B together
establish that the fallback insures and the precise form acts — neither is
carrying the other.

### C — HARD-03's split reverted to the bare-comma form (the required control)

- Corpus: 11819 / 1 unmoved. **`parser: tightened patterns keep every line
  whole` stayed at 1 check, `ok`. Family 3 did NOT bite.**
- Synthetic: `adaptability` FAILED (3), including
  `a mob whose name contains a comma was split into two mobs that do not exist:
  ['Kalamainu', 'Prime', 'Cave Bat']`.

**Recorded as a limit of the guard.** This is exactly what the survey predicted:
all 469 real kill-objective lines split identically under either rule, so no
corpus line can distinguish them. Family 3 is therefore *unfalsified* by this
corpus rather than *proven* by it — it guards against a future regression on a
future line, and the only thing that catches the HARD-03 revert today is the
synthetic adaptability block. A future corpus containing a comma-bearing name
would change that.

### D, E, F — which families do bite under a deliberate revert

- **D, boon name capture made greedy** (`(.-)` → `(.*)`): no bite. Every one of
  the 351 real boon lines carries exactly one `(…): ` tail, so lazy and greedy
  agree. Another recorded limit.
- **E, the opening parenthesis left outside the location capture**
  (`at (%(.+%))!$` → `at %((.+%))!$`) — a realistic mis-edit: **family 1 fired
  467 times** while `parser: structural lines all parse` stayed at **11819**.
  This is the guard earning its place: the lines still parsed, coverage saw
  nothing, and the window would have drawn coordinates missing their opening
  parenthesis. Sample: `'Yagudo Scout' + 'J-9) (Map #1)' vs 'Yagudo Scout at
  (J-9) (Map #1)'`.
- **F, glyph group over-tightened to a single character** (`[^)]+` → `[^)]`) —
  the deliberate over-reach this plan exists to prevent: **family 4 fired 351
  times** (`the window would miss a boon here`), and coverage fired 351 times
  alongside it. Both instruments saw it.

**Summary of which families are live on this corpus:** families 1, 2 and 4 all
have non-zero tallies (1050, 1050, 351) and families 1 and 4 have been watched
to bite. Family 2's tally is non-zero (1050 lines carry ` at (`) but it cannot
be made to bite on this corpus, because Q2 is zero — no real name contains
` at `, so first-occurrence and last-occurrence anchoring cannot disagree.
Family 3's tally is non-zero (469) but likewise cannot bite, per control C.
Families 2 and 3 are guards against future lines; families 1 and 4 are guards
that have been demonstrated on today's.

## The patterns now in the file

### HARD-02 — precise form first, 1.1.0 form as the fallback (three sites)

| Site | Precise form (tried first) | Fallback (shipped 1.1.0, unchanged) |
|---|---|---|
| boss objective | `^New Objective: Defeat (.*) at (%(.+%))!$` | `^New Objective: Defeat (.-) at (.+)!$` |
| boss hint | `^%(Boss: (.*) at (%(.+%))%)$` | `^%(Boss: (.-) at (.+)%)$` |
| named-NM bonus | `^Bonus Objective: Defeat (.*) at (%(.+%))! %(Expires in (%d+) Minutes?%)$` | `^Bonus Objective: Defeat (.-) at (.+)! %(Expires in (%d+) Minutes?%)$` |

Greedy `(.*)` is the whole mechanism: it makes the split fall on the last ` at `
that is followed by an opening parenthesis. The location capture requires both
the opening and the closing parenthesis. The event fields keep their present
names and trimming, and the precise forms live *inside* the existing matcher
functions — no entry was added to the `specific` table, so the ordering contract
at `parser.lua:72-80` cannot have moved. The two contract pairs most at risk are
asserted directly: a count-form bonus is still a count and not a named NM, and a
kill objective is still a kill objective and not a boss.

### HARD-03 — one replacing form, no fallback

```lua
local i, j = s:find(', ', start, true);
```

A plain-text scan for comma-space, walking the string and slicing between hits,
each piece trimmed, a piece empty after trimming dropped. `gmatch` is gone from
the file entirely (`grep -cF gmatch` prints `0`, down from `1`), and so is
`[^,]+`. **There is nothing underneath this.** What stands between it and a
silent loss is the survey — 469 kill-objective lines, zero split differences,
zero commas not followed by a space — together with the exact-11819 and exact-1
pins.

One behaviour did change beyond the separator: the 1.1.0 form dropped only
zero-length runs, so a whitespace-only entry survived as `''` and the window
would have drawn a blank name. The new form drops it. This is a narrowing on
what can enter the mob list, it cannot drop a real mob (only one whose entire
name is whitespace), and the corpus guard recomputes the same rule independently.

### HARD-04 — one replacing form, no fallback

```lua
s:match('^(%S+) gains the effect of (.-) %([^)]+%): (.+)$')
```

plus, in the body, `name = trim(name)` and a `name ~= ''` test before the event
is returned. Two changes and no more. The glyph group is a non-empty run up to
the closing parenthesis — the minimum tightening that cannot over-reach, since
it accepts exactly what the old lazy group accepted minus the empty case, and
the survey shows the corpus has no empty case. The player name is deliberately
*not* required to match, so a name the addon has not learned yet still produces
a boon. **There is nothing underneath this either**, and the same three
instruments are its guard.

`grep -c "at (%(" ` prints `3`; `grep -cF "', ', start, true"` prints `1`;
`grep -cF "gmatch"` prints `0`; `grep -cF "[^)]+"` prints `1`. All four
acceptance greps hold.

## Files changed

`git diff --name-only b896444 HEAD` lists exactly two files:

- `inctrack/parser.lua` — the three tightenings and their comments (+67 lines net)
- `test/run_tests.py` — 21 new adaptability checks, the third parser Result and
  its reference patterns (+289 lines net)

`MUST_PARSE` is **byte-identical** to its pre-plan state, proven by diffing the
extracted block against `b896444` rather than asserted: no hunk touches those
lines. The cheap-rejection guard, the ordering contract, the coverage Result and
the dormant Result are all unchanged. `inctrack/ui.lua`, `inctrack/state.lua`
and `inctrack/inctrack.lua` were not touched. `parser.lua` remains one pure
function over one string with no Ashita dependency and no state.

## Commits

| Commit | What |
|---|---|
| `89b141a` | `test(03-02)`: the 21 failing checks — 11 red against the shipped patterns |
| `c8fc6ed` | `feat(03-02)`: the three tightenings |
| `2f8206c` | `test(03-02)`: the corpus-wide over-reach guard |

## TDD gate compliance

Task 2 ran the full cycle. RED (`89b141a`) recorded 11 failures against the
shipped patterns — 6 HARD-02 truncations, 3 HARD-03 splits, 2 HARD-04
acceptances — with the other 10 new checks green, which is what proves the block
is not merely asserting current behaviour. GREEN (`c8fc6ed`) turned all 21 green
with no other suite moving. No REFACTOR commit was needed.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — missing robustness] The new guard's failure messages could kill
the run's own report**

- **Found during:** Task 3, negative control F
- **Issue:** the guard's failure messages echoed raw corpus text through `%r`.
  A boon line's glyph bytes become `U+FFFD` under `errors="replace"`, which is
  printable, so `repr()` keeps it — and a default Windows cp1252 console then
  raises `UnicodeEncodeError` inside `Result.report()`. Under control F the run
  produced a traceback where a readable red line was owed, which is precisely
  the outcome `run_suite`'s own docstring exists to prevent.
- **Fix:** all six of the new Result's failure messages go through `ascii()`,
  the same discipline the survey script used for the same reason. Confirmed by
  re-running control F: 351 readable failure lines, no traceback.
- **Scope:** only the lines this plan added. The pre-existing `coverage` message
  (`"unparsed %s:%d %r"`) has the same exposure on a failing boon line and was
  deliberately left alone — the plan says to change nothing else in
  `test_parser`. Carried forward below.
- **Files modified:** `test/run_tests.py`
- **Commit:** `2f8206c`

**2. [Rule 1 — bug] Two tuple-formatting errors in the new checks**

- **Found during:** Task 2, first RED run
- **Issue:** `"%r" % (e and (a, b))` unpacks the tuple against a single format
  spec and raises `TypeError`, which `run_suite` correctly turned into a red
  suite ("adaptability: the suite did not finish") rather than a crash.
- **Fix:** wrapped as a one-tuple in both places.
- **Files modified:** `test/run_tests.py`
- **Commit:** `89b141a`

No architectural decisions arose and no authentication gates were hit.

## Carry-forwards — recorded, not acted on

- **PERF-01, Phase 4 — the cheap-rejection guard's broad boon clause.**
  `parser.lua`'s `s:find('): ', 1, true)` clause still lets every line
  containing `): ` through to the full matcher list. Narrowing it was tempting
  while editing the boon matcher and is explicitly out of scope: doing it here
  would have confounded this plan's corpus comparison. Untouched.
- **PERF-01, Phase 4 — the per-line allocations ahead of it.** `parse()` still
  trims and runs the timestamp `gsub` loop on every chat line before the
  rejection test. Unchanged by this plan.
- **The harness's duplicated wording knowledge.** `MUST_PARSE`, `BEGIN`,
  `COMPLETE`, `POINTS`, `PHASE` and now `BOSS_OBJ_BODY`, `BOSS_HINT_BODY`,
  `NM_BONUS_BODY`, `KILLS_BODY` and `BOON_REF` each restate the server's wording
  in Python. That duplication is deliberate — a reference derived from the
  parser would drift with the parser and agree with it while both were wrong —
  but it is now ten patterns, and a server wording change means editing the Lua
  and the Python in step. Worth a note in Phase 4's documentation pass.
- **`Result.report()` can die encoding a failure message.** The new Result is
  safe; the older `coverage` message is not, and would raise on a cp1252 console
  if a boon line ever failed to parse. Out of scope here (hard rule: change
  nothing else in `test_parser`). A one-line `ascii()` fix whenever that file is
  next open.
- **Family 2 and family 3 of the corpus guard are unfalsifiable on today's
  corpus.** Recorded above under negative controls. They guard future lines, not
  present ones, and should not be read as evidence that the anchoring or the
  separator rule has been exercised against real data.
- **Q2 is zero.** No mob name in 127 logs contains ` at `. HARD-02 remains
  prophylactic, and the honest statement of its value is that it removes a
  content dependency, not that it fixed an observed fault.

## Self-Check: PASSED

- `inctrack/parser.lua` — FOUND
- `test/run_tests.py` — FOUND
- `.planning/phases/03-fragile-paths/03-02-SUMMARY.md` — FOUND
- commit `89b141a` — FOUND
- commit `c8fc6ed` — FOUND
- commit `2f8206c` — FOUND

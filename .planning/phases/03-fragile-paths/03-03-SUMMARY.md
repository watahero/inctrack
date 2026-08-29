---
phase: 03-fragile-paths
plan: 03
subsystem: database
tags: [lua, persistence, json, schema-validation, structural-validation, defensive-copy, timers]

requires:
  - phase: 01-the-net
    provides: the lupa harness, the stubbed Ashita host with its own json, and
      the persistence suite's round trip through Ashita's real json.lua --
      without the last of these the validator's acceptance of real serialised
      output would be unproven
  - phase: 02-the-three-defects
    provides: schema version 2, the version-1 migration path, and the
      wall-clock ageing inside restore() -- which is the arithmetic that made a
      wrong-typed field a raise rather than only a wrong number, recorded as
      review finding IN-01
  - phase: 03-fragile-paths
    plan: 01
    provides: the render-path containment (HARD-01) and the addon suite at 112
      checks, which this plan's floor inherits
  - phase: 03-fragile-paths
    plan: 02
    provides: the adaptability suite at 41 and the third parser Result, which
      this plan's floor inherits
provides:
  - a file-local structural validator over the decoded session, run after the
    version gate and before any field is read for its value
  - rejection rather than coercion on every field, including a numeric string
  - whole-blob rejection rather than half-application: the boon loop stops
    skipping malformed members
  - the objective and the boss preview rebuilt field by field from validated
    values instead of adopted by reference (review finding IN-01)
  - State:reset() clearing the held timer sync, so a /incursion reset between
    the server's remaining-minutes line and 'Begins!' cannot seed the next
    run's clock
  - 32 state checks, 4 persistence checks, 6 timers checks and 7 addon checks
    pinning all of it
affects: [phase-04-performance, phase-04-docs]

actuals:
  tokens: 7728        # chars/4 over the realized diff (30,910 chars)
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A validator over an untrusted decoded blob rejects, never coerces: a
       coerced field is a number the server never sent, displayed with the
       same confidence as one it did"
    - "Discard whole, never half-apply: a malformed member of a list fails the
       entire session rather than being skipped into a run that is quietly
       short of what the player had"
    - "The validator runs after the version gate and before the migration, so
       schema evolution and shape checking stay separate questions"
    - "Every rejection case is a real serialise() output with exactly one
       field broken, so a rejection can never be attributed to the wrong cause"
    - "Every rejection case asserts three things together -- falsy return, no
       run left behind, nothing raised -- because a raise escapes into an
       Ashita event handler that has no protected call around it"

key-files:
  created: []
  modified:
    - inctrack/state.lua
    - test/run_tests.py

key-decisions:
  - "The validator is a set of small named predicates (opt_number, opt_string, opt_boolean, full_string, array_of, map_of) so the body reads as a table of rules rather than a wall of conditionals"
  - "array_key tests k >= 1 and k % 1 == 0 rather than any integer subtype, because a JSON-decoded number is a float and a tonumber-derived one may be an integer -- the luajit21 run is what proves that choice"
  - "objective.kind is checked for being a string and never against a list of kinds: a shape check is allowed, a content check is not"
  - "Both list-shaped fields are walked by key as well as by value, so a stray key or a hole cannot smuggle a value past a length-based loop"
  - "next_boss.name and every mob-list entry must be a non-empty string; a blank name is a row the window would draw empty"
  - "reset() clears pending_time; the thirty-second staleness guard at begin is untouched, because it answers a different question"
  - "The right_text finding is accepted as intended behaviour, recorded here, and is not handed to Phase 4 and not counted as a seventh fragility"

patterns-established:
  - "Reject-not-coerce as an explicit, tested position: the points-as-'84'
     case exists precisely because Lua would have coerced it silently"
  - "One-field-broken fixtures: a helper rebuilds a known-good blob from a
     fresh state on every call, because serialise() hands out the live run's
     own sub-tables and a mutated fixture would poison every case after it"
  - "A control at the top of a rejection block: a validator that rejected
     everything would pass every rejection case and cost the player their run"
  - "Two layers, both kept: 03-01 keeps the frame up when wrong data reaches
     the render path; 03-03 stops the wrong data reaching the run record"

requirements-completed: [HARD-05, HARD-06]

coverage:
  - id: D1
    description: "A structurally malformed saved session is discarded whole:
      restore() returns falsy, leaves no run behind, and never reaches
      arithmetic on a field of the wrong type"
    requirement: HARD-05
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: 27 one-field-broken rejection cases, each asserting falsy return + no run left behind + no raise"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#persistence: a hand-edited session whose objective count is a string was not discarded whole"
        status: pass
      - kind: unit
        ref: "negative control: validator call disabled -> state 28, persistence 2, addon 5 fail; 8 state cases and the addon load path fail by raising"
        status: pass
    human_judgment: false
  - id: D2
    description: "A well-formed session still restores exactly as it does
      today, including the version-1 migration path Phase 2 added"
    requirement: HARD-05
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: a session the addon had just written itself was refused (the control at the head of the block)"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#persistence: restore rejected a round-tripped snapshot -- the full 35-check round trip through Ashita's own json.lua"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#persistence: a session written by 1.1.0 was rejected outright, losing an in-progress run on upgrade"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#persistence: a run the player had only just entered -- no objective, no boss, no bonus, no boons -- was thrown away on reload"
        status: pass
    human_judgment: false
  - id: D3
    description: "restore() cannot raise on any shape of well-formed JSON --
      the validator runs before the first arithmetic, so a hand-edited
      settings file cannot throw inside an Ashita event handler"
    requirement: HARD-05
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: a saved session of the wrong shape took the addon's load handler down with it"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: the four cases whose fields restore() itself does arithmetic on -- time_left, elapsed, saved_at, bonus.remaining"
        status: pass
    human_judgment: false
  - id: D4
    description: "A malformed member of a list is rejected whole, not skipped,
      and a rejection leaves a run already in progress untouched"
    requirement: HARD-05
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: a saved session whose second boon carries no name ... was not discarded"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: a rejected session took the run the player was standing in with it"
        status: pass
      - kind: integration
        ref: "test/run_tests.py#persistence: a session holding a boon with no name was half-applied"
        status: pass
    human_judgment: false
  - id: D5
    description: "The objective and the boss preview are copies of validated
      values, not references into a decoded blob"
    requirement: HARD-05
    verification:
      - kind: unit
        ref: "test/run_tests.py#state: the restored objective is the decoded blob's own table"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: the restored mob list is the decoded blob's own table"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#state: the restored boss preview is the decoded blob's own table"
        status: pass
      - kind: other
        ref: "grep -cF 'run.objective      = data.objective' inctrack/state.lua || true -> 0"
        status: pass
    human_judgment: false
  - id: D6
    description: "/incursion reset within thirty seconds of a remaining-minutes
      line does not seed the next run's clock: pending_time is nil after
      reset(), and a run begun without a reset still adopts the sync"
    requirement: HARD-06
    verification:
      - kind: unit
        ref: "test/run_tests.py#timers: a reset left the last remaining-minutes line held"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#timers: a run begun straight after a reset came up showing a clock left over from the run the player had just cleared"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#timers: the entry sync stopped seeding a new run's clock (the counter-pin)"
        status: pass
      - kind: unit
        ref: "test/run_tests.py#addon: /incursion reset then a new run: the window came up already counting down from the cleared run's clock"
        status: pass
      - kind: other
        ref: "grep -c 'self.pending_time = nil' inctrack/state.lua -> 2"
        status: pass
    human_judgment: false
  - id: D7
    description: "The whole phase is green together: all six HARD requirements,
      no pre-existing suite's count fallen, on both backends against 127 logs"
    verification:
      - kind: integration
        ref: "python test/run_tests.py <chatlogs> -- PASS, exit 0, 0 known defects, parser 11819, generic 1, replay 888, ui 65"
        status: pass
      - kind: integration
        ref: "INCTRACK_LUA=luajit21 python test/run_tests.py <chatlogs> -- identical verdict and identical per-suite counts"
        status: pass
      - kind: other
        ref: "git diff --name-only b2d30cc -- inctrack/ -> inctrack.lua, parser.lua, state.lua (ui.lua untouched by the whole phase)"
        status: pass
    human_judgment: false
  - id: D8
    description: "The right_text finding is recorded as accepted intended
      behaviour with the existing assertions that pin it, and is not counted
      as a seventh fragility"
    verification:
      - kind: unit
        ref: "test/run_tests.py:2646-2654 -- a long line and its right-aligned value printed on top of one another / a right-aligned value was dropped when the line ran long"
        status: pass
      - kind: unit
        ref: "test/run_tests.py:2445-2449 -- WINDOW_FINISHED, whose comment names the do-not-overprint branch at ui.lua:96-100 by line"
        status: pass
    human_judgment: false
  - id: D9
    description: "The validator's rules match what the shipped addon and the
      real Ashita decoder actually produce in game, not only what the harness
      can synthesise"
    verification: []
    human_judgment: true
    rationale: "The persistence round trip runs against Ashita's own json.lua
      and a fully populated run, which is the strongest available evidence.
      What it cannot cover is a settings file written by a build of the addon
      that is not this one -- a future schema version, or a blob written by a
      fork. Carried alongside the two in-game checks already open from Phase 2
      and 03-01's D8."

duration: 16min
completed: 2026-08-29
status: complete
---

# Phase 3 Plan 03: Structural Restore Validation and the Held Timer Sync Summary

**A saved session of the wrong shape is now refused whole before a single field is read for its value — 27 one-field-broken rejection cases, each proving falsy return, no run left behind and nothing raised — with the objective and boss preview rebuilt from validated values instead of adopted by reference, the boon loop no longer skipping malformed members, and `reset()` clearing the held timer sync so a `/incursion reset` cannot seed the next run's clock.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-29T05:32:00Z
- **Completed:** 2026-08-29T05:48:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- **A structural validator that rejects rather than coerces.** A file-local
  predicate over the decoded blob, called after the version gate and *before*
  the wall-clock arithmetic, before the migration, before a single field is
  read for its value. A false answer returns false immediately, so the session
  is discarded whole and the state is left exactly as it was found.
- **The whole blob, or none of it.** The boon loop used to silently skip a
  malformed entry — a half-apply by definition, and the player came back to a
  run holding one of the two boons they picked with nothing on screen saying
  the other was dropped. A malformed member now fails the entire session, and
  the loop copies unconditionally.
- **`restore()` can no longer raise on well-formed JSON.** Four of the fields
  it does arithmetic on itself — `time_left`, `elapsed`, `saved_at` and
  `bonus.remaining` — raised out of `restore()` before this plan, at both of
  its call sites, neither of which has a protected call around it. That is
  review finding IN-01 exactly, and the addon-suite load-path check reproduces
  it end to end through the real load handler.
- **The objective and the boss preview are copies.** Rebuilt field by field
  from validated values, the mob list as a fresh array — which is what IN-01
  recommended rather than narrowing. Three checks mutate the decoded blob after
  a successful restore and assert the run does not move.
- **A held timer sync does not survive a reset.** One line in `State:reset()`,
  with the counter-pin written immediately beside it: a run begun *without* a
  reset still adopts the sync and its clock still reads the announced ninety
  minutes.
- **Both negative controls run and recorded**, the HARD-05 one including nine
  cases that fail by *raising*.
- **The phase closes green on both backends against 127 logs**, no suite below
  its floor, `parser` flat at 11819 and `generic` flat at 1.

## Task Commits

1. **Task 1: reset() clears the held timer sync (HARD-06)** — `1286ffb` (test, RED) then `bd45f24` (feat, GREEN)
2. **Task 2: a structural validator on restore (HARD-05)** — `80db2f6` (test, RED) then `10d679e` (feat, GREEN)
3. **Task 3: close the phase — the whole-phase run and the `right_text` decision** — no files modified; verification and recording only, carried in this SUMMARY

**Plan metadata:** see the `docs(03-03)` commit.

## Files Created/Modified

- `inctrack/state.lua` — `State:reset()` clearing `pending_time` with the
  reason stated in a comment; nine new file-local helpers
  (`opt_number`, `opt_string`, `opt_boolean`, `opt_table`, `full_string`,
  `array_key`, `array_of`, `map_of`, and the four `valid_*` predicates over
  the objective, the boss preview, the bonus, a boon and an extras entry)
  plus `valid_session`; the call to it in `restore()` immediately after the
  version gate; the objective and `next_boss` rebuilt field by field; and the
  boon loop copying unconditionally.
- `test/run_tests.py` — a timers block for the reset case, its counter-pin and
  both staleness guards; a state block with a control, 27 one-field-broken
  rejection cases, the prior-run-undisturbed case and three
  copy-not-reference cases; two persistence cases through Ashita's own decoder
  plus a thin-run round trip; and an addon block for the wrong-shape session on
  the load path.

## The three run reports, verbatim

### Run 1 — no chatlogs (the log-independent floor)

```
inctrack tests
  lua: Lua 5.5
  chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)

  state: objectives, bonus, recovery               88 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                      0 checks  ok
      skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           119 checks  ok

  0 known defects

PASS
```

### Run 2 — the author's 127 logs, default backend

```
inctrack tests
  lua: Lua 5.5
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945288 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               88 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                     35 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           119 checks  ok

  0 known defects

PASS
```

### Run 3 — the same 127 logs under `INCTRACK_LUA=luajit21`

```
inctrack tests
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  chatlogs: C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs
  2945288 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
      event kinds: begin, bonus_done, bonus_new, bonus_progress, boon, boss_hint, complete, objective_boss, objective_kills, phase, points, recover, time
  parser: generic tier matches nothing today        1 checks  ok
      all real lines handled by a specific pattern
  parser: tightened patterns keep every line whole      1 checks  ok
      re-derived from the raw text: 1050 boss/hint/named-NM splits (1050 of them with a parenthesised group), 469 mob lists, 351 boon tails
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery               88 checks  ok
  adaptability: unseen content still tracked       41 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                     35 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           119 checks  ok

  0 known defects

PASS
```

All three exit 0. The two corpus runs carry the `chatlogs:` header and report
127 logs. The grep for `FAILED`, `XFAIL ` and `NOW PASSING ` over a corpus run
prints `0` (the `|| true` is load-bearing — zero is the passing answer and
`grep -c` exits 1 on it). `persistence` is 35 rather than 0, so Ashita's own
`json.lua` really was found and the round trip really ran; a skipped
persistence suite would have left the validator's acceptance of real serialised
output unproven.

The two backends read the same 2,945,288 lines this time. Plan 03-01 recorded a
four-line difference between them; that was the author's client still appending
to the live chatlog directory between runs, and it moves no per-suite count.

## The whole-phase per-suite table

Four columns, every row non-decreasing, the two parser rows flat. No total is
reported: the guarantee is per-suite, and a total hides a fall.

| Suite | Phase-2 floor | after 03-01 | after 03-02 | after 03-03 | Verdict |
|---|---|---|---|---|---|
| `parser: structural lines all parse` | 11819 | 11819 | 11819 | **11819** | flat, as required |
| `parser: generic tier matches nothing today` | 1 | 1 | 1 | **1** | flat, as required |
| `parser: tightened patterns keep every line whole` | — | — | 1 | 1 | added by 03-02 |
| `state: run reconstruction` (replay) | 888 | 888 | 888 | 888 | at floor |
| `state: objectives, bonus, recovery` | 53 | 53 | 53 | **88** | +35 |
| `adaptability: unseen content still tracked` | 20 | 20 | 41 | 41 | +21 (03-02) |
| `disconnect: stale progress is not trusted` | 23 | 23 | 23 | 23 | at floor |
| `timers: countdown, linger, staleness` | 25 | 25 | 25 | **31** | +6 |
| `persistence: json round trip` | 31 | 31 | 31 | **35** | +4 |
| `ui: helpers, layout contract, render` | 65 | 65 | 65 | 65 | **exactly 65** |
| `addon: load, chat, settings, commands` | 83 | 112 | 112 | **119** | +36 |

`ui` is exactly 65 for the third plan running, which is the same statement as
the source diff below: **the render path was made un-crashable from outside
it.** `ui.lua` was not edited once in this phase.

Against the plan's floors: `state` ≥ 70 → **88**. `timers` ≥ 29 → **31**.
`persistence` ≥ 34 and non-zero → **35**. `adaptability` ≥ 34 → **41**.
`addon` at or above 03-01's 112 plus two → **119**. `parser` exactly 11819,
`generic` exactly 1, `replay` exactly 888, `ui` exactly 65 — all met.

### The phase's source diff

```
$ git diff --name-only b2d30cc -- inctrack/
inctrack/inctrack.lua
inctrack/parser.lua
inctrack/state.lua
```

Exactly the three files the phase's three plans own, and `inctrack/ui.lua`
untouched by all of it.

## Both negative controls

### Negative control 1 — the `pending_time` clear removed (HARD-06)

This is what the RED commit (`1286ffb`) *is*: the six checks were written and
run against `State:reset()` as it stood, clearing the run and nothing else.

**Result: `timers` 31 checks, 3 FAILED; `addon` 114 checks, 2 FAILED.**

1. `timers`: a reset left the last remaining-minutes line held, so it is still waiting to seed a run the player has not entered yet
2. `timers`: a run begun straight after a reset came up showing a clock left over from the run the player had just cleared: 5400
3. `timers`: a run begun straight after a reset carried the old run's sync time, so its clock will start counting down from a number the server never gave it
4. `addon`: /incursion reset then a new run: the window came up already counting down from the cleared run's clock (5400 seconds left) instead of blank
5. `addon`: a run begun after /incursion reset carried the cleared run's sync time

**The counter-pin is not among them.** "The entry sync stopped seeding a new
run's clock" passed before the fix and passes after it, and so did both
thirty-second staleness checks. That is the shape the control had to have: had
the counter-pin failed too, the fix would have taken the hold away entirely and
been wrong.

### Negative control 2 — the validator call removed from `restore()` (HARD-05)

Run deliberately and in isolation: the `if not valid_session(data) then return
false; end` call was disabled while the copy-not-reference rebuild and the
unconditional boon loop were left in place, so the control exercises the
*validator* and nothing else. The suite was re-run green and the call restored
before the GREEN commit landed.

**Result: `state` 28 FAILED, `persistence` 2 FAILED, `addon` 5 FAILED — 35 in
all.** The three copy-not-reference checks passed throughout, confirming the
control isolated what it was meant to.

**Nine of the thirty-five fail by raising rather than by returning the wrong
answer** — which is the specific failure IN-01 described, and the reason this
control was required to include one:

| Case | Raise |
|---|---|
| `bonus.remaining` is a string | `state.lua:909: attempt to add a 'number' with a 'string'` |
| `time_left` is a string | `state.lua:820: attempt to add a 'string' with a 'number'` |
| `elapsed` is a string | `state.lua:882: attempt to sub a 'number' with a 'string'` |
| `saved_at` is a string | `state.lua:796: attempt to sub a 'number' with a 'string'` |
| `next_boss` is a number | `state.lua:855: attempt to index a number value (field 'next_boss')` |
| `boons` is a bare string | `state.lua:920: attempt to index a nil value (local 'b')` |
| `boons` holds a number | `state.lua:920: attempt to index a number value (local 'b')` |
| `extra` is a number | `state.lua:925: bad argument #1 to 'for iterator' (table expected, got number)` |
| **the addon load path** | `state.lua:820: attempt to add a 'string' with a 'number'` — thrown through `inctrack.lua:153: in method 'restore'`, inside the `load` handler |

That last row is the whole point. The traceback goes through the real load
handler at `inctrack.lua:153`, where `restore()` is called *outside* the
`pcall` that protects `json.decode`. In game that error escapes into Ashita,
and the `settings.save()` that would have cleared the unusable string never
runs — so it fails again on the next load, and the one after that.

The other twenty-six fail by being accepted and building a run:
`kills_max`, `objective.count`, `bonus.max`, `phase`, `points` (as the numeral
`"84"`, which Lua would have coerced silently), the four mob-list shapes, a
bare-string `objective`, a bare-string `bonus`, a nameless second boon, a
numeric boon `stats`, a numeric `objective.kind`, a blank `next_boss.name`, a
string extras entry, a numeric `difficulty`, a string `points_partial`, a blank
`instance`, and a malformed session applied straight over a run in progress —
plus, through Ashita's own decoder, a hand-edited objective count and a boon
with no name.

## The validator's rules, as implemented

So a later reader can see what a session must look like without re-deriving it
from the code. `absent` means the field is nil; every rule is derived from what
`serialise()` writes.

| Field | Rule |
|---|---|
| the blob itself | a table |
| `instance` | a string, and not empty |
| `difficulty`, `finish_time` | absent or a string |
| `phase`, `kills_cur`, `kills_max`, `points`, `awards_seen`, `phases_cleared`, `elapsed`, `time_left`, `saved_at` | absent or a number |
| `finished`, `points_partial` | absent or a boolean |
| `objective` | absent, or a table whose `kind`, `name`, `loc` and `text` are each absent or a string, whose `count` is absent or a number, whose `stale` is absent or a boolean, and whose `mobs` is absent or an array of non-empty strings |
| `next_boss` | absent, or a table whose `name` is a non-empty string and whose `loc` is absent or a string |
| `bonus` | absent, or a table whose `kind`, `label` and `loc` are each absent or a string, whose `cur`, `max` and `remaining` are each absent or a number, and whose `done` is absent or a boolean |
| `boons` | absent, or an array whose every value is a table with a non-empty string `name` and an absent-or-string `stats` |
| `extra` | absent, or a table with string keys whose every value is a table with an absent-or-string `label`, absent-or-number `cur` and `max`, and absent-or-boolean `done` |

Two rules govern the whole table and are worth stating separately:

- **"An array"** means *every key* is checked as well as every value:
  `type(k) == 'number' and k >= 1 and k % 1 == 0`. A stray non-integer key or a
  hole is a shape the addon's own writers cannot produce, and admitting one
  would let a decoded blob carry a value past a length-based loop unseen. The
  key test is deliberately arithmetic rather than a subtype test: a
  JSON-decoded number is a float and a `tonumber`-derived one may be an
  integer, and `INCTRACK_LUA=luajit21` is how that choice is proven rather than
  assumed.
- **`version` is not in the table**, because the version gate above already
  owns it: `serialise()` still writes `version = 2`, `restore()` still accepts
  1 or 2 and refuses anything else, and the version-1 migration still
  re-derives the cleared count from the phase number and still starts the award
  count at zero. The validator runs strictly between them. Phase 2's schema
  work is built on, not replaced —
  `grep -cE "version[[:space:]]+= 2," inctrack/state.lua` prints `1` and
  `grep -cF "data.version == 1" inctrack/state.lua` prints `1`.

**`objective.kind` is checked for being a string and never against a list of
known kinds.** A shape check is allowed; a content check is forbidden by the
project's zero-content-knowledge constraint, and a kind the server adds later
must survive.

## Phase 3's five ROADMAP criteria, each tied to named checks

A criterion with no named check is not met, however green the run.

**1. A run record that errors mid-render leaves the ImGui stack balanced; the
failure is reported once and the window disables itself.**
Established by the `addon` suite (plan 03-01): *"a bad value in the mob list
threw out of d3d_present and into the game thread every addon shares"*, *"a
percent sign in a name the server sent threw out of d3d_present"*, *"the ImGui
stacks were left unbalanced after a render error"*, *"the ImGui stacks were
left unbalanced after a raise from a draw call"*, *"one render failure produced
N chat lines"*, *"a window that took itself off screen kept drawing anyway"*,
*"/incursion did not bring the window back"* and *"/incursion reset left the
window switched off"*. Trigger C's *"the shell closed a window that was never
opened"* and *"the shell popped a style var that was never pushed"* pin the
conditionality, and 03-01's second negative control shows those are the only
three checks that notice it.

**2. A boss objective naming a mob whose own name contains " at " parses with
the full name intact; a mob list containing a comma-bearing name yields one
mob.**
Established by the `adaptability` suite (plan 03-02): *"a boss whose own name
contains ' at ' was shown truncated"*, *"part of the boss's name was folded
into its coordinates"*, *"the boss waiting at the end of the phase was named
wrong"*, *"the bonus NM was shown under a truncated name"*, *"a boss objective
with no coordinates vanished from the window entirely"*, *"a mob whose name
contains a comma was split into two mobs that do not exist"* and *"the mob list
picked up an empty or untrimmed entry"* — and corpus-wide by
`parser: tightened patterns keep every line whole`, which re-derives 1050
boss/hint/named-NM splits and 469 mob lists from the raw text in Python across
127 logs.

**3. An ordinary buff line is never claimed as a boon, while the existing boon
assertions all still pass.**
Established by the `adaptability` suite (plan 03-02): *"a line with an empty
glyph group was listed as a boon"*, *"a boon with no name was listed, so the
window would draw a blank row"* and *"an ordinary buff was listed among the
boons picked this run"*; corpus-wide by the same third parser Result's 351 boon
tails, checked in both directions. The existing assertions still passing is
what the flat `parser` count of 11819 and the unmoved `replay` count of 888
say.

**4. A structurally malformed saved session is discarded whole: `restore()`
returns falsy and leaves no run behind, so nothing of that shape ever reaches
arithmetic in `ui.lua`.**
Established by this plan's `state` block — 27 rejection cases, each asserting
falsy return *and* no run left behind *and* no raise, including the two the
criterion names by field: *"a saved session whose kill cap is the word 'twenty'
rather than a number was not discarded"* and *"a saved session whose mob list
holds a number where a mob's name belongs was not discarded"*. Plus *"a
rejected session took the run the player was standing in with it"*, the
persistence-suite pair through Ashita's own decoder, and the `addon` load-path
block. The negative control above is the evidence these bite.

**5. `/incursion reset` within 30 seconds of a `You have N minutes remaining`
line does not seed the next run's clock — `pending_time` is nil after
`reset()`.**
Established by the `timers` block — *"a reset left the last remaining-minutes
line held"*, *"a run begun straight after a reset came up showing a clock left
over from the run the player had just cleared"*, *"a run begun straight after a
reset carried the old run's sync time"*, with the counter-pin *"the entry sync
stopped seeding a new run's clock"* and both staleness guards — and by the
`addon` block driving the real `/incursion reset` command: *"/incursion reset
then a new run: the window came up already counting down from the cleared run's
clock"*.

## The `right_text` decision

**Accepted as intended behaviour. Not a defect, not deferred to Phase 4, and
not counted as a seventh fragility.**

The finding, from Phase 1: `Complete 48m 44s` stops right-aligning once the
instance name plus difficulty runs past the target x, because `right_text`'s
do-not-overprint branch fires and the value sits after the text instead of at
the right edge.

Three things support accepting it, and all three are recorded here:

1. **The branch is correct as written.** `ui.lua:93-101` computes
   `target = origin_x + CONTENT_W - CalcTextSize(text)` and moves the cursor
   only `if target > imgui.GetCursorPosX()`. Printing the value on top of the
   instance name would be strictly worse than letting it sit after it. There is
   no third option that does not change the layout.
2. **The behaviour is already pinned by the suite in two places**, so the
   decision is durable in the tests rather than in prose alone:
   - `test/run_tests.py:2646-2654`, at the helper level: *"a long line and its
     right-aligned value printed on top of one another"* and *"a right-aligned
     value was dropped when the line ran long"* — a sixty-character line
     followed by `right_text`, asserting no `SetCursorPosX` at all and two
     `TextColored` calls.
   - `test/run_tests.py:2445-2449`, the `WINDOW_FINISHED` snapshot, whose
     comment names the branch by line: *"There is no SetCursorPosX before the
     value because the instance and difficulty already run past where it would
     start — the do-not-overprint branch at ui.lua:96-100."*
3. **The alternative is out of scope for the milestone.** Shortening or eliding
   the header so the value always reaches the right edge is a change to what
   the window looks like, which the ROADMAP rules out for the whole of v1.2.0
   — this is a quality pass on shipped code, not a redesign.

`ui.lua` was not edited by any plan in this phase, and this decision is why it
stays that way.

## Decisions Made

Everything substantive was locked by `03-CONTEXT.md` and honoured as written.
The discretionary ones, now fixed:

- **The validator's shape.** Small named predicates over the two questions it
  keeps asking — `opt_number`, `opt_string`, `opt_boolean`, `full_string` —
  plus `array_of` and `map_of` for the two collection shapes, so
  `valid_session` reads as a table of rules rather than a wall of conditionals.
- **`array_key` tests `k >= 1 and k % 1 == 0`**, not an integer subtype. A
  JSON-decoded number is a float; a `tonumber`-derived one may be an integer.
  The `luajit21` run is the proof, not the hope.
- **A control at the head of the rejection block.** A validator that rejected
  everything would pass all 27 rejection cases and cost the player their
  in-progress run on every reload. The control asserts a session the addon just
  wrote itself restores, with the objective kind, the count, all three mobs,
  the boss name, the bonus max, both boons, the points and the phase intact.
- **One-field-broken fixtures, rebuilt from a fresh state every time.**
  `serialise()` hands out the live run's own `objective` and `next_boss` tables
  — which is the very defect being fixed — so a mutated fixture would have
  poisoned every case after it. The helper builds a new state and re-feeds the
  chat lines per case.
- **A discarded session is not reported at the player.** The run is gone either
  way and there is nothing they can do about it; an error line would be noise.
  The addon check asserts no error line *and* no false "Resumed run" line.
- **`opt_table` is defined but currently unused** — every table-shaped field
  has a stronger rule than "absent or a table". It is left in place as the
  obvious hook for a field that later needs only that, and it costs one line.

## Deviations from Plan

None — plan executed exactly as written. The plan's `read_first` pointers were
accurate, both RED runs failed in exactly the shape predicted, and no existing
check turned out to depend on the boon loop's skipping behaviour (hard rule 4's
stop-and-report condition was never reached).

## Issues Encountered

None.

## Carry-forwards for Phase 4 — one list

Recorded here so Phase 4 inherits a list rather than an archaeology exercise.
All noted, none acted on, per this phase's scope fence.

1. **The per-frame options table.** The `{ visible = ..., locked = ... }`
   literal in `inctrack.lua`'s frame handler is still allocated sixty times a
   second. **PERF.**
2. **The unrate-limited `parse error:` chat line.** Since 03-01 latched the
   render report, this is the only chat output in the addon with no
   report-once guard; a systematically malformed line would flood chat.
3. **The cheap-rejection guard's broad boon clause, and the allocations ahead
   of it.** Deliberately left alone by 03-02 so it could not confound that
   plan's corpus comparison. **PERF-01.**
4. **`shorten()`'s unbounded memo cache.** **PERF-04.**
5. **`docs/design.md` drift and the stale `ui.lua:15-26` layout comment.**
   **DOC-01/02.**
6. **The harness's duplicated wording knowledge** — the reference shapes the
   over-reach guard re-derives in Python restate what `parser.lua` knows.
7. **IN-07: integer versus float on the version-1 migration's phase
   arithmetic.** Explicitly deferred by this plan's hard rules and still open.
8. **Capping persisted key and value lengths.** `T-03-19` in this plan's threat
   register is dispositioned *accept*: server text is used as table keys in the
   extras map, and the validator checks those keys are strings and their values
   shape-correct, but does not bound their length. Out of scope for a
   correctness milestone; recorded here so it is not lost.
9. **The `coverage` message's cp1252 exposure**, carried forward from an
   earlier phase and still unaddressed.

## The two in-game checks still open from Phase 2

Restated as **still open and still unclaimed**. Nothing was deployed to the
live install by this phase, and nothing in Phase 3 closes either of them.
Alongside them sit 03-01's coverage item D8 — that Ashita's real ImGui binding
accepts `pcall(imgui.End)` and `pcall(imgui.PopStyleVar, 1)` reached through
its `__index` metatable — and this plan's D9.

Every one of Phase 3's five criteria is assertable in the harness, which is why
all five are tied to named checks above.

## Next Phase Readiness

- **Phase 3 is complete.** All six HARD requirements closed: HARD-01 (03-01),
  HARD-02/03/04 (03-02), HARD-05/06 (03-03).
- **The standing guarantee holds and has risen**: no pre-existing suite's count
  fell in any of the three plans, `parser` is still exactly 11819 and `generic`
  exactly 1, zero known defects, green on both backends against 127 logs.
- **Phase 4 is unblocked.** Parser behaviour is now settled, which is what
  PERF's benchmark baseline and DOC-01/02's corrections were waiting on. The
  carry-forward list above is Phase 4's inbox.
- **Two layers now stand between a wrong-shaped blob and the player**, and both
  stay: 03-01's containment keeps the frame up when wrong data reaches the
  render path, and 03-03's validator keeps the wrong data out of the run record
  in the first place. Neither is redundant — the first covers what the second
  cannot see, which is anything the *live* event stream produces.

---
*Phase: 03-fragile-paths*
*Completed: 2026-08-29*

## Self-Check: PASSED

- Files claimed created/modified all exist on disk: `03-03-SUMMARY.md`,
  `inctrack/state.lua`, `test/run_tests.py`.
- All four task commits resolve in git history: `1286ffb`, `bd45f24`,
  `80db2f6`, `10d679e`.
- `git status --porcelain inctrack/ test/` is clean; `git diff --name-only`
  over this plan's commits lists exactly `inctrack/state.lua` and
  `test/run_tests.py` — `ui.lua`, `parser.lua` and `inctrack.lua` untouched by
  this plan.
- No stubs, no `TODO`/`FIXME`/placeholder text, and no skipped or expected-fail
  checks introduced. `EXPECTED_XFAILS` is still `0` and `EXPECTED_DEFECTS` is
  still empty; all three runs report `0 known defects`.
- Every `<verify>` command in the plan was run and its output is reproduced
  above; none was left unrun.
- Phase 2's schema is intact:
  `grep -cE "version[[:space:]]+= 2," inctrack/state.lua` → `1`,
  `grep -cF "data.version == 1" inctrack/state.lua` → `1`,
  `grep -cF "run.objective      = data.objective" inctrack/state.lua || true` → `0`,
  `grep -c "self.pending_time = nil" inctrack/state.lua` → `2`.

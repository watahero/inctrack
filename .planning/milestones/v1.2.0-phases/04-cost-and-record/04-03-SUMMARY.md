---
phase: 04-cost-and-record
plan: 03
subsystem: documentation
tags: [lua, ashita, imgui, changelog, versioning, design-record, release]

requires:
  - phase: 01-coverage
    provides: the stubbed Ashita host the changelog pin's suite runs in, and the six whole-window snapshots the layout comment is reviewed against
  - phase: 02-defects-and-contracts
    provides: the three fixed defects the 1.2.0 changelog entry names, schema version 2, and the Begin(name, nil, flags) contract the design doc now states
  - phase: 03-fragile-paths
    provides: the render containment, the structural validator and the three parser tightenings the design doc now describes -- and the two superseded summaries it deliberately does not describe them from
  - phase: 04-cost-and-record
    plan: 01
    provides: the cheap gate and its colour fall-through, and the reject-path figure the README and design doc now quote as a printed number
  - phase: 04-cost-and-record
    plan: 02
    provides: the deferred write, the hoisted frame table and the bounded memo cache the README's write policy and the design doc's cost section now state
provides:
  - "addon.version = '1.2.0', and a CHANGELOG.md 1.2.0 entry naming the three defects, six hardenings and four cost changes in user-facing terms"
  - "a harness pin: the newest '##' heading in CHANGELOG.md must name the version addon.version holds; notes and skips when the file is absent"
  - "docs/design.md rewritten against the shipped source -- window sizing, NoTitleBar, the real stats layout, the run-record fields, and new sections on persistence and the schema, the restore validator, render containment, cost, and what the player is told"
  - "ui.lua's layout comment enumerating all nine rows in draw order with the condition each appears under"
  - "README corrected: the harness stub module, the suites that run without chatlogs, corpus figures re-derived from a real run, the current write policy, two new disconnect rows"
  - "the milestone hand-off: three in-game checks still open, four carry-forwards not taken, PROC-01..04 named as deliberately v2, and four accepted residuals"
affects: [milestone-close, gsd-audit-milestone]

actuals:
  tokens: 13794
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "pin two records to each other rather than to a constant: the harness reads addon.version out of the host and the newest changelog heading off disk, and asserts they agree -- neither is hardcoded in the test"
    - "a documentation check that notes-and-skips when its input is absent, because the addon folder is distributable on its own"
    - "write the design record from the source file, never from a phase summary: a summary can be superseded after it is written and the code cannot"
    - "the pre-copy comparison before a redeploy: a post-copy comparison can only prove the copy succeeded, never say what the install actually held"

key-files:
  created: []
  modified:
    - inctrack/inctrack.lua
    - inctrack/ui.lua
    - docs/design.md
    - README.md
    - CHANGELOG.md
    - test/run_tests.py

key-decisions:
  - "1.2.0, not 1.3.0 (no new features) and not 1.1.1 (three defects, six hardenings, four cost changes)"
  - "The changelog is written in the terms the Phase-1 expected failures used -- 'a bonus objective payout was counted as a cleared phase', never a file or function name"
  - "The version pin lives in the addon suite beside the banner check, reads both sides out of their real sources, and notes-and-skips on an absent CHANGELOG.md exactly as the persistence suite does for Ashita's json.lua"
  - "docs/design.md keeps its seven top-level sections and is rewritten inside them, so a reader who knows the old document can still navigate; the new material lands as subsections under Architecture and Error handling"
  - "Every ledger row was checked against the cited source file before the sentence was written; four rows' line citations had drifted since the plan was written and are corrected here"
  - "The README's inherited 'documents a close button and a title bar' claim is false and was recorded as a correction to the context rather than acted on"
  - "state.lua was not changed by Phase 4, so 'pre-copy same: state.lua' is the correct verdict, not the copy-target-wrong signal -- the other three DRIFTED is what proves the target"

patterns-established:
  - "A claim in a document carries the file it was checked against; a claim taken from a summary carries the risk that the summary was reversed"
  - "Re-derive a corpus figure from the corpus and cross-check it against a printed report line -- 888 replay checks == 111 runs x 8 checks is what makes both numbers trustworthy"
  - "Record what the deployment target held before overwriting it; the overwrite destroys the only evidence of staleness"

requirements-completed: [DOC-01, DOC-02]

coverage:
  - id: D1
    description: "addon.version reads '1.2.0' and CHANGELOG.md carries a 1.2.0 entry naming what changed in user-facing terms"
    requirement: DOC-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: load, chat, settings, commands -- the banner naming this build reached chat once"
        status: pass
      - kind: other
        ref: "grep -c \"addon.version = '1.2.0'\" inctrack/inctrack.lua == 1; grep -c '^## 1.2.0' CHANGELOG.md == 1; grep -c '^## 1' CHANGELOG.md == 3"
        status: pass
    human_judgment: false
  - id: D2
    description: "The version string and the newest changelog heading cannot drift apart unnoticed: the harness asserts they agree"
    requirement: DOC-02
    verification:
      - kind: unit
        ref: "test/run_tests.py#addon: load, chat, settings, commands -- the addon reports version X and the newest changelog heading names Y"
        status: pass
      - kind: other
        ref: "negative control: heading set to 9.9.9 -> that check alone red, exit 1; changelog removed -> notes and skips at 189, exit 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "docs/design.md states what the code does -- window sizing, NoTitleBar, the stats layout, the boons row, and the elapsed_final / desynced / recovered / points_partial / bonus.loc run-record fields"
    requirement: DOC-01
    verification:
      - kind: other
        ref: "grep -c AlwaysAutoResize docs/design.md == 2; NoTitleBar, CONTENT_W, elapsed_final, points_partial, recovered, desynced all >= 1; 'rather than `AlwaysAutoResize`' == 0"
        status: pass
    human_judgment: true
    rationale: "A grep proves a token is present, never that the sentence around it is true of the code. Every claim was checked against the cited source file and the completed ledger below records what each file actually said, but the correctness of the prose is a reading, not an assertion."
  - id: D4
    description: "docs/design.md carries what this milestone changed: awards_seen and the single author for phases_cleared, schema version 2 and its version-1 migration, the structural validator and its shape-only rule, render containment and its two latches, the three parser tightenings, and this phase's cost changes"
    requirement: DOC-01
    verification:
      - kind: other
        ref: "grep -c awards_seen == 5; 'version = 2' == 1; render_ok == 3; render_off == 1; saved_at == 2; pending_time == 1; full_string == 0"
        status: pass
    human_judgment: true
    rationale: "Same reason as D3. The two negative greps prove the reversed claims did not reach the document; they cannot prove the replacements are right."
  - id: D5
    description: "ui.lua's layout comment names every row the window can draw and the condition under which each appears"
    requirement: DOC-01
    verification:
      - kind: unit
        ref: "test/run_tests.py#ui: helpers, layout contract, render -- all six whole-window snapshots, 74 checks, unmoved"
        status: pass
      - kind: other
        ref: "git diff -U0 inctrack/ui.lua contains no line that is not a comment; 43 insertions, all inside the file header block"
        status: pass
    human_judgment: true
    rationale: "The snapshots prove the drawn output did not change. That the nine enumerated rows are the complete set is a reading of render() and its seven draw_ helpers, not an assertion the suite makes."
  - id: D6
    description: "README.md describes the addon that ships: the suites that run without chatlogs, corpus figures re-derived from an actual run, the file tree including the harness stubs, and the write policy as it now works"
    requirement: DOC-02
    verification:
      - kind: other
        ref: "grep -c stubs.py README.md == 1; grep -cF '106 completed runs' == 0; grep -ci 'close button' == 0; figures cross-checked against the run header (127 logs, 2,951,129 lines) and a re-derivation (111 runs, 8 instances, 130 days)"
        status: pass
    human_judgment: false
  - id: D7
    description: "The milestone closes green: both backends, 127 logs, parser exactly 11819, generic exactly 1, zero known defects, no pre-existing suite's count fallen, and the repo redeployed to the live install with what the install held before the overwrite recorded first"
    verification:
      - kind: integration
        ref: "python test/run_tests.py; python test/run_tests.py <chatlogs>; INCTRACK_LUA=luajit21 python test/run_tests.py <chatlogs> -- all PASS, exit 0, 0 known defects, zero XFAIL and zero NOW PASSING lines"
        status: pass
      - kind: other
        ref: "pre-copy: 3 DRIFTED + 1 same (state.lua, unchanged since Phase 3); post-copy: same x4, DIFFERS x0; deployed inctrack.lua reports 1.2.0"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-29
status: complete
---

# Phase 4 Plan 03: DOC-01 / DOC-02 Summary

**inctrack ships as 1.2.0 with a changelog the harness holds the version to, a design record rewritten from the source rather than from two summaries the code review reversed, a `ui.lua` layout comment naming all nine rows, and the milestone closed green on both backends against 127 logs and redeployed to the live install.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-29T08:53:43Z
- **Completed:** 2026-08-29T09:18:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- **`addon.version` reads `'1.2.0'`** — a one-literal diff under `inctrack/`, and the only behavioural change this plan makes.
- **`CHANGELOG.md` has a 1.2.0 entry** naming the three defects, six hardenings and four cost changes in the terms a player would use, and **the harness now pins the two together**: the newest `##` heading must name the version the addon reports. Negative control run both ways.
- **`docs/design.md` rewritten against the shipped source.** All twenty-five ledger rows worked, each one checked against the file it cites. Five sections the document never had: persistence and the schema, the restore validator, render containment, cost, and what the player is told.
- **`ui.lua`'s layout comment enumerates all nine rows** in draw order with the condition each appears under, keeping the sample above it. Comments only, and the six whole-window snapshots are byte-identical.
- **The README describes what ships** — the harness stub module, the window/addon-shell/cost suites, corpus figures re-derived from a real run, 04-02's write policy, and two new disconnect rows.
- **The milestone closes green on both backends** against 127 logs, zero known defects, no pre-existing suite's count fallen, `parser` flat at 11819 and `generic` flat at 1, and the live install now holds the 1.2.0 build.

## Task Commits

1. **Task 1: 1.2.0 — the version, the changelog, the README (DOC-02)** — `d7e881e` (docs)
2. **Task 2: `docs/design.md` describes the code that ships, and the layout comment names every row (DOC-01)** — `af2c6f1` (docs)
3. **Task 3: the phase closes, the milestone closes, and the build goes to the live install** — runs, redeploy and record; no repo change of its own, carried by the plan metadata commit

## Files Created/Modified

- `inctrack/inctrack.lua` — `addon.version = '1.2.0'`. One line; `git diff --numstat` reports `1 1`.
- `inctrack/ui.lua` — the layout comment. 43 inserted lines, every one inside the `--[[ ]]--` file header block; the non-comment diff is empty.
- `CHANGELOG.md` — the 1.2.0 entry. The 1.1.0 and 1.0.0 entries are untouched.
- `README.md` — file tree, what runs without chatlogs, corpus figures, the write policy, two disconnect rows.
- `docs/design.md` — rewritten inside its seven existing top-level sections; 565 changed lines.
- `test/run_tests.py` — the changelog pin, in the addon suite beside the banner check. `addon` 189 → 190.

---

# The three closing runs, verbatim

## 1. `python test/run_tests.py` (no logs, default backend) — exit 0

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
  addon: load, chat, settings, commands           190 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 287,503 lines/s, 3.478 us/line
      new shape (shipped):  1,079,240 lines/s, 0.927 us/line
      new/old: 3.75x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

## 2. `python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"` — exit 0

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
  addon: load, chat, settings, commands           190 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: Lua 5.5
      old shape (Phase 3): 282,995 lines/s, 3.534 us/line
      new shape (shipped):  1,024,194 lines/s, 0.976 us/line
      new/old: 3.62x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

## 3. `INCTRACK_LUA=luajit21 python test/run_tests.py "...\chatlogs"` — exit 0

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
  addon: load, chat, settings, commands           190 checks  ok
  cost: the non-Incursion reject path               6 checks  ok
      corpus: 24 lines (18 colour-free, 6 coloured), 3000 iterations a pass, best of 3
      backend: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
      old shape (Phase 3): 567,155 lines/s, 1.763 us/line
      new shape (shipped):  2,865,466 lines/s, 0.349 us/line
      new/old: 5.05x
      per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub
      per coloured rejected line -- old: 1.00 strip_colors, 5.00 gsub; new: 1.00 strip_colors, 2.00 gsub
      recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold

  0 known defects

PASS
```

The two 127-log runs report **identical per-suite check counts to each other**, and identical to the no-logs run for every suite the no-logs run has. All three: `PASS`, exit 0, `0 known defects`, **zero `XFAIL ` lines and zero `NOW PASSING ` lines** (grepped on the captured output of each run: `XFAIL=0 NOWPASSING=0 FAILED=0` for all three).

---

# The whole-phase per-suite table

| Suite | Phase floor (03 close) | After 04-01 | After 04-02 | **After 04-03** | Movement |
|---|---|---|---|---|---|
| `parser: structural lines all parse` | 11819 | 11819 | 11819 | **11819** | flat — exact pin held |
| `parser: generic tier matches nothing today` | 1 | 1 | 1 | **1** | flat — exact pin held |
| `parser: tightened patterns keep every line whole` | 1 | 1 | 1 | **1** | flat |
| `state: run reconstruction` (replay) | 888 | 888 | 888 | **888** | flat |
| `state: objectives, bonus, recovery` | 105 | 105 | 105 | **105** | flat |
| `adaptability` | 42 | 119 | 119 | **119** | flat here |
| `disconnect` | 23 | 23 | 23 | **23** | flat |
| `timers` | 31 | 31 | 31 | **31** | flat |
| `persistence` | 40 | 40 | 40 | **40** | flat, running not skipping in both 127-log runs |
| `ui` | 65 | 65 | 74 | **74** | flat here — all six snapshots still byte-identical |
| `addon` | 143 | 160 | 189 | **190** | **+1 here** — the changelog pin |
| `cost: the non-Incursion reject path` | — | 6 | 6 | **6** | flat |

Every row is non-decreasing across all four columns. `parser` and `generic` are flat at exactly 11819 and 1. The only movement this plan makes is the single new `addon` check, which is what the plan predicted.

---

# The completed drift ledger

Twenty-five rows, each checked against the file it cites **before** the replacement sentence was written. "Source, as checked" is what the file actually said on 2026-08-29 at commit `9d98a85`.

| # | The document said | Source, as checked | What was written |
|---|---|---|---|
| D1 | `:34` one points message per phase, and the count of them is the count of cleared phases | `state.lua:208-210` (phase line: `phases_cleared = e.phase - 1` when higher) and `:434-437` (completion: `closing = run.phase or (run.recovered and 0 or 1)`, assigned only upwards) are the **only** two authors. `state.lua:76` declares `awards_seen` "Never displayed"; `:381` increments it on each points award | The message-stream row now reads "Our own points award; a boss just died. **Not** a count of cleared phases", and `state.lua`'s Rules carry a dedicated bullet naming the single author plus a second on what `awards_seen` is for |
| D2 | `:99` the bonus record's fields, no `loc` | `state.lua:286-294` stores `loc = e.loc`; `ui.lua:233-235` draws it as the label suffix when the bonus counts only to one | `bonus = { kind, label, loc, cur, max, expires_at, done }` in the record listing, and the bonus row's condition in the layout list |
| D3 | `:104` run record tail: `started, points, phases_cleared, finished, finish_time, hide_at` | `new_run` (`state.lua:53-83`) also creates `awards_seen` and `elapsed_final`. `desynced`, `recovered`, `points_partial` and `objective.stale` are set elsewhere and never created by `new_run` | The listing gains `awards_seen` and `elapsed_final`, and a paragraph beneath names the four fields that appear only once something sets them, with what each means |
| D4 | `:129` `phases_cleared` increments on each `points` event | False; see D1 | Removed. `grep -cF "increments on each \`points\` event" docs/design.md` prints 0 |
| D5 | `:130` the completion freezes elapsed and sets the linger | True but partial. `state.lua:416-448` also closes the phase — **assigned, not incremented, only upwards** — clears bonus/objective/note/extras, records `finish_time` and `elapsed_final`, and gives a `recovered` run no floor | A full bullet: what it freezes, what it clears, and the whole assigned-not-incremented argument including why a run joined at the final phase gets no floor |
| D6 | `:134` serialised after every unrepeatable event, at most every 5 s otherwise | `inctrack.lua:292-296` marks; `:369-372` flushes on the frame above both early returns; `:228-235` writes unconditionally on unload | A new **Persistence and the schema** section states the mark/flush/unload split, the flag being consumed before the write, and the one-frame residual in plain words |
| D7 | `:145` one window, fixed width, height auto-fitting | `ui.lua` `render` builds `NoFocusOnAppearing + AlwaysAutoResize + NoScrollbar + NoTitleBar`, plus `NoMove` when locked, and `Dummy(ARG_SPACER)` at `CONTENT_W = 300` is the first thing inside `Begin` | The flags named individually, the spacer named as the width mechanism, and the `Begin(name, nil, flags)` positional contract stated with why the explicit `nil` asks for no close control |
| D8 | `:147-163` a `Time left / Elapsed / Points / Phases` grid mockup | `render` draws: spacer, header (clock on the header line), desync banner, objective, bonus, extras, one `Phases cleared … Elapsed` line, boons, note | Replaced with a mockup matching `render`, followed by the nine-row enumeration in draw order with each row's condition |
| D9 | `:171` points and phases cleared are per-run | `draw_stats` (`ui.lua:277-283`) draws only `Phases cleared` and `Elapsed`; points appear nowhere in `ui.lua` | "Points are tracked per run and reset on `begin`, and are **not displayed** — the 1.1.0 compaction removed the row and nothing has put it back" |
| D10 | `:173-175` fixed width **rather than** `AlwaysAutoResize` | Exactly backwards. `ui.lua:56-63` states the hazard and names the spacer as the mitigation | The hazard is kept and the mitigation corrected: "Aligning against the live width of an `AlwaysAutoResize` window feeds the alignment back … the spacer is the mitigation, and the flag stays." `grep -cF "rather than \`AlwaysAutoResize\`"` prints 0 |
| D11 | `:179-180` `/incursion` toggles and overrides until the next run | True, plus: the bare command while `render_off` is a **re-enable, not a toggle**, deliberately does not clear `override`, and reports what is on screen rather than what was asked (`inctrack.lua:478-513`) | The Visibility section keeps the toggle rule and adds the exception with all three reasons |
| D12 | `:199-204` error handling: one `pcall` and a discarded blob | Missing the render `pcall` in `d3d_present`, the two latches, the conditional repair, the deliberately unrepaired colour stack, the closure-wrapped calls, the validator, and the two report-once guards | A new **Render containment** section, a new **What the player is told** section, and an Error handling section restructured as four numbered boundaries in the order a bad input meets them |
| D13 | `:206-222` seven suites | The harness docstring numbers **eleven** suites; a real run prints **twelve** `Result` lines, because `test_parser` emits three. `ui.lua` and `inctrack.lua` run behind `test/stubs.py` | "Eleven suites, reported as twelve result lines", as a table with a **Needs** column: chatlogs, Ashita's `json.lua`, or nothing. `grep -cF "Seven suites"` prints 0 |
| D14 | `:22-23` ~106 runs across 8 instances | Re-derived from the corpus: **127 logs, 130 days, 2,951,129 chat lines, 111 completed runs across 8 instances** (9 entered, 8 completed one) | Those figures, with the measurement date |
| D15 | `:31` the boss preview row, no note | `parser.lua:165-185` and `:177-185`: the precise form captures the name greedily and requires the location parenthesised, putting the split on the **last** ` at (`; the 1.1.0 lazy shape is kept as a fallback at all three ` at ` sites | The row's note states the location-is-the-anchor rule and why; the parser section states that the three ` at ` forms keep a fallback and the other two tightenings do not |
| D16 | `:30` the mob list row, no note | `parser.lua:45-60`: `s:find(', ', start, true)` — plain text, comma-**space**, no fallback, empty pieces dropped | The row's note states the separator, why a comma-carrying name survives, and that a blank piece is dropped |
| D17 | `:41` the `(glyph): stats` tail distinguishes a boon from a buff | `parser.lua:268-276`: the group is `%([^)]*%)` and **may be empty**; the discriminator is the tail **plus a non-blank trimmed name** | The row states both, and states why emptiness is allowed: an unset icon field renders `()` through the same template and the server never announces a boon twice |
| D18 | `:86-87` a cheap prefix check before any pattern runs | `parser.relevant` (`parser.lua:401-413`) is called from `inctrack.lua:256` **before `strip_colors`**, and again at `parse`'s head; a colour-marker byte is an unconditional yes; the timestamp loop is gated on a leading `[` | A new **Rejecting a line the addon does not care about** subsection: both rejections, the plural-free timer needle, the colour fall-through and why, and the false-positives-only property |
| D19 | absent | `state.lua:582` writes `version = 2`; `:820` accepts 1 or 2; `:912-932` migrates a version-1 blob | The Persistence section: what version 2 changed, why a v1 blob is migrated not imported, and what the migration does with each counter |
| D20 | absent | `state.lua:629-814`: reject-never-coerce, discard-whole, shape-not-content, `is_string` accepting a blank, `array_of` demanding contiguity from 1, `array_key` testing `k % 1 == 0` | A new **The restore validator** section with all six, including why a blank passes and why a holed list does not |
| D21 | `:116` a restored run is desynced | `state.lua:847-853` ages by the `saved_at` gap clamped at zero; `:855-857` refuses past three hours; `:873-875` refuses when the gap exceeds the saved `time_left` plus a minute | The Persistence section's **Restoring** paragraphs: both refusals, the clamp and why, and how the gap moves elapsed, `time_left` and the bonus countdown |
| D22 | absent | `inctrack.lua:172-182`: `resume()` prints on refusal, with a deliberate exemption for a blob that was already `finished` | The first bullet of **What the player is told**, including what a silent rejection looks like to the player and why the finished-run exemption is right |
| D23 | absent | `state.lua:85-95`: `reset()` clears `pending_time` as well as the run | A Rules bullet naming `pending_time` and the bridge it exists for |
| D24 | `:208-211` the two pure modules under `lupa` | Plus `ui.lua` and `inctrack.lua` behind the stubs in `test/stubs.py`; `inctrack.lua` exports nothing and `ui.lua` exports only `render` and `forget`, so file-scope state is reached by upvalue reflection | The Testing section's opening paragraph |
| D25 | `:7` revised 2026-08-20 | — | A 2026-08-29 (v1.2.0) revision line added **beneath** the 2026-08-20 one, which stays |

## Rows that had drifted again since the plan was written

Four line citations in the plan's ledger no longer point at what they name, and one factual premise in Task 3 does not hold. All five were found by opening the file rather than trusting the citation, which is the whole reason the plan required it.

1. **D7's `ui.lua:394-418`** does not contain `render`. `render` was at `ui.lua:440-488` before this task and is at `:483-531` after it. The row's other citation, `ui.lua:56-74`, is correct.
2. **D11's `inctrack.lua:372-399`** is inside `d3d_present`, not the command handler. The bare-`/incursion` re-enable is at `inctrack.lua:478-513`, inside the handler registered at `:467`.
3. **D13's arithmetic is off by one in both directions.** The plan says "ten suites, eleven `Result` lines, plus the reject-path cost line". The harness docstring numbers **eleven** suites (the cost suite is its own numbered entry, 11), and a real run prints **twelve** `Result` lines, because `test_parser` returns three. The document states the checked figures, not the plan's.
4. **D22's `inctrack.lua:122-154`** is the `persist()`/`reset()` region. `resume()` is at `:150-182`.
5. **Task 3's premise that "this phase changed all four files" is false.** `state.lua`'s last change is `a11583e`, a Phase 3 commit (WR-01, `array_of` contiguity). Phase 4 changed `inctrack.lua`, `parser.lua` and `ui.lua` only. See the redeploy section below for why this makes the pre-copy verdicts *more* informative rather than less.

## The two reversed claims, and confirmation neither reached the document

`03-02-SUMMARY.md` and `03-03-SUMMARY.md` each open with a SUPERSEDED note; the code review reversed two decisions after they were written. Both were checked against the source, and both are absent from the document in their reversed form:

| Claim as the superseded summary first wrote it | What the source says | Verified |
|---|---|---|
| The boon glyph group must be **non-empty** (`%([^)]*%)+` in spirit — the `+` form) | `parser.lua:269` is `%([^)]*%)`. The group **may be empty**: WR-04 restored it because emptiness separates nothing, the tail plus a non-blank name already tell a boon from a buff, and this matcher has no fallback tier under it. The non-blank name guard at `:271` does the discriminating | `docs/design.md` states "The glyph group may be **empty**" and gives the `()` reason. No sentence in the document requires a non-empty group |
| The validator demands a **non-empty string** via a `full_string` predicate | `full_string` does not exist anywhere in `inctrack/`: `grep -rc full_string inctrack/*.lua` prints 0 for all four files. The predicate is `is_string` (`state.lua:693-695`), and the rule is "what shape is this, never is this informative" — a blank passes | `grep -cF "full_string" docs/design.md` prints **0**. The validator section states the shape-only rule and spends a paragraph on why a blank passes |

A third claim from the same source was also kept out: **`array_of` does not admit a hole.** `state.lua:733-737` demands contiguity from 1 after counting what `pairs()` visited, and the document states that rule and the `{1, 3}` case that motivates it.

## A correction to the context this phase inherited, not work done

`04-CONTEXT.md` and the codebase map's drift list both record that **`README.md` documents a close button and a title bar the addon no longer has**. That did not survive checking:

- `grep -ci "close button" README.md` → **0**
- `grep -ci "close" README.md` → **0** (the word does not appear in the file at all)
- `README.md:87` already reads: *"The window has no title bar; drag it by its body (`/incursion lock` to pin it)."*

Nothing was changed for it and no correction was invented. The README's real staleness was elsewhere — the file tree, the without-chatlogs suite list, the corpus figures, the write policy and the disconnect table — and that is what Task 1 fixed. Recorded here so the milestone audit does not read the unchanged line as an oversight.

---

# The redeploy

## Pre-copy, run **before** anything was written

```
pre-copy DRIFTED: inctrack.lua
pre-copy DRIFTED: parser.lua
pre-copy same: state.lua
pre-copy DRIFTED: ui.lua
```

and the version string the live install held before the overwrite:

```
22:addon.version = '1.1.0';
```

**This is the correct answer, and it is more informative than the plan expected.** The plan predicted four `DRIFTED:` on the premise that Phase 4 changed all four files. It did not: `state.lua` was last changed by `a11583e`, a Phase 3 commit, and the install was byte-identical to the repo at the head of Phase 4. So `state.lua` being unchanged since the last deploy is exactly right, and the three files Phase 4 *did* change are exactly the three that drifted.

The failure signal the plan was watching for — **four** `pre-copy same:` after a phase that changed files, meaning the copy is pointed somewhere that is not the live install — did not occur, and the three `DRIFTED:` verdicts plus the `1.1.0` version string read out of the target are positive evidence that the target is right: a wrong directory could not have held the previous build.

## Post-copy, line-ending insensitive

```
same: inctrack.lua
same: parser.lua
same: state.lua
same: ui.lua
```

Four `same:`, zero `DIFFERS:`. And the deployed build now identifies itself as what was shipped:

```
$ grep -c "1.2.0" ".../Ashita/addons/inctrack/inctrack.lua"
1
22:addon.version = '1.2.0';
```

The comparison is line-ending insensitive (`diff --strip-trailing-cr`) deliberately: the repo enforces LF through `.gitattributes` and the install may hold CRLF, so a byte comparison would report a difference that is not one.

`git status --short` lists **no modified tracked file** at the end of the plan.

---

# Phase 4's five ROADMAP criteria, each tied to what establishes it

| # | Criterion | What establishes it |
|---|---|---|
| 1 | The harness prints a per-line cost figure for a recorded baseline and for the post-change code, and the post-change figure is better | The `cost: the non-Incursion reject path` report block, printed in all three runs above. Quoting run 2: `old shape (Phase 3): 282,995 lines/s, 3.534 us/line` / `new shape (shipped): 1,024,194 lines/s, 0.976 us/line` / `new/old: 3.62x`, beside `recorded baseline (2026-08-29, commit a6a3577, Lua 5.5, Python 3.14.5): 285,562 lines/s, 3.502 us/line -- provenance, not a threshold`. Under `luajit21`, `5.05x` |
| 2 | A non-Incursion line is rejected before any string is allocated: zero `strip_colors`, no `trim`, no timestamp loop unless the line starts with `[` | The same report block's allocation lines: `per colour-free rejected line -- old: 1.00 strip_colors, 5.33 gsub; new: 0.00 strip_colors, 0.00 gsub`, printed in all three runs; plus the named checks 04-01 added to `addon` (143 → 160) and `adaptability` (42 → 119), all green here |
| 3 | A burst of `MUST_SAVE` events performs no `settings.save` inline on the chat thread, and no run data is lost across a simulated unload immediately after such a burst | Named checks in `addon: load, chat, settings, commands`, 190 green — 04-02's marked-then-flushed cases at every site, the not-visible and latched-off cases, the unload-without-a-frame and throttled-unload cases, and the reset and profile-switch cases. 04-02 recorded the negative controls that prove each bites |
| 4 | `shorten()`'s memo cache stops growing at a stated bound, and holds nothing from a previous run after a reset or character switch | Named checks in `ui: helpers, layout contract, render`, 74 green — 04-02's cap, drop, correctness, in-place-clear and identity cases, counted over `pairs` on the live table rather than off a bookkeeping counter — plus the two `addon` checks for the reset and profile-switch paths |
| 5 | `docs/design.md` states what the code does — `AlwaysAutoResize` plus a fixed-width spacer, `NoTitleBar`, the actual stats layout, the boons row and the five run-record fields; `CHANGELOG.md` has a 1.2.0 entry; `addon.version` reads `'1.2.0'` | The ledger above, row by row, each checked against its source. Assertable parts: `grep -c "addon.version = '1.2.0'" inctrack/inctrack.lua` = 1; `grep -c "^## 1.2.0" CHANGELOG.md` = 1 and `grep -c "^## 1" CHANGELOG.md` = 3; `grep -c AlwaysAutoResize docs/design.md` = 2 with `grep -cF "rather than \`AlwaysAutoResize\`"` = 0; `NoTitleBar`, `CONTENT_W`, `elapsed_final`, `points_partial`, `recovered`, `desynced`, `awards_seen`, `version = 2`, `saved_at`, `pending_time`, `render_ok`, `render_off` each ≥ 1; `full_string` = 0; `Seven suites` = 0. And the new harness check pinning the version to the changelog, with its negative control |

**The standing guarantee**, restated and met: the full suite is green against the author's chatlogs at `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs`; **no pre-existing suite's check count fell** (see the four-column table); the generic tier still matches nothing in today's logs (`generic` exactly 1, note `all real lines handled by a specific pattern`); the purity boundary holds — `parser.lua` and `state.lua` gained no Ashita dependency and were not touched by this plan at all; and no instance, boss, mob, objective or difficulty name entered any Lua file. This plan added no line to a Lua file that is not a comment or the version literal.

---

# Milestone hand-off for `/gsd-audit-milestone`

## 1. The three in-game human checks still open

None of them is closed by this phase. The redeploy above is what makes all three performable: the live install now holds the 1.2.0 build.

**A. Phase 2, criterion 4 — the reload clock (FIX-02 on a real host).**
In an Incursion: note the window's clock, `/addon reload inctrack`, stay unloaded about two minutes, reload and read the clock, then wait for the server's next `You have N minutes remaining` line.
*PASS* if the two agree within a minute.
*FAIL* if the clock came back unchanged, or if it jumps down by roughly the downtime when the server's line arrives.

**B. Phase 2, CR-01 — the window frame.**
Same session: no title bar and no close control; not resizable by dragging an edge; the height still auto-fits as content appears and disappears; `/incursion lock` still prevents dragging; `/incursion` still toggles.
*PASS* on all five.
*FAIL* on any title bar, any resize handle, a clipped or padded fixed height, or a per-frame console error mentioning `bad argument #2` or `Begin`.
This one exists because CR-01's fix rests on Ashita's SDK header and a survey of 220 `imgui.Begin(` call sites, not on an observed frame. The compiled binding's type handling cannot be inspected; only a rendered window proves the flags land in slot 3.

**C. Phase 3, D8 (prudence, not a defect) — the repair calls reaching Ashita's GUI manager.**
The repair does `pcall(function () imgui.End(); end)` and `pcall(function () imgui.PopStyleVar(1); end)`, both of which reach Ashita's `GuiManager` through a metatable `__index`. The stub models that shape but cannot execute it.
*PASS* if a provoked render error leaves the window off, prints one line naming `/incursion` as the way back, and the game's frame rate and other addons' windows are unaffected afterwards.
*FAIL* on a second console error in the same frame, or on any other addon's window losing its frame.
Closed by the same in-game session as A and B.

## 2. The four carry-forwards this phase did not take

From `03-03-SUMMARY.md`'s list of nine, Phase 4 took five (the per-frame options table, the unrate-limited `parse error:` line, the cheap-rejection guard and the allocations ahead of it, the memo cache, and the design-doc/layout-comment drift). These four are the milestone's hand-off:

1. **The harness's duplicated wording knowledge.** The reference shapes the over-reach guard re-derives in Python restate what `parser.lua` knows. *Reason not taken:* the duplication is deliberate and load-bearing — a reference derived from the parser would drift with it and agree with it while both were wrong — so removing it would weaken the guard. It is recorded as a maintenance cost to watch, not a defect to fix.
2. **IN-07: integer versus float on the version-1 migration's phase arithmetic.** *Reason not taken:* explicitly deferred by 03-03's hard rules and never re-opened. The `luajit21` run exercises the same dialect question for `array_key` and is green, but the migration path's arithmetic has not been separately pinned.
3. **Capping persisted key and value lengths (`T-03-19`).** Dispositioned **accept** in Phase 3's threat register: server text is used as a table key in the extras map, and the validator checks the key is a string and the value shape-correct, but does not bound either length. *Reason not taken:* out of scope for a correctness milestone. Now also stated in `docs/design.md` so it is a documented decision rather than an omission.
4. **IN-05 (NaN and ±inf admitted by `opt_number`).** *Reason not taken, and this one wants **re-deciding** rather than applying as written:* CR-01 reversed the proportionality argument it rested on. Rejecting a whole live run over a NaN is exactly the trade that was just reversed in favour of accepting a blank string, and the validator's own comments now argue at length that refusing the blob costs the whole run while the server re-announces none of it. Whoever picks this up should re-derive the trade, not implement the finding's text.

## 3. PROC-01…04 — deliberately v2, untouched, and not promised

CI, a linter (luacheck), a versioned release artifact, and a public chatlog fixture. All four are v2 by decision, not by oversight. None was added, and `docs/design.md` and `README.md` were both written so that neither promises any of them.

## 4. The four residuals this milestone accepted, stated

1. **The one-frame write window.** Between the chat line that changes the run and the frame that writes it, there is roughly one frame in which the newest event is not on disk; a hard crash inside it loses that one event. Taken knowingly against a synchronous serialise, JSON encode and disk write on the game thread on every chat line. The unload handler's unconditional write covers every orderly departure.
2. **A coloured chat line still pays `strip_colors`.** The cheap gate declines to judge any line carrying a colour-code marker byte, because a code can sit inside the very needle it searches for. Such a line costs what it always did and never more — the printed figures show 1.00 `strip_colors` and 2.00 `gsub` per coloured rejected line, against 1.00 and 5.00 before.
3. **The mob-list split has no fallback tier (IN-03).** All 469 kill-objective lines across 127 logs split identically either way, so the narrowing changes nothing the server has actually sent; but a comma-only list from a future server would now be drawn as one name rather than two. Knowingly taken, and pinned by `parser` staying exactly 11819.
4. **The style colour stack is deliberately not repaired** after a caught render error. Its only push and pop in the whole file bracket a single ImGui call with no data-driven raise site between them, so nothing can stop between them. The addon suite asserts all three stacks anyway, so if that stops being true the tests say so rather than a guess papering over it.

---

## Decisions Made

- **1.2.0.** No new features, so not 1.3.0; three defects, six hardenings and four cost changes, so not a patch.
- **The changelog speaks in the player's terms**, the same terms the Phase-1 expected failures were written in. No file names, no function names, no line numbers — those belong in the design document and the phase records.
- **The version pin reads both sides out of their real sources** — `addon.version` out of the stubbed host, the newest `##` heading off disk — so neither side is hardcoded in the test and the check cannot pass by agreeing with itself.
- **The pin notes-and-skips on an absent `CHANGELOG.md`**, exactly as the persistence suite does for Ashita's `json.lua`. The addon folder is installable on its own; a changelog that is not beside it says nothing about the addon.
- **`docs/design.md` keeps its seven top-level sections** and is rewritten inside them, so a reader who knows the old document can still find their way. The five new sections land as subsections under Architecture, and Error handling is restructured as four numbered boundaries pointing into them.
- **Every claim carries the file it was checked against.** Where the plan's ledger and the source disagreed, the source won and the disagreement is recorded above.
- **The README's inherited close-button claim was checked before being acted on**, found false, and recorded as a correction to the context rather than as work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 3's expected redeploy verdict was wrong about which files this phase changed**

- **Found during:** Task 3
- **Issue:** The plan states "this phase changed all four files, so `pre-copy DRIFTED:` on all four is the expected answer". `state.lua` was last changed by `a11583e`, a Phase 3 commit; Phase 4 changed `inctrack.lua`, `parser.lua` and `ui.lua` only.
- **Fix:** Recorded the actual four verdicts (3 DRIFTED, 1 same) and the reasoning that makes `pre-copy same: state.lua` the correct answer, rather than treating it as the copy-target-wrong signal. The signal the plan was watching for is *four* `same:` verdicts, which did not occur; three DRIFTED plus a `1.1.0` version string read out of the target is positive evidence the target is right.
- **Files modified:** none — a record correction.
- **Verification:** `git log -1 -- inctrack/state.lua` → `a11583e … fix(03): WR-01 …`; post-copy `same:` on all four.

**2. [Rule 1 - Bug] Ledger row D13's suite arithmetic did not match the harness**

- **Found during:** Task 2
- **Issue:** The plan's D13 says "ten suites, eleven `Result` lines, plus the reject-path cost line". The harness docstring numbers eleven suites (the cost suite is entry 11) and a real run prints twelve `Result` lines, because `test_parser` returns three.
- **Fix:** `docs/design.md` states the checked figures — "Eleven suites, reported as twelve result lines" — as a table with a **Needs** column. The plan's arithmetic was not transcribed. This is the same class of miscount as the open `WINDOWS.md` entry, so it is logged there too.
- **Files modified:** `docs/design.md`
- **Verification:** the twelve `Result` lines are visible in run 2 and run 3 above; `grep -cF "Seven suites" docs/design.md` prints 0.
- **Committed in:** `af2c6f1`

**3. [Rule 3 - Blocking] Four line citations in the plan's ledger no longer point at what they name**

- **Found during:** Task 2
- **Issue:** D7's `ui.lua:394-418`, D11's `inctrack.lua:372-399` and D22's `inctrack.lua:122-154` name regions that do not contain the code described. Acting on them would have meant describing the wrong code.
- **Fix:** Each was found by opening the file — `render` at `ui.lua:440-488`, the `/incursion` re-enable at `inctrack.lua:478-513`, `resume()` at `inctrack.lua:150-182` — and the document was written from what is actually there. Corrected citations are recorded in the ledger above.
- **Files modified:** `docs/design.md`
- **Verification:** the ledger rows above, each stating what the file said when it was opened.
- **Committed in:** `af2c6f1`

---

**Total deviations:** 3 auto-fixed (3 bugs in the plan's own statements about the source; 0 in the code).
**Impact on plan:** None on scope. All three are the plan's `hard_rules` #1 doing exactly what it was written to do — the source won, and the disagreement is recorded. No code behaviour changed as a result.

## Issues Encountered

None. The plan's two negative controls both behaved:

- **The version pin, wrong version.** With the newest changelog heading temporarily set to `## 9.9.9`, `addon` went `FAILED (1)` with *"the addon reports version '1.2.0' and the newest changelog heading names '9.9.9', so the build and the record of what is in it disagree"*, the run exited 1, and **nothing else moved**. Restored, green.
- **The version pin, absent changelog.** With `CHANGELOG.md` moved aside, `addon` reported 189 checks `ok` with the note *"skipped: CHANGELOG.md not found beside the addon folder"* and the run exited 0 — the skip branch works and is not a silent pass of the real check, since the check count visibly drops by one.

Two untracked paths remain in the working tree — `.gsd/` and `.claude/settings.local.json`. Both pre-date this plan (they were present in `git status` before the first task) and both are GSD/editor tooling state rather than anything this plan produced. Left alone under the scope fence; adding `.gitignore` entries would be a change outside this plan's `files_modified` and outside a correctness milestone.

## User Setup Required

None — no external service configuration required. The two 127-log runs need the author's private chatlog directory and Ashita's `json.lua`; both were present (127 logs, `addons/libs/json.lua` found, `persistence` running at 40 checks rather than skipping), and the live install directory existed and was writable.

## Next Phase Readiness

- **Phase 4 is complete.** All six requirements closed: PERF-01/04 (04-01), PERF-02/03 (04-02), DOC-01/02 (04-03).
- **v1.2.0 is the last phase of the milestone.** `/gsd-audit-milestone` runs next, and everything it needs is in the hand-off above: the three in-game checks with pass and fail conditions, the four carry-forwards with reasons, PROC-01…04 named as deliberately v2, and the four accepted residuals.
- **The standing guarantee holds and has risen.** No pre-existing suite's count fell in any of the three plans, `parser` is still exactly 11819 and `generic` exactly 1, zero known defects, green on both backends against 127 logs.
- **The live install holds the shipped build.** `1.2.0`, all four files verified line-ending-insensitively identical to the repo, with what the install held before the overwrite recorded first.
- **Nothing from a prior phase was undone.** Phase 2's `imgui.Begin(name, nil, flags)` and the strictly-positional stub, schema `version = 2` and its v1 migration, Phase 3's `render_ok`/`render_off` latches, WR-02's deliberate non-clearing of `override`, WR-03's closure-wrapped repair calls, WR-04's empty-glyph allowance, WR-05's `resume()` and its finished-run exemption, the validator's `is_string` rule, the three parser tightenings, 04-01's gate and its colour fall-through, and 04-02's deferred write and bounded cache are all in place, all still asserted, and all now described in `docs/design.md`.

---
*Phase: 04-cost-and-record*
*Completed: 2026-08-29*

## Self-Check: PASSED

All six modified files and the SUMMARY exist on disk; both task commits (`d7e881e`, `af2c6f1`) are present in `git log`.

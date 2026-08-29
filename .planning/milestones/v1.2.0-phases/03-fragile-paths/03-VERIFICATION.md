---
phase: 03-fragile-paths
verified: 2026-08-29T11:20:00Z
status: human_needed
score: 5/5 roadmap criteria verified; 6/6 requirements satisfied
behavior_unverified: 0
overrides_applied: 0
overrides: []
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
deferred: []
behavior_unverified_items: []
coincidental_reliance_items: []
human_verification:

  - test: "In game, with the live install at ...\\Ashita\\addons\\inctrack\\, force a
      render error (e.g. /addon reload after hand-editing the settings session blob
      to put a boolean in objective.mobs) and watch the window and the rest of the
      HUD landscape for the next few seconds."
    expected: "One chat line naming /incursion; the inctrack window gone; every other
      addon's window still drawn correctly on the following frames; /incursion brings
      inctrack back."
    why_human: "Coverage item D8, raised by the executor itself in 03-01-SUMMARY.md and
      still open. pcall(function () imgui.End(); end) reaches Ashita's GuiManager
      through a metatable __index, not a Lua wrapper. The harness models that shape
      (arm_lookup_fault) but cannot execute it, so whether the real binding accepts the
      repair calls and actually rebalances a real ImGui stack is unprovable from the
      stub by construction. ROADMAP criterion 1 is deliberately written against the
      stub, so this is prudence beyond the contract, not a criterion gap. Carried
      alongside the two in-game checks still open from Phase 2."

  - test: "Decide whether 03-02-SUMMARY.md and 03-03-SUMMARY.md should be amended with a
      post-review note, or left as the pre-review record with 03-REVIEW.md as the
      correction."
    expected: "A stated choice. If amended: 03-02-SUMMARY.md stops describing a
      non-empty glyph group as shipped, and 03-03-SUMMARY.md stops listing full_string
      as a validator predicate and stops recording 'next_boss.name and every mob-list
      entry must be a non-empty string' as a live key decision."
    why_human: "A judgement about how this project keeps its record, not a testable
      behaviour. Both passages are verifiably false about the shipped code (see WARNING
      W-01 below); both were reversed by review findings WR-04 and CR-01 whose reasoning
      is recorded in 03-REVIEW.md and in the code's own comments. Phase 4 carries DOC-01
      and DOC-02 and will read these files."
audit_acknowledged:
  milestone: v1.2.0
  at: 2026-08-29
  status: human_needed
---

# Phase 3: Fragile Paths Verification Report

**Phase Goal:** The window cannot take the frame down, and neither the parser nor
the restore path can put on screen something the server never said.
**Verified:** 2026-08-29
**Status:** human_needed — all five criteria verified in code; two items want a human
**Re-verification:** No — initial verification

## Method

SUMMARY.md claims were not taken as evidence. Every verdict below rests on one of:

- a run of `test/run_tests.py` against the author's 127 logs, performed by this
  verifier, on both backends;

- a **mutation** performed in a throwaway `git clone --local` at
  `…\scratchpad\mut`, confirming the suite turns red when the fix is reverted;

- a direct probe driving real server text through parser → state → serialise →
  restore → `ui.render` against the ImGui recorder, reading what is actually drawn.

The real checkout was never modified: `git status --porcelain` at
`C:\Users\badr\inctrack` reports only the untracked `.gsd/` and
`.claude/settings.local.json`, before and after.

## Suite runs (performed by this verifier)

### Default backend — `python test/run_tests.py "C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs"`

```
  lua: Lua 5.5
  2945648 chat lines from 127 logs, character Godwen

  parser: structural lines all parse            11819 checks  ok
  parser: generic tier matches nothing today        1 checks  ok
  parser: tightened patterns keep every line whole      1 checks  ok
  state: run reconstruction                       888 checks  ok
  state: objectives, bonus, recovery              105 checks  ok
  adaptability: unseen content still tracked       42 checks  ok
  disconnect: stale progress is not trusted        23 checks  ok
  timers: countdown, linger, staleness             31 checks  ok
  persistence: json round trip                     40 checks  ok
  ui: helpers, layout contract, render             65 checks  ok
  addon: load, chat, settings, commands           143 checks  ok

  0 known defects
PASS
```

### `INCTRACK_LUA=luajit21` — the dialect Ashita embeds

```
  lua: LuaJIT 2.1.1774896198 (INCTRACK_LUA)
  2945659 chat lines from 127 logs, character Godwen
  … identical check counts, every suite ok …
PASS
```

Total 13,158 checks. The two runs differ only in line count (2,945,648 vs
2,945,659) because the author kept playing between them; the log count (127) and
every check count are identical.

**The persistence suite ran — it was not skipped.** 40 checks, against
`C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\json.lua` (confirmed
present, 10,037 bytes). This is what the code review's own run could not reach, so
the round trip through Ashita's real decoder is now first-hand evidence rather
than an open question.

### Per-suite floor

| Suite | Floor | Observed | |
|---|---|---|---|
| parser: structural | **exactly 11819** | 11819 | ✓ pin held |
| parser: generic | **exactly 1** | 1 | ✓ pin held |
| parser: tightened | 1 | 1 | ✓ |
| state: run reconstruction (replay) | 888 | 888 | ✓ |
| state: objectives, bonus, recovery | 105 | 105 | ✓ |
| adaptability | 42 | 42 | ✓ |
| disconnect | 23 | 23 | ✓ |
| timers | 31 | 31 | ✓ |
| persistence | 40 | 40 | ✓ |
| ui | 65 | 65 | ✓ |
| addon | 143 | 143 | ✓ |

Nothing fell, on either backend. The Phase-1 and Phase-2 floors are also clear by
inspection (state 38→53→105, timers 21→25→31, persistence 25→31→40, ui 55→65,
addon 83→143).

## Goal Achievement — the five ROADMAP criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | A run record that errors mid-render leaves the ImGui stack balanced; failure reported once; window disables itself | ✓ VERIFIED | Mutation M1/M2/M3 + 29 addon checks |
| 2 | Boss name containing " at " parses whole with the location separate; a comma-bearing mob name yields one mob | ✓ VERIFIED | Mutation M5/M6 + corpus probe P2 |
| 3 | An ordinary buff line is never claimed as a boon; suite 4's boon assertions still pass | ✓ VERIFIED | Mutation M7/M8/M9 + corpus pins |
| 4 | A structurally malformed saved session is discarded whole; `restore()` falsy, no run behind | ✓ VERIFIED | Mutation M10/M13 + 40 persistence checks |
| 5 | `/incursion reset` within 30s of a remaining-minutes line does not seed the next run's clock | ✓ VERIFIED | Mutation M11 + explicit `pending_time is None` assertion |

**Score: 5/5.**

### Criterion 1 — the window cannot take the frame down

`inctrack/inctrack.lua:281` calls `pcall(ui.render, …)`. The repair at `:340-343`
is conditional on `render_ok` — the latch that says the render shape has run end
to end on this host — and both repair calls wrap the *lookup* as well as the call
(`pcall(function () imgui.End(); end)`), which is WR-03's fix.

Mutation evidence, each run in the scratch clone:

| Mutation | Result |
|---|---|
| **M1** — `ui.render` called unprotected | addon suite **FAILED (24)**. Both named triggers escape: `invalid value (boolean) at index 1 in table for 'concat'`, and `TextColored refused Vault of 100% Ruin`. Balance `{window: 1, style_var: 1, style_color: 0}`. |
| **M2** — stack repair removed | **FAILED (2)** — "the ImGui stacks were left unbalanced after a render error" for both triggers |
| **M3** — `pcall(imgui.End)` instead of `pcall(function () … end)` | **FAILED (6)** — the lookup raise seen escaping `d3d_present`, the window left switched on, the recovery line swallowed |
| **M4** — WR-02 reverted (`override` cleared, fixed wording) | **FAILED (3)** — including "the chat line and the screen disagree" |

The clean run asserts `{window: 0, style_var: 0, style_color: 0}` after each
trigger, exactly one chat line naming `/incursion`, sixty subsequent frames with
**no ImGui calls and no chat**, chat still driving the run while the HUD is off,
and the window drawing again on the very next frame after `/incursion`. Trigger C
(a raise from `PushStyleVar`, before `Begin`) proves the repair emits nothing when
nothing is owed.

`ui.lua` was not edited: `git diff b2d30cc..HEAD -- inctrack/ui.lua` is **0 bytes**.
The render path was made un-crashable entirely from outside it.

### Criterion 2 — the parser cannot invent a name

`parser.lua:166` / `:178` / `:214` try the greedy parenthesised form first
(`(.*) at (%(.+%))`), so the split falls on the **last** ` at (`; the 1.1.0 lazy
form is kept underneath at all three sites, so nothing that parses today can stop
parsing. `split_mobs` (`:45-60`) scans for `', '` as plain text.

| Mutation | Result |
|---|---|
| **M5** — all three ` at ` matchers reverted to lazy-first | adaptability **FAILED (6)**: name `'Warden'`, loc `'the Ninth Gate at (K-7) (Map #4)'` at all three sites |
| **M6** — mob list split on any comma | adaptability **FAILED (3)**: `['Kalamainu', 'Prime', 'Cave Bat']` |

The fallback is genuinely exercised: `New Objective: Defeat Gate Sentry at the
northern span!` still parses to name `Gate Sentry`, loc `the northern span`.

### Criterion 3 — a buff is not a boon

`parser.lua:269` requires `(%S+) gains the effect of (.-) %([^)]*%): (.+)$` plus a
non-blank trimmed name.

| Mutation | Result |
|---|---|
| **M7** — non-blank-name guard removed | adaptability **FAILED (1)**: "a boon with no name was listed" |
| **M8** — `[^)]` relaxed to lazy `.-` | **FAILED (1)**: the group stepped over a `)`, name became `'Aura'` |
| **M9** — WR-04 reverted (`[^)]+`) | **FAILED (1)**: the empty-glyph boon dropped |

`gains the effect of Protect.` and `Warding Aura (Signet) Attack+5` both produce
`nil`. Suite 4's existing boon assertions all pass (adaptability 42, unmoved).

### Criterion 4 — the restore path cannot half-apply

`valid_session` (`state.lua:797`) runs after the version gate and before the first
arithmetic. `array_of` (`:707`) counts what `pairs()` visits and then demands
`t[1..n]` — WR-01's contiguity fix.

| Mutation | Result |
|---|---|
| **M10** — `valid_session` never consulted | suite **crashes**: `state.lua:873: attempt to add a 'string' with a 'number'`, from `restore()` inside the profile-switch callback — the exact unprotected path the criterion exists to close. A holed boons list is also accepted. |
| **M13** — contiguity loop removed | state **FAILED (2)** + persistence **FAILED (1)**, the last through Ashita's real `json.lua` decoding `[{…}, null, {…}]` |
| **M14** — WR-05's discard message removed | addon **FAILED (2)** |
| **M15** — WR-05's finished-run exemption removed | addon **FAILED (1)** — false alarm after every completed run |

The clean suite runs 27 one-field-broken rejection cases, each asserting all three
of *falsy return*, *no run left behind*, *nothing raised* — including both triggers
the criterion names (`kills_max = "twenty"`, `objective.mobs[2] = 5`) — behind a
control proving a well-formed blob still restores with objective, boss, bonus,
2 boons, points and phase intact.

### Criterion 5 — a held sync does not leak across a reset

`state.lua:93`: `self.pending_time = nil` in `State:reset()`.

| Mutation | Result |
|---|---|
| **M11** — line removed | timers **FAILED (3)** + addon **FAILED (2)** |

The suite asserts the criterion's literal wording (`s7["pending_time"] is None`
after `reset()`), then the consequence (`time_left` and `time_sync` both `None` on
the next run), then drives the same thing through `/incursion reset` in the addon
suite, and pins the *other* direction — without the reset the same sequence must
still adopt the sync, so the fix cannot have removed the hold.

## The over-reach pins are load-bearing — proven, not assumed

The phase's whole safety argument rests on three corpus guards. Each was mutated
to confirm it actually fires.

| Probe | Mutation | Guard that fired |
|---|---|---|
| **P1** | `Phase #` pattern broken so real lines fall to the generic tier | `parser: generic tier matches nothing today` → **7899 FAILURES**. Notably `parser: structural` stayed 11819 ok — a fall-through still parses. |
| **P2** | `split_mobs` silently drops mobs past the second | `parser: tightened patterns keep every line whole` → **451 FAILURES** against real logs (`['Yagudo Conquistador', 'Yagudo Lutenist'] vs [… 'Yagudo Prior', 'Yagudo Zealot'] — Godwen_2026.05.24.log:15819`), plus ui/persistence/state |
| **P3** | boon tail over-tightened (`(.+)$` → `(%a+)$`) — the no-fallback path WR-04 was about | `parser: structural lines all parse` → **351 FAILURES**, and `boon` disappears from the observed event-kind list |

The three are complementary and all three are live: pin 2 catches a regression the
generic tier absorbs, pin 1 catches a line that stops parsing outright, and the
new re-derivation suite catches a line that still parses but is split wrongly. The
"either … or" framing in `03-CONTEXT.md` is accurate as written.

## The CR-01 judgement — assessed, with direct evidence

The reviewer proposed adding a blank-name guard to the boss matchers. The
executor declined that half and instead removed `full_string` entirely in favour
of `is_string` at all four blank-string sites, on the rule that *the validator
answers "what shape is this", never "is this informative"*.

**Is the judgement sound?** Yes.

- **The regression was real and severe.** Mutation **M12b** (`is_string` demanding
  non-empty again) turns **exactly 12** state checks red — matching the review's
  claim precisely — including "a run the addon had just written itself was refused
  on reload because one server line named no boss". One degenerate line converting
  every later reload into total loss of a live run is strictly worse than the
  fragility HARD-05 was written to close.

- **The asymmetry argument holds.** The boon matcher is the only one in the file
  with no `Incursion [` / `New Objective:` / `(Boss:` anchor, so a blank name there
  is evidence the match is not a boon at all — a *disambiguator*. The boss forms
  are anchored on fixed server wording, so a match is certainly a boss line, and
  the location is information the server did send.

**Did it leave a gap — can a blank now render as a confident-looking wrong value?**
No. Probed directly against the ImGui recorder, driving real server text end to end:

| Input | Drawn |
|---|---|
| `(Boss:  at (J-9))` | `TextColored dim 'Next: '` · `TextColored text ''` · `TextColored dim '(J-9)'` |
| `New Objective: Defeat  at (J-9)!` | `ProgressBar 1.0 'BOSS    (J-9)'` |
| `Incursion [] Begins! (Normal)` | `TextColored instance ''` · `TextColored dim '. Normal'` |

In every case the blank draws **nothing** and the part the server did send — the
location, the difficulty — survives. Nothing is fabricated. Worth recording
precisely: the `or '?'` and `or 'Incursion'` fallbacks in `ui.lua:136` and `:169`
were written for `nil` and do **not** fire on `''` (empty string is truthy in
Lua), so a blank yields an empty row rather than a `?` placeholder. That direction
is *less* invention, not more, and is exactly what the validator's own comment
claims (`imgui.TextColored('') draws nothing at all`). It is a cosmetic
nicety at most, and squarely Phase 4's territory if anyone wants it.

## Standing guarantee (whole milestone)

| Guarantee | Status | Evidence |
|---|---|---|
| Full suite green against the author's chatlogs, no pre-existing count fallen | ✓ | Both backends, table above |
| Suite 2 holds: no generic-tier pattern matches anything | ✓ | 1 check, ok, both backends |
| Purity: `parser.lua` and `state.lua` gain no Ashita dependency | ✓ | `grep -nE "require\(\|ashita\|AshitaCore\|imgui"` over both files returns **only comments** |
| No instance, boss, mob, objective or difficulty name in any Lua file | ✓ (see ℹ️) | 492 added Lua lines scanned; sole hit is `'Incursion [] Begins! (Normal)'` in a `state.lua` comment |

ℹ️ `(Normal)` in that comment is an illustrative server line, not data — no
behaviour reads it, and the same convention pre-dates the phase (`b2d30cc`'s
`parser.lua:65` and `:81` already carry `(Normal)`). Not a violation.

**Live install parity:** all four files at
`C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` are byte-identical to
the repo (`cmp` clean), so the in-game item below can be run against this build.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `inctrack/inctrack.lua` | `pcall` containment, conditional repair, report-once, recovery | ✓ VERIFIED | 188 lines changed; every branch mutation-pinned |
| `inctrack/parser.lua` | three tightenings, HARD-02 with a fallback | ✓ VERIFIED | 85 lines changed; three corpus guards proven live |
| `inctrack/state.lua` | structural validator, defensive copy, `reset()` clears `pending_time` | ✓ VERIFIED | 245 lines changed; `full_string` correctly absent |
| `inctrack/ui.lua` | **unchanged** | ✓ VERIFIED | `git diff b2d30cc..HEAD` = 0 bytes |
| `test/run_tests.py` | checks for all six HARD items | ✓ VERIFIED | +1345 lines; every one mutation-pinned |
| `test/stubs.py` | fault injector, off by default | ✓ VERIFIED | +187 lines; `arm_fault`/`arm_lookup_fault`/`__imgui_stub` appear nowhere under `inctrack/` |

## Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `d3d_present` | `ui.render` | `pcall(ui.render, …)` | ✓ WIRED (M1 red without it) |
| `render_off` | early return, `/incursion`, `reset()`, profile switch | all four sites | ✓ WIRED (M1, M4 red) |
| `render_ok` latch | conditional repair | `if incursion.render_ok then` | ✓ WIRED (trigger C green) |
| fault injector | percent-sign trigger | `arm_fault('TextColored', contains=…)` | ✓ WIRED, default-off (ui 65 unmoved) |
| `valid_session` | `restore()` before first arithmetic | `state.lua:830` | ✓ WIRED (M10 raises without it) |
| `array_of` contiguity | `#`-driven boon/mob loops | `state.lua:917-922`, `:845-851` | ✓ WIRED (M13 red) |
| `State:reset()` | shell `reset(quiet)` + profile switch | `pending_time = nil` | ✓ WIRED (M11 red) |
| tightened-pattern suite | 127-log corpus | Python re-derivation of every split | ✓ WIRED (P2: 451 real failures) |
| persistence suite | Ashita's real `json.lua` | `INCURSION_ASHITA_LIBS` | ✓ WIRED (40 checks, ran) |

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| HARD-01 | Error in `ui.render` cannot unbalance the ImGui stack or repeat per frame | ✓ SATISFIED | M1/M2/M3, 29 addon checks, balance `{0,0,0}` |
| HARD-02 | Boss name containing " at " parsed correctly | ✓ SATISFIED | M5, fallback preserved |
| HARD-03 | Comma-bearing mob name not split | ✓ SATISFIED | M6, P2 |
| HARD-04 | Boon matcher matches only the `(<glyph>): <stats>` form | ✓ SATISFIED | M7/M8, P3 |
| HARD-05 | Restored session validated structurally; malformed discarded whole | ✓ SATISFIED | M10/M13, 27 rejection cases, persistence 40 |
| HARD-06 | `reset()` clears `pending_time` | ✓ SATISFIED | M11, literal assertion |

No orphaned requirements: `REQUIREMENTS.md` maps exactly HARD-01…06 to Phase 3,
and all six are claimed by the three plans.

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|---|---|---|---|
| `inctrack/*.lua`, `test/*.py` | `TBD` / `FIXME` / `XXX` / `TODO` / `HACK` / `PLACEHOLDER` | — | **None found.** Completion is auditable. |
| `state.lua:657` | `opt_table` defined and never used | ℹ️ Info | Dead line, already recorded as IN-01, out of the review's fix scope |

## Findings

### ⚠️ W-01 (WARNING) — two SUMMARY files describe decisions the review reversed

Both are verifiably false about the shipped code. Neither affects behaviour; both
affect the record Phase 4 (DOC-01/DOC-02) will read.

**`03-02-SUMMARY.md`** — line 23 records "a boon tail requiring a **non-empty**
glyph group"; line 509 prints the shipped pattern as `%([^)]+%)`; the coverage
entry at line 139 cites a passing check named *"a line with an empty glyph group
was listed as a boon"*. `parser.lua:269` ships `%([^)]*%)`, and the check now
asserts the **opposite** — that an empty glyph group *is* a boon (WR-04, `51f5cb5`).
Mutation M9 confirms the current assertion.

**`03-03-SUMMARY.md`** — lines 70, 293 and 653 list `full_string` among the
validator's predicates, and the key-decision at line 75 reads "next_boss.name and
every mob-list entry must be a **non-empty** string; a blank name is a row the
window would draw empty". `grep -n full_string inctrack/state.lua` returns
**nothing**: CR-01 (`e07126b`) removed it at all four sites, and the surviving
`is_string` comment argues the reverse position at length.

Both reversals are correct, and both are properly reasoned in `03-REVIEW.md`
(committed after the summaries, at `6bdf0b0`) and in the code's own comments — so
the phase record *taken as a whole* is consistent. Read alone, each SUMMARY
misstates the shipped code on the single most contested decision of the phase.
A short "superseded by 03-REVIEW.md" note at each site would close it.

### ℹ️ I-01 — 03-02-PLAN's must-have truth was deliberately superseded

`03-02-PLAN.md` frontmatter asserts *"…and neither does one whose glyph group is
empty or whose name is blank"*. The empty-glyph half was reversed by WR-04 and is
now asserted the other way. This is an intentional, reviewed deviation and **not a
gap**: the ROADMAP contract (criterion 3) requires only that *"a line without the
`(<glyph>): <stats>` tail produces no boon event"*, and `REQUIREMENTS.md` HARD-04
requires only that the matcher match *"the `(<glyph>): <stats>` form"* — an empty
glyph group is still that form. Recorded here so a future reader does not
re-derive it. No override entry is needed, since no ROADMAP criterion failed.

### ℹ️ I-02 — `right_text` decision was made, as the phase required

Accepted as intended behaviour, recorded at `03-03-SUMMARY.md:611-639` with three
supporting arguments and the two existing assertions that pin it
(`run_tests.py:2646-2654` and the `WINDOW_FINISHED` snapshot). Not counted as a
seventh fragility, not deferred to Phase 4. This discharges the obligation
`03-CONTEXT.md` carried in from Phase 1.

## Human Verification Required

### 1. In game: the repair against Ashita's real ImGui binding (coverage item D8)

**Test:** With the live install (byte-identical to this build, verified), provoke a
render error and watch the next few seconds.
**Expected:** One chat line naming `/incursion`; the inctrack window gone; **every
other addon's window still drawn correctly**; `/incursion` brings it back.
**Why human:** `pcall(function () imgui.End(); end)` reaches Ashita's GuiManager
through a metatable `__index`. The harness models that shape and can make the
lookup raise, but cannot execute the real binding. ROADMAP criterion 1 is written
against the stub deliberately — this is prudence beyond the contract, raised by the
executor itself, and joins the two in-game checks still open from Phase 2.

### 2. A decision: amend the two SUMMARYs, or leave them

**Test:** Choose whether W-01's two passages get a "superseded by 03-REVIEW.md"
note.
**Expected:** A stated choice, recorded.
**Why human:** How this project keeps its record is a judgement, not a testable
behaviour. Both statements are false about the code; both reversals are correct and
documented elsewhere.

## Gaps Summary

**None.** All five ROADMAP success criteria and all six HARD requirements are
verified in the codebase by executed evidence, and each was confirmed load-bearing
by reverting it in a scratch clone and watching the suite go red. The three
over-reach guards were each shown to fire against the author's real logs. The two
pins the phase treats as non-negotiable read **exactly 11819** and **exactly 1** on
both backends, and `ui.lua` is byte-identical to `b2d30cc` — the render path was
made un-crashable entirely from outside the file that draws.

The status is `human_needed` rather than `passed` for two narrow reasons, neither
of which is a defect in the delivered code: one in-game confirmation the harness
cannot reach by construction (D8, carried forward by the executor itself), and one
record-keeping decision (W-01). Nothing here blocks Phase 4.

---

_Verified: 2026-08-29_
_Verifier: Claude (gsd-verifier)_
_Mutations run: 16 (M1–M15, M12b) + 3 corpus over-reach probes (P1–P3)_

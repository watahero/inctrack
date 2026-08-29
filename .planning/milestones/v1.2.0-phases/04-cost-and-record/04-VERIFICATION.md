---
phase: 04-cost-and-record
verified: 2026-08-29T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
method: >
  Goal-backward. Every figure below was produced by the verifier in its own
  process, in the main checkout for the suite runs and in a throwaway
  `git clone --local` for every mutation. The real checkout was never modified
  (`git status --porcelain` clean before and after). Behavioural claims were
  re-derived with verifier-authored probes driving the shipped handlers, not by
  re-reading the harness's own checks.
findings:

  - id: WARN-01
    severity: warning
    title: "Criterion 2's 'zero strip_colors' holds for colour-free lines only"
    detail: >
      A non-Incursion line that carries an Ashita colour code still pays 1.00
      strip_colors and 1.00 gsub (measured, both backends). This is deliberate
      and correctness-mandated -- CR-01 established that a marker byte can sit
      inside a needle, so the gate declines to judge a coloured line -- but the
      roadmap criterion is written unconditionally and the harness asserts zero
      only over REJECT_FREE. Real FFXI chat is heavily coloured, so this is the
      common case in game, not the edge case.
    decision_requested: >
      Accept the narrowing (an override entry), or restate the criterion as
      "zero for a colour-free line; strictly cheaper for a coloured one".

  - id: WARN-02
    severity: warning
    title: "CHANGELOG 1.2.0 says a line the addon ignores 'costs nothing'"
    detail: >
      Measured, an ignored colour-free line still costs up to ten string.find
      searches, and an ignored coloured line costs a strip_colors and a gsub.
      Already logged as IN-03 in 04-REVIEW-FIX.md and explicitly left for a
      deliberate decision. Independently confirmed here as an overclaim, and it
      is the one user-facing sentence in the milestone record that overstates a
      real and substantial improvement.
    decision_requested: >
      Reword to what is measured (e.g. "is turned away before anything is built
      for it"), or accept the shorthand.

  - id: INFO-01
    severity: info
    title: "coloured() in run_tests.py is the last surviving copy of the corrected premise"
    detail: >
      Zero call sites (verified by grep), so it cannot cause the defect. Its
      body and docstring still encode the two-marker premise CR-01 corrected
      (`"\x1e" in line or "\x1f" in line`). Matches the IN-01 disposition.

  - id: INFO-02
    severity: info
    title: "ui.lua:12-13 claims no content name appears in the file, directly above six"
    detail: >
      Pre-existing and byte-identical to the pre-phase state (git show
      2ef924c). Phase 4 appended the numbered row list below the mockup and did
      not touch the sentence or the mockup. Read as "no content name is
      hardcoded in the drawing logic" the sentence is true; read literally it is
      not. Not a Phase 4 regression.

  - id: INFO-03
    severity: info
    title: "reset() and the /incursion lock|auto paths call settings.save() unprotected"
    detail: >
      Surfaced by a verifier probe: a persistent save fault makes
      `/incursion reset` raise out of the command handler. Confirmed
      pre-existing at Phase 3's final commit 2ef924c and unchanged by this
      phase; outside CR-02's scope, which was persist() inside d3d_present.
      Same class as CR-02 pointed at the command path rather than the frame.
human_verification:

  - test: "In game: /addon reload inctrack mid-run, then wait for the next 'You have N minutes remaining' line."
    expected: "The instance clock agrees with the server's line rather than being optimistic by the downtime."
    why_human: "Carried forward from Phase 2. Requires a live server sending the time line across a real unload."
    origin: "Phase 2 (FIX-02)"

  - test: "In game: confirm the window draws with no title bar and no close control, and that /incursion dismisses it."
    expected: "No close affordance is present; /incursion is the dismiss."
    why_human: "Carried forward from Phase 2. Visual appearance on a real ImGui host."
    origin: "Phase 2 (FIX-03)"

  - test: "In game: force a render error and confirm the ImGui stack repair does not raise a second time (the D8 imgui.End metatable lookup)."
    expected: "The window disables itself, says so once, and the frame completes."
    why_human: "Carried forward from Phase 3. The stub cannot reproduce Ashita's imgui metatable lookup semantics."
    origin: "Phase 3 (HARD-01, D8)"

  - test: "In game: confirm a real coloured Incursion line still starts a run -- e.g. that the 'Begins!' line reaches the window when the client has colour codes in it."
    expected: "The run starts. The gate declined to judge the coloured line, strip_colors removed all three marker bytes, and parse matched."
    why_human: >
      NEW this phase, and structural: the colour fall-through has ZERO corpus
      backing. Ashita's log writer strips 0x1E/0x1F/0x7F on the way to disk, so
      all 2,951,129 recorded lines across 127 logs carry none of the three and
      no survey over them could ever exercise this path. The gate/stub coupling
      is verified against the host's source
      (addons/libs/sugar/string.lua, string_mt.strip_colors) and against
      synthetic fixtures, both of which the verifier confirmed -- but never
      against observed traffic. This is the silent-permanent-false-negative
      class defect CR-01 fixed; a regression here is invisible in chat.
    origin: "Phase 4 (CR-01)"
audit_acknowledged:
  milestone: v1.2.0
  at: 2026-08-29
  status: human_needed
---

# Phase 4: Cost and Record — Verification Report

**Phase Goal:** A chat line the addon does not care about costs measurably less
than it did, saving no longer blocks the chat thread, and the project's own
documents describe the addon that actually ships.

**Verified:** 2026-08-29
**Status:** human_needed — all five criteria verified in the codebase; four
in-game checks (three carried forward, one new) cannot be closed programmatically.
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | The harness prints a per-line cost figure for a recorded pre-change baseline and for the post-change code, and the post-change figure is lower | ✓ VERIFIED | Printed every run. Lua 5.5: old 286,858 lines/s / 3.486 us; new 1,013,369 lines/s / 0.987 us; ratio 3.53x. LuaJIT 2.1: 583,601 → 2,807,028; 4.81x. Recorded baseline 288,437 lines/s / 3.467 us, labelled "provenance, not a threshold". |
| 2 | A non-Incursion line is rejected before any string is allocated: zero `strip_colors`, `trim` does not run, the timestamp loop does not run unless the line starts with `[` | ✓ VERIFIED (scope note — see WARN-01) | Verifier probe: 4 irrelevant lines → **0 strip_colors, 0 gsub**. A *stamped* irrelevant line → **0 gsub**. Loop gated on `s:byte(1) == LBRACKET` (parser.lua:469). Coloured non-Incursion lines still cost 1.00/1.00 by correctness-mandated design. |
| 3 | A burst of `MUST_SAVE` events performs no inline `settings.save` on the chat thread — writes happen from the per-frame flush — and no run data is lost across a simulated unload immediately after such a burst | ✓ VERIFIED | Verifier probe: 17-event burst → `saves == 0`, `save_attempts == 0` on the chat thread; **1** save after one `d3d_present`. Unload with **no frame in between** → 1 save, blob decodes to `phase == 8`, instance intact. **No data lost.** |
| 4 | `shorten()`'s memo cache stops growing at a stated bound, and holds nothing from a previous run after a reset or character switch | ✓ VERIFIED | Verifier probe, measured on the live table via upvalue reflection: cap 64, **peak 64 over 2000 distinct strings**, drops observed, correctness preserved after eviction (`Acc+7 STP+7`). Cache 2→**0** across `/incursion reset`; 3→**0** across profile switch. |
| 5 | `docs/design.md` states what the code does; `CHANGELOG.md` has a 1.2.0 entry; `addon.version` reads `'1.2.0'` | ✓ VERIFIED | `addon.version = '1.2.0'` (inctrack.lua:22). CHANGELOG 1.2.0 dated 2026-08-29, all defects named in user terms including CR-02's new message. design.md spot-checks below all hold. Both known traps avoided. |

**Score: 5/5 truths verified** (0 present-but-behaviour-unverified — every
behaviour-dependent truth above was exercised by a verifier-authored probe, not
inferred from symbol presence).

---

## The Two Criticals — verified at the source, not via the suite

### CR-01: the colour-marker fall-through

**The host's real marker set, read directly:**

`C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\sugar\string.lua:1045-1047`

```lua
string_mt.strip_colors = function (self)
    return (self:gsub('[' .. string.char(0x1E, 0x1F, 0x7F) .. '].', ''));
end
```

Three marker bytes, one gsub, character class. (The installed copy is at
`:1045-1047`, not the `:1044-1046` the review cited — the fix report's own
correction is accurate.)

**All three carriers now agree:**

| Carrier | Location | Marker set | gsubs | Status |
|---|---|---|---|---|
| The gate | `parser.lua` `function parser.relevant` | `\30`, `\31`, `\127` | n/a (3 plain finds) | ✓ superset of the host |
| The stub | `test/stubs.py` `function string.strip_colors` | `[\30\31\127].` | **1** | ✓ byte-for-byte the host's shape |
| The safety pin | `run_tests.py`, `for marker, label in ((CC_A,...),(CC_B,...),(CC_C,...))` | all three | n/a | ✓ once per marker |

**A `\127`-hidden needle is genuinely accepted.** The pin is self-checking: it
first asserts the fixture actually hides the needle (`all(needle not in hidden
...)`), so the check below it cannot pass with the fall-through removed. This is
what the old single-marker pin could not do.

**Mutation kills (throwaway clone):**

| Mutation | Result |
|---|---|
| Drop the `\127` search from the gate | **FAIL** — `addon` suite: *"a 0x7F colour code landing inside one of the gate's needles lost the line that starts a run"*. The 0x1E and 0x1F pins stayed green — the discrimination the old pin lacked. `record` suite additionally failed twice: *"parser.lua states the gate's cost as ten … and it is 9 searches — 2 for the colour markers, then 7 needles"*, same for `docs/design.md`. |
| Restore the stub to the 2-marker, 2-gsub form (gate left correct) | **FAIL** — the same 0x7F pin fires, and the inflated figures reappear at exactly the documented values: colour-free 1.00 strip / **5.33** gsub, coloured 1.00 / **5.00**. |

The concealment is broken in **both** directions: neither a wrong gate nor a
wrong stub can now hide behind the other. The `record` suite's search count is
*derived* from `parser.relevant`'s own body (total / markers / needles split)
rather than grepped for, which is why the gate mutation moved it to 9
automatically.

### CR-02: `persist()` inside `d3d_present`

Verified by verifier-authored probe against the shipped handler, using the
harness's new `fail_saves` / `save_attempts` surface — not by reading the
suite's own checks.

| Question | Observed | Verdict |
|---|---|---|
| Does a refused write escape onto the game thread? | `pcall(persist)`; no exception left `d3d_present` | ✓ contained |
| Is the run silently lost? | attempt made (`save_attempts` 0→1), `save_due` re-armed, retried after the window, and the owed write **landed** once the fault healed (`saves` 0→1, session blob decodes with the run intact) | ✓ kept |
| Does it retry sixty times a second? | **61 frames inside the window produced exactly 1 attempt.** After `tick(+6s)`, attempts 1→2 | ✓ throttled at `SAVE_RETRY_SECONDS = 5.0` |
| Is the player told, once? | 1 chat line: *"Could not write the run down: … it will be retried … /incursion reset to hear them again."* Still 1 after 60 more frames and after a second failed retry | ✓ report-once |
| Is the latch re-armable? | `reset()` clears `save_told`, `save_due` **and** `save_retry_at` (inctrack.lua:155-163); profile switch does the same (:631-637) | ✓ stated way back |
| Format-string discipline | host error text is an argument; the default fault message carries `100%` on purpose and did not corrupt output | ✓ |

The re-arm-on-failure departure from the review's suggestion is the right call
and is correctly implemented: `save_due` is consumed **before** the attempt and
restored **only** on failure, so no window exists in which an unbounded retry is
possible. The flush sits above both of `d3d_present`'s early returns, so a
hidden or latched-off window still writes the run down.

---

## PERF-04: are the figures honest?

**Yes.** Confirmed three ways:

1. **No wall-clock rate is a pass/fail threshold.** The only rates printed are
   labelled *"provenance, not a threshold"* and nothing is asserted against
   them. The single wall-clock assertion in the entire suite is
   `ratio >= 1.2` — a **same-run** ratio between two shapes on the same corpus
   on the same machine, with the 1.2 explicitly documented as a noise margin,
   not a target. Observed 3.53x (Lua 5.5) and 4.81x (LuaJIT), far above it. That
   the ratio differs by backend while the *counters* are identical is itself
   evidence the counters, not the clock, carry the weight.

2. **The revision downward is real and self-documenting.** `REJECT_BASELINE`'s
   comment records the superseded 285,562 / 3.502 figure, states that it was
   measured against a stub doing two gsubs where the host does one, and says
   plainly *"Honest and smaller beats flattering."* `commit: a6a3577` exists and
   is correctly described as naming where the old shape was transcribed from
   rather than when the figure was taken.

3. **The corpus cannot flatter the result.** The suite's first check asserts no
   corpus line actually parses, so the two shapes are never comparing a path
   that skipped real work with one that did it.

Deterministic counters, identical on both backends:

| Line class | Old shape | New shape |
|---|---|---|
| colour-free rejected | 1.00 strip_colors, 4.33 gsub | **0.00 / 0.00** |
| coloured rejected | 1.00 strip_colors, 4.00 gsub | **1.00 / 1.00** |

Both classes cost measurably less. The phase goal is met for both — see WARN-01
for the criterion-wording gap on the coloured class.

---

## DOC-01 / DOC-02 — spot-checks against source

Both named traps handled correctly:

| Trap | Expected | Found |
|---|---|---|
| Boon glyph group | `%([^)]*%)`, may be empty | design.md:54 — *"The glyph group may be **empty**: a server data table with an unset icon field renders `()`…"*, matching `parser.lua:280` `s:match('^(%S+) gains the effect of (.-) %([^)]*%): (.+)$')` ✓ |
| `full_string` | must not appear | **zero hits** across `docs/design.md`, all four Lua files and the harness ✓ |

Further spot-checks, all confirmed against source:

| design.md claim | Source | Verdict |
|---|---|---|
| `AlwaysAutoResize` + `NoTitleBar` + an invisible fixed-width spacer (:369-379) | `ui.lua:492-495` flags; `ui.lua:513` `imgui.Dummy(ARG_SPACER)` | ✓ |
| Nine rows in render's draw order (:406-428) | `ui.lua` render body: Dummy → draw_header → `reconnected - awaiting update` → draw_objective → draw_bonus → draw_extra → draw_stats → draw_boons → draw_note | ✓ exact 1:1 correspondence |
| "`Phases cleared N` with `Elapsed m:ss` right-aligned. **The only stats row.**" | `ui.lua:320-326` — precisely those two, nothing else | ✓ |
| "Points are tracked… and are **not** displayed" (:432) | `draw_stats` never reads `run.points` | ✓ |
| `render_off` cleared by `/incursion`, `/incursion reset` and a character change; `render_ok` never cleared by a reset (:464-471) | `render_off = false` at inctrack.lua:153, :553, :629 (three sites); `render_ok` assigned only at :468 | ✓ |
| `elapsed_final`, `desynced`, `recovered`, `points_partial`, `bonus.loc`, `awards_seen`, schema `version = 2` | present at design.md:163-198, :274-286 | ✓ |
| Ten `string.find` searches, split 3 markers + 7 needles | derived from `parser.relevant`'s own body by the `record` suite; mutation-confirmed to move to 9 when the gate loses a marker | ✓ |

`ui.lua`'s layout comment (DOC-01's comment fix) now enumerates every row the
window can draw, in render order, with each row's condition — checked against
the render body above. `README.md`'s WR-04 wording is corrected to *"the bound
is the next frame that actually runs"* and it documents no close control and no
title bar.

`CHANGELOG.md` 1.2.0 names every defect in the user-facing terms the Phase-1
xfails used, including the message CR-02 newly ships. It does **not** claim any
in-game verification. One wording overclaim remains — see WARN-02.

---

## Standing Guarantee (whole milestone)

Run in the main checkout against `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs`,
2,951,129 lines from **127** logs.

| Suite | Floor | Lua 5.5 | LuaJIT 2.1 | Status |
|---|---|---|---|---|
| parser coverage | 11819 **exact** | 11819 | 11819 | ✓ |
| generic tier | 1 **exact** | 1 | 1 | ✓ |
| tightened patterns | 1 | 1 | 1 | ✓ |
| run reconstruction | 888 | 888 | 888 | ✓ |
| state units | 105 | 105 | 105 | ✓ |
| adaptability | 119 | 119 | 119 | ✓ |
| disconnect | 23 | 23 | 23 | ✓ |
| timers | 31 | 31 | 31 | ✓ |
| persistence | 40 | **40 (running, not skipped)** | 40 | ✓ |
| ui | 74 | 74 | 74 | ✓ |
| addon | 218 | 218 | 218 | ✓ |
| record | 17 | 17 | 17 | ✓ |
| cost | 6 | 6 | 6 | ✓ |

**PASS, 0 known defects, no XFAIL, no FAILED, no NOW PASSING, on both backends.**
No count fell.

| Other standing guarantee | Result |
|---|---|
| Purity boundary — `parser.lua` / `state.lua` gain no Ashita dependency | **0** hits for `require('common'\|'chat'\|'settings'\|'json'\|'imgui')`, `AshitaCore`, `ashita.` in both ✓ |
| No content name added to any Lua file | The six names in `ui.lua`'s mockup are **byte-identical** to the pre-phase state (`git show 2ef924c`); `parser.lua`'s are 1.0.0-era example message shapes. Nothing added. ✓ (see INFO-02) |
| Suite runs with no chatlogs and no Ashita install | Verified: PASS, 0 known defects, `chatlogs: none`, all non-corpus suites report non-zero counts ✓ |
| Deployed build matches the repo | All four Lua files **IDENTICAL** to `…\Ashita\addons\inctrack\` (`diff --strip-trailing-cr`) ✓ |
| Main checkout untouched by verification | `git status --porcelain` clean before and after; every mutation ran in a throwaway `git clone --local` ✓ |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| PERF-01 | Non-Incursion line rejected before allocation | ✓ SATISFIED | Probe: 0 strip_colors / 0 gsub on colour-free and stamped lines (WARN-01 scope note) |
| PERF-02 | A settings write never blocks the chat thread | ✓ SATISFIED | Probe: 0 inline saves/attempts across a 17-event burst; flushed on the next frame; unload writes unconditionally |
| PERF-03 | The memo cache has a bound | ✓ SATISFIED | Probe: peak 64 / cap 64 over 2000 distinct strings; cleared on reset and profile switch |
| PERF-04 | Per-line cost measured against a recorded baseline, demonstrably lower | ✓ SATISFIED | Printed both backends; deterministic counters; no rate used as a threshold |
| DOC-01 | `docs/design.md` matches shipped behaviour | ✓ SATISFIED | Seven independent spot-checks against source, both traps avoided |
| DOC-02 | `CHANGELOG.md` and version string record 1.2.0 | ✓ SATISFIED | `addon.version = '1.2.0'`; dated 1.2.0 entry (WARN-02 on one sentence) |

No orphaned requirements — REQUIREMENTS.md maps exactly these six to Phase 4.

## Anti-Patterns

| Scan | Result |
|---|---|
| `TBD` / `FIXME` / `XXX` / `HACK` / `PLACEHOLDER` / "not yet implemented" | **none** in `inctrack/*.lua`, `test/*.py`, `docs/design.md`, `README.md`, `CHANGELOG.md` |
| `TODO` | **none** |
| Dead code encoding a corrected premise | 1 — `coloured()` in `run_tests.py`, zero call sites (INFO-01) |

## Gaps Summary

**No gaps against the phase goal.** All five roadmap criteria are achieved in
the codebase, and both Criticals are genuinely fixed — verified at the source and
by mutation, not by reading the SUMMARY. The two Criticals' mutual-concealment
property is broken in both directions, which is the durable part of the CR-01
fix.

Four in-game checks remain open and cannot be closed from the codebase: three
carried forward from Phases 2 and 3, and one added by this phase. The new one is
the most consequential of the four and is structural rather than incidental —
the colour fall-through has **zero corpus backing** by construction, because
Ashita's log writer strips all three marker bytes on the way to disk. No amount
of replaying the 127 logs can ever exercise it. Its correctness rests entirely on
the gate/stub/host coupling verified above and on synthetic fixtures. That
coupling is now pinned three ways and mutation-tested, which is the strongest
guarantee available without live traffic — but a single in-game confirmation
would convert it from "argued" to "observed", and it is worth taking before the
milestone is archived.

Two warnings request a human decision (WARN-01, WARN-02). Neither blocks the
phase; both concern the accuracy of a claim rather than the behaviour of code,
which is exactly the class of defect this phase existed to remove.

---

_Verified: 2026-08-29_
_Verifier: Claude (gsd-verifier)_

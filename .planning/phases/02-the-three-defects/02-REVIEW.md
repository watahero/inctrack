---
phase: 02-the-three-defects
reviewed: 2026-08-29T00:00:00Z
depth: standard
diff_base: b8a19fa
files_reviewed: 4
files_reviewed_list:
  - inctrack/state.lua
  - inctrack/ui.lua
  - inctrack/inctrack.lua
  - test/run_tests.py
findings:
  critical: 1
  warning: 4
  info: 7
  total: 12
status: findings
fixed: 2026-08-29T00:00:00Z
fix_commits:
  CR-01: 8ce5a95
  WR-01: c6cfc36
  WR-02: 06763b4
  WR-03: aeda6ba
  WR-04: 1746f91
resolution:
  fixed: 5
  skipped: 0
  out_of_scope: 7
---

# Phase 2: Code Review Report

**Reviewed:** 2026-08-29
**Depth:** standard (adversarial, with empirical probes against the real state machine)
**Files Reviewed:** 4
**Status:** findings

## Summary

FIX-03 is clean as a *removal* — no residue, `origin_x` still used, `End()` still
unconditionally paired, no half-hoisted variable. But the replacement call shape
it introduced (`imgui.Begin(name, flags)`) is not a shape any other addon in the
live Ashita install uses, and Ashita's own SDK header declares exactly one
positional `Begin(name, p_open, flags)`. That is CR-01 and it is the headline.

FIX-01's arithmetic is right for every run shape the fixtures cover and for the
awkward ones they do not (phase repeats, phase going backwards, a run abandoned
mid-phase, a reconnect between a boss kill and the next phase line, a `complete`
arriving while desynced, a repeated `complete` inside the linger window). Two
shapes it is *not* right for, both proven by direct execution: a run joined
without ever seeing a phase line, where `complete` fabricates `phases_cleared =
1` out of nothing (WR-01); and a session written by shipped 1.1.0, whose
defective count is imported verbatim and then compounded by the new `complete`
increment (WR-02). Both put a confident wrong number on the HUD, which is the
one outcome PROJECT.md names as worse than no HUD at all.

FIX-02's clock arithmetic is correct. The negative-gap clamp is real, the
`time_left` floor is real, `started` and the bonus expiry age consistently, and
the wall-clock stamp does not double-count against the monotonic base. What it
does not do is use its new knowledge to *reject* a run the gap proves is over
(WR-04, proven: 7500s elapsed and `time_left = 0` on a 90-minute instance,
`should_show()` still true).

The test changes are honest. All three re-derived assertions are equivalent or
stronger, and suite 3's cross-check is genuinely recomputed from raw log text
rather than from state — though it now shares the implementation's signal
(IN-06) and its degenerate branch restates the implementation outright (IN-04).
The two persistence tolerance widenings (`==` → `<= 1`) are justified by real
wall-clock ticking, not by "whatever the code produces". The one field this
phase added, `awards_seen`, has no coverage at all (WR-03).

---

## Critical

### CR-01: `imgui.Begin(name, flags)` is an unverified call shape; Ashita's own SDK says slot 2 is `p_open`

**Status: FIXED** — `8ce5a95`. The binding was checked rather than assumed.
`addons/libs/imgui.lua` in the live install defines no Lua-side functions at
all (875 lines, zero `imgui.X =` assignments): it is a constants table whose
`__index` is `AshitaCore:GetGuiManager()`, so `Begin` reaches the SDK signature
at `plugins/sdk/imgui.h:305` unmediated, and that signature is declared once,
positionally. A sweep of all **220** `imgui.Begin(` call sites across the
installed addons confirmed the reviewer's count: inctrack was the only one
passing flags in slot 2, and the `nil` idiom is in use (`trove` x2). The
compiled binding's own type-handling could not be inspected (no source ships
with the install), so the fix takes the idiom every other addon uses:
`Begin(name, nil, flags)`. `test/stubs.py` no longer type-sniffs a numeric
slot 2 into flags -- it is strictly positional like the host -- the six
snapshots record `p_open=nil flags=...`, and a new ui block pins the argument
positions by name. Reinstating the two-argument form now fails 14 checks.
The FIX-03 assertion and its precondition are byte-identical (audit exit 0).

**File:** `inctrack/ui.lua:407`
**Also:** the six re-pasted golden snapshots at `test/run_tests.py:1532, 1566, 1593, 1642, 1674, 1698`

FIX-03 replaced

```lua
imgui.Begin('inctrack###incursion_window', ARG_OPEN, flags)
```

with the two-argument form

```lua
imgui.Begin('inctrack###incursion_window', flags)
```

`imgui` here is `addons/libs/imgui.lua`, which is a constants table with
`__index = AshitaCore:GetGuiManager()` — so `Begin` resolves to the native
binding over `IGuiManager`. That interface is declared once, positionally, in
the SDK shipped with the install:

```cpp
// Ashita/plugins/sdk/imgui.h:305
virtual IMGUI_API bool Begin(const char* name, bool* p_open = nullptr,
                             ImGuiWindowFlags flags = 0) = 0;
```

There is no overload. Parameter 2 is `p_open`. Nothing in Ashita documents a
"number in slot 2 means flags" convenience, and a survey of every `imgui.Begin`
call site across the ~60 addons in `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\`
found **inctrack is the only one that passes flags in slot 2**. Every other
two-argument call passes a `p_open` boolean or box; the established way to pass
flags without a close box is the three-argument form with an explicit nil, e.g.
`imgui.Begin(label .. '###pf_roulette', nil, ImGuiWindowFlags_NoCollapse)`.

If the binding does not type-sniff, one of two things happens sixty times a
second inside `d3d_present`:

- the flags are coerced to a truthy `p_open` and silently dropped — the window
  gains a title bar, becomes resizable and collapsible, steals focus on
  appearing, loses `AlwaysAutoResize` (so the width spacer no longer settles the
  layout) and ignores `locked`; or
- the binding type-checks and raises `bad argument #2` every frame, which
  PROJECT.md's rendering constraint calls out as "a frame-rate or stack problem,
  not a log line".

The suite cannot catch either. `test/stubs.py:214-231` was written in Phase 1 to
accept a numeric second argument as flags; that is a project assumption about
the host, not a fact derived from it. FIX-03's re-paste then baked the
unverified shape into the layout contract, so six golden snapshots now assert
that the unverified form is correct. The build is already deployed to the live
install (`02-02-SUMMARY.md`), and the summary's claim that "nothing in game
changed" rests entirely on the stub.

**Fix — use the unambiguous three-argument form:**

```lua
-- ui.lua:407
-- Explicit nil for p_open: the window is drawn without a title bar, so there is
-- nowhere for a close box to live. IGuiManager::Begin is positional, so the
-- flags must go in slot 3.
if imgui.Begin('inctrack###incursion_window', nil, flags) then
```

This keeps `not offered_close` true at `run_tests.py:2069` (`lua_type(nil) ~=
"table"`), so the FIX-03 assertion and its pin both stay green. It does require
one stub change: `Stub._begin_line` (`test/stubs.py:466-478`) currently falls
through to `flags = box` when slot 2 is not a table, so a nil there would render
`flags=none`. Handle nil explicitly, then re-paste the six snapshots as
`Begin 'inctrack###incursion_window' p_open=nil flags=...`.

If the two-argument form is genuinely supported, say so with evidence — an
actual `/addon reload inctrack` in game confirming the window still has no title
bar, cannot be resized, and still auto-fits its height — and record it beside
the existing FIX-02 human-verification item. Right now that verification does
not exist for FIX-03, even though FIX-03 is the change that touches the render
call.

---

## Warnings

### WR-01: `complete` invents `phases_cleared = 1` for a run it joined without ever seeing a phase line

**Status: FIXED** — `c6cfc36`. Assign-max as the review proposed. Four new
cases: the cold completion (0), the watched `Begins!`-to-`Complete!` run that
must still report 1, and a repeated completion inside the linger window.
Restoring the old increment fails the cold-completion check.

**File:** `inctrack/state.lua:413-415`

```lua
if not run.finished then
    run.phases_cleared = run.phases_cleared + 1;
end
```

The increment is unconditional on whether the addon has any idea what phase the
run was on. Proven by direct execution against the shipped state machine:

```
feed: "Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s"
  -> phases_cleared=1  phase=nil  awards_seen=0  recovered=true  finished=true
```

`complete` carries `instance` (`parser.lua:87`), so it bootstraps a run at
`state.lua:172-175`. A five-phase run the addon was loaded into during the final
phase now renders **"Phases cleared 1"** — and it renders it with no uncertainty
marking at all, because `ui.lua:412` suppresses the `reconnected - awaiting
update` banner once `run.finished` is set. Pre-fix this path showed `0`. The new
value is not a lower bound the player can reason about; it is a claim the addon
has no evidence for, which is precisely what "never quietly wrong" forbids.

Secondary effect: the increment compounds rather than converges. Combined with
WR-02 it takes a restored count of 5 to 6.

**Fix — assign the phase the completion closes, rather than incrementing:**

```lua
if t == 'complete' then
    -- The completion closes the phase we are on: reaching 'Phase #N' and then
    -- finishing means N cleared, since the final boss kill never produces a
    -- phase line of its own. Assign-max rather than increment, so a repeated
    -- 'Complete!' is idempotent and a restored count is never compounded. A
    -- run we joined without ever seeing a phase line has no phase to close, so
    -- nothing is invented for it.
    local closing = run.phase or (run.recovered and 0 or 1);
    if closing > run.phases_cleared then
        run.phases_cleared = closing;
    end
```

Verified compatible with every existing assertion:

| shape | current | proposed | asserted at |
|---|---|---|---|
| `Begins!` → `Phase #1` → `Phase #2` → `Complete!` | 2 | 2 | `run_tests.py:762` |
| `Begins!` → `Complete!`, no phase line | 1 | 1 | `run_tests.py:1683` snapshot |
| cold `Complete!` (recovered, no phase) | **1** | **0** | *unasserted — the defect* |
| 127 real logs, `max(phase numbers)` | ok | ok | `run_tests.py:511` |
| repeated `Complete!` in linger | ok | ok | idempotent by construction |

The `not run.finished` guard becomes unnecessary and can go. Add a case for the
cold-`Complete!` shape next to the `f1a`/`f1b`/`f1c` block at
`run_tests.py:752-789`.

### WR-02: the on-disk schema changed but `version` stayed 1, so a 1.1.0 session imports the very defect FIX-01 removed

**Status: FIXED** — `06763b4`. Both remedies the review offered, taken
together: `serialise()` now writes `version = 2`, `restore()` accepts 1 or 2
and refuses anything else, and a version-1 blob is *migrated* rather than
discarded -- the cleared count is re-derived from `data.phase`, the one field
in that blob the server authored outright. Discarding was the simpler option
but throws away a live run's points, boons, bonus and elapsed on the exact
upgrade path the phase brief flags.

One deviation from the review's migration sketch: `awards_seen` is set to **0**
for a legacy blob, not to `data.phases_cleared`. The old field was
`max(awards, phase - 1)`, so it *over*-states the award count, and an
over-stated `awards_seen` silences the `points_partial` lower-bound marking for
the rest of the run -- the same suppression this finding complains about.
Zero marks rather than hides, which is the only safe direction here.

**File:** `inctrack/state.lua:602, 644-645`

`serialise()` gained a field and changed the meaning of an existing one, but
still writes `version = 1` and `restore()` still accepts `version == 1`. The
`awards_seen` fallback at :644 is careful; `phases_cleared` at :645 is not:

```lua
run.awards_seen    = data.awards_seen or data.phases_cleared or 0;
run.phases_cleared = data.phases_cleared or 0;   -- <- 1.1.0 semantics, imported whole
```

Under 1.1.0 `phases_cleared` was incremented by *every* points award, including
bonus payouts and chests. Proven against a 1.1.0-shaped blob (`phase = 3`,
`phases_cleared = 5`, true cleared count 2):

```
restore -> phases_cleared=5  awards_seen=5  phase=3
then "Complete!" -> phases_cleared=6
```

The HUD shows 5, then 6, for a three-phase run. The phase-line inference only
raises, so it never corrects this for the life of the run. Users upgrading with
an in-progress session — the exact path the phase brief flags — see the old
defect, plus one.

The inherited `awards_seen = 5` also suppresses `points_partial` for the rest of
the run (`points_partial=false` at phase 3 with 5 recorded awards), so the
lower-bound marking is lost on the same blob.

**Fix — either bump the schema and let an old session go, which is the reason
the version field exists:**

```lua
-- serialise()
version = 2,
-- restore()
if type(data) ~= 'table' or data.version ~= 2 or not data.instance then
    return false;
end
```

**or migrate the count off the only field in a 1.1.0 blob that is still
trustworthy — the phase number:**

```lua
if data.awards_seen == nil then
    -- A 1.1.0 blob's phases_cleared was authored by points awards, so it
    -- carries the defect FIX-01 removed. Re-derive from the phase instead.
    run.awards_seen    = data.phases_cleared or 0;
    run.phases_cleared = data.phase and (data.phase - 1) or 0;
else
    run.awards_seen    = data.awards_seen;
    run.phases_cleared = data.phases_cleared or 0;
end
```

Whichever is chosen, add a legacy-blob case to the persistence suite — see WR-03.

### WR-03: `awards_seen`, the field this phase added, has no test coverage at all

**Status: FIXED** — `aeda6ba` (round trip) and `06763b4` (both fallback
branches). The `data.awards_seen or data.phases_cleared or 0` expression the
finding calls untested no longer exists: WR-02 replaced it with an explicit
version-1 branch, and each branch now has its own case.

**File:** `inctrack/state.lua:76, 563, 644` / `test/run_tests.py:1345-1370`

`grep -rn awards_seen test/` returns nothing. The json round-trip suite asserts
`points`, `phases_cleared`, `phase`, kills, objective, boss hint, bonus, extras
and boons survive encode/decode (`run_tests.py:1349-1372`) but never
`awards_seen`, even though the fixture produces `awards_seen = 1`. Nothing
exercises the `data.awards_seen or data.phases_cleared or 0` fallback either, so
the upgrade path in WR-02 is untested in both branches.

`awards_seen` is the sole input to the `points_partial` marking after FIX-01. If
it silently fails to round-trip, a resumed run stops flagging missed awards and
nothing in the suite notices.

**Fix — add to the round trip at `run_tests.py:1355` and cover both fallback
branches:**

```python
res.check(int(b["awards_seen"]) == 1, "awards_seen lost")

# A 1.1.0 blob has no awards counter. Reading one out of the old
# phases_cleared is what keeps the missed-award marking working across the
# upgrade, so both branches of that fallback are pinned.
legacy = js.decode(encoded)
legacy["awards_seen"] = None
s3 = new_state(lua, State)
res.check(bool(s3.restore(s3, legacy)), "a 1.1.0 blob was rejected")
res.check(int(s3.snapshot(s3)["awards_seen"]) == 1,
          "a 1.1.0 blob's award count was not recovered from phases_cleared")
```

### WR-04: `restore()` now knows the instance timer expired during the gap, and resumes the run anyway

**Status: FIXED** — `1746f91`. The guard landed beside the staleness rule
exactly as written. Both directions are pinned: two hours away with ten minutes
left is refused and leaves no half-applied run; ninety seconds away with ten
minutes left is still resumed, so the rule is a statement about the timer and
not a second staleness window.

**File:** `inctrack/state.lua:620-661`

`STALE_SECONDS` is three hours, but an Incursion is ninety minutes. FIX-02 gave
`restore()` the gap in real seconds and a saved `time_left`; it uses them to age
the clock but never to reject a run they jointly prove is over. Proven with a
two-hour gap on a blob holding ten minutes remaining:

```
restore -> true   time_left=0   elapsed=7500   should_show=true
```

The window comes back showing an active run: `~0:00` in red, `Elapsed 2:05:00`
on a ninety-minute instance, `Waiting for next objective...`, and a phase count
that will never move again. It sits there until the player types `/incursion
reset` or a new run starts. This is the "started moving backwards makes elapsed
exceed the instance duration" case from the phase brief, and after FIX-02 the
one-line guard is now available.

**Fix — at `state.lua:630`, beside the existing staleness rule:**

```lua
if data.saved_at and gap > STALE_SECONDS then
    return false;
end

-- The instance clock ran out while we were gone, so the run ended without us
-- whether or not we ever saw the completion. Resuming it would present a
-- finished run as live. One server-minute of slack, because the server reports
-- whole minutes and our own countdown floors at zero.
if data.time_left and gap > data.time_left + 60 then
    return false;
end
```

---

## Info

_All seven Info findings are **out of scope** for this fix pass (Critical +
Warning only) and are left open deliberately. IN-01 is explicitly Phase 3's
(HARD-05). IN-03 and IN-06 are explicitly Phase 4's. IN-02, IN-04, IN-05 and
IN-07 remain unaddressed and unclaimed -- IN-07 in particular now also applies
to the version-1 migration path added for WR-02, whose `data.phase - 1` is an
integer under Lua 5.3+ and a float from a JSON-decoded blob._


### IN-01: FIX-02 widened the crash surface on a malformed blob (Phase 3 / HARD-05 owns this)

**File:** `inctrack/state.lua:656`

`run.time_left = data.time_left - gap;` performs arithmetic on a field that was
previously assigned untouched. A non-numeric `time_left` in a hand-edited or
corrupted settings file now raises:

```
state.lua:656: attempt to sub a 'string' with a 'number'
```

`restore()` is called outside any `pcall` in both call sites —
`inctrack.lua:127` (the `load` event) and the `settings.register` callback at
`inctrack.lua:244` — so the error escapes into an Ashita event handler and, in
the settings path, skips the trailing `settings.save()`.

**Phase 3 owns the fix: HARD-05 is "a restored session is validated structurally
before it is applied, and a malformed one is discarded rather than half-applied."**
Recorded here only because this phase enlarged the surface HARD-05 will have to
cover; nothing needs to change in Phase 2.

### IN-02: the comment justifying the wall clock states something that is not true

**File:** `inctrack/state.lua:614-616`

> "the injected monotonic clock restarts from zero with the addon, so the stamp
> written at save time is the only record of the gap"

The injected clock is `os.clock` (`inctrack.lua:73-76`), which measures from
*process* start. `/addon reload inctrack` does not restart the FFXI process, so
`os.clock()` does not restart either — it only resets on a full client restart.
The code is correct either way (`restore()` re-seeds `started` relative to the
current `now`, so it does not care), but the comment is the reason a future
reader would trust the design, and it is wrong about the mechanism it cites.

**Fix:** "the injected monotonic clock has no fixed relationship to the previous
session's — it restarts with the client process, and even across a bare addon
reload nothing ties its origin to the saved run — so the wall-clock stamp is the
only record of the gap."

### IN-03: `points_partial` has no consumer

**File:** `inctrack/state.lua:211, 567, 646`

FIX-01 rewired what sets `points_partial` (from `phases_cleared` to
`awards_seen`) and re-derived a test around it, but `grep -rn points_partial
inctrack/` shows it is set, serialised and restored, and read by nothing.
`ui.lua` renders neither `points` nor `points_partial`. The "visibly marked as
unconfirmed" half of the core value is not actually delivered for points — the
flag is computed and thrown away.

Not a defect of this phase (the flag was already unread before it), and the
decision to keep it is recorded in `02-CONTEXT.md`. Worth resolving in Phase 4
alongside DOC-01: either surface it or document why it exists unread.

### IN-04: suite 3's degenerate branch restates the implementation instead of cross-checking it

**File:** `test/run_tests.py:511`

```python
want_cleared = max(active["phases"]) if active["phases"] else 1
```

The `else 1` is not re-derived from anything in the log — it is exactly what
`state.lua:414` produces for a run with no phase line (`0 + 1`). If the branch is
ever reached it passes by construction, and it is the branch that covers the
WR-01 shape. The `max(...)` branch is a genuine independent recomputation from
raw text; this one is not.

**Fix:** if a completed run with no phase line is not expected in real logs, make
that a claim rather than an assumption:

```python
res.check(bool(active["phases"]),
          "%s: a completed run with no phase line at all -- the cleared count "
          "cannot be re-derived for it" % tag)
want_cleared = max(active["phases"]) if active["phases"] else -1
```

### IN-05: suite 3 lost its orthogonal signal

**File:** `test/run_tests.py:506-514`

The old cross-check tied `phases_cleared` to the *points-event count* — a
different signal from the one the implementation reads. The new one derives from
the phase-number sequence, which is the same signal `state.lua:201` uses. It is
still recomputed from raw text rather than from state, which is what
`02-CONTEXT.md` required, and it does catch a double-counting `complete` or a
broken inference. But a systematic misreading of phase numbers by `PHASE` /
`parser.lua` would now satisfy both sides.

**Fix (optional, cheap):** keep the orthogonality by also asserting the relation
between the two signals over real logs, e.g. `awards_seen >= max(phases)` on a
clean run — a boss paid out for every phase the log shows.

### IN-06: `ui.render`'s return value and its `opts.visible` parameter are now inert in production

**File:** `inctrack/ui.lua:388-427`, `inctrack/inctrack.lua:214-218`

`d3d_present` now discards the return, and the only caller hardcodes
`visible = true`, so `opts.visible` is a constant that is read once and echoed
back. The doc comment at `ui.lua:382-386` explains this and the ui suite asserts
`kept is visible`, so it is deliberate rather than residue — but it is a
parameter and a return value that exist only for the test. Worth collapsing in
Phase 4 if `ui.render`'s contract is revisited; not a defect now.

### IN-07: `phases_cleared` is integer or float depending on provenance, and renders as `2.0` under Lua 5.3+

**File:** `inctrack/ui.lua:280`, `inctrack/state.lua:645`

`tostring(run.phases_cleared)` renders a restored count as `2.0` under the test
backend:

```
Lua 5.5:  restore(phases_cleared = 2.0) -> tostring(...) = "2.0"
```

The shipped path is safe — Ashita embeds LuaJIT 2.1, where all numbers are
doubles and `tostring(2.0)` is `"2"`. But the field's type now depends on where
it came from: `e.phase - 1` via `tonumber` yields an integer under 5.3+, while a
JSON-decoded blob yields a float, and `complete`'s `+ 1` preserves whichever
arrived. No test renders a *restored* run, so the suite has a blind spot exactly
where the divergence lives.

**Fix:** normalise on the way in, which costs nothing and removes the dialect
dependency entirely:

```lua
run.phases_cleared = math.floor(data.phases_cleared or 0);
run.awards_seen    = math.floor(data.awards_seen or data.phases_cleared or 0);
run.points         = math.floor(data.points or 0);
```

---

## What was checked and found sound

Recorded so a later reader does not re-litigate it:

- **FIX-01 across awkward run shapes.** Two phase lines for the same phase
  (idempotent), a phase number going backwards (never lowers), a run abandoned
  mid-phase (count stays at `phase - 1`, correct), a reconnect between a boss
  kill and the next phase line (under-reports by one until the next phase line —
  the safe direction, and the desync banner is showing), a `complete` while
  desynced (correct), a repeated `complete` inside the linger window (guarded),
  and a `complete` after the linger expires (blocked at `state.lua:185`).
- **`points_partial` is equal-or-stronger than before.** Bonus payouts still
  inflate `awards_seen` and can mask a genuinely missed boss award — but the old
  code compared against a `phases_cleared` that was itself `max(award count,
  phase - 1)`, so it masked at least as much. No regression.
- **FIX-02's clamps.** The negative-gap clamp is real and the stale check now
  reads the clamped value, so a future stamp is inert rather than
  generous. `time_left` floors at zero. `started`, `time_left` and the bonus
  expiry all move by the same gap, so the window cannot contradict itself. The
  wall-clock stamp does not double-count against the monotonic base:
  `data.elapsed` is frozen at save time and `started` is re-seeded relative to
  the current `now`.
- **A bonus that lapsed during the gap** is dropped by `State:bonus()`'s existing
  expiry rule rather than by a special case, and the record survives so a later
  progress line can revive it — as the comment claims.
- **FIX-03 left no residue.** `ARG_OPEN` is gone with no dangling reference,
  `origin_x` is still assigned and read, `imgui.End()` is still called
  unconditionally outside the `if` (correct for ImGui), the style stacks stay
  balanced, and `grep -rn 'ARG_OPEN\|shown' inctrack/` is clean.
- **The three re-derived assertions are equivalent-or-stronger.**
  `run_tests.py:607` (`0`, was `1`): correct — no phase line, no completion.
  `run_tests.py:1146` (`2`, was `3`): correct — `mid_phase()` reaches `Phase #3`,
  and the award during phase 3 must not advance the count. Both gained sharper
  failure messages that name the rule rather than saying "wrong".
  `run_tests.py:511`: genuinely re-derived from raw text; see IN-04/IN-05 for the
  two places it is weaker than it looks.
- **The two persistence tolerance widenings** (`==` → `abs(...) <= 1`, `1359` and
  `1367`) are justified by the wall-clock second ticking between encode and
  decode, and `1` is the exact maximum that can happen. Not slack.
- **The `EXPECTED_XFAILS = 0` / `EXPECTED_DEFECTS = set()` guard still bites** —
  `main()` compares sorted lists, so any name at all mismatches `[]`, and the
  summary records the negative control that proved it.
- **The suite is green** at the recorded per-suite counts (`state 49, adaptability
  20, disconnect 23, timers 21, ui 56, addon 83`) with no chatlogs.

---

_Reviewed: 2026-08-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---

## Fix pass, 2026-08-29

Applied by `gsd-code-fixer` against scope "Critical + Warning".

| Finding | Status | Commit |
|---|---|---|
| CR-01 | fixed | `8ce5a95` |
| WR-01 | fixed | `c6cfc36` |
| WR-02 | fixed | `06763b4` |
| WR-03 | fixed | `aeda6ba` |
| WR-04 | fixed | `1746f91` |
| IN-01 … IN-07 | out of scope, left open | — |

**Verification**, all run in the main checkout (`workflow.use_worktrees` is
false, so there is no worktree environment to qualify these numbers):

| Command | Result |
|---|---|
| `python test/run_tests.py` | PASS, exit 0 |
| `python test/run_tests.py "<Ashita>\chatlogs"` | PASS, exit 0, 2 944 071 lines / 127 logs |
| `INCTRACK_LUA=luajit21 python test/run_tests.py "<Ashita>\chatlogs"` | PASS, exit 0 |
| `python /tmp/inctrack-assert-integrity.py` | exit 0, all 4 intact (negative control on the FIX-03 disjunction exited 1 first) |

Zero `FAILED`, zero `NOW PASSING`, zero `XFAIL` lines on both backends.

Per-suite counts against the floor -- none fell:

| Suite | Floor | Now |
|---|---|---|
| parser: structural | 11819 | 11819 |
| parser: generic tier | 1 | 1 |
| state: run reconstruction | 888 | 888 |
| state: objectives, bonus, recovery | 49 | 53 |
| adaptability | 20 | 20 |
| disconnect | 23 | 23 |
| timers | 21 | 25 |
| persistence | 25 | 31 |
| ui | 56 | 65 |
| addon | 83 | 83 |

Every fix was negative-controlled: the change was reverted and the new checks
were confirmed to fail (CR-01: 14 checks, WR-01: 1, WR-02: 3, WR-04: 2).

Re-deployed to `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\`
and verified CR-insensitively: all four `.lua` files identical to the
repository ignoring line endings.

_Fixed: 2026-08-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

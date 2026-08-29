---
phase: 03-fragile-paths
reviewed: 2026-08-29T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - inctrack/inctrack.lua
  - inctrack/parser.lua
  - inctrack/state.lua
  - test/run_tests.py
  - test/stubs.py
findings:
  critical: 1
  warning: 5
  info: 5
  total: 11
status: findings
fixed: 2026-08-29
fix_scope: critical_warning
fix_status:
  CR-01: fixed (validator half applied; parser half deliberately declined -- see the status note)
  WR-01: fixed
  WR-02: fixed
  WR-03: fixed
  WR-04: fixed
  WR-05: fixed
  IN-01: not addressed -- Info, outside the critical+warning fix scope
  IN-02: not addressed -- Info, outside the critical+warning fix scope
  IN-03: not addressed -- Info; the review itself recommends no change this milestone
  IN-04: not addressed -- Info, outside the critical+warning fix scope
  IN-05: fixed 2026-08-29 (milestone audit G-1) -- re-decided as 'reject the
    field, keep the run': a NaN or +/-infinity is read exactly as a missing key
    would be, so the field is unknown and the rest of the run survives
fix_commits:
  CR-01: e07126b
  WR-01: a11583e
  WR-02: f8fb735
  WR-03: 8478359
  WR-04: 51f5cb5
  WR-05: 2ef924c
---

# Phase 3: Code Review Report

**Reviewed:** 2026-08-29
**Depth:** standard
**Files Reviewed:** 5 (+ `inctrack/ui.lua` as an unchanged reference)
**Status:** findings

## Summary

Scope confirmed against `git diff --stat b2d30cc..HEAD`: exactly
`inctrack/inctrack.lua`, `inctrack/parser.lua`, `inctrack/state.lua`,
`test/run_tests.py`, `test/stubs.py`. **`inctrack/ui.lua` is byte-identical to
`b2d30cc`** (`git diff b2d30cc..HEAD -- inctrack/ui.lua` is empty) — no finding
there. `python test/run_tests.py` is green locally (Lua 5.5, no chatlogs, no
Ashita libs; the persistence suite therefore **skipped** and the round trip
through Ashita's real `json.lua` was not exercised in this review).

The fault injector is clean: `arm_fault` / `fire_fault` / `__imgui_stub` appear
nowhere under `inctrack/`, `S.fault` defaults to `nil`, `S.reset()` disarms it,
firing consumes the arming, and every suite builds its own isolated `Host`
(its own Lua state), so nothing can stay armed across suites.

The three parser tightenings hold up better than expected. HARD-02's greedy/
fallback pair was probed directly and behaves as documented, including a boss
name that *contains* `" at ("` (`Chariot at (Gate)`) and a name that itself ends
in a parenthesised group. HARD-03 handles a single-name list, a trailing
separator, and a list that trims to nothing. HARD-04's glyph class `[^)]+` is
safe against Shift-JIS glyph bytes (`0x29` is not a valid SJIS trail byte).

Where this phase does misfire is HARD-05. The validator's own comment claims
two guarantees it does not deliver:

- *"a shape the addon's own writers cannot produce"* — it **is** producible.
  `(Boss:  at (J-9))` yields `next_boss.name = ''`, and `Incursion [] Begins!`
  yields `instance = ''`; both are written by `serialise()` and both now cause
  the whole restored session to be **rejected**, losing a live run's boons,
  points and elapsed on a legitimate reload. Verified by execution.
- *"discard whole, never half-apply"* — `array_of` accepts a hole. A `boons`
  table with keys `{1, 3}` passes validation and `restore()`'s `#`-driven loop
  keeps **one of three boons** with nothing on screen saying so. Verified by
  execution.

Both are exactly the class of harm the brief warned about: a defence that
causes the harm it was meant to prevent.

---

## Critical Issues

### CR-01: A session the addon wrote itself is rejected whole when a name field is blank — the live run is lost on reload

**Status: FIXED** (`e07126b`) — the validator half only; the parser half was
considered and declined.

`full_string` is gone from `state.lua`. Every string field is now checked with
`is_string` — for *being* a string, never for saying anything — so a blank
`instance`, `next_boss.name`, `boon.name` or mob entry no longer fails the
blob. The relaxation was taken further than the review proposed, to all four
sites rather than two, because the asymmetry the review calls accidental is
live in both directions: `restore()` still accepts `version = 1` blobs, and
shipped 1.1.0 had no boon-name guard and kept empty pieces in its mob split,
so a blank boon name and a blank mob are both on players' disks today. Leaving
those two strict would have kept the same regression alive on the upgrade path.

The parser half — giving the three `' at '` matchers HARD-04's `name ~= ''`
guard — was **not** applied. With the validator no longer treating a blank as
fatal, that guard only destroys information: `(Boss:  at (J-9))` would stop
producing an event at all, and the location, which the server *did* send,
would be dropped along with the name it did not. The guard is right for the
boon matcher and wrong here for a statable reason, now recorded in
`parser.lua`: the boon pattern is the loosest in the file — no `Incursion [`,
`New Objective: ` or `(Boss: ` anchor — so a blank name there means the match
probably found something that is not a boon at all, and the guard is a
*disambiguator*. The boss forms are anchored on fixed server wording, so a
match is certainly a boss line, and the right answer to a boss line naming no
boss is to show the part it did say.

Pinned by 11 new checks in the state suite: three `accepts_blank` cases, each
also asserting the rest of the run came back intact so that accepting cannot
become its own half-apply, plus two end-to-end cases driven by server text —
`(Boss:  at (J-9))` and `Incursion [] Begins!` — fed through the parser,
serialised, and reloaded. Negative control: restoring `full_string` turns 12
checks red.

**File:** `inctrack/state.lua:720`, `inctrack/state.lua:748`
(writers: `inctrack/parser.lua:178-185`, `inctrack/parser.lua:84`)

**Issue:**
`valid_next_boss` requires `full_string(b.name)` and `valid_session` requires
`full_string(data.instance)` — a *non-empty* string in both cases. Failing
either fails the **entire** blob, and `restore()` returns `false`, which the
load handler answers by clearing `settings.session` outright
(`inctrack/inctrack.lua:155-158`).

Both blank values are producible by the addon's own parser, because the boss
matchers capture with `(.*)` / `(.-)` and — unlike the boon matcher, which
HARD-04 gave an explicit `name ~= ''` guard — have no blank-name guard at all:

```
'(Boss:  at (J-9))'                -> { t='boss_hint',       name='',  loc='(J-9)' }
'New Objective: Defeat  at (J-9)!' -> { t='objective_boss',  name='',  loc='(J-9)' }
'Incursion [] Begins! (Normal)'    -> { t='begin', instance='' }
```

Reproduced end to end against the shipped modules:

```
next_boss.name = ""
restore of a live run whose boss hint had a blank name -> false
instance = ""
restore with a blank instance -> false
restore of an ordinary live run -> true          (control)
```

This is a **regression introduced by this phase**. Before HARD-05, `restore()`
only tested `not data.instance`, and `''` is truthy in Lua, so both blobs
restored fine. Now one degenerate line anywhere in a ninety-minute run silently
converts every subsequent `/addon reload`, zone crash or client restart into
total loss of that run's boons, points, phase and elapsed — the precise data
the persistence layer exists to protect, and which the server never re-announces.

The `valid_boon` `full_string(b.name)` at `inctrack/state.lua:736` is safe only
because HARD-04 happens to guard the boon name; the asymmetry is accidental,
not designed.

**Fix:** two halves — stop writing blanks, and stop treating a blank as fatal.

```lua
-- inctrack/parser.lua -- apply HARD-04's own rule to the three ' at ' matchers.
-- A blank name is not a boss, exactly as a blank name is not a boon.
    function(s)
        local name, loc = s:match('^%(Boss: (.*) at (%(.+%))%)$');
        if not name then
            name, loc = s:match('^%(Boss: (.-) at (.+)%)$');
        end
        if name then
            name = trim(name);
            if name ~= '' then
                return { t = 'boss_hint', name = name, loc = trim(loc) };
            end
        end
    end,
```

```lua
-- inctrack/state.lua -- a blank string is harmless to every consumer
-- (TextColored('') draws nothing); it must not cost the whole run.
local function valid_next_boss(b)
    if b == nil then
        return true;
    end
    return type(b) == 'table' and type(b.name) == 'string' and opt_string(b.loc);
end

local function valid_session(data)
    if type(data) ~= 'table' then
        return false;
    end
    return type(data.instance) == 'string'   -- was full_string()
        -- ... unchanged ...
```

Add a check pinning it: a blob whose `next_boss.name` is `''` must restore, and
must come back with the rest of the run intact. The existing `control` case at
`test/run_tests.py:1181` uses a fully-populated well-formed blob and cannot see
this.

---

## Warnings

### WR-01: `array_of` admits holes, so `restore()` still half-applies — the rule HARD-05 was written to enforce is not enforced

**Status: FIXED** (`a11583e`) — as proposed. `array_of` counts what `pairs()`
visits and then requires `t[1..n]`, so keys `{1, 3}` fail. Pinned in the state
suite (a holed mob list and a holed three-boon list, both refused whole) and —
the part the review's own run could not reach — in the **persistence** suite,
through Ashita's real `json.lua`: `[{...}, null, {...}]` decodes to exactly
keys `{1, 3}` with `#` answering 1, and is now refused. The empty-table
question is settled in the same place: `json.lua` writes an empty table as
`[]`, decodes it back to an empty table, `n = 0`, and a run with no boons and
no extras yet still restores. Numeric-looking object keys were checked while
there — `{"5": ...}` decodes with a *string* key, so `map_of` is unaffected.
Negative control: deleting the contiguity loop turns 3 checks red.

**File:** `inctrack/state.lua:673-686`, consumed at `inctrack/state.lua:917-922`

**Issue:** The comment above `array_of` states: *"Every key as well as every
value. A stray key or a hole is a shape the addon's own writers cannot produce,
and admitting one would let a decoded blob smuggle a value past a length-based
loop unseen."* The code checks each key is a positive integer and each value is
valid — it never checks the keys are **contiguous from 1**. `{[1]=a, [3]=c}`
passes.

`restore()` then reads that table with `for i = 1, #data.boons`, and `#` on a
table with a hole is unspecified (it returned `1` here). Verified against the
shipped module:

```
boons before: ['A', 'B', 'C']
restore with a hole in boons -> True | boons kept: ['A']
```

The run resumes holding one of the three boons the player picked, with nothing
on screen saying the other two were dropped — verbatim the failure the
`inctrack/state.lua:915-916` comment says it fixed. The same gap applies to
`objective.mobs` (`inctrack/state.lua:845-851`), where a hole silently truncates
the mob list.

Reachable input: `"boons": [{...}, null, {...}]` is well-formed JSON, and the
file is one a player can hand-edit — a case `restore()` already contemplates at
`inctrack/state.lua:790-791`. A decoder that skips JSON `null` elements yields
exactly `{1, 3}`.

**Fix:**

```lua
local function array_of(t, ok)
    if t == nil then
        return true;
    end
    if type(t) ~= 'table' then
        return false;
    end
    local n = 0;
    for k, v in pairs(t) do
        if not array_key(k) or not ok(v) then
            return false;
        end
        n = n + 1;
    end
    -- Contiguous from 1, or the '#'-driven loops below walk past a hole and
    -- half-apply what the whole-blob rule says must be discarded whole.
    for i = 1, n do
        if t[i] == nil then
            return false;
        end
    end
    return true;
end
```

### WR-02: `/incursion` after a render error says "Window re-enabled" and leaves the window hidden when `auto` is off

**Status: FIXED** (`f8fb735`) — both halves of the review's either/or, because
each covers a state the other does not. The `override` clear is gone, so a
manual show survives the failure and is what brings the window back; and the
chat line now reports what is on screen rather than what was asked for,
because the player can have turned automatic show/hide off between the failure
and the recovery, and no fixed wording is true of every state. Pinned by 7
checks, one of which compares the claim against the screen directly. Negative
control: restoring the clear turns 3 checks red, including that comparison.

**File:** `inctrack/inctrack.lua:328-334`

**Issue:** The re-enable branch clears `render_off` **and** `override`, on the
stated assumption that dropping back to automatic visibility makes the window
"reappear on its own". That holds only when `settings.auto` is `true`. A player
running with `/incursion auto` off had `override = true` (that is the only way
they could see the window at all), so clearing it puts the window straight back
off screen — while the chat line asserts the opposite.

Reproduced through the harness:

```
auto = False  override = True
render_off = True
chat said: ['[inctrack] Window re-enabled.']
render_off = False  override = None
frame after re-enable drew: []          <- nothing
```

The player must type `/incursion` a second time. A chat line that states
something untrue about what is on screen is the core value inverted, and it
lands on the one recovery path the error message itself advertises.

**Fix:** delete the `override` clear. Both prior states — `nil` under `auto`,
`true` under manual — are already the state you want restored, and `render_off`
can only have been latched on a frame where `visible()` was true.

```lua
        if incursion.render_off then
            incursion.render_off = false;
            -- Deliberately *not* clearing override: whatever it held is what
            -- put the window on screen on the frame that failed, so it is
            -- what brings it back. Clearing it hides the window outright
            -- whenever automatic show/hide is off.
            printf('Window re-enabled.');
            return;
        end
```

### WR-03: the stack repair's own function lookups run outside their `pcall`s

**Status: FIXED** (`8478359`) — both repair calls are now
`pcall(function () ... end)`, and the `printf` on the same path is wrapped the
same way, as a whole statement so `tostring(err)` on a foreign error value is
covered too. Testing it needed a new capability: the recorder is an ordinary
table, so `stubs.py` gained `arm_lookup_fault`, which lifts an entry point out
of the table and raises from an `__index` — modelling how Ashita's `imgui`
actually resolves, and asserting nothing about whether its GUI manager does
raise. Pinned by 8 checks over `End` and `PopStyleVar`. Negative control:
restoring `pcall(imgui.End)` turns 6 checks red, with the raise seen escaping
`d3d_present`.

**File:** `inctrack/inctrack.lua:297-300`

**Issue:** The block comment is explicit that the repair must never become the
second error of the frame: *"Each repair call is protected on its own, for the
same reason as above: neither of them may become the second error of the frame
either."* But in `pcall(imgui.End)`, Lua evaluates `imgui.End` **before**
`pcall` is entered. `imgui` in Ashita is a constants table whose `__index` is
`AshitaCore:GetGuiManager()` (`inctrack/inctrack.lua:34-37` says so), so the
lookup is a live metatable call — and a raise from *it* escapes `d3d_present`
uncaught, into the game thread every addon shares. `printf` on line 306 is
likewise unprotected on the same path.

The likelihood is low (it needs the GUI manager to be unavailable during
`d3d_present`), but the cost of closing it is two characters of syntax, and the
comment currently claims an invariant the code does not hold. This is also
listed as unverified coverage item D8, which makes an unprotected lookup the
wrong side to be on.

**Fix:**

```lua
    if incursion.render_ok then
        -- The lookups go inside too: imgui's __index is a live call into
        -- AshitaCore's GUI manager, and a raise from the lookup would escape
        -- this handler exactly as the failed render would have.
        pcall(function () imgui.End(); end);
        pcall(function () imgui.PopStyleVar(1); end);
    end

    incursion.render_off = true;

    pcall(printf, 'Render error, window disabled: %s -- /incursion to try again.',
          tostring(err));
```

### WR-04: HARD-04's non-empty glyph requirement drops a boon permanently, with no fallback tier

**Status: FIXED** (`51f5cb5`) — `%([^)]+%)` is now `%([^)]*%)`: the
`)`-exclusion kept, the emptiness rule dropped, the name guard alongside it
left to do the discriminating. `BOON_REF` in the harness follows to
`([^)]*)`. Suite 1 stayed at exactly 11819 and suite 2 at exactly 1, which is
what says the loosening reached nothing real. Two checks pin it, and the
second is the one that tells the two halves of HARD-04 apart:
`Aura (Signet) (<glyph>): Attack+5` keeps the name whole under `[^)]` and
loses `(Signet)` under a lazy `.-`. Negative control run both ways — `+`
fails the empty-glyph check, `.-` fails the `)`-exclusion check.

**File:** `inctrack/parser.lua:251`

**Issue:** The glyph class went from `%(.-%)` to `%([^)]+%)`. `[^)]` is the
useful half of the change (it stops the lazy `.-` skipping over a `)`), but the
`+` adds a second, separable rule: the glyph group must be **non-empty**.
Confirmed:

```
'Godwen gains the effect of Warding Aura (): Attack+5'  ->  nil
```

That rule buys no discriminating power. What separates a boon from an ordinary
buff is the ` (…): <stats>` tail plus a non-blank name — `gains the effect of
Protect.` has no tail at all, empty group or not. So the `+` narrows only
against the server, not against false positives, and it does so on a path with
**no fallback**: HARD-02 kept the 1.1.0 shape underneath, HARD-04 did not.
A boon whose icon field is unset in a server data table (template
`%s gains the effect of %s (%s): %s`) renders `()` and vanishes silently and
permanently — boons are never re-announced, and this is one of the `MUST_SAVE`
events precisely because of that.

The 127-log corpus is evidence that today's glyphs are non-empty. It is not
evidence that every future one will be, and the corpus is also gathered on raw
log lines that never pass through `strip_colors()`, which the live path applies
at `inctrack/inctrack.lua:183`.

**Fix:** keep the `)`-exclusion, drop the emptiness rule; the name guard added
alongside it is what actually does the work.

```lua
    function(s)
        local who, name, stats = s:match('^(%S+) gains the effect of (.-) %([^)]*%): (.+)$');
        if who then
            name = trim(name);
            if name ~= '' then
                return { t = 'boon', who = who, name = name, stats = trim(stats) };
            end
        end
    end,
```

`MUST_PARSE` at `test/run_tests.py:116` already writes the glyph group as
`\(.*\)`, so the corpus guard is on the looser side of this either way; the
Python `BOON_REF` at `test/run_tests.py:148` needs the matching `[^)]*`.

### WR-05: a session the new validator rejects is discarded with no word to the player

**Status: FIXED** (`2ef924c`) — with one qualification the review does not
mention. Both call sites now go through a shared `resume()` that prints on the
discard path, so the load handler and the profile switch answer alike. But a
*finished* run is exempt: `restore()` refuses those on purpose, every completed
Incursion leaves exactly such a blob in settings, and complaining there would
put a false alarm on every login after a run — the same fault pointed the
other way. Pinned by 7 checks, including the no-false-alarm case. Negative
controls run in both directions: removing the message turns 2 checks red, and
removing the finished-run exemption turns 1 red.

**File:** `inctrack/inctrack.lua:150-159`

**Issue:** The load handler prints `Resumed run in %s.` on success and says
nothing at all on failure — it clears `settings.session` and moves on. That
was tolerable when the only rejection paths were unreadable JSON, a finished
run and a three-hour-old blob. HARD-05 widens the surface to *every* shape
mismatch, and CR-01 above shows one such path is reachable from ordinary
server text.

What the player sees is a mid-run reload where the HUD comes back with nothing,
and then — as soon as the next Incursion-tagged line arrives — a bootstrapped
run at phase `nil`, `phases_cleared 0` and an elapsed counter starting from
zero (`inctrack/state.lua:179-182` sets `recovered` but no `desynced` flag, so
there is no `reconnected - awaiting update` banner either). That is a window
showing numbers the server never sent, with no uncertainty marking: the exact
condition the core value forbids.

**Fix:** one line on the discard path, so the loss is visible rather than quiet.

```lua
        if ok and type(blob) == 'table' and incursion.state:restore(blob) then
            printf('Resumed run in %s.', tostring(blob.instance));
        else
            printf('Saved run could not be resumed (unreadable, stale or of an unexpected shape); starting fresh.');
            incursion.settings.session = '';
            settings.save();
        end
```

The same applies to the profile-switch path at `inctrack/inctrack.lua:393-398`.

---

## Info

**Status for IN-01 … IN-04: not addressed.** This fix pass was scoped to
critical and warning findings. IN-03 is additionally a case the review itself
recommends leaving alone this milestone.

**IN-05 has since been re-decided and fixed** (2026-08-29, milestone audit
G-1). It is the one finding this review left explicitly open pending a
decision, and the decision is recorded below and in
`.planning/v1.2.0-MILESTONE-AUDIT.md`.

### IN-01: `opt_table` is defined and never used

**File:** `inctrack/state.lua:657`
**Issue:** Dead code. `opt_number`, `opt_string` and `opt_boolean` all have call
sites; `opt_table` has none — the table-shaped fields are each checked by their
own `valid_*` helper.
**Fix:** delete the line.

### IN-02: `not data.instance` at the top of `restore()` is now dead

**File:** `inctrack/state.lua:764`
**Issue:** `valid_session` re-tests `instance` a few lines later and more
strictly, so the early gate can never be the reason a blob is refused. Harmless,
but it reads as a live guard and will drift out of step with the validator.
**Fix:** reduce line 764 to `if type(data) ~= 'table' then return false; end`
and let `valid_session` own the `instance` rule (see CR-01 for what that rule
should be).

### IN-03: `split_mobs` has no fallback tier, so a comma-only list would draw a fabricated name

**File:** `inctrack/parser.lua:45-60`
**Issue:** The symmetric risk to the one HARD-03 removed. Confirmed:
`'... enemies (A,B)'` now yields the single mob `'A,B'` where 1.1.0 yielded
`A` and `B`. If the server ever emits a list without the space, the window
draws one name it never sent — the same harm, in the other direction, and with
no fallback underneath (HARD-02 kept one). The 469-line corpus survey is the
whole of the evidence.
**Fix:** no change recommended for this milestone; the tradeoff was made
knowingly. Worth pinning as an explicit test case with a comment naming the
accepted risk, so a future reader does not have to re-derive it.

### IN-04: the pre-`Begin` residual set is larger than the comment enumerates

**File:** `inctrack/inctrack.lua:288-292`
**Issue:** The `opts.locked` residual is assessed as **genuinely unreachable**:
`ImGuiWindowFlags_NoMove` is defined by the same load of Ashita's `imgui.lua`
as the four flags `ui.lua:404-407` reads unconditionally, and `render_ok` cannot
be set unless those four resolved. For it to fire, that one constant would have
to be absent while its four siblings are present.

But two more statements sit before the window opens and are covered by the same
assumption without being named: `imgui.PushStyleVar` itself
(`inctrack/ui.lua:412`) and `imgui.Begin` (`inctrack/ui.lua:425`). A raise from
either on a `render_ok` host makes `pcall(imgui.End)` an unmatched close, just
as `opts.locked` would. All three are host-level rather than data-driven, which
is what makes the design sound — the comment should say so, rather than naming
one of the three.
**Fix:** extend the residual paragraph to name all three and state the shared
justification (no data reaches any of them) once.

### IN-05: `opt_number` admits NaN and ±inf into the clock arithmetic

**Status: FIXED** (2026-08-29, as milestone audit G-1) — but *not* as the fix
below proposes, and the difference is the whole of the re-decision this finding
asked for.

The suggestion below is "fail the blob", and it notes correctly that this
collides with CR-01's proportionality problem: refusing a live run over one bad
field costs boons, points, phase and elapsed that the server never sends again.
CR-01 settled that the validator answers *what shape is this*, never *is this
informative*. Failing the blob would have reversed that a second time.

What was decided instead is that a NaN is neither the right value nor a wrong
shape — it is **no value at all**. There is nothing a NaN could be said to be.
So it is read exactly as a **missing key** would be: `state.lua`'s new
`finite()` turns a NaN or ±infinity into `nil` at each of the fifteen places
`restore()` reads a number out of the blob, that one field comes back unknown,
and the rest of the run comes back whole. Neither the run refused nor the
number kept.

That keeps CR-01's rule intact — the validator still never judges whether a
number is informative — while closing the core-value breach the audit
demonstrated, where a restored session drew
`~-9223372036854775808:-9223372036854775808:-9223372036854775808` as the
instance clock. A blank string and a NaN are the same case except in what they
draw: a blank draws nothing, so the run keeps it; a NaN draws garbage, so the
field goes and the run stays.

Pinned by 117 checks across the state, ui and persistence suites (the last
driving `1e999` through Ashita's own `json.lua`, which decodes it to `+inf` on
both dialects). Negative-controlled four ways on both backends: neutering
`finite()` turns 92 checks red on Lua 5.5 and 94 on LuaJIT 2.1, and dropping the
NaN, the ±infinity and the −infinity clauses individually turns 31/32, 61/62 and
29/29 red.


**File:** `inctrack/state.lua:654`, consumed at `inctrack/state.lua:820`,
`889-895`
**Issue:** `type(v) == 'number'` is true for NaN. A `time_left` of NaN passes
`gap > data.time_left + 60` (false), passes `run.time_left < 0` (false), and
reaches `clock_str` in `ui.lua`, where `string.format('%d:%02d', …)` on a NaN
raises under Lua 5.3+ and prints garbage under LuaJIT. Not reachable from
`serialise()`; reachable from a hand-edited file if the decoder accepts `nan` /
`1e999`. HARD-01's containment now catches the consequence, which is why this
is Info rather than a warning.
**Fix:** if tightened later, `type(v) == 'number' and v == v and v ~= math.huge
and v ~= -math.huge` — but note the "reject, never coerce" rule means this must
fail the blob, and that interacts with CR-01's proportionality problem.

---

## Out-of-phase notes

- Nothing found belonging to PERF-01…04 or DOC-01/02 that is not already on
  `03-03-SUMMARY.md`'s carry-forward list. The nine carry-forwards there
  (including the unrate-limited `parse error:` line and IN-07's integer/float
  question) were checked and are **not** re-raised.
- The `right_text` / `Complete 48m 44s` alignment item is confirmed as intended
  behaviour, not a defect, per `03-CONTEXT.md`.
- The persistence suite **skipped** in this review's run (`Ashita json.lua not
  found`). CR-01 and WR-01 were both reproduced without it, but the encoding of
  empty tables and of numeric-looking object keys through Ashita's real decoder
  remains unverified here.

---

_Reviewed: 2026-08-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

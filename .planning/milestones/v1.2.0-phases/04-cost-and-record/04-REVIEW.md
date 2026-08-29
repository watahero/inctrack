---
phase: 04-cost-and-record
reviewed: 2026-08-29T09:24:59Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - inctrack/inctrack.lua
  - inctrack/parser.lua
  - inctrack/ui.lua
  - test/run_tests.py
  - test/stubs.py
  - docs/design.md
  - README.md
  - CHANGELOG.md
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: fixed
fixed_at: 2026-08-29
fix_scope: critical_warning
fixed: 8
skipped: 0
deferred: 4
fix_report: .planning/phases/04-cost-and-record/04-REVIEW-FIX.md
---

# Phase 04: Code Review Report

**Reviewed:** 2026-08-29T09:24:59Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The phase is well engineered and the reasoning in the comments is unusually
honest, but two defects in it are load-bearing and both sit in the two hot
paths the phase touched.

The first is the one the phase's own risk register was pointed at and missed:
`parser.relevant`'s colour-marker fall-through recognises **two** of the
**three** marker bytes Ashita's `strip_colors` actually strips. The third,
`0x7F`, is verifiable in the shipped host source on this machine
(`Ashita/addons/libs/sugar/string.lua:1044-1046`,
`self:gsub('[' .. string.char(0x1E, 0x1F, 0x7F) .. '].', '')`). The gate's
stated rule is "a line carrying a code is one this function is not entitled to
judge"; that rule is applied to two thirds of the codes the shell itself then
removes. The failure mode is the exact one the design says is unacceptable — a
silent, permanent false negative on a line the server really did send. The test
harness cannot catch it because `test/stubs.py`'s `strip_colors` stub encodes
the same wrong marker set.

The second is a protection that PERF-02 removed without noticing. `persist()`
used to run inside `text_in`'s `pcall`; it now runs at the top of `d3d_present`
with nothing around it. `inctrack.lua`'s own header argues at length that an
error in the frame handler "is not a log line" — and then places an unprotected
disk write there, above the `pcall` that exists for exactly that reason.

Beyond those, the documentation rewrite — which this phase claims as a
deliverable, and which is checked here as a real review dimension — carries
three provably wrong statements, and the test harness's line citations into the
shipped Lua have drifted by 40 to 280 lines almost everywhere.

Verified as correct, and explicitly not flagged: the needle set is a genuine
superset of every matcher under every optional group, alternation and
two-attempt fallback (checked one matcher at a time, including the
`minutes?`/`Minutes?` splits and the empty `%([^)]*%)` glyph group); the
`FRAME_OPTS` table is read and dropped by `ui.render` with no retention or
mutation; the memo cache cannot drop mid-lookup (the hit returns before the cap
test, and `short_held` cannot drift from the entry count because a hit never
re-inserts); `ui.forget()` has exactly two callers and both are correct; the
unload write is unconditional and is pinned by a test that would notice if it
stopped being; the flush is genuinely above both early returns and both are
pinned.

## Critical Issues

### CR-01: The colour-marker fall-through misses Ashita's third marker byte, so the gate can still silently drop a real line

**FIXED** — `459d17b`, with `00cc3e5`. Pinned by the addon suite's needle-hiding pin, now run once per marker byte.


**File:** `inctrack/parser.lua:401-413` (the guard is at `:402`)

**Issue:**

```lua
function parser.relevant(line)
    if line:find('\30', 1, true) or line:find('\31', 1, true) then
        return true;
    end
```

Ashita's shipped `strip_colors` — the very call this gate runs in front of,
`inctrack.lua:261` — strips **three** marker bytes, not two:

```lua
-- Ashita/addons/libs/sugar/string.lua:1044-1046
string_mt.strip_colors = function (self)
    return (self:gsub('[' .. string.char(0x1E, 0x1F, 0x7F) .. '].', ''));
end
```

`0x7F` (`\127`) is absent from the gate. The consequence is precisely the
scenario the fall-through was written to make impossible: a marker/payload pair
landing inside one of the seven needles. A line such as

```
Incursio\127Nn [Fort Ghelsba] Begins! (Normal)
```

contains none of `Incursion [`, `New Objective: `, `Bonus Objective: ` or
`(Boss: `, carries neither `\30` nor `\31`, and is therefore rejected by
`relevant()` before `strip_colors` ever runs — while the shell's own strip would
have turned it into a perfectly ordinary `Begins!` line. Nothing is logged,
nothing is drawn differently, and the window simply never appears.

The comment at `:355-364`, the summary at `04-01-SUMMARY.md:234`, and
`docs/design.md:127-131` all assert that Ashita's codes are "a marker byte
(`\30` or `\31`)". That premise is wrong, and every argument built on it — "a
false negative is impossible rather than unlikely" — is only two thirds true.

The corpus argument does not cover this either: `04-01-SUMMARY.md:226` records
**zero** colour-marker bytes across all 2,951,129 lines, because Ashita's
chatlog writer strips them on write. The fall-through has no empirical backing
at all, which is precisely why it must be a superset of the host's own strip
rather than a survey result.

**Fix:** make the gate's marker set match `strip_colors`'s exactly, and say so
in the comment so the two stay coupled:

```lua
-- The marker bytes Ashita's own strip_colors removes -- 0x1E, 0x1F and 0x7F
-- (addons/libs/sugar/string.lua). This set must stay a superset of that one:
-- a marker the shell strips but this gate does not judge itself unentitled to
-- read is a line lost before strip_colors ever runs.
function parser.relevant(line)
    if line:find('\30', 1, true)
        or line:find('\31', 1, true)
        or line:find('\127', 1, true) then
        return true;
    end
```

Fix `test/stubs.py`'s stub in the same change (WR-01) or the suite will stay
green through the defect, and correct the "two escape forms" claim in
`parser.lua:356-364` and `docs/design.md:127-131`.

---

### CR-02: `persist()` runs unprotected inside `d3d_present`, undoing the protection it had before PERF-02

**FIXED** — `9d85dc5` (containment, retry, report-once), `0e9786b` (docs/design.md's boundary list), `c0a3b8f` (CHANGELOG). Pinned by 24 new addon-suite checks against a stub whose `settings.save()` can be made to raise.


**File:** `inctrack/inctrack.lua:369-372`

**Issue:**

```lua
if incursion.save_due then
    incursion.save_due = false;
    persist();
end
```

`persist()` calls `incursion.state:serialise()`, `pcall(json.encode, blob)` and
`settings.save()`. Only the encode is protected. `serialise()` and — far more
importantly — `settings.save()`, which is Ashita's synchronous disk write, are
not. Before PERF-02 this whole call ran inside `text_in`'s `pcall`
(`04-02-SUMMARY.md:169`: *"Until this plan all of that ran inside `text_in`"*),
so a raise from it was caught, reported once, and cost one line. It is now the
first statement of the frame handler with nothing around it.

The consequences, in the order they bite:

1. A raise escapes `d3d_present` onto the game thread every addon in the
   process shares — the exact failure mode this file's own header
   (`:337-344`) and the entire `render_off` / stack-repair apparatus exist to
   prevent. The flush was placed *above* the render `pcall`, so it is outside
   the containment rather than inside it.
2. `ui.render` never runs on that frame, so the window blanks for a frame with
   no explanation.
3. The player is told nothing. Every other failure path in this addon has a
   report-once latch (`render_off`, `parse_told`); this one has none.
4. The write is dropped. The flag was cleared first, deliberately, so nothing
   retries it; recovery depends entirely on some later chat event happening to
   set the flag again.
5. It recurs. `save_due` is set again on the next qualifying event, so a
   persistent I/O fault (read-only settings file, full disk, locked file)
   raises out of `d3d_present` once per owed write for the rest of the session.

Nothing in `test/run_tests.py` or `test/stubs.py` provokes a failing
`settings.save()` — the stub's save cannot fail — so this is unpinned as well
as unprotected.

`docs/design.md:559-575` lists "Three protected boundaries" and describes the
frame handler's boundary as the render `pcall` alone. It does not mention that
a disk write now runs above it, unprotected.

**Fix:** contain it exactly as the render is contained, with the same
report-once discipline. Keep the flag consumed before the write:

```lua
if incursion.save_due then
    incursion.save_due = false;
    -- Contained for the same reason as the render below: this is the frame
    -- handler, and a raise here reaches every addon in the process. The flag
    -- is already consumed, so a fault costs this write and not a retry loop;
    -- the next owed write tries again, and the unload path is unconditional.
    local ok, err = pcall(persist);
    if not ok and not incursion.save_told then
        incursion.save_told = true;
        pcall(function ()
            printf('Could not write the run down: %s -- further failures '
                   .. 'this session will not be reported.', tostring(err));
        end);
    end
end
```

Declare `save_told = false` beside `parse_told` in the `incursion` table, and
clear it in `reset()` and in the profile-switch callback alongside the other
two latches. Add a stub hook that makes `settings.save()` raise, and a check
that one frame with a failing save neither escapes the handler nor stops the
next frame drawing.

## Warnings

### WR-01: The test stub's `strip_colors` does not match Ashita's, which blinds the suite to CR-01 and inflates the PERF-04 figures

**FIXED** — `00cc3e5`. Marker set and gsub count both corrected; PERF-04 figures and `REJECT_BASELINE` re-recorded against the corrected stub.


**File:** `test/stubs.py:835-846`

**Issue:** The stub is documented as *"Ashita's two colour-code escape forms are
a marker byte followed by one payload byte"* and implemented as:

```lua
function string.strip_colors(s)
    __host_strip_calls = __host_strip_calls + 1;
    local out = tostring(s):gsub('\30.', '');
    out = out:gsub('\31.', '');
    return out;
end
```

Two divergences from the shipped host, both material:

1. **Wrong marker set.** `0x7F` is missing, so the harness models a host that
   does not strip it. This is why the otherwise excellent safety pin at
   `test/run_tests.py:3953-3969` — which plants `CC_B` inside `Incursion ` and
   asserts the run still starts — cannot see CR-01: `CC_A`/`CC_B`
   (`run_tests.py:190-191`) only ever use `\x1e` and `\x1f`.
2. **Wrong gsub count.** Ashita does it in one `gsub` with a character class;
   the stub does two. The PERF-04 suite counts `gsub` calls to produce its
   figures, so every "old shape" cost is inflated by one allocation per line
   (`run_tests.py:5143-5147` even asserts the *claim* "two gsubs and two
   allocations"). The recorded baseline at `run_tests.py:234-241`
   (285,562 lines/s) and the `ratio >= 1.2` check at `:5171` are both measured
   against an old shape that costs more than the real one did. The improvement
   is real; the reported size of it is not honest.

**Fix:**

```lua
-- Ashita's colour codes are three marker bytes -- 0x1E, 0x1F and 0x7F -- each
-- followed by one payload byte, stripped in a single gsub with a character
-- class (addons/libs/sugar/string.lua:1044-1046). Both the byte set and the
-- gsub count matter: the set is what the reject-gate's fall-through must be a
-- superset of, and the count is an input to the PERF-04 figures.
function string.strip_colors(s)
    __host_strip_calls = __host_strip_calls + 1;
    return (tostring(s):gsub('[\30\31\127].', ''));
end
```

Then add `CC_C = "\x7f\x31"` to `run_tests.py:190`, include it in
`REJECT_COLOURED`, add a `\x7f`-coded variant to the needle-hiding pin at
`:3953-3969`, and re-record `REJECT_BASELINE` — its `commit`/`date` provenance
fields make that a supported operation.

---

### WR-02: `parser.lua`'s module header still says the module has one function

**FIXED** — `ab79894`. Pinned by the new `record` suite.


**File:** `inctrack/parser.lua:10-12`

**Issue:**

```lua
* Pure Lua. No Ashita dependency, no state. One function:
*
*     parser.parse(line) -> event table, or nil if the line is not ours.
```

The module now exports two, and the second one (`parser.relevant`, `:401`) is
the highest-stakes function in the file — it decides whether a line is parsed at
all, and it is called directly from `inctrack.lua:256`, not only through
`parse`. A reader who trusts the header will not know the shell has its own
entry point into this module, which is exactly the coupling CR-01 turns on.

**Fix:**

```lua
* Pure Lua. No Ashita dependency, no state. Two functions:
*
*     parser.relevant(line) -> boolean. Could this line possibly be ours?
*         Allocation-free, runs on the raw message, and is a deliberate
*         superset: it may produce false positives but never false negatives.
*         The shell calls it before strip_colors; parse calls it again on
*         entry so the module is safe standalone.
*
*     parser.parse(line) -> event table, or nil if the line is not ours.
```

---

### WR-03: "seven `string.find` searches" undercounts the reject path by two

**FIXED** — `5848d25`. The number is **ten**, not nine: CR-01 added a third marker search. Pinned by the `record` suite, counted from `parser.relevant`'s own body.


**File:** `inctrack/parser.lua:350`, `docs/design.md:114`

**Issue:** Both say a "no" from `relevant()` costs seven searches. It costs
**nine**: the two marker searches at `:402` must both fail before the seven
needles are tried, and all seven must then fail. `parser.lua:350-351` compounds
it — *"a 'no' here costs seven searches over a short string and nothing else.
The number of searches is fixed and does not depend on the input"* — the second
sentence is what makes the first checkable, and it is checkable and wrong.

This is small, but it is a cost claim in a phase whose whole subject is cost,
in the one function whose budget is the argument for its existence.

**Fix:** in `parser.lua:350`:

```lua
* string, so a 'no' here costs nine searches over a short string and nothing
* else -- two for the marker bytes below, then the seven needles. The number
```

and in `docs/design.md:114`, replace "It is seven `string.find` searches" with
"It is nine `string.find` searches — two for the colour markers, then seven
needles".

---

### WR-04: The "roughly one frame" residual is stated as an absolute in three places, and omits the failure mode that does not need a crash

**FIXED** — `9d85dc5` (`inctrack.lua`, in the comment block CR-02 had to rewrite) and `c9bc2be` (`docs/design.md`, `README.md`). Pinned by the `record` suite, one check per file per fact.


**File:** `inctrack/inctrack.lua:361-367`, `docs/design.md:243-248`,
`README.md:117-122`

**Issue:** All three say the same thing — *"between the chat line and the next
frame there is a window of roughly one frame in which the run is not on disk,
and a crash inside it loses that one event."* Two problems:

1. **The bound is not one frame.** It is "until the next `d3d_present`", which
   the addon does not control. `d3d_present` is driven by the client's Present
   hook; a minimised or background-throttled client, an alt-tab, or a stalled
   frame extends the window arbitrarily. The unload handler covers *orderly*
   departures, and the profile-switch callback deliberately discards
   `save_due` (`:563`) — but a client killed while minimised loses everything
   since the last frame that actually ran, which may be much more than one
   frame's worth.
2. **A crash is not required.** As CR-02 establishes, a raise inside
   `persist()` drops the owed write with the flag already cleared, and nobody
   is told. The residual as written implies the only way to lose the write is
   to die inside the gap.

The project's standard is that residuals are *stated rather than hidden*. This
one is stated at a size that is not the size it is.

**Fix:** in `inctrack.lua:361-367`, replace the residual paragraph with:

```lua
* The residual, stated rather than hidden: the run is not on disk between the
* chat line and the next frame that actually runs. That is normally about one
* frame, but the bound is 'the next d3d_present', not '16 ms' -- a minimised
* or background-throttled client can stretch it, and a client killed there
* loses everything since the last frame that ran. The unload handler covers
* every orderly departure. The other way to lose the write is a raise inside
* persist(): the flag is already consumed, so nothing retries, which is why
* that raise is caught and reported rather than left silent.
```

Mirror the same correction in `docs/design.md:243-248` and `README.md:117-122`.

---

### WR-05: `docs/design.md`'s suite count contradicts both the table under it and the harness

**FIXED** — `371c520`. The answer is **eleven suite functions, thirteen result lines** once this review's own `record` suite is counted. `run_tests.py`'s docstring and `run_suite`'s docstring carried the same confusion and are corrected; `.planning/WINDOWS.md` entry 2 is closed.


**File:** `docs/design.md:587`

**Issue:**

> Eleven suites, reported as twelve result lines — the parser suite emits three:

The table immediately below lists **twelve** rows. `test/run_tests.py` calls
`run_suite()` **ten** times (`:5231, 5232, 5239, 5240, 5242, 5244, 5245, 5247,
5248, 5252`), and `test_parser` returns three `Result`s
(`return coverage, dormant, whole`), giving twelve result lines from ten suite
functions. "Eleven" matches neither number, and the sentence contradicts itself:
if the parser suite emits three of the twelve lines, the suite count cannot be
eleven with a twelve-row table.

The provenance makes this worse rather than better: `04-03-SUMMARY.md:502-509`
records this exact line being written as the *fix* for a miscount found in the
plan, verified only by `grep -cF "Seven suites"` returning 0 — a check that
cannot distinguish a right answer from a differently wrong one.

**Fix:**

```markdown
Ten suite functions, reported as twelve result lines — the parser suite emits
three (coverage, the dormant generic tier, and the over-reach guard):
```

If a check is wanted, count `run_suite(` occurrences rather than grepping for
the old wording.

---

### WR-06: The harness's line citations into the shipped Lua are stale almost everywhere

**FIXED** — `e6eddf4`. All 27 citations re-anchored to searchable tokens and walked by the `record` suite.


**File:** `test/stubs.py:80-82, 190, 557, 685, 709, 745-748, 824, 835, 854`;
`test/run_tests.py:3184-3185, 3777, 3862, 4681`

**Issue:** The harness's comments pin each stub to the exact shipped statement
it models — a good discipline, and the reason the phase's own ledger caught four
drifted citations in the plan. That discipline was applied to `docs/design.md`
and not to the test files. Verified against the current sources:

| Citation | Says it points at | Actually points at |
|---|---|---|
| `stubs.py:709` — `inctrack.lua:80` | `now()` | mid-comment; `now()` is at `:111` |
| `stubs.py:745` — `inctrack.lua:127` and `:177` | `GetMemberName(0)` | `reset()`; actual calls at `:205` and `:271` |
| `stubs.py:748` — `inctrack.lua:176-181` | deferred name fetch | `resume()`'s comment; actual `:270-275` |
| `stubs.py:824` — `inctrack.lua:281` | `settings.register` | mid-comment; actual `:548` |
| `stubs.py:835` — `inctrack.lua:167` | `strip_colors()` | `resume()`'s comment; actual `:261` |
| `stubs.py:854` — `inctrack.lua:229` | `string:args()` | the unload handler; actual `:468` |
| `stubs.py:81` — `ui.lua:67` | `origin_x` default | layout comment; actual `:110` |
| `stubs.py:82`, `:557` — `ui.lua:408` | `origin_x = GetCursorPosX()` | memo-cache comment; actual `:512` |
| `stubs.py:191` — `ui.lua:98` | `right_text`'s overflow branch | `CONTENT_W` comment; actual `:140` |
| `stubs.py:685` — `ui.lua:28` | `require('imgui')` | layout comment; actual `:71` |
| `run_tests.py:3777` — `inctrack.lua:160` | the `text_in` `pcall` | `resume()`'s comment; actual `:244` |
| `run_tests.py:3862`, `stubs.py:1200` — `inctrack.lua:156` | the read-only guarantee | `resume()`'s comment; actual `:237-242` |
| `run_tests.py:4681` — `inctrack.lua:219-222` | the manual-hide branch | the `load` handler |

`run_tests.py:2957` (`ui.lua:15-26`) is the one that is right — it is the
comment this phase corrected.

A citation that points at unrelated code is worse than none: it sends a reader
to the wrong statement with the confidence of a reference.

**Fix:** re-anchor each to a searchable identifier rather than a line number,
which is the shape that does not rot:

```python
# ... the now() at inctrack.lua (`local function now`) ...
# ... right_text's overflow branch in ui.lua (`if target > imgui.GetCursorPosX()`) ...
```

If line numbers are kept, add a harness check that greps each cited file:line
for an expected token, so drift fails the suite instead of accumulating.

## Info

### IN-01: `coloured()` is defined and never called, and encodes the same wrong marker set

**DEFERRED** — Info, out of this pass's scope. Note that `coloured()` still encodes the two-marker set CR-01 corrected; it is dead code, so nothing reads it, but it is the last surviving copy of the wrong premise.


**File:** `test/run_tests.py:244-246`

**Issue:** Dead code. It also hardcodes `"\x1e" in line or "\x1f" in line`,
which is a third copy of the CR-01 premise waiting to be trusted by whoever
does eventually call it.

**Fix:** delete it, or use it to build `REJECT_COLOURED`/`REJECT_FREE` (which
currently partition the corpus by slice index, `:211-219`) and correct its byte
set at the same time.

---

### IN-02: `install_ashita()` is documented as public harness API and never called

**DEFERRED** — Info, out of this pass's scope.


**File:** `test/stubs.py:1363` (documented at `:20`)

**Issue:** `install_imgui` is used at `run_tests.py:450`; `install_ashita` has
no call site anywhere in `test/`. Callers construct `AshitaHost` directly.

**Fix:** delete it and its docstring entry, or route `Host.__init__` through it
so the documented entry point is the one that runs.

---

### IN-03: `CHANGELOG.md` says a line the addon ignores "costs nothing", which is not true of a coloured line

**DEFERRED** — Info, out of this pass's scope. Re-checked against the standing 'correct the changelog if it now overclaims' constraint: the "costs nothing" wording was already an overclaim before this pass and is not made newly wrong by it, so it is left for a deliberate decision rather than folded in here.


**File:** `CHANGELOG.md:30-31`

**Issue:** *"A chat line the addon does not care about now costs nothing — it is
turned away before anything is built for it."* By design
(`04-03-SUMMARY.md:476`), a line carrying a colour code still pays a full
`strip_colors` — 1 strip and 2 gsubs per line by the suite's own printed
figures. The unqualified "nothing" is the only overclaim in an otherwise
carefully hedged changelog. The rest of the entry is accurate, including the
deliberately modest framing of the write policy and the memo bound.

**Fix:** *"A chat line the addon does not care about now costs almost nothing —
it is turned away before anything is built for it."*

---

### IN-04: `ui.render`'s return value is dead

**DEFERRED** — Info, out of this pass's scope.


**File:** `inctrack/ui.lua:485, 530`; consumed at `inctrack/inctrack.lua:390`

**Issue:** `render` returns `opts.visible` on both paths. The only caller is
`local ok, err = pcall(ui.render, incursion.state, FRAME_OPTS)`, which discards
it. Since `FRAME_OPTS.visible` is now a hoisted constant `true`
(`inctrack.lua:328`), the function returns a constant nobody reads — and the
docstring at `:479-482` still explains what the return "means".

This interacts mildly with the `FRAME_OPTS` hoist: `visible = true` is correct
only because `d3d_present` returns above the render when the window is off. That
invariant is now split across two files with a comment in each. It holds today.

**Fix:** drop the two `return opts.visible` statements and the paragraph
describing them, leaving `opts.visible` unread — or keep the field and have
`render` early-return on `not opts.visible`, which would make the hoisted `true`
a fact rather than a promise the shell has to keep.

---

_Reviewed: 2026-08-29T09:24:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Fixed: 2026-08-29 by Claude (gsd-code-fixer) -- see 04-REVIEW-FIX.md_

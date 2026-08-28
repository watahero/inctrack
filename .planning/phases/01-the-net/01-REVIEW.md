---
phase: 01-the-net
reviewed: 2026-08-28T22:01:09Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - test/stubs.py
  - test/run_tests.py
findings:
  critical: 1
  warning: 8
  info: 12
  total: 21
status: fixed
fixed_at: 2026-08-29
fixed_commits: d0db28a 94e748b e731dee 9517409 05f6560 55a80a6 0e793e9 9e11e05 bc616dc
---

# Phase 1: Code Review Report

**Reviewed:** 2026-08-28T22:01:09Z
**Depth:** standard
**Files Reviewed:** 2 (`test/stubs.py`, `test/run_tests.py`)
**Status:** findings

## Summary

The harness does what the phase set out to do: `ui.lua` and `inctrack.lua` are
executed as shipped, the stubs live entirely in `test/`, `inctrack/` is
untouched, and the run is green with exactly three expected failures. The
assertions in the new suites are, with two exceptions, real assertions — they
compare against intent, not against observed output, and they are written so a
refactor inside the addon does not falsely fail them.

Three things need fixing before this is a load-bearing safety net:

1. **The six inline window snapshots are pinned to one Lua backend.**
   `stubs._num` branches on the *Python* type of a number, which depends on
   which Lua `lupa.LuaRuntime` selected. Verified: `python test/run_tests.py`
   passes on the bundled Lua 5.5 and produces **six failures** when the same
   code runs on `lupa.luajit21` — the dialect Ashita actually runs. The failures
   name `ui.lua` and are entirely spurious.

2. **The FIX-03 assertion can be satisfied by drawing nothing at all.** It is a
   disjunction whose first term (`not offered_close`) is true whenever no
   `Begin` was recorded. A Phase 2 change that stops the window rendering turns
   the defect test green.

3. **`origin_x = imgui.GetCursorPosX()` (ui.lua:408) is not covered**, because
   the stub's `PADDING` is 8.0 and ui.lua's file default for `origin_x` is 8.
   Verified by deleting that line from a copy of `ui.lua`: under LuaJIT the
   recorded call log is byte-identical, and under Lua 5.5 it is caught only by
   an int-vs-float rendering accident with a message that says nothing about the
   cause.

The three xfail assertions were each traced against `state.lua` and `ui.lua`.
**FIX-01 (`:654`) and FIX-02 (`:707`) are durable** — both are stated as deltas
or as tolerance windows, and every legitimate fix I could construct (deriving
`phases_cleared` from phase numbers, suppressing the increment after a
`bonus_done`, ageing `started`/`time_left`/`expires_at` by `os.time() -
saved_at`) turns them green without editing them. **FIX-03 (`:1773`) is durable
in the positive direction** — I confirmed against the stub that both intended
fixes (drop the `p_open` table; drop `NoTitleBar`) flip it — but it is not
guarded against the degenerate case above.

## Critical Issues

### CR-01: Snapshot number formatting depends on which Lua backend `lupa` picked, so six windows fail on LuaJIT

**FIXED** (d0db28a) -- `_num` normalises to float before formatting, so 252 and 252.0 both render `252`; the six inline windows were re-pasted from the recorder. A second backend dependency surfaced while verifying and was fixed in the same commit: module-level `lupa.lua_type` only recognises proxies from the Lua that a plain `lupa.LuaRuntime()` resolves to, so under LuaJIT the p_open box in a recorded `Begin` was not seen as a table and the suite crashed rather than merely diffing; `stubs.lua_type` now dispatches on the proxy's own module. `INCTRACK_LUA` pins the backend and the run header prints the resolved implementation. Verified: identical check counts and PASS on lua51, lua52, lua53, lua54, lua55, luajit20 and luajit21, and a full 2.94M-line chatlog replay under luajit21.

**File:** `test/stubs.py:291-297` (`_num`), consumed by `test/run_tests.py:1278-1467`
**Issue:**

```python
def _num(value):
    if isinstance(value, bool): ...
    if isinstance(value, int):
        return "%d" % value
    return "%.2f" % value
```

`lupa` maps Lua numbers to Python types differently per backend. On the Lua 5.5
build bundled with `lupa` 2.8 (the current default), `13` from
`ImGuiStyleVar_ItemSpacing` arrives as a Python `int` → `"13"`, while `252.0`
from `SetCursorPosX` arrives as a `float` → `"252.00"`. On `lupa.luajit21` —
the dialect Ashita actually embeds, and the one this addon ships against — every
Lua number is a double and `lupa` converts integral doubles to Python `int`, so
`252.0` renders as `"252"`.

Verified on this machine:

```
$ python test/run_tests.py                       # Lua 5.5
  ui: helpers, layout contract, render   53 checks  ok (1 known defects)

$ # same code, lupa.luajit21
  ui: helpers, layout contract, render   53 checks  FAILED (6)
      FAIL the mid-phase window is not the one the layout contract describes:
           line 8 drew 'SetCursorPosX 252', expected 'SetCursorPosX 252.00'
      ... (five more, one per window)
```

`lupa` ships `lua51`, `lua52`, `lua53`, `lua54`, `lua55`, `luajit20` and
`luajit21`; which one `lupa.LuaRuntime` resolves to varies with the `lupa`
version and how it was built. Any contributor whose install resolves to LuaJIT
gets six red lines blaming `ui.lua` for a defect in the recorder, and the
milestone-wide "the full suite is green" guarantee is false for them. This is
the same class of problem the phase exists to prevent, on the wrong side of the
harness.

**Fix:** normalise before formatting instead of branching on the Python type, so
the rendering is identical on every backend. Pick one canonical form and adjust
the six inline windows once:

```python
def _num(value):
    """Integers plainly, fractions to two decimals -- diffable either way,
    and identical on every Lua backend lupa may resolve to (LuaJIT hands
    back an int for an integral double; Lua 5.4+ hands back a float)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    value = float(value)
    if value == int(value):
        return "%d" % int(value)
    return "%.2f" % value
```

With that, `252.0` and `252` both render `"252"`, and the six windows lose their
`.00` suffixes. Consider also pinning the backend explicitly in `make_lua()` /
`Host.__init__` (`from lupa import lua54` or similar) and printing the resolved
`lua.lua_implementation` in the run header, so a mismatch is visible rather than
inferred from six confusing diffs.

## Warnings

### WR-01: The FIX-03 assertion is satisfied when no window is drawn at all

**FIXED** (94e748b) -- `res.check(bool(begins), ...)` now runs before the xfail; the xfail condition itself is untouched.

**File:** `test/run_tests.py:1769-1775`
**Issue:**

```python
begins = [args for name, args in close_host.imgui.calls if name == "Begin"]
offered_close = any(len(args) > 1 and lupa.lua_type(args[1]) == "table"
                    for args in begins)

res.xfail((not offered_close) or still_shown is False, ...)
```

If `begins` is empty — `ui.render` returned early because `state:snapshot()` was
nil, or a regression stopped the window rendering — then `offered_close` is
`False`, `not offered_close` is `True`, and the expected failure reports **NOW
PASSING** for a frame in which nothing happened. The exactly-three guard then
fails with "the run reported 2", pointing at the wrong thing. This is precisely
the accidental-satisfaction hole the phase's own criterion 4 is meant to close,
and it sits in the one assertion Phase 2 is forbidden to edit.

**Fix:** assert the precondition separately, before the xfail, so the disjunction
can only be reached once a window is known to exist:

```python
res.check(bool(begins),
          "the close-button case drew no window at all, so nothing was "
          "proved about the close button either way")

res.xfail((not offered_close) or still_shown is False,
          "the window asks for a close button and then ignores it -- "
          "clicking close leaves the window on screen")
```

### WR-02: The exactly-three guard counts xfails but never checks which three, and ignores `fixed`

**FIXED** (9517409) -- `Result.xfail` takes a required defect id, `EXPECTED_DEFECTS = {FIX-01, FIX-02, FIX-03}` is compared as a set, and a populated `fixed` list now fails the run. `EXPECTED_XFAILS` is kept as the count guard. Verified: setting `EXPECTED_XFAILS = 2` exits 1; swapping FIX-03 for FIX-99 with the count still at 3 exits 1; an early fix plus a new xfail (count still 3, previously green) exits 1.

**File:** `test/run_tests.py:2280-2286`
**Issue:** `known = sum(len(s.xfails) for s in suites)` compared against
`EXPECTED_XFAILS`. The docstring at `:46-47` claims "a fourth failure -- or a fix
that landed before its red line could prove anything -- fails the run", but the
guard cannot distinguish identity. A fix that lands early (one xfail moves to
`fixed`) *plus* any newly-introduced xfail leaves `known == 3` and the run green,
with a "NOW PASSING" line printed and no consequence attached to it. `Result.fixed`
is populated and printed and then never used for anything.

**Fix:** make the guard identity-based, and make an unexpectedly-passing xfail
loud in the exit code — the whole point of the mechanism is that a green line is
as significant as a red one during this phase:

```python
    known = sum(len(s.xfails) for s in suites)
    early = sum(len(s.fixed) for s in suites)
    print()
    print("  %d known defects (expected until Phase 2)" % known)
    if known != EXPECTED_XFAILS or early != 0:
        print("  guard: this phase closes on exactly %d known defects and no "
              "early fixes; the run reported %d and %d"
              % (EXPECTED_XFAILS, known, early))
        ok = False
```

Stronger still: give each xfail a stable id (`"FIX-01"`, …) as a third argument
and compare the collected set against a literal
`{"FIX-01", "FIX-02", "FIX-03"}`, so a swap cannot pass.

### WR-03: `ui.lua:408` (`origin_x = imgui.GetCursorPosX()`) is not covered — the stub's padding equals the addon's default

**FIXED** (e731dee) -- the stub's `PADDING` is 11.0, `ImGuiRecorder.padding` exposes it, and `test_ui` asserts `origin_x == recorder.padding` after a render. The six windows were re-pasted (every position moved by 3px). Verified: deleting `origin_x = imgui.GetCursorPosX();` from a copy of `ui.lua` now produces 7 named failures, identically on Lua 5.5 and LuaJIT; previously the LuaJIT log was byte-identical.

**File:** `test/stubs.py:59` (`local PADDING = 8.0`), `test/run_tests.py:1505-1507`
**Issue:** `ui.lua:67` declares `local origin_x = 8;` as its file default, and
`ui.lua:408` overwrites it with `imgui.GetCursorPosX()` inside `Begin`. The stub
resets its cursor to `PADDING = 8.0` in `Begin`, so `GetCursorPosX()` returns
exactly the value `origin_x` already had. Every right-alignment and wrap
position in all six windows is therefore identical whether or not `ui.lua:408`
executes.

Verified: with `origin_x = imgui.GetCursorPosX();` deleted from a copy of
`ui.lua`, the recorded call log under LuaJIT is byte-for-byte identical
(`SetCursorPosX 273`, `PushTextWrapPos 308`, `SetCursorPosX 224` in both cases).
Under Lua 5.5 two of six windows fail — but only because the deletion changes
`308.0` to `308`, i.e. by the same type accident as CR-01, with a diff line
(`'PushTextWrapPos 308' vs 'PushTextWrapPos 308.00'`) that names nothing useful.

The suite claims whole-window coverage of `render`; one of `render`'s eleven
statements is invisible to it.

**Fix:** make the stub's padding distinguishable from the addon's default, so
capturing it is observable, and read `origin_x` after a render rather than
before:

```python
# test/stubs.py
# Deliberately not 8: ui.lua's file default for origin_x is 8, and a stub
# padding of 8 would make `origin_x = imgui.GetCursorPosX()` (ui.lua:408) a
# no-op that no snapshot could ever catch.
PADDING = 11.0
```

Then add one assertion in `test_ui` that `origin_x` equals the stub's padding
after a render:

```python
after = float(lua_locals(host, ui.render)["origin_x"])
res.check(after == float(host.imgui._s["padding"]),
          "the window did not take its left edge from ImGui, so every "
          "right-aligned value is measured from a guess: %r" % after)
```

(The six inline windows shift by 3px and must be re-pasted once.)

### WR-04: The "read-only chat handler" guarantee is asserted against an event table that lacks the fields the real host reads back

**FIXED** (05f6560) -- `stubs.TEXT_IN_FIELDS` carries the real Ashita v4 `text_in` shape and `AshitaHost.fire_text_in` fires it; every `text_in` in the shell suite goes through it, and the read-only assertions now cover `message_modified`, `mode_modified` and `indent_modified`. Verified: a copy of `inctrack.lua` that sets `e.message_modified` is caught, where before it passed.

**File:** `test/stubs.py:950-961` (`AshitaHost.fire`), asserted at `test/run_tests.py:1882-1896`
**Issue:** `fire()` builds the event table purely from the kwargs the test passes:

```python
e = self.lua.table_from(dict(fields))
handler(e)
return e
```

So for `text_in` the table contains only `message`. Ashita v4's `text_in` event
carries `mode`, `indent`, `message`, `mode_modified`, `indent_modified`,
`message_modified`, `blocked` and `injected`, and the host reads the
`*_modified` fields — writing to `e.message` is *not* how an addon rewrites
chat. The assertions

```python
res.check(e["message"] == ordinary, "the chat handler rewrote an ordinary line")
res.check(e["blocked"] is None, "the chat handler blocked an ordinary line")
```

therefore guard the wrong field. A future change that set `e.message_modified`
would rewrite the player's chat in game and every one of these checks would
still pass. (`blocked` is genuinely covered, because a handler writing it makes
the key appear.)

**Fix:** build the event with the shape the real host supplies, and assert the
fields it actually reads:

```python
TEXT_IN_FIELDS = {
    "mode": 0, "indent": 0, "message": "",
    "mode_modified": None, "indent_modified": None, "message_modified": None,
    "blocked": None, "injected": False,
}

def fire_text_in(self, message):
    fields = dict(TEXT_IN_FIELDS)
    fields["message"] = message
    return self.fire("text_in", **{k: v for k, v in fields.items()
                                   if v is not None})
```

and in `test_addon_shell`:

```python
res.check(e["message_modified"] is None and e["mode_modified"] is None,
          "the chat handler rewrote the line the player sees")
```

### WR-05: The whole-window balance check omits the style-colour stack while claiming to cover "the ImGui stacks"

**FIXED** (55a80a6) -- `bal["style_color"] == 0` added to the whole-window balance check.

**File:** `test/run_tests.py:1720-1722`
**Issue:**

```python
res.check(bal["window"] == 0 and bal["style_var"] == 0,
          "the %s window left the ImGui stacks unbalanced: %r" % (name, bal))
```

`ImGuiRecorder.balance()` returns three counters and the message says "the ImGui
stacks", but `style_color` is never asserted. `bar()` is the only pusher today
and it pops in the same call, so there is no current signal — which is exactly
why the omission will survive until it matters. A window that leaves a colour
pushed tints every frame drawn after it, and the comment two lines above says
Phase 3 leans on this check.

**Fix:**

```python
res.check(bal["window"] == 0 and bal["style_var"] == 0
          and bal["style_color"] == 0,
          "the %s window left the ImGui stacks unbalanced: %r" % (name, bal))
```

### WR-06: `first_diff` strips each line, so a nesting-only difference reports "identical"

**FIXED** (0e793e9) -- `first_diff` compares raw lines; the no-difference return now reads "identical apart from trailing whitespace". Verified: an indentation-only difference reports the line and both renderings.

**File:** `test/run_tests.py:1260-1268`
**Issue:**

```python
a = g[i].strip() if i < len(g) else "<end of window>"
b = w[i].strip() if i < len(w) else "<end of window>"
```

Indentation in the snapshot *is* the `Begin`/`End` nesting depth
(`ImGuiRecorder.snapshot` at `stubs.py:399-411`). If a change alters only the
depth — an extra `Begin`, a missing `End`, a section drawn one level deeper —
every stripped line matches, the loop runs to completion, and the failure reads:

```
the mid-phase window is not the one the layout contract describes: identical
```

which is the least useful message a diff can produce, on the failure mode the
suite most wants to catch.

**Fix:** compare the raw lines and only strip for display:

```python
def first_diff(got, want):
    """Where two windows first disagree, as one readable line."""
    g, w = got.splitlines(), want.splitlines()
    for i in range(max(len(g), len(w))):
        a = g[i] if i < len(g) else "<end of window>"
        b = w[i] if i < len(w) else "<end of window>"
        if a != b:
            return "line %d drew %r, expected %r" % (i + 1, a, b)
    return "identical apart from trailing whitespace"
```

### WR-07: Nothing ever cross-checks the stubbed json against Ashita's real `json.lua`

**FIXED** (9e11e05) -- `test_json_roundtrip` now decodes Ashita's output with the stub, re-encodes it with the stub, decodes that with Ashita's json and restores it into a `State`, comparing instance, phase, kills, boss, bonus, the unknown counter and the raw-high-byte boon name. Compared through the JSON text rather than the table, because a Lua proxy belongs to the runtime that built it. The two encoders do produce different text (key order, and `boons: []` vs `{}`), so this is a real comparison. Persistence suite: 20 -> 25 checks, green.

**File:** `test/stubs.py:612-904` (JSON_CHUNK), `test/run_tests.py:1946`
**Issue:** the shell suite proves the save/resume round trip *through the stub*
(`saver.json.decode(saver.sessions[-1])`, and `loaded_host(profile={"session":
...})` re-encoding and re-decoding with the same stub). Suite 8 proves the round
trip through Ashita's real `json.lua`. No test compares the two. The stub is
noticeably more permissive and more opinionated than a typical `json.lua` — it
emits bytes ≥ 0x80 raw rather than `\u`-escaped (`stubs.py:643-648`), it encodes
an empty table as `{}` and never `[]`, it sorts object keys, and it accepts a
leading `+` on numbers. If the stub accepts or produces something the real
library does not, the shell suite is green and the shipped addon loses the
player's in-progress run on the next reload — the exact failure the persistence
code exists to prevent.

**Fix:** when `libs` is available, assert the two agree in `test_json_roundtrip`
(which already has both in hand). It costs four lines and closes the gap:

```python
    # The shell suite round-trips through the stubbed json; prove the two
    # encoders agree, or that suite is green against a fiction.
    stub = stubs.AshitaHost(lua_for_stub).json     # or a small helper runtime
    blob = s.serialise(s)
    res.check(js.decode(stub.encode(blob))["instance"] == blob["instance"],
              "the harness's json writes something Ashita's json cannot read")
    res.check(stub.decode(js.encode(blob))["instance"] == blob["instance"],
              "the harness's json cannot read what Ashita's json writes")
```

### WR-08: A regression in `State:restore` turns FIX-02 into a traceback instead of a reported failure

**FIXED** (bc616dc) -- the `restore` and `snapshot` dereferences in the state suite are guarded, with stand-in values chosen so the assertion that follows still fails rather than passing on a sentinel; the FIX-01 and FIX-02 conditions are unchanged. The same crash shape existed in other suites (`test_disconnect:1064` among them), so `run_suite()` now turns any suite-level exception into a reported failure with the traceback on stderr. Verified: with `State:restore` forced to return false in a copy of `state.lua`, the run reports 7 named failures across three suites and exits 1, where before it produced a bare traceback with no report at all and the known-defect guard never ran.

**File:** `test/run_tests.py:698-715`
**Issue:**

```python
res.check(bool(f3.restore(f3, blob)),
          "a run saved ten minutes ago was thrown away as too old")

back_left = float(f3.time_left(f3))
back_elapsed = float(f3.elapsed(f3))
```

`Result.check` accumulates rather than aborts — that is its documented contract
(`CONTEXT.md`: "failures accumulate rather than abort"). But if `restore`
returns false, `f3.time_left()` returns nil, `float(None)` raises `TypeError`,
`test_state_units` never returns, and `main()` dies before any suite reports or
the exactly-three guard runs. A named state regression becomes an unhandled
traceback that takes the whole phase guarantee down with it. The same shape
appears at `:632` (`int(f1.snapshot(f1)["phases_cleared"])` would raise if the
snapshot were nil).

**Fix:** guard the dereference and let the xfail record a failure instead:

```python
    restored = bool(f3.restore(f3, blob))
    res.check(restored,
              "a run saved ten minutes ago was thrown away as too old")

    back_left = float(f3.time_left(f3)) if restored else 0.0
    back_elapsed = float(f3.elapsed(f3)) if restored else 0.0
    back_bonus = f3.bonus(f3) if restored else False   # not None: not a pass
```

## Info

**Not addressed this pass.** The fix scope was Critical + Warning. IN-01, IN-03,
IN-08 and IN-11 describe harness quality rather than a hole in what the suite
proves; IN-02, IN-04, IN-06, IN-07 and IN-09 are about stub reach that only
matters once Phase 2 and Phase 3 need it; IN-05 and IN-10 are cosmetic. Two are
worth carrying forward explicitly:

  * **IN-09** (the ImGui stub has exactly the fourteen entry points ui.lua uses
    today) is a live risk for Phase 2: a close control drawn manually would hit
    `attempt to call a nil value` inside `render`. That is now a *reported*
    failure rather than a bare traceback (see WR-08), but it is still a crash
    rather than a named diff.
  * **IN-06**'s empty-table divergence (`[]` vs `{}`) was observed directly
    while verifying WR-07: Ashita's json writes `"boons":[]` for an empty run
    and the stub writes `"boons":{}`. The fixture used by the cross-check has a
    boon, so the two agree there; a run with no boons at all would not.

### IN-01: Dead public surface in `test/stubs.py`

**File:** `test/stubs.py:1016-1023`, `:947-948`, `:979-981`, `:1001-1008`, `:463`, `:237-238`, `:356-358`; `test/run_tests.py:1218`
**Issue:** the module docstring advertises two entry points, `install_imgui(lua)`
and `install_ashita(lua)` — but `install_ashita` is never called: `Host.__init__`
constructs `stubs.AshitaHost` directly. Also never read anywhere: the `aliases`
property and the `__host_aliases` table it wraps, `strip_colors_calls` and
`__host_strip_calls`, `wall()` (the entire wall-clock-ageing capability), the
`__host_epoch` global (written from Python, never read from Lua),
`S.px_per_char`, `S.padding`, and `ImGuiRecorder.counts`. `render_case`'s `opts`
parameter is never passed a non-`None` value.
**Fix:** either route `Host.__init__` through `install_ashita` so the documented
API is the used one, or drop the wrapper and correct the docstring. Delete or
annotate the rest — the `strip_colors_calls`/`wall()` pair are explicitly
forward-looking (Phase 4 PERF-01, and offline ageing), so a one-line
`# unused until Phase N` beats silence.

### IN-02: The event registry keys on event name, not on alias

**File:** `test/stubs.py:482-489`
**Issue:** `__host_events[event] = fn` — a second registration for the same event
name silently replaces the first. Real Ashita keys handlers by `(event, alias)`
and runs all of them. `inctrack.lua` registers one handler per event so nothing
is wrong today, but the stub cannot represent an addon that registers two.
**Fix:** store a list per event and have `fire()` invoke each in registration
order; keep `events` returning the first for the existing call sites.

### IN-03: Snapshot rendering can be silently lossy or non-deterministic for value shapes it does not expect

**File:** `test/stubs.py:279-288` (`_color_map`), `:300-323` (`_render`)
**Issue:** `_color_map` inverts name → colour into components → name; two COLOR
entries with identical RGBA would collapse to whichever `pairs()` yielded last,
making the snapshot non-deterministic. `_render` of a Lua table uses `_seq`,
which returns `[]` for a string-keyed table (silent data loss), and falls through
to `str(value)` for a function — which embeds a memory address in the snapshot.
None of these are reachable from `ui.lua` today.
**Fix:** raise or emit a marker rather than degrade: `return "<map:%d>" %
len(list(value.keys()))` for a non-array table, `"<function>"` for a function,
and assert in `_color_map` that no two names share an RGBA key.

### IN-04: `string.args()` splits on whitespace only

**File:** `test/stubs.py:603-609`
**Issue:** Ashita's `string.args()` honours quoting (`/inc "two words"` →
`{'/inc', 'two words'}`); the stub does not. `inctrack.lua` reads only `args[1]`
and `args[2]`, so nothing is wrong today, but a future subcommand taking a
quoted argument would behave differently in the harness than in game.
**Fix:** note the limitation in the comment, or implement quote handling.

### IN-05: Several shell assertions pin the stub's chat formatting rather than the addon's

**File:** `test/run_tests.py:1863`, `:2124`, `:2130`, `:2144`, `:2150`
**Issue:** `banner[0].startswith("[inctrack] ")` and
`toggles.chat[-1].endswith("Window locked.")` hold only because
`stubs.py:528-531` makes `chat.header(n)` return `'[' .. n .. '] '` and
`chat.message` the identity. Ashita's real `chat.header` emits colour escapes.
The underlying intent (the addon passes `addon.name`, the addon reports the new
state) is real; the literal form is the stub's.
**Fix:** assert the invariant instead of the rendering, e.g.
`res.check(addon_name in banner[0] and version in banner[0], ...)`.

### IN-06: json stub edge cases that diverge from JSON

**File:** `test/stubs.py:687-710`, `:786-802`, `:885-888`
**Issue:** an empty Lua table always encodes as `{}`, never `[]`, so an empty
array does not survive as an array; `null` inside an array assigns `nil` and
leaves a hole while the index counter keeps advancing, corrupting `#`;
`parse_number` accepts a leading `+`, which JSON forbids. None is reachable from
`State:serialise()` today.
**Fix:** document the three as deliberate, or reject `+` and error on `null`
inside an array so a future caller finds out rather than getting a silently
shortened list.

### IN-07: `Begin` always returns true, so the collapsed-window path is never exercised

**File:** `test/stubs.py:195-218`
**Issue:** real ImGui's `Begin` returns false when the window is collapsed or
clipped, and `ui.lua:407-421` correctly skips the body while still calling
`End()`. The stub returns `true` unconditionally, so the skip branch has no
coverage.
**Fix:** add a `collapse()` switch alongside `arm()` that makes the next `Begin`
return false, and one assertion that `End`, `PopStyleVar` and the return value
still behave.

### IN-08: The measurement model is an invention, and `SameLine` adds no item spacing

**File:** `test/stubs.py:56` (`PX_PER_CHAR = 7.0`), `:98-101` (`drew`), `:133-136`
**Issue:** `CalcTextSize` returns a single number (Ashita's binding returns
`x, y`; harmless because `ui.lua:95` uses it only in arithmetic), measures bytes
rather than glyphs, and `SameLine` sets the cursor to the previous item's end
with **no** `ItemSpacing.x` — although `ui.lua:404` explicitly pushes
`ItemSpacing = {4, 2}`. Every recorded `SetCursorPosX` in the six windows is
therefore systematically ~4px per preceding `SameLine` away from what real ImGui
computes, and the `target > GetCursorPosX()` branch outcome in `WINDOW_FINISHED`
(no `SetCursorPosX`) is decided by that invented metric.
**Fix:** model the pushed `ItemSpacing.x` in `SameLine` (the stub already
records the `PushStyleVar` value), or state in the header comment that the
absolute pixel numbers in the snapshots are recorder arithmetic and only their
relative relationships carry meaning.

### IN-09: The ImGui stub covers only the entry points `ui.lua` uses today, which will bite Phase 2

**File:** `test/stubs.py:116-222`
**Issue:** the stub table has exactly the fourteen functions `ui.lua` calls now.
FIX-03's fix may well introduce a new one — a small close control drawn manually
(`imgui.SmallButton`, `imgui.IsItemClicked`), or a context menu
(`imgui.BeginPopupContextWindow`). Any of those raises "attempt to call a nil
value (field 'X')" inside `render`, which surfaces as a lupa exception mid-suite
rather than a named failure.
**Fix:** give the stub a metatable that records and no-ops unknown entry points
while flagging them in the snapshot, so a new call shows up as an explicit
`<unstubbed:SmallButton>` line rather than a crash:

```lua
setmetatable(imgui, { __index = function (t, k)
    return function (...) record('<unstubbed:' .. k .. '>', ...); end;
end });
```

### IN-10: Snapshot strings are quoted without escaping

**File:** `test/stubs.py:314-315`
**Issue:** `return "'" + value + "'"` — the fixture instance name
`Crawlers' Nest Depths` renders as `'Crawlers' Nest Depths'`, which is ambiguous
to a reader and would collide if two different strings ever quoted the same way.
**Fix:** use `repr(value)` (which escapes and picks a quote character), or escape
the single quote.

### IN-11: `Host.addon` flattens two files' upvalue namespaces into one dict

**File:** `test/run_tests.py:200-215`, `:146-173` (`UPVALUE_CHUNK`)
**Issue:** the walk descends through `ui.render` (an upvalue of the
`d3d_present` handler), so `host.addon` contains `inctrack.lua`'s locals *and*
`ui.lua`'s (`COLOR`, `origin_x`, `bar`, `shorten`, …) in a single flat map.
`out[name] = value` is last-writer-wins in BFS order, so a future name shared
between the two files resolves silently and arbitrarily.
**Fix:** either scope the walk (`lua_locals(host, fn)` per handler, as the
docstring implies) or make the collision detectable:

```lua
if out[name] ~= nil and out[name] ~= value then
    error('upvalue name collision: ' .. name);
end
```

### IN-12: FIX-01 depends on `__clock` being 0 on entry, implicitly

**File:** `test/run_tests.py:617-663`
**Issue:** FIX-02 immediately below sets `lua.globals()["__clock"] = 0`
explicitly and restores it at `:717`, with a comment explaining why. FIX-01 does
neither — it relies on nothing earlier in `test_state_units` having moved the
shared clock. That happens to be true today; inserting one clock-moving fixture
above it would change `elapsed` and, if the phase logic ever grows a time
component, the result.
**Fix:** add `lua.globals()["__clock"] = 0` at the top of the FIX-01 block, the
way FIX-02 does.

---

_Reviewed: 2026-08-28T22:01:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Fixed: 2026-08-29 by Claude (gsd-code-fixer) -- CR-01 and WR-01..WR-08 fixed, Info deferred_

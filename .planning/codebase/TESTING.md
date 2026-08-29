# Testing Patterns

**Analysis Date:** 2026-08-29

## Test Framework

**Runner:** none. `test/run_tests.py` (6,255 lines) is a self-contained
harness with its own `Result` collector — no pytest, no unittest, no CI, no
build step. `test/stubs.py` (1,504 lines) supplies the Ashita and ImGui hosts.

**Dependency:** `lupa` only (`pip install lupa`). The harness loads the
*shipped* Lua from `inctrack/` into an embedded interpreter, so a pass means
the shipped code behaves, not a reimplementation. Nothing under `inctrack/` is
modified, mocked or wrapped.

**Run Commands:**
```bash
python test/run_tests.py                     # unit suites only
python test/run_tests.py <chatlog_dir>       # + replay of real chatlogs
INCURSION_CHATLOGS=<dir> python test/run_tests.py
INCTRACK_LUA=luajit21 python test/run_tests.py <dir>   # pin the Lua backend
```

Current full run (127 logs, 2,951,129 chat lines, character `Godwen`):

```
11 suite functions -> 13 result lines -> 13,461 checks -> PASS, 0 known defects
```

| Result line | Checks | Needs |
|---|---:|---|
| `parser: structural lines all parse` | 11,819 | chatlogs |
| `parser: generic tier matches nothing today` | 1 | chatlogs |
| `parser: tightened patterns keep every line whole` | 1 | chatlogs |
| `state: run reconstruction` | 888 | chatlogs |
| `state: objectives, bonus, recovery` | 204 | — |
| `adaptability: unseen content still tracked` | 119 | — |
| `disconnect: stale progress is not trusted` | 23 | — |
| `timers: countdown, linger, staleness` | 31 | — |
| `persistence: json round trip` | 46 | Ashita `json.lua` |
| `ui: helpers, layout contract, render` | 86 | — |
| `addon: load, chat, settings, commands` | 220 | — |
| `record: what the source and the docs say about themselves` | 17 | — |
| `cost: the non-Incursion reject path` | 6 | — |

`test_parser` is one function returning **three** Results; every other suite
returns one — that is why 11 functions print 13 lines. Both numbers are
themselves asserted by the `record:` suite against this harness's docstring and
against `docs/design.md`, because the arithmetic has been stated wrongly before.

`state: run reconstruction` is 888 checks = 8 assertions × **111 completed
runs** replayed out of the corpus.

## Skips

Skips are noted, never failed, and the run still reports `PASS`:
- **Without chatlogs** (`find_logs`): the four `[logs]` lines above simply do
  not run — `test_parser` and `test_replay` are never called, so the printed
  report drops to 9 lines. `main()` prints
  `chatlogs: none (pass a directory or set INCURSION_CHATLOGS ...)`.
- **Without Ashita's `json.lua`** (`find_ashita_libs`, looked for at
  `<Ashita>/addons/libs` beside the chatlogs or via `INCURSION_ASHITA_LIBS`):
  `test_json_roundtrip` returns early with
  `res.note("skipped: Ashita json.lua not found ...")` and 0 checks.
- `test_addon_shell` notes and skips its CHANGELOG assertions when
  `CHANGELOG.md` is absent.

The known-defect guard holds identically with and without chatlogs, because the
suites that carry defects always run.

## Test File Organization

Two files, no per-module test files. `test/run_tests.py` is the single entry
point; `test/stubs.py` is imported and is never run directly (no CLI). Suites
are numbered sections in file order, delimited by
`# ----- \n# N. <title>` banners.

## Test Structure

Each suite is a plain function returning a `Result`; `main()` wraps every call
in `run_suite`:

```python
def test_timers(lua, parser, State):
    res = Result("timers: countdown, linger, staleness")
    res.check(cond, "message a human can act on")
    res.note("context printed under the result line")
    return res
```

**`Result`** (`test/run_tests.py:684`) accumulates rather than aborts:
- `check(cond, msg)` — counts a check; a false condition appends to `failures`.
- `note(msg)` — prose printed under the result line (event kinds, corpus
  shape, benchmark figures, skip reasons).
- `xfail(cond, msg, defect)` — asserts behaviour the addon is *supposed* to
  have, knowing a defect makes it false. Counts as a check. A false condition
  is the expected failure (`xfails`); a condition that unexpectedly *holds*
  lands in `fixed`, which is loud and red — a defect that stopped reproducing
  before its own fix landed means the red line never proved anything.
- `report()` prints `title / checks / status` and returns `not failures`, so an
  expected failure still exits 0.

**`EXPECTED_XFAILS = 0` and `EXPECTED_DEFECTS = set()`** — both currently
empty. `main()` guards the *count* and the *set of defect ids* separately: a
count alone cannot tell three defects from three different ones, so one fix
landing plus one regression arriving would leave the total unchanged and the
run green. The three defects this milestone opened on (FIX-01 bonus payout
counted as a cleared phase, FIX-02 run clock not aged while unloaded, FIX-03
the close button the window asks for and ignores) are fixed and are ordinary
checks now. Any new `xfail` at all, or any regression re-reddening a fixed
line, fails the run.

**`run_suite`** turns a crash into a reported red suite rather than a traceback
that takes every other suite's report and the guard down with it.

## Runtimes: two of them, on purpose

**`make_lua()`** (`test/run_tests.py:406`) — one shared runtime with
`parser.lua` and `state.lua` loaded and an injected `__clockfn`. Eight suites
share it. Pure Lua only; no host.

**`make_host()` / `class Host`** (`test/run_tests.py:463`) — a **fresh, isolated
lupa runtime per host**, with the recording ImGui stub and the Ashita host
installed, so `ui.lua` (`short_cache`, `origin_x`) and `inctrack.lua` (one
`incursion` table) get clean module state per scenario instead of the suite
juggling `package.loaded`. Any scenario needing a pristine addon builds a new
host: `render_case`, `edge_host`, `blank_host`, `close_host`, `shape_host`,
`nf_host`, `loaded_host`, `bench_host`.

`Host.addon` exposes the shell's file-scope locals (`incursion`, `visible`,
`reset`, `persist`, `printf`, `now`, `MUST_SAVE`) resolved lazily over every
registered handler plus the profile-switch callback.

**Backend selection.** Which Lua sits behind lupa is not stable across installs
(lupa 2.8 ships lua51..lua55, luajit20, luajit21; Ashita embeds LuaJIT 2.1).
`lua_runtime()` honours `INCTRACK_LUA` and the resolved implementation is
printed in the run header, so a mismatch is visible rather than inferred. This
exists because the ui snapshots once depended on it — green on Lua 5.5 while six
failed on LuaJIT, blaming `ui.lua` for a recorder formatting choice.
`stubs.lua_type` dispatches on the proxy's own module for the same reason.

## Reaching file-scope locals

`lua_locals(host, fn)` (`test/run_tests.py:514`) walks upvalues transitively via
`debug.getupvalue`, following function-valued ones with a `seen` set so a cycle
cannot loop, and skipping `_ENV` so a global cannot be mistaken for a file-scope
local. It is injected as the Lua chunk `__gsd_upvalues` and raises a clear error
if `debug.getupvalue` is unavailable in the build.

```python
L = lua_locals(host, ui.render)
COLOR = L["COLOR"]        # also: clock_str, right_text, wrapped, bar, urgency,
                          # replace_plain, shorten, STAT_SHORT, CONTENT_W, origin_x
```

This is what lets `ui.lua`'s helpers be unit-tested **without exporting them**
— the addon's own convention forbids widening its surface for tests.

## Mocking: the host, never the addon

`test/stubs.py` supplies exactly the two hosts that do not exist outside the
game.

**`install_imgui(lua)` → `ImGuiRecorder`.** Every entry point `ui.lua` touches
appends `{ name, n, args }` to a log and bumps a per-name counter. Recording is
**strictly positional**: `n = select('#', ...)` is stored alongside `args`, so a
trailing `nil` and an omitted argument are distinguishable and an overload the
addon must not use cannot pass unnoticed (`imgui.Begin`'s `p_open` box is
checked this way). Cursor bookkeeping is one number — enough to make
`right_text`'s overflow branch reachable — and wrapping, real font metrics and
window sizing are explicitly **not** simulated. `balance()` checks the ImGui
stack is left even; `snapshot()` renders the recorded calls into the text
window the ui suite diffs.

**One-shot fault injector.** `arm_fault(name, contains=None)` and
`arm_lookup_fault(name)` arm exactly one raise, disarmed before raising so one
arming produces one raise. Substring matching is plain-text `find(..., true)`,
never a pattern — the substrings used contain a percent sign. For
stack-moving calls (`Begin`, `End`, `PushStyleVar`, `PopStyleVar`) the raise
happens *before* the call is logged: a refused push did not push, and logging
the attempt would put a phantom into `balance()`'s arithmetic. `arm_lookup_fault`
raises from the metatable `__index`, reproducing Ashita's constants-table
lookup so the harness can prove the shell's `pcall(function () imgui.End() end)`
closure shape is required.

**`install_ashita(lua)` → `AshitaHost`.** In-memory `addon`, `ashita.events`,
`AshitaCore`, `chat`, `settings`, plus a pure-Lua `json`. Offers `fire`,
`fire_text_in`, `saves`/`sessions`/`save_attempts`, `fail_saves`/`heal_saves`
(to drive the retry path), `set_party_name`, `switch_profile`, `tick`/`wall` for
the injected clocks, and opt-in `count_gsub`/`strip_colors_calls` counters.

## Fixtures and Data

Real Ashita chatlogs are the primary fixture: `load_lines` reads
`<Name>_YYYY.MM.DD.log`, `player_from_logs` takes the character off the
filename, `clean` strips timestamps, and `at(path, text, lineno)` formats a
console-safe location for every failure message. Unit suites use inline
synthetic lines fed through `feed(state, parser, lines)` against `PLAYER =
"Godwen"`.

`test_replay` re-derives every expected fact **straight from the raw text**
(`BEGIN`/`PHASE`/`POINTS`/`COMPLETE` regexes) and never from anything the state
machine produced, then compares eight facts per completed run in `verify_run`.

## The `record:` suite

`test_record` (`test/run_tests.py:5724`) pins what the source and the docs say
about themselves. Every check is of the form "the file says N and the file is
M": the module header must name every function the module exports, the header's
spelled-out function count must equal `len(parser.keys())`, the suite/result
counts in this harness's own docstring and `docs/design.md` must match reality,
and every quoted citation in the harness (≥20 of them, and that floor is itself
checked) must still be findable in the file it names. Nothing greps for a
phrase that must be absent — that check cannot tell a right answer from a
differently wrong one, which is how a documentation defect survived being
"fixed" once.

## The `cost:` benchmark

`test_reject_cost` (`test/run_tests.py:6004`, PERF-04) runs last, because it is
the only suite that reads a stopwatch and everything else has stopped competing
for the machine by then. It times two shapes — the Phase 3 reject path copied
into the harness at commit `a6a3577`, and the shipped one — over one fixed
24-line corpus (18 colour-free, 6 coloured), 3,000 iterations a pass, best of 3,
timed from Python because `os.clock`/`os.time` are stubbed inside the host.

It asserts *counters*, not wall time: per colour-free rejected line the old
shape costs 1.00 `strip_colors` + 4.33 `gsub` and the new one 0.00 + 0.00.
Counters and stopwatch never share a host (the counter is a Lua function in
front of a C one). The rate figures and the recorded baseline are printed as
**provenance, not a threshold**, along with a note that the 3.45x ratio is a
property of this corpus's colour mix — Ashita's log writer strips marker bytes,
so the player's real mix is not measurable here.

## Common Patterns

**Fault injection round trip:**
```python
host = make_host()
host.imgui.arm_fault("TextColored", contains="%")
host.fire("d3d_present")
# assert: render_off latched, stack balanced, one printed report, one only
```

**Save policy — every save asserted twice:** nothing written on the chat line
that delivered the event, then written on the next frame. The unload handler is
asserted to write unconditionally.

## What remains uncovered

- **No CI, no linter, no build step** — deliberate, deferred as v2 requirements
  PROC-01…04. The suite runs only when a human runs it.
- **Real ImGui layout**: wrapping, font metrics and window sizing are not
  simulated, so the window snapshots pin structure and text, not pixels.
- **The real Ashita host**: `settings.save()`, the GUI manager, and the game
  thread are stubs. The stack-repair path on a genuine over-pop is a C++
  assert no `pcall` reaches — stated in `inctrack/inctrack.lua`, provoked by no
  test.
- **The locked-path flags arithmetic** raising before `Begin` on a host where an
  unlocked frame has already drawn clean: nothing data-driven reaches it and no
  test provokes it.
- **The residual write window**: the run is not on disk between a chat line and
  the next `d3d_present`. Bounded by "the next frame", which a minimised client
  can stretch arbitrarily. Stated, not tested.
- **Line families absent from the corpus** are flagged by the parser suite
  itself (`no <kind> line in this corpus -- that family is unguarded`) rather
  than silently passing.
- **LuaJIT 2.1, the dialect Ashita ships**, is only exercised when a contributor
  sets `INCTRACK_LUA=luajit21`; the default run uses whatever lupa resolved.

---

*Testing analysis: 2026-08-29*

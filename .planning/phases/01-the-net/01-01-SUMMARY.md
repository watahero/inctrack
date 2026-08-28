---
phase: 01-the-net
plan: 01
subsystem: testing
tags: [lua, lupa, imgui, ashita, json, test-harness, stubs, upvalues, xfail]

# Dependency graph
requires: []
provides:
  - "test/stubs.py — a recording ImGui stub, the in-memory Ashita host fakes, and a pure-Lua json"
  - "make_host(player, profile) — an isolated Ashita + ImGui host in one call"
  - "lua_locals(host, fn) — upvalue reflection reaching ui.lua's and inctrack.lua's file-scope locals"
  - "Result.xfail(cond, msg) and an xfail-aware Result.report()"
  - "The pinned report markers 'XFAIL ' and 'NOW PASSING '"
affects: [01-02-ui-suite, 01-03-addon-shell-suite, 02-the-fixes, 03-hardening, 04-performance]

actuals:
  tokens: 19128
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Stub the host, never the addon — the suite keeps loading shipped Lua"
    - "A fresh lupa runtime per host, so file-scope module state is never shared between scenarios"
    - "Upvalue reflection instead of exporting helpers from the addon"
    - "Expected failures as a first-class assertion kind, reported distinctly and exiting 0"

key-files:
  created:
    - test/stubs.py
  modified:
    - test/run_tests.py

key-decisions:
  - "The stub bodies are Lua source chunks executed in the host runtime; Python handles read them back, so recording costs no Python/Lua boundary crossing per call"
  - "CalcTextSize is 7.0 px per character — a declared stand-in for font metrics that are deliberately not modelled"
  - "Window flag values are the upstream Dear ImGui ones; only their distinctness as powers of two is load-bearing"
  - "The json decoder scans character by character and never evaluates its input, so {a=1} raises (T-01-01)"
  - "os.clock and os.time are stubbed separately, because state.lua deliberately mixes two clocks with different epochs"
  - "wall(seconds) is an offset from a fixed EPOCH (1767225600) so serialised blobs are reproducible"
  - "_ENV is excluded from lua_locals so a global cannot be mistaken for a file-scope local"

patterns-established:
  - "make_host() vs make_lua(): the eight existing suites keep their single shared runtime untouched; new suites build isolated hosts"
  - "Snapshot testing via a normalised, indented, diffable call log with colour names resolved — no golden files on disk"
  - "Expected-failure markers are a cross-plan data contract, grepped from stdout rather than parsed from a report object"

requirements-completed: [COVR-01, COVR-02, COVR-03]

coverage:
  - id: D1
    description: "A lupa runtime can require('ui') and run ui.render with no Ashita install, and every ImGui call is recoverable from the call log"
    requirement: COVR-01
    verification:
      - kind: unit
        ref: "PLAN 01-01 Task 1 <automated> block — require('ui'), CalcTextSize determinism, both Begin shapes"
        status: pass
      - kind: unit
        ref: "arm_close with and without ImGuiWindowFlags_NoTitleBar; ui.render driven end to end against a real run record"
        status: pass
    human_judgment: false
  - id: D2
    description: "inctrack.lua loads to completion outside the game; all five handlers plus the profile-switch callback are captured and invocable"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "PLAN 01-01 Task 3 <automated> block — five events registered, host.addon resolves the shell's locals"
        status: pass
      - kind: integration
        ref: "load/text_in/command/d3d_present fired through the stub: chat captured, settings flipped, e.blocked read back, a window drawn"
        status: pass
  - id: D3
    description: "The stubbed pure-Lua json round-trips a run serialised by state.lua and rejects malformed input"
    requirement: COVR-02
    verification:
      - kind: unit
        ref: "round trip of nested object, array, string-keyed map, byte 0x81, percent sign, integer, boolean; {a=1}, {\"a\": , nope, [1,2 and {\"a\":1}x all raise"
        status: pass
    human_judgment: false
  - id: D4
    description: "Result.xfail records an expected failure, prints it on an 'XFAIL ' line (and 'NOW PASSING ' when the defect is gone), and never exits non-zero"
    requirement: COVR-03
    verification:
      - kind: unit
        ref: "PLAN 01-01 Task 3 <automated> block — marker prefixes, report() returns True, no XFAIL/FAILED substring in a NOW PASSING report"
        status: pass
    human_judgment: false
  - id: D5
    description: "The pre-existing eight suites are untouched and the addon source is byte-identical"
    verification:
      - kind: unit
        ref: "python test/run_tests.py — PASS, exit 0, header still reads 'chatlogs: none (...)'"
        status: pass
      - kind: unit
        ref: "python test/run_tests.py <chatlogs> — PASS, exit 0, 12821 checks, 0 FAILED lines"
        status: pass
      - kind: unit
        ref: "git diff --quiet -- inctrack/ && git diff --cached --quiet -- inctrack/"
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-08-28
status: complete
---

# Phase 1 Plan 01: The Net Summary

**A recording ImGui stub, in-memory Ashita fakes and a pure-Lua json that let the suite load and run all 734 previously-unreachable lines of `ui.lua` and `inctrack.lua`, plus `make_host()`, upvalue reflection into the addon's file-scope locals, and an expected-failure mechanism that reports distinctly without turning the run red.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-08-28T20:53:00Z
- **Completed:** 2026-08-28T21:16:00Z
- **Tasks:** 3
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `ui.lua` is executable outside the game. A lupa runtime resolves `require('imgui')` to a recording stub and drives the whole `ui.render` tree — header, objective bar, mob list, boss hint, bonus, extras, stats, boons, note — with every call recoverable from an ordered log.
- `inctrack.lua` loads to completion outside the game. All five Ashita handlers and the settings profile-switch callback are captured and callable from Python, with an in-memory settings store, a captured console, deterministic clocks and a party name that can be withheld and then supplied.
- The addon's file-scope locals are reachable without editing the addon. `lua_locals` walks upvalues transitively and names all eleven `ui.lua` helpers and constants plan 01-02 needs, and the six shell locals plan 01-03 needs.
- `Result.xfail` exists and is counted, and the two report markers plans 01-02 and 01-03 grep for are pinned.
- The eight existing suites are byte-for-byte identical in their per-suite check counts, and `inctrack/` is untouched.

## Task Commits

1. **Task 1: The recording ImGui stub** — `86356f0` (feat)
2. **Task 2: The Ashita host fakes and the pure-Lua json stub** — `602d7e9` (feat)
3. **Task 3: make_host(), upvalue reflection, and Result.xfail** — `9811c00` (feat)

## Files Created/Modified

- `test/stubs.py` (new, 1023 lines) — the ImGui recorder, the Ashita host fakes, the pure-Lua json. No `__main__`, no CLI; `python test/run_tests.py` remains the single entry point.
- `test/run_tests.py` (+170 / -5) — `Host`, `make_host()`, `lua_locals()`, `UPVALUE_CHUNK`, `Result.xfail`, `Result.status()`, an xfail-aware `Result.report()`, and an updated suite index in the module docstring.

---

## The contract plans 01-02 and 01-03 are written against

Everything below is fixed. Do not paraphrase any of it.

### The two report markers, verbatim

| Marker | Literal | Meaning |
|---|---|---|
| Expected failure | `XFAIL ` | uppercase, exactly one trailing space, then the message |
| No longer failing | `NOW PASSING ` | uppercase, exactly one trailing space, then the message |

They are also available as `run_tests.XFAIL_MARK` and `run_tests.FIXED_MARK`.

- Every expected-failure line begins with `XFAIL ` (after report indentation, which is six spaces).
- **Nothing else the harness prints contains the substring `XFAIL`.** The suite status column reads `ok (N known defects)`, never anything containing `XFAIL`.
- Every no-longer-failing line begins with `NOW PASSING ` and contains neither `XFAIL` nor `FAILED`.
- An xfail never makes the process exit non-zero: `Result.report()` still returns `not self.failures`.

Status column, for reference:

| Condition | Status text |
|---|---|
| no failures, no xfails | `ok` |
| no failures, N xfails | `ok (N known defects)` |
| any real failure | `FAILED (n)` |

`Result` fields: `checks` (incremented by both `check` and `xfail`), `failures`, `notes`, `xfails` (the expected failures), `fixed` (conditions that unexpectedly held).

### The host handle — the exact public surface

`make_host(player=PLAYER, profile=None)` returns a `run_tests.Host`, a subclass of `stubs.AshitaHost`. A **fresh** `lupa.LuaRuntime()` is built per call, with the same `package.path` and `__clock` / `__clockfn` bootstrap `make_lua()` uses. `make_lua()` and the eight suites sharing its runtime are untouched.

| Member | Signature / type | Meaning |
|---|---|---|
| `lua` | `lupa.LuaRuntime` | the runtime; a different object for every host |
| `require(name)` | `-> module` | require inside that runtime (truncated to one value; Lua 5.4+ `require` returns two) |
| `imgui` | `stubs.ImGuiRecorder` | the ImGui recorder handle (see below) |
| `events` | `dict[str, luafunction]` | event name -> registered handler, read live from the registry |
| `aliases` | `dict[str, str]` | event name -> the alias the addon registered under |
| `fire(event, **fields)` | `-> lua table` | build the event table from kwargs, call the handler, return the table so `e["blocked"]` is readable back |
| `chat` | `list[str]` | captured console lines (the addon's `print` is redirected) |
| `settings` | lua table | the live settings table the addon holds |
| `saves` | `int` | how many `settings.save()` calls happened |
| `sessions` | `list[str]` | the `session` string recorded at each save |
| `switch_profile(dict)` | `-> lua table` | merge over the recorded defaults, install as the live table, fire the profile-switch callback |
| `profile_callback` | luafunction or None | the callback registered at inctrack.lua:281 |
| `set_party_name(name)` | `-> None` | what `AshitaCore` reports as party member 0; `""` keeps it withheld |
| `tick(seconds)` | `-> None` | **set** the monotonic clock (also mirrors into `__clock`) |
| `wall(seconds)` | `-> None` | **set** the wall clock to `stubs.EPOCH + seconds` |
| `strip_colors_calls` | `int` | how many times `string:strip_colors()` ran |
| `json` | lua table | the stubbed json module |
| `addon` | `dict[str, value]` | inctrack.lua's file-scope locals, resolved lazily over all five handlers plus the profile-switch callback |

`stubs.EPOCH == 1767225600` (2026-01-01 00:00:00 UTC). `os.time()` is seeded there so serialised blobs are reproducible; `os.clock()` starts at 0. They are separate on purpose — `state.lua` deliberately mixes two clocks with different epochs, so `wall(4 * 60 * 60)` ages a snapshot past `STALE_SECONDS` without moving a single run timer.

`lua_locals(host, fn) -> dict[str, value]` walks upvalues transitively from `fn`, following function-valued upvalues, tracking visited functions so a cycle cannot loop, and skipping `_ENV`. Confirmed reachable from `ui.render`: `clock_str`, `right_text`, `wrapped`, `bar`, `urgency`, `replace_plain`, `shorten`, `STAT_SHORT`, `COLOR`, `CONTENT_W`, `origin_x`, plus `short_cache` and the seven `draw_*` functions. Confirmed reachable from `host.addon`: `incursion`, `visible`, `reset`, `persist`, `printf`, `now`, `MUST_SAVE`.

### The ImGui recorder

`stubs.install_imgui(lua) -> ImGuiRecorder`. Populates `package.loaded['imgui']` and sets the enum globals.

| Member | Signature | Meaning |
|---|---|---|
| `calls` | `list[(name, args)]` | the raw log; `args` is a tuple of that call's arguments in order |
| `counts` | `dict[str, int]` | per-entry-point call counts |
| `reset()` | | clear the log, the counts and the cursor state, and disarm the close switch |
| `arm_close()` | | arm a **one-shot** "the user clicked close this frame" |
| `snapshot(colors=None, measurements=True)` | `-> str` | the normalised snapshot text |
| `balance()` | `-> dict` | `{"window", "style_var", "style_color"}`, each `pushed - popped`, popped counting the numeric argument |
| `api` | lua table | the imgui table itself |

Recorded entry points: `SameLine`, `CalcTextSize`, `GetCursorPosX`, `SetCursorPosX`, `TextColored`, `PushTextWrapPos`, `PopTextWrapPos`, `PushStyleColor`, `PopStyleColor`, `ProgressBar`, `PushStyleVar`, `PopStyleVar`, `Begin`, `End`, `Dummy`.

**Constants:**

| Constant | Value | Note |
|---|---|---|
| pixels per character | **7.0** | `CalcTextSize(text)` returns `7.0 * #text`, a single number, as ui.lua:95 consumes it. A declared stand-in for font metrics we deliberately do not model. |
| window padding | **8.0** | the x a drawing call starts a fresh line at; `origin_x` reads back as 8.0 |
| nominal fill width | **300.0** | cursor bookkeeping only, for a `-1` width item |

**Enum globals:**

| Name | Value |
|---|---|
| `ImGuiCol_PlotHistogram` | 40 |
| `ImGuiStyleVar_ItemSpacing` | 13 |
| `ImGuiWindowFlags_NoTitleBar` | **1** |
| `ImGuiWindowFlags_NoMove` | **4** |
| `ImGuiWindowFlags_NoScrollbar` | **8** |
| `ImGuiWindowFlags_AlwaysAutoResize` | **64** |
| `ImGuiWindowFlags_NoFocusOnAppearing` | **4096** |

`ui.render`'s unlocked flag sum is therefore `4169`, and `4173` when `opts.locked` is true. `stubs.window_flags(value) -> list[str]` decomposes a summed value into alphabetically sorted short names, appending `?<n>` for any unrecognised remainder.

`Begin` records both real call shapes as they arrived: a table second argument is the `p_open` box, a number second argument is the flags. It returns `true`. With the close switch armed it writes `false` into the box **only if the flags do not include `NoTitleBar`** — ImGui draws no close button on a window with no title bar.

### The shape of the normalised snapshot text

One recorded call per line, indented two spaces between `Begin` and `End`. `Begin` is rendered specially; every other call is `Name` followed by its rendered arguments, space-separated.

- Colour tables resolve to their `COLOR` key name when a reverse map is supplied (pass the addon's `COLOR` table, obtained via `lua_locals`, as `colors=`); otherwise they print as `[r, g, b, a]`.
- Integers print plainly, fractions to two decimals: `0.60`, `273.00`.
- Flags print as `|`-joined sorted short names, or `none`.
- Text is reproduced verbatim inside single quotes and is **never** used as a format string, so a percent sign in server text survives.
- `nil` prints as `nil`, booleans as `true` / `false`, non-colour tables as `[a, b]`.
- `measurements=False` omits `CalcTextSize` and `GetCursorPosX`, which measure rather than draw. They are always recorded either way. (`stubs.MEASUREMENT_CALLS` names them.)

A real frame, `snapshot(colors=COLOR, measurements=False)`:

```
PushStyleVar 13 [4, 2]
Begin 'inctrack###incursion_window' p_open=[true] flags=AlwaysAutoResize|NoFocusOnAppearing|NoScrollbar|NoTitleBar
  Dummy [300, 1]
  TextColored instance 'Fort Ghelsba'
  SameLine
  TextColored dim '. Normal'
  SameLine
  SetCursorPosX 273.00
  TextColored dim '--:--'
  PushStyleColor 40 bar_kills
  ProgressBar 0.60 [-1, 16] 'Phase #2  9/15'
  PopStyleColor 1
  PushTextWrapPos 308.00
  TextColored dim 'Orcish Grunt'
  PopTextWrapPos
  TextColored dim 'Phases cleared '
  SameLine
  TextColored text '1'
  SameLine
  SetCursorPosX 224.00
  TextColored dim 'Elapsed 0:00'
End
PopStyleVar 1
```

### The json stub

`package.loaded['json']` in the host runtime only — the shared runtime from `make_lua()` never sees it, and suite 8 keeps round-tripping through Ashita's real `json.lua`.

- `encode(value)` — arrays when `#t > 0`, objects otherwise, with keys sorted for reproducible output. Integers via `%d`, other numbers via `%.14g`. Bytes >= 0x80 are emitted raw rather than `\u`-escaped, because escaping them would decode back to a codepoint instead of the byte and break the round trip.
- `decode(text)` — a character scanner. It never hands its input to `load`, `loadstring` or `dofile`. Confirmed to raise on `{a=1}` (valid Lua, invalid JSON — this is the T-01-01 gate), `{"a": `, `[1,2`, `nope`, and `{"a":1}x`.
- `null` decodes to `nil`. The encoder never emits it, since `State:serialise` simply omits nil fields.

---

## Decisions Made

- **Stub bodies are Lua chunks, handles are Python.** Recording happens inside the runtime, so no Python/Lua boundary is crossed per ImGui call; `ImGuiRecorder.calls` converts the log on read.
- **`make_host()` builds a fresh runtime per call rather than resetting a shared one.** `ui.lua` keeps `short_cache` and `origin_x` at file scope and `inctrack.lua` keeps one `incursion` table, so a pristine addon is cheaper to get by construction than by cleanup.
- **`tick` and `wall` are absolute setters, `wall` expressed as an offset from `EPOCH`.** `tick(42)` matches the existing `__clock = N` idiom the eight suites already use; `wall(14400)` reads as "four hours later" without the caller needing to know the epoch.
- **`_ENV` is excluded from `lua_locals`.** Including it would let a caller reach a global through a dict that exists specifically to expose file-scope locals.
- **Window flag values are the upstream Dear ImGui ones.** Only distinctness as powers of two is load-bearing, but using the real values costs nothing and keeps the stub honest.
- **`snapshot()` records measurement calls but can omit them.** "One recorded call per line" is preserved by default; 01-02 can pass `measurements=False` for a tighter, more reviewable inline expected string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `AshitaHost.require` returned a tuple instead of the module**

- **Found during:** Task 3 (running Task 3's own automated verification)
- **Issue:** From Lua 5.4 on, `require` returns two values — the module and its loader data — and lupa surfaces multiple returns as a Python tuple. `host.require("ui")` therefore handed back `(module, loaderdata)`, and `ui.render` was an attribute error. The installed lupa build is 2.8 embedding **Lua 5.5**, so this fires on every `require`.
- **Fix:** Added `__host_require(name)` to the Ashita chunk, which parenthesises the call to truncate it to one value, and pointed `AshitaHost.require` and the `json` property at it.
- **Files modified:** `test/stubs.py`
- **Verification:** Task 3's automated block now passes; `h.require("ui").render` and `h.require("inctrack")` both work.
- **Committed in:** `9811c00` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for the plan's own acceptance criteria to be checkable. No scope creep; nothing under `inctrack/` was touched.

## Issues Encountered

**The 12,841-check baseline is stale, by 20 checks, for reasons outside this plan.**

The plan's acceptance criterion is a summed check count of **at least 12,841** on the full run. The full run now reports **12,821**, from **127** logs and 2,943,686 chat lines — the baseline was recorded against **126** logs and 2,943,169 lines on 2026-08-28.

This is not a regression from this plan, and that was established rather than assumed. The **unmodified** pre-plan `run_tests.py` (`git show HEAD~2:test/run_tests.py`) was run against the same chatlog directory, and its per-suite check counts are **identical, line for line**, to the extended harness's:

```
parser: structural lines all parse            11819 checks  ok
parser: generic tier matches nothing today        1 checks  ok
state: run reconstruction                       888 checks  ok
state: objectives, bonus, recovery               29 checks  ok
adaptability: unseen content still tracked       20 checks  ok
disconnect: stale progress is not trusted        23 checks  ok
timers: countdown, linger, staleness             21 checks  ok
persistence: json round trip                     20 checks  ok
```

The cause is input drift: `Godwen_2026.08.29.log` appeared after the baseline was taken, and `Godwen_2026.08.28.log` kept being written to after it. `test_replay` only counts a run it watched from `Begins!` through `Complete!`, so a run straddling the point at which the baseline was measured can move the total in either direction. The check count is a property of the author's private, still-growing chatlog corpus, not only of the harness.

**What plans 01-02 and 01-03 should do:** treat **12,821 measured on 2026-08-29 against 127 logs** as the floor, and — more usefully — hold the *per-suite* line above constant rather than the sum. The sum will keep drifting every time the author plays. No suite reports `FAILED`, the run exits 0, and both parser suites are green.

## User Setup Required

None — no external service configuration required. The full run needs the author's private chatlogs and a local Ashita install, exactly as before; the new stubs deliberately need neither.

## Next Phase Readiness

Plans 01-02 and 01-03 are unblocked. Everything they were written against exists and is pinned above: `make_host()`, `host.imgui`, `host.fire`, `host.addon`, `lua_locals`, `arm_close()`, `snapshot()`, `Result.xfail`, and the two markers.

Concerns to carry forward:

- **The check-count floor is 12,821, not 12,841** (see above). Plan 01-03's closing verification and the phase's ROADMAP criterion both cite 12,841 and should be read as "no suite went down", not as a literal sum.
- **`EXPECTED_XFAILS` is deliberately absent.** The guard belongs in 01-03, once all three defect tests exist; a guard asserting three while two exist would be red for two plans.
- **Non-UTF-8 text does not cross the Python boundary.** lupa raises `UnicodeDecodeError` when a Lua string with raw high bytes is read into Python. This does not affect the json stub (its round trip is verified inside Lua) or any render path exercised so far, because the parser strips the boon glyph. A future snapshot fixture that puts a raw high byte into displayed text would need to assert inside Lua.
- **`ui.render` currently cannot be closed** — the armed close click is correctly blocked by `NoTitleBar`. That is FIX-03, and it is 01-02's xfail to write, not a stub defect.

---
*Phase: 01-the-net*
*Completed: 2026-08-28*

## Self-Check: PASSED

All claimed artifacts exist on disk (`test/stubs.py`, `test/run_tests.py`,
`.planning/phases/01-the-net/01-01-SUMMARY.md`) and all three task commit
hashes resolve in `git log` (`86356f0`, `602d7e9`, `9811c00`).

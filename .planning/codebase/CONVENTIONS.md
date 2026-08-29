# Coding Conventions

**Analysis Date:** 2026-08-29

The shipped addon is four Lua files under `inctrack/`; the harness is two Python
files under `test/`. The Lua conventions below are the ones that matter — they
are enforced by review and, where countable, by the `record:` suite in
`test/run_tests.py`, not by any linter (there is none; see PROC-01…04).

## Naming Patterns

**Files:**
- Lowercase, one word, `.lua`: `inctrack/parser.lua`, `inctrack/state.lua`,
  `inctrack/ui.lua`, `inctrack/inctrack.lua` (the shell, named for the addon).
- Test files are plain Python: `test/run_tests.py`, `test/stubs.py`.

**Functions:**
- `snake_case` throughout, Lua and Python alike: `split_mobs`, `new_run`,
  `strip_colors`, `right_text`, `make_host`, `lua_locals`.
- Module entry points are terse verbs or nouns on the module table:
  `parser.relevant`, `parser.parse`, `ui.render`, `State.new`.
- Methods on the state object use colon syntax and `self`: `State:apply`,
  `State:snapshot`, `State:serialise`, `State:restore`, `State:now`.

**Variables:**
- `snake_case` locals. Short, non-abbreviated where the word is short
  (`line`, `run`, `event`, `blob`), suffixed rather than prefixed for pairs:
  `kills_cur` / `kills_max`, `save_due` / `save_at` / `save_retry_at`.
- Boolean latches read as past-tense facts: `render_off`, `render_ok`,
  `parse_told`, `save_told`, `desynced`, `points_partial`.

**Constants:**
- `UPPER_SNAKE` file-scope locals with the unit in the name:
  `STALE_SECONDS`, `LINGER_SECONDS`, `NOTE_SECONDS`, `SAVE_RETRY_SECONDS`,
  `MUST_SAVE`, `COLOR`, `CONTENT_W`, `STAT_SHORT`, `FRAME_OPTS`.

**Types:**
- No type system. The state record is a plain table with fixed field names
  documented at `inctrack/state.lua` `new_run`; parser events are tables with a
  `t` tag (`begin`, `phase`, `points`, `boon`, `bonus_new`, …).

## Code Style

**Formatting:**
- No formatter, no linter, no build step. Style is held by review.
- Four-space indent. Statements end with a semicolon in the addon Lua — this is
  Ashita house style and is applied consistently in all four files.
- Lines wrap near 79 columns; string concatenation continues with a leading
  `.. ` on the next line.

**Module pattern (all four Lua files):**
```lua
--[[
* inctrack -- parser.lua
* Copyright (c) 2026 Godwen. MIT License; see LICENSE in the repository root.
* Written with Claude (Anthropic).
]]--

--[[
* parser.lua -- one-paragraph statement of what this file is and is not.
* ... entry points named explicitly ...
]]--

local parser = {};

local function trim(s) ... end   -- helpers are file-scope locals

function parser.parse(line) ... end

return parser;
```
- Every file opens with the two block comments above: the licence banner, then
  a design header naming the module's entry points and its constraints.
- **Helpers are file-scope `local`s and are never exported for testability.**
  The addon may not be edited to widen its surface for tests; the harness
  reaches them by upvalue reflection instead (`lua_locals` in
  `test/run_tests.py`). This is a hard rule.
- `state.lua` uses the metatable pattern (`State.__index = State`) and injects
  its clock (`State.new({ clock = os.clock, player = ... })`) so tests are
  deterministic.
- `parser.lua` and `state.lua` are pure Lua with no Ashita dependency;
  `ui.lua` requires only `imgui`; `inctrack/inctrack.lua` is the only file that
  touches the host (`addon`, `ashita.events`, `AshitaCore`, `chat`, `settings`,
  `json`).

## The content-name rule

**No instance, boss, mob, objective or difficulty name may appear in any code
path.** Everything drawn comes from the run record, which comes from the
server's own messages, so content added to the server later needs no code
change. Stated at the top of `inctrack/state.lua` and `inctrack/ui.lua`.

The two permitted exceptions are illustrative and inert:
- comments and design headers may quote real lines as examples
  (`inctrack/parser.lua` `split_mobs` cites an Orcish mob list);
- `inctrack/ui.lua`'s layout sketch draws a sample window naming real content.

Nothing reads from either. A name in a pattern, a table key, a branch, or a
format string is a defect. The adaptability suite (`test_future_content`,
`test/run_tests.py`) proves the rule by feeding invented content and asserting
it is still tracked.

## Error Handling

Three containment boundaries, in the shell only. Each has a **report-once
latch** so a persistent fault produces one sentence per session, not one per
line or per frame, and each latch has a stated way back (`/incursion reset`).

1. **`text_in` pcall** — `inctrack/inctrack.lua:269`. The whole handler body
   runs inside `pcall(function () ... end)`. The failure path only prints; it
   does not reset state, disable anything, or stop the next line being read —
   a parse error costs one line, not the frame. Latch: `parse_told`, cleared by
   `/incursion reset` and by a character change.
2. **`ui.render` pcall with conditional stack repair** —
   `inctrack/inctrack.lua:460`. On a raise, if `render_ok` is set (render has
   completed end to end at least once on this host, so the repair is a repair
   and not a guess) the handler closes the ImGui stack:
   ```lua
   if incursion.render_ok then
       pcall(function () imgui.End(); end);
       pcall(function () imgui.PopStyleVar(1); end);
   end
   ```
   Each repair is individually protected **and the lookup goes inside the
   closure**: `imgui` is Ashita's constants table whose `__index` is
   `AshitaCore:GetGuiManager()`, so bare `pcall(imgui.End)` would evaluate a
   live host call before `pcall` is entered and escape into `d3d_present`.
   Latch: `render_off` — the window takes itself off screen for the session;
   `/incursion` and `/incursion reset` clear it. `render_ok` is deliberately
   *not* cleared by reset: it is a fact about the host, not the run.
3. **Protected settings write** — `inctrack/inctrack.lua:422`. `pcall(persist)`
   in the frame handler; on failure the write stays owed and is retried after
   `SAVE_RETRY_SECONDS`. Latch: `save_told`.

Rules that apply to all three:
- `tostring(err)` is always an **argument**, never part of the format string —
  a percent sign in server text is one of the things that gets you there.
- The report itself is `pcall`-wrapped as a whole statement, so the report
  cannot become the second error of the frame.
- No `pcall` inside `parser.lua` or `state.lua`: the shell's boundary is the
  one that catches, and adding a local one would hide a defect
  (`inctrack/parser.lua:421` says so explicitly — "No type guard, deliberately").

## Threading and write policy

Chat lines arrive on the game thread; `settings.save()` is a synchronous disk
write. So `text_in` only *decides* a write is owed (`save_due`, immediately for
a `MUST_SAVE` event the server never repeats, otherwise once every five
seconds) and `d3d_present` performs it, above both of its early returns, so a
hidden or latched-off window still writes the run down. The unload handler
writes unconditionally without consulting the mark.

## Logging

**Framework:** none. A single `printf` helper wrapping Ashita's
`chat.header`/`chat.message` (`inctrack/inctrack.lua`).

**When to print:**
- Player-facing faults only, once per session per latch, phrased in the
  player's terms with a stated recovery (`/incursion reset to hear them again`).
- No debug or trace output ships. The addon is silent in normal operation.

## Comments

**Style:** `--[[ * ... ]]--` block comments with a leading `*` on continuation
lines for anything explaining a decision; `--` line comments for local notes.

**When to comment:** the convention is heavy, prose-grade commenting of
*decisions and residuals*, not of mechanics. Comments state:
- why a shape was chosen over the alternative that looks equivalent
  (`split_mobs` splitting on comma-space rather than comma);
- what the residual risk is, in plain words, rather than hiding it (the run is
  not on disk between the chat line and the next frame);
- counted claims about the corpus ("All 469 kill-objective lines across 127
  logs split identically either way").

**Counted claims are load-bearing.** Any number stated in prose in
`inctrack/*.lua`, `README.md`, `docs/design.md` or the harness docstrings is
checked by the `record:` suite against the thing it counts, including the
module header naming every exported function. Change a number, and either the
code or the sentence must move with it.

## Function Design

**Size:** helpers stay small and single-purpose; `ui.render` and the event
handlers are the long functions and are structured by commented sections.

**Parameters:** positional, few. Options arrive as a single table
(`State.new(opts)`, `ui.render(state, opts)`).

**Hoisting:** tables passed every frame and read-then-dropped are hoisted to
file scope to avoid GC churn — `FRAME_OPTS` in the shell, `ARG_*` in `ui.lua`.
Same pattern, same stated reason.

**Return values:** `nil` for "not mine" (`parser.parse`, `State:snapshot`),
never a sentinel table. Booleans for latch state.

## Module Design

**Exports:** one table per file, returned at the bottom. Everything else local.

**Barrel files:** none.

---

*Convention analysis: 2026-08-29*

# Coding Conventions

**Analysis Date:** 2026-08-28

The addon is four Lua files (`inctrack/inctrack.lua`, `inctrack/parser.lua`, `inctrack/state.lua`, `inctrack/ui.lua`, 1722 lines total) plus one Python test file (`test/run_tests.py`). There is **no linter config, no formatter config, no CI, and no build step** — every convention below is enforced by consistency of the existing code, so match it by hand.

## The Hard Convention: Nothing Is Hardcoded

**No instance, boss, mob, objective, difficulty, or bonus name may appear anywhere in the addon source.**

Everything displayed is extracted from the server's own chat text at runtime:
- `inctrack/parser.lua` matches message *shapes* only (`'^Incursion %[(.-)%] Begins! %((.-)%)$'`), never literal content names.
- `inctrack/state.lua` header states it explicitly: "Nothing here knows the name of an instance, a boss, a mob or an objective."
- `inctrack/ui.lua` header states it explicitly: "No instance, boss, mob or objective name appears in this file."

Consequences you must preserve when editing:
- New server content (a new zone, a new difficulty tier, a phase beyond #8, a new objective wording) must work with **zero code change**.
- Unknown shapes are caught by the **generic tier** in `inctrack/parser.lua` (`generic_counter`, `generic_done`, `generic_note`, `objective_text`, generic `bonus_new`) and surfaced as readable text rather than dropped.
- Unknown counters are stored keyed by their own label in `run.extra` (`inctrack/state.lua`, `generic_counter` branch) so several coexist.
- Literal names appear **only** in `test/run_tests.py` fixtures, and there the invented ones ("Castle Zvahl Baileys", "Mythic", "Seals Broken") exist precisely to prove the addon does not know them.

The only string literals allowed in the addon are message *grammar* fragments (`'Expires in'`, `'incursion points'`, `'Phase #'`) and UI chrome.

## Naming Patterns

**Files:** lowercase, one word, `.lua`. Module file name equals the `require` name: `require('parser')` ← `inctrack/parser.lua`.

**Modules:** `local parser = {}` … `return parser` for plain tables; `local State = {}; State.__index = State` for the one class (`inctrack/state.lua`).

**Functions:**
- Methods on the class: `State:apply`, `State:snapshot`, `State:time_left` — `snake_case`, colon syntax, `self` implicit.
- Module-private helpers: `local function trim(s)`, `local function split_mobs(s)`, `local function new_run(self, ...)` — declared `local` at file scope before first use.
- Addon-shell helpers: `local function printf(...)`, `local function persist()`, `local function visible()` in `inctrack/inctrack.lua`.

**Variables:** `snake_case` (`kills_cur`, `time_sync`, `phases_cleared`, `hide_at`). Short well-known names are fine in tight scopes: `s` (the trimmed line), `e` (the event), `run`, `b`.

**Constants:** `UPPER_SNAKE`, file-scope `local`, with a one-line comment explaining the number: `STALE_SECONDS`, `LINGER_SECONDS`, `NOTE_SECONDS` (`inctrack/state.lua`), `BAR_MAIN`, `BAR_THIN`, `CONTENT_W`, `COLOR`, `ARG_SPACER` (`inctrack/ui.lua`), `MUST_SAVE` (`inctrack/inctrack.lua`).

**Event types:** lowercase `snake_case` on the `t` field: `begin`, `recover`, `complete`, `phase`, `objective_kills`, `objective_boss`, `objective_text`, `boss_hint`, `bonus_new`, `bonus_progress`, `bonus_done`, `generic_counter`, `generic_done`, `generic_note`, `time`, `points`, `boon`. Generic-tier events additionally carry `generic = true`.

**Avoid shadowing Lua globals:** the code uses `labelText` rather than `label` where a local would shadow a field, and never names a local `string`, `type`, `next`.

## Code Style

**Semicolons:** every statement ends with `;`. This is universal in the codebase — match it.

**Indentation:** 4 spaces, no tabs.

**Table literals:** aligned `=` for related fields in multi-field constructors:
```lua
run.finished      = true;
run.finish_time   = string.format('%dm %ds', e.minutes, e.seconds);
run.elapsed_final = e.minutes * 60 + e.seconds;
```
Short event tables stay inline: `return { t = 'time', minutes = tonumber(mins) };`

**Strings:** single quotes for Lua (`'Incursion %['`), double quotes in the Python tests.

**Line length:** ~80–90 columns. Long `s:match(...)` calls wrap after `=`.

**Blank lines:** one blank line between logical steps inside a function; comment blocks are separated from the code above by a blank line.

## Module Pattern

Three layers, strictly one-directional, and the two lower ones are **pure Lua with no Ashita dependency** — this is what makes `test/run_tests.py` possible:

| Module | Ashita dependency | Pattern |
|---|---|---|
| `inctrack/parser.lua` | none | Stateless. Single entry point `parser.parse(line) -> event or nil`. Two ordered arrays of matcher closures, `specific` then `generic`. |
| `inctrack/state.lua` | none | Class via `setmetatable`/`__index`. Clock **injected** through `State.new({ clock = ..., player = ... })` so tests are deterministic. |
| `inctrack/ui.lua` | ImGui only | Read-only renderer: "renders a run record from state.lua and never mutates it." |
| `inctrack/inctrack.lua` | full | Shell: `ashita.events.register` handlers, settings, persistence, slash command. |

**Rules that follow:**
- Never call `os.clock()` directly in `state.lua`; go through `self:now()`. The addon injects `now()` from `inctrack.lua`; tests inject `__clockfn`.
- Never `require('ashita...')`, `imgui`, `settings`, or `json` from `parser.lua` or `state.lua` — it breaks the whole test suite.
- Matchers are added by appending a closure to the `specific` array in the correct order. Ordering is a documented contract: `bonus_progress` before `phase`, `objective_kills` before `objective_boss`, chest/count/named bonus before generic bonus. Generic matchers always run last so they never shadow a specific one.
- `State:apply(e)` returns `true` when the run changed, so the caller knows to persist. Keep that contract in new branches (`self.dirty = true; return true;`).

## Error Handling

**The pcall boundary.** The `text_in` handler in `inctrack/inctrack.lua` wraps its **entire body** in `pcall`, because a Lua error inside a chat event handler can take Ashita's chat processing down:

```lua
ashita.events.register('text_in', 'incursion_text_in', function (e)
    local ok, err = pcall(function ()
        ...parse and apply...
    end);

    if not ok then
        printf('parse error: %s', tostring(err));
    end
end);
```

Rules for this boundary:
- The handler is **read-only** — `e.message` is never modified, `e.blocked` is never set. The comment says so; keep it true.
- A parse failure must never propagate. Any new work triggered by a chat line goes *inside* the pcall.
- The failure path only prints; it never resets state or disables the addon.

**Other pcall uses** — both around the JSON library, which can raise on malformed input:
- `local ok, encoded = pcall(json.encode, blob)` in `persist()`; on failure the session is stored as `''` rather than half-written.
- `local ok, blob = pcall(json.decode, saved)` on load and on profile switch; a corrupt blob is discarded and the setting cleared, never half-applied.

**Validation over exceptions.** Neither pure module ever raises. They guard and return a falsy value instead:
- `parser.parse` returns `nil` for non-strings, empty lines, and anything failing the cheap prefix rejection.
- `State:apply` returns `false` for `type(e) ~= 'table' or not e.t`, and for events with no run to attach to.
- `State:restore(data)` returns `false` for wrong `version`, missing `instance`, a finished run, or a snapshot older than `STALE_SECONDS` — and leaves state untouched when it refuses (asserted by the tests).

**Defensive defaults on restore:** `data.kills_cur or 0`, `data.points or 0`, `type(data.boons) == 'table'` before iterating, `entry.label or labelText`.

## Logging

**Framework:** Ashita's `chat` library, through one helper in `inctrack/inctrack.lua`:
```lua
local function printf(fmt, ...)
    print(chat.header(addon.name) .. chat.message(fmt:format(...)));
end
```

**When to log:** only things the player needs to see — load banner, run resumed, run cleared, lock/auto toggled, usage text, and the pcall error. No debug/trace logging exists; do not add per-message logging to a handler that runs on every chat line.

**`parser.lua` and `state.lua` never print.** They are pure; keep them silent so the tests stay clean.

## Comments

The comment density is high and deliberate — this codebase explains *why*, at length, and new code is expected to do the same.

**Block comments** use the Ashita `--[[ * ... ]]--` form with a leading `*` on each line:
```lua
--[[
* event: text_in
*
* Read-only. The message is never modified or blocked, and a parse failure can
* never take the chat handler down with it.
]]--
```
Used for: file headers, every registered event handler, every non-obvious public method, and the `specific`/`generic` matcher-array preambles.

**File headers** are mandatory and have a fixed two-block shape:
1. Copyright / MIT license / "Written with Claude (Anthropic)."
2. Purpose block: what the module is, whether it is pure Lua, its entry point, and — for `state.lua` and `ui.lua` — the explicit no-hardcoded-names guarantee.

**Line comments** (`--`) sit *above* the code they explain and give the reason, not the mechanism. Examples of the expected register:
- `-- Cheap rejection: every message we care about starts with one of these. Chat volume in a party is high and this runs on every line.`
- `-- A points award means a boss just died, so whatever phase progress we were showing is stale.`
- `-- Ashita has no monotonic clock exposed to addons, so os.clock is used...`

**Each matcher carries a sample line** as its comment — the real server message it recognises:
```lua
-- Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s
function(s) ... end,
```
Add one for every new matcher; it is how the pattern is reviewed.

**No JSDoc/LDoc/annotations.** No `---@param`. Prose only.

**No commented-out code, no TODO/FIXME/HACK markers** anywhere in the tree. Keep it that way.

## Function Design

**Size:** helpers are 3–15 lines. `State:apply` is the deliberate exception — a long flat dispatch of `if t == '...' then ... return true; end` blocks, in event order, each ending in an explicit `return`. Extend it by adding another block in the same shape; do not convert it to a dispatch table.

**Parameters:** positional and few. Options go in a single table (`State.new(opts)`, `ui.render(state, opts)`), with `opts = opts or {}` as the first line.

**Return values:** small plain tables from the parser (`{ t = ..., ... }`); `nil` for "not ours"; booleans for "did something change" / "was this accepted". Never multiple ad-hoc returns where a table would read better.

**Numbers are converted at the boundary:** `tonumber(...)` in the parser, so `state.lua` and `ui.lua` never see strings.

**Allocation awareness in hot paths.** Anything on the `d3d_present` (60fps) or `text_in` (every chat line) path avoids per-call garbage: `NO_EXTRAS` shared empty table in `State:extra_sorted`, hoisted `ARG_*` tables in `ui.lua`, and the prefix-rejection `find` chain in `parser.parse` before any real matching.

## Module Design

**Exports:** one table per file, returned at the bottom (`return parser;`, `return State;`, `return ui;`). No barrel files, no `package.loaded` tricks.

**No globals.** Every function and constant is `local`. The only globals touched are Ashita's own (`addon`, `ashita`, `AshitaCore`, `T`).

**Requires** sit at the top of `inctrack/inctrack.lua` in a fixed order: `require('common')` first (Ashita bootstrap), then Ashita libs (`chat`, `settings`, `json`), then local modules (`parser`, `state`, `ui`).

## Persistence Conventions

- The in-progress run is stored as a **JSON string in a single settings field** (`session`), not a nested table — "so the settings merge cannot reshape it on the way back in" (`inctrack/inctrack.lua`).
- Serialisation lives in `state.lua` (`State:serialise` / `State:restore`), not in the addon shell, explicitly so the round trip is testable without Ashita.
- Timers are serialised as **remaining durations**, never absolute clock values, because `os.clock` resets on reload.
- Staleness is judged on `os.time()` wall clock (`saved_at`), not the injected clock.
- Writes are throttled: events in the `MUST_SAVE` set persist immediately (the server never repeats them); everything else waits out a 5-second window.

---

*Convention analysis: 2026-08-28*

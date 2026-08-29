<!-- refreshed: 2026-08-29 -->
# Architecture

**Analysis Date:** 2026-08-29

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Ashita v4 host (game)                     │
│   text_in · d3d_present · command · load · unload · settings │
└────────┬─────────────────────────────────────────┬──────────┘
         │ raw chat line                            │ frame
         ▼                                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Addon shell — `inctrack/inctrack.lua`        │
│  the ONLY file that touches Ashita: events, settings, json,  │
│  AshitaCore, pcall containment, save/render latches          │
└───┬──────────────────┬──────────────────────┬───────────────┘
    │ relevant()/parse │ apply(event)         │ render(state, opts)
    ▼                  ▼                      ▼
┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐
│ `parser.lua` │→ │   `state.lua`    │→ │     `ui.lua`       │
│ pure,        │  │ pure, run record │  │ read-only ImGui    │
│ stateless    │  │ + serialise/     │  │ draw + `ui.forget` │
│ line → event │  │   restore        │  │ (bounded memo)     │
└──────────────┘  └────────┬─────────┘  └────────────────────┘
                           │ serialise() → json → settings.save()
                           ▼
                ┌────────────────────────────────┐
                │ Ashita per-character settings   │
                │ `session` = JSON blob, version 2│
                └────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Addon shell | Ashita glue: event registration, settings/profile lifecycle, JSON encode/decode, error containment, deferred-write scheduling, render latching, `/incursion` commands | `inctrack/inctrack.lua` |
| Parser | Chat line → event table, or nil. Cheap `relevant()` gate, timestamp stripping, specific-then-generic matcher tiers | `inctrack/parser.lua` |
| State | Event → single run record; timers, desync marking, phase/award accounting, `serialise()` / `restore()` with structural validation and v1 migration | `inctrack/state.lua` |
| UI | Read-only ImGui render of a run record; boon-stat shorthand memo with `ui.forget()` | `inctrack/ui.lua` |
| Test host stubs | Recording ImGui stub + in-memory Ashita fakes so the shipped `ui.lua` and `inctrack.lua` can execute outside the game | `test/stubs.py` |

## Pattern Overview

**Overall:** Strict one-way layered pipeline with a single impure shell (a hexagonal/ports arrangement in miniature).

**Key Characteristics:**
- Exactly one file requires Ashita. `parser.lua` and `state.lua` require nothing at all; `ui.lua` requires only `imgui`.
- Dependencies point one direction only: shell → parser → state → ui. No module reaches back upward; `ui.lua` never mutates the run record.
- No content is hardcoded. No instance, boss, mob or objective name appears in any code path (`inctrack/parser.lua`, `inctrack/state.lua`, `inctrack/ui.lua` all state and honour this) — the generic matcher tier keeps unknown future server content visible instead of dropped.
- The clock is injected (`State.new({ clock = now })`, `inctrack/inctrack.lua`), which is what makes the timer logic testable.
- Every value drawn came from a server message. The refusal to display a number the server never sent is the project's governing rule and shows up as a design constraint in the validator, in `finite()`, and in the desync markings.

## Layers

**Shell (Ashita glue):**
- Purpose: own every side effect — events, disk, chat printing, ImGui stack repair
- Location: `inctrack/inctrack.lua`
- Contains: five `ashita.events.register` handlers plus one `settings.register` profile callback; the mutable `incursion` table holding all session flags
- Depends on: `common`, `chat`, `settings`, `json`, `imgui`, and the three pure modules
- Used by: the host

**Parser (pure):**
- Purpose: recognise a line's shape
- Location: `inctrack/parser.lua`
- Contains: `parser.relevant`, `parser.parse`, a `specific` matcher array and a `generic` array
- Depends on: nothing
- Used by: the shell's `text_in` handler (both entry points are called from there)

**State (pure):**
- Purpose: hold one run record and answer timer questions
- Location: `inctrack/state.lua`
- Contains: `State.new`, `apply`, `snapshot`, `serialise`, `restore`, `reset`, `desync`, `should_show`, `time_left`, `elapsed`, `bonus`, `note`, `extra_sorted`, plus the file-local structural validator
- Depends on: injected clock, `os.time` for the wall-clock save stamp
- Used by: shell and `ui.lua` (read-only)

**UI (read-only draw):**
- Purpose: render the run record
- Location: `inctrack/ui.lua`
- Contains: `ui.render(state, opts)`, `ui.forget()`, the draw helpers, the `STAT_SHORT` shorthand table and `short_cache`
- Depends on: `imgui`, a `State` instance it only reads
- Used by: shell's `d3d_present`

## Data Flow

### Chat line → screen

1. Host fires `text_in`; handler body runs inside a `pcall` (`inctrack/inctrack.lua`, `incursion_text_in`)
2. `parser.relevant(line)` on the **raw** message, before any allocation (`inctrack/parser.lua:relevant`)
3. `line:strip_colors()` — the only avoidable allocation, so the gate sits in front of it
4. `parser.parse(line)` — relevance re-asked, timestamp prefixes stripped, anchored rejection, specific tier, then generic tier
5. Player name filled in lazily from `AshitaCore:GetMemoryManager():GetParty():GetMemberName(0)` when still nil
6. `incursion.state:apply(event)` → true when the run changed
7. Write policy arithmetic: `MUST_SAVE[event.t]` or five seconds elapsed → `save_at = t; save_due = true` (**no disk write on this thread**)
8. Next `d3d_present` consumes `save_due` and writes; `ui.render` draws the run

### Deferred write (v1.2.0)

1. `d3d_present` opens with `if incursion.save_due and now() >= incursion.save_retry_at`
2. The flag is **consumed before** the write, so a raise cannot retry sixty times a second
3. `pcall(persist)` — `state:serialise()` → `json.encode` → `settings.save()`
4. On failure: `save_due` re-armed and `save_retry_at = now() + SAVE_RETRY_SECONDS` (5.0 s, deliberately the same number as the chat-thread throttle); reported once via the `save_told` latch, itself inside a `pcall`
5. This block sits **above both early returns** (`render_off`, `not visible()`) — a hidden or latched-off window still writes the run down
6. `unload` writes unconditionally, ignoring `save_due`; the profile-switch callback discards what is owed on purpose

### Restore on load / profile switch

1. `settings.load(default_settings)`; `session` is a JSON **string**, not a nested table, so the settings merge cannot reshape it
2. `resume(saved)`: `pcall(json.decode)` → `state:restore(blob)`
3. `restore` gates on `data.version == 1 or 2`, then `valid_session(data)` structurally, then rejects finished runs, then applies staleness rules
4. Failure clears the stored string and prints once; a run already in progress is never disturbed by a rejection

## Key Abstractions

**Event table:**
- Purpose: the parser's whole output contract — `{ t = '<kind>', ... }`
- Kinds: `begin`, `recover`, `complete`, `phase`, `points`, `boon`, `objective_kills`, `objective_boss`, `boss_hint`, `bonus_new`, `bonus_progress`, `bonus_done`, plus generic `generic_counter`, `generic_done`, `generic_note`, `objective_text`
- Generic events carry `generic = true`

**Run record:**
- Purpose: the single mutable object the whole addon is about
- Built by `new_run` (`inctrack/state.lua:53`); `snapshot()` hands it out read-only by convention

**Structural restore validator:**
- Location: `inctrack/state.lua` (`opt_number`/`opt_string`/`opt_boolean`/`opt_table`, `is_string`, `array_of`, `map_of`, `valid_objective`, `valid_next_boss`, `valid_bonus`, `valid_boon`, `valid_extra`, `valid_session`)
- Rule: **"what shape is this, never is this informative."** Types only. A blank string passes; an empty instance name, a blank boon name, a blank mob all survive, because a blank draws nothing and cannot lie, while refusing the blob costs a live run's boons, points, phase and elapsed which the server never re-announces
- Two governing rules stated in the source: *reject, never coerce* and *discard whole, never half-apply*
- `array_of` checks every key **and** contiguity 1..n, because `#` on a holed table is unspecified and a hole is exactly the silent half-apply the validator forbids
- `map_of` requires string keys

**`finite(v)`:**
- Purpose: the one place where "right shape, no value" is separated from "right shape". NaN and ±infinity are read exactly as a **missing key** — that field reads unknown, the rest of the run comes back intact
- Written as `v ~= v or v == math.huge or v == -math.huge` because that is the one form meaning the same under LuaJIT (Ashita's dialect) and Lua 5.3+
- Applied to every number the blob carries: `saved_at`, `time_left`, `elapsed`, `phase`, `kills_cur`, `kills_max`, `points`, `awards_seen`, `phases_cleared`, objective `count`, bonus `cur`/`max`/`remaining`, extras
- Reachable, not hypothetical: `1e999` is well-formed JSON and the settings file is hand-editable

**Persisted schema, `version = 2`:**
- Written by `State:serialise()`; `restore` accepts 1 and 2 only
- Timers stored as remaining **durations** plus a wall-clock `saved_at`, because the injected monotonic clock restarts with the process
- **Version-1 migration:** 1.1.0's `phases_cleared` was authored by every points award (bonus payouts and chests included) and then raised to `phase - 1`, i.e. `max(awards, phase-1)`. Importing it whole reinstates the defect FIX-01 removed. So a v1 blob sets `awards_seen = 0` and re-derives `phases_cleared = phase - 1` from the one field the server authored outright. The award count is unrecoverable; zero *marks* rather than hides, the only safe direction

**`awards_seen` vs `phases_cleared`:**
- `phases_cleared` counts phases the server announced (`e.phase - 1` on a phase line; on `complete`, `run.phase or (run.recovered and 0 or 1)` **assigned upwards**, never incremented — idempotent under a repeated Complete! inside the linger window, and it refuses to invent a cleared phase for a run joined at the final phase)
- `awards_seen` counts our own points awards actually witnessed. **Never displayed** — it is purely the yardstick: `e.phase - 1 > run.awards_seen` sets `points_partial`, the lower-bound marking on the points total

**Single-author rule for `phases_cleared`:** only phase lines and the completion may author it, and only upwards. Points awards no longer touch it — that coupling was FIX-01.

**Bounded `short_cache` (`inctrack/ui.lua`):**
- Memoises the FFXI stat shorthand per boon-stats string. `SHORT_CACHE_MAX = 64`; at the cap `short_clear()` empties the table **in place** and never reassigns it, so no handle taken on it becomes an orphan
- `ui.forget()` is exported (the file's second and only other export) because after a reset the shell stops calling `render` at all, so the draw function never gets a frame in which to notice its cache belongs to nobody. Called from `reset()` and from the profile-switch callback

## Entry Points

**`load` (`incursion_load`):** prints the build banner, seeds the player name, resumes a saved run.

**`text_in` (`incursion_text_in`):** the whole parse pipeline, inside one `pcall`. Failure prints once behind `parse_told` and reads the next line — a parse error costs one line, not the frame.

**`d3d_present` (`incursion_present`):** deferred write, then `render_off` early return, then `visible()` early return, then `pcall(ui.render, state, FRAME_OPTS)`.

**`command` (`incursion_command`):** `/incursion` | `/inc` with `reset`, `lock`, `auto`. Bare `/incursion` *re-enables* rather than toggles when `render_off` is set, and deliberately does not clear `override`.

**`unload` (`incursion_unload`):** unconditional `persist()`.

**`settings.register('settings', 'incursion_settings_update', ...)`:** character profile switch — resets run, name, all three "told" latches, both save fields, `ui.forget()`, then resumes the new profile's own run.

## Architectural Constraints

- **Threading:** everything runs on the game thread. `text_in` fires per chat line; `d3d_present` per frame. There is no asynchronous write in Ashita, which is precisely why the flush rides the existing frame handler rather than introducing a mechanism.
- **Global state:** one module-level `incursion` table in `inctrack/inctrack.lua`; one file-scope `short_cache`/`short_held` pair and an `origin_x` in `inctrack/ui.lua`. Nothing else is module-global.
- **Circular imports:** none. `imgui` is required by both `ui.lua` and the shell; both handles are the same table via `package.loaded`, which is what lets the shell repair the stack that `ui.lua` unbalanced.
- **Latch discipline:** `render_off`, `parse_told`, `save_told` all follow one rule — say a thing once. `/incursion reset` and a profile switch clear all three. `render_ok` is deliberately **not** cleared by reset: it is a fact about the host, not about the run.
- **Bound on write latency (stated, not hidden):** the run is not on disk between the chat line and the next frame that actually runs. The bound is "the next `d3d_present`", not 16 ms — a minimised or background-throttled client stretches it arbitrarily.

## Anti-Patterns

### Writing to disk on the chat thread

**What happens:** calling `persist()` inline from `text_in`, which serialises, JSON-encodes and performs a synchronous `settings.save()` on every qualifying chat line.
**Why it's wrong:** `text_in` runs on the game thread for every line the client receives; the write is unbounded and a raise inside it used to be absorbed by the chat pcall in a way that hid a persistent disk fault.
**Do this instead:** decide *whether* a write is owed on the chat thread (`save_due = true`), perform it in `d3d_present` above both early returns, consume the flag before writing, re-arm behind `SAVE_RETRY_SECONDS` on failure (`inctrack/inctrack.lua`).

### Repairing the ImGui stack unconditionally after a caught render error

**What happens:** calling `imgui.End()` / `PopStyleVar` whenever `pcall(ui.render, ...)` returns false.
**Why it's wrong:** three statements in `render` run *before* `Begin` — `state:snapshot()` with its early return, the flags arithmetic, the `PushStyleVar`. A raise there leaves nothing open, so `End` is an unmatched close: a C++ assert inside the host that no `pcall` reaches, i.e. the repair becomes the second error of the frame.
**Do this instead:** repair only when `render_ok` is set, and wrap each repair call in its own closure-based `pcall` — `pcall(function () imgui.End(); end)`. The closure is load-bearing: `pcall(imgui.End)` reads `imgui.End` *before* pcall is entered, and `imgui`'s `__index` is a live call into `AshitaCore:GetGuiManager()`, so a raise from the read escapes the handler.

### Coercing or partially applying a restored blob

**What happens:** defaulting a wrong-typed field, or skipping a malformed boon while keeping the rest.
**Why it's wrong:** a coerced field is a number the server never sent, shown with the same confidence as a real one; a skipped boon is a run resumed with two of three picks and nothing on screen saying so.
**Do this instead:** `valid_session` fails the whole blob on any wrong *type*; the boon copy loop is unconditional because a malformed entry already failed the blob (`inctrack/state.lua`).

### Guarding on content in the validator

**What happens:** demanding a non-empty instance name, boon name or mob string.
**Why it's wrong:** the addon's own writers produce blanks (`Incursion [] Begins!`, `(Boss:  at (J-9))`), and shipped 1.1.0 blobs on players' disks carry them. Refusing turns one degenerate server line into total loss of a live run.
**Do this instead:** `is_string` checks type only. Content judgements belong in the parser (which *does* reject a blank boon name, because that matcher is unanchored and has no fallback tier under it).

### Adopting a decoded table by reference

**What happens:** `run.objective = data.objective`.
**Why it's wrong:** the caller keeps a handle on the decoded blob and can change it afterwards (review finding IN-01).
**Do this instead:** copy field by field, and copy `mobs` element by element (`inctrack/state.lua` `restore`).

### Passing flags in slot 2 of `imgui.Begin`

**What happens:** `imgui.Begin(name, flags)`.
**Why it's wrong:** Ashita's binding is declared once and positionally — `Begin(const char* name, bool* p_open, ImGuiWindowFlags flags)` — with no Lua wrapper, so flags land in `p_open` and the window silently loses `NoTitleBar`.
**Do this instead:** explicit `nil` in slot 2: `imgui.Begin('inctrack###incursion_window', nil, flags)`. `test/stubs.py` mirrors the positional signature so the mistake is caught by the suite.

## Error Handling

**Strategy:** contain at the shell boundary; never let a fault reach the game thread or repeat.

**Patterns:**
- Every host-facing handler body that touches foreign data is `pcall`-wrapped: `text_in`, `persist` in the frame handler, `ui.render`, and each stack-repair call.
- `tostring(err)` is always an **argument**, never part of the format string — a percent sign in server text is one of the things that gets you there.
- Cost proportionality: a parse error costs one line (report once, keep reading); a render error costs the window for the session (`render_off`, recoverable via `/incursion`); a write error costs one attempt per five-second window and says so once.
- Failure is reported, not silent. `resume()` prints on rejection — except for an already-finished run, where silence is correct.

## Cross-Cutting Concerns

**Logging:** `printf` → `chat.header(addon.name) .. chat.message(...)`, shell only. The pure modules print nothing.
**Validation:** two tiers — the parser's shape gates on the way in, `valid_session` + `finite` on the way back from disk.
**Uncertainty marking:** `desynced`, `objective.stale`, `points_partial`, `recovered` — the record carries what it is unsure of, and `ui.lua` renders that uncertainty (`reconnected - awaiting update`, ` ?`, `  (?)`).
**Authentication:** not applicable.

---

*Architecture analysis: 2026-08-29*

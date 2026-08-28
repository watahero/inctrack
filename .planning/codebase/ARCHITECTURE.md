<!-- refreshed: 2026-08-28 -->
# Architecture

**Analysis Date:** 2026-08-28

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                  Ashita v4 host (game process)               │
│   events: load / unload / text_in / d3d_present / command    │
├─────────────────────────────────────────────────────────────┤
│                      Addon shell (glue)                      │
│                    `inctrack/inctrack.lua`                   │
│   owns: settings, persistence, visibility, clock injection   │
└────────┬──────────────────┬──────────────────┬──────────────┘
         │ chat line        │ event            │ per frame
         ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌───────────────────┐
│   parser.lua     │ │    state.lua     │ │      ui.lua       │
│ line -> event    │ │ event -> run     │ │ run -> ImGui      │
│ pure, stateless  │ │ pure, 1 run rec  │ │ read-only draw    │
│ 2 tiers          │ │ injectable clock │ │ no game reads     │
└──────────────────┘ └────────┬─────────┘ └───────────────────┘
                              │ serialise()/restore()
                              ▼
                  ┌──────────────────────────────┐
                  │ Ashita settings profile      │
                  │ `settings.session` (JSON str)│
                  └──────────────────────────────┘

              ┌──────────────────────────────────────┐
              │ test/run_tests.py (lupa)             │
              │ loads parser.lua + state.lua directly │
              └──────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Addon shell | Ashita event registration, settings load/save, run persistence, player-name discovery, visibility override, `/incursion` command | `inctrack/inctrack.lua` |
| Parser | One pure function `parse(line) -> event|nil`; two tiers of anchored Lua patterns | `inctrack/parser.lua` |
| State | Single run record, event application, timers, desync model, serialise/restore | `inctrack/state.lua` |
| UI | Reads a run record and a `State` handle, draws one ImGui window; mutates nothing | `inctrack/ui.lua` |
| Test harness | Loads the two pure modules into embedded Lua, replays real chatlogs, 8 suites | `test/run_tests.py` |
| Design record | Intended behaviour, message-stream ground truth | `docs/design.md` |

## Pattern Overview

**Overall:** Unidirectional pipeline (parse → reduce → render) with a thin host-adapter shell; a functional-core / imperative-shell split.

**Key Characteristics:**
- Strict one-way data flow: chat line → event table → run record → pixels. No layer calls back up.
- `parser.lua` and `state.lua` have **zero Ashita dependency** — no `require` of `common`, `chat`, `settings`, `json`, or `imgui`. That is the purity boundary that makes them runnable in a standalone interpreter.
- Zero content knowledge: no instance, boss, mob, objective or difficulty name appears in any Lua file. Everything displayed is quoted from the server's own text.
- Only `inctrack/inctrack.lua` touches `AshitaCore`, `settings`, `json`, and `os.clock`; only `inctrack/ui.lua` touches `imgui`.

## Layers

**Addon shell (`inctrack/inctrack.lua`):**
- Purpose: adapt Ashita's event model to the pipeline
- Depends on: `common`, `chat`, `settings`, `json`, and all three internal modules
- Used by: the Ashita runtime only
- Injects the clock: `State.new({ clock = now })` where `now = os.clock` (`inctrack/inctrack.lua:74-76`)

**Parser (`inctrack/parser.lua`):**
- Purpose: recognise a chat line, return a flat event table or `nil`
- Depends on: nothing
- Used by: the shell's `text_in` handler and the test harness

**State (`inctrack/state.lua`):**
- Purpose: reduce events into one run record; answer all timer questions
- Depends on: `os.clock` default and `os.time` (only inside `serialise`/`restore` staleness checks)
- Used by: the shell (apply/persist) and the UI (read-only accessors)

**UI (`inctrack/ui.lua`):**
- Purpose: one ImGui window per frame
- Depends on: `imgui`, plus a `State` instance for derived values
- Used by: the shell's `d3d_present` handler

## Data Flow

### Primary Request Path

1. Ashita fires `text_in` with a coloured chat line (`inctrack/inctrack.lua:148`)
2. Handler wraps everything in `pcall`, strips colours with `line:strip_colors()` (`inctrack/inctrack.lua:157`)
3. `parser.parse(line)` strips any `[HH:MM:SS]` timestamp prefixes, applies a cheap prefix rejection, then specific then generic matchers (`inctrack/parser.lua:279-330`)
4. `state:apply(event)` mutates the single run record and returns `true` if anything changed (`inctrack/state.lua:114`)
5. On `begin`, the manual visibility override is cleared (`inctrack/inctrack.lua:172-175`)
6. Persistence: immediate write if `MUST_SAVE[event.t]`, otherwise throttled to one write per 5 s (`inctrack/inctrack.lua:55-66`, `181-186`)
7. Each frame, `d3d_present` checks `visible()` and calls `ui.render(state, {visible, locked})` (`inctrack/inctrack.lua:193-208`)

### Parser two-tier flow

1. **Cheap rejection.** A line must start with `Incursion [`, `New Objective: `, `Bonus Objective: `, `(Boss: `, `You have <digit>`, or end with `incursion points.`, or contain `): ` (the boon glyph tail). Everything else returns `nil` before any pattern runs — this executes on every chat line in a party (`inctrack/parser.lua:308-316`).
2. **Specific tier** (`inctrack/parser.lua:65-206`), an ordered array of matcher closures producing precise events: `begin`, `recover`, `complete`, `bonus_done`, `bonus_progress`, `phase`, `objective_kills`, `objective_boss`, `boss_hint`, `bonus_new` (chest/kills/nm), `time`, `points`, `boon`. Order encodes disambiguation: `bonus_progress` before `phase` (both are `Incursion [X] … N/M`), `objective_kills` before `objective_boss`, and bonus chest → count → named NM so `Defeat 5 Sentry Lizard!` is not read as a named NM.
3. **Generic tier** (`inctrack/parser.lua:209-262`), tried only after every specific matcher declines, so it can never shadow one: `generic_counter`, `generic_done`, `generic_note`, `objective_text`, `bonus_new` (kind `text`, expiry still parsed by the shared `split_expiry` helper). All carry `generic = true`.
4. The design contract, enforced by suite 2 of `test/run_tests.py`: **no generic pattern may match anything in today's chatlogs.** A generic firing on a real line means a specific pattern regressed and the window silently lost detail.

**State Management:**
- Exactly one mutable run record lives at `state.run`; there is no history and no event log.
- `state.dirty` is set by every mutating branch but the shell currently drives persistence off `apply()`'s boolean return rather than reading `dirty`.

## Key Abstractions

**Event table (parser output):**
- Flat table, always with `t` (type). Optional `instance`, `generic`, plus type-specific fields.
- `instance` is load-bearing: any instance-tagged event naming a different instance than the live run resets the run (`inctrack/state.lua:180-185`). Deliberately generic so it guards message shapes added later.

**Run record (`state.run`), constructed by `new_run` (`inctrack/state.lua:53-77`):**

```
run = {
  instance, difficulty,
  phase, kills_cur, kills_max,
  objective  = { kind = 'kills'|'boss'|'text', count, mobs, name, loc, text, stale },
  next_boss  = { name, loc },
  bonus      = { kind, label, loc, cur, max, expires_at, done },
  extra      = { [label] = { label, cur, max, done, at } },  -- generic counters
  note       = { text, at },                                 -- unrecognised line
  boons      = { { name, stats }, ... },                     -- pick order, deduped by name
  time_left, time_sync,        -- seconds; ticked from the injected clock, snapped on sync
  started, points, phases_cleared,
  finished, finish_time, elapsed_final, hide_at,
  -- set conditionally, not in new_run:
  desynced, recovered, points_partial,
}
```

**Derived accessors (never stored):** `State:time_left()`, `State:elapsed()`, `State:bonus()`, `State:bonus_remaining()`, `State:note()`, `State:extra_sorted()`, `State:should_show()`. The UI calls these each frame instead of reading raw fields, which is what keeps rendering side-effect free.

## Desync / lower-bound model

The server replays nothing on reconnect — `Recovering session...` re-syncs only the timer. So anything held across a gap is treated as a **lower bound**, not truth:

- `State:desync()` sets `run.desynced` on a live unfinished run (`inctrack/state.lua:88-93`). It is set by `recover` and unconditionally by `restore()`.
- `recover` keeps the existing run when the instance matches, it is unfinished, and it is younger than `STALE_SECONDS` (3 h); otherwise it starts a partial run flagged `recovered` whose objective stays unknown until the next message fills it in (`inctrack/state.lua:131-152`).
- `resync(run)` clears `desynced` and the objective's `stale` flag; called by `objective_kills`, `objective_boss`, `objective_text`, and `boss_hint` — authoritative content restores confidence in the mob list and boss.
- A `phase` event restores confidence in *progress* (`run.desynced = false`) even though the mob list may still belong to the previous phase.
- **Missed-phase inference:** reaching phase N implies N−1 phases cleared. When that raises `phases_cleared`, `points_partial = true`, because those bosses awarded points the client never saw (`inctrack/state.lua:187-196`).
- Coming back on a *different* phase marks `run.objective.stale = true` (mobs are probable, not confirmed) and drops `next_boss` outright (`inctrack/state.lua:198-205`).
- A `points` award while desynced clears the stale mid-count display (`objective`, `next_boss`, `kills_cur`, `kills_max`) rather than leaving it frozen (`inctrack/state.lua:307-312`).
- UI surface: a `reconnected - awaiting update` warning line, a `?` suffix on the phase label, the amber `bar_stale` colour, and `(?)` on flagged mob lists (`inctrack/ui.lua:186-206`, `403-405`).

## Timers

- **Instance clock.** `time_left` is seeded from a whole-minute `time` sync and decremented against the injected clock: `run.time_left - (now - run.time_sync)`, floored at 0 (`inctrack/state.lua:353-364`). Displayed with a leading `~` because the source is minute-granular; it snaps whenever a fresh sync lands.
- **Pending sync.** The entry sync arrives *before* `Begins!`, so a `time` event with no run is stashed in `self.pending_time` and applied by `begin` if it is under 30 s old (`inctrack/state.lua:118-129`, `155-164`). The stash also happens when a *finished* previous run still occupies state, so back-to-back runs get a clock immediately instead of at the first phase boundary.
- **Bonus expiry.** `expires_at = now + minutes*60` at announcement. A `bonus_progress` proves the bonus is still live, so a locally-lapsed `expires_at` is cleared rather than hiding an objective the server still counts (`inctrack/state.lua:270-277`). `State:bonus()` drops a lapsed, incomplete bonus entirely instead of showing `0:00` — the server never announces the expiry.
- **Linger.** `complete` sets `hide_at = now + LINGER_SECONDS` (30) and clears bonus/objective/note/extra. Past `hide_at`, the finished run stops absorbing events so later activity cannot mix into a settled result (`inctrack/state.lua:174-177`).
- **Notes.** Unrecognised status lines age out after `NOTE_SECONDS` (30) via `State:note()`.
- **Injection.** `State.new({ clock = os.clock })` in game; a fake clock in tests. `os.clock` is used rather than `os.time` for sub-second resolution; on Windows it is wall time since process start (`inctrack/inctrack.lua:69-76`).

## Persistence

- Single settings key `session`, a **JSON-encoded string** rather than a nested table, so Ashita's settings merge cannot reshape it on the way back in (`inctrack/inctrack.lua:36-43`).
- `State:serialise()` returns a version-1 plain table (`inctrack/state.lua:445-509`). Timers are stored as **remaining durations**, not absolute clock values, because `os.clock` resets on reload. `saved_at` uses wall-clock `os.time`.
- `State:restore(data)` rejects anything that is not `version == 1` with an `instance`, anything `finished`, and anything older than 3 h. Restored runs are `recovered` and unconditionally `desynced` (`inctrack/state.lua:511-580`).
- Write policy: immediate on events the server never repeats (`MUST_SAVE` — begin, recover, complete, all three objective forms, boss_hint, bonus_new, bonus_done, generic_done, boon), otherwise throttled to 5 s.
- Profile switching: `settings.register` clears the run, clears the player name (so the new character's own points are not filtered out), and attempts to restore that profile's own saved session (`inctrack/inctrack.lua:262-292`).

## Purity boundary (testability)

`test/run_tests.py` loads `inctrack/parser.lua` and `inctrack/state.lua` into an embedded Lua runtime via `lupa` — the shipped files, not reimplementations. This is only possible because neither module requires an Ashita library, reads `AshitaCore`, or draws. Consequences to preserve:

- Never `require` an Ashita lib from `parser.lua` or `state.lua`.
- Never read the current time directly in `state.lua`; go through `self:now()`.
- Serialisation lives in `state.lua`, not the shell, so the round trip can be tested (against Ashita's real `json.lua` when available).
- Eight suites: parser coverage, generic-tier silence, per-run replay reconstruction, state units, invented future content, disconnect, timers, JSON round trip. Log-backed suites skip (not fail) without chatlogs.

## Architectural Constraints

- **Threading:** single-threaded. All handlers run on the game thread; `d3d_present` runs every frame, `text_in` on every chat line — both are hot paths.
- **Global state:** each Lua module returns a single table; `inctrack.lua` holds one `incursion` table with the sole `State` instance. `ui.lua` keeps frame-local module state (`origin_x`, `short_cache`, hoisted `ARG_*` tables) — acceptable because there is exactly one window.
- **Circular imports:** none. The dependency graph is a tree rooted at `inctrack.lua`.
- **Content-name ban:** no instance/boss/mob/objective/difficulty name may be hard-coded anywhere. The only display-side name table is `STAT_SHORT` in `ui.lua`, which is abbreviation-only and passes unknown phrases through untouched.
- **Read-only host interaction:** the `text_in` handler never modifies, blocks, or consumes a message.

## Anti-Patterns

### Hard-coding server content

**What happens:** adding an instance, boss, mob, difficulty or objective wording to a table in Lua.
**Why it's wrong:** breaks the project's second stated goal — the addon must keep working when the server adds content — and the generic tier exists precisely so it is never needed.
**Do this instead:** extend the generic tier or route the text through `objective_text` / `generic_note` / `run.extra`, which `ui.lua` already renders verbatim.

### Letting a generic pattern shadow a specific one

**What happens:** adding a broad pattern into the `specific` array, or reordering it so a loose matcher precedes a precise one.
**Why it's wrong:** the window silently loses bars, coordinates and timers while still appearing to work.
**Do this instead:** add precise patterns to `specific` in disambiguation order, catch-alls to `generic`, and rely on suite 2 of `test/run_tests.py` to prove no generic fires on real logs.

### Reading the clock directly in state.lua

**What happens:** calling `os.clock()` or `os.time()` inside an `apply` branch.
**Why it's wrong:** breaks the injected clock and makes the timer suites non-deterministic.
**Do this instead:** call `self:now()`. `os.time` is used only for wall-clock staleness in `serialise`/`restore`, where a reload must be survived.

### Mutating the run record from ui.lua

**What happens:** caching or normalising a value onto `run` while drawing.
**Why it's wrong:** the render path runs 60× a second and would make state depend on whether the window is visible.
**Do this instead:** add a derived accessor to `state.lua` (as with `State:bonus()` and `State:extra_sorted()`), or keep the value in `ui.lua`'s own memo table.

### Right-aligning against the live window width

**What happens:** computing an alignment target from `imgui.GetWindowWidth()` inside an `AlwaysAutoResize` window.
**Why it's wrong:** the alignment feeds back into the computed width and oscillates forever.
**Do this instead:** align against `origin_x + CONTENT_W` and pin the width with the per-frame `imgui.Dummy(ARG_SPACER)` (`inctrack/ui.lua:55-73`).

## Error Handling

**Strategy:** contain failures at the host boundary; never take the chat handler down.

**Patterns:**
- The whole `text_in` body runs inside a `pcall`; a failure prints `parse error: …` and the message passes through untouched (`inctrack/inctrack.lua:149-191`).
- `json.encode` / `json.decode` are both `pcall`-wrapped; a failed encode writes an empty session rather than a partial blob.
- An unparseable line simply returns `nil`. A malformed, stale, or finished persisted run is discarded whole, never half-applied.
- `State:apply` returns `false` for a non-table or `t`-less argument.

## Cross-Cutting Concerns

**Logging:** `printf` → `chat.header(addon.name) .. chat.message(...)` into the game chat. Used for load banner, resume notice, command feedback, and parse errors only.
**Validation:** shape checks at the two trust boundaries — parser pattern anchoring on input, `restore()` version/age/finished checks on persisted data.
**Authentication / ownership:** `points` and `boon` events are filtered by `self.player` (party member 0), with an accept-all fallback when the name is not yet known; the name is re-fetched lazily in `text_in` and cleared on profile switch.
**Performance:** prefix rejection before parsing, hoisted per-frame ImGui argument tables, a shared `NO_EXTRAS` table, and a memoised `shorten()` cache — all to keep the per-line and per-frame paths allocation-free.

## Documented-design drift

`docs/design.md` is broadly accurate; verified deviations in the shipped code:

- **Window sizing.** The doc says the window is "fixed width rather than `AlwaysAutoResize`". The code uses `ImGuiWindowFlags_AlwaysAutoResize` *plus* a fixed-width spacer (`CONTENT_W = 300`) — auto height, pinned width. The stated hazard is real; the mitigation differs.
- **Title bar.** The doc describes a title-bar close button driving visibility; the window is created with `ImGuiWindowFlags_NoTitleBar`, so the `ARG_OPEN` close path is effectively unreachable in game.
- **Layout and stats.** The doc's mockup shows a `Time left / Elapsed / Points / Phases` grid. The code puts the instance clock in the header line and draws a single `Phases cleared … Elapsed` line; **points are tracked but never displayed** (`inctrack/ui.lua:271-278`).
- **Boons row.** Rendered as a per-run list with abbreviated stats (`draw_boons`); not shown in the doc's mockup.
- **Run record fields.** `elapsed_final`, `desynced`, `recovered` and `points_partial` exist in code but are absent from (or only prose-mentioned in) the doc's record listing. `points_partial` is persisted but not surfaced in the UI.
- **Bonus location.** `run.bonus.loc` is stored and rendered; the doc's record listing omits it.

---

*Architecture analysis: 2026-08-28*

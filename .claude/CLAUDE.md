<!-- GSD:project-start source:PROJECT.md -->

## Project

**inctrack**

inctrack is a live HUD for **CatsEyeXI** Incursions — an Ashita v4 addon (Lua +
ImGui) that shows the current instance, phase and kill progress, the mobs that
count, the boss waiting at the end of the phase, the bonus objective and its
countdown, time left, phases cleared, and the boons picked. Everything it
displays is read from the server's own chat messages: no packet inspection, and
no memory reading for run data. The single memory read in the addon is
`GetParty():GetMemberName(0)` — the player's own character name, used only to
tell "you gained a boon" from another player's line.

It ships at **v1.2.0** and is in daily use by its author on CatsEyeXI. v1.2.0
added nothing to the window. It was a quality pass on shipped code: the two
files the suite had never reached are now covered, three defects visible in the
code are gone, six fragile paths were hardened, the cost paid on every chat line
was cut and measured, and the project's own documents were brought back into
agreement with what ships.

**What comes next is not chosen.** The candidates are in Active below and they
are all things this milestone deliberately set aside: the process tooling that
was deferred while there was too little coverage to be worth running, a short
list of residuals that were named rather than fixed, and four checks that only a
live Incursion can close. No feature milestone has been proposed.

**Core Value:** **What the window shows is either true, or visibly marked as unconfirmed —
never quietly wrong.** A HUD that lies is worse than no HUD, because the player
stops reading chat and trusts it.

**Shipping v1.2.0 did not change this, and that is a decision, not an
oversight.** It is still the right priority, and this milestone is the strongest
evidence for it so far — because the value earned its keep against the
milestone's own work rather than against the server.

Of the five Critical findings raised across the four phase reviews, four were
regressions this milestone's own hardening introduced, and three of them were
exactly the class the core value exists to catch:

- **Phase 2 CR-01.** FIX-03's fix shipped `imgui.Begin(name, flags)`. Ashita's
  SDK declares one positional signature and slot 2 is `p_open`; a survey of 220
  `imgui.Begin(` call sites across the install found inctrack was the only addon
  passing flags there. The window could have silently lost `AlwaysAutoResize`,
  `NoTitleBar` and `NoMove` — a window that looks fine and is not.

- **Phase 3 CR-01.** HARD-05's new validator required non-empty strings, and the
  addon's own parser emits a blank `next_boss.name` from a line the server
  really sends. The validator was rejecting sessions the addon itself had
  written, turning one such line into total loss of the run's boons, points,
  phase and elapsed on the next reload.

- **Phase 4 CR-01.** PERF-01's cheap gate covered two of Ashita's three colour
  marker bytes. A marker landing inside one of the seven needles would have made
  the addon reject a real Incursion line before it was ever uncoloured — the
  window simply never appears, and a dropped line looks exactly like a quiet
  stretch of chat.

Each was found by asking the core value's question of a change made in its name.
None of the three was visible in a green suite until someone went looking.

The fourth, Phase 4 CR-02, is the same origin and a different class: PERF-02's
move of `persist()` onto the frame handler left it unprotected on the thread
every addon in the process shares. Phase 1's CR-01 was a harness defect, not
shipped behaviour.

### Constraints

- **Tech stack**: LuaJIT 2.1 as embedded by Ashita v4 — Lua 5.1 semantics plus LuaJIT extensions — with ImGui bindings. The host decides, not us; the harness is exercised across all seven Lua backends `lupa` ships precisely so nothing depends on which one a contributor happens to have
- **The ImGui binding is uninspectable**: `addons/libs/imgui.lua` defines no Lua-side functions at all — it is a constants table whose `__index` is `AshitaCore:GetGuiManager()`, so every call reaches a compiled binding that ships without source. Call shapes are settled by the SDK header and by what the other 220 call sites in the install do, and only a rendered frame proves them
- **Build**: none, and none wanted — edit the `.lua` files and copy the folder across; install is a folder copy
- **Purity boundary**: `parser.lua` and `state.lua` must stay free of any Ashita dependency — it is the only reason they can be tested outside the game, and breaking it silently removes the entire test suite's reach
- **Zero content knowledge**: no instance, boss, mob, objective or difficulty name may appear in any **code path** — nothing the addon reads, matches on or draws from is a content name, so the addon survives the server adding content without a code change. Comments and layout sketches may name real content illustratively; nothing reads from them
- **Runtime budget**: the `text_in` handler runs on **every** chat line the client receives; cost there is paid during combat, in crowded zones, forever
- **Rendering**: `ui.render` runs inside `d3d_present`, once per frame, on the thread every addon in the process shares — an unhandled error there is a frame-rate or stack problem, not a log line
- **Verification data is private**: the deepest suites replay the author's own chatlogs, which are not in the repo; anyone else's run of the suite covers less
- **Compatibility**: the server's chat wording is the API, and it can change without notice or versioning

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Lua 5.1 (Ashita v4's embedded LuaJIT dialect) — the entire shipped addon: `inctrack/inctrack.lua`, `inctrack/parser.lua`, `inctrack/state.lua`, `inctrack/ui.lua` (1,722 lines total)
- Python 3 — test harness only, never shipped: `test/run_tests.py` (956 lines)
- Markdown — `README.md`, `CHANGELOG.md`, `docs/design.md`

## Runtime

- Ashita v4 addon host (LuaJIT / Lua 5.1) running in-process with the FFXI client, against the **CatsEyeXI** private server
- Installed by copying the `inctrack/` folder to `<CatsEyeXI install>\catseyexi-client\Ashita\addons\inctrack\`; loaded with `/addon load inctrack`
- Windows only (Ashita is a Windows d3d8 hook). `inctrack/inctrack.lua:70` explicitly relies on `os.clock()` being wall-clock-since-process-start, which is the Windows CRT behaviour
- Python 3 + `lupa` (embedded Lua) for the out-of-game test runner
- None for the addon. There is no manifest, no lockfile, no vendored dependency directory
- `pip` is used only to install the single test dependency: `pip install lupa`

## Frameworks

- **Ashita v4 addon API** — event registration, settings persistence, chat output, memory manager. Entry point `inctrack/inctrack.lua`
- **Dear ImGui** via Ashita's `imgui` Lua binding — the entire HUD. `inctrack/ui.lua:28`
- **Python `unittest`-free custom harness** — hand-rolled `Result` suite class in `test/run_tests.py:149`, no pytest
- **`lupa`** — embeds a Lua runtime in Python so `parser.lua` and `state.lua` (which have zero Ashita dependency) run outside the game. Bootstrap at `test/run_tests.py:95` (`make_lua()`), which prepends the `inctrack/` folder onto `package.path` and `require`s the two modules
- None. There is no build step, transpile, bundle, or minify. Edit `.lua` and copy the folder

## Key Dependencies

- `common` — Ashita prelude; provides `T{}` tables and the `string:strip_colors()` extension used at `inctrack/inctrack.lua:26,157`
- `settings` — per-character settings load/save/profile-switch. `inctrack/inctrack.lua:29`
- `json` — Ashita's `addons/libs/json.lua`; encodes the in-progress run into a single settings string. `inctrack/inctrack.lua:30`
- `chat` — `chat.header()` / `chat.message()` for coloured console output. `inctrack/inctrack.lua:28`
- `imgui` — window, text, progress bars, style stack. `inctrack/ui.lua:28`
- `parser` (`inctrack/parser.lua`) — pure Lua, stateless, no Ashita dependency. Chat line → event table
- `state` (`inctrack/state.lua`) — pure Lua; event → run record, owns all timers. Clock is injected (`State.new({ clock = ... })`, `inctrack/state.lua:38`) so tests can drive it
- `ui` (`inctrack/ui.lua`) — read-only renderer; the only ImGui-dependent module
- `lupa` — Lua-in-Python bridge (`test/run_tests.py:37`)
- Python stdlib: `os`, `re`, `sys`, `glob`

## Configuration

- No `.env` file and no secrets of any kind. The addon makes no network calls of its own
- Runtime configuration lives in Ashita's per-character settings, defaults declared at `inctrack/inctrack.lua:34`:
- Test-only environment variables:
- No build configuration files exist
- `.gitattributes` enforces LF line endings for `*.lua`, `*.py`, `*.md`
- `.gitignore` excludes `__pycache__/`, `.venv/`, `chatlogs/`, `*.log`, and the `config/` and `settings/` directories Ashita writes next to the addon when run from a checkout

## Platform Requirements

- Windows with a CatsEyeXI client install for live testing
- Python 3 with `lupa` for the offline suite: `python test/run_tests.py`, optionally `python test/run_tests.py "C:\path\to\Ashita\chatlogs"`
- Chatlogs are named `<Character>_YYYY.MM.DD.log`; the harness reads the character name off the filename (`test/run_tests.py:64`)
- Distribution is a folder copy (git clone or release download) into the Ashita addons directory. No installer, no package registry, no CI-published artifact
- Version is declared in-source at `inctrack/inctrack.lua:22` (`addon.version = '1.1.0'`) and mirrored in `CHANGELOG.md`

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## The Hard Convention: Nothing Is Hardcoded

- `inctrack/parser.lua` matches message *shapes* only (`'^Incursion %[(.-)%] Begins! %((.-)%)$'`), never literal content names.
- `inctrack/state.lua` header states it explicitly: "Nothing here knows the name of an instance, a boss, a mob or an objective."
- `inctrack/ui.lua` header states it explicitly: "No instance, boss, mob or objective name appears in this file."
- New server content (a new zone, a new difficulty tier, a phase beyond #8, a new objective wording) must work with **zero code change**.
- Unknown shapes are caught by the **generic tier** in `inctrack/parser.lua` (`generic_counter`, `generic_done`, `generic_note`, `objective_text`, generic `bonus_new`) and surfaced as readable text rather than dropped.
- Unknown counters are stored keyed by their own label in `run.extra` (`inctrack/state.lua`, `generic_counter` branch) so several coexist.
- Literal names appear **only** in `test/run_tests.py` fixtures, and there the invented ones ("Castle Zvahl Baileys", "Mythic", "Seals Broken") exist precisely to prove the addon does not know them.

## Naming Patterns

- Methods on the class: `State:apply`, `State:snapshot`, `State:time_left` — `snake_case`, colon syntax, `self` implicit.
- Module-private helpers: `local function trim(s)`, `local function split_mobs(s)`, `local function new_run(self, ...)` — declared `local` at file scope before first use.
- Addon-shell helpers: `local function printf(...)`, `local function persist()`, `local function visible()` in `inctrack/inctrack.lua`.

## Code Style

## Module Pattern

| Module | Ashita dependency | Pattern |
|---|---|---|
| `inctrack/parser.lua` | none | Stateless. Single entry point `parser.parse(line) -> event or nil`. Two ordered arrays of matcher closures, `specific` then `generic`. |
| `inctrack/state.lua` | none | Class via `setmetatable`/`__index`. Clock **injected** through `State.new({ clock = ..., player = ... })` so tests are deterministic. |
| `inctrack/ui.lua` | ImGui only | Read-only renderer: "renders a run record from state.lua and never mutates it." |
| `inctrack/inctrack.lua` | full | Shell: `ashita.events.register` handlers, settings, persistence, slash command. |

- Never call `os.clock()` directly in `state.lua`; go through `self:now()`. The addon injects `now()` from `inctrack.lua`; tests inject `__clockfn`.
- Never `require('ashita...')`, `imgui`, `settings`, or `json` from `parser.lua` or `state.lua` — it breaks the whole test suite.
- Matchers are added by appending a closure to the `specific` array in the correct order. Ordering is a documented contract: `bonus_progress` before `phase`, `objective_kills` before `objective_boss`, chest/count/named bonus before generic bonus. Generic matchers always run last so they never shadow a specific one.
- `State:apply(e)` returns `true` when the run changed, so the caller knows to persist. Keep that contract in new branches (`return true;` on every path that mutated the run). That boolean is the whole mechanism -- `state.lua` holds no dirty flag; the write is decided by `MUST_SAVE` plus the five-second throttle in `inctrack.lua`.

## Error Handling

- The handler is **read-only** — `e.message` is never modified, `e.blocked` is never set. The comment says so; keep it true.
- A parse failure must never propagate. Any new work triggered by a chat line goes *inside* the pcall.
- The failure path only prints; it never resets state or disables the addon.
- `local ok, encoded = pcall(json.encode, blob)` in `persist()`; on failure the session is stored as `''` rather than half-written.
- `local ok, blob = pcall(json.decode, saved)` on load and on profile switch; a corrupt blob is discarded and the setting cleared, never half-applied.
- `parser.parse` returns `nil` for non-strings, empty lines, and anything failing the cheap prefix rejection.
- `State:apply` returns `false` for `type(e) ~= 'table' or not e.t`, and for events with no run to attach to.
- `State:restore(data)` returns `false` for wrong `version`, missing `instance`, a finished run, or a snapshot older than `STALE_SECONDS` — and leaves state untouched when it refuses (asserted by the tests).

## Logging

## Comments

* event: text_in
* Read-only. The message is never modified or blocked, and a parse failure can
* never take the chat handler down with it.
- `-- Cheap rejection: every message we care about starts with one of these. Chat volume in a party is high and this runs on every line.`
- `-- A points award means a boss just died, so whatever phase progress we were showing is stale.`
- `-- Ashita has no monotonic clock exposed to addons, so os.clock is used...`

## Function Design

## Module Design

## Persistence Conventions

- The in-progress run is stored as a **JSON string in a single settings field** (`session`), not a nested table — "so the settings merge cannot reshape it on the way back in" (`inctrack/inctrack.lua`).
- Serialisation lives in `state.lua` (`State:serialise` / `State:restore`), not in the addon shell, explicitly so the round trip is testable without Ashita.
- Timers are serialised as **remaining durations**, never absolute clock values, because `os.clock` resets on reload.
- Staleness is judged on `os.time()` wall clock (`saved_at`), not the injected clock.
- Writes are throttled: events in the `MUST_SAVE` set persist immediately (the server never repeats them); everything else waits out a 5-second window.

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- Strict one-way data flow: chat line → event table → run record → pixels. No layer calls back up.
- `parser.lua` and `state.lua` have **zero Ashita dependency** — no `require` of `common`, `chat`, `settings`, `json`, or `imgui`. That is the purity boundary that makes them runnable in a standalone interpreter.
- Zero content knowledge: no instance, boss, mob, objective or difficulty name appears in any Lua file. Everything displayed is quoted from the server's own text.
- Only `inctrack/inctrack.lua` touches `AshitaCore`, `settings`, `json`, and `os.clock`; only `inctrack/ui.lua` touches `imgui`.

## Layers

- Purpose: adapt Ashita's event model to the pipeline
- Depends on: `common`, `chat`, `settings`, `json`, and all three internal modules
- Used by: the Ashita runtime only
- Injects the clock: `State.new({ clock = now })` where `now = os.clock` (`inctrack/inctrack.lua:74-76`)
- Purpose: recognise a chat line, return a flat event table or `nil`
- Depends on: nothing
- Used by: the shell's `text_in` handler and the test harness
- Purpose: reduce events into one run record; answer all timer questions
- Depends on: `os.clock` default and `os.time` (only inside `serialise`/`restore` staleness checks)
- Used by: the shell (apply/persist) and the UI (read-only accessors)
- Purpose: one ImGui window per frame
- Depends on: `imgui`, plus a `State` instance for derived values
- Used by: the shell's `d3d_present` handler

## Data Flow

### Primary Request Path

### Parser two-tier flow

- Exactly one mutable run record lives at `state.run`; there is no history and no event log.
- The shell drives persistence off `apply()`'s boolean return. `state.lua` keeps no dirty flag of its own: one was carried until 1.2.1, written by every mutating branch and read by nothing.

## Key Abstractions

- Flat table, always with `t` (type). Optional `instance`, `generic`, plus type-specific fields.
- `instance` is load-bearing: any instance-tagged event naming a different instance than the live run resets the run (`inctrack/state.lua:180-185`). Deliberately generic so it guards message shapes added later.

```

```

## Desync / lower-bound model

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

### Letting a generic pattern shadow a specific one

### Reading the clock directly in state.lua

### Mutating the run record from ui.lua

### Right-aligning against the live window width

## Error Handling

- The whole `text_in` body runs inside a `pcall`; a failure prints `parse error: …` and the message passes through untouched (`inctrack/inctrack.lua:149-191`).
- `json.encode` / `json.decode` are both `pcall`-wrapped; a failed encode writes an empty session rather than a partial blob.
- An unparseable line simply returns `nil`. A malformed, stale, or finished persisted run is discarded whole, never half-applied.
- `State:apply` returns `false` for a non-table or `t`-less argument.

## Cross-Cutting Concerns

## Documented-design drift

- **Window sizing.** The doc says the window is "fixed width rather than `AlwaysAutoResize`". The code uses `ImGuiWindowFlags_AlwaysAutoResize` *plus* a fixed-width spacer (`CONTENT_W = 300`) — auto height, pinned width. The stated hazard is real; the mitigation differs.
- **Title bar.** The doc describes a title-bar close button driving visibility; the window is created with `ImGuiWindowFlags_NoTitleBar`, so the `ARG_OPEN` close path is effectively unreachable in game.
- **Layout and stats.** The doc's mockup shows a `Time left / Elapsed / Points / Phases` grid. The code puts the instance clock in the header line and draws a single `Phases cleared … Elapsed` line; **points are tracked but never displayed** (`inctrack/ui.lua:271-278`).
- **Boons row.** Rendered as a per-run list with abbreviated stats (`draw_boons`); not shown in the doc's mockup.
- **Run record fields.** `elapsed_final`, `desynced`, `recovered` and `points_partial` exist in code but are absent from (or only prose-mentioned in) the doc's record listing. `points_partial` is persisted but not surfaced in the UI.
- **Bonus location.** `run.bonus.loc` is stored and rendered; the doc's record listing omits it.

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

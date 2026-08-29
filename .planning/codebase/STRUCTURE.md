# Codebase Structure

**Analysis Date:** 2026-08-29

## Directory Layout

```
inctrack/
├── inctrack/            # The shipped addon — the only directory Ashita loads
│   ├── inctrack.lua     # Addon shell: Ashita events, settings, commands (661 lines)
│   ├── parser.lua       # Pure chat-line parser (512 lines)
│   ├── state.lua        # Pure run state machine + persistence (1048 lines)
│   └── ui.lua           # Read-only ImGui window (535 lines)
├── test/
│   ├── run_tests.py     # The entire suite, single entry point (6255 lines)
│   └── stubs.py         # Ashita + ImGui host stubs (1504 lines)
├── docs/
│   └── design.md        # Design rationale, kept in step with the source (699 lines)
├── .planning/           # GSD planning artifacts (milestones, roadmap, this map)
├── .claude/             # CLAUDE.md project instructions, local settings
├── README.md            # Install and usage
├── CHANGELOG.md         # Keep-a-Changelog format, current at v1.2.0
├── LICENSE              # MIT
├── .gitattributes       # LF enforced for .lua/.py/.md
└── .gitignore           # excludes chatlogs/, *.log, config/, settings/, __pycache__/
```

## Directory Purposes

**`inctrack/`:**
- Purpose: the addon as Ashita loads it — this directory is what gets copied into `<Ashita>/addons/inctrack/`
- Contains: four Lua modules, nothing else. No subdirectories, no vendored libraries
- Key files: `inctrack.lua` is the entry point Ashita executes; the other three are `require`d by name

**`test/`:**
- Purpose: the whole verification story
- Contains: `run_tests.py` (eleven suite functions printing thirteen result lines) and `stubs.py`
- Key files: `test/run_tests.py` is the only entry point; `test/stubs.py` is imported by it and has no CLI

**`docs/`:**
- Purpose: the "why", separate from the source's line-level "why"
- Key file: `docs/design.md` — rewritten from the source during v1.2.0 and currently accurate

**`.planning/`:**
- Purpose: GSD workflow state — `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `MILESTONES.md`, `WINDOWS.md`, `milestones/` (per-milestone requirements, roadmap, audit and phase directories), `codebase/` (this map)
- Not shipped, not loaded by anything

## Key File Locations

**Entry Points:**
- `inctrack/inctrack.lua`: Ashita loads this; all five event handlers and the settings profile callback live here
- `test/run_tests.py`: `python test/run_tests.py [chatlog_dir]`

**Configuration:**
- `default_settings` table at the top of `inctrack/inctrack.lua` (`auto`, `locked`, `session`) — there is no config file in the repo; Ashita writes per-character settings at runtime and `.gitignore` excludes `config/` and `settings/`
- `.gitattributes`: LF line endings for all source types
- Environment variables read by the suite: `INCURSION_CHATLOGS`, `INCURSION_ASHITA_LIBS`

**Core Logic:**
- `inctrack/parser.lua`: `parser.relevant`, `parser.parse`, the `specific` and `generic` matcher arrays
- `inctrack/state.lua`: `State:apply` (event dispatch), `State:serialise` / `State:restore`, the structural validator block, timer accessors
- `inctrack/ui.lua`: `ui.render`, `ui.forget`, `draw_*` helpers, `COLOR`, `STAT_SHORT`, `short_cache`

**Testing:**
- `test/run_tests.py`: all suites
- `test/stubs.py`: `install_imgui(lua)` → `ImGuiRecorder`; `install_ashita(lua, player, profile)` → `AshitaHost`. Also `IMGUI_CHUNK`, `ASHITA_CHUNK`, `JSON_CHUNK`, `GSUB_COUNTER_CHUNK` (Lua source embedded as Python strings), `WINDOW_FLAGS`, `MEASUREMENT_CALLS`, `TEXT_IN_FIELDS`

## Naming Conventions

**Files:**
- Lua: lowercase, one word, matching the `require` name — `parser.lua`, `state.lua`, `ui.lua`. The shell is named after the addon, which Ashita requires.
- Python: lowercase with underscore — `run_tests.py`, `stubs.py`
- Docs: lowercase for `docs/`, UPPERCASE for repo-root conventional files (`README.md`, `CHANGELOG.md`, `LICENSE`)

**Directories:**
- Lowercase, single word. The addon directory name must match `addon.name`.

**Within Lua:**
- File-scope constants `SCREAMING_SNAKE` (`STALE_SECONDS`, `LINGER_SECONDS`, `NOTE_SECONDS`, `SAVE_RETRY_SECONDS`, `MUST_SAVE`, `SHORT_CACHE_MAX`, `CONTENT_W`, `BAR_MAIN`, `COLOR`, `STAT_SHORT`, `ARG_*`, `FRAME_OPTS`, `LBRACKET`)
- Local functions and methods `snake_case` (`split_mobs`, `new_run`, `draw_header`, `valid_session`)
- The state class is `State` (PascalCase, the only one); its module handle in the shell is `State`, instances are `state`
- Module tables are lowercase and returned at the bottom of the file: `return parser;`, `return ui;`, `return State;`
- Semicolon statement terminators throughout the Lua, matching Ashita house style

## Where to Add New Code

**A new server message shape:**
- Add a matcher function to the `specific` array in `inctrack/parser.lua`, ordered before any generic form and after any more-precise specific one it could shadow
- Add a covering literal to `parser.relevant`'s needle list — it must be a literal the new pattern cannot match without, under every alternation and every optional group
- Handle the new `e.t` in `State:apply` (`inctrack/state.lua`); add it to `MUST_SAVE` in `inctrack/inctrack.lua` if the server never repeats it
- If it persists, add the field to `serialise()` **and** to `valid_session`/the relevant `valid_*` helper, and read it through `finite()` if it is a number

**A new displayed row:**
- Add a `draw_*` local in `inctrack/ui.lua` and call it from `ui.render` in draw order
- Update the row inventory in the `ui.lua` header comment — the suite's whole-window snapshot is reviewed against that list before it is pasted in

**A schema change:**
- Bump `version` in `State:serialise()`, widen the version gate in `State:restore()`, and add a migration arm beside the existing `if data.version == 1` branch

**A new Ashita interaction:**
- It goes in `inctrack/inctrack.lua` and nowhere else. `parser.lua` and `state.lua` must stay dependency-free; `ui.lua` may require `imgui` only

**Tests:**
- New assertions go in the matching suite function in `test/run_tests.py`; new host surface goes in `test/stubs.py`

## Special Directories

**`test/__pycache__/`:**
- Purpose: Python bytecode
- Generated: Yes. Committed: No (`.gitignore`)

**`.claude/worktrees/`:**
- Purpose: agent worktree scratch
- Generated: Yes. Committed: No

**`chatlogs/`, `config/`, `settings/`:**
- Purpose: private replay data and Ashita's runtime per-character output
- Generated: Yes (outside the repo in normal use). Committed: No — excluded explicitly; point the suite at logs with `INCURSION_CHATLOGS`

**`.planning/`:**
- Purpose: GSD artifacts
- Generated: By GSD commands. Committed: Yes

---

*Structure analysis: 2026-08-29*

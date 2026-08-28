# Technology Stack

**Analysis Date:** 2026-08-28

## Languages

**Primary:**
- Lua 5.1 (Ashita v4's embedded LuaJIT dialect) — the entire shipped addon: `inctrack/inctrack.lua`, `inctrack/parser.lua`, `inctrack/state.lua`, `inctrack/ui.lua` (1,722 lines total)

**Secondary:**
- Python 3 — test harness only, never shipped: `test/run_tests.py` (956 lines)
- Markdown — `README.md`, `CHANGELOG.md`, `docs/design.md`

## Runtime

**Environment:**
- Ashita v4 addon host (LuaJIT / Lua 5.1) running in-process with the FFXI client, against the **CatsEyeXI** private server
- Installed by copying the `inctrack/` folder to `<CatsEyeXI install>\catseyexi-client\Ashita\addons\inctrack\`; loaded with `/addon load inctrack`
- Windows only (Ashita is a Windows d3d8 hook). `inctrack/inctrack.lua:70` explicitly relies on `os.clock()` being wall-clock-since-process-start, which is the Windows CRT behaviour
- Python 3 + `lupa` (embedded Lua) for the out-of-game test runner

**Package Manager:**
- None for the addon. There is no manifest, no lockfile, no vendored dependency directory
- `pip` is used only to install the single test dependency: `pip install lupa`

## Frameworks

**Core:**
- **Ashita v4 addon API** — event registration, settings persistence, chat output, memory manager. Entry point `inctrack/inctrack.lua`
- **Dear ImGui** via Ashita's `imgui` Lua binding — the entire HUD. `inctrack/ui.lua:28`

**Testing:**
- **Python `unittest`-free custom harness** — hand-rolled `Result` suite class in `test/run_tests.py:149`, no pytest
- **`lupa`** — embeds a Lua runtime in Python so `parser.lua` and `state.lua` (which have zero Ashita dependency) run outside the game. Bootstrap at `test/run_tests.py:95` (`make_lua()`), which prepends the `inctrack/` folder onto `package.path` and `require`s the two modules

**Build/Dev:**
- None. There is no build step, transpile, bundle, or minify. Edit `.lua` and copy the folder

## Key Dependencies

**Critical (all supplied by Ashita, none vendored):**
- `common` — Ashita prelude; provides `T{}` tables and the `string:strip_colors()` extension used at `inctrack/inctrack.lua:26,157`
- `settings` — per-character settings load/save/profile-switch. `inctrack/inctrack.lua:29`
- `json` — Ashita's `addons/libs/json.lua`; encodes the in-progress run into a single settings string. `inctrack/inctrack.lua:30`
- `chat` — `chat.header()` / `chat.message()` for coloured console output. `inctrack/inctrack.lua:28`
- `imgui` — window, text, progress bars, style stack. `inctrack/ui.lua:28`

**Internal modules (first-party, resolved by `require` from the addon folder):**
- `parser` (`inctrack/parser.lua`) — pure Lua, stateless, no Ashita dependency. Chat line → event table
- `state` (`inctrack/state.lua`) — pure Lua; event → run record, owns all timers. Clock is injected (`State.new({ clock = ... })`, `inctrack/state.lua:38`) so tests can drive it
- `ui` (`inctrack/ui.lua`) — read-only renderer; the only ImGui-dependent module

**Test-only:**
- `lupa` — Lua-in-Python bridge (`test/run_tests.py:37`)
- Python stdlib: `os`, `re`, `sys`, `glob`

## Configuration

**Environment:**
- No `.env` file and no secrets of any kind. The addon makes no network calls of its own
- Runtime configuration lives in Ashita's per-character settings, defaults declared at `inctrack/inctrack.lua:34`:
  - `auto` (bool, default `true`) — automatic show/hide around a run
  - `locked` (bool, default `false`) — window drag lock
  - `session` (string, default `''`) — the in-progress run, JSON-encoded. Deliberately a flat string rather than a nested table so the settings merge cannot reshape it on restore
- Test-only environment variables:
  - `INCURSION_CHATLOGS` — directory of Ashita chatlogs to replay (`test/run_tests.py:47`); can also be passed as `argv[1]`
  - `INCURSION_ASHITA_LIBS` — path to Ashita's `addons/libs` so the persistence suite can `dofile` the real `json.lua`. Otherwise inferred as `<chatlogs>/../addons/libs` (`test/run_tests.py:54`). Suite is skipped if not found

**Build:**
- No build configuration files exist
- `.gitattributes` enforces LF line endings for `*.lua`, `*.py`, `*.md`
- `.gitignore` excludes `__pycache__/`, `.venv/`, `chatlogs/`, `*.log`, and the `config/` and `settings/` directories Ashita writes next to the addon when run from a checkout

## Platform Requirements

**Development:**
- Windows with a CatsEyeXI client install for live testing
- Python 3 with `lupa` for the offline suite: `python test/run_tests.py`, optionally `python test/run_tests.py "C:\path\to\Ashita\chatlogs"`
- Chatlogs are named `<Character>_YYYY.MM.DD.log`; the harness reads the character name off the filename (`test/run_tests.py:64`)

**Production:**
- Distribution is a folder copy (git clone or release download) into the Ashita addons directory. No installer, no package registry, no CI-published artifact
- Version is declared in-source at `inctrack/inctrack.lua:22` (`addon.version = '1.1.0'`) and mirrored in `CHANGELOG.md`

---

*Stack analysis: 2026-08-28*

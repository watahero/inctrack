# Technology Stack

**Analysis Date:** 2026-08-29

## Languages

**Primary:**
- Lua (Lua 5.1 semantics, as embedded by Ashita v4) — the entire shipped addon:
  `inctrack/inctrack.lua` (661 lines), `inctrack/parser.lua` (512),
  `inctrack/state.lua` (1048), `inctrack/ui.lua` (535).

**Secondary:**
- Python 3.14.5 — test harness only, never shipped: `test/run_tests.py` (6255 lines),
  `test/stubs.py` (1504 lines).
- Markdown — `README.md`, `CHANGELOG.md`, `docs/design.md`, `.planning/`.

## Runtime

**Environment:**
- **Ship target:** Ashita v4 on Windows, against the CatsEyeXI FFXI client
  (`<CatsEyeXI install>\catseyexi-client\Ashita\addons\inctrack\`). Ashita
  embeds **LuaJIT 2.1**, so the shipped code must hold to **Lua 5.1 semantics** —
  no integer division, no `goto`-era 5.4 idioms, no 5.4 `require` second return.
- **Test host:** CPython 3.14.5 driving an embedded Lua through `lupa` 2.8.
  `lupa` 2.8 ships seven backends — `lua51`, `lua52`, `lua53`, `lua54`, `lua55`,
  `luajit20`, `luajit21` — and a plain `lupa.LuaRuntime()` resolves to whichever
  was built in. `lua_runtime()` in `test/run_tests.py` (~line 393) selects one by
  name from the `INCTRACK_LUA` environment variable:

  ```
  INCTRACK_LUA=luajit21 python test/run_tests.py
  ```

  An unknown name raises with the list of shipped backends. The suite is verified
  green on **Lua 5.5** (lupa's default build on the contributor machine) and on
  **LuaJIT 2.1** (the dialect Ashita actually embeds). `test/stubs.py` carries its
  own `lua_type` shim (~line 30) because module-level `lupa.lua_type` only
  recognises proxies from the one backend a plain `LuaRuntime()` resolved to.

**Package Manager:**
- None for the addon. No `package.json`, `requirements.txt`, `pyproject.toml`,
  `Cargo.toml` or `go.mod` exists anywhere in the repository.
- Lockfile: none, and none wanted — the addon is copied into an Ashita addons
  directory by hand or by `git clone`.
- The single Python dependency is installed ad hoc: `pip install lupa`.

## Frameworks

**Core:**
- Ashita v4 addon framework — `ashita.events.register`, `AshitaCore`, and the
  stock libraries `common`, `chat`, `settings`, `json`, `imgui`. See
  `.planning/codebase/INTEGRATIONS.md`.
- Dear ImGui, reached through Ashita's `addons/libs/imgui.lua`, for the whole HUD
  (`inctrack/ui.lua`).

**Testing:**
- No third-party test framework. `test/run_tests.py` is a hand-rolled harness:
  eleven suite functions printing thirteen result lines, a `Result` type with
  `xfail` support, and `main()` guarding totals against `EXPECTED_XFAILS` /
  `EXPECTED_DEFECTS` (both now empty).
- `lupa` 2.8 is the only import that is not stdlib (`os`, `re`, `sys`, `glob`,
  `time`, `importlib`, `traceback`).
- `test/stubs.py` supplies a recording ImGui stub and in-memory Ashita host fakes
  so `ui.lua` and `inctrack.lua` can run outside the game.

**Build/Dev:**
- No build step, no bundler, no transpiler, no CI config. The `.lua` files under
  `inctrack/` are the deliverable verbatim.

## Key Dependencies

**Critical:**
- `lupa` 2.8 (Python) — embeds real Lua so the suite exercises the *shipped*
  `parser.lua` / `state.lua` / `ui.lua` / `inctrack.lua` rather than a
  reimplementation.
- Ashita v4's own `addons/libs/json.lua` — used at runtime by the addon, and used
  by the persistence suite (`test_json_roundtrip`, `test/run_tests.py` ~line 2913)
  to round-trip the real save format. Located next to the chatlogs
  (`<Ashita>\addons\libs`) or via `INCURSION_ASHITA_LIBS`; absent, that suite skips
  rather than fails.

**Infrastructure:**
- None. No database, no network client, no server component.

## Configuration

**Environment:**

Only the test harness reads environment variables; the addon reads none.

| Variable | Read at | Purpose |
|----------|---------|---------|
| `INCTRACK_LUA` | `test/run_tests.py` ~393 | Pin the lupa Lua backend (`lua51`..`lua55`, `luajit20`, `luajit21`). Unset = lupa's default. |
| `INCURSION_CHATLOGS` | `test/run_tests.py` ~100 (`find_logs`) | Directory of Ashita chatlogs for the replay suites. Also positional argv[1]. |
| `INCURSION_ASHITA_LIBS` | `test/run_tests.py` ~103 (`find_ashita_libs`) | Path to Ashita's `addons/libs` for the `json.lua` round-trip suite. |

No `.env` file exists and none is expected.

**Addon settings:**
- Persisted through Ashita's `settings` library, per character profile.
  `default_settings` in `inctrack/inctrack.lua` (~line 39): `auto` (bool),
  `locked` (bool), `session` (JSON-encoded in-progress run, deliberately a single
  string so the settings merge cannot reshape the nested table on the way back in).
- Ashita writes these next to the addon; `.gitignore` excludes `config/` and
  `settings/` so a checkout run in place never ships them.

**Build:**
- `.gitattributes` pins `*.lua`, `*.py`, `*.md` to LF with `* text=auto`.
- `.gitignore` excludes `__pycache__/`, `*.pyc`, `.venv/`, editor/OS junk,
  `chatlogs/` and `*.log` (personal and large — point the suite at them with
  `INCURSION_CHATLOGS`), and `config/` / `settings/`.

## Platform Requirements

**Development:**
- Python 3.14.5 with `lupa` 2.8 for the suite; a text editor for the Lua.
- Optional: a real Ashita install for chatlog replay and the `json.lua` suite.
- The suite runs with no Ashita dependency at all for `parser.lua` and
  `state.lua`; `ui.lua` and `inctrack.lua` go through the stubbed hosts.

**Production:**
- Windows, Ashita v4, CatsEyeXI client. Install by copying `inctrack/` into
  `<CatsEyeXI install>\catseyexi-client\Ashita\addons\inctrack\` (must contain all
  four `.lua` files), then `/addon load inctrack`, optionally added to
  `<Ashita>\scripts\default.txt`.
- Read-only with respect to the game: chat stream only, no packet or memory
  inspection beyond the party member-name lookup.

**Version:** `addon.version = '1.2.0'` (`inctrack/inctrack.lua` ~line 22).
Licensed MIT (`LICENSE`).

---

*Stack analysis: 2026-08-29*

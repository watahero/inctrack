# Codebase Structure

**Analysis Date:** 2026-08-28

## Directory Layout

```
inctrack/
├── inctrack/           # The shippable addon folder — copies to <Ashita>\addons\inctrack\
│   ├── inctrack.lua    # Entry point; folder name must match addon.name
│   ├── parser.lua      # Chat line -> event (pure)
│   ├── state.lua       # Event -> run record (pure)
│   └── ui.lua          # Run record -> ImGui
├── docs/
│   └── design.md       # Message-stream ground truth and intended design
├── test/
│   └── run_tests.py    # Python + lupa harness; loads the real Lua modules
├── .gitattributes      # text=auto; LF enforced for .lua/.py/.md
├── .gitignore          # Excludes chatlogs, *.log, config/, settings/
├── CHANGELOG.md
├── LICENSE             # MIT
└── README.md           # Install and usage
```

Four Lua files, one Python file, four Markdown files. No build step, no package manifest, no lockfile, no dependency directory.

## Directory Purposes

**`inctrack/` (inner):**
- Purpose: the complete deployable addon; nothing outside it is installed
- Contains: only Lua modules
- Key files: `inctrack.lua`, `parser.lua`, `state.lua`, `ui.lua`
- Constraint: Ashita v4 resolves `require('parser')` relative to the addon folder, so all modules must be flat siblings of `inctrack.lua`. There are no subdirectories here and adding one would need explicit path handling.

**`test/`:**
- Purpose: the entire test suite, in one file
- Contains: `run_tests.py` — eight suites driving the shipped Lua through `lupa`
- Inputs: a chatlog directory (argv[1] or `INCURSION_CHATLOGS`) and Ashita's `addons/libs` (`INCURSION_ASHITA_LIBS`); log-backed suites skip when absent

**`docs/`:**
- Purpose: design record, including the verified message-stream table that is the project's ground truth
- Contains: `design.md` only

## Key File Locations

**Entry Points:**
- `inctrack/inctrack.lua`: sets `addon.name/author/version/link/desc`, registers `load`, `unload`, `text_in`, `d3d_present`, `command`, plus a `settings.register` profile-change callback
- `test/run_tests.py`: `main()` at the bottom, guarded by `if __name__ == "__main__"`

**Configuration:**
- `inctrack/inctrack.lua` `default_settings` (`auto`, `locked`, `session`) — the only configuration surface; Ashita writes the per-character profile itself
- `.gitignore`: `config/` and `settings/` are Ashita's own per-character output when the addon runs from a checkout, and are never committed

**Core Logic:**
- `inctrack/parser.lua`: the `specific` and `generic` matcher arrays and `parser.parse`
- `inctrack/state.lua`: `new_run`, `State:apply`, the derived accessors, `serialise`/`restore`

**Testing:**
- `test/run_tests.py`: `test_parser`, `test_replay`, `test_state_units`, `test_future_content`, `test_disconnect`, `test_timers`, `test_json_roundtrip`

## Naming Conventions

**Files:**
- Lowercase single-word `.lua` per module; the module file name is the `require` name (`require('state')` → `state.lua`)
- The addon folder, the entry file, and `addon.name` are all `inctrack` — Ashita requires this match

**Directories:**
- Lowercase, single word: `inctrack/`, `docs/`, `test/`

**Lua identifiers:**
- `snake_case` for locals and functions; `SCREAMING_SNAKE` for module constants (`STALE_SECONDS`, `LINGER_SECONDS`, `CONTENT_W`, `BAR_MAIN`, `MUST_SAVE`, `ARG_*`, `COLOR`, `STAT_SHORT`)
- `State` is the one PascalCase name — it is a metatable-based class with `State.__index = State` and colon methods
- Event type strings are lowercase snake and paired between parser and state: `begin`, `recover`, `complete`, `phase`, `objective_kills`, `objective_boss`, `objective_text`, `boss_hint`, `bonus_new`, `bonus_progress`, `bonus_done`, `generic_counter`, `generic_done`, `generic_note`, `time`, `points`, `boon`

**Python identifiers:**
- `snake_case` functions, `SCREAMING_SNAKE` module constants (`HERE`, `ADDON`, `PLAYER`, `TS`, `MUST_PARSE`); suites are `test_*` functions collected manually in `main()`, not by a runner

**File headers:**
- Every Lua file opens with a `--[[ ... ]]--` block: name, copyright/MIT line, "Written with Claude (Anthropic)", then a prose description of the module's contract

## Where to Add New Code

**A new server message shape:**
- Precise handling: add a matcher closure to the `specific` array in `inctrack/parser.lua`, placed so it cannot be shadowed by (or shadow) a neighbour
- Reduce it: add a `if t == '<type>' then` branch in `State:apply` (`inctrack/state.lua`)
- Draw it: add or extend a `draw_*` helper in `inctrack/ui.lua` and call it from `ui.render`
- If the server will not repeat the message, add its type to `MUST_SAVE` in `inctrack/inctrack.lua`
- If it belongs in the save blob, extend both `State:serialise` and `State:restore`
- Cover it: add assertions to `test_state_units` or `test_future_content` in `test/run_tests.py`

**A new derived value for the UI:**
- Add a method on `State` in `inctrack/state.lua`, not a computation in `ui.lua` — this keeps the render path pure and the value testable

**A new command or setting:**
- `default_settings` and the `command` handler in `inctrack/inctrack.lua`; also update the usage block printed by the fallthrough branch, the header comment, and `README.md`

**A new test:**
- A `test_*(...)` function in `test/run_tests.py` returning a `Suite`, appended in `main()`

**Utilities:**
- No shared helper module exists. Helpers are file-local (`trim`, `split_mobs`, `split_expiry` in `parser.lua`; `clock_str`, `right_text`, `wrapped`, `bar`, `urgency`, `replace_plain`, `shorten` in `ui.lua`). Keep them local rather than introducing a `util.lua`.

## Special Directories

**`inctrack/` (inner addon folder):**
- Purpose: the install artifact
- Generated: No
- Committed: Yes

**`config/`, `settings/`:**
- Purpose: Ashita's per-character settings written next to the addon when running from a checkout
- Generated: Yes
- Committed: No (`.gitignore`)

**`chatlogs/`, `*.log`:**
- Purpose: real Ashita chatlogs replayed by the log-backed test suites
- Generated: Yes (by the game)
- Committed: No — personal and large; point the harness at them with `INCURSION_CHATLOGS`

**`.planning/codebase/`:**
- Purpose: generated codebase analysis documents
- Generated: Yes
- Committed: Per project convention

---

*Structure analysis: 2026-08-28*

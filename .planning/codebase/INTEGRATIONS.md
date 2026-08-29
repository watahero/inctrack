# External Integrations

**Analysis Date:** 2026-08-29

The addon integrates with exactly one thing: the Ashita v4 host process, and
through it the CatsEyeXI server's chat stream. There is no network client, no
HTTP, no database, no telemetry, and no third-party service of any kind.

## APIs & External Services

### Ashita v4 addon API

**Event registrations** — all in `inctrack/inctrack.lua`:

| Event | Alias | Line | What it does |
|-------|-------|------|--------------|
| `load` | `incursion_load` | ~225 | Prints the version banner, fetches the player name, resumes a saved run. |
| `unload` | `incursion_unload` | ~253 | Clears `save_due` and calls `persist()` unconditionally — the one path that cannot wait for a frame. |
| `text_in` | `incursion_text_in` | ~268 | The whole ingest path. Read-only: the message is never modified and `e.blocked` is never set here. Wrapped in `pcall`. |
| `d3d_present` | `incursion_present` | ~370 | Per-frame. Performs the deferred settings write (above both early returns), then calls `ui.render` inside a `pcall`. |
| `command` | `incursion_command` | ~543 | Handles `/incursion` and `/inc`; sets `e.blocked = true` on a match. |

**`AshitaCore` calls** — one, used twice:

- `AshitaCore:GetMemoryManager():GetParty():GetMemberName(0)` —
  `inctrack/inctrack.lua` ~230 (load handler) and ~296 (deferred re-fetch inside
  `text_in`, because the name is not always available at load time when logging
  in with the addon already active).
- `AshitaCore:GetGuiManager()` is never called by name from addon code; it is
  reached implicitly as the `__index` of the `imgui` table (see below).

**Stock libraries required** — `inctrack/inctrack.lua` ~26-37:

| Module | Use |
|--------|-----|
| `common` | Required for side effects only (the `T{}` prelude constructor used by `default_settings` and `incursion`). |
| `chat` | `chat.header(addon.name)` + `chat.message(...)` inside `printf` (~120). Every player-facing line goes through it. |
| `settings` | `settings.load(default_settings)` (~50), `settings.save()` (~143, 169, 245, 598, 606, 660), and `settings.register('settings', 'incursion_settings_update', ...)` (~624) for the character-profile switch. |
| `json` | `pcall(json.encode, blob)` in `persist()` (~141) and `pcall(json.decode, saved)` in `resume()` (~198). Both always protected — the decoded *shape* is then validated separately in `State:restore` (`inctrack/state.lua` ~632). |
| `imgui` | The HUD. Required in both `inctrack/inctrack.lua` ~37 and `inctrack/ui.lua` ~73; both handles are the same table through `package.loaded`. |

**Sugar string methods** (Ashita's `addons/libs/sugar/string.lua`, installed onto
the `string` metatable by the host):

- `string:strip_colors()` — called once per relevant line at
  `inctrack/inctrack.lua` ~286. The host implementation removes **three** marker
  bytes — `0x1E`, `0x1F`, `0x7F` — each followed by one payload byte, in a
  **single** gsub with a character class:

  ```lua
  -- addons/libs/sugar/string.lua, string_mt.strip_colors
  return (self:gsub('[' .. string.char(0x1E, 0x1F, 0x7F) .. '].', ''));
  ```

  Both the byte set and the gsub count are load-bearing. The set is what
  `parser.relevant`'s unconditional-yes fall-through must be a superset of
  (`inctrack/parser.lua` ~426-431 searches `\30`, `\31`, `\127`); a gate that
  models only two of the three would silently drop every `0x7F`-coded line. The
  count feeds the PERF-04 reject-cost figures — the stub in `test/stubs.py` ~897
  did two gsubs where the host does one until Phase 4's review, which inflated the
  recorded baseline.
- `string:args()` — `e.command:args()` in the command handler (~544).
- `string:lower()`, `string:find`, `string:gsub`, `string:byte` are plain Lua.

**Clock:** Ashita exposes no monotonic clock to addons, so `now()`
(`inctrack/inctrack.lua` ~130) uses `os.clock` — on Windows this is wall time since
process start with sub-second resolution. `os.time()` is used separately for
`saved_at` and the staleness check (`inctrack/state.lua` ~598, ~906). Two clocks
with different epochs, deliberately, and both stubbed independently in the harness.

### ImGui bindings

`imgui` resolves through Ashita's `addons/libs/imgui.lua`. **There is no Lua-side
wrapper**: that file is a constants table whose `__index` is
`AshitaCore:GetGuiManager()`, so every call reaches the C++ binding's signature
unmediated (documented at `inctrack/ui.lua` ~505-512). Consequences the code
depends on:

- `imgui.Begin(name, p_open, flags)` is declared once and positionally
  (`plugins/sdk/imgui.h:305`), so flags must go in slot 3 and `p_open` must be an
  explicit `nil` — `inctrack/ui.lua` ~513. Passing `nil` asks for no close control
  at all, which is right for a window drawn without a title bar.
- `pcall(imgui.End)` would read `imgui.End` through `__index` *before* `pcall` is
  entered, so an error escapes the handler. The shell's stack repair therefore
  wraps each call in a closure: `pcall(function () imgui.End(); end)` and
  `pcall(function () imgui.PopStyleVar(1); end)` — `inctrack/inctrack.lua` ~514-524.

**Functions used** (all from `inctrack/ui.lua` except the repair pair):
`Begin`, `End`, `CalcTextSize`, `Dummy`, `GetCursorPosX`, `SetCursorPosX`,
`SameLine`, `TextColored`, `ProgressBar`, `PushStyleColor`, `PopStyleColor`,
`PushStyleVar`, `PopStyleVar`, `PushTextWrapPos`, `PopTextWrapPos`.

**Enum globals read** (set by the host, stubbed by the harness):
`ImGuiCol_PlotHistogram`, `ImGuiStyleVar_ItemSpacing`,
`ImGuiWindowFlags_AlwaysAutoResize`, `ImGuiWindowFlags_NoScrollbar`,
`ImGuiWindowFlags_NoTitleBar`, `ImGuiWindowFlags_NoFocusOnAppearing`,
`ImGuiWindowFlags_NoMove`.

### CatsEyeXI chat message stream

The server's own chat text is the addon's only data source — no packets, no
memory reads. `parser.relevant` (`inctrack/parser.lua` ~426) is the cheap gate run
on the **raw** message before any allocation, because `text_in` fires on every
line the client receives and over 127 real logs 97.5% of them are not ours. It
uses `string.find(..., 1, true)` (plain, index-returning, never allocating) and
answers in two rules:

1. Unconditional yes for any line carrying a colour marker byte (`\30`, `\31`,
   `\127`) — a payload byte can land inside a needle, so such a line is one the
   gate is not entitled to judge.
2. Otherwise yes when the line holds any of seven literal needles, each a
   substring the corresponding matcher's pattern cannot match without, under every
   alternation and optional group:
   - `Incursion [`
   - `New Objective: `
   - `Bonus Objective: `
   - `(Boss: `
   - `remaining inside this Incursion` — begins after the optional plural, because
     the one-minute warning sends "1 minute remaining"
   - `incursion points.`
   - `gains the effect of ` — the loosest; boons carry no other anchor, so every
     ordinary buff line pays one wasted colour strip and is then turned away by
     the anchored rejection in `parser.parse`.

`parser.parse` re-asks the same question so the module is safe standalone, trims,
and strips any number of `[HH:MM:SS] ` timestamp prefixes (a timestamp plugin may
be active; the chatlogs show doubled stamps) before its `^`-anchored patterns run.

## Data Storage

**Databases:** None.

**File storage:** Ashita's per-character settings file, written by
`settings.save()`. The in-progress run lives there as `settings.session`, a JSON
string produced by `State:serialise()` + `json.encode`. Nothing else is written.
Writes are deferred to the `d3d_present` handler (Ashita exposes no asynchronous
write, and `settings.save()` is a synchronous disk write that must not run on the
chat thread); failures re-arm behind a 5-second retry window
(`SAVE_RETRY_SECONDS`, `inctrack/inctrack.lua` ~100).

**Caching:** In-memory only — `ui.forget()` clears the memoised boon shorthand on
reset and on character switch.

## Authentication & Identity

- No auth. Identity is the FFXI character name from
  `GetParty():GetMemberName(0)`, used to filter the player's own points messages.
- Character changes arrive through the `settings` profile-switch callback
  (`settings.register`, ~624), which resets the run, clears `render_off` /
  `parse_told` / `save_told` / `save_due` / `save_retry_at`, calls `ui.forget()`,
  and sets the player name back to `nil` so `text_in` re-fetches it.

## Monitoring & Observability

**Error tracking:** None external. Three "say it once" latches print a single
chat line per session and then go quiet: `render_off` (render raised inside
`d3d_present`), `parse_told` (chat handler's `pcall` returned false), `save_told`
(a write raised out of `persist()`). All three are cleared by `/incursion reset`
and by a character change; `render_off` is additionally cleared by bare
`/incursion`.

**Logs:** Player-facing chat lines only, via `printf` →
`chat.header`/`chat.message` → `print`. The test harness captures `print` into
`__host_chat` rather than writing stdout.

## CI/CD & Deployment

**Hosting:** None. Distribution is GitHub
(`https://github.com/watahero/inctrack`, `addon.link`) — release download or
`git clone`, then a folder copy into the Ashita addons directory.

**CI pipeline:** None. No `.github/workflows`, no CI config of any kind. The
suite is run manually: `python test/run_tests.py [chatlog_dir]`.

## Environment Configuration

**Required env vars:** None at runtime. The harness optionally reads
`INCTRACK_LUA`, `INCURSION_CHATLOGS`, `INCURSION_ASHITA_LIBS` — see
`.planning/codebase/STACK.md`.

**Secrets location:** No secrets exist in this project. `chatlogs/` and `*.log`
are gitignored as personal data, not as credentials.

## Webhooks & Callbacks

**Incoming:** None (network). Host callbacks: the five `ashita.events`
registrations plus the `settings.register` profile-switch callback.

**Outgoing:** None. The addon never sends anything to the server; it does not
even echo to chat except through `print`, and it blocks only its own
`/incursion` / `/inc` commands.

---

*Integration audit: 2026-08-29*

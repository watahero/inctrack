# External Integrations

**Analysis Date:** 2026-08-28

There are **no network integrations**. The addon opens no sockets, calls no HTTP
API, and inspects no packets or process memory beyond one Ashita accessor. Its
two "external" surfaces are the **Ashita v4 addon API** and the **CatsEyeXI
server's chat message stream**.

## APIs & External Services

### Ashita v4 addon API — the entire host surface

**Addon metadata (globals set by the host, populated at load):**
- `inctrack/inctrack.lua:20-24` — `addon.name`, `addon.author`, `addon.version` (`1.1.0`), `addon.link`, `addon.desc`

**Ashita libraries required (`inctrack/inctrack.lua:26-32`):**

| Library | Where | Used for |
|---|---|---|
| `common` | `inctrack/inctrack.lua:26` | `T{}` tables; the `string:strip_colors()` extension |
| `chat` | `inctrack/inctrack.lua:28` | `chat.header(name)` + `chat.message(text)` in `printf()` (`inctrack/inctrack.lua:57`) |
| `settings` | `inctrack/inctrack.lua:29` | `settings.load()`, `settings.save()`, `settings.register()` |
| `json` | `inctrack/inctrack.lua:30` | `json.encode` / `json.decode` of the session blob |
| `imgui` | `inctrack/ui.lua:28` | The whole window |

**`ashita.events.register(event, alias, fn)` — four handlers, all in `inctrack/inctrack.lua`:**

| Event | Alias | Line | Responsibility |
|---|---|---|---|
| `load` | `incursion_load` | `inctrack/inctrack.lua:110` | Print the identifying banner, read the player name, restore a saved run |
| `unload` | `incursion_unload` | `inctrack/inctrack.lua:137` | `persist()` the run to settings |
| `text_in` | `incursion_text_in` | `inctrack/inctrack.lua:147` | The data feed. Read-only; wrapped in `pcall` so a parse failure can never take the chat handler down. Never sets `e.blocked` and never mutates `e.message` |
| `d3d_present` | `incursion_present` | `inctrack/inctrack.lua:187` | Per-frame render via `ui.render()`; a close click sets the manual override |
| `command` | `incursion_command` | `inctrack/inctrack.lua:204` | `/incursion` and `/inc`; sets `e.blocked = true` on match |

**`text_in` event shape used:** only `e.message` is read (`inctrack/inctrack.lua:149`). It is passed through `line:strip_colors()` before parsing because the parser patterns are `^`-anchored and colour codes would defeat them.

**`command` event shape used:** `e.command:args()` (Ashita's tokenizer), then `args[1]:lower()` for the command and `args[2]:lower()` for the subcommand — so commands are case-insensitive (`inctrack/inctrack.lua:205-212`).

**`AshitaCore` memory manager — the single memory read:**
- `AshitaCore:GetMemoryManager():GetParty():GetMemberName(0)` — the local player's name
- Called at `inctrack/inctrack.lua:114` (load) and again lazily at `inctrack/inctrack.lua:161` inside `text_in`, because the name is not available at load time when the addon is already active during login
- Needed to filter `<name> gains N incursion points.` and boon messages to the local character only

**ImGui bindings (`inctrack/ui.lua`) — the complete call surface:**
- Window: `imgui.Begin('inctrack###incursion_window', ARG_OPEN, flags)` / `imgui.End()` (`inctrack/ui.lua:407,422`)
- Flags: `ImGuiWindowFlags_NoFocusOnAppearing`, `AlwaysAutoResize`, `NoScrollbar`, `NoTitleBar`, plus `NoMove` when locked (`inctrack/ui.lua:396-402`)
- Style: `imgui.PushStyleVar(ImGuiStyleVar_ItemSpacing, {4,2})` / `PopStyleVar`; `imgui.PushStyleColor(ImGuiCol_PlotHistogram, color)` / `PopStyleColor` around each bar (`inctrack/ui.lua:116-118`)
- Text: `imgui.TextColored`, `imgui.SameLine`, `imgui.CalcTextSize`, `imgui.GetCursorPosX`, `imgui.SetCursorPosX`, `imgui.PushTextWrapPos` / `PopTextWrapPos`
- Widgets: `imgui.ProgressBar(fraction, size, overlay)`, `imgui.Dummy(size)` (the invisible spacer that pins content width to `CONTENT_W = 300`, `inctrack/ui.lua:63,409`)
- Per-frame argument tables are hoisted to module locals (`ARG_SPACER`, `ARG_BAR_MAIN`, `ARG_BAR_THIN`, `ARG_OPEN`, `ARG_PAD_TIGHT`, `inctrack/ui.lua:71-75`) to avoid GC churn at 60fps

### CatsEyeXI server — the chat message stream

The server is the sole data source, consumed one-way through `text_in`. Nothing is ever sent back. `inctrack/parser.lua` translates lines to event tables; `docs/design.md:25-41` holds the full message table.

**Prefilter** (`inctrack/parser.lua:303`) — chat volume in a party is high, so a line is rejected cheaply unless it starts with `Incursion [`, `New Objective: `, `Bonus Objective: `, `(Boss: `, `You have <digit>`, or ends with `incursion points.`, or contains the `): ` boon tail. Leading `[HH:MM:SS] ` timestamp prefixes (a timestamp plugin may add doubled stamps) are stripped in a loop first (`inctrack/parser.lua:289`).

**Specific message contracts consumed:**

| Server message | Event |
|---|---|
| `You have 90 minutes remaining inside this Incursion.` | `time` — timer sync, whole minutes only, arrives *before* `Begins!` |
| `Incursion [Fort Ghelsba] Begins! (Normal)` | `begin` |
| `Incursion [Giddeus] Recovering session...` | `recover` — **re-syncs only the timer**; objective, phase, boss and boons are never re-announced |
| `Incursion [X] Complete! (Normal) Time: 48m 44s` | `complete` |
| `Incursion [X] Phase #3 12/15` | `phase` |
| `New Objective: Defeat 20 enemies (A, B, C)` | `objective_kills` |
| `New Objective: Defeat <NM> at (G-6)!` | `objective_boss` |
| `(Boss: <NM> at (G-6))` | `boss_hint` |
| `Bonus Objective: Defeat 5 <mob>! (Expires in 10 Minutes)` | `bonus_new` kind `kills` |
| `Bonus Objective: Defeat <NM> at (H-9)! (Expires in 10 Minutes)` | `bonus_new` kind `nm` |
| `Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)` | `bonus_new` kind `chest` |
| `Incursion [X] Bonus Objective: <mob> 2/5` | `bonus_progress` |
| `Incursion [X] Bonus Objective Complete!` | `bonus_done` |
| `<name> gains 84 incursion points.` | `points` — one per phase; the count equals phases cleared |
| `<name> gains the effect of <Boon> (<glyph>): <stats>` | `boon` — the `(glyph): stats` tail is what distinguishes it from an ordinary buff |

**Generic (forward-compatibility) tier** — tried only after every specific matcher declines, so it can never shadow one (`inctrack/parser.lua:214-250`): `New Objective: <anything>` → `objective_text`; `Incursion [X] <label> N/M` → `generic_counter`; `Incursion [X] <label> Complete!` → `generic_done`; `Bonus Objective: <anything>` → `bonus_new` kind `text`; `Incursion [X] <anything else>` → `generic_note`. No instance, boss, mob, objective or difficulty name is hardcoded anywhere, so new content appears without a code change. The test suite asserts this tier matches **nothing** in current chatlogs — a generic firing on a real line means a specific pattern has regressed.

## Data Storage

**Databases:**
- None.

**File Storage:**
- Ashita's per-character settings file, written next to the addon. Accessed only via the `settings` library, never by path
- The run is stored as `settings.session`: a single JSON **string** produced by `state:serialise()` (`inctrack/state.lua:528`) and `json.encode` in `persist()` (`inctrack/inctrack.lua:82`). A flat string, not a nested table, so the settings merge cannot reshape it on the way back in
- Restore is defensive: `pcall(json.decode, ...)` plus a `type(blob) == 'table'` check plus `state:restore(blob)` returning true; anything corrupt or stale is discarded wholesale rather than half-applied (`inctrack/inctrack.lua:122-133`). `state.lua:597` additionally drops blobs older than `STALE_SECONDS` using the `saved_at = os.time()` stamp written at `inctrack/state.lua:554`

**Write policy:**
- `MUST_SAVE` (`inctrack/inctrack.lua:64`) lists events the server will never repeat — `begin`, `recover`, `complete`, `objective_kills`, `objective_boss`, `objective_text`, `boss_hint`, `bonus_new`, `bonus_done`, `generic_done`, `boon` — and forces an immediate disk write
- Everything else (kill counts, which arrive constantly and are cheap to lose) is throttled to one write per 5 seconds via `incursion.save_at` (`inctrack/inctrack.lua:176`)

**Caching:**
- None.

## Authentication & Identity

**Auth Provider:**
- None. Identity is the FFXI character name read from `GetMemberName(0)`, used purely to filter the local player's `points` and `boon` messages
- `settings.register('settings', 'incursion_settings_update', ...)` (`inctrack/inctrack.lua:279`) fires when Ashita switches character profiles (login, logout, character change). The handler resets the run, clears the cached player name to `nil` so the next `text_in` re-fetches it, and attempts to restore the new profile's own saved run — keeping the old name would silently filter out the new character's points messages

## Monitoring & Observability

**Error Tracking:**
- None external. The `text_in` handler wraps everything in `pcall` and prints `parse error: <err>` to the game console on failure (`inctrack/inctrack.lua:182`)

**Logs:**
- Chat-console output only, via `printf()` → `chat.header`/`chat.message`. A load banner identifies the build and author explicitly so it is not mistaken for another Incursion addon (`inctrack/inctrack.lua:112`)
- Ashita's own chatlog files are consumed *by the test harness* as replay input; the addon never writes them

## CI/CD & Deployment

**Hosting:**
- Not applicable. Distribution is a git clone or release download copied into `<Ashita>\addons\inctrack\`

**CI Pipeline:**
- None. No `.github/` directory exists. Tests are run manually: `python test/run_tests.py`

## Environment Configuration

**Required env vars:**
- None for the addon.
- Test-only, both optional: `INCURSION_CHATLOGS`, `INCURSION_ASHITA_LIBS`

**Secrets location:**
- None exist. The addon handles no credentials and makes no outbound requests

## Webhooks & Callbacks

**Incoming:**
- None (HTTP). The Ashita event callbacks listed above are the only inbound surface

**Outgoing:**
- None. The addon transmits nothing — no packets, no telemetry, no chat commands sent to the server

---

*Integration audit: 2026-08-28*

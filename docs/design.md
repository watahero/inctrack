# IncursionTracker — Design

**Target:** Ashita v4 (CatsEyeXI), Lua + ImGui
**Install path:** `<Ashita>\addons\incursiontracker\`
**Author:** Godwen, written with Claude (Anthropic). Independent project; see README.

Revised 2026-08-20: loot tracking removed, generic parser tier added,
disconnect handling, renamed from `incursion` to `IncursionTracker`.

## Purpose

A live HUD window showing the current CatsEyeXI Incursion objective and progress,
driven entirely by parsing the server's chat message stream. No packet inspection,
no memory reading.

A second goal, equal in weight: **the addon must keep working when the server
adds content.** No instance, boss, mob, objective or difficulty name appears
anywhere in the code.

## Message stream (ground truth)

Verified against ~106 real runs across 8 instances in the author's chatlogs
(`<Ashita>\chatlogs\<Character>_YYYY.MM.DD.log`).

| Message | Meaning |
|---|---|
| `You have 90 minutes remaining inside this Incursion.` | Timer sync. Fires on entry and after each phase. Whole minutes only, and arrives *before* `Begins!`. |
| `Incursion [Fort Ghelsba] Begins! (Normal)` | Run start. Difficulty in parens. |
| `Incursion [Giddeus] Recovering session...` | Reconnect/zone-in. **Only re-syncs the timer** — does not re-emit objective or phase. |
| `New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)` | Phase kill objective. |
| `(Boss: Orcish Martial at (G-6))` | Boss preview for the current phase. Coords may carry a `(Map #N)` suffix. |
| `Incursion [Fort Ghelsba] Phase #1 7/20` | Kill progress. Phase number and cap both vary (phases seen up to `#8`; caps `/10`, `/15`, `/20`). |
| `New Objective: Defeat Orcish Martial at (G-6)!` | Kills done — boss is up. |
| `Godwen gains 84 incursion points.` | Boss defeated. One per phase; count of these == phases cleared. |
| `Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)` | Bonus, kill-count form. |
| `Bonus Objective: Defeat Sentinel Lizard at (I-8)! (Expires in 10 Minutes)` | Bonus, named-NM form. |
| `Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)` | Bonus, chest form. |
| `Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 2/5` | Bonus progress. |
| `Incursion [Fort Ghelsba] Bonus Objective Complete!` | Bonus done. |
| `Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s` | Run over. |
| `Godwen gains the effect of Ronin's Revenge (<glyph>): WS Accuracy+15 / Store TP+8` | Boon picked between phases. The `(glyph): stats` tail distinguishes it from an ordinary buff (`gains the effect of Protect.`). Not re-announced on recovery. |

## Architecture

Four modules, each with one responsibility. `parser` and `state` are pure Lua
with no Ashita dependency, so they run under a standalone interpreter for
testing.

```
incursiontracker.lua  entry: registers text_in / d3d_present / command; owns settings
   |
   +-- parser.lua   chat line -> event table (or nil). Stateless, two tiers.
   +-- state.lua    event -> run record. Owns timers. Injectable clock.
   +-- ui.lua       run record -> ImGui. Read-only.
```

### parser.lua

`parser.parse(line) -> event|nil`, in two tiers.

**Specific tier** — the shapes the server sends today, recognised precisely so
the window can draw bars, coordinates and timers: `begin`, `recover`,
`complete`, `phase`, `objective_kills`, `objective_boss`, `boss_hint`,
`bonus_new`, `bonus_progress`, `bonus_done`, `time`, `points`, `boon`.

Patterns are anchored and ordered where two could overlap (`bonus_progress`
before `phase`; `objective_kills` before `objective_boss`; the bonus
chest/count/NM forms in that order).

**Generic tier** — tried only after every specific pattern declines, so it can
never shadow one. It exists so content added later still reaches the window
instead of being dropped:

| Pattern | Event |
|---|---|
| `New Objective: <anything>` | `objective_text` |
| `Incursion [X] <label> N/M` | `generic_counter` |
| `Incursion [X] <label> Complete!` | `generic_done` |
| `Bonus Objective: <anything>` | `bonus_new` (kind `text`, expiry still parsed) |
| `Incursion [X] <anything else>` | `generic_note` |

Generic events carry `generic = true`. The test suite asserts that **no generic
pattern matches anything in the current chatlogs** — a generic firing on a real
line means a specific pattern regressed and the window silently lost detail.

A cheap prefix check rejects non-Incursion lines before any pattern runs, since
this executes on every chat line.

### state.lua

Holds at most one active run:

```
run = {
  instance, difficulty,
  phase, kills_cur, kills_max,
  objective  = { kind = 'kills'|'boss'|'text', count, mobs, name, loc, text },
  next_boss  = { name, loc },
  bonus      = { kind, label, cur, max, expires_at, done },
  extra      = { [label] = { label, cur, max, done, at } },   -- unknown counters
  note       = { text, at },                                  -- unknown status line
  boons      = { { name, stats }, ... },                      -- picks, in order
  time_left, time_sync,          -- seconds; ticked locally, snapped on sync
  started, points, phases_cleared,
  finished, finish_time, hide_at,
}
```

Rules:

- `begin` starts a fresh run. The entry timer sync arrives *before* it, so a
  pending sync is held and applied here — otherwise the clock stays blank until
  the first phase boundary ten minutes in.
- `recover` keeps a live run of the same instance; otherwise it starts a partial
  run whose objective stays unknown until the next message fills it in. Either
  way the run is marked **desynced**, as is any run restored from disk.
- While desynced, everything held is a lower bound. A `phase` event restores
  confidence in the progress; a fresh objective restores it in the mob list and
  boss. Reaching phase N implies N-1 phases cleared, which is the only way to
  notice boss kills that happened while disconnected — and when that inference
  raises the count, `points_partial` is set because those bosses awarded points
  the client never saw.
- A `points` award while desynced means the displayed phase is over, so the
  stale kill progress is cleared rather than left frozen mid-count.
- A bonus whose timer lapsed without completing is dropped rather than shown at
  `0:00`; the server never announces the expiry.
- **Any** instance-tagged event naming a different instance resets the run. This
  is deliberately generic so it guards new message shapes too.
- `phases_cleared` increments on each `points` event.
- `complete` freezes elapsed time and sets `hide_at = now + 30`.
- A finished run stops absorbing events once its linger window passes, rather
  than mixing later activity into a settled result.
- State is serialised after every event that the server will not repeat, and at
  most every 5s otherwise.

Timers. `time_left` is seeded from the whole-minute sync and decremented from a
monotonic clock, so it is displayed as approximate (`~58:00`) and snaps whenever
a fresh sync arrives. Bonus expiry counts down from its announcement. Unknown
status notes age out after 30s. The clock is injected (`os.clock` in game, a
fake in tests) to keep tests deterministic.

### ui.lua

One window, fixed width, height auto-fitting, position and size remembered by
ImGui against the `###` id.

```
+--------------------------------------------+
| Fort Ghelsba                        Normal |
|--------------------------------------------|
| Phase #3                             12/15 |
| [########################......]           |
| Orcish Grunt, Orcish Neckchopper, Orcish   |
| Stonechucker                               |
| Next: Orcish Sieger                  (I-9) |
|--------------------------------------------|
| BONUS  Sentry Lizard                  6:00 |
| [############..................]      2/5  |
|--------------------------------------------|
| Time left ~64:00     Elapsed  4:00         |
| Points    233        Phases   2            |
+--------------------------------------------+
```

- The objective block turns into `BOSS  Orcish Sieger  (I-9)` in orange when
  kills are done, or renders raw text for an objective wording we do not know.
- The bonus row is hidden when no bonus is active, and green on completion.
- Unknown counters render below the bonus, one labelled bar each.
- Phase totals are deliberately **not** shown ("Phase #3", not "3 of 4") because
  the count varies by instance and is absent from the chat stream.
- Points and phases cleared are per-run and reset on `begin`.

The window is **fixed width rather than `AlwaysAutoResize`**: right-aligning a
value against the window edge inside an auto-resizing window feeds the
alignment back into the computed width and oscillates.

### Visibility

Auto: shown on `begin` / `recover`, hidden 30s after `complete`. `/incursion`
toggles manually and overrides the automatic state until the next run.

## Commands

| Command | Effect |
|---|---|
| `/incursion` | Toggle the window |
| `/incursion reset` | Clear the current run |
| `/incursion lock` | Toggle window drag lock |
| `/incursion auto` | Toggle automatic show/hide |

`/inc` is accepted as a short form.

## Not tracked

Loot and materials. They land in the inventory anyway, and counting them
correctly required a phrase table plus treasure-pool bookkeeping that added
surface area for no benefit the player could not get by opening their bags.

## Error handling

Parsing runs on `message:strip_colors()` inside a `pcall`; the handler never
modifies, blocks, or consumes a message. An unparseable line is ignored. A
malformed or stale persisted run is discarded rather than half-applied, as is a
finished one.

## Testing

`parser.lua` and `state.lua` are dependency-free, so `test/run_tests.py` loads
them into an embedded Lua runtime (`lupa`) and replays the real chatlogs.

Seven suites: every structural line parses; the generic tier matches nothing that
exists today; each of the 106 recorded runs reconstructs correctly; invented
future content (new instance, new difficulty, `Phase #12`, unknown objective
wording, unknown counters, a bonus with no expiry) is still tracked; disconnects never present
stale numbers as current; the timers count down, linger and go stale correctly;
and the save format survives a JSON round trip through Ashita's own `json.lua`.

The run-reconstruction suite additionally asserts that no clean run is ever
flagged as desynced or short on points, which is what keeps the missed-phase
inference from misfiring on ordinary play.

This is regression coverage against real recorded runs, not synthetic fixtures.

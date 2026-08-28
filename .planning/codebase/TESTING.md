# Testing Patterns

**Analysis Date:** 2026-08-28

## Test Framework

**Runner:** none. `test/run_tests.py` (956 lines) is a **standalone Python script** — no pytest, no unittest, no test discovery. It defines its own `Result` class, prints its own report, and exits `0` / `1`.

**Assertion library:** none. A hand-rolled collector in `test/run_tests.py`:
```python
class Result:
    def __init__(self, title):
        self.title = title
        self.checks = 0
        self.failures = []
        self.notes = []

    def check(self, cond, msg):
        self.checks += 1
        if not cond:
            self.failures.append(msg)
```
Failures **accumulate** rather than abort — one broken pattern reports every line it breaks, not just the first.

**Lua bridge:** [`lupa`](https://pypi.org/project/lupa/) — an embedded Lua runtime inside Python. The suite loads the **shipped** `inctrack/parser.lua` and `inctrack/state.lua`, not a reimplementation. That is the whole point of the design: "a pass here means the shipped code behaves."

**Config:** none. No `pytest.ini`, no `tox.ini`, no `requirements.txt` (the single dependency is documented in the module docstring and `README.md`).

**CI:** none. Tests are run manually.

## Run Commands

```bash
pip install lupa

python test/run_tests.py                              # unit suites only (5 of 8)
python test/run_tests.py "C:\path\to\Ashita\chatlogs" # + replay of real chatlogs
```

**Environment variables** (both read in `test/run_tests.py`):

| Var | Purpose | Fallback |
|---|---|---|
| `INCURSION_CHATLOGS` | Directory of Ashita chatlogs. Used when no positional argument is given. | `None` → replay suites skipped |
| `INCURSION_ASHITA_LIBS` | Path to Ashita's `addons/libs` (for `json.lua`). | `<parent-of-logdir>/addons/libs` → else persistence suite skipped |

Resolution order, from `find_logs()` and `find_ashita_libs()`:
1. `sys.argv[1]` → chatlog dir; else `os.environ["INCURSION_CHATLOGS"]`; else `None`.
2. `os.environ["INCURSION_ASHITA_LIBS"]` → libs dir; else derived as `dirname(abspath(logdir))/addons/libs`; else `None`.

Chatlogs are **never committed** — `.gitignore` excludes `chatlogs/` and `*.log` as personal and large.

## Test File Organization

**Location:** one file, `test/run_tests.py`, at the repo root's `test/` directory. Tests are **not** co-located with source and are **not** written in Lua.

**Naming:** suite functions are `test_<area>(...)` but are called explicitly from `main()`, not discovered.

**Structure:**
```
test/run_tests.py
├── module docstring          # usage, env vars, suite index
├── helpers                   # find_logs, find_ashita_libs, make_lua, new_state,
│                             #   clean, load_lines, feed, extra_of
├── regex constants           # TS, MUST_PARSE, BEGIN, COMPLETE, POINTS, PHASE
├── class Result              # check / note / report
├── test_parser               # suites 1 + 2   [needs logs]
├── test_replay               # suite 3        [needs logs]
├── test_state_units          # suite 4
├── test_future_content       # suite 5
├── test_disconnect           # suite 6
├── test_timers               # suite 7
├── test_json_roundtrip       # suite 8        [needs Ashita libs]
└── main                      # wiring + PASS/FAIL
```

## Test Structure

**Lua runtime bootstrap** — `make_lua()` in `test/run_tests.py`. Note the injected clock: `__clock` is a Lua global the tests move by hand, and `__clockfn` is what `State.new` receives, making every timer deterministic.
```python
def make_lua():
    lua = lupa.LuaRuntime()
    lua.execute("package.path = [[%s\\?.lua;]] .. package.path" % ADDON.replace("\\", "\\\\"))
    lua.execute("__clock = 0")
    lua.execute("function __clockfn() return __clock end")
    lua.execute("__parser = require('parser')")
    lua.execute("__State  = require('state')")
```

**State construction** — `new_state()` builds the Lua options table via `lua.table_from`:
```python
State.new(lua.table_from({"clock": lua.eval("__clockfn"), "player": player}))
```

**Driving the code under test** — `feed()` is the universal fixture verb: raw chat strings in, parser and state exercised as in game.
```python
def feed(state, parser, lines):
    for line in lines:
        ev = parser.parse(line)
        if ev is not None:
            state.apply(state, ev)
```

**Calling Lua methods from Python.** lupa does not bind `self`, so every colon-method takes the object explicitly:
```python
run = s.snapshot(s)
s.time_left(s)
s2.restore(s2, s.serialise(s))
```
This is easy to get wrong when adding tests — always pass the receiver twice.

**Reading Lua values.** Lua tables come back as lupa proxies:
- arrays: `list(run["boons"].values())`, `len(list(run["objective"]["mobs"].values()))`
- numbers: wrap in `int(...)` before comparing (`int(run["points"]) == 84`)
- booleans: wrap in `bool(...)` (`bool(run["finished"])`)
- `extra_of(state)` normalises the generic-counter table into a plain `{label: (cur, max, done)}` dict.

**Advancing time:**
```python
def tick(t):
    lua.execute("__clock = %d" % t)
```
Suites reset with `lua.execute("__clock = 0")` before and after, since the runtime is shared across all suites.

## The Suites

### 1. `test_parser` — "structural lines all parse" [needs chatlogs]
Every real log line matching `MUST_PARSE` must produce a non-`nil` event. `MUST_PARSE` is an independent regex listing the known structural shapes (Begins/Complete/Phase/Bonus/Recovering, `New Objective: Defeat`, `(Boss: … at …)`, the minutes-remaining line, the points line, the boon line). Failure message includes file, line number, and the raw text. Notes the set of event kinds observed.

### 2. `test_parser` — "generic tier matches nothing today" [needs chatlogs]
The inverse assertion, and the most interesting one in the suite: **any** event with `generic == true` fired against a real chatlog is a **failure**. The generic patterns exist only for content the server does not send yet; if one fires today, a specific pattern has regressed and the window has silently lost a progress bar or a coordinate.

### 3. `test_replay` — run reconstruction [needs chatlogs]
Walks every log line once, driving the real state machine, and at each `Complete!` compares the machine's view against facts recomputed straight from the raw text with independent regexes (`BEGIN`, `PHASE`, `POINTS`, `COMPLETE`). Per run it asserts: instance name, total points, `phases_cleared == number of points events`, `finished`, `finish_time` present, final phase number — plus that a cleanly-observed run is **not** flagged `points_partial` and **not** flagged `desynced`.

### 4. `test_state_units` — objectives, bonus, recovery
Synthetic fixtures with the fixed player `Godwen`. Covers: instance/difficulty/phase/kill parsing; kills→boss objective switch (kills snap to max); boss location with a `(Map #N)` suffix surviving intact; all three bonus announcement forms (`kills`, `nm`, `chest`); bonus progress and completion; **only the player's own** points counted, not a party member's; `Recovering session...` preserving a live run of the same instance; a foreign instance message resetting a stale run; completion freezing `elapsed` to the server's reported time and keeping the window shown; boons — recognised only by the `(glyph): stats` tail, ordinary buffs (`gains the effect of Protect.`) ignored, other players' boons ignored, repeat picks deduped in place, and boons cleared by a new run.

### 5. `test_future_content` — adaptability
The suite that enforces the no-hardcoding rule. Invents content the server has never sent — instance `Castle Zvahl Baileys`, difficulty `Mythic`, `Phase #12`, a 40-kill cap, a 120-minute timer, an escort objective, counters `Seals Broken` and `Braziers Lit`, a brazier bonus, a bonus with no expiry at all — and asserts it is all still tracked, that multiple unknown counters coexist without collision, and that an unknown completion line applies to a previously seen counter. Also asserts single and doubled `[HH:MM:SS]` timestamp prefixes still parse, and — the negative case — that ordinary party chat merely mentioning "Incursion" (`LFM Palborough Mines Incursion 5@`, `!incursions`, item-obtained lines) never leaks into the window.

### 6. `test_disconnect` — stale progress is never presented as current
Builds a mid-phase-3 fixture, then reconnects. Asserts: reconnect sets `desynced` but keeps showing progress; the timer resyncs; a return at `Phase #5` infers 4 cleared phases, sets `points_partial`, drops the now-wrong boss preview, and flags the old mob list `stale`; a fresh objective announcement clears every flag; a same-phase reconnect is **not** treated as missed progress; returning after a boss kill clears the finished kill display; a bonus that lapsed while away is dropped rather than shown at 0:00, while a bonus that *completed* before expiring stays visible; and a `restore()` from disk is treated as a disconnect (`desynced` on the restored run).

### 7. `test_timers` — countdown, linger, staleness
Countdown of `time_left` and `bonus_remaining`, `elapsed` advancing, snapping to a new sync, expiry clamping at 0 (never negative), the unrecognised-note 30s ageing-out, elapsed freezing on completion, the 30s linger window then hiding, a finished run past its linger refusing to absorb later points, `restore` rejecting a snapshot older than the 3-hour staleness window, and two back-to-back-run regressions (the entry timer sync arriving before `Begins!` must seed the *new* run's clock, both past the linger window and on an instant re-queue). Finally, a live bonus progress message reviving a bonus whose locally-estimated expiry had already lapsed.

### 8. `test_json_roundtrip` — persistence [needs Ashita libs]
Loads Ashita's **real** `json.lua` via `dofile`, stubbing `T{}` with a passthrough since only encode/decode are exercised. Round-trips a fully populated run (objective + mob list, boss hint, bonus with expiry, generic counter, boon with a raw high-byte glyph, points, phase) and asserts every field survives, including that `bonus_remaining` and `time_left` match across the trip. Also asserts `restore` refuses a **finished** run (it would pop a stale "Complete!" window on next login), refuses a bad `version`, leaves no state behind when it refuses, and that `serialise` of an empty state is `nil`.

## Fixtures and Factories

**Test data is raw chat text.** There are no object fixtures — every scenario is a list of strings fed through the real parser:
```python
s = new_state(lua, State)
feed(s, parser, [
    "You have 90 minutes remaining inside this Incursion.",
    "Incursion [Fort Ghelsba] Begins! (Normal)",
    "New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)",
    "(Boss: Orcish Martial at (G-6))",
    "Incursion [Fort Ghelsba] Phase #1 7/20",
])
```
Add new coverage by adding lines, not by constructing event tables — this keeps the parser in the loop.

**Location:** inline in each suite function. Reusable scenarios are nested factory functions, e.g. `mid_phase()` inside `test_disconnect`.

**Player name:** the constant `PLAYER = "Godwen"` for synthetic fixtures; the replay suites read the real character off the log filenames via `player_from_logs()` (`<Character>_YYYY.MM.DD.log`).

**Log preprocessing:** `clean()` strips the one-or-two `[HH:MM:SS] ` prefixes a timestamp plugin adds (`TS` regex) plus trailing newlines. `load_lines()` returns `(basename, lineno, text)` triples so failures are locatable.

## What Is Skipped, and When

The suite **skips rather than fails** when its optional inputs are missing:

| Missing | Effect |
|---|---|
| Chatlog directory (no argv, no `INCURSION_CHATLOGS`) | Suites 1, 2, 3 not run. `main()` prints `chatlogs: none (pass a directory or set INCURSION_CHATLOGS to replay real runs)`. Overall result can still be `PASS`. |
| `json.lua` not found at the libs path | Suite 8 runs with zero checks and notes `skipped: Ashita json.lua not found (set INCURSION_ASHITA_LIBS)`. |
| `*.log` files absent from a directory that *was* supplied | Hard `SystemExit("no *.log files found in %s")` — an explicitly given path that is wrong is an error, not a skip. |
| `lupa` not installed | Hard `ImportError` at module import. There is no graceful degradation; the suite cannot run at all. |

**Consequence:** a bare `python test/run_tests.py` on a machine with no logs and no Ashita install prints `PASS` while exercising only 5 of 8 suites. Treat a green run without the `chatlogs:` header line as partial.

## Coverage Gaps

**`inctrack/ui.lua` (433 lines) — completely untested.** It requires `imgui`, which only exists inside Ashita. Every layout decision, colour rule, bar computation, `clock_str` formatting, right-alignment against `CONTENT_W`, and the close-button → manual-hide path is verified only by running the addon in game. This is the largest gap by far.

**`inctrack/inctrack.lua` (301 lines) — completely untested.** It requires `addon`, `ashita.events`, `AshitaCore`, `settings`, `common`, and `chat`. Untested behaviour includes:
- the `text_in` pcall boundary and its error path
- the `MUST_SAVE` / 5-second save throttle in `persist()`
- load-time session resume and the "Resumed run in %s" path
- player-name resolution from `GetParty():GetMemberName(0)`, including the deferred fetch when the name is unavailable at load
- the `/incursion` command dispatch (`reset`, `lock`, `auto`, bare toggle, usage) and `e.blocked`
- the `visible()` override-vs-auto logic
- the `settings.register` profile-switch handler (character change clearing run + player name + loading the new profile's session)

**Other gaps:**
- No test asserts the addon never mutates or blocks `e.message` — that guarantee is comment-enforced only.
- `strip_colors()` is an Ashita string extension; colour-coded input is never exercised, only pre-stripped text.
- Replay suites depend on **personal, uncommitted** chatlogs, so suites 1–3 are unreproducible for any other contributor and cannot gate a PR.
- No CI, so nothing runs the suite automatically; regressions surface only when someone runs it by hand.
- No coverage measurement of any kind for the Lua modules.
- Concurrency/ordering hazards from Ashita's event loop (`text_in` and `d3d_present` interleaving) are outside the harness entirely.

## Common Patterns

**Time-dependent testing** — move the injected clock, never sleep:
```python
tick(0)
feed(s, parser, ["Incursion [Fort Ghelsba] Begins! (Normal)",
                 "Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)"])
res.check(int(s.bonus_remaining(s)) == 600, "bonus expiry not seeded")
tick(700)
res.check(s.bonus(s) is None, "expired bonus still displayed")
tick(0)   # leave the shared clock where the next suite expects it
```

**Negative assertions carry equal weight.** Much of the value is in what must *not* happen — the generic tier must stay dormant, ordinary chat must not leak in, a clean run must not be flagged partial, a stale finished run must not absorb points, `restore` must not resume a finished or corrupt snapshot.

**Failure messages name the symptom in user terms**, not the assertion: `"kept showing kill progress after the phase's boss died"`, `"ordinary chat mentioning Incursion leaked into the window"`. Match this style — it is how a failure is diagnosed without reading the test.

**Reporting:** `Result.report()` prints a fixed-width line per suite with the check count, then notes, then up to 10 failures and a `... N more` tail. `main()` ANDs every suite and prints `PASS` or `FAIL`.

---

*Testing analysis: 2026-08-28*

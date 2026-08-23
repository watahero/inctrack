# IncursionTracker

A live HUD for **CatsEyeXI** Incursions. Ashita v4 addon.

Shows the current instance, phase and kill progress, the mobs that count, the
boss waiting at the end of the phase, the bonus objective with its countdown,
time left, points, phases cleared, and the boons you picked — all read from the
server's own chat messages. No packet inspection, no memory reading.

```
+----------------------------------------------+
| Fort Ghelsba . Normal                 ~64:00 |
|############# Phase #3  12/15 #####.........  |
| Orcish Grunt, Orcish Neckchopper, Orcish     |
| Stonechucker                                 |
| Next: Orcish Sieger                    (I-9) |
| BONUS Sentry Lizard  2/5                6:00 |
|=================---------------------------  |
| Pts 233  Ph 2                   Elapsed 4:00 |
| Ronin's Revenge  WS Accuracy+15 / Store TP+8 |
| Stallwart's Sentinel  VIT+10 / Dmg taken-15% |
+----------------------------------------------+
```

> **Not affiliated** with the CatsEyeXI server team or with any other Incursion
> addon or plugin — including the Incursion browser inside the `trove` addon,
> which is a separate project by a different author. This addon tracks a live
> run; it does not browse static content. See [Attribution](#attribution).

## Install

1. Download the latest release or clone this repository:

   ```
   git clone https://github.com/watahero/incursiontracker.git
   ```
2. Copy the `incursiontracker` folder into your Ashita addons directory:

   ```
   <CatsEyeXI install>\catseyexi-client\Ashita\addons\incursiontracker\
   ```

   The folder must contain `incursiontracker.lua`, `parser.lua`, `state.lua`
   and `ui.lua`.

3. In game:

   ```
   /addon load incursiontracker
   ```

   You should see a line in chat confirming the version and author.

4. To load it automatically, add that line to your Ashita default script
   (`<Ashita>\scripts\default.txt`).

The window appears on its own when a run starts and hides 30 seconds after it
finishes.

## Commands

| Command | Effect |
|---|---|
| `/incursion` | Toggle the window |
| `/incursion reset` | Clear the current run |
| `/incursion lock` | Toggle window drag lock |
| `/incursion auto` | Toggle automatic show/hide |

`/inc` works as a short form. Commands are case-insensitive.

## What it shows

- **Phase / kill progress** with the mobs that count toward it, and the boss
  waiting at the end of the phase. When the kills are done the block flips to
  `BOSS  Orcish Sieger  (I-9)` in orange.
- **Bonus objective** with its own progress and a countdown from the
  `Expires in 10 Minutes` announcement. Turns green on completion; the timer
  goes amber then red as it runs out.
- **Time left** counts down from the server's sync and snaps whenever a fresh
  one arrives. Shown with a `~` because the server only ever reports whole
  minutes. Amber under 5 minutes, red under 1.
- **Points and phases cleared** for the current run, reset when a new one starts.
- **Boons** chosen between phases, one per line with their stats. They last
  the whole run, and survive a reload with the rest of it.

The window has no title bar; drag it by its body (`/incursion lock` to pin it).

Phase totals are deliberately not shown — the count varies by instance and the
chat stream never states it. Loot is not tracked; it lands in your inventory
anyway.

## Adapting to content added later

Nothing in the addon hardcodes an instance, boss, mob, objective, or difficulty
name. All of it is read out of the messages, so a new instance or a new boss
simply appears.

For message *shapes* it does not know, the parser has a second, generic tier
that runs only after every specific pattern has declined:

| Unknown message | What happens |
|---|---|
| `New Objective: <anything>` | Shown verbatim in the objective block |
| `Incursion [X] <label> N/M` | Tracked as its own labelled progress bar |
| `Incursion [X] <label> Complete!` | Marks that tracker done |
| `Bonus Objective: <anything>` | Becomes the bonus, with any `Expires in N Minutes` still read |
| `Incursion [X] <anything else>` | Shown as a status line for 30 seconds |

The test suite asserts the generic tier matches **nothing** in current
chatlogs. If a generic pattern ever fires on a real line, a specific one has
regressed and the window would have quietly lost a progress bar or a
coordinate.

## Disconnects

Zoning out, crashing, or reloading the addon mid-run does not lose the run.
State is written to the addon's settings after every event and restored on load.

This matters because the server's `Recovering session...` message only re-syncs
the instance timer — it does **not** re-announce the objective, the phase, or
the boss.

But the party keeps playing while you are gone, and none of it is replayed. So
everything held after a reconnect is treated as a **lower bound**, never as
fact, and the window says which parts it cannot vouch for:

| State | Display |
|---|---|
| Just reconnected | `reconnected - awaiting update`, kill count and bar in amber |
| Back on a later phase | Old mob list kept but marked `(?)`; the old boss preview is dropped |
| Boss kills missed | `Phases` corrected — reaching phase N means N-1 were cleared — and `Points` shown as `233+` |
| Boss died while away | Kill progress cleared to `Waiting for next objective...` rather than frozen mid-count |
| Bonus lapsed while away | Dropped, not left sitting at `0:00` |

Everything clears as soon as real information arrives. Points awarded while
disconnected cannot be recovered — the server sends that number once — which
is why the total is marked `+` rather than quietly under-reported.

## Development

```
incursiontracker/
  incursiontracker.lua   Ashita glue: events, commands, settings, load banner
  parser.lua             Chat line -> event. Pure Lua, stateless, two tiers
  state.lua              Event -> run record. Owns the timers
  ui.lua                 Draws the run record. Read-only
test/run_tests.py        Test suite
docs/design.md           Design notes and the full server message table
```

`parser.lua` and `state.lua` have no Ashita dependency, so the test suite runs
them outside the game in an embedded Lua interpreter:

```bash
pip install lupa
python test/run_tests.py
```

That runs the unit suites (objectives, bonus, recovery, invented future
content, disconnects, timers). To also replay real runs, point it at a
directory of Ashita chatlogs — the character name is read from the filenames:

```bash
python test/run_tests.py "C:\path\to\Ashita\chatlogs"
```

or set `INCURSION_CHATLOGS`. The persistence suite round-trips the save format
through Ashita's own `json.lua`, found next to the chatlogs or via
`INCURSION_ASHITA_LIBS`; it is skipped when unavailable.

Against the author's logs — 120 days, 2.8M chat lines, 106 completed runs
across 8 instances — every structural Incursion line parses, every run
reconstructs correctly, and the generic tier stays dormant.

There is no build step. Edit the `.lua` files and copy the folder across.

## Attribution

**Author:** Godwen (CatsEyeXI).

**Written with Claude** (Anthropic's AI assistant). The design, code, and test
suite were produced in collaboration with Claude; message formats were derived
from the author's own chatlogs.

This is an independent project. It is not affiliated with, endorsed by, or
derived from the CatsEyeXI server, its team, or any other addon. In particular
it shares no code with the `trove` addon's Incursion plugin, which is a static
content browser by a different author — the similar name is a coincidence of
subject, which is why this addon is called *IncursionTracker* and identifies
itself on load.

## License

MIT — see [LICENSE](LICENSE).

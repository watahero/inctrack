# Changelog

## 1.1.0 — 2026-08-23

- Shows the boons picked between phases (`gains the effect of <Boon> (...): <stats>`),
  one per line with their stats in FFXI shorthand. They persist across reloads
  like the rest of the run.
- Much more compact window: no title bar, instance clock on the header line,
  phase and kill count drawn as the progress bar's own label, boss objective as
  a single orange bar, one stats line, thin secondary bars, tighter spacing.
  Roughly half the previous height.
- Points are no longer displayed (still tracked internally to count phases).

## 1.0.0 — 2026-08-20

First release.

- Live window showing the current Incursion's instance, difficulty, phase and
  kill progress, the mobs that count, the boss preview, the bonus objective with
  its expiry countdown, time left, elapsed time, points and phases cleared.
- Auto show/hide around a run; `/incursion` (or `/inc`) to toggle, `reset`,
  `lock`, `auto` subcommands.
- Nothing content-specific is hardcoded. A generic parser tier keeps unknown
  future objectives, counters and bonus wordings visible.
- Run state persists across reloads, zoning and crashes. After a reconnect all
  held progress is treated as a lower bound and marked as such until the server
  confirms it; phases cleared while disconnected are inferred from the phase
  number and points are flagged `+` as incomplete.
- Test suite replays real chatlogs through the shipped Lua modules.

# Changelog

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

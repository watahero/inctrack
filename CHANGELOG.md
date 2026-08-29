# Changelog

## 1.2.0 — 2026-08-29

No new features. Everything the window shows works the way it always claimed
to: three confirmed defects fixed, the paths that could go wrong made to say so
instead, and the cost paid on every chat line cut.

- A bonus objective payout was counted as a cleared phase, so `Phases cleared`
  ran ahead of the run. It now moves only when the server announces a phase, and
  when the run completes.
- After a reload the run clock came back as generous as it had been when the
  addon went away, and a bonus objective that had really already lapsed came
  back still counting down. Time spent unloaded is now taken off both, and a run
  whose instance time has already run out is not resumed at all.
- The window asked for a close control it could never show — it is drawn without
  a title bar, so there was nowhere to put one. `/incursion` is the dismiss.
- An error while drawing the window could repeat sixty times a second. The
  window now takes itself off screen after the first one, says what happened,
  and says that `/incursion` brings it back.
- A boss whose name contains " at " was split in the wrong place and shown
  truncated; the name now survives whole.
- A mob whose name contains a comma became two mobs in the list; the list is now
  split only where the server actually separates it.
- An ordinary buff line could be mistaken for a boon, and a boon whose icon code
  was blank was dropped; both now read correctly.
- A saved run in a shape this build does not recognise is discarded whole and
  said out loud, rather than half-applied in silence.
- Clearing a run no longer lets its instance timer leak into the next one.
- A chat line the addon does not care about now costs nothing — it is turned
  away before anything is built for it.
- Saving the run no longer happens while chat is being read; it rides the next
  frame, and unloading still writes the run down unconditionally.
- If that write is refused — a read-only settings file, or something else
  holding it open — the addon says so once and keeps what it owes, retrying
  shortly, rather than dropping the run in silence or letting the failure
  reach the rest of the frame.
- The boon shorthand the window remembers is now bounded, and is dropped when
  the run is cleared or you switch character.

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

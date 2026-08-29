# inctrack — Design

**Target:** Ashita v4 (CatsEyeXI), Lua + ImGui
**Install path:** `<Ashita>\addons\inctrack\`
**Author:** Godwen, written with Claude (Anthropic). Independent project; see README.

Revised 2026-08-20: loot tracking removed, generic parser tier added,
disconnect handling, renamed from `incursion` to `inctrack`.

Revised 2026-08-29 (v1.2.0): rewritten against the shipped source rather than
against the previous revision of this document. Three defects were fixed, six
fragile paths hardened and four costs cut in the meantime, and this document had
drifted from the code in both directions — describing behaviour the addon never
had, and omitting behaviour it now does. Every statement below was checked
against the file it describes.

## Purpose

A live HUD window showing the current CatsEyeXI Incursion objective and progress,
driven entirely by parsing the server's chat message stream. No packet inspection,
no memory reading.

A second goal, equal in weight: **the addon must keep working when the server
adds content.** No instance, boss, mob, objective or difficulty name appears
anywhere in the code.

A third, which decides every trade below when the first two do not: **what the
window shows is either true, or visibly marked as unconfirmed — never quietly
wrong.** A HUD that lies is worse than no HUD, because the player stops reading
chat and trusts it.

## Message stream (ground truth)

Verified against 111 completed runs across 8 instances in the author's chatlogs
(`<Ashita>\chatlogs\<Character>_YYYY.MM.DD.log`) — 127 logs spanning 130 days
and 2,951,129 chat lines, as re-measured on 2026-08-29.

| Message | Meaning |
|---|---|
| `You have 90 minutes remaining inside this Incursion.` | Timer sync. Fires on entry and after each phase. Whole minutes only, and arrives *before* `Begins!`. At the one-minute warning the server says `1 minute`, singular. |
| `Incursion [Fort Ghelsba] Begins! (Normal)` | Run start. Difficulty in parens. |
| `Incursion [Giddeus] Recovering session...` | Reconnect/zone-in. **Only re-syncs the timer** — does not re-emit objective or phase. |
| `New Objective: Defeat 20 enemies (Orcish Grappler, Orcish Mesmerizer, Orcish Fodder)` | Phase kill objective. The mob list is split on comma-*space*, scanned as plain text: a name carrying its own comma has no space after it, so splitting on the pair keeps such a name whole. A piece that is empty once trimmed is dropped rather than drawn blank. |
| `(Boss: Orcish Martial at (G-6))` | Boss preview for the current phase. The **location** is the anchor, not the name: the pattern captures the name greedily and requires the location to be parenthesised, which puts the split on the *last* ` at (` rather than the first, so a boss whose own name contains " at " survives whole. Coords may carry a `(Map #N)` suffix. |
| `Incursion [Fort Ghelsba] Phase #1 7/20` | Kill progress. Phase number and cap both vary (phases seen up to `#8`; caps `/10`, `/15`, `/20`). |
| `New Objective: Defeat Orcish Martial at (G-6)!` | Kills done — boss is up. Same anchor rule as the boss preview. |
| `Godwen gains 84 incursion points.` | Our own points award; a boss just died. **Not** a count of cleared phases — see `state.lua` below. |
| `Bonus Objective: Defeat 5 Sentry Lizard! (Expires in 10 Minutes)` | Bonus, kill-count form. |
| `Bonus Objective: Defeat Sentinel Lizard at (I-8)! (Expires in 10 Minutes)` | Bonus, named-NM form. Same anchor rule again. |
| `Bonus Objective: Find the hidden chest! (Expires in 10 Minutes)` | Bonus, chest form. |
| `Incursion [Fort Ghelsba] Bonus Objective: Sentry Lizard 2/5` | Bonus progress. |
| `Incursion [Fort Ghelsba] Bonus Objective Complete!` | Bonus done. |
| `Incursion [Fort Ghelsba] Complete! (Normal) Time: 48m 44s` | Run over. |
| `Godwen gains the effect of Ronin's Revenge (<glyph>): WS Accuracy+15 / Store TP+8` | Boon picked between phases. What separates it from an ordinary buff (`gains the effect of Protect.`) is the tail — a parenthesised group, a colon, a space, then stats — **plus a name that is not blank once trimmed**. The glyph group may be **empty**: a server data table with an unset icon field renders `()` through the same template, and a boon dropped there is dropped for good, because the server never announces one twice. The glyph itself is a client-side icon code and is discarded. Not re-announced on recovery. |

## Architecture

Four modules, each with one responsibility. `parser` and `state` are pure Lua
with no Ashita dependency, so they run under a standalone interpreter for
testing.

```
inctrack.lua  entry: registers text_in / d3d_present / unload / command; owns
   |          settings, persistence, the render pcall and the load banner
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

The three ` at ` forms — the boss objective, the boss preview and the named-NM
bonus — try the location-anchored shape first and fall back to the shape that
shipped in 1.1.0 if it declines, so nothing that reached the window before can
stop reaching it. The mob-list split and the boon tail have no fallback tier;
they rest on a survey of the whole corpus instead, which is what the exact
check counts in the test suite pin.

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

### Rejecting a line the addon does not care about

There are two rejections, and both stay. They answer the same question at
different costs on different text.

`parser.relevant(line)` is the first, and the shell calls it in `text_in`
**before `strip_colors`**, on the raw message, which is the only place the
allocation is actually avoidable — no reordering inside `parser.lua` can decline
to make a call the shell already made. It is seven `string.find` searches with
`plain = true`, which return indices and never build a string, so a "no" costs a
fixed number of searches over a short string and nothing else. Each needle is a
literal the corresponding matcher cannot match without, under every alternation
and every optional group: the timer needle is `remaining inside this Incursion`,
beginning *after* the optional plural, because at the one-minute warning the
server drops the `s` and a needle carrying it would silently stop the clock at
the moment it matters most.

A line carrying a colour-code marker byte gets an unconditional **yes**. Ashita's
codes are a marker byte plus one arbitrary payload byte that can land anywhere,
including between two characters of a needle, so a line with a code in it is one
this function is not entitled to judge — it declines, and that line costs exactly
what it cost before the gate existed and never more. The gate may therefore only
ever produce false *positives*, each worth one wasted colour strip.

The marker set is **`0x1E`, `0x1F` and `0x7F`** — the three bytes Ashita's own
`strip_colors` removes, in a single `gsub` with a character class
(`addons/libs/sugar/string.lua`, `string_mt.strip_colors`). The gate's set must
stay a **superset** of the host's, and nothing local can check that: the chatlogs
contain no marker byte at all, because Ashita's log writer strips them on the way
to disk. A marker the shell strips but the gate reads through is a real line
dropped before `strip_colors` ever runs — silently, permanently, and with no
corpus that could have shown it.

`parser.parse` asks the same question again on entry, so the module is safe
called standalone, and then applies the second rejection: after trimming and
stripping any `[HH:MM:SS] ` prefixes, an anchored test against the seven shapes
the matchers accept. The timestamp loop runs only for a line that actually starts
with `[`.

### state.lua

Holds at most one active run:

```
run = {
  instance, difficulty,
  phase, kills_cur, kills_max,
  objective  = { kind = 'kills'|'boss'|'text', count, mobs, name, loc, text, stale },
  next_boss  = { name, loc },
  bonus      = { kind, label, loc, cur, max, expires_at, done },
  extra      = { [label] = { label, cur, max, done, at } },   -- unknown counters
  note       = { text, at },                                  -- unknown status line
  boons      = { { name, stats }, ... },                      -- picks, in order
  time_left, time_sync,          -- seconds; ticked locally, snapped on sync
  started, points, awards_seen, phases_cleared,
  finished, finish_time, elapsed_final, hide_at,
}
```

Four more fields are not created by `new_run` and appear only once something
sets them: `desynced` (out of step with the server), `recovered` (this run was
picked up mid-flight rather than watched from `Begins!`), `points_partial` (the
points total is a lower bound), and `objective.stale` (the mob list probably
belongs to the previous phase). `awards_seen` and `points_partial` are tracked
and **never displayed**; `points` is tracked and never displayed either.

Rules:

- `begin` starts a fresh run. The entry timer sync arrives *before* it, so a
  pending sync is held and applied here if it is under 30 s old — otherwise the
  clock stays blank until the first phase boundary ten minutes in.
- `recover` keeps a live run of the same instance; otherwise it starts a partial
  run whose objective stays unknown until the next message fills it in. Either
  way the run is marked **desynced**, as is any run restored from disk.
- While desynced, everything held is a lower bound. A `phase` event restores
  confidence in the progress; a fresh objective restores it in the mob list and
  boss. Reaching phase N implies N−1 phases cleared, which is the only way to
  notice boss kills that happened while disconnected.
- **`phases_cleared` has a single author, and it is not the points award.** It
  moves when the server announces a phase (reaching `Phase #N` sets it to N−1 if
  that is higher) and when the run completes, which closes the phase we were on.
  Counting points awards instead was the defect fixed in 1.2.0: a bonus objective
  payout is a points award too, and it used to advance the phase count.
- `awards_seen` counts the points awards we actually witnessed, and exists to
  answer one question: on a phase line, more phases behind us than awards we saw
  land means the bosses that cleared the difference paid out to a window that was
  not listening, so `points_partial` is set. It is measured against the awards,
  never against whether `phases_cleared` moved — that now moves on every ordinary
  phase transition.
- A `points` award while desynced means the displayed phase is over, so the
  stale kill progress is cleared rather than left frozen mid-count.
- A `boon` is deduplicated by name: a repeat pick, or a replayed line, updates
  the stats in place rather than listing the boon twice.
- A bonus whose timer lapsed without completing is dropped rather than shown at
  `0:00`; the server never announces the expiry. A `bonus_progress` proves the
  bonus is still live, so a locally-lapsed expiry is cleared rather than hiding
  an objective the server is still counting.
- **Any** instance-tagged event naming a different instance resets the run. This
  is deliberately generic so it guards new message shapes too.
- `complete` freezes elapsed time into `elapsed_final`, records the server's own
  run time, clears the bonus, objective, note and extras, and sets
  `hide_at = now + 30`. It also closes the phase the run was on — **assigned,
  never incremented, and only ever upwards**. An increment invents a number when
  there is nothing to add to: a run joined at the final phase has no phase behind
  it that we ever saw, and claiming one cleared phase for a five-phase run would
  be a confident wrong answer with no uncertainty marking left to carry it, since
  the desync banner is suppressed once a run is finished. So a run we watched
  begin has a floor of one cleared phase; a run we were dropped into gets none.
  Assigning also makes a repeated `Complete!` inside the linger window idempotent
  without a guard.
- A finished run stops absorbing events once its linger window passes, rather
  than mixing later activity into a settled result.
- `reset()` clears the held timer sync (`pending_time`) as well as the run. The hold exists to
  bridge the few seconds between the server's remaining-minutes line and the
  `Begins!` that follows it — not to survive the player throwing the run away in
  between, which would seed the next run's clock with the old one's number.

Timers. `time_left` is seeded from the whole-minute sync and decremented from a
monotonic clock, so it is displayed as approximate (`~58:00`) and snaps whenever
a fresh sync arrives, floored at zero. Bonus expiry counts down from its
announcement. Unknown status notes age out after 30 s. The clock is injected
(`os.clock` in game, a fake in tests) to keep tests deterministic; `state.lua`
never reads a clock directly.

### Persistence and the schema

The in-progress run is stored as a **JSON string in a single settings field**
(`session`), not a nested table, so Ashita's settings merge cannot reshape it on
the way back in. Serialisation lives in `state.lua` rather than in the shell
precisely so the round trip is testable without Ashita. Timers are stored as
remaining *durations*, never absolute clock values, because `os.clock` resets
when the addon reloads; `saved_at` uses wall-clock `os.time`, which is the only
source that survives process death.

**The write policy, as of 1.2.0.** The chat line that changes the run does not
write. It decides whether a write is *owed* — immediately for the events the
server never repeats (`begin`, `recover`, `complete`, all three objective forms,
`boss_hint`, `bonus_new`, `bonus_done`, `generic_done`, `boon`), otherwise at
most once every five seconds — and marks it. The per-frame handler performs the
write, and does so **above both of its early returns**, so a window that is
hidden or that has latched itself off after a render error still has its run
written down. The unload handler writes **unconditionally**, without consulting
the mark, because there will be no further frame; that is what makes deferring
every other write safe at all. The flag is consumed before the write, so a raise
inside it cannot leave the flag set and retry sixty times a second.

The residual is stated rather than hidden: between the chat line and the next
frame there is a window of roughly one frame in which the newest event is not on
disk, and a hard crash inside it loses that one event. That is the trade, taken
knowingly against a synchronous serialise, JSON encode and disk write on the game
thread on every chat line the client receives.

**Schema `version = 2`.** Version 1 was the format shipped by 1.1.0. The split of
the phase counter changed the meaning of a field without changing its name:
`phases_cleared` now counts phases the server announced, where in version 1 it
counted points awards raised to phase−1 by the reconnect inference. A version-1
blob therefore cannot be read field for field, and `restore()` **migrates** it
rather than importing it:

- `phases_cleared` is re-derived from the saved phase number, exactly as a live
  phase line would derive it. The phase number is the one field in that blob the
  server authored outright.
- `awards_seen` starts at **zero**. The real award count is not recoverable —
  the old field over-states it — and an over-stated `awards_seen` would suppress
  the points lower-bound marking for the rest of the run. Starting at zero marks
  rather than hides, which is the only safe direction.

**Restoring.** `restore()` refuses a blob whose `version` is neither 1 nor 2,
one that fails the structural validator below, and one already `finished` —
resuming a finished run would pop a stale `Complete!` window on the next login.
It then works out how long we were gone from the wall-clock gap
`os.time() - saved_at`, clamped at zero, because time spent away can only be
taken off a run and never added to it, and a stamp from the future is clock skew
or a hand-edited settings file. Two refusals follow from the gap:

- older than three hours: stale, discarded;
- gap greater than the saved `time_left` plus a minute of slack: the instance
  clock has already run out, so the run is over whatever the staleness rule
  says. Without this a ninety-minute Incursion could come back inside the
  three-hour window showing `~0:00` in red beside an elapsed counter past the
  instance duration and a phase count that would never move again. Presenting a
  finished run as live is exactly the failure this addon exists to avoid. The
  minute of slack errs towards resuming a run that might still be live.

What comes back is aged by the gap in every direction it touches: elapsed grows
by it, `time_left` shrinks by it and floors at zero, and a bonus countdown moves
down by it — with no special case for one that lapsed while we were away, since
a negative result simply puts the expiry in the past and `State:bonus()` already
drops a not-done bonus past its expiry, which keeps the record in place so a
later progress line can revive it. The objective, boss preview, bonus, boons and
extras are copied **field by field** rather than adopted by reference: the
decoded blob is a table the addon does not own and the caller keeps a handle on
it. The restored run is marked `recovered` and unconditionally `desynced`.

### The restore validator

`json.decode` is already protected; the decoded *shape* is not. A kill cap that
is a string, an objective count the progress bar divides by, a mob list holding a
number where `table.concat` wants a name — all of those are well-formed JSON, and
all of them reach arithmetic one frame later, or inside `restore()` itself, which
runs outside any protected call at both of its call sites. So a file-local
structural validator runs after the version gate and before any field is read for
its value.

Two rules govern it, and both are the core value restated:

- **Reject, never coerce.** A coerced field is a number the server never sent,
  displayed with exactly the same confidence as one it did.
- **Discard whole, never half-apply.** A malformed member fails the entire blob.
  A run resumed with one of the two boons the player picked, and nothing on
  screen saying the other was dropped, is quietly wrong.

And one rule it deliberately does **not** enforce: it checks **what shape this
is, never whether it is informative**. `objective.kind` must be a string and is
never matched against a list of known kinds, so a kind the server adds later
survives — and a list of kinds is content knowledge, which belongs in no Lua file
here. For the same reason a **blank** string passes. A blank is not a wrong
shape; it is the right shape carrying nothing, and every consumer already handles
it — `imgui.TextColored('')` draws nothing at all. The costs are not comparable:
a blank costs one empty row on screen, while refusing the blob costs the whole
run — boons, points, phase, elapsed — and the server re-announces none of it. Nor
is a blank hypothetical, since the addon's own writers produce them from
degenerate server lines (`Incursion [] Begins! (Normal)`, `(Boss:  at (J-9))`),
and blobs written by shipped 1.1.0, which `restore()` still accepts by version,
can carry a blank boon name or a blank mob. What still fails is a field of the
wrong *type*: nil where a name belongs, a number, a nested table.

Lists are checked key by key **and** for contiguity from 1. Every loop that reads
one is driven by `#`, and `#` on a table with a hole is unspecified — keys
`{1, 3}` can answer 1, so a three-boon list would come back holding one boon with
nothing on screen saying the other two were dropped, which is the half-apply the
validator exists to forbid. Checking keys one at a time cannot see that: a hole is
the *absence* of a key, so `pairs()` never visits it. Counting what `pairs()` did
visit and then demanding `1..n` does. It is reachable rather than hypothetical:
`"boons": [{...}, null, {...}]` is well-formed JSON, the settings file is one a
player can hand-edit, and a decoder that drops null elements hands back exactly
`{1, 3}`. Positive-integer keys are tested by the value's own arithmetic
(`k >= 1 and k % 1 == 0`) rather than by an integer subtype, because a
JSON-decoded number is a float and a `tonumber`-derived one may be an integer.

The extras map is checked for string keys and shape-correct values. Their
**lengths** are deliberately not bounded: server text is used as a table key
there, and capping it is recorded as accepted risk rather than done, since this
was a correctness milestone.

### ui.lua

One window. `AlwaysAutoResize`, so the height fits whatever sections are visible
this frame — bonus, extras and boons come and go — plus `NoTitleBar`,
`NoFocusOnAppearing` and `NoScrollbar`, and `NoMove` as well while
`/incursion lock` is on. Position is remembered by ImGui against the `###` id.

The width is **not** left to auto-resize: it is pinned by an invisible spacer of
`CONTENT_W` (300) drawn as the first thing inside `Begin`, and every right-aligned
value and every text wrap is positioned against that constant rather than against
the live window width. Aligning against the live width of an `AlwaysAutoResize`
window feeds the alignment back into the computed size and it never settles. That
hazard is real; the spacer is the mitigation, and the flag stays.

`Begin` is called as `imgui.Begin(name, nil, flags)`. Ashita's binding is
declared once and positionally, so the flags must go in slot 3; the explicit
`nil` for `p_open` asks for **no close control at all**, which is what this window
wants, because it is drawn without a title bar and there is nowhere for one to
appear. Asking for one and ignoring it was the third defect fixed in 1.2.0.

```
+----------------------------------------------+
| Fort Ghelsba . Normal                 ~64:00 |
|############# Phase #3  12/15 #####.........  |
| Orcish Grunt, Orcish Neckchopper, Orcish     |
| Stonechucker                                 |
| Next: Orcish Sieger                    (I-9) |
| BONUS Sentry Lizard  2/5                6:00 |
|=================---------------------------  |
| Phases cleared 2                Elapsed 4:00 |
| Ronin's Revenge              WS Acc+15 STP+8 |
| Stallwart's Sentinel           VIT+10 DT-15% |
+----------------------------------------------+
```

That is one shape out of many. In draw order, with the condition each row
appears under — the same list `ui.lua`'s own layout comment carries, and the one
the whole-window snapshots in the suite are reviewed against:

1. The invisible width spacer. Every frame, unconditionally.
2. The header: instance name, `. difficulty` when known, and right-aligned
   either `Complete <the server's run time>` once finished or the instance clock
   as `~mm:ss` — `--:--` before any sync lands.
3. `reconnected - awaiting update`, while desynced and not finished.
4. The objective block — nothing at all once finished, otherwise exactly one of:
   a full orange bar `BOSS  <name>  <loc>` when the kills are done; the phase
   bar labelled `Phase #N  cur/max`, amber and suffixed ` ?` while desynced,
   followed by the mob list suffixed `  (?)` when it belongs to a phase the
   server never confirmed and then `Next: <name>` with coordinates right-aligned;
   an objective wording the parser did not recognise, drawn verbatim; or
   `Waiting for next objective...` when there is no objective yet.
5. The bonus row, while one is held and unlapsed: `BONUS  Complete!` once done,
   otherwise the label with its count or its coordinates, the countdown
   right-aligned, and a thin strip beneath when it counts.
6. One row per generic counter, with a thin strip when it has a maximum. Gone
   once the run is finished.
7. `Phases cleared N` with `Elapsed m:ss` right-aligned. **The only stats row.**
8. One row per boon picked this run, in pick order, with the stats right-aligned
   in FFXI shorthand — abbreviated for display only, longer phrases replaced
   before their own substrings, and anything not in the table passed through
   untouched so a boon added later still reads.
9. The most recent Incursion line the parser could not interpret, for the thirty
   seconds it stays fresh.

Phase totals are deliberately **not** shown (`Phase #3`, not `3 of 4`) because the
count varies by instance and is absent from the chat stream. Points are tracked
per run and reset on `begin`, and are **not displayed** — the 1.1.0 compaction
removed the row and nothing has put it back.

### Visibility

Auto: shown on `begin` / `recover`, hidden 30 s after `complete`. A bare
`/incursion` toggles manually against what is on screen, and that override lasts
until the next run starts.

With one exception. When the window has switched *itself* off after a render
error, `/incursion` is a **re-enable, not a toggle** — toggling against a window
that is not being drawn would read as "hide it", which is the opposite of what
was asked. It deliberately does not clear the manual override, because whatever
that override held is what put the window on screen on the frame that failed and
is also what brings it back; clearing it would drop a manual show and, for a
player running with automatic show/hide off, that is the only thing keeping the
window visible. The line printed afterwards reports **what is on screen**, not
what was asked for, because the player may have turned automatic show/hide off in
between and no fixed wording is true of every state.

### Render containment

`ui.render` runs inside `d3d_present`, on the game thread, once a frame, and is
handed strings that came off the wire and tables that came out of a JSON blob, so
an error there is reachable. It is not a log line either: it leaves the ImGui
window and style stacks unbalanced for every addon in the process, and then it
happens again on the next frame, and the one after.

So the call is wrapped in a `pcall` in the frame handler — beside the one that
has protected `text_in` since 1.0.0 — rather than inside `ui.lua`, which stays a
pure draw function. Two latches follow from it:

- **`render_off`** is set when the render raises. The handler returns before
  asking anything else on every later frame, so a failure costs one branch a
  frame instead of repeating. `/incursion`, `/incursion reset` and a character
  change all clear it, so there is a stated way back.
- **`render_ok`** is set the first time render returned cleanly *with a run
  drawn*, and is deliberately never cleared by a reset: it is a fact about the
  host, not about the run.

`render_ok` is what makes the stack repair a repair rather than a guess. Three of
render's statements run *before* `Begin`, so a raise from one of them leaves
nothing open and nothing pushed, and an `End` there is an unmatched close — on a
real host, an ImGui assert, and therefore the second error of the frame, which is
the exact failure the containment exists to prevent. When `render_ok` is set, the
render shape has run end to end on this host at least once, so exactly one window
and one style var are owed. When it is not set, **nothing is repaired**: a style
var left pushed is recovered when the frame ends; an unmatched close is not.

The style **colour** stack is deliberately not repaired. Its only push and pop in
the whole file bracket a single ImGui call with no data-driven raise site between
them, so nothing can stop between them. The test suite asserts all three stacks
anyway, so if that ever stops being true the tests say so rather than a guess
quietly papering over it.

Both repair calls are wrapped in closures — `pcall(function () imgui.End(); end)`
— and that is not a formality. `pcall(imgui.End)` would read `imgui.End` *before*
`pcall` is entered, and `imgui` here is Ashita's constants table whose `__index`
is `AshitaCore:GetGuiManager()`, so the read is itself a live call into the GUI
manager. A raise from it would escape the handler exactly as the failed render
would have. The closure moves the read inside.

One residual is stated rather than guarded: the flags arithmetic reads
`opts.locked`, so a nil ImGui constant reached only on the locked path could
raise before `Begin` on a host where an unlocked frame has already drawn clean,
and there the repair would over-close by one window. Nothing data-driven reaches
it and no test provokes it.

### Cost

The `text_in` handler runs on **every** chat line the client receives; over 127
real logs, 97.5 % of them are not ours. `d3d_present` runs sixty times a second.
Four things follow, and the test suite prints the first one's effect as a
lines-per-second figure beside a recorded pre-change baseline in every run, so
the improvement is a number in the report rather than a claim here:

- The reject path costs no allocation. `parser.relevant` is asked before
  `strip_colors`, and the timestamp loop runs only for a line starting with `[`.
  A colour-free line the addon ignores now performs zero colour strips and zero
  `gsub`s. A coloured one costs what it always did, by design.
- The settings write is off the chat thread, as described under Persistence.
- The per-frame argument tables are hoisted, in the shell and in `ui.lua` both:
  ImGui reads them and never keeps them, so rebuilding them sixty times a second
  was pure GC churn.
- The boon-shorthand memo cache is **bounded** at 64 entries and drops whole past
  the cap. Its key is text the server chose and the addon lives as long as the
  client does, so without a bound it grows for a whole play session; 64 is far
  above any run the corpus holds, so the drop can only fire on input the server
  never sent. The whole cache goes rather than one entry being evicted, because a
  run's stat strings are few and repeat every frame — an LRU would be more code,
  on the render path, for no measurable gain — and a drop costs one re-shorten
  per live string on the next frame. `ui.forget()` empties it **in place**, never
  replacing the table, and is called from `reset()` and from the profile-switch
  callback: after a reset there is no run, so the window stops being drawn and
  can never notice for itself that what it cached belongs to nobody.

### What the player is told

"Either true, or visibly marked as unconfirmed" is enforced on screen by the
`reconnected - awaiting update` banner, the `?` on a phase label, the amber bar
colour and the `(?)` on an unconfirmed mob list. It is enforced in chat by three
lines:

- **A saved run that could not be taken up says so.** Silence was defensible
  while the only ways to fail were unreadable JSON, a finished run and a
  three-hour-old blob; the structural validator widened it to every shape
  mismatch. What a rejection looks like to the player is a mid-run reload where
  the HUD comes back with nothing and then bootstraps a fresh run from the next
  Incursion line — phase nil, no boons, elapsed counting from zero, and no
  "reconnected" marking on any of it, because a bootstrapped run is not a
  desynced one. That is a window showing numbers the server never sent, unmarked.
  Silence is still right for a run that had already finished: there is nothing
  left to resume, and saying a run "could not be resumed" when the player watched
  it end would be the same fault pointed the other way.
- **A render error is reported once**, names the window as disabled, and names
  `/incursion` as the way back.
- **A chat line that could not be read is reported once**, and names
  `/incursion reset` as the way to hear about them again. A malformed shape
  arrives on every chat line the client receives, so an unrated complaint is the
  same sentence sixty times in a burst on top of the chat the player was trying
  to read.

Both report-once latches are cleared by `/incursion reset` and by a character
change, so neither is a one-way door.

## Commands

| Command | Effect |
|---|---|
| `/incursion` | Toggle the window — or re-enable it, after a render error |
| `/incursion reset` | Clear the current run, both report-once latches, and any write still owed |
| `/incursion lock` | Toggle window drag lock |
| `/incursion auto` | Toggle automatic show/hide |

`/inc` is accepted as a short form, and subcommands are case-insensitive.

## Not tracked

Loot and materials. They land in the inventory anyway, and counting them
correctly required a phrase table plus treasure-pool bookkeeping that added
surface area for no benefit the player could not get by opening their bags.

## Error handling

Three protected boundaries, and one validator, in the order a bad input meets
them:

1. **The chat handler.** The whole `text_in` body runs inside a `pcall` on
   `message:strip_colors()`; the handler never modifies, blocks or consumes a
   message, and an unparseable line is simply ignored. The failure path only
   prints — it does not reset state, disable anything, or stop the handler
   reading the next line — and it prints once per session. The error text is
   always an argument and never part of a format string, because a percent sign
   in server text is one of the things that gets us there in the first place.
2. **The frame handler.** The render `pcall`, its two latches and its conditional
   stack repair, as described above.
3. **The settings round trip.** `json.encode` and `json.decode` are both
   `pcall`-wrapped. A failed encode writes an empty session rather than a partial
   blob; a blob that cannot be decoded is discarded and the stored string
   cleared, so an unusable one is not retried on every load forever.
4. **The structural validator**, which keeps a wrong-shaped blob out of the run
   record entirely. It and the render containment are not redundant: the first
   covers what the second cannot see, which is anything the *live* event stream
   produces.

`State:apply` returns `false` for a non-table or a `t`-less argument, and for
events with no run to attach to. A malformed, stale, finished or clock-expired
persisted run is discarded whole, never half-applied.

## Testing

`parser.lua` and `state.lua` are dependency-free, so `test/run_tests.py` loads
them into an embedded Lua runtime (`lupa`) and replays the real chatlogs.
`ui.lua` and `inctrack.lua` are not dependency-free, so they run behind recording
ImGui and Ashita stubs in `test/stubs.py` instead. `inctrack.lua` exports nothing
at all and `ui.lua` exports only `render` and `forget`, so their file-scope state
is reached by upvalue reflection rather than by adding an export to the shipped
code for the tests' benefit.

Eleven suites, reported as twelve result lines — the parser suite emits three:

| Suite | Needs |
|---|---|
| parser coverage — every structural Incursion line parses | chatlogs |
| generic tier — the catch-alls match nothing that exists today | chatlogs |
| tightened patterns — each split re-derived from the raw text and compared | chatlogs |
| run reconstruction — instance, phase, points, completion, per run | chatlogs |
| state units — objectives, bonus, recovery | nothing |
| adaptability — invented future content is still tracked | nothing |
| disconnect — stale progress is never presented as current | nothing |
| timers — countdown, linger, staleness | nothing |
| persistence — the save format through Ashita's own `json.lua` | Ashita's `json.lua` |
| ui — the pure helpers, and whole-window render snapshots | nothing |
| addon shell — registration, chat, settings, commands, the write policy | nothing |
| reject cost — what a line the addon ignores costs, before and after | nothing |

The split matters: the deepest suites replay the author's own chatlogs, which are
not in the repository, so anyone else's run covers less. Coverage of the *shipped*
behaviour is deliberately not gated on that — the window, the addon shell and the
cost figure all run with nothing but Python and `lupa`.

The suites that read logs are the regression net against real recorded runs
rather than synthetic fixtures. The run-reconstruction suite compares the state
machine against facts recomputed straight from the raw text, never from anything
the state machine produced, and additionally asserts that no clean run is ever
flagged as desynced or short on points — which is what keeps the missed-phase
inference from misfiring on ordinary play. The tightened-pattern suite does the
same for the three narrowed patterns: the reference shapes are re-derived in
Python from the raw line, because a reference derived from the parser would drift
with the parser and agree with it while both were wrong.

Two guards sit over the whole run. Every assertion recorded as an expected
failure names the defect it stands for, and the runner compares both the count
and the *set* of names against declared constants — a count alone cannot tell
three defects from three *different* defects. Both constants are empty as of
1.2.0, and an empty set is not a slack one: any name at all mismatches it. A
suite that raises is reported as a failed suite rather than vanishing, so a
regression can never surface as a traceback with no report.

Verification is on two Lua backends, because one of the validator's rules turns
on whether a decoded number is an integer or a float, and only running both
proves the rule is written in a dialect-independent form.

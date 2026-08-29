# Codebase Concerns

**Analysis Date:** 2026-08-29

Scope: full repo at v1.2.0 — `inctrack/inctrack.lua` (661), `inctrack/state.lua` (1048),
`inctrack/ui.lua` (535), `inctrack/parser.lua` (512), `test/run_tests.py` (6255),
`test/stubs.py` (1504).

Each entry is marked **[DEFECT]** — visible in the code as written — or **[RISK]** —
contingent on input, host or sequence. The known-open items carried forward from the
v1.2.0 milestone are listed separately at the end and are **not** findings.

**v1.2.1 (2026-08-29)** closed the three defects and one of the risks, all of them on
the persistence path: the encode failure that destroyed the last good save, `reset()`'s
resurrection ordering, the vestigial `State.dirty`, and the unprotected load and unload
writes. Those entries are kept below, marked **RESOLVED**, with what was done. Line
numbers in every remaining entry are as of v1.2.0 and have shifted; the searchable text
has not.

---

## Tech Debt

### [DEFECT] [RESOLVED 1.2.1] `State.dirty` is written twenty-one times and read zero times

- Files: `inctrack/state.lua:41` (init), `:94`, `:140`, `:161`, `:241`, `:251`, `:263`,
  `:274`, `:281`, `:295`, `:317`, `:330`, `:341`, `:357`, `:363`, `:370`, `:393`,
  `:407`, `:412`, `:446` (all writes).
- Issue: `self.dirty` is set `true` on every state mutation and after `reset()`, and is
  never read — not by `inctrack.lua`, not by `ui.lua`, not by the suite (`grep dirty`
  returns writes only). It is also never cleared back to `false` after `State.new`, so
  even a reader who wired it up would find it permanently latched after the first event.
- Impact: no runtime effect, but it is actively misleading. The persistence decision is
  actually made by `MUST_SAVE` plus the five-second throttle in
  `inctrack/inctrack.lua:106-118` and `:317-321`, and a maintainer reading `state.lua`
  first will reasonably conclude that `dirty` is the thing that drives the disk write. In
  a file whose comments are otherwise unusually load-bearing, a vestigial field that
  contradicts them is a real navigation hazard.
- Fix approach: delete the field, or clear it in a `State:take_dirty()` and route the
  frame handler's `save_due` through it. Deleting is the smaller change and matches what
  the shell actually does.
- **Resolved in 1.2.1** by deleting it — twenty assignments and the initialiser. The
  rule is now derived rather than remembered: the `record:` suite walks every `self.X`
  assigned in `state.lua` and fails on any that nothing reads, so the next vestigial
  field is caught when it is written rather than at the next audit.

### [RISK] Complexity has become its own risk

- Files: `inctrack/state.lua` (1048 lines, ~60% of it prose), `inctrack/inctrack.lua`
  (661 lines, ~60% prose), `inctrack/ui.lua` (~44%), `inctrack/parser.lua` (~49%).
- Issue: the four shipped files total 2,756 lines of which roughly 1,456 are code. The
  structural validator alone (`state.lua:629-861`) is ~230 lines for ~60 lines of
  predicate, and the frame handler's deferred-write comment (`inctrack.lua:371-418`) is
  48 lines in front of 24 lines of code. Individually each block is justified; in
  aggregate the reader must hold four interacting latches (`render_off`, `render_ok`,
  `save_told`, `parse_told`), two clocks (`os.clock` monotonic, `os.time` wall), two
  save gates (`save_due`, `save_retry_at`) and two blob versions in their head at once.
- Impact: the failure mode is not a bug today; it is that the next change is priced
  higher than the change deserves, and that reviewers start skimming prose that is
  carrying real constraints. The three items below (`persist()`'s silent blanking,
  `reset()`'s ordering, `dirty`) all sit inside heavily-commented regions and were not
  caught by the prose. All three are fixed in 1.2.1; the point about the prose stands,
  and 1.2.1 added a little more of it.
- Fix approach: consider moving the validator's rationale (`state.lua:629-739`,
  `:759-786`) into `docs/design.md` and leaving a one-line pointer, and likewise the
  deferred-write essay. This is a documentation-placement change, not a code change, and
  it should not be done casually — the comments are the project's memory. Flagged so the
  cost is priced rather than discovered.

### [RISK] Test harness is 2.8× the size of the code it tests

- Files: `test/run_tests.py` (6255), `test/stubs.py` (1504) against 2756 lines of Lua.
- Issue: 7,759 lines of Python, 11 suites, 13,461 checks. The harness has no tests of its
  own, and `test/stubs.py` encodes non-trivial host behaviour that is asserted against —
  the ImGui stack accounting (`stubs.py:620-637`), the `Begin` positional recorder
  (`:663-681`), the `strip_colors` byte set, the settings-fault injector.
- Impact: a bug in `stubs.py` reads as a passing suite. The `Begin`-shape and
  `strip_colors` cases in particular are places where the stub *is* the specification, so
  a stub that drifts from Ashita makes the suite confidently wrong rather than red.
- Fix approach: no action proposed; recorded so it is a known property rather than a
  surprise. The mitigation already in place — stub comments citing Ashita source paths
  and line numbers — is the right one.

---

## Known Bugs

### [DEFECT] [RESOLVED 1.2.1] A failed `json.encode` silently destroys the last good saved run

- Files: `inctrack/inctrack.lua:139-144`.
- Symptoms: `persist()` reads

  ```lua
  local ok, encoded = pcall(json.encode, blob);
  incursion.settings.session = (ok and blob ~= nil) and encoded or '';
  settings.save();
  ```

  When the encode raises, `ok` is false and the expression falls to `''`. The addon then
  writes that empty string to disk over a perfectly good previously-saved run, and says
  nothing.
- Trigger: any raise out of the host's `json.encode` on a serialised run — the test
  harness's own encoder raises on non-finite numbers (`test/stubs.py`, `numstr`), and
  Ashita's real encoder is a dependency whose failure modes are not enumerated here. The
  blob's strings are server-authored text that has been through `strip_colors` and the
  parser but is otherwise unconstrained.
- Impact: this is the one failure path in the file that is both **silent** and
  **destructive**, and it is the odd one out by design intent. The neighbouring write
  failure is caught, retried on a five-second window, and reported once via `save_told`
  (`:419-442`); the render failure latches and reports; the parse failure reports. An
  encode failure does none of that and additionally overwrites the run it failed to
  encode. A mid-run reload afterwards comes back blank — exactly the outcome the
  persistence layer exists to prevent.
- Workaround: none available to the player; `/incursion reset` is what they would reach
  for and it makes no difference.
- Fix approach: on `not ok`, leave `incursion.settings.session` untouched, skip the
  `settings.save()`, and route the report through the existing `save_told` latch. Blank
  the session only in the one case that means it — `blob == nil`, i.e. there is no run.
  Two branches instead of one ternary.
- **Resolved in 1.2.1** as described. `persist()` now has three outcomes rather than one
  ternary — no run writes `''`, an encoded run writes the blob, and a raise writes
  nothing and is re-raised to the caller, which is already the machinery that keeps what
  is owed, retries behind the five-second window and reports once. The harness gained the
  encode fault it never had (`test/stubs.py`, `__host_encode_fault`), so the branch that
  used to blank the session is now exercised rather than merely reasoned about.

### [DEFECT] [RESOLVED 1.2.1] `reset()` can resurrect the run it cleared, if the disk write fails

- Files: `inctrack/inctrack.lua:146-173`, specifically `:159` (`save_due = false`) and
  `:168-169` (`session = ''; settings.save()`).
- Symptoms: `reset()` clears `save_due` first — correctly, so a stale owed write cannot
  put the run back — and then performs its own unprotected `settings.save()`. If that
  save raises, the exception leaves the command handler, **and** the in-memory
  `session = ''` is now owed to a disk write that no later frame will ever make, because
  `save_due` was just cleared and nothing re-arms it. The old run stays on disk.
- Trigger: a read-only settings file, a full disk, or the file held open by another
  process — the same fault class the frame handler was hardened against this milestone.
- Impact: the player types `/incursion reset`, sees a raise instead of `Run cleared.`,
  and on the next addon load the run they threw away is resumed. This is a consequence of
  the *ordering*, not just of the unprotected save, so it is not fully covered by the
  known-open note that `reset()`'s save is unprotected: fixing only the protection
  (wrapping the call in `pcall`) leaves the resurrection intact.
- Fix approach: on a failed save inside `reset()`, re-arm `save_due = true` so the frame
  handler retries the clear, and report through `save_told`. Same shape as the frame
  handler already uses.
- **Resolved in 1.2.1** as described, and the ordering half was negative-controlled: with
  the `pcall` in place and the re-arm removed, five checks stay red, the resurrection
  among them. The three things a failed write is owed — keep it, bound the retry, say so
  once — are now one `save_failed()` shared by the frame handler, `reset()` and the load
  handler, rather than a copy per caller.

### [RISK] [RESOLVED 1.2.1] The unload and load handlers still write to disk unprotected

- Files: `inctrack/inctrack.lua:259` (`persist()` in the unload handler),
  `inctrack/inctrack.lua:245` (`settings.save()` in the load handler).
- Symptoms: a raise out of `settings.save()` on either path escapes into Ashita's event
  dispatch. The unload case is the more consequential: it fires during addon unload or
  client shutdown, it is documented at `:254-257` as "the one path that cannot wait for a
  frame", and its unconditional write is explicitly what makes deferring every other
  write safe. A raise there means the last write of the session did not happen, on the
  one path with no retry behind it.
- Trigger: same disk fault class as above.
- Impact: silent loss of everything since the last successful frame write, on exactly the
  path that exists to prevent that. Note these two are **not** on the known-open list —
  that list names `reset()`, the command handler and the profile-switch callback, all on
  the command path. The unload path is a different one and is unmentioned.
- Fix approach: `pcall(persist)` in the unload handler. There is nothing useful to do
  with the failure at unload time beyond reporting it, but the raise itself should not
  escape.
- **Resolved in 1.2.1.** The load handler's clear goes through `save_failed()` like every
  other write — frames follow a load, so there is somewhere to retry, and dropping it left
  the unusable blob on disk to be met again on the next load. The unload handler is
  `pcall`ed and reports; the ceiling is stated in the code rather than dressed up, because
  there is no frame left to retry on. Its report is deliberately made *past* `save_told`:
  everything that latch suppresses is a fault that will be tried again, and this one will
  not, so it is a different sentence — 'anything since the last write is lost' — and
  unload fires once, so it cannot become noise.

---

## Security Considerations

### [RISK] The settings file is a player-editable, un-integrality-checked input to arithmetic and `%d`

- Files: `inctrack/state.lua:699-704` (`finite`), `:844-861` (`valid_session`), `:937-938`
  and `:968` and `:985-988` (the reads); consumed at `inctrack/ui.lua:232`, `:277`,
  `:310`, `:312`.
- Risk: `valid_session` checks *shape* and `finite()` removes NaN and ±infinity, and both
  choices are deliberate and well-argued. Neither checks **sign** or **integrality**, and
  neither bounds magnitude. A hand-edited or corrupted `session` blob carrying
  `"phase": -5`, `"phase": 2.5`, `"kills_max": 1e300` or `"phases_cleared": -40` passes
  every gate and reaches the run record intact.
- Current mitigation: `finite()` for the non-finite cases; `bar()` clamps its fraction to
  `[0,1]` (`ui.lua:158-159`) so the drawn bar cannot overflow.
- What it costs: the *labels* are not clamped. `ui.lua:232` formats `'%s  %d/%d'` with
  `run.kills_cur` and `run.kills_max` straight from the blob, and `ui.lua:233` concatenates
  `'Phase #' .. run.phase`. Under LuaJIT — the dialect Ashita embeds — a fractional or
  huge value there prints a truncated or garbage integer; under Lua 5.5 `%d` on a
  non-integral float raises, which reaches `ui.render`, trips `render_off`, and takes the
  window off screen for the session. Either way the outcome is the one the project names
  as its worst: a number on screen the server never sent, drawn with the same confidence
  as one it did. `ui.lua:325` (`tostring(run.phases_cleared)`) will happily print `-40`.
- Recommendations: add a small `count(v)` beside `finite(v)` in `state.lua` that answers
  nil for anything non-integral or negative, and read `phase`, `kills_cur`, `kills_max`,
  `phases_cleared`, `awards_seen`, `points`, and `bonus.cur`/`bonus.max` through it. This
  is the same "reject, never coerce" rule already stated at `state.lua:640-647` — it just
  is not currently applied to the numeric domain, only to the numeric *type*. The two
  reads that are genuinely continuous (`elapsed`, `time_left`, `saved_at`,
  `bonus.remaining`) should keep `finite()` and only gain a sign check where a negative
  is meaningless.

### [RISK] `json.decode` is a trust boundary this repo cannot inspect

- Files: `inctrack/inctrack.lua:30` (`require('json')`), `:198` (`pcall(json.decode, saved)`).
- Risk: the decoded value is a player-editable file's contents. The addon does the right
  things around it — the call is protected, the result is type-checked, the shape is
  validated, and every field is copied rather than adopted (`state.lua:940-944`). What it
  cannot do is verify that Ashita's `json.decode` is a scanner rather than a `load()`-based
  evaluator; no vendored copy ships in this repo. `test/stubs.py`'s replacement encoder is
  explicitly a character-by-character scanner and says why, which pins the harness but not
  the host.
- Current mitigation: `pcall` around the decode, plus the structural validator behind it.
- Recommendations: none actionable in this repo. Recorded in the same spirit as the
  known-open ImGui-binding item: an assumption resting on a dependency whose source is not
  available here. If a vendored `json.lua` ever lands in the tree, this becomes checkable.

---

## Performance Bottlenecks

### [RISK] `run.extra` is unbounded and re-sorted with fresh allocations on every frame

- Files: `inctrack/state.lua:336-343` (`generic_counter` writes), `:528-545`
  (`extra_sorted`), `:1035-1042` (restore copies without limit), `:788-801` (`map_of`,
  unbounded); consumed at `inctrack/ui.lua:297-318`.
- Problem: `run.extra` is keyed by `e.label`, which is trimmed text the *generic* matcher
  pulled out of a server line (`parser.lua:296-305`). Every distinct label the server ever
  sends during a run adds a permanent entry; the table is cleared only on `complete`
  (`state.lua:444`) or `reset()`. `extra_sorted()` then, on every frame in which the table
  is non-empty, allocates a fresh list, allocates a fresh comparator closure, and runs
  `table.sort` over the whole thing.
- Cause: no cap and no eviction, in a file that is otherwise scrupulous about exactly this
  — `NO_EXTRAS` at `state.lua:525` exists to avoid one table allocation per frame, and
  `ui.lua` hoists `ARG_SPACER`, `ARG_BAR_MAIN`, `ARG_BAR_THIN`, `ARG_PAD_TIGHT` and
  `inctrack.lua` hoists `FRAME_OPTS` for the same reason.
- Notable asymmetry: the boon shorthand memo cache **was** given a hard bound this
  milestone (`ui.lua:404`, `SHORT_CACHE_MAX = 64`) with three paragraphs explaining why an
  unbounded server-authored key set is unacceptable. `run.extra` has a server-authored key
  set, no bound, a per-frame sort, and a round trip through the disk blob — and got none of
  that treatment. The argument at `ui.lua:382-403` applies to it verbatim and more forcibly.
- Improvement path: cap `run.extra` the same way (a count, and drop-the-lot or
  drop-oldest-by-`at` at the cap), and either cache the sorted list against a generation
  counter or sort only when `extra` actually changed. The corpus cannot exercise this —
  the suite asserts the generic tier matches nothing in the 127 logs (`parser.lua:36-38`),
  which is precisely why nothing has ever put more than a handful of entries in this table.

### [RISK] The memo cache bounds entry *count*, not key *size*

- Files: `inctrack/ui.lua:404-449` (`SHORT_CACHE_MAX`, `short_cache`, `shorten`),
  `:364-377` (`replace_plain`).
- Problem: the bound is 64 entries; nothing bounds how long a single `stats` string is. On
  a cache miss, `shorten()` runs 21 sequential `replace_plain` passes
  (`ui.lua:435-437`), each of which builds a complete new copy of the string via
  `table.concat`, and then two `gsub`s. That is ~23 full copies of the key on the game
  thread in one frame.
- Reachability: from chat the key is bounded by the client's line length, which makes this
  a non-issue. From a **restored blob** it is not: `valid_boon` (`state.lua:835-837`)
  accepts any string of any length, `restore()` copies it verbatim (`:1031`), and JSON
  string length is unbounded in a file the player can hand-edit. `right_text` then hands
  the result to `imgui.CalcTextSize` (`ui.lua:139`).
- Improvement path: reject or truncate a `stats` (and `name`, and `objective.text`) longer
  than some sane display bound in the validator, or refuse to memoise a key past a length
  and short-circuit `shorten` for it. The cheaper half — refusing to cache an oversized key
  — does not fix the per-frame re-shorten, so the validator side is the one that matters.

### [RISK] `save_at` and `save_retry_at` measure different things and are not reconciled

- Files: `inctrack/inctrack.lua:317-321` (throttle decision), `:419-425` (retry window),
  `:102` (`SAVE_RETRY_SECONDS = 5.0`).
- Problem: `save_at` is stamped when the chat thread *decides* a write is owed, not when
  one lands. After a failed write the retry is deferred by five seconds, during which
  further non-`MUST_SAVE` events see `t - save_at > 5.0` and re-arm `save_due` that is
  already armed — harmless — but the throttle's own window has meanwhile drifted off the
  actual write cadence.
- Impact: cosmetic under any fault-free run; under a persistent disk fault the two
  five-second numbers interleave in a way nothing pins. The code comment at `:98-101`
  reasons about the retry bound being "one fewer number to reason about" by reusing five
  seconds, which is true of the constant and not of the two clocks it now governs.
- Improvement path: stamp `save_at` in the frame handler when a write actually succeeds,
  rather than in `text_in` when one is decided. Small, and it makes the throttle mean what
  its comment says.

---

## Fragile Areas

### [RISK] The profile-switch callback's `s == nil` path saves anyway, and no test can reach it

- Files: `inctrack/inctrack.lua:624-661`; harness at `test/stubs.py`, `__host_switch`.
- Why fragile: the callback body is `if s ~= nil then ... end` followed by an
  **unconditional** `settings.save()` at `:660`. On a `nil` callback argument the addon
  clears nothing, adopts nothing, resumes nothing — and then writes. What it writes is
  whatever `incursion.settings` currently holds, which is the *previous* character's table
  including that character's `session` string. Whether Ashita ever invokes the callback
  with nil is not determinable from this repo; the guard at `:625` exists, so at some point
  someone believed it could.
- Safe modification: move the `settings.save()` inside the `if`, or state explicitly why a
  nil update is owed a write. Either is a one-line change; the current shape is the one
  that cannot be read as intentional.
- Test coverage: none, and none reachable. `__host_switch(over)` in `test/stubs.py` always
  merges defaults with the override and always passes a table, so the `nil` arm of `:625`
  and the save-on-nil at `:660` are both dead to the suite. Extending the stub with an
  explicit nil-fire is cheap and would settle it.

### [RISK] Four latches, three clearing sites, no single owner

- Files: `inctrack/inctrack.lua:78` (`save_told`), `:82` (`render_off`), `:87`
  (`render_ok`), `:95` (`parse_told`); cleared at `:153-163` (`reset`), `:559`
  (`/incursion` bare, `render_off` only), `:635-643` (profile switch).
- Why fragile: three of the four are cleared in two places with the clearing duplicated
  rather than shared — the profile-switch callback's own comment at `:630-634` says so
  outright ("This callback does its own clearing rather than calling `reset()`, so all
  three fields have to be cleared here too"). `render_ok` is deliberately cleared by
  neither. `/incursion` bare clears `render_off` alone. The next latch added has four
  sites to get right and one of them is a comment asking to be remembered.
- One interaction worth naming: `reset()` clears `save_told` — "so the player hears about
  disk faults again" — and then immediately performs the unprotected `settings.save()` at
  `:169` that, on a persistent fault, is the very call most likely to raise. The clearing
  and the raise are two lines apart, and the raise escapes before anything can report it.
  **That half is fixed in 1.2.1**: the save is protected and its failure goes through the
  shared `save_failed()`, so the latch that was just cleared is what reports it. The
  duplication this entry is actually about is unchanged — the *reporting* was factored,
  the *clearing* was not, and the profile-switch callback still keeps its own copy.
- Safe modification: factor the clearing into one `clear_session_latches()` called from
  both `reset()` and the profile-switch callback, leaving `render_ok` explicitly outside
  it with the existing comment. Do not fold `/incursion` bare into it — that path
  deliberately preserves `override`, per `:560-568`.

### [RISK] The deferred write's bound is "the next `d3d_present`", not a duration

- Files: `inctrack/inctrack.lua:406-417` (states the residual), `:419-442`.
- Why fragile: fully documented and correctly reasoned — recorded here only because it is
  the one accepted data-loss window in the design and it is invisible in the code itself.
  A minimised, alt-tabbed or background-throttled client stretches the unwritten interval
  arbitrarily; a client killed in that interval loses everything since the last frame that
  ran, not one event. Orderly exits are covered by the unload handler — which was itself
  unprotected until 1.2.1, so the two concerns compounded: the mitigation for the deferral
  was the one write with no retry and no protection behind it. It is protected now. It
  still has no retry, and it cannot have one.
- Test coverage: the deferral and the retry are covered, and since 1.2.1 so is an unload
  write that fails — the raise is contained and the loss is reported. The compound case (a
  client that stops presenting *and then* fails its unload write) is not covered, and
  probably cannot be; nothing can recover it either, which is the honest ceiling on this
  path.

---

## Scaling Limits

**`run.extra` entries:** no cap. Growth is driven by distinct server-authored labels
reaching the generic counter matcher; the practical current capacity is "however many the
server sends", which is zero across the whole 127-log corpus. See the performance entry
above.

**`short_cache` entries:** 64, enforced at `inctrack/ui.lua:443-445` by dropping the
whole table. Key length is unbounded; see above.

**Boons per run:** unbounded, drawn one row per boon (`ui.lua:452-464`) inside an
auto-resizing window with no scrollbar (`ui.lua:496`). A run with many boons grows the
window until it exceeds the screen, with nothing to scroll. Not reachable from real
content; reachable from a hand-edited blob, since `array_of(data.boons, valid_boon)`
(`state.lua:859`) has no length limit.

---

## Dependencies at Risk

**Ashita `imgui` binding** — known-open, see below.

**Ashita `json`** — see the security entry. No vendored copy and no enumerable failure
modes; what changed in 1.2.1 is only the reaction, which no longer destroys the last good
save. The dependency is exactly as opaque as it was.

**`lupa` / Lua backends in the harness** — `test/stubs.py:29-45` already documents that the
module-level `lupa.lua_type` answers `None` for LuaJIT-built proxies and dispatches around
it. This is a live compatibility seam between the harness and whichever `lupa` a
contributor has installed, and it is asserted on rather than merely used.

---

## Test Coverage Gaps

**Numeric domain of the restore validator** — `state.lua:699-704`, `:844-861`.
Not tested: negative, fractional, or astronomically large values for `phase`,
`kills_cur`, `kills_max`, `phases_cleared`, `awards_seen`. `grep` for fractional or
negative fixtures in `test/run_tests.py` returns nothing relevant. Risk: the `%d`
formats in `ui.lua` consume all of these. **Priority: high** — this is the cheapest
of the gaps to close and the one attached to a live finding.

**~~`persist()`'s encode-failure branch~~** — **closed in 1.2.1.** `test/stubs.py` gained
`__host_encode_fault`, in the same shape as the save fault, and the addon suite points it
at a run already on disk.

**~~`reset()` with a failing save~~** — **closed in 1.2.1.** Both halves are covered: the
raise that escaped the command handler, and the resurrection on the next load.

**~~Unload handler with a failing save~~** — **closed in 1.2.1**, along with the load
handler's clear, which this list did not name.

**Profile-switch callback invoked with nil** — `inctrack.lua:625`, `:660`. Requires a
small extension to `__host_switch` in `test/stubs.py`. **Priority: medium.**

**`run.extra` under many distinct labels** — `state.lua:336-343`, `:528-545`.
Nothing drives more than a handful of generic counters, by construction: the suite
asserts the generic tier matches nothing in the corpus. A synthetic feed of N distinct
labels would pin both the growth and the per-frame sort cost. **Priority: medium.**

**Oversized strings through restore** — `state.lua:835-837`, `ui.lua:428-449`.
No fixture carries a `stats`, `name` or `objective.text` longer than a chat line.
**Priority: low.**

---

## Known-Open Items (carried forward, not findings)

Recorded here so this document is complete. These were established at v1.2.0 and are
not new discoveries.

**Four in-game checks that no test can close.** Nothing in the suite can reach them, and
the reason is structural in each case, not an omission:

- The colour fall-through in `parser.relevant` (`inctrack/parser.lua:427-430`) has zero
  corpus backing by construction — Ashita strips colour markers when writing logs, so no
  real log can carry one.
- The reload clock.
- The window frame following the `Begin` call-shape change (`inctrack/ui.lua:513`).
- The `imgui.End` lookup through Ashita's metatable (`inctrack/inctrack.lua:513-523`).

These are the honest limit of what has been proven.

**`settings.save()` is unprotected on the command path** — in the `lock` and `auto`
subcommands (`inctrack.lua:710`, `:718` as of 1.2.1) and the profile-switch callback
(`:772`). Same fault class as the frame-handler fix. `reset()` left this list in 1.2.1,
along with the load and unload writes recorded as findings above; these three are what
remains, and none of them writes a run — two toggle a setting the player just changed,
and the third belongs to a character that has already gone.

**`Phase  13/0`** — with `kills_max` and `objective.count` both absent, the phase bar's
label at `inctrack/ui.lua:231-233` prints a denominator the server never sent.

**The compiled ImGui binding cannot be inspected** — no binding source ships, so the
`Begin(name, nil, flags)` call shape at `inctrack/ui.lua:513` rests on the SDK header
(`plugins/sdk/imgui.h:305`) plus a survey of 220 call sites.

**PROC-01…04** — CI, luacheck, a versioned release artifact, and a public chatlog fixture
are deliberately deferred, not debt discovered.

---

*Concerns audit: 2026-08-29*

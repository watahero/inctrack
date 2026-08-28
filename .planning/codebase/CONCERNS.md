<!-- refreshed: 2026-08-28 -->
# Codebase Concerns

**Analysis Date:** 2026-08-28

Scope: `inctrack` v1.1.0 — Ashita v4 addon, 4 Lua files (1,722 lines) plus a
956-line Python test harness. Findings are ranked by severity within each
section. Each is marked **[DEFECT]** (a fault visible in the code as written) or
**[RISK]** (a fragility contingent on server behaviour, Ashita binding details,
or future change).

---

## Known Bugs

**[DEFECT] Every points award counts as a cleared phase:**
- Symptoms: `Phases cleared` over-reports whenever the server awards incursion
  points for anything other than a phase boss — a bonus objective payout, a
  chest, a completion bonus.
- Files: `inctrack/state.lua:358-365` (`run.phases_cleared = run.phases_cleared + 1`)
- Trigger: any `<Name> gains N incursion points.` line not caused by a boss kill.
- Contributing: the `phase` handler at `inctrack/state.lua:198-202` derives the
  same counter a second, incompatible way (`e.phase - 1`, monotonic max). The two
  writers agree only under the assumption "one points award == one phase". A
  points award after the last phase can never be corrected by the `phase` path,
  because no further `phase` line arrives.
- Workaround: none in code. Fix approach: make `phase` the sole authority for
  `phases_cleared` and let `points` only accumulate `run.points` / set
  `points_partial`; or require an intervening `phase`/`objective_boss` event
  before an award may increment.

**[DEFECT] Restore does not age the timers by the time the addon was unloaded:**
- Symptoms: after a reload, crash, or relog, the instance clock (`~mm:ss`), the
  elapsed counter and the bonus countdown are all optimistic by exactly the
  downtime — up to `STALE_SECONDS` (3 hours) in the worst accepted case.
- Files: `inctrack/state.lua:600-634`. `run.started = now - (data.elapsed or 0)`
  (`:612`), `run.time_sync = now` (`:621`) and
  `expires_at = now + data.bonus.remaining` (`:632`) all treat the restore
  instant as if it were the save instant.
- Trigger: any gap between `serialise()` and `restore()`. `saved_at` (wall clock,
  written at `state.lua:556`) is already recorded and is used for the staleness
  check at `state.lua:597`, so the correction term is available and simply not
  applied.
- Fix approach: compute `local gap = math.max(0, os.time() - (data.saved_at or os.time()))`
  and subtract it from `elapsed`'s inverse, from `time_left`, and from
  `bonus.remaining` — dropping the bonus outright when the adjusted remaining
  reaches zero.

**[DEFECT] Dead close-button path; the window has no title bar:**
- Symptoms: the manual-hide branch can never fire, yet both files carry code and
  comments implying it can.
- Files: `inctrack/ui.lua:399` adds `ImGuiWindowFlags_NoTitleBar`, so
  `imgui.Begin(..., ARG_OPEN, ...)` (`ui.lua:407`) never writes
  `ARG_OPEN[1] = false`; the check at `ui.lua:427-429` is therefore dead, as is
  the `shown == false` handler at `inctrack/inctrack.lua:219-222` with its
  comment "Closing via the title bar counts as a manual hide."
- Trigger: unreachable. Harmless at runtime, but a false affordance that will
  mislead the next change to visibility handling.
- Fix approach: delete the `ARG_OPEN` plumbing, or drop `NoTitleBar` if a close
  button is actually wanted.

**[RISK] `objective_boss` splits on the first " at ":**
- Symptoms: a mob whose name contains " at " is truncated, and the remainder is
  folded into the location.
- Files: `inctrack/parser.lua:135` — `'^New Objective: Defeat (.-) at (.+)!$'`.
  The name capture is non-greedy, so the *earliest* " at " wins. Same shape at
  `parser.lua:145` (`boss_hint`) and `parser.lua:176` (`bonus_new` NM form).
- Trigger: any FFXI NM name containing the substring (the "Goblin at Arms"
  construction is real in the game's name space).
- Fix approach: anchor on the location instead — split with
  `' at (%(.+%))$'` — since the location is reliably parenthesised coordinates.

**[RISK] Mob-list splitting assumes names contain no commas:**
- Files: `inctrack/parser.lua:34-41` (`split_mobs`, splitting on `[^,]+`).
- Trigger: a comma-bearing mob name in the `New Objective: Defeat N enemies (...)`
  list produces phantom entries in `run.objective.mobs`, displayed verbatim at
  `inctrack/ui.lua:204-206`.

---

## Fragile Areas

**[RISK] The whole feature rests on exact server wording — the single largest structural risk:**
- Files: `inctrack/parser.lua:63-201` (14 specific matchers), all `^`-anchored and
  literal down to punctuation: `'Begins!'`, `'Complete! (%s) Time: %dm %ds'`,
  `'Bonus Objective: Find the hidden chest!'`, `'incursion points.'`.
- Why fragile: CatsEyeXI is a private server that can reword any message in any
  patch, with no notice and no versioning. A single changed word silently demotes
  a line from the specific tier to the generic tier (or to nothing), and the addon
  degrades from progress bars and timers to a line of grey text without ever
  reporting a problem.
- Mitigations already present and worth preserving: the generic tier
  (`parser.lua:206-262`) keeps unknown Incursion-tagged content visible instead of
  dropping it, and `state.lua` holds no instance, boss, mob or objective names at
  all — so new server content needs no change in the state machine.
- Missing mitigation: nothing surfaces "a specific pattern stopped matching." The
  test suite asserts the generic tier matches nothing in today's logs
  (`test/run_tests.py`, suite 2), but that runs offline against the author's
  private logs. In game, a generic-tier hit is indistinguishable from normal
  operation.
- Safe modification: never add to `specific` without honouring the ordering
  contract documented at `parser.lua:54-62`. Three ordering pairs are
  load-bearing — `bonus_progress` before `phase` (`parser.lua:100` / `:113`),
  `objective_kills` before `objective_boss` (`:125` / `:135`), and
  chest → count → named NM (`:150` / `:161` / `:172`). Reorder any of them and a
  real line is captured by the wrong shape, with no error and no test failure
  unless the chatlogs happen to contain that case.
- Test coverage: strong for `parser.lua` and `state.lua` — but only when the
  private chatlogs are supplied (see *Test Coverage Gaps*).

**[RISK] The boon matcher is the loosest pattern in the file:**
- Files: `inctrack/parser.lua:194` —
  `'^(%S+) gains the effect of (.-) %(.-%): (.+)$'`.
- Why fragile: it distinguishes an Incursion boon from an ordinary buff purely by
  the presence of a parenthesised glyph followed by `': '`. Any future server or
  third-party message shaped `<word> gains the effect of X (Y): Z` is absorbed as
  a boon and rendered in the window. It is also the only matcher reachable via the
  broadest clause of the fast-path guard, `s:find('): ', 1, true)`
  (`parser.lua:294`).

**[RISK] Desync inference is heuristic and partly self-cancelling:**
- Files: `inctrack/state.lua:88-101` (`desync` / `resync`), `:133-150` (`recover`),
  `:196-231` (`phase`), `:358-380` (`points`), `:600-618` (`restore`).
- Why fragile: `phase` clears `desynced` at `state.lua:227` on the grounds that a
  kill count is live information — but that same handler has *already* consumed
  `run.desynced` two branches earlier (`:208-215`) to decide whether to invalidate
  the mob list and drop the boss preview. Any future reordering silently disables
  that invalidation. `phase` also clears the flag directly rather than through
  `resync()`, deliberately preserving `run.objective.stale`; that asymmetry
  between the two clearing paths is undocumented at the call site.
- Second-order: `recover` reuses the existing run when the instance name matches
  and it is under three hours old (`state.lua:139-142`), then marks it desynced.
  A player who re-enters the *same* instance as a genuinely new run within that
  window inherits the previous run's phase, points and boons, because
  `Recovering session...` carries no phase or objective to contradict them.
- Safe modification: change `state.lua` only with suites 4-7 of
  `test/run_tests.py` green; they exist precisely to pin this logic.

**[RISK] `ui.render` runs unprotected inside `d3d_present`:**
- Files: `inctrack/inctrack.lua:209-223`. Contrast the `text_in` handler
  (`inctrack.lua:160-204`), which wraps everything in `pcall` for exactly this
  reason.
- Why fragile: an error thrown between `imgui.Begin` (`ui.lua:407`) and
  `imgui.End` (`ui.lua:421`) leaves the ImGui window stack unbalanced *and* skips
  the matching `imgui.PopStyleVar(1)` (`ui.lua:404` / `:424`). Unbalanced ImGui
  stacks do not degrade gracefully — they assert or corrupt subsequent frames for
  every addon in the process — and the fault recurs on every frame thereafter.
- Reachable error paths in the render tree, all fed by data that came off the wire
  or out of a JSON blob:
  - `table.concat(obj.mobs, ', ')` (`ui.lua:202`) errors if `mobs` holds a
    non-string. `restore` adopts `run.objective = data.objective` wholesale
    (`state.lua:606`) with no shape validation, so a truncated or hand-edited
    settings file reaches this line directly.
  - `imgui.CalcTextSize(text)` is consumed as a single number at `ui.lua:95`. If
    the binding returns a vector or a second value in a different position, the
    arithmetic errors — and `right_text` is called from five sites.
  - `imgui.TextColored(color, text)` is handed server-supplied strings at
    `ui.lua:137` (instance), `:238`/`:243` (bonus label), `:263` (generic label),
    `:363` (boon name) and via `wrapped` at `:204`/`:206`/`:374`. If the Ashita
    binding forwards these as a printf format string, a `%` in server text is a
    hazard rather than a display glitch.
- Fix approach: `pcall` the render; on failure, force `imgui.End()` and
  `PopStyleVar` cleanup, then disable the window with a single chat message rather
  than repeating the error sixty times a second.

**[RISK] Restored state is trusted structurally:**
- Files: `inctrack/state.lua:583-654`. `version`, `instance`, `finished` and age
  are checked (`:584-597`); `objective` (`:606`) and `next_boss` (`:607`) are
  adopted as-is, and `data.extra` entries (`:646-652`) are copied with only a
  label fallback. `kills_max`, `objective.count` and `bonus.max` are never
  type-checked, and a string where a number belongs reaches arithmetic in
  `ui.lua:196-200`, `:233` and `:266-269`.
- Current mitigation: `json.decode` is `pcall`-wrapped at `inctrack.lua:135` and
  `:288`, so malformed *JSON* is safe. Well-formed JSON of the wrong *shape* is
  not.
- Recommendation: validate types field-by-field on restore rather than assigning
  decoded sub-tables by reference.

---

## Performance Bottlenecks

**[RISK] Per-chat-line cost is paid before the cheap rejection, not after:**
- Problem: `text_in` fires for every line in the chat stream — hundreds per second
  in a full party during combat — and each line allocates several strings before
  anything decides it is irrelevant.
- Files, in execution order:
  1. `inctrack/inctrack.lua:167` — `line:strip_colors()` allocates a new string
     for *every* line, unconditionally.
  2. `inctrack/parser.lua:270` — `trim()` (defined `parser.lua:28-30`) runs two
     chained `gsub`s, each allocating.
  3. `inctrack/parser.lua:277-283` — the timestamp-stripping `while` loop runs a
     `gsub` per iteration, plus one more just to discover there is nothing to
     strip.
  4. Only then does the prefix guard at `parser.lua:286-294` reject.
- Cause: the guard is documented as the cheap path ("Chat volume in a party is
  high and this runs on every line", `parser.lua:286`) but sits behind three
  allocating steps. Its final clause, `s:find('): ', 1, true)` (`parser.lua:294`),
  is broad enough that ordinary player chat and many system messages fall through
  into all 14 specific matchers and then all 5 generic ones.
- Improvement path: run a cheap `find` on the *raw* line before `strip_colors` and
  before `trim`; narrow the boon fast-path from `'): '` to
  `' gains the effect of '`; skip the timestamp loop unless the line starts with
  `[`.

**[RISK] Synchronous settings writes on the chat thread:**
- Problem: `persist()` (`inctrack.lua:83-88`) JSON-encodes the run and calls
  `settings.save()` — a file write — from inside the `text_in` handler.
- Files: `inctrack/inctrack.lua:190-197`. Eleven event types in `MUST_SAVE`
  (`inctrack.lua:56-68`) write immediately; everything else still writes every
  five seconds (`:194`), and `phase` — which arrives on every kill — rides that
  throttle for the entire run.
- Cause: durability was chosen over latency deliberately and for a good reason
  (the server never re-announces objectives), but the cost lands on a hot game
  thread rather than on a timer.
- Improvement path: mark dirty and flush from `d3d_present` on an interval;
  compare the encoded blob against the last one written and skip no-op saves.

**[RISK] Unbounded memo cache:**
- Files: `inctrack/ui.lua:336` (`short_cache`), keyed by raw server stat strings
  and read every frame from `shorten` (`ui.lua:338-351`).
- Impact is small in practice — a run yields a handful of boons — but the key
  space is server-controlled and the cache is never cleared, not on run reset and
  not on character switch.

---

## Tech Debt

**[DEFECT] No CI, no linter, no static analysis:**
- Issue: `test/run_tests.py` must be run by hand, on Windows, by someone who holds
  the chatlogs. There is no `.github/` directory in the repository — confirmed
  absent.
- Files: repository root; `test/run_tests.py`.
- Impact: a regression in `parser.lua` or `state.lua` is caught only if the author
  remembers to run the suite before tagging. Nothing at all catches Lua-level
  mistakes — accidental globals, typos in rarely-taken branches, unbalanced ImGui
  push/pop.
- Fix approach: a GitHub Actions workflow running `luacheck` over `inctrack/` plus
  the log-independent suites (4-7) of `run_tests.py` on every push. Those suites
  need only Python and `lupa`, and are already written to skip cleanly without
  logs.

**[DEFECT] No versioned release artifact:**
- Issue: `addon.version = '1.1.0'` (`inctrack/inctrack.lua:22`) and `CHANGELOG.md`
  are the only version markers. Installation is "copy the folder from the default
  branch", so users cannot pin a version, and a broken commit is live for anyone
  who re-downloads.
- Fix approach: tag releases and attach a zip of `inctrack/` to a GitHub release;
  assert in CI that the tag matches `addon.version`.

**[RISK] `os.clock` as the monotonic source:**
- Issue: acknowledged in the code at `inctrack/inctrack.lua:70-76` — `os.clock` is
  CPU time by ISO C, and the addon relies on the MSVCRT behaviour of returning
  wall time since process start.
- Impact: correct on the target platform today, but every timer in the addon
  (`state.lua:456-503`, all `clock_str` output in `ui.lua:78-91`) skews silently if
  that assumption breaks. It is also process-lifetime-relative, which is why
  `restore` must fall back to `os.time()` (`state.lua:556`, `:597`) — two clocks
  with different epochs coexist in one file.
- Fix approach: keep the single `now()` accessor, and mark the mixed-epoch call
  sites explicitly so the next reader does not compare them.

**[RISK] `pending_time` outlives `reset()`:**
- Files: `inctrack/state.lua:82-85` — `State:reset` clears `run` and sets `dirty`
  but leaves `self.pending_time`, which is consumed at `state.lua:125-129`.
- Impact: a `/incursion reset` within 30 seconds of a
  `You have N minutes remaining` line seeds the *next* `begin` with the pre-reset
  timer. A narrow window, bounded only by that 30-second guard.

**[RISK] Duplicated wording knowledge in the test harness:**
- Files: `test/run_tests.py:70-92` — `MUST_PARSE`, `BEGIN`, `COMPLETE`, `POINTS`
  and `PHASE` re-encode the server's message shapes as Python regexes, in parallel
  with `inctrack/parser.lua`.
- Impact: a server wording change requires edits in two files in two languages,
  and a matching mistake made in both directions yields a green suite over a
  broken parser.

---

## Test Coverage Gaps

**[DEFECT] `ui.lua` (433 lines) has zero automated coverage:**
- What's not tested: every function in the render tree — `clock_str`
  (`ui.lua:78-91`), `right_text` (`:94-102`), `wrapped` (`:104-110`), `bar`
  (`:112-120`), `urgency` (`:122-135`), `replace_plain` (`:320-333`), `shorten`
  (`:338-351`), the `STAT_SHORT` table (`:294-316`), and `ui.render`'s ImGui stack
  balance (`:387-431`).
- Files: `inctrack/ui.lua` (entire file).
- Risk: this is the only file that can crash the game (see *`ui.render` runs
  unprotected inside `d3d_present`*), and it is the least verified.
- Priority: **High**. The pure helpers — `clock_str`, `replace_plain`, `shorten`,
  `urgency` — have no ImGui dependency and are testable in the existing `lupa`
  harness today with no new infrastructure. The longest-phrase-first ordering
  contract of `STAT_SHORT` (documented at `ui.lua:286-292`) is entirely unasserted,
  and it is exactly the kind of table a future edit re-sorts alphabetically.

**[DEFECT] `inctrack.lua` (301 lines) has zero automated coverage:**
- What's not tested: the `MUST_SAVE` throttle policy (`inctrack.lua:56-68`,
  `:190-197`), `visible()`'s override/auto interaction (`:97-106`), the command
  surface (`:228-273`), the load-time resume path (`:113-146`), and the
  character-switch handler (`:275-301`).
- Files: `inctrack/inctrack.lua`.
- Risk: the profile-switch handler is the piece most likely to leak one
  character's run — or one character's name filter — into another's window, and
  bugs here are user-visible on every login.
- Priority: **High** for `visible()` and the settings-profile handler, which are
  pure enough to exercise against an Ashita stub; **Medium** for the rest.

**[DEFECT] The deepest suites depend on the author's private chatlogs:**
- What's not tested without them: suites 1-3 — parser coverage, the generic-tier
  assertion, and full run reconstruction — that is, the entire real-data
  validation of the parser.
- Files: `test/run_tests.py:44-66` (`find_logs`, `find_ashita_libs`); the logs are
  excluded by `.gitignore` as personal data.
- Risk: a contributor or a CI job runs the suite, sees green, and has actually
  verified only the synthetic unit tests. The silent skip is the right default for
  a contributor and the wrong one for a release gate.
- Priority: **High**. Fix approach: commit a small anonymised fixture log — one
  run per instance type, character name scrubbed — so suites 1-3 have a public
  floor; keep the private-log path as the extended run; and add a `--strict` mode
  that exits non-zero when any suite skips.

**[RISK] Suite 8 (persistence round-trip) needs Ashita's `json.lua`:**
- Files: `test/run_tests.py:20-23`, resolved via `INCURSION_ASHITA_LIBS`.
- Risk: the serialise/restore contract — including both `state.lua` restore
  defects above — is verified only on a machine with Ashita installed.
- Priority: **Medium**. Vendor a copy of `json.lua` under `test/`, or fetch it as a
  pinned dependency in CI.

---

## Security Considerations

**Server-controlled strings reach a printf-style UI layer:**
- Risk: instance names, boon names, mob lists and unrecognised notes travel
  untouched from the chat stream into `imgui.TextColored` — `ui.lua:137`, `:238`,
  `:243`, `:263`, `:363`, and via `wrapped` at `:204`, `:206`, `:374`. If the
  Ashita ImGui binding treats the string as a format string, a `%` sequence in
  server text is a crash or memory-read hazard; if it does not, it is a display
  artefact. The binding's behaviour is assumed, not asserted anywhere.
- Current mitigation: none — no escaping and no length cap. Unbounded strings also
  defeat the fixed-width wrapping contract at `ui.lua:104-110`.
- Recommendations: route server text through an explicit `'%s'` format, or escape
  `%`; truncate to a sane maximum before display.

**Server-controlled strings are persisted to disk:**
- Risk: `serialise()` writes labels, mob names and boon text into the settings JSON
  (`state.lua:527-580`), and `run.extra` uses server text as *table keys*
  (`state.lua:576`). That blob is read back and re-adopted at `state.lua:646-652`
  with only a label fallback.
- Current mitigation: `pcall`-wrapped encode (`inctrack.lua:85`) and decode
  (`inctrack.lua:135`, `:288`); no shape validation after decode.
- Recommendations: validate types on restore (see *Restored state is trusted
  structurally*); cap key and value lengths before persisting.

**Points attribution accepts anyone when the player name is unknown:**
- Risk: `state.lua:360-363` filters points to `self.player`, but only when a name
  is set. Before the name resolves (`inctrack.lua:170-179` fills it lazily on the
  first parsed event), any `<Name> gains N incursion points.` is accepted — and
  because of the phase-counting defect above, it also increments
  `phases_cleared`. The same fallback applies to boons (`state.lua:382-384`).
- Current mitigation: the code comment argues the server only addresses these
  messages to us; that is an assumption about a private server, not an enforced
  invariant.
- Recommendation: buffer or drop attribution-sensitive events until a player name
  is known, rather than accepting them.

**Chat error spam has no rate limit:**
- Risk: `printf('parse error: %s', ...)` (`inctrack.lua:202`) fires once per
  offending chat line. A systematic parse failure floods the player's chat at
  chat-stream rate and drowns the game's own messages.
- Recommendation: report the first failure, then suppress until the message text
  changes or N seconds elapse.

**Not a concern, and worth stating explicitly:** the addon is read-only with
respect to the game. No packet injection, no memory writes; `text_in` never sets
`e.blocked` and never modifies `e.message` (`inctrack.lua:160-204`). The only
`e.blocked` is on the addon's own `/incursion` command (`inctrack.lua:236`).
`AshitaCore` reads are limited to `GetParty():GetMemberName(0)`
(`inctrack.lua:122`, `:174`).

---

## Scaling Limits

**Chat throughput:**
- Current capacity: untested and unmeasured. Cost scales linearly with party chat
  volume; see *Per-chat-line cost is paid before the cheap rejection*.
- Limit: unknown — there is no profiling hook and no frame-budget assertion.
- Scaling path: move the rejection ahead of the allocations (`inctrack.lua:167`,
  `parser.lua:270-294`).

**Generic counters per run:**
- Current capacity: `run.extra` (`state.lua:64`) grows one entry per distinct
  unrecognised counter label, cleared only on `complete` (`state.lua:414`) or
  `reset`.
- Limit: every entry is rendered each frame through `extra_sorted()`
  (`state.lua:491-511`), which allocates a list and sorts it *per frame* whenever
  any extras exist. The `NO_EXTRAS` fast path (`state.lua:487`) only covers the
  empty case.
- Scaling path: cache the sorted list and invalidate on write, rather than
  rebuilding it at 60fps.

**Restore window:**
- `STALE_SECONDS = 3 * 60 * 60` (`state.lua:27`) is one constant governing three
  distinct decisions: restore acceptance (`state.lua:597`), `recover` run reuse
  (`state.lua:142`), and — implicitly — how far wrong the un-aged timers can be
  (see the restore defect). Three hours is generous for all three, and they
  probably want different values.

---

## Dependencies at Risk

**Ashita v4 addon API** (`common`, `chat`, `settings`, `json`, `imgui`):
- Risk: an unversioned, private-target platform. `settings.register`
  (`inctrack.lua:275`), `string:strip_colors` (`inctrack.lua:167`) and the exact
  ImGui binding signatures are all assumed and none are probed.
- Impact: an Ashita update changing any of them breaks the addon at load or — in
  the ImGui case — at render time, inside an unprotected per-frame callback.
- Migration plan: none exists; there is no alternative host. Mitigate by probing
  for the required functions at load and refusing to register handlers with a
  clear chat message, rather than erroring on every frame.

**`lupa` (test-only):**
- Risk: the suite embeds a Lua runtime via `test/run_tests.py:35`. Unpinned, with
  no `requirements.txt` in the repository.
- Impact: a `lupa` release that changes table-conversion semantics breaks
  `new_state`/`lua.table_from` (`test/run_tests.py:99-102`) and the suite fails for
  reasons unrelated to the addon.

---

## Missing Critical Features

**No self-diagnostic for pattern drift:**
- Problem: nothing tells the player, or the author, that a specific pattern has
  stopped matching and the generic tier is now carrying the run.
- Blocks: the earliest possible detection of this project's largest risk. A
  `/incursion debug` reporting generic-tier hit counts for the current run would
  turn a silent degradation into a bug report.

**No window configuration:**
- Problem: position, scale, opacity and section visibility are compile-time
  constants — `CONTENT_W` (`ui.lua:63`), the bar heights (`ui.lua:56-57`), the
  `COLOR` table (`ui.lua:32-49`). Only `auto` and `locked` are persisted
  (`inctrack.lua:36-45`).
- Blocks: any user running a non-default UI scale or resolution, who cannot make
  the window fit without editing source.

---

*Concerns audit: 2026-08-28*

# inctrack

## What This Is

inctrack is a live HUD for **CatsEyeXI** Incursions — an Ashita v4 addon (Lua +
ImGui) that shows the current instance, phase and kill progress, the mobs that
count, the boss waiting at the end of the phase, the bonus objective and its
countdown, time left, phases cleared, and the boons picked. Everything it
displays is read from the server's own chat messages: no packet inspection, and
no memory reading for run data. The single memory read in the addon is
`GetParty():GetMemberName(0)` — the player's own character name, used only to
tell "you gained a boon" from another player's line.

It ships at **v1.2.0** and is in daily use by its author on CatsEyeXI. v1.2.0
added nothing to the window. It was a quality pass on shipped code: the two
files the suite had never reached are now covered, three defects visible in the
code are gone, six fragile paths were hardened, the cost paid on every chat line
was cut and measured, and the project's own documents were brought back into
agreement with what ships.

**What comes next is not chosen.** The candidates are in Active below and they
are all things this milestone deliberately set aside: the process tooling that
was deferred while there was too little coverage to be worth running, a short
list of residuals that were named rather than fixed, and four checks that only a
live Incursion can close. No feature milestone has been proposed.

## Core Value

**What the window shows is either true, or visibly marked as unconfirmed —
never quietly wrong.** A HUD that lies is worse than no HUD, because the player
stops reading chat and trusts it.

**Shipping v1.2.0 did not change this, and that is a decision, not an
oversight.** It is still the right priority, and this milestone is the strongest
evidence for it so far — because the value earned its keep against the
milestone's own work rather than against the server.

Of the five Critical findings raised across the four phase reviews, four were
regressions this milestone's own hardening introduced, and three of them were
exactly the class the core value exists to catch:

- **Phase 2 CR-01.** FIX-03's fix shipped `imgui.Begin(name, flags)`. Ashita's
  SDK declares one positional signature and slot 2 is `p_open`; a survey of 220
  `imgui.Begin(` call sites across the install found inctrack was the only addon
  passing flags there. The window could have silently lost `AlwaysAutoResize`,
  `NoTitleBar` and `NoMove` — a window that looks fine and is not.
- **Phase 3 CR-01.** HARD-05's new validator required non-empty strings, and the
  addon's own parser emits a blank `next_boss.name` from a line the server
  really sends. The validator was rejecting sessions the addon itself had
  written, turning one such line into total loss of the run's boons, points,
  phase and elapsed on the next reload.
- **Phase 4 CR-01.** PERF-01's cheap gate covered two of Ashita's three colour
  marker bytes. A marker landing inside one of the seven needles would have made
  the addon reject a real Incursion line before it was ever uncoloured — the
  window simply never appears, and a dropped line looks exactly like a quiet
  stretch of chat.

Each was found by asking the core value's question of a change made in its name.
None of the three was visible in a green suite until someone went looking.

The fourth, Phase 4 CR-02, is the same origin and a different class: PERF-02's
move of `persist()` onto the frame handler left it unprotected on the thread
every addon in the process shares. Phase 1's CR-01 was a harness defect, not
shipped behaviour.

## Requirements

### Validated

Shipped in 1.0.0–1.1.0 and confirmed working against 127 real chatlogs
spanning 130 days (2026-04-22 to 2026-08-29) — 2,951,129 chat lines and 111
completed runs across 8 instances.

- ✓ Live HUD driven entirely by the server chat stream — no packets, no memory reads for run data — existing
- ✓ Instance, difficulty, phase number and kill progress with the mobs that count — existing
- ✓ Boss preview for the current phase, flipping to a boss objective when kills complete — existing
- ✓ Bonus objective in all three observed forms (kill-count, named NM, chest) with expiry countdown — existing
- ✓ Instance time remaining, seeded from the server's whole-minute sync and ticked locally — existing
- ✓ Phases cleared and elapsed run time — existing
- ✓ Boons picked between phases, with stats in FFXI shorthand — existing
- ✓ Zero hardcoded content: no instance, boss, mob, objective or difficulty name appears in any code path — nothing read, matched on or drawn is a content name, so new server content works with no code change. Pattern-example comments and `ui.lua`'s layout sketch do name real content illustratively; nothing reads from them — existing
- ✓ Generic parser tier so unrecognised future messages still reach the window instead of being dropped — existing
- ✓ Run state persists across reload, zoning and crash; post-reconnect state treated as a lower bound and marked as such — existing
- ✓ `/incursion` (`/inc`) with `reset`, `lock`, `auto` subcommands; automatic show/hide around a run — existing
- ✓ Test harness replaying real chatlogs through the shipped Lua modules in an embedded interpreter — existing
- ✓ Purity boundary: `parser.lua` and `state.lua` have zero Ashita dependency, so they run outside the game — existing

Delivered by **v1.2.0 — correctness and cost**. All 19 v1 requirements, each
backed by a test that goes red when the change is reverted:

- ✓ The two files the suite had never reached are covered — `ui.lua` renders against a stubbed ImGui and `inctrack.lua` runs against a stubbed Ashita host, so draw calls, colours and text, event registration, the `text_in` handler and its `pcall` boundary, settings load and save, `/incursion` and its subcommands, and visibility are all assertable (COVR-01, COVR-02) — v1.2.0
- ✓ Every defect fixed this milestone has a regression test that was red before the fix and green after, with the assertion bytes proven unedited across the fix by an audit script that was negative-controlled first (COVR-03) — v1.2.0
- ✓ The suite runs to completion with no chatlogs directory and no Ashita install, reporting a non-zero count for every suite that does not need private data (COVR-04) — v1.2.0
- ✓ `phases_cleared` has a single author — the phase line and the completion. A bonus payout, a chest or a completion bonus no longer counts as a cleared phase (FIX-01) — v1.2.0
- ✓ Restore ages the run clock, the elapsed time and the bonus expiry by the wall-clock gap `saved_at` already recorded; a gap from a stamp in the future is clamped to zero, and a run whose instance time has already lapsed is not resumed at all (FIX-02) — v1.2.0
- ✓ No unreachable close affordance remains: `ARG_OPEN` is gone from `ui.lua` and the `shown == false` branch from `inctrack.lua`. `/incursion` is the dismiss (FIX-03) — v1.2.0
- ✓ An error raised while drawing is caught in the frame handler, the ImGui window and style-var stacks are repaired, the failure is reported once, and the window disables itself for the session with `/incursion` as the way back — it cannot recur once per frame inside `d3d_present`. Proven against the stub; the real binding is in-game check 3 (HARD-01) — v1.2.0
- ✓ A server name survives the parser whole — a boss name containing " at " is split on the last one before the parenthesised location, and a mob name containing a comma stays one mob (HARD-02, HARD-03) — v1.2.0
- ✓ The boon matcher matches only the `(<glyph>): <stats>` tail, so an ordinary buff line cannot be claimed as a boon. The glyph group is `%([^)]*%)` and may be **empty**, deliberately: there is no fallback tier below it, so a stricter rule would have dropped a blank-glyph boon silently and permanently (HARD-04) — v1.2.0
- ✓ A saved session of the wrong shape is discarded whole before any field is read for its value, and lists are checked for contiguity from 1 as well as key by key, so a hole cannot half-apply a boon list (HARD-05) — v1.2.0
- ✓ `reset()` clears `pending_time`, so a held timer sync cannot seed an unrelated later run (HARD-06) — v1.2.0
- ✓ A chat line the addon does not care about is turned away before anything is built for it — no copy of the line, no colour strip, no pattern run — and the saving is a printed number rather than a claim: 3.54× on the reject path, stated together with the corpus colour mix it is a property of (PERF-01, PERF-04) — v1.2.0
- ✓ A settings write never blocks the chat thread: `text_in` marks the run as owed a write, `d3d_present` flushes it above both early returns inside a `pcall` that re-arms the flag on failure and reports once, and the unload handler still writes unconditionally (PERF-02) — v1.2.0
- ✓ The boon shorthand memo cache is bounded at 64, dropped whole when it fills, and emptied on reset and on a character switch (PERF-03) — v1.2.0
- ✓ `docs/design.md` describes the addon that ships, `CHANGELOG.md` and `addon.version` both read 1.2.0, and the two are pinned to each other in both directions by the harness reading each out of its real source (DOC-01, DOC-02) — v1.2.0

One further outcome, raised by the milestone audit rather than by a requirement:

- ✓ A number in a saved run that is not really a number — NaN or ±infinity, which a hand-edited or corrupted settings file can hold and which Ashita's own `json.lua` decodes from well-formed JSON — is read exactly as a missing key would be. That one field is unknown; the instance, boss, mobs, boons and every other number come back whole. 117 checks, negative-controlled four ways on both dialects (audit G-1) — v1.2.0

### Active

Candidates for the next milestone. Everything here is something v1.2.0
deliberately set aside and recorded; nothing here has been scoped or scheduled.

**Process — deferred in v1.2.0, and the reason has now expired**

The four were deferred with the words "revisit once the coverage exists to be
worth running." That coverage now exists: 13 result lines from 11 suite
functions, 13,461 checks, green on both backends with zero known defects. The
reason no longer holds, so they belong here rather than in Out of Scope.

- [ ] **PROC-01** — GitHub Actions runs the suite on push and on pull request
- [ ] **PROC-02** — a linter (luacheck) with a checked-in config
- [ ] **PROC-03** — tagging a version produces a downloadable release artifact
- [ ] **PROC-04** — a small public chatlog fixture so a contributor can run the deep suites without the author's private logs

**Residuals v1.2.0 named and did not take**

- [ ] The phase bar's `0` denominator. When the kill cap is absent and the objective carries no count either, the label reads `Phase #N  cur/0` with an empty bar — a denominator the server never sent. It is the one place an unknown number is drawn as a number rather than left off. Pre-existing `ui.lua` behaviour; stated in `docs/design.md` and left unfixed because the change that surfaced it was scoped to the validator
- [ ] `settings.save()` is unprotected in `reset()`, in the `/incursion lock` and `auto` command paths and in the profile-switch callback. Same class as Phase 4's CR-02, which was fixed on the frame path only; these are pre-existing and on the command path
- [ ] `points_partial` and `awards_seen` are a dead chain end to end — written, serialised, validated, restored, and read by nothing. Retire them or give them a consumer
- [ ] `ui.render`'s return value is dead: it returns `opts.visible` on both paths and its only caller discards it (`02-REVIEW.md` IN-06, re-raised as `04-REVIEW.md` IN-04 and deferred there)
- [ ] Integer versus float on the version-1 migration's phase arithmetic is not separately pinned (`03-REVIEW.md` IN-07). The `luajit21` run exercises the same dialect question for `array_key` and is green; the migration path is not covered by that
- [ ] Persisted key and value lengths are unbounded. Server text is used as a table key in the extras map; the validator checks the key is a string and the value shape-correct but bounds neither. Dispositioned **accept** in Phase 3's threat register (`T-03-19`) and recorded in `docs/design.md` as a decision rather than an omission

**Verification carried forward**

- [ ] The four in-game checks listed under Context. All four run in a single Incursion; the colour fall-through is the one to do first, because it has zero corpus backing by construction

**Recorded, not scheduled.** The over-reach guard re-derives in Python what
`parser.lua` knows about the server's wording. The duplication is deliberate and
load-bearing — a reference derived from the parser would drift with it and agree
with it while both were wrong — so it is a maintenance cost to watch, not a
defect to fix. Likewise the 29 review findings left open across the four phases
(28 Info-severity, plus the deliberately declined parser half of Phase 3's
CR-01): they are a list to triage, not a backlog to adopt. Every Critical and
Warning across all four phases is fixed.

### Out of Scope

- **New HUD features** — the v1.2.0 exclusion was milestone-scoped and expired with the milestone. Nothing is excluded here on principle and nothing is planned; a feature milestone would have to be chosen deliberately rather than drifted into.
- **Loot and material tracking** — decided against in 1.0.0 and still declined: it needs a phrase table plus treasure-pool bookkeeping for information the player already has by opening their bags.
- **Phase totals ("3 of 4")** — the count varies by instance and the chat stream never states it. 2,951,129 recorded lines have not produced one. Showing it would mean inventing it.
- **Packet inspection, and memory reading for run data** — the chat-only constraint is the project's defining choice, not a limitation to route around. The one memory read in the addon is the player's own character name through Ashita's party API, inherited from 1.0.0 and used only to tell whose line a boon is.
- **Rewriting the parser as a grammar** — the two-tier pattern design is proven against 111 completed runs and 2,951,129 lines; replacing it would discard that evidence for no gain that has been named.

## Context

**Where the code stands.** v1.2.0 ships four Lua files — `inctrack.lua` (661),
`parser.lua` (512), `state.lua` (1,048), `ui.lua` (535) — against a harness of
`test/run_tests.py` (6,255) and `test/stubs.py` (1,504). The live install at
`...\Ashita\addons\inctrack\` is byte-identical to the repository.

**The suite, run 2026-08-29 at milestone close.** Eleven suite functions
reported as thirteen result lines, **13,461 checks**, PASS with zero known
defects. Per-suite, identical on both backends: `parser 11819` (exact pin) ·
`generic 1` (exact pin) · `tightened 1` · `replay 888` · `state 204` ·
`adaptability 119` · `disconnect 23` · `timers 31` · `persistence 46` ·
`ui 86` · `addon 220` · `record 17` · `cost 6`. The generic tier still matches
nothing that exists today, which is the check that says no specific pattern
regressed.

**Backends.** The harness runs on any of the seven Lua implementations
`lupa` 2.8 ships — `lua51`…`lua55`, `luajit20`, `luajit21` — selected by
`INCTRACK_LUA` and printed in the run header. Phase 1 verified identical check
counts and PASS on all seven; the closing runs are made on Lua 5.5 (lupa's
default here) and on **LuaJIT 2.1, which is what Ashita actually embeds**. The
two dialects genuinely differ where it matters — `string.format('%d', nan)`
prints `-9223372036854775808` under LuaJIT and raises under Lua 5.3+ — so
running both is not ceremony.

**The corpus.** 127 chatlogs spanning 130 days (2026-04-22 to 2026-08-29),
2,951,129 chat lines, 111 completed runs across 8 instances. Nine distinct
instances appear in the logs; eight of them have a run that reached a
completion line. The corpus is the author's own and is not in the repository, so
anyone else's run of the suite covers less — the `parser`, `replay` and
`tightened` suites are the ones that need it.

**Verification environment on this machine:**

- Chatlogs: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs`
- Ashita's own `json.lua`: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\json.lua` (the persistence suite skips with a printed reason if it is absent)
- `lupa` 2.8 on Python 3.14.5
- The addon is deployed live at `...\Ashita\addons\inctrack\`, so changes can be exercised in game

**Four in-game checks are open. They are the honest limit of what v1.2.0
proved.** No test suite can close any of them, and the milestone was closed with
them outstanding rather than by narrowing the claims:

1. **The colour-code fall-through.** The cheap gate answers yes unconditionally
   to any line carrying `\30`, `\31` or `\127`, so a colour code landing inside
   a needle cannot cause a silent drop. This rule has **zero corpus backing by
   construction**: Ashita's log writer strips all three markers on the way to
   disk, so none of the 2,951,129 recorded lines can ever exercise it. Its
   correctness rests entirely on the SDK source coupling and synthetic fixtures.
   A single live Incursion tracking normally in ordinary coloured chat closes it.
   This is the priority of the four.
2. **The reload clock.** Note the window's clock mid-run, `/addon reload
   inctrack`, stay unloaded ~2 minutes, reload, then wait for the server's next
   `You have N minutes remaining` line. PASS if they agree within a minute.
3. **The window frame.** No title bar and no close control; not resizable by
   dragging an edge; height still auto-fits; `/incursion lock` still prevents
   dragging; `/incursion` still toggles. This exists because the
   `Begin(name, nil, flags)` fix rests on Ashita's SDK header and a survey of
   220 call sites, not on an observed frame — the compiled binding's type
   handling cannot be inspected, so only a rendered window proves the flags land.
4. **The render-error repair.** Provoke a render error: the repair does
   `pcall(function () imgui.End(); end)`, which reaches Ashita's `GuiManager`
   through a metatable `__index`. The stub models that shape but cannot execute
   it. PASS if the window goes off, one line names `/incursion` as the way back,
   and no other addon's window loses its frame.

**Architecture, unchanged by this milestone.** A unidirectional pipeline — chat
line → event table → run record → pixels — with a functional-core /
imperative-shell split. `parser.lua` and `state.lua` are pure; only
`inctrack.lua` touches `AshitaCore`, `settings`, `json` and `os.clock`; only
`ui.lua` touches `imgui`. The purity boundary was re-checked at close: a grep
for `require`, `AshitaCore`, `ashita.`, `imgui`, `settings.` and `json.` in the
two pure files returns only comments. v1.2.0 added two containment boundaries
inside the shell — the frame handler's `pcall` around `ui.render` with its stack
repair and session latch, and the `pcall` around the deferred `persist()` with
its re-arm, 5-second retry throttle and report-once latch.

**Documents.** `docs/design.md` was rewritten from the source in Phase 4 and is
the project's ground-truth record of the server message stream; two of its
hardest claims are machine-pinned by the `record` suite, so it cannot drift
silently. `.planning/codebase/` still holds the seven analysis documents written
2026-08-28 (1,468 lines) — they describe the **pre-milestone** code and
CONCERNS.md's findings are all now closed, so they are a historical artifact
rather than a current map. `.claude/CLAUDE.md` was generated from the
pre-milestone PROJECT.md and carries stale figures.

## Constraints

- **Tech stack**: LuaJIT 2.1 as embedded by Ashita v4 — Lua 5.1 semantics plus LuaJIT extensions — with ImGui bindings. The host decides, not us; the harness is exercised across all seven Lua backends `lupa` ships precisely so nothing depends on which one a contributor happens to have
- **The ImGui binding is uninspectable**: `addons/libs/imgui.lua` defines no Lua-side functions at all — it is a constants table whose `__index` is `AshitaCore:GetGuiManager()`, so every call reaches a compiled binding that ships without source. Call shapes are settled by the SDK header and by what the other 220 call sites in the install do, and only a rendered frame proves them
- **Build**: none, and none wanted — edit the `.lua` files and copy the folder across; install is a folder copy
- **Purity boundary**: `parser.lua` and `state.lua` must stay free of any Ashita dependency — it is the only reason they can be tested outside the game, and breaking it silently removes the entire test suite's reach
- **Zero content knowledge**: no instance, boss, mob, objective or difficulty name may appear in any **code path** — nothing the addon reads, matches on or draws from is a content name, so the addon survives the server adding content without a code change. Comments and layout sketches may name real content illustratively; nothing reads from them
- **Runtime budget**: the `text_in` handler runs on **every** chat line the client receives; cost there is paid during combat, in crowded zones, forever
- **Rendering**: `ui.render` runs inside `d3d_present`, once per frame, on the thread every addon in the process shares — an unhandled error there is a frame-rate or stack problem, not a log line
- **Verification data is private**: the deepest suites replay the author's own chatlogs, which are not in the repo; anyone else's run of the suite covers less
- **Compatibility**: the server's chat wording is the API, and it can change without notice or versioning

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Quality milestone rather than new features | v1.1.0 works and is in daily use; an audit surfaced three confirmed defects and a set of fragile paths worth closing before building on top of them | ✓ Good — 19 of 19 requirements delivered, zero scope creep, zero new displayed information, and the audit independently reverted 14 changes and watched 13 of them go red |
| Scope set at code + test coverage; CI, linter and release artifact deferred | Keeps the milestone finishable; process tooling is worth more once the coverage it would run actually exists | ✓ Good — 4 phases, 11 plans, all finished. The condition it was deferred against is now met, so PROC-01…04 move to Active |
| Coverage before fixes, not after | All three confirmed defects survived a fully green suite. Without new tests there is no way to demonstrate a fix worked, only to assert it | ✓ Good — and it paid twice over: the same net caught the three Criticals the hardening itself introduced, which no green suite had reported either |
| Chat-parsing remains the only data source | It is the project's defining constraint and the reason it needs no packet or memory access; the fragility it brings is managed by the generic tier, not removed by abandoning it | ✓ Good — the generic tier still matches nothing across 2,951,129 lines, which is the check that says the specific patterns are still doing the work |
| Test against the author's real chatlogs rather than synthetic fixtures | Regression coverage against recorded real runs catches wording reality that invented fixtures would not | ✓ Good — 111 completed runs replayed end to end; the parser count is an exact pin at 11819, so a tightening that quietly dropped a line would fail rather than pass |
| The restore validator answers "what shape is this", never "is this informative" | Phase 3's CR-01: a non-empty-string rule rejected sessions the addon itself writes, and refusing a blob costs a live run's boons, points, phase and elapsed, none of which the server re-announces | ✓ Good — pinned by 11 checks that also assert the rest of the run came back intact, so accepting cannot become its own half-apply |
| A NaN or ±infinity reads as **absent** — reject the field, keep the run | The narrower judgement that there is no number there, not the judgement that a number is uninformative. A blank string and a NaN are the same case except in what they draw: a blank draws nothing, a NaN drew `~-9223372036854775808:...` where the clock belongs | ✓ Good — 117 checks across three suites, negative-controlled four ways on both dialects |
| `imgui.Begin(name, nil, flags)` — the idiom every other addon uses | Ashita's SDK declares one positional signature and slot 2 is `p_open`; inctrack was the only one of 220 call sites passing flags there. Losing `AlwaysAutoResize`/`NoTitleBar`/`NoMove` silently is worse than a visibly broken call | ⚠️ Revisit — correct against the header and the install's idiom, but the compiled binding cannot be inspected. In-game check 3 is the only thing that closes it |
| The cheap gate answers yes unconditionally to any line carrying a colour marker byte (`\30`, `\31`, `\127`) | A colour code can land inside the very needle the gate searches for, so the gate must be a superset of the host's own `strip_colors` rather than a survey result. False positives cost one wasted colour strip; a false negative is a silently invisible HUD | ⚠️ Revisit — structurally right and the marker set matches Ashita's `strip_colors` exactly, but it has **zero corpus backing by construction** and is unprovable from the logs. In-game check 1, and the priority of the four |
| Keep `NoTitleBar`; remove the dead close path rather than restore the title bar | The compact 1.1.0 layout is a shipped feature, and the alternative was adding a window frame nobody asked for in order to make a control reachable. `/incursion` already was the dismiss | ✓ Good — `ARG_OPEN` gone from `ui.lua`, `shown` gone from `inctrack.lua`; the frame itself is in-game check 3 |
| Additive versus strict in the three parser tightenings, decided per pattern | HARD-02's boss split keeps the 1.1.0 lazy form as a fallback at all three call sites, so a location the server stops parenthesising still parses. HARD-03 and HARD-04 keep none, resting instead on a survey of all 127 logs plus the exact-11819 and exact-1 pins | ✓ Good — with one residual named rather than hidden: a comma-only mob list from a future server would now be drawn as one name, not two (`03-REVIEW.md` IN-03) |
| Settings writes deferred to the next frame; the unload write stays unconditional | A synchronous serialise, JSON encode and disk write on the game thread on every chat line is the cost being removed; the unconditional unload write is what makes deferring every other write safe | ✓ Good — with a one-frame residual accepted and stated: a hard crash between the chat line and the flush loses that one event |
| The zero-content guarantee reworded to "no content name in any **code path**" | The unqualified form is literally false — `ui.lua`'s layout sketch and `parser.lua`'s pattern examples name real content, and `ui.lua`'s header contradicted its own next ten lines. The sketches are the clearest thing in the file; the claim was what was wrong | ✓ Good — the claim moved onto the thing that is true, in `ui.lua`, the ROADMAP and here. The behaviour being claimed never changed |
| A summary reversed by review carries a SUPERSEDED note at its top | A summary is the most-cited record of what shipped, and a reader who trusts a reversed one believes something the code does not do — `02-02-SUMMARY.md` recorded the exact `Begin` shape a Critical condemned | ✓ Good — all five reversals annotated, each naming the finding, what actually shipped, and where to read the reversal |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-29 after v1.2.0 milestone*

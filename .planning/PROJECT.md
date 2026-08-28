# inctrack

## What This Is

inctrack is a live HUD for **CatsEyeXI** Incursions — an Ashita v4 addon (Lua +
ImGui) that shows the current instance, phase and kill progress, the mobs that
count, the boss waiting at the end of the phase, the bonus objective and its
countdown, time left, phases cleared, and the boons picked — all read from the
server's own chat messages. No packet inspection, no memory reading.

It shipped at **v1.1.0** and is in daily use by its author on CatsEyeXI. This
milestone is not new features. It is a **quality pass on shipped code**: close
the automated-test gaps, fix the defects a codebase audit confirmed, harden the
fragile paths, and cut the cost paid on every chat line.

## Core Value

**What the window shows is either true, or visibly marked as unconfirmed —
never quietly wrong.** A HUD that lies is worse than no HUD, because the player
stops reading chat and trusts it.

## Requirements

### Validated

Shipped in 1.0.0–1.1.0 and confirmed working against 126 real chatlogs
(2.94M lines, 106 completed runs across 8 instances).

- ✓ Live HUD driven entirely by the server chat stream — no packets, no memory reads — existing
- ✓ Instance, difficulty, phase number and kill progress with the mobs that count — existing
- ✓ Boss preview for the current phase, flipping to a boss objective when kills complete — existing
- ✓ Bonus objective in all three observed forms (kill-count, named NM, chest) with expiry countdown — existing
- ✓ Instance time remaining, seeded from the server's whole-minute sync and ticked locally — existing
- ✓ Phases cleared and elapsed run time — existing
- ✓ Boons picked between phases, with stats in FFXI shorthand — existing
- ✓ Zero hardcoded content: no instance, boss, mob, objective or difficulty name anywhere in the Lua — existing
- ✓ Generic parser tier so unrecognised future messages still reach the window instead of being dropped — existing
- ✓ Run state persists across reload, zoning and crash; post-reconnect state treated as a lower bound and marked as such — existing
- ✓ `/incursion` (`/inc`) with `reset`, `lock`, `auto` subcommands; automatic show/hide around a run — existing
- ✓ Test harness replaying real chatlogs through the shipped Lua modules in an embedded interpreter — existing
- ✓ Purity boundary: `parser.lua` and `state.lua` have zero Ashita dependency, so they run outside the game — existing

### Active

Milestone **v1.2.0 — correctness and cost**. Ordered deliberately: coverage
first, because the three confirmed defects all survived a fully green test
suite, which means the suite cannot currently prove a fix works.

**Test coverage — build the net before working under it**

- [ ] `ui.lua` (433 lines) is exercised by automated tests against a stubbed ImGui, closing a total coverage gap
- [ ] `inctrack.lua` (301 lines) is exercised by automated tests against a stubbed Ashita host, closing a total coverage gap
- [ ] Each confirmed defect below has a test that fails before its fix and passes after

**Confirmed defects — visible in the code as written**

- [ ] `phases_cleared` is authored in two places (`state.lua:198-202` and `:358-365`) and can double-count
- [ ] Restore does not age timers by the time the addon was unloaded, though `saved_at` is already persisted (`state.lua:600-634`)
- [ ] The close-button path is unreachable under `NoTitleBar` (`ui.lua:399`, `inctrack.lua:219-222`)

**Hardening — fragile paths that have not bitten yet**

- [ ] `ui.render` cannot leave an unbalanced ImGui stack when it errors inside `d3d_present`
- [ ] `objective_boss` no longer mis-splits names containing " at "; mob lists no longer assume names are comma-free
- [ ] The boon matcher is tightened so it cannot claim ordinary buff lines
- [ ] Restored state is validated structurally before it is applied, not merely parsed
- [ ] `pending_time` does not outlive `reset()`

**Performance — this runs on every chat line the client receives**

- [ ] The cheap rejection happens before any per-line cost is paid, not after
- [ ] Settings are not written synchronously on the chat thread
- [ ] The memo cache is bounded

**Standing guarantee for the whole milestone**

- [ ] The full suite stays green against the author's 126 chatlogs, and the generic parser tier still matches nothing that exists today

### Out of Scope

- **CI / GitHub Actions** — deliberately deferred; scope for this milestone was set at code plus test coverage, not process debt. Revisit once the coverage exists to be worth running.
- **luacheck or any linter config** — same reason.
- **Versioned release artifact (zip on tag)** — same reason; install is still "copy the folder".
- **New HUD features** — this is a correctness milestone. Anything that adds displayed information belongs to a later one.
- **Loot and material tracking** — decided against in 1.0.0: it needs a phrase table plus treasure-pool bookkeeping for information the player already has by opening their bags.
- **Phase totals ("3 of 4")** — the count varies by instance and the chat stream never states it. Showing it would mean inventing it.
- **Packet inspection or memory reading** — the chat-only constraint is the project's defining choice, not a limitation to route around.

## Context

**Codebase map:** `.planning/codebase/` holds seven analysis documents written
2026-08-28 (STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING,
CONCERNS — 1,468 lines). CONCERNS.md is the source of the Active list above and
marks each finding `[DEFECT]` (visible in the code) or `[RISK]` (contingent on
server behaviour or Ashita binding details).

**Baseline, measured 2026-08-28 before any change:** the suite is fully green —
12,841 checks across eight suites, over 2,943,169 chat lines from 126 logs. The
three confirmed defects live in paths the suite does not reach. That is the
whole argument for the coverage-first ordering.

**Verification environment is available on this machine**, which is what makes
this milestone verifiable rather than theoretical:

- Chatlogs: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\chatlogs` — 126 logs through 2026-08-28
- Ashita's own `json.lua`: `C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\json.lua` (needed by the persistence round-trip suite)
- `lupa` 2.8 on Python 3.14.5
- The addon is deployed live at `...\Ashita\addons\inctrack\`, so changes can be exercised in game

**Documented-design drift:** `docs/design.md` no longer matches the shipped
code on window sizing (`AlwaysAutoResize` plus a fixed-width spacer, not fixed
width), the title bar (`NoTitleBar`), the stats layout (points tracked but
never displayed), the boons row, and several run-record fields
(`elapsed_final`, `desynced`, `recovered`, `points_partial`, `bonus.loc`). The
design doc is the project's ground-truth record of the server message stream,
so this drift is worth correcting as the code changes.

**Architecture that constrains the work:** a unidirectional pipeline — chat
line → event table → run record → pixels, with a functional-core /
imperative-shell split. `parser.lua` and `state.lua` are pure; only
`inctrack.lua` touches `AshitaCore`, `settings`, `json` and `os.clock`; only
`ui.lua` touches `imgui`.

## Constraints

- **Tech stack**: Lua 5.1 as embedded by Ashita v4, plus ImGui bindings — the host decides, not us
- **Build**: none, and none wanted — edit the `.lua` files and copy the folder across; install is a folder copy
- **Purity boundary**: `parser.lua` and `state.lua` must stay free of any Ashita dependency — it is the only reason they can be tested outside the game, and breaking it silently removes the entire test suite's reach
- **Zero content knowledge**: no instance, boss, mob, objective or difficulty name may appear in any Lua file — the addon must survive the server adding content without a code change
- **Runtime budget**: the `text_in` handler runs on **every** chat line the client receives; cost there is paid during combat, in crowded zones, forever
- **Rendering**: `ui.render` runs inside `d3d_present`, once per frame — an unhandled error there is a frame-rate or stack problem, not a log line
- **Verification data is private**: the deepest suites replay the author's own chatlogs, which are not in the repo; anyone else's run of the suite covers less
- **Compatibility**: the server's chat wording is the API, and it can change without notice or versioning

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Quality milestone rather than new features | v1.1.0 works and is in daily use; an audit surfaced three confirmed defects and a set of fragile paths worth closing before building on top of them | — Pending |
| Scope set at code + test coverage; CI, linter and release artifact deferred | Keeps the milestone finishable; process tooling is worth more once the coverage it would run actually exists | — Pending |
| Coverage before fixes, not after | All three confirmed defects survived a fully green suite. Without new tests there is no way to demonstrate a fix worked, only to assert it | — Pending |
| Chat-parsing remains the only data source | It is the project's defining constraint and the reason it needs no packet or memory access; the fragility it brings is managed by the generic tier, not removed by abandoning it | ✓ Good |
| Test against the author's real chatlogs rather than synthetic fixtures | Regression coverage against 106 recorded real runs catches wording reality that invented fixtures would not | ✓ Good |

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
*Last updated: 2026-08-28 after initialization*

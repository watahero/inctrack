# Requirements: inctrack v1.2.0 — correctness and cost

**Defined:** 2026-08-29
**Core Value:** What the window shows is either true, or visibly marked as unconfirmed — never quietly wrong.

This is a quality milestone on shipped code (v1.1.0). Requirements are derived
from `.planning/codebase/CONCERNS.md`, which marks each finding `[DEFECT]`
(visible in the code as written) or `[RISK]` (contingent on server behaviour or
Ashita binding details).

**Baseline to beat:** the existing suite is green — 12,841 checks over 2,943,169
chat lines from 126 logs, measured 2026-08-28. Every requirement below must
leave it green.

## v1 Requirements

### Coverage

The net comes first. All three confirmed defects survived a fully green suite,
so without new tests a fix can only be asserted, never demonstrated.

- [x] **COVR-01**: `ui.lua` renders under a stubbed ImGui in the test harness, so a given run record can be asserted to produce the expected draw calls, colours and text
- [x] **COVR-02**: `inctrack.lua` runs under a stubbed Ashita host in the test harness, covering event registration, the `text_in` handler, settings load/save, the `/incursion` command and its subcommands, and visibility
- [x] **COVR-03**: every defect in the Defects category below has a regression test that fails against current code and passes after its fix
- [x] **COVR-04**: the new suites run to completion with no chatlogs directory present, so coverage of shipped behaviour is not gated on the author's private data

### Defects

Faults visible in the code as written, independent of what the server sends.

- [x] **FIX-01**: a boss kill increments `phases_cleared` exactly once — the count has a single author, not the two at `state.lua:198-202` and `state.lua:358-365`
- [x] **FIX-02**: after the addon is unloaded and reloaded, `time_left` and the bonus expiry reflect the time that passed while it was gone, using the already-persisted `saved_at` (`state.lua:600-634`)
- [x] **FIX-03**: no unreachable close path remains — the window's close affordance either works or is gone (`ui.lua:399`, `inctrack.lua:219-222`, dead under `NoTitleBar`)

### Hardening

Paths that are fragile but have not yet been observed to fail.

- [x] **HARD-01**: an error raised inside `ui.render` cannot leave the ImGui stack unbalanced, and cannot repeat once per frame unchecked — it runs inside `d3d_present`
- [x] **HARD-02**: a boss objective naming a mob whose own name contains " at " is parsed correctly rather than split at the first occurrence
- [x] **HARD-03**: a mob list containing a name with a comma in it is not split into two mobs
- [x] **HARD-04**: the boon matcher cannot claim an ordinary buff line — it matches only the `(<glyph>): <stats>` form
- [ ] **HARD-05**: a restored session is validated structurally before it is applied, and a malformed one is discarded rather than half-applied
- [ ] **HARD-06**: `reset()` clears `pending_time`, so a held timer sync cannot leak into an unrelated later run

### Performance

The `text_in` handler runs on every chat line the client receives, forever.

- [ ] **PERF-01**: a non-Incursion chat line is rejected before any allocation or pattern matching is paid for — the cheap rejection runs first, not after
- [ ] **PERF-02**: a settings write never blocks the chat thread synchronously
- [ ] **PERF-03**: the memo cache has a bound, so a long session cannot grow it without limit
- [ ] **PERF-04**: per-line cost is measured against a recorded pre-change baseline and demonstrably lower, not merely assumed lower

### Documentation

- [ ] **DOC-01**: `docs/design.md` matches shipped behaviour — window sizing, `NoTitleBar`, the stats layout, the boons row, and the run-record fields (`elapsed_final`, `desynced`, `recovered`, `points_partial`, `bonus.loc`)
- [ ] **DOC-02**: `CHANGELOG.md` and the addon's version string record 1.2.0 and what changed

## v2 Requirements

Deferred to a future milestone. Acknowledged, not in this roadmap.

### Process

- **PROC-01**: GitHub Actions runs the suite on push and on pull request
- **PROC-02**: a linter (luacheck) runs with a checked-in config
- **PROC-03**: tagging a version produces a downloadable release artifact
- **PROC-04**: a small public chatlog fixture ships in the repo so contributors can run the deep suites without the author's private logs

## Out of Scope

| Feature | Reason |
|---------|--------|
| New HUD features | This is a correctness milestone; anything that adds displayed information belongs to a later one |
| Loot and material tracking | Decided against in 1.0.0 — needs a phrase table plus treasure-pool bookkeeping for information the player already has by opening their bags |
| Phase totals ("3 of 4") | The count varies by instance and the chat stream never states it; showing it would mean inventing it |
| Packet inspection or memory reading | The chat-only constraint is the project's defining choice, not a limitation to route around |
| Rewriting the parser as a grammar | The two-tier pattern design is proven against 106 real runs; replacing it would discard that evidence for no gain in this milestone |

## Traceability

Populated during roadmap creation (2026-08-29). See `.planning/ROADMAP.md` for phase goals and success criteria.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COVR-01 | Phase 1 | Complete |
| COVR-02 | Phase 1 | Complete |
| COVR-03 | Phase 1 | Complete |
| COVR-04 | Phase 1 | Complete |
| FIX-01 | Phase 2 | Complete |
| FIX-02 | Phase 2 | Complete |
| FIX-03 | Phase 2 | Complete |
| HARD-01 | Phase 3 | Complete |
| HARD-02 | Phase 3 | Complete |
| HARD-03 | Phase 3 | Complete |
| HARD-04 | Phase 3 | Complete |
| HARD-05 | Phase 3 | Pending |
| HARD-06 | Phase 3 | Pending |
| PERF-01 | Phase 4 | Pending |
| PERF-02 | Phase 4 | Pending |
| PERF-03 | Phase 4 | Pending |
| PERF-04 | Phase 4 | Pending |
| DOC-01 | Phase 4 | Pending |
| DOC-02 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 19 total
- Mapped to phases: 19 ✓
- Unmapped: 0 ✓
- Orphans: none. Duplicates: none.

---
*Requirements defined: 2026-08-29*
*Last updated: 2026-08-29 after roadmap creation — traceability populated*

# Phase 1: The Net - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds test coverage and nothing else. It brings `inctrack/ui.lua` and
`inctrack/inctrack.lua` — currently at zero automated coverage — under the
existing Python harness by stubbing their hosts (ImGui, Ashita, `json`), and it
turns each of the three confirmed defects into a named test that asserts the
correct behaviour and therefore fails today.

**The addon source is not modified by this phase.** `git diff` over `inctrack/`
must be empty at the end of it. Fixing anything here would destroy the point of
the coverage-first ordering: the defects survived a fully green suite, so the
suite must be shown to catch them *before* anything is changed.

Requirements: COVR-01, COVR-02, COVR-03, COVR-04.

</domain>

<decisions>
## Implementation Decisions

### Stub design

- Stubs live in a new `test/stubs.py`, imported by `test/run_tests.py`. The runner is already 956 lines; the stubs add roughly 400 more, and a second module in `test/` is the smaller cost. There is still exactly one entry point (`python test/run_tests.py`), so the project's no-runner, no-config convention is intact.
- The ImGui stub is a **recording** stub: every call appends `(name, args)` to a call log. `CalcTextSize` returns a deterministic width derived from `#text` rather than real font metrics. Tests assert against the recorded log. No layout or wrapping simulation — simulating it would test the stub instead of the addon.
- The Ashita stub is a set of **in-memory fakes**, not strict mocks: an event registry table, a settings dict, a captured chat list, and an `AshitaCore` returning a fixed party member name. Tests assert on resulting behaviour, not on exact call sequences, so refactors inside the addon do not produce false failures.
- `inctrack.lua` requires `json`. The harness supplies a **stubbed pure-Lua `json`**, so the new suites run with no Ashita install present. Suite 8 (persistence round-trip) keeps using Ashita's real `json.lua` when it is available — that suite's whole purpose is round-tripping through the real thing.

### The three red tests

- The three defect tests use an **expected-failure mechanism** — `Result.xfail(cond, msg)` alongside the existing `Result.check`. The report prints them as `3 known defects (expected until Phase 2)` and the process still exits **0**. This keeps the milestone-wide standing guarantee ("the full suite is green") true and answerable at every point in the milestone.
- A **guard asserts the xfail count is exactly 3**. That is success criterion 4: not "some things fail" but "these three, and nothing else, fail." If a fourth appears, something regressed; if one disappears, a fix leaked into this phase.
- The tests assert **intended** behaviour, never current behaviour. That is why they are red now, and it is what makes the Phase 2 rule — flip them green without editing their assertions — meaningful.
- They are **named in user terms**, e.g. "counted a bonus payout as a cleared phase", "clock was optimistic by the reload gap after a reconnect", not in code terms.
- They live in **the suite they belong to** — FIX-01 and FIX-02 in the state suite, FIX-03 in the new UI suite — flagged as xfail rather than quarantined into a separate defects suite. A defect is a property of the thing it afflicts.

### Coverage reach and depth

- **`ui.lua`**: the pure helpers (`clock_str`, `right_text`, `wrapped`, `bar`, `urgency`, `replace_plain`, `shorten`, and the longest-phrase-first ordering contract of `STAT_SHORT`) get direct unit tests. `render` gets a handful of whole-window snapshots against representative run records — not an exhaustive matrix.
- **`inctrack.lua`**: everything reachable through the stub — event registration, the `text_in` handler and its `pcall` boundary, settings load/save and the `MUST_SAVE` throttle, every `/incursion` subcommand (`reset`, `lock`, `auto`, bare toggle, usage), `visible()`'s override-vs-auto logic, and the profile-switch handler.
- **The new suites never read chatlogs.** They use hand-written fixtures only, so they run to completion on a machine with no chatlogs directory and no Ashita install, reporting a non-zero check count for each. Chatlog replay stays the job of the existing suites. This is COVR-04.
- **Snapshot format** is the recorded call log normalised into a readable text form and compared against an **inline expected string** in the test — diffable and reviewable in a diff, rather than golden files on disk that reviewers skip.

### Claude's Discretion

- The exact shape of the normalised snapshot text, the naming of stub classes and helper functions, and how the xfail count guard is wired into `main()`.
- Which representative run records the `render` snapshots use, provided they cover at least: a mid-phase run with mobs, a boss-up run, a run with an active bonus, a desynced/reconnected run, and a finished run.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `test/run_tests.py:make_lua()` already bootstraps a `lupa` runtime, sets `package.path` to the addon directory, and injects `__clock` / `__clockfn` for deterministic timers. The new suites extend this rather than building a second bootstrap.
- `feed(state, parser, lines)` is the established fixture verb — raw chat strings in, parser and state driven as in game.
- `class Result` (`check` / `note` / `report`) is the assertion collector; failures accumulate rather than abort. `xfail` is a natural third method on it.
- `new_state()` builds the Lua options table via `lua.table_from`, passing the injected clock.

### Established Patterns

- The suite loads the **shipped** Lua modules, never a reimplementation — "a pass here means the shipped code behaves." The new stubs must preserve that: stub the *host*, never the addon.
- lupa does not bind `self`. Every colon-method takes its receiver explicitly: `s.snapshot(s)`, `s2.restore(s2, s.serialise(s))`. This is the single easiest thing to get wrong when adding tests.
- Lua values come back as proxies: `list(t.values())` for arrays, `int(...)` / `bool(...)` before comparing scalars.
- Suites are plain `test_<area>(...)` functions called explicitly from `main()` — no discovery.

### Integration Points

- `inctrack/ui.lua:28` — `local imgui = require('imgui')`. The ImGui stub is injected by pre-populating `package.loaded['imgui']` in the Lua runtime before `require('ui')`.
- `inctrack/inctrack.lua:26-33` — requires `common`, `chat`, `settings`, `json`, plus the three local modules. Same injection approach for the first four.
- `inctrack/inctrack.lua:122,149,159,209,228` — `ashita.events.register` for `load`, `unload`, `text_in`, `d3d_present`, `command`. The stub's registry captures these handlers so tests can invoke them directly.
- `inctrack/inctrack.lua:127,177` — `AshitaCore:GetMemoryManager():GetParty():GetMemberName(0)` for player-name discovery; the stub returns a fixed name.

### Constraints carried in from the project

- The purity boundary is absolute: stubs live in the harness, never in the addon. `parser.lua` and `state.lua` gain no Ashita dependency.
- Baseline to preserve: 12,841 checks, 8 suites, 2,943,169 chat lines from 126 logs, all green as of 2026-08-28. Check counts may only go up.
- Suite 2 must continue to hold — no generic-tier pattern matches anything in today's logs.

</code_context>

<specifics>
## Specific Ideas

- Criterion 4's wording matters and should be honoured literally: the failure list is *exactly three entries*, one per defect, each named so a reader who has never seen `state.lua` understands what went wrong.
- The `git diff` emptiness check over `inctrack/` should be part of the phase's own verification, not a manual step — it is the mechanism that stops a fix from sneaking in early and hiding the red.

</specifics>

<deferred>
## Deferred Ideas

- Running the suite in CI, adding a linter, and shipping a public chatlog fixture so contributors can run the deep suites — all recorded as v2 requirements PROC-01…04, deliberately out of this milestone.

</deferred>

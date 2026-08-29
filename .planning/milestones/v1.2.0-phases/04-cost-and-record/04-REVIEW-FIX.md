---
phase: 04-cost-and-record
fixed_at: 2026-08-29
review_path: .planning/phases/04-cost-and-record/04-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
deferred: 4
status: all_fixed
verification_env: main checkout (workflow.use_worktrees = false)
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-08-29
**Source review:** `.planning/phases/04-cost-and-record/04-REVIEW.md`
**Iteration:** 1

**Summary:**

- Findings in scope (Critical + Warning): 8
- Fixed: 8
- Skipped: 0
- Deferred (Info, out of scope): 4

Every fix was negative-controlled: the change was reverted, the suite run, and
the specific new check watched to go red before the change was restored. The
control output is recorded per finding below.

## The host's real marker set

Read from the shipped host on this machine,
`C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\libs\sugar\string.lua`:

```lua
string_mt.strip_colors = function (self)
    return (self:gsub('[' .. string.char(0x1E, 0x1F, 0x7F) .. '].', ''));
end
```

**Three** marker bytes — `0x1E`, `0x1F`, `0x7F` — stripped in **one** `gsub`
with a character class. Both facts were wrong in the code and in the harness,
and each was wrong in a way the other concealed.

One correction to the review itself: it cites this as
`sugar/string.lua:1044-1046`. On the copy installed here it is **`:1045-1047`**
— the review's line numbers are off by one, which is a small instance of
exactly the defect WR-06 is about. The function name is the durable anchor and
is what every new citation uses.

## Fixed Issues

### CR-01: The colour-marker fall-through misses Ashita's third marker byte

**Files modified:** `inctrack/parser.lua`, `docs/design.md`
**Commit:** `459d17b` (with `00cc3e5`)

`parser.relevant`'s fall-through now searches `\30`, `\31` **and** `\127`. The
comment names `strip_colors` as the function this set must stay a superset of,
and says why the coupling is checked against the host's source rather than
against the corpus: Ashita's log writer strips codes on the way to disk, so all
2,951,129 recorded lines carry none of the three and no survey could ever have
found this. The same wrong premise in `docs/design.md` is corrected.

**Negative control:** removing the `\127` search failed exactly one check —
`a 0x7F colour code landing inside one of the gate's needles lost the line that
starts a run` — while the 0x1E and 0x1F pins stayed green, which is the
discrimination the old single-marker pin could not make.

### CR-02: `persist()` runs unprotected inside `d3d_present`

**Files modified:** `inctrack/inctrack.lua`, `test/stubs.py`, `test/run_tests.py`,
`docs/design.md`, `CHANGELOG.md`
**Commits:** `9d85dc5` (containment), `0e9786b` (design.md), `c0a3b8f` (changelog)

Contained in the idiom Phase 3 established:

- `pcall(persist)`, so a refused disk write cannot reach the game thread or
  cost the frame its render.
- A `save_told` report-once latch beside `parse_told` and `render_off`, cleared
  by `/incursion reset` and by the profile switch, with `/incursion reset` named
  in the message as the way back. The host's error text is an argument, never
  part of the format string.
- **The flag is re-armed on failure rather than consumed**, which is where this
  departs from the review's suggested fix. A run that is owed a write and never
  given one comes back blank on the next reload, so the write is kept. It is
  re-armed behind `SAVE_RETRY_SECONDS` (5.0 — the number the chat thread
  already throttles with), so a persistent fault costs one attempt per window
  instead of a serialise, an encode and a failed write sixty times a second on
  the game thread. Consumed *before* the attempt and restored only on failure,
  so there is no window in which an unbounded retry is possible.
- `save_retry_at` is cleared wherever `save_due` is cleared, so a stale retry
  window cannot hold the next run's first write back.

The harness could not provoke this at all before — the stub's `save()` could not
fail. It now can: `fail_saves(message, times)` / `heal_saves()` /
`save_attempts`, persistent by default, with a default message carrying a
percent sign so the format-string discipline is actually tested.

**Negative control:** reverting the containment failed **12** checks, one per
consequence the review listed — the raise escaping `d3d_present`, the window
blanking for the frame, nothing said, the write dropped with nothing retrying
it, and nothing on disk when the fault cleared.

### WR-01: The stub's `strip_colors` diverges from Ashita's

**Files modified:** `test/stubs.py`, `test/run_tests.py`
**Commit:** `00cc3e5`

Both divergences corrected: one `gsub` with the character class `[\30\31\127]`.
`CC_C` (`\x7f\x31`) added; `REJECT_COLOURED` rotates through all three markers
so each appears both at the head of a line and inside one, keeping six lines
with two codes apiece so the asserted per-line counts still mean what they did.
The needle-hiding pin runs once per marker byte.

**PERF-04 figures moved, and downward**, as expected once the harness stopped
modelling a host that costs more than the real one:

| | before | after |
|---|---|---|
| colour-free rejected line, old shape | 1.00 strip, **5.33** gsub | 1.00 strip, **4.33** gsub |
| coloured rejected line, old shape | 1.00 strip, **5.00** gsub | 1.00 strip, **4.00** gsub |
| coloured rejected line, new shape | 1.00 strip, **2.00** gsub | 1.00 strip, **1.00** gsub |
| new/old ratio (Lua 5.5) | **3.71x** | **3.50–3.57x** |
| `REJECT_BASELINE` | 285,562 lines/s, 3.502 us/line | **288,437 lines/s, 3.467 us/line** |

The counts are deterministic and identical on both backends. The baseline was
re-taken as the median of three consecutive runs; its comment records the old
figure, why it was too slow, and that `commit: a6a3577` still names where the
old shape was transcribed from rather than when the figure was measured. The
`res.check` message claiming "two gsubs and two allocations" per strip now says
one of each.

**Negative control:** restoring the two-gsub, two-marker stub failed the 0x7F
pin *and* put the inflated 5.33 / 5.00 figures back — one revert, both defects
visible.

### WR-02: `parser.lua`'s header says the module has one function

**Files modified:** `inctrack/parser.lua`, `test/run_tests.py`
**Commit:** `ab79894`

Header names both functions, describes `relevant` as the deliberate superset it
is, and says plainly that the shell calls it directly rather than only through
`parse`.

**Negative control:** restoring "One function" failed with
`says it has 'One' functions and it exports 2 (parse, relevant)`.

### WR-03: "seven `string.find` searches" undercounts the reject path

**Files modified:** `inctrack/parser.lua`, `docs/design.md`, `test/run_tests.py`
**Commit:** `5848d25`

The answer is **ten**, not the nine the review computed: CR-01 adds a third
marker search in front of the seven needles. Both files state the total and its
split, and the `record` suite counts the searches out of `parser.relevant`'s own
body — total, markers and needles separately — and compares.

**Negative control:** putting "seven" back in either file failed that file's
check with the true split printed.

### WR-04: The "roughly one frame" residual

**Files modified:** `inctrack/inctrack.lua`, `docs/design.md`, `README.md`,
`test/run_tests.py`
**Commits:** `9d85dc5` (`inctrack.lua`), `c9bc2be` (docs)

All three now say the bound is the next frame that actually runs — not a length
of time — because the addon does not drive Present, and that a client killed in
that gap loses everything since the last frame that ran rather than one event.
All three also name the loss path that needs no crash: a raise inside
`persist()`.

`inctrack.lua`'s copy was rewritten as part of CR-02, which had to replace the
same comment block; that is why it is attributed to `9d85dc5`.

**Negative control:** restoring `README.md`'s old sentence failed both of its
checks.

### WR-05: `docs/design.md`'s suite count

**Files modified:** `docs/design.md`, `test/run_tests.py`, `.planning/WINDOWS.md`
**Commit:** `371c520`

The true figures, counting the `record` suite this pass adds: **eleven suite
functions, thirteen result lines**, because `test_parser` returns three Results
and every other suite returns one. Stated in `docs/design.md` with a thirteenth
table row; in `run_tests.py`'s module docstring, which had the same confusion
(eleven numbered entries, the tightened-patterns line missing); and in
`run_suite`'s docstring, which said the parser suites "come in pairs" and they
come in threes.

`.planning/WINDOWS.md` entry 2 logged exactly this arithmetic confusion and is
**closed** (`gsd-tools windows fixed 2`). Entry 1 is a different matter — a plan
acceptance criterion about a `grep -c` count — and is left open.

All three numbers are now derived rather than asserted: `run_suite` call sites,
the length of `test_parser`'s return, and the rows of the table under the
sentence. This is the check the previous correction needed; it was verified by
`grep -cF "Seven suites"` returning 0, which cannot tell a right answer from a
differently wrong one.

**Negative control:** restoring the old sentence failed both the count check and
the table-row check.

### WR-06: Stale line citations into the shipped Lua

**Files modified:** `test/stubs.py`, `test/run_tests.py`
**Commit:** `e6eddf4`

All **27** citations re-anchored to searchable tokens in one form —
``file (`token`)`` — and walked by the `record` suite, which resolves each
against the file it names and holds a floor on how many it finds so they cannot
be quietly converted back to line numbers. Zero numeric citations remain.

Beyond the review's 13, five more were checked and re-anchored: `inctrack.lua`'s
`addon.*` assignments and `require('common')`, `ui.lua`'s `STAT_SHORT` ordering,
`state.lua`'s reconnect branch, and a harness-to-harness citation of "suite 8"
by number. The one citation the review found correct (`ui.lua`'s layout mockup)
keeps its target and gains a token.

One comment was stale in a second way the review did not flag: it claimed "the
ui suite's one expected failure" and "the exactly-three guard" while all three
expected failures were fixed earlier in this milestone and the guard is at zero.
Rewritten to what is true.

**Negative control:** pointing one citation at `local function clock_now` failed
with the file it names and the text it could not find.

## Deferred Issues

The four Info findings were out of this pass's scope and are unchanged. One is
worth a note:

- **IN-01** — `coloured()` in `run_tests.py` is dead code and still hardcodes
  `"\x1e" in line or "\x1f" in line`. It is now the **last surviving copy** of
  the premise CR-01 corrected. Nothing reads it, so it cannot cause the defect;
  it can seed it again if someone calls it.
- **IN-02**, **IN-04** — unchanged.
- **IN-03** — re-checked against the standing "correct the changelog if it now
  overclaims" constraint. The "costs nothing" wording was already an overclaim
  before this pass and is not made newly wrong by it, so it is left for a
  deliberate decision. What *was* added is a changelog line for the
  player-visible message CR-02 introduces (`c0a3b8f`), since a new message
  shipping in 1.2.0 and absent from the record is the same accuracy gap pointed
  at the record instead of the code. `addon.version` stays `1.2.0` and the
  newest heading still matches it.

## New harness surface

- **`record` suite** (17 checks) — the counted claims the source and the docs
  make about themselves. Every check derives the true number and compares;
  nothing greps for a phrase that must be absent, which is the check shape that
  let WR-05 survive a previous correction.
- **`settings.save()` fault injection** in `test/stubs.py` — `fail_saves`,
  `heal_saves`, `save_attempts`.
- **24 new addon-suite checks** for CR-02.

## Verification

Run in the **main checkout** (`workflow.use_worktrees` is `false`), not in an
isolated worktree — so these figures are reproducible from the tree as it
stands.

| Run | Result |
|---|---|
| `python test/run_tests.py` | **PASS**, 0 known defects |
| `python test/run_tests.py "<chatlogs>"` | **PASS**, 0 known defects |
| `INCTRACK_LUA=luajit21 python test/run_tests.py "<chatlogs>"` | **PASS**, 0 known defects |

Suite counts against the standing floor, on the chatlog runs (identical on both
backends):

| Suite | Floor | Result |
|---|---|---|
| parser coverage | 11819 exact | 11819 |
| generic tier | 1 exact | 1 |
| tightened patterns | 1 | 1 |
| run reconstruction | 888 | 888 |
| state units | 105 | 105 |
| adaptability | 119 | 119 |
| disconnect | 23 | 23 |
| timers | 31 | 31 |
| persistence | 40 | 40 (running, not skipped) |
| ui | 74 | 74 |
| addon | 190 | **218** |
| cost | 6 | 6 |
| record | — | **17** (new) |

No XFAIL, no FAILED, no NOW PASSING. No count fell.

Other constraints checked: `parser.lua` and `state.lua` still have zero Ashita
dependency (grep for `require('common'|'chat'|'settings'|'json'|'imgui')`,
`AshitaCore`, `ashita.` returns 0 in both); no content name was added to any Lua
file; `addon.version` is `1.2.0`; Phase 2's `imgui.Begin(name, nil, flags)` and
schema `version = 2` are intact; `incursion.render_off = false` still appears at
3 sites and `parse_told`/`save_told` at 2 each; no CI, luacheck or release
tooling added.

**Deployment:** the four Lua files were copied to
`C:\Games\CatsEyeXI\catseyexi-client\Ashita\addons\inctrack\` and verified
CR-insensitively (`diff --strip-trailing-cr`) — all four identical. The deployed
copy was then loaded through the harness under LuaJIT 2.1: it registers, starts
a run from a `Begins!` line, writes it on the next frame, and its gate accepts a
`\127`-hidden needle.

---

_Fixed: 2026-08-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

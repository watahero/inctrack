<!-- generated-by: gsd-doc-writer -->
# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.2.0 — correctness and cost

**Shipped:** 2026-08-29
**Phases:** 4 | **Plans:** 11 (30 tasks) | **Sessions:** 1

117 commits from `44e0eb1` to the `v1.2.0` tag, almost all on one day.

### What Was Built

- **A harness that can reach the addon.** A recording ImGui stub, in-memory
  Ashita fakes and a pure-Lua json, plus `make_host()` and upvalue reflection
  into the addon's file-scope locals. `ui.lua` and `inctrack.lua` — 734 lines
  that had never been executed by a test — now run outside the game.
- **Three defects fixed, each red before and green after** with the assertion
  bytes proven unedited across the fix: `phases_cleared` double-counting a bonus
  payout, a restore that did not age the clocks by the reload gap, and a close
  affordance the window could never draw.
- **Six fragile paths hardened**: a `pcall` with stack repair around `ui.render`
  inside `d3d_present`; three parser tightenings; a structural validator that
  discards a malformed saved session whole; `reset()` clearing the held timer
  sync.
- **The chat-line cost cut and measured**: a seven-needle superset gate turns an
  irrelevant line away before anything is built for it, 3.54× on the reject
  path over a corpus that is three quarters uncoloured; the settings write moved
  off the chat thread onto the frame handler; the memo cache bounded.
- **The documents brought back into agreement with the code**: `docs/design.md`
  rewritten from the source, with two of its hardest claims machine-pinned by
  the `record` suite.

**Where it ended.** 13,461 checks across 13 result lines from 11 suite
functions, PASS with zero known defects on both Lua 5.5 and LuaJIT 2.1, against
127 logs / 2,951,129 lines / 111 completed runs across 8 instances (nine
instances appear in `Begins!` lines; eight have a completion). Four in-game
checks are open and are not claimed as passed.

### What Worked

**Coverage before fixes.** All three confirmed defects had survived a fully
green suite, so the ordering was the argument: build the net, then touch
anything. It paid for itself twice. The first time was the intended one — three
named red lines that went green with their bytes provably untouched. The second
was not planned for: the same net is what made the milestone's own regressions
findable at all.

**Negative-control discipline, and specifically the willingness to report a
control that did not bite.** This is the practice most worth keeping, because
every instance of it is an agent volunteering evidence against its own verdict:

- Phase 3's HARD-03 control was the one the plan required, and it *did not
  bite*: the corpus tightening stayed at 1 check, green. All 469 real
  kill-objective lines split identically under either rule, so no recorded line
  can distinguish them. Family 3 was recorded as **unfalsified by this corpus,
  not proven by it**. Two extra controls were run to find which families do bite
  (1 and 4 did, 467 and 351 times).
- Phase 1's verifier ran a `STAT_SHORT` reorder (M2) that passed, diagnosed
  *why* — the two phrases are not a substring pair, so the reorder is genuinely
  harmless — and retargeted with a true substring pair (M4), which failed by
  name. It reported the first attempt as an invalid mutation rather than as a
  coverage gap or as a pass.
- Phase 4's executor found the plan's prescribed second control **could not
  discriminate**: in the burst-then-unload case the flag is set either way, so a
  conditional and an unconditional unload write behave identically. It wrote a
  control that does discriminate (a throttled kill count outstanding at unload)
  and, in doing so, closed a real hole — nothing in the suite would have noticed
  the unload write being made conditional.
- Phase 2's assertion-integrity script was negative-controlled *before* its
  exit-0 verdict was trusted, once per newly audited item rather than once per
  script.

**Reading the host rather than the documentation.** Every one of the four
Criticals below was found by opening the actual install:
`Ashita/addons/libs/sugar/string.lua:1044-1046`, `plugins/sdk/imgui.h:305`, and
a sweep of all 220 `imgui.Begin(` call sites across the installed addons. None
was findable from a summary, a plan, or a green test run.

**Running both dialects.** Not ceremony: `string.format('%d', nan)` prints
`-9223372036854775808` under LuaJIT and raises under Lua 5.3+, so the same
defect showed as a fabricated clock on the shipped backend and as a dark window
on the harness default.

**The milestone audit earned its cost.** Nine gaps, zero blocking, seven closed
the same day. Fourteen mutations in a throwaway clone: thirteen caught, one
missed — and the one it missed (the timestamp-loop gate) was a genuine unpinned
clause of a ROADMAP criterion.

### What Was Inefficient

**Four of the five Critical findings were regressions introduced by this
milestone's own hardening, and none was visible to the test suite when it
landed.** This is the milestone's central fact and it is not a success story:

| Finding | The regression | Why the suite could not see it |
|---|---|---|
| Phase 2 CR-01 | FIX-03 shipped `imgui.Begin(name, flags)` — a call shape no other addon in the install uses. Ashita's SDK declares one positional signature and slot 2 is `p_open`, so `AlwaysAutoResize`, `NoTitleBar` and `NoMove` could have been silently dropped. | The stub had been written to type-sniff a numeric slot 2 into flags. It agreed with the code. |
| Phase 3 CR-01 | HARD-05's new validator required non-empty strings. The addon's own parser writes a blank `next_boss.name` from a line the server really sends, so the validator rejected sessions the addon itself had written — total loss of a run's boons, points, phase and elapsed on the next reload. | The validator's own comment claimed the shape was "one the addon's own writers cannot produce". It was producible. Nothing tested a round trip through a degenerate real line. |
| Phase 4 CR-01 | PERF-01's cheap gate covered two of Ashita's three colour marker bytes. A marker landing inside one of the seven needles would reject a real Incursion line before it was uncoloured — the window simply never appears, and a dropped line looks exactly like a quiet stretch of chat. | `test/stubs.py`'s `strip_colors` encoded the same wrong marker set. **Each error concealed the other**: the gate was wrong, the stub was wrong in the same direction, and the run was green. |
| Phase 4 CR-02 | PERF-02 moved `persist()` from inside `text_in`'s `pcall` to the top of `d3d_present` with nothing around it — an unprotected disk write on the thread every addon in the process shares, directly under a file header that argues at length that an error there "is not a log line". | Nothing asserted the containment, because the containment had been inherited rather than written. |

The common thread is one sentence: **a stub that agrees with the code proves
nothing.** Phase 4 CR-01 is the pure form of it — two artifacts encoding the
same wrong premise, mutually confirming, with the suite reporting PASS. The
repair was to break the concealment in both directions: the `record` suite now
*derives* the gate's search count from `parser.relevant`'s own body, so a
mutation to either side moves it.

The fifth Critical (Phase 1 CR-01) was a harness defect, not shipped behaviour —
snapshot number formatting that branched on which Lua `lupa` had resolved, so
six windows failed under the dialect Ashita actually embeds.

**Summaries were written before the thing that changed what shipped.** Five
needed SUPERSEDED notes because a review reversed them, and three of the five
went un-annotated until the milestone audit caught them. `02-02-SUMMARY.md` is
the worst case: it is the most-cited record of what shipped for FIX-03, and it
records the two-argument `Begin` call — the exact shape a Critical condemned —
in its frontmatter, its narrative, its scope note and six literal diff blocks.
The ordering is the defect, not the authors: an executor writes the record of
what shipped, then a reviewer changes what shipped, and nothing structurally
returns to the record.

**A review finding that says "decide this" had no mechanism forcing a
decision.** `03-REVIEW.md` IN-05 was left open with the explicit note that
CR-01's fix "has now decided in the opposite direction, so it wants re-deciding
rather than applying as written." No re-decision was ever recorded. The
milestone closed. Only the milestone audit re-opened it — and it turned out to
be a live behavioural hole (a NaN or ±infinity walked through the validator and
drew `~-9223372036854775808:...` where the clock belongs). Two other findings
handed forward to a later phase were also not closed there: `02-REVIEW.md` IN-06
was re-raised in Phase 4 and deferred again; IN-03 was not raised at all.

**The baseline was stale within a day of being recorded.** Phase 1 was given a
floor of 12,841 checks; the unmodified pre-phase harness produced 12,821,
because the corpus is the author's own chatlog directory and he kept playing. A
new log appeared and an existing one kept being appended to. Real effort went
into proving this was input drift and not a regression, and the criterion had to
be re-read as "no suite's count went down" rather than as a literal sum. A check
count over a live private corpus is not a baseline.

**Tooling friction cost real time.** The harness forks agent worktrees from
`origin/HEAD`, which was 109 commits behind local `main`. Two executor
dispatches halted before the workflow was reconfigured to run sequentially
(`workflow.use_worktrees: false`, which is where it still sits). Everything
after that ran in the main checkout, which is why the review and verification
figures are reproducible from the tree as it stands — an accidental benefit of a
real defect.

**Two plan instructions did not survive contact.** Phase 4's plan directed a
correction to a `run_tests.py` module docstring that does not describe the write
policy at all, and asserted `grep -c 'render_off = false'` prints 3 when it
prints 4. Both were caught and recorded rather than silently satisfied; the
second is still open as Broken Window #1.

**The record is very expensive.** Across the milestone: 1,108 inserted lines of
shipped Lua, 6,849 of test harness, and **21,410 lines of `.planning/`
documentation across 51 files**. The eleven summaries alone run to 6,219 lines.
Some of that spend is load-bearing — the audit and the reviews found four
Criticals — but a nineteen-to-one ratio of record to shipped code is a number
that should be looked at before the next milestone, not after it.

### Patterns Established

- **A negative control that does not bite is reported as a limit of the guard,
  not filed as a pass.** Say which family is unfalsified by the corpus rather
  than proven by it, and name what would change that.
- **Break concealment in both directions.** Where a test double encodes a
  premise the shipped code also encodes, derive one from the other in the test
  (the `record` suite reads the gate's cost out of `parser.relevant`'s body) so
  a mutation on either side moves the check.
- **A summary reversed by review carries a SUPERSEDED note at its top**, naming
  the finding, what actually shipped, and where to read the reversal.
- **A defect assertion is written as a delta or a tolerance, never an absolute**,
  so the fix flips it green without the assertion being edited — and the
  byte-identity of the unedited assertion is proven mechanically, with a
  negative control run before the exit-0 verdict is trusted.
- **A disjunctive red line retires with a companion check pinning which branch
  the fix took**, so the other branch cannot satisfy it later.
- **Guard the count, not just the checks.** The phase closes on exactly three
  named red lines, and a guard fails the run on any other number — including
  two.
- **Verify against the host, not the documentation.** Open the shipped install
  and count the call sites.

### Key Lessons

1. **A stub that agrees with the code proves nothing.** Four Criticals, and the
   suite was green for all four. When a test double models a host behaviour, the
   double and the code must be derived from a third thing — the host's own
   source — or checked against it explicitly. Phase 4 CR-01 is the case to cite:
   the gate and the stub carried the same wrong marker set and confirmed each
   other.
2. **Hardening is a change like any other, and its own review is the only thing
   that catches it.** Four of five Criticals were introduced by fixes made in
   the core value's name. A milestone that only reviews the *original* code is
   reviewing the wrong diff.
3. **A review finding of the form "this wants re-deciding" needs a gate.**
   `03-REVIEW.md` IN-05 was correctly identified, correctly deferred, and then
   nothing made anyone decide. It was a live behavioural hole. Info-severity
   findings that request a decision should not be closable by phase completion.
4. **Write the summary after the review, or accept that the record of what
   shipped will be wrong.** Five reversals, three of them un-annotated until an
   audit. The convention (SUPERSEDED notes) works; the ordering that makes it
   necessary is what should change.
5. **A check count over a living private corpus is provenance, not a
   threshold.** Same for a wall-clock rate. State the floor as "no suite's count
   fell" and pin the two counts that genuinely must not move (`parser 11819`,
   `generic 1`) exactly.
6. **A measurement revised downward should be reported as loudly as one revised
   up.** When the stub's `strip_colors` was corrected, the cost ratio fell from
   3.71× to 3.50–3.57× and the recorded baseline moved with it. It was restated,
   with the reason, in the same table — and the shipped CHANGELOG still claims
   3.5× where the shipped backend actually delivers 4.75×. Being wrong in that
   direction is the correct direction to be wrong in.
7. **Name what a number is conditional on, in the place the number is printed.**
   The 3.5× is a property of an 18/6 colour-free benchmark mix, and the real
   in-game mix is *unmeasurable* — Ashita strips the marker bytes before a line
   reaches disk. The figure survived the audit by acquiring its condition, not
   by being deleted.
8. **Evidence has a shape, and the corpus is evidence, not proof.** Two of this
   milestone's guarantees have zero corpus backing by construction: the colour
   fall-through (the markers never reach disk) and HARD-02's " at " case (the
   line never occurs in 127 logs). Both rest on host source and synthetic
   fixtures. Saying so is what makes the other 13,459 checks worth anything.

### Cost Observations

- **Model mix:** not recorded. `config.json` has `model_profile: inherit`, so no
  per-agent model attribution exists for this milestone. What is true: a
  large-context model was used throughout, including for the eleven executor
  dispatches, the four code reviews, the four verifications and the milestone
  audit. If the next milestone wants a cost answer, the profile has to be set
  before it starts.
- **Sessions:** 1 conversation.
- **Dispatches:** roughly 40 subagents across context-gathering, planning,
  plan-checking, execution, review, review-fixing, verification and audit. The
  eleven executor dispatches account for 4h43m of recorded plan-execution time;
  the rest is unmeasured and was almost certainly larger.
- **Where the spend clearly paid:** the four code reviews (four Criticals, three
  of them live silent-failure paths) and the milestone audit (nine gaps, one of
  them a demonstrated behavioural hole nobody had decided about). Both were
  agents doing work no green test run would have done.
- **Where it plausibly did not:** 21,410 lines of planning record for 1,108
  lines of shipped code. Individual summaries run 329–779 lines each and five of
  them are now partly wrong. The audit had to read all eleven to find that out.
  The reviews are worth their cost; the summaries at this length are the
  candidate for trimming.
- **Deferred and now due:** PROC-01…04 (CI, linter, release artifact, public
  fixture) were deferred with the words "revisit once the coverage exists to be
  worth running." That coverage now exists. CI in particular would have caught
  the LuaJIT-only failures in Phase 1 CR-01 without a human noticing.

---

## Cross-Milestone Trends

*This is the first retrospective. The tables below establish the baseline; there
is no trend yet.*

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.2.0 | 1 | 4 (11 plans, 30 tasks) | Baseline. Coverage-before-fixes ordering; per-plan negative controls with non-biting controls reported as limits; SUPERSEDED notes on review-reversed summaries; a milestone audit that re-runs the suite and mutates in a throwaway clone rather than reading the record. Worktrees disabled mid-milestone after two halted dispatches. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.2.0 | 13,461 checks / 13 result lines / 11 suite functions; green on Lua 5.5 and LuaJIT 2.1 | 4 of 4 shipped Lua files reachable by the suite (from 2 of 4). No line-coverage instrument exists; "reachable" is the honest measure. | 0 — no runtime dependency added. Harness needs `lupa` only. |

Open at close, carried into the next milestone: 4 in-game checks (the colour
fall-through first — zero corpus backing by construction); 29 review findings
(28 Info plus the deliberately declined parser half of Phase 3's CR-01); 2 audit
gaps (G-4, needing a rendered frame; G-8, archiving); 1 open Broken Window.
Every Critical and Warning across all four phases is fixed.

### Top Lessons (Verified Across Milestones)

*Nothing is cross-validated yet — one milestone cannot confirm a trend. The two
candidates most worth testing against v1.3.0:*

1. **A stub that agrees with the code proves nothing.** Four of five Criticals
   in v1.2.0. If the next milestone's Criticals come from anywhere else, this is
   specific to a milestone that built test doubles; if they come from here
   again, it is the project's dominant failure mode.
2. **The record of what shipped is written before the thing that changes what
   shipped.** Five reversals in v1.2.0. Whether the SUPERSEDED convention is
   sufficient, or whether the summary has to move after the review, is the
   question v1.3.0 should answer.

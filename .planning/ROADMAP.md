# Roadmap: inctrack

A live HUD for CatsEyeXI Incursions — an Ashita v4 addon that reads the server's
own chat stream. See `.planning/PROJECT.md` for current state.

## Milestones

- ✅ **v1.2.0 — correctness and cost** — Phases 1-4 (shipped 2026-08-29)
- ○ **Next** — not chosen. Candidates are in PROJECT.md's Active section.

## Phases

<details>
<summary>✅ v1.2.0 correctness and cost (Phases 1-4) — SHIPPED 2026-08-29</summary>

A quality pass on shipped code, not a feature release. The ordering was the
argument: all three confirmed defects had survived a fully green test suite, so
the net was built before anything was touched.

- [x] Phase 1: The Net (3/3 plans) — completed 2026-08-29
      `ui.lua` and `inctrack.lua` went from zero automated coverage to a stubbed
      ImGui and a stubbed Ashita host; each defect became a named failing test,
      guarded so the phase could not close with two or four.
- [x] Phase 2: The Three Defects (2/2 plans) — completed 2026-08-29
      The double-counted phase, the un-aged restore and the dead close path. All
      three Phase-1 assertions flipped green with their bytes provably untouched.
- [x] Phase 3: Fragile Paths (3/3 plans) — completed 2026-08-29
      Render errors contained inside `d3d_present`; the parser stopped
      mis-splitting names; a malformed session is discarded whole. `ui.lua` was
      never edited — the render path was made un-crashable from outside it.
- [x] Phase 4: Cost and Record (3/3 plans) — completed 2026-08-29
      An ignored chat line rejected before any allocation, the settings write off
      the chat thread, and the project's documents rewritten from the source.

**Archive:** `.planning/milestones/v1.2.0-ROADMAP.md` ·
`v1.2.0-REQUIREMENTS.md` · `v1.2.0-MILESTONE-AUDIT.md` · `v1.2.0-phases/`

**Closed as `override_closeout`.** Four in-game checks were never run and are not
claimed as passed — they are listed in PROJECT.md and STATE.md. The most
consequential is the colour fall-through, which has zero corpus backing by
construction: Ashita strips colour markers when it writes chatlogs, so none of
the 2,951,129 recorded lines can ever exercise it.

</details>

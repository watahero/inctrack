---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-08-29T08:35:17.028Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 4 | deviation | .planning/phases/04-cost-and-record/04-01-PLAN.md |  | 04-01 acceptance criterion asserts grep -c 'render_off = false' prints 3; it printed 4 at a6a3577 and still does (declaration plus three clearing sites). Intent verified with grep -c 'incursion.render_off = false' = 3. | open |  | 2026-08-29T08:35:17.028Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "4",
    "file": ".planning/phases/04-cost-and-record/04-01-PLAN.md",
    "line": null,
    "description": "04-01 acceptance criterion asserts grep -c 'render_off = false' prints 3; it printed 4 at a6a3577 and still does (declaration plus three clearing sites). Intent verified with grep -c 'incursion.render_off = false' = 3.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-29T08:35:17.028Z",
    "resolved_at": null
  }
]
````

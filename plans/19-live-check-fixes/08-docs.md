# Task 8: Corrections of plans/17-tasks/06-live-check.md

> Finding C1. Docs only; no test. The outcome lines of plan 17's check belong to plan 17 Task 7 (History, D16),
> not here: only the four items below change, in place, each with `(corrected by plan 19)` at its end.

**Files**
- Modify: `plans/17-tasks/06-live-check.md`

## 8.1 The four corrections (final text)

- Item 2, the example request: `(for example, in CONTENT MANAGER: "find where build_export_payload builds the
  export in library/export.py, then add a CSV export next to it with a test")`. The calendar export of the old
  example does not exist there.
- Item 4: `Start a one-step task with an edit step whose goal says "change nothing and do not write the HANDOFF
  block".` (an edit step, not a code step with an empty edit).
- Item 11: `Older rung. Plain Run with the haiku 4.5 rung picked on the card's route (Run raw uses
  cfg.default_model by design, not the card's select): the row shows haiku 4.5 and the result's modelUsage names
  it.` and its second half: `/usage in a terminal has no line per Opus version, so this check cannot tell whether
  the plan counts claude-opus-4-6 apart from Opus 5.5: decision 17's open fact stays open (local Stats lists Opus
  4.6 as its own row).`
- Decision 17 in `plans/17-tasks/README.md` section 2: append `Open fact unresolved by the live check: /usage has
  no per-Opus line (2026-10-12).` to its row. Stage only that line of the README.

## 8.2 Order

1. Edit both files; `git diff` shows only those lines; commit `docs: correct the plan 17 live check items (plan 19 Task 8)`.
2. PLAN.md History line; commit.

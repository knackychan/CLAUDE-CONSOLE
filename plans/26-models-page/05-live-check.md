# Task 5: Fred's live check

> Claude never starts a run, never POSTs `/api/run`, `/api/task`, `/api/prep` or `/api/config/models` against Fred's
> service, and never edits `~/.claude/console/config.json`. Fred runs this after Task 4 is placed and the tray's
> service restarted. Keep a copy of config.json first (`copy config.json config.before-26.json` in the data folder).

## 5.1 The page

1. Settings band, `Models and tuning ›`: the page opens on Kinds; every kind reads `auto`; Checks shows verify and
   fix fixed. The `?` of a card opens its sentence under the head and closes again.
2. Tiers: the order matches config.json's `tiers` (or the defaults); a harness that is off has its rungs counted in
   `n hidden · codex is off`; turn it on in the Settings band, Reload: they come back in their place.
3. Tuning: every value matches config.json or its default; `Turns on design` shows `design_max_turns`.

## 5.2 A Save reaches the next step

4. Kinds: pin `test` to a read rung (for example `haiku`) and effort `low`; Save. config.json holds `"kinds":
   {"test": {"rung": "haiku", "effort": "low"}}` and every other key as before. Run a task with a test step: its
   route line shows `pin test: haiku` and `pin effort: low`; a step of another kind is unchanged. No restart.
5. Pin `design` to a codex think model with codex off: the row says `pinned model hidden · codex is off`; a design step
   routes as auto with `pin design: codex:... refused: codex is off -> auto`.
6. Tiers: move a write rung first; Save; with no allowances set, the next code step runs on it
   (`balance: no allowance set -> <rung> (list order)`).
7. Tuning: set Spend per step to 2; Save; the next step's run carries `--max-budget-usd 2.00` (Claude steps).

## 5.3 Refusals

8. Type 99 in Steps per task: red with the range, Save off. Hand-edit config.json (add a project, say), then Save a
   change on the page: the hand edit is still in the file (D1 a). Break the file (a missing comma) and Save: the page
   shows `cannot read ...: fix it by hand`, the file is untouched; fix it, Reload.

## 5.4 Record

- Each item: what was expected, what was seen. Findings become fixes in a later plan or small commits on this branch
  when they are one-liners.
- Any range of README 3.3 Fred wants different (D3), and the allowances he set (for plan 18's D2).
- Put config.json back from the copy if the check left values Fred does not want.

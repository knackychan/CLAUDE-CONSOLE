> Mirrored by Claude Console from its task folder tasks/20261015-152042-970e/03-design/ for history. Edit the console's copy: this file is rewritten.

# Plan: Audit the Claude Console codebase and write plan 34

## Goal
Turn the scout's findings, the test report (617 tests, 6 failures) and the design read into `plans/34-audit-fixes.md`. Plan 34 is a guided plan in the style of plan 27: findings by severity with file:line, then zero-decision tasks with tests first and final code. Also add a PLAN.md row and a History line. No code changes in this task. Done looks like this: `py -c "import pathlib;t=pathlib.Path('plans/34-audit-fixes.md').read_text(encoding='utf-8');print(t.count('\n## Task '), 'F8' in t)"` prints `6 True`, and `git diff --numstat PLAN.md` prints `2	0	PLAN.md`.

## Decisions
- One file, `plans/34-audit-fixes.md`, not a folder: the goal names `plans/34-*.md` and plan 33 is a single file too.
- File number: 34 unless `plans/34*` exists when the writer starts. In that case use the lowest free N of 34 or more, and change every `34` in the file name, the title and the `plan 34` / `Plan 34` strings to N.
- The plan text is fixed: Sub-plan 1 gives it whole and the writer copies it verbatim.
- PLAN.md is edited by inserting two lines (Edit tool), never rewritten: other chats have uncommitted lines in it (memory: shared docs).
- Nothing is staged or committed: the working tree holds plan 33's uncommitted work from another chat.
- Test failures: five come from test_server reading this machine's config.json, models.json and PATH (F7). One is a race (F8). All are fixed in the tests, not in code.

## Out of scope
- Any file under console/, web/, tests/, dotclaude/, cc_events.py, install_hooks.py: plan 34 is written now and executed later.
- The plan 33 working-tree changes and `plans/33-handoff-retry.md`: another chat's work.
- A second audit pass of the modules the scout did not read: plan 34 lists them as not audited.

## Files
- plans/34-audit-fixes.md (new): the plan text given in Sub-plan 1, verbatim.
- PLAN.md (change): one row after the row `| 33 |` and one History line at the end.

## Sub-plans
| # | Part | Kind | Owns | Depends on | Hard |
|---|---|---|---|---|---|
| 1 | Write plans/34-audit-fixes.md | document | plans/34-audit-fixes.md | - | no |
| 2 | PLAN.md row and History line | document | PLAN.md | 1 | no |

## Acceptance
- `git status --porcelain` shows only `?? plans/34-audit-fixes.md` beyond the entries present at the start (the 11 modified files and `?? plans/33-handoff-retry.md`, unchanged).
- `git diff --numstat PLAN.md` minus the start's PLAN.md diff: exactly 2 added lines, 0 removed (the row and the History line, text as in Sub-plan 2).
- plans/34-audit-fixes.md equals the fenced text of Sub-plan 1 byte for byte, except a renumbering per the Decisions.
- The Sub-plan 1 done check prints `6 True`.
- No file under console/, web/, tests/ changed (`git diff --stat -- console web tests` equals the start state).

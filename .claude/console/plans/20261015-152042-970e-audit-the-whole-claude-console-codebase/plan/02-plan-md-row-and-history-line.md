> Mirrored by Claude Console from its task folder tasks/20261015-152042-970e/03-design/ for history. Edit the console's copy: this file is rewritten.

# Part 2: PLAN.md row and History line

## Files
- PLAN.md (change)
## Actions
1. Read PLAN.md. Find the row that starts `| 33 | [plans/33-handoff-retry.md]` in the `## Sub-plans` table. With the Edit tool, insert this line directly after it (if Sub-plan 1 used another number N, write N in place of 34 in all three places):
```
| 34 | [plans/34-audit-fixes.md](plans/34-audit-fixes.md) - fixes from the codebase audit of 2026-10-15: the hook's import inside never-raise, more secret shapes masked, Stop and reconcile never act on a recycled pid, draft.txt and settings.json written through a temp file, test_server isolated from this machine's config and PATH | written 2026-10-15, code open |
```
2. With the Edit tool, append this line after the last line of the file (the `## History` list ends the file):
```
- 2026-10-15 - Plan 34 written from a codebase audit task (scout, a full test run, design). On Windows, 617 tests had 6 failures: five from test_server reading this machine's config.json, models.json and PATH, and one race in test_bulk_delete_takes_finished_tasks_only. 8 findings with a task each (F1-F3 security, F4-F6 data safety, F7-F8 tests); the plan also lists what was checked OK and the modules this pass did not read. No code changed.
```
3. Do not stage or commit. Change no other line.
## Tests
- No test files: this part edits a document.
## Done check
`git diff -U0 PLAN.md | findstr /B "+| 34 +- 2026-10-15 - Plan 34"` prints the two added lines.

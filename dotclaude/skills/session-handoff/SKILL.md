---
name: session-handoff
description: Use when a task has landed, the chat has run long, or the user corrected the same point twice, before running /clear or /compact. Writes the decisions and the next step as one-liners where the next chat will read them, then hands the user a restart line. Stops before the next task starts.
---

# Session handoff

Turns the useful part of a long chat into a few one-line records, so a fresh chat can start clean without losing its decisions. It writes the records and a starter prompt, then stops; the user runs `/clear` (Claude cannot run slash commands). In Claude Console the turn that runs this skill marks the session Done.

## Read first

- If the skill came with arguments (Claude Console's Hand off after a PASS starts a fresh chat), they are a brief of the earlier chat: goal, last message, edited files, last check and git status. Treat the brief as "this chat" in the steps below, and take its decisions from it, the diff and the git log.
- The project's `CLAUDE.md`, then its plan: `PLAN.md` at the repo root, or `projects/<name>/PLAN.md` in a repo with several projects. Its `## History` section is the decision log.
- The auto-memory index `MEMORY.md` and any memory file it lists for the same project.
- `git status --short` and `git log --oneline -5` for what actually changed.

## Steps

1. Check inputs: name the task of this chat in one line. If no task was finished or decided, say so and stop (nothing to hand off).
2. List the decisions made in this chat. One line each: what + why. Drop anything the code or git history already records.
3. List what is still open: the next step, and any check that has not been run (tests, build, GUI check).
4. Write each decision where it belongs:
   - project decision or progress: append one dated line to `## History` in the project's `PLAN.md`, in the format already used there (for example `- 2026-10-10 - <what>; <why>.`); a project without a `PLAN.md` gets none, use memory instead;
   - how the user wants work done, or a fact for every future chat: update or add an auto-memory file (check for an existing one first, then the `MEMORY.md` pointer);
   - a rule for every task in this repo: propose the CLAUDE.md line to the user, do not write it.
5. Remove or correct any older line this chat proved wrong (notes spread mistakes too).
6. Print a starter prompt for the next chat, at most 5 lines: the project, the files to read first, the next step, the check that proves it is done.
7. Tell the user the exit:
   - default: `/clear <short-name>` (the name labels this chat in `/resume`), then paste the starter prompt;
   - only if the task must continue in this chat: `/compact focus on <the open step and the decisions above>`.

## Done looks like

- Every decision from step 2 appears in exactly one place (PLAN.md History, a memory file, or a proposed CLAUDE.md line shown to the user).
- `git diff` shows only one-line additions or corrections to History / memory files, no code changes.
- The starter prompt names a file to read and a check to run.

## Never

- Never write notes into folders the project's CLAUDE.md marks as generated, exported or wiped, and never create a new decisions file without the user asking.
- Never paste a chat summary into memory or PLAN.md; one line per decision, or nothing.
- Never edit CLAUDE.md in this skill; propose the line and let the user decide.

## Sources

CONTENT MANAGER `data/notes/context-playbook.md` (levers 1, 3 and 5; "Lever details"), source page by @donimas: famous-mandarin-287.notion.site/Context-Playbook-3f11be55d9b881e7a6f6eee5d74b196d. `/clear [name]` and `/compact [instructions]` checked against code.claude.com/docs/en/commands on 2026-10-10. Moved from CONTENT MANAGER to `~/.claude/skills` by Claude Console plan 04.

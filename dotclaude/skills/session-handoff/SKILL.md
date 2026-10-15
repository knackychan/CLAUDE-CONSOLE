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
   - a lesson, what you would tell someone starting this kind of task tomorrow (transferable, one sentence; most chats teach nothing, so leave it out rather than pad): append one line to `~/.claude/console/lessons.md` (create it with the line `# Lessons` and a blank line first if it does not exist), in exactly this shape, so Claude Console's rules review reads it:

```
- 2026-10-13 - CLAUDE CONSOLE - chat: a stream-json interrupt stops a turn cleanly where Ctrl+C to a hidden console does nothing.
```

     The project is the git root folder's name; the kind is `chat`.
5. Remove or correct any older line this chat proved wrong (notes spread mistakes too).
6. Tell the user the exit, in one line:
   - default: `/clear <short-name>` (the name labels this chat in `/resume`), then paste the handoff block below;
   - only if the task must continue in this chat: `/compact focus on <the open step and the decisions above>`.
7. End the message with the handoff block, the same six headings a Claude Console task step writes, so the next chat (or the console's Start next chat) reads it whole. Nothing comes after `END HANDOFF`. Keep it under 300 words; a heading with nothing to say gets `- (none)`:

```
HANDOFF
## Goal
<the task goal in one line, then what the next chat does of it in one line>
## Findings
- <what this chat established that the next one needs, one line each>
## Files touched
- <path>: <what changed, one line>
## Troubleshooting
- <a trap the next chat would hit again: the symptom, then what works>
## Open questions
- <only questions the next chat cannot answer from the files>
## Next
<the next step and the check that proves it is done; name a file to read first>
END HANDOFF
```

## Done looks like

- Every decision from step 2 appears in exactly one place (PLAN.md History, a memory file, or a proposed CLAUDE.md line shown to the user).
- `git diff` shows only one-line additions or corrections to History / memory files, no code changes.
- The message ends with the HANDOFF block; its Next names a file to read and a check to run.
- A lesson, when there was one, is one line in `~/.claude/console/lessons.md` and nowhere else.

## Never

- Never write notes into folders the project's CLAUDE.md marks as generated, exported or wiped, and never create a new decisions file without the user asking.
- Never paste a chat summary into memory or PLAN.md; one line per decision, or nothing.
- Never edit CLAUDE.md in this skill; propose the line and let the user decide.
- Never write a lesson that only applies to this one file or chat: most chats teach nothing, and a padded line costs every later review.

## Sources

CONTENT MANAGER `data/notes/context-playbook.md` (levers 1, 3 and 5; "Lever details"), source page by @donimas: famous-mandarin-287.notion.site/Context-Playbook-3f11be55d9b881e7a6f6eee5d74b196d. `/clear [name]` and `/compact [instructions]` checked against code.claude.com/docs/en/commands on 2026-10-10. Moved from CONTENT MANAGER to `~/.claude/skills` by Claude Console plan 04.

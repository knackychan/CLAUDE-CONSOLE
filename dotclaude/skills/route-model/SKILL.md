---
name: route-model
description: Use at the start of a coding task in Claude Code (or when the user asks which model or effort to use) to pick effort first, then the model tier, by task type and risk; then verify on opus, escalate once on FAIL, and log the miss. Stops after the verify step reports PASS or after one escalation.
---

# Route model

Picks the cheapest route that should solve the task: effort level first, model tier second, delegating mechanical or read-heavy parts to subagents with a fixed model. It checks the result with code, escalates one step at most, and records every miss so the next route is better. Claude Console's Prep step uses the same table and the same misses file.

## Read first

- The task as the user wrote it, and the project's plan if one exists (a zero-decision plan usually runs fine at lower effort).
- The project's `CLAUDE.md`: what it calls risky (database, threading, installer, user data) decides the `risky` row.
- `~/.claude/console/routing-misses.md`, the lines tagged with this project (` - <project folder name> - `). Past misses override the table.
- The `verifier` agent (`.claude/agents/verifier.md` in the project, else `~/.claude/agents/verifier.md`).

## Route table

| type | when | model | effort | who does it |
|---|---|---|---|---|
| mechanical | rename, copy, docs text, a 1-2 file edit with a clear spec | sonnet | low | `cavecrew-builder` subagent with `model: sonnet` |
| lookup | find, explain, summarise, read many files, no edits | haiku | low | `cavecrew-investigator` or Explore subagent; restate the rules that matter (they do not see CLAUDE.md) |
| normal | a feature or fix with a clear spec or plan | sonnet | medium | main session |
| risky | database schema, threading, security, installer or updater, anything near user data | sonnet | high | main session; the opus verifier (step 6) checks it, and a FAIL escalates to opus/high (step 7) |
| vague | design, planning, or unclear (and ask in `question`) | opus | high | ask questions or brainstorm first, then re-route; plan mode |

## Steps

1. Check inputs: restate the task in one line. If it is vague, ask the clarifying questions before routing (a clear spec buys more than effort does).
2. Read the project's lines in `~/.claude/console/routing-misses.md` and apply any that match this task type.
3. Pick the row. Tell the user the route on its own line, in this shape (Claude Console reads it): `Route: mechanical, low effort, cavecrew-builder on sonnet`.
4. If the main session's level should change, tell the user the command (`/effort low|medium|high|xhigh|max`, or `/model haiku|sonnet|opus|fable`); Claude cannot run slash commands. Change routes at the start, not mid-task: a model switch rebuilds the prompt cache.
5. For delegated parts, call the Agent tool with the row's agent and `model`; this skill counts as the explicit instruction for an `effort` value when the row names one.
6. Verify with code: run the `verifier` agent with the Agent tool and `model: opus` (a stronger model checks the cheaper one's work); its report ends in `VERDICT: PASS` or `VERDICT: FAIL <line>`.
7. On FAIL: one repair at the same route. If it still fails, escalate one step, once: effort +1 while below high; at high or above, the next model (haiku, sonnet, opus, fable) at the same effort; on fable, effort +1. If that fails too, stop and report the failing lines.
8. If step 7 escalated, append one line to `~/.claude/console/routing-misses.md` (create it with the line `# Routing misses` and a blank line first if it does not exist). Use exactly this shape, so Claude Console's Prep can read it:

```
- 2026-10-10 - CLAUDE CONSOLE - normal: sonnet/medium failed (tests/test_state.py:40 - KeyError: 'rules'); next time start at sonnet/high.
```

   The project is the git root folder's name; the type is the row from step 3.
9. If you must stop for a decision only the user can make, end the message with one line: `STOP: <question>`.

## Done looks like

- The route line was shown to the user before work started.
- The verify step ran on opus and its output is quoted (PASS, or the shortest failing line).
- Every escalation has a matching line in `~/.claude/console/routing-misses.md`.

## Never

- Never start implementation on opus: opus is for design, planning (the `vague` row) and the verify step; code reaches opus only by escalating on FAIL.
- Never escalate more than once per task, or retry the same failing route more than once.
- Never call the work done on a cheap route without a code check; a passing test can still hide a wrong patch, so say what the check did not cover.
- Never switch the model mid-task to save money on the remaining steps.
- Never write misses anywhere else (not auto memory, not the repo): one file, read by Prep and by this skill.

## Sources

CONTENT MANAGER `data/notes/model-routing-playbook.md` (5 rules, patterns 1 to 5, "The GOAT router in real tools", "The spec rule"); page by @donimas: famous-mandarin-287.notion.site/Model-Routing-Playbook-3f01be55d9b881fbb5d5f0a20f30b265. `/effort`, `/model` and subagent `model` / `effort` frontmatter checked against code.claude.com/docs (commands, model-config, sub-agents). Moved from CONTENT MANAGER to `~/.claude/skills` by Claude Console plan 04; the table matches `console/prep_prompt.md` (a test checks it).

# Task 4: Tell every worker what to write

Plan only. Future files: `console/step_prompt.md`, `console/tasks.py`, the thirteen kind seeds below,
`tests/test_tasks.py`, `tests/test_dotclaude.py` and the existing fake-provider fixtures. Do not change installed
kind files in this task. `kinds.ensure` never overwrites Fred's existing text, so changing a seed alone is not a
rollout. Fred's reset is an explicit Task 5 step.

## 1. Final shared prompt

Replace `console/step_prompt.md` with this text. Only handoff transport changes; six headings and their content
instructions remain. The output pathname is a service-supplied absolute path, quoted as JSON in the rendered
prompt so spaces, backslashes and Unicode do not require the model to expand `~` or infer cwd.

```text
You run one step of a task that Claude Console drives as a chain of separate runs. Earlier steps ran in other
sessions; what they found reaches you only through the handoff below. Later steps will see only your handoff.

Task: $title
$goal

Step $n of $m: $kind. $step_goal

${role}$retry
${plan}What the earlier steps left you:
$prev

${lessons}${part}Rules for this step:
- Do only this step. Do not start the next one, and do not run /session-handoff.
- Work alone: read what you need yourself, as little as the step needs, and do not hand the work to another agent.
- Edit project files only when your step's role permits it. Every worker must write its assigned handoff file;
  that single output is an exception to a read-only role. It is not permission to edit other Console files.
- Write your complete handoff as UTF-8 Markdown to this exact absolute file path: $handoff_path
  Its parent already exists. Keep the project as your working directory. Replace the whole file when updating
  it. Do not write another handoff.md, the step's parent handoff.md, or an earlier attempt's file.
- Use the six headings below, in order. Do not add HANDOFF or END HANDOFF markers or a surrounding code fence.
  Keep the complete file within 20 KiB. A missing or invalid file fails the step; a note pasted into the reply
  does not substitute for the file. Read back the file before finishing when your tools permit it.
- Your final reply may contain a short completion note and useful debugging detail under ## Notes. The service
  saves it as notes.md. Keep VERDICT and PLAN/SUBPLAN output in the reply when your role requires them.
- If you cannot go on without a choice only $you can make, end the reply with:
  DECISION: <the question in one line>
  - a) <option>
  - b) <option>
  DEFAULT: a <why this one, one line>
  Two to four options. Leave DEFAULT out when no option is safe to take without $you. A fact you can read in the
  project is never a DECISION: read it. Save the current handoff if possible, but ask the question even when a
  file write is blocked. After an answer, use the new output path supplied with that turn.

The file must contain:

## Goal
The task goal in one line, then this step's part of it in one line.
## Findings
What you learned or did, in a few lines, with the file paths and line numbers that matter.
## Files touched
- project path (what changed), or: - (none). The handoff output itself is not a project change.
## Troubleshooting
- what failed and what fixed it, what you tried that does not work, a command that reproduces it, or: - (none)
## Open questions
- a question the next step or $you must settle, or: - (none)
## Next
One line for the next step. Add `Next model: <tier>/<effort>` only when the next step needs more than planned: the
tier is haiku, sonnet or opus (cheapest to strongest, whatever CLI runs the step), the effort low, medium or high.
Add `Lesson: <one sentence>` only when something transferable surprised you, what you would tell someone starting
this kind of step tomorrow; most steps have none, so leave the line out rather than pad.
```

`tasks.step_prompt` gains the trailing keyword `handoff_path: str = ""`; for FILE_KINDS refuse an empty/non-absolute
path rather than leaving a template variable visible. Add to the existing safe_substitute call:

```python
        handoff_path=json.dumps(handoff_path, ensure_ascii=False),
```

Do not put a path variable in the kind files; `role_text` has a different substitution context. The common
prompt carries the exact path once. Existing role/lessons/goal/plan/retry slots retain their semantics.

## 2. Final kind edits and exact reset list

For these twelve kinds, replace the common closing paragraph beginning `End your final message with the HANDOFF
block` and ending `hands the next step the block alone` with:

```text
Write the six-heading handoff to the exact file named in the shared rules below. Do not put the handoff in your
reply. Useful debugging detail may stay in the reply under ## Notes; the service saves that as notes.md and
hands the next step the checked file alone. This assigned file is the only exception to any read-only rule in
this role; it does not authorize changes to other Console files or to project files outside this step's scope.
```

| Seed under dotclaude/console/kinds | Additional exact change | Fred resets |
|---|---|---|
| scout.md | `Edit, create or delete any file.` becomes `Edit, create or delete project files. The assigned handoff output is required.` | scout |
| search.md | Same read-only sentence change | search |
| explain.md | Same read-only sentence change | explain |
| test.md | `Edit any file, or fix what fails: the next step does that.` becomes `Edit project files or fix what fails: the next step does that. Write only the assigned handoff output.` | test |
| verify.md | Both `Do not edit any file` and the Do not bullet become project-file restrictions with the handoff exception. Replace `in your final message, just before the HANDOFF block` with `in your final message. Write the six-heading note into the assigned handoff file` | verify |
| draft.md | Append the assigned-output exception to `Touch any file the step goal does not name.` | draft |
| proofread.md | Common closing paragraph only; its role still permits wording edits | proofread |
| edit.md | Append the assigned-output exception to `Touch a file the spec does not name.` | edit |
| code.md | Add to `Touch a file the plan's Files list does not name`: `The service-assigned handoff output is an exception.` | code |
| document.md | Common closing paragraph only | document |
| debug.md | Common closing paragraph only | debug |
| fix.md | Append the assigned-output exception to `Touch a file the failure does not lead to.` | fix |
| design.md | Special replacements below; no common closing paragraph | design |

For design, replace `Write no file: the plan is your final message.` with:

```text
Do not edit project files. The plan is your final message; the assigned handoff file is your only file output.
```

Replace the two sentences beginning `Your final message carries the plan` with:

```text
Your final message carries the plan between a line PLAN and a line END PLAN, with any SUBPLAN blocks afterward.
Write the separate six-heading handoff to the exact file named in the shared rules. The service saves the plan
whole as plan.md in the task folder; it is never compacted and never cut, so do not shorten it to fit anything.
```

Keep all design's sections, final-code requirements, Plan gap/DECISION behavior, part allocation and limits.
Do not convert PLAN into another file contract in this task. Prep, replan, planner and supervisor seeds and
`dotclaude/skills/session-handoff/SKILL.md` are deliberately unchanged (D7).

## 3. Continue wording and legacy prompts

On file-protocol Continue/guidance, replace `Rebuild your complete HANDOFF from the resulting work` with the
following helper's result; legacy Continue retains its original wording. Do not substitute the new protocol
into the middle of an old in-flight conversation that was given the marker contract.

```python
def output_instruction(path: str) -> str:
    return ("Write the complete updated six-heading handoff to "
            + json.dumps(path, ensure_ascii=False)
            + ". This is the output for this turn; earlier output files do not count. "
              "Do not put HANDOFF markers or the handoff body in the reply.")
```

Add it in `tasks.py` for both `_guidance_tick` and `_pull` to call. Design guidance still asks for the complete
updated PLAN/SUBPLAN reply. Include the instruction in the actual prompt stored in the stream, not merely
role.md, so recovery shows which path that turn received.

## 4. Future checks and Fred's rollout

Update prompt tests to assert the absolute target occurs once, HEADINGS are in order, no wrapper marker lines
exist, project-read-only exceptions are present and no `$handoff_path` leaks. Keep a session-handoff skill test
using legacy parse_handoff; it must still pass. Fake providers now create the assigned file when explicitly in
file mode, independently of their final reply; missing/invalid/stale modes must be selectable without real tools.

After Fred approves and the code is built, he reviews any custom local kinds, then uses **Models > Kinds >
Reset to repo copy** for: scout, search, draft, proofread, edit, code, document, explain, debug, test, design,
verify, fix. Confirm the next run's role.md and stored prompt both describe the file and the same output path.
Restarting the service only seeds missing kinds and does not replace existing ones. The executor never resets
them behind Fred's back or copies over his CLI settings. Record each reset (or reviewed manual merge) in Task 5.

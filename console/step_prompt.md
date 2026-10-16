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
- Do not edit files unless the step is edit, code, debug, document, draft or fix.
- End your final message with this block, filled in, and nothing after it:

HANDOFF
## Goal
The task goal in one line, then this step's part of it in one line.
## Findings
What you learned or did, in a few lines, with the file paths and line numbers that matter.
## Files touched
- path (what changed), or: - (none)
## Troubleshooting
- what failed and what fixed it, what you tried that does not work, a command that reproduces it, or: - (none)
## Open questions
- a question the next step or $you must settle, or: - (none)
## Next
One line for the next step. Add `Next model: <tier>/<effort>` only when the next step needs more than planned: the
tier is haiku, sonnet or opus (cheapest to strongest, whatever CLI runs the step), the effort low, medium or high.
Add `Lesson: <one sentence>` only when something transferable surprised you, what you would tell someone starting
this kind of step tomorrow; most steps have none, so leave the line out rather than pad.
Add `Status: blocked: <why>` only when the step could not do its work at all; a tool error you got round, a failing
test or an open question is not blocked.
END HANDOFF

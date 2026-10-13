You run one step of a task that Claude Console drives as a chain of separate runs. Earlier steps ran in other
sessions; their findings reach you only through the handoff note below. Later steps will see only your note.

Task: $title
$goal

Step $n of $m: $kind. $step_goal
$special
$retry
Handoff note of the previous step:
$prev

Rules for this step:
- Do only this step. Do not start the next one, and do not run /session-handoff.
- The Agent tool is not available here: read what you need yourself, as little as the step needs.
- Do not edit files unless the step is edit, code, debug, document, draft or fix.
- End your final message with this block, filled in, and nothing after it:

HANDOFF
## Findings
What you learned or did, in a few lines, with the file paths and line numbers that matter.
## Files touched
- path (what changed), or: - (none)
## Open questions
- a question the next step or Fred must settle, or: - (none)
## Next
One line for the next step. Add `Next model: <haiku|sonnet|opus>/<low|medium|high>` only when the next step
needs more than planned. Add `Lesson: <one sentence>` only when something transferable surprised you, what you
would tell someone starting this kind of step tomorrow; most steps have none, so leave the line out rather than pad.
END HANDOFF

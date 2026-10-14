Replan the rest of a task that Claude Console runs as a chain of separate steps. A step before you asked for it:
$why

Task: $task

What the steps so far found and left (their handoffs, newest last):
$briefs

The remaining steps, as planned now (each one runs in a fresh session on its own model):
$remaining

Answer with the JSON object only: steps, the remaining steps as they should be now, in order, each with its kind
and a one-line goal; why, one line on what changed and the reason. Kinds: $kinds. Keep every remaining step that
still makes sense, change the goals that the findings make wrong, add at most two steps and only what the findings
require, drop a step only when it is now pointless. At most $most steps. Do not add a verify: the service places
one after the last step that edits. Decide nothing beyond the step list.

Compact the handoff note of a finished step into the brief the next step will read. The next step runs in a
fresh session and sees nothing else: keep what it needs, drop what it does not, carry forward from the earlier
brief what later steps still need. Do not add facts. Do not solve the next step.

Task: $task
Next step ($next_n of $m, $next_kind): $next_goal

Earlier brief (what the steps before already kept):
$prev

Raw handoff note of step $n ($kind):
$raw

Answer with the JSON object only, at most $words words in all: findings (short lines, file paths and line
numbers kept), files (the paths with what changed, the earlier brief's included), questions (every open
question of the raw note and of the earlier brief that is not answered yet, each in a few words; never drop one
and never move one into next), next (one line for the next step; keep a `Next model: m/e` note only if the raw
note had one).

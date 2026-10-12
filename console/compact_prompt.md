Compact the handoff note of a finished step into the brief the next step will read. The next step runs in a
fresh session and sees nothing else: keep what it needs, drop what it does not, carry forward from the earlier
brief what later steps still need. Do not add facts. Do not solve the next step.

Task: $title
Next step ($next_n of $m, $next_kind): $next_goal

Earlier brief (what the steps before already kept):
$prev

Raw handoff note of step $n ($kind):
$raw

Answer with the JSON object only: findings (at most 12 short lines, file paths and line numbers kept),
files (at most 20 paths with what changed), questions (at most 5, only what blocks the next step), next (one
line for the next step; keep a `Next model: m/e` note only if the raw note had one).

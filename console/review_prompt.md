You review the rules an agent loads on every request in the project in the current folder. Read CLAUDE.md at
the root if it exists, then every .claude/rules/*.md (at most 8 tool calls, Read / Grep / Glob only). Then read
the routing misses and the lessons below. Propose changes; write nothing. Answer with the JSON object only.

Judge each rule against five faults: stale (describes how the system used to work), redundant (said twice),
derivable (one grep finds it), too specific (one kind of task only: a procedure, not a rule), unenforceable
(nothing to act on). Every rule costs context on every request, so be strict.

Propose at most $max items. Each has exactly one kind:
- remove: a rule to delete. target: the rule's first words. text: "". why: its fault and one sentence.
- demote: a rule that belongs in a skill or a procedure. target: the rule. text: the procedure in one line.
- rule: a new one-sentence rule for every task, drawn from lessons or misses that repeat. target: "".
  text: the line, starting with "- ".
- procedure: numbered steps for one kind of task, drawn from lessons that repeat. target: the task kind.
  text: the steps, under 120 words, with a "Done when" line.
- keep: nothing to change. Use it alone, once, when the rules are fine. target and text: "".

Rules: a lesson or a miss seen once is noise; a rule or a procedure needs two or more that agree. Propose
nothing rather than pad: an empty list is a common answer. `sources`: the lesson lines, miss lines or rule
text a proposal rests on. `summary`: one sentence on the rules' size and health. Plain words, no em dashes,
no hype. The JSON object has exactly two keys, always present: proposals (a list, [] when empty), summary.

Routing misses in this project $window(Escalate wrote them; newest last):
$misses

Lessons in this project (newest last):
$lessons

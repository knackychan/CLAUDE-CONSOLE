# Task 3: one decision card (change C, D2 a, D3 a)

Files: `console/tasks.py` (`reply_decision`, `DECISION_MAX`, `on_step_ended`), `console/server.py` (`_ended`,
`Hub.tick`, `task_row`, `task_message` answer path, `_decision_default`), `console/step_prompt.md`,
`dotclaude/console/kinds/design.md`, `console/plan.py` (no change; `add_answer` reused), `console/paths.py`,
`console/tuning.py`, `tests/test_tasks.py`, `tests/test_server.py`, `tests/test_plan.py`.
Commit boundary: `feat: DECISION block, the decision card and its default after a timeout (plan 52 Task 3)`.

## Format (the model's side)

`console/step_prompt.md`, one rule added after the "Do not edit files" line:

```
- When the step cannot go on without a choice only $you can make, end your final message with the HANDOFF block
  and then:
  DECISION: <the question in one line>
  - a) <option>
  - b) <option>
  DEFAULT: a <why this one, one line>
  Two to four options. Leave DEFAULT out when no option is safe to take without $you. A fact you can read in the
  project is never a DECISION: read it.
```

`dotclaude/console/kinds/design.md`, after "If you cannot close a fork from what you read, read more.":
"An Open question from an earlier step that the project answers (a file, a config value, a script name) is yours to
answer here, in Decisions, with the path you read. Only a choice of taste, scope or naming that two readings of
the repo would make differently goes to $you, as a DECISION block (the rule at the end of this prompt)."

## Parse (`console/tasks.py`)

```python
_DECISION = re.compile(r"^[\s`*>\-]*DECISION:\s*(.+?)[\s`*]*$", re.M)
_OPTION = re.compile(r"^[\s`*>]*-\s*([a-d])\)\s*(.+?)\s*$", re.M)
_DEFAULT = re.compile(r"^[\s`*>\-]*DEFAULT:\s*([a-d])\b[\s:,\-]*(.*?)[\s`*]*$", re.M)
DECISION_MAX = 200  # characters of the question and of each option, as a STOP question


def reply_decision(text: str):
    """The last DECISION block of a reply: {"q", "options": [{"key", "text"}], "default": key or "", "why"}; None
    when there is none or it has fewer than two options (a DECISION line alone is a plain STOP question, read by
    reply_question)."""
```

`reply_question(text)`: also matches a `DECISION:` line (the same `_NO_QUESTION` rule), so a block with one
option still waits as a plain question. `_STOP` gains `DECISION` as an alternative: `r"^[\s`*>\-]*(?:STOP|DECISION):\s*(.+?)[\s`*]*$"`.

`on_step_ended(..., question, now, cap="", decision=None)`: when `decision`, `task["decision"] = {**decision,
"step": s["n"], "asked": now}` before `_task_to(task, "waiting", "asks: " + question ...)`; the chain line's why is
`asks: <q> (a, b; default a)`. Popped in `Hub._ended` when the run goes live again (the answer arrived) and by
Stop, Retry, Finish (`tasks.fred`).

## Service (`console/server.py`)

- `_ended`: `decision = tasks.reply_decision(text)`; `question = ... or (decision["q"] if decision else "")`; passes
  `decision=decision` to `on_step_ended`. The Plan gap path is unchanged (free text only).
- `task_row`: `"decision": t.get("decision") or None`.
- `task_message` in `answer` mode: unchanged (the UI posts the option's text, or free text). The answer joins
  plan.md Decisions when the task has a plan: in `_guidance_tick` where `question` is detected (server.py:1321),
  when `task.get("decision")` and `task.get("plan")`: `plan.add_answer(self.folder, task, f"{q}: {text}", who=paths.you(self.cfg, start=True))`
  and the chain line `decision answered by <you>: <text>`.
- `Hub._decision_default(task, now) -> bool` (called from `Hub.tick` once a second, under tlock): when
  `task["state"] == "waiting"`, `task.get("decision")` has a `default`, the policy mode is `auto`, not paused, no
  pending guidance, and `now - decision["asked"] >= self.cfg["decision_timeout_s"]`: the default option's text goes to
  the step as an answer through `self.pull(cs["session"], "continue", text, auto=1)`; chain line `decision taken by
  default: <key>) <text>` and `plan.add_answer(..., who="Default")` when the task has a plan; `task["decision"]["taken"]
  = "default"`. Returns True once. `gated` and `suggest` wait.
- `paths.DEFAULTS`: `"decision_timeout_s": 600`; `tuning.TUNING`: `("supervisor", "s", 0, 86400)`; 0 = take the default
  at once on `auto`.

## Tests (red first)

- `tests/test_tasks.py::test_reply_decision_parses_options_and_default`, `test_decision_with_one_option_is_a_question`,
  `test_on_step_ended_saves_the_decision_and_waits`.
- `tests/test_server.py::test_decision_card_waits_and_an_answer_joins_the_plan` (fake word `DECIDE-NAME`: the fake
  answers with a HANDOFF and a DECISION block with two options and a default; the task waits `asks: ...`,
  `task_row["decision"]` has two options; POST /api/task/message answer mode with the option text: the step's
  session gets the text, plan.md Decisions gains the line, `task["decision"]` is popped),
  `test_decision_default_after_timeout_on_auto_only` (fake clock: auto takes the default at 600 s with the chain
  line and `who` Default; gated and suggest still wait at 601 s; a task with no default waits on auto).
- `tests/test_plan.py::test_with_answer_names_the_default` (who "Default").

## Drift guards

- No new model call: the card is parsed by code; the timeout sends the default as an ordinary answer.
- `plan.gap` and `Plan gap:` keep their free-text card (plan 24); a `DECISION` block in a design step's reply is
  refused like a `Replan:` line (chain `decision refused: design step`) because the design step must close forks.

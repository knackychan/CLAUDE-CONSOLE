# Ticket: Prep fails with error_max_structured_output_retries

Status: second fix applied 2026-10-13 (schema loosened, Fred's choice); see "Fix 2". The 2026-10-12
prompt fix did not hold.
Open this file first in a fresh session, then read "If it happens again".

## Symptom

Red Prep card with "Try again" in the web UI:

```
Prep failed: error_max_structured_output_retries; structured_output_retry_exhausted;
Failed to provide valid structured output after 5 attempts. Output does not match required schema:
root: must have required property 'question', root: must have required property 'route'
```

The CLI (`claude -p --json-schema ...`, Haiku) retried 5 times and every try missed `question` and `route`.

## Where

- `console/prep.py`: `SCHEMA` (all 8 keys required, `route` is an object with type, model, effort),
  `parse_output`, `run_prep`
- `console/prep_prompt.md`: the instructions Haiku gets, `$raw` and `$misses` filled by `build_prompt`
- `console/claude_cli.py`: `prep_command` (the flags)

## What was found (2026-10-12)

- Could not reproduce: 11 real Prep calls on the old prompt, simple, vague, risky and long requests,
  all succeeded. The failure is intermittent or depends on one request. The raw request of the
  failing run was not saved.
- Hypothesis (unconfirmed): the old prompt said `question` was optional ("else """) and defined
  `route` only through the table columns, so Haiku skipped `question` and put type, model and effort
  at the top level.

## Fix applied

- `console/prep_prompt.md`: added an "Output rules" paragraph: exactly 8 keys, all always present,
  `""` for an empty text field, `"question": ""` when nothing is open, `route` always an object with
  type, model and effort, never at the top level.
- `tests/test_prep.py`: `test_schema_shape`, `test_prompt_demands_every_key`.
- `SCHEMA` required list untouched.
- `py -m unittest discover -s tests`: 146 tests OK. The Try again path in `web/app.js` was not
  driven in the UI.
- Not synced: `plans/03-levers.md` Step 7 still holds the old prompt text.

## Reproduced (2026-10-13)

- Request: Fred's "focus on the mobile app, settings area ... Obsidian synchronization, Google Drive
  account ..." (four lines, three bugs), project `D:\MY DOCS\MY TOOLS\CONTENT MANAGER`, with its
  routing misses filled in. Fred's Prep failed twice in the window.
- 5 real calls: 1 ended in `error_max_structured_output_retries` ("must have required property
  'done_when'"), 1 succeeded only on the 5th and last attempt, 3 succeeded at once.
- The `stream-json` trace of each `StructuredOutput` attempt shows the keys are just absent, never
  flattened: the flattening hypothesis is wrong. Missing per attempt: keep + last_decisions +
  question; question; question + route; question + route; then all 9.
- What drops is the tail of a long answer (`where` and `keep` ran past 1,000 characters each) and the
  keys that would be `""`. On a retry Haiku resends the same object with the same keys missing, so
  the 5 retries rarely help.

## Fix 2 (2026-10-13)

- `console/prep.py`: `SCHEMA` requires only `goal` and `route`; `route` is the first property;
  `parse_output` sets every missing text field (`TEXT_KEYS`) to `""`. The prompt's Output rules stay.
- `tests/test_prep.py`: `test_schema_shape` updated, `test_parse_output_fills_missing_text_fields`.
- 5 live calls on the mobile request after the fix: 5 succeeded on the first attempt; 3 of them still
  left out `question` or `last_decisions`, each of which used to cost a retry.
- Left open: a missing `route` still fails the schema (not seen after the fix). If it shows up, the
  next options are one automatic retry of the Prep job, or `prep_model` sonnet.

## If it happens again

1. Get the raw request that failed (the text typed in the prompt box). Without it nothing can be
   reproduced.
2. Check the card text. `parse_output` now prints `subtype`, `terminal_reason` and `errors`, so the
   missing keys are named.
3. Reproduce with the script below (read-only Haiku call, about 0.004 USD, writes nothing).
   Run it 3 to 5 times with the failing request; the bug is intermittent.
4. Read the whole `structured_output` of a failing run. If keys sit at the top level
   (type, model, effort), the flattening hypothesis is right. If keys are just absent, the model is
   treating them as optional.
5. Next options, in order, each needs Fred's OK because they go beyond the prompt text:
   - add a worked JSON example of a full answer to the prompt
   - raise the Prep model (`prep_model` in `~/.claude/console/config.json`, default `haiku`)
   - loosen `SCHEMA` (drop `question` from `required`, default it to `""` in `parse_output`)
6. After a fix: update `plans/03-levers.md` Step 7 so the plan text matches `prep_prompt.md`.

## Repro script

Save outside the repo (for example in a temp folder), run from the repo root with
`py -I repro.py "the request"` or `py -I repro.py request.txt`:

```python
import json, subprocess, sys
sys.path.insert(0, r"D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE")
from console import prep, claude_cli, paths

cfg = paths.DEFAULTS
exe = [claude_cli.find_exe(cfg)]
raw = sys.argv[1]
if raw.endswith(".txt"):
    raw = open(raw, encoding="utf-8").read()
cmd = claude_cli.prep_command(exe, cfg["prep_model"], prep.SCHEMA)
out = subprocess.run(cmd, cwd=r"D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE",
                     input=prep.build_prompt(raw, []).encode(), capture_output=True, timeout=180,
                     env=claude_cli.child_env(), creationflags=claude_cli.NO_WINDOW)
d = json.loads(out.stdout.decode("utf-8", "replace"))
print(json.dumps({k: d.get(k) for k in ("is_error", "subtype", "terminal_reason", "errors",
                                        "structured_output", "num_turns", "total_cost_usd")},
                 indent=1, ensure_ascii=False))
```

Note: `claude_cli.find_exe` returns a string, so wrap it in a list for `prep_command`.

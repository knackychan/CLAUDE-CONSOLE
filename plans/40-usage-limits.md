# Plan 40: a usage limit names itself, moves the step to another provider, and Retry picks the model

> Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md). Extends plan 33 (Retry takes a note) and
> plan 35 (balancing); the routing gate is `Hub.rung_ok` (plan 5 README 3.6), which `fills.pool` already reads.
>
> Start state: `1559fc9` (branch `claude/brainstorm-task-actions`). Anchor by the quoted lines, never by line numbers.

Status: code done (786 tests OK); Fred's live check open. Decisions D1-D6 answered by Fred 2026-10-16 (section 2); departures are in PLAN.md History.

## 1. What happened (task 20261016-195841-99bd)

Step 01 (design) ran on `opencode:opencode-go/kimi-k3`. Fred answered its question, the run went on four minutes and
died on the OpenCode Go subscription's 5-hour limit. Both run streams end the same way:

```json
{"type":"error","error":{"type":"provider.quota","message":"Go usage limit exceeded","status":429,
 "response":{"body":"{...\"GoUsageLimitError\"...\"metadata\":{...\"limitName\":\"5 hour\"}}"}}}
{"type": "cc_exit", "code": 1}
```

| Id | Where | Today | Change |
|---|---|---|---|
| F1 | adapters' `summary()` (`console/harness/*.py`) | an error line is only `subtype: "error"` | `summary()` also returns `"limit": {"why", "until", "window_s"}` or `None` (Task 1) |
| F2 | `Hub._ended` (`ok = not (s["interrupted"] or s["stopped"] or s["failed"]) and subtype == "success"`) | the reason is `the run did not finish cleanly (no HANDOFF block)` | the reason is `opencode:opencode-go: Go usage limit exceeded (5 hour), until 01:39` and the provider is recorded (Task 2) |
| F3 | `tasks._retry_or_stuck` then `Hub.start_step` -> `_route_for` -> `fills.pool(refuse=...)` | the automatic retry balanced onto `opencode:opencode-go/glm-5.3`, the same subscription, and died in 4 s | `Hub.rung_ok` refuses every rung of a limited provider until its time, so the pool skips them (Task 2) |
| F4 | `tasks.fred` retry, the stuck box in `inspTask` | Retry reruns the step on the route it would get anyway | Retry takes a model (`auto` or a rung); a limited rung is not in the list (Task 3) |
| F5 | `Hub._step_files` (`notes.<k>.md` = the final message) and `tasks.step_prompt` | notes.1.md held 222 bytes: the design text and Fred's answer were not passed on | notes.<k>.md keeps the attempt's chat; the retry prompt carries it (Task 4) |
| F6 | `Hub.levers` handoff, `tasks.fred` handoff | Fred's Hand off resumed the limited session (it failed again), the task went `handed` with no note and only Mark done left | Hand off is off when the step's run hit a limit; a handed task with no note and a failed step may Retry (Task 5) |

## 2. Decisions (Fred, 2026-10-16)

- D1 Name the limit, no same-provider retry, Retry on another model, carry the partial work: all four.
- D2 Cooldown: Claude's `rate_limit_event` gives `resetsAt`, used as is. Otherwise the window named in the error
  (`5 hour`, `five_hour`, `seven_day`, `daily`, `weekly`) counted from the hit; else config `limit_cooldown_s` (3600).
- D3 Scope: the whole provider. Key `limits.provider(rung)`: `claude`, `codex` and `cmd` are one provider each;
  an OpenCode rung is `opencode:<prefix before the first />` (`opencode:opencode-go` covers kimi-k3 and glm-5.3).
- D4 Hand off: off when the step's last attempt hit a limit (the session cannot answer), with the reason
  `the run hit a usage limit: Retry on another model`. Other stuck steps keep Hand off. A `handed` task with no
  handoff note whose current step is `failed` may Retry (this recovers 99bd).
- D5 Partial work: notes.<k>.md of a failed attempt holds the attempt's chat (Claude's texts and Fred's answers, no
  tool output, the step prompt left out, tail kept at `ATTEMPT_MAX` 12000 characters); the retry prompt carries it
  inline (an OpenCode run may be denied reads outside the project) and says to check the tree for edits already made.
- D6 The limits file is `~/.claude/console/limits.json` (`{provider: {"until": epoch, "why": str}}`), pruned on read.
  No Clear button: an expired entry drops itself.

## 3. Tasks, in order

Each task: tests first, see them fail, place the code, `py -m unittest discover -s tests`, `node --check web/app.js`
for Tasks 3 and 5, commit `plan 40 task N: <what> (<n> tests OK)`.

### Task 1: detect a limit in the run stream (`console/limits.py`, the four adapters)

New `console/limits.py` (pure, plus two file helpers):

```python
"""Usage limits of the providers (plan 40): which rungs share one subscription, how long a hit keeps them out of
routing, and limits.json in the console folder. Pure but for read/save."""
import json
import re
import time
from pathlib import Path

from . import claude_cli

FILE = "limits.json"
WINDOWS = ((r"five[_ ]?hour|5[ -]?hour", 5 * 3600), (r"seven[_ ]?day|weekly|7[ -]?day", 7 * 86400),
           (r"daily|one[_ ]?day|1[ -]?day|24[ -]?hour", 86400), (r"(\d+)[ -]?hour", None))
TEXT = re.compile(r"usage limit|rate limit|hit your limit|quota|\b429\b", re.I)


def provider(rung: str) -> str:
    name, bare = claude_cli.split_rung(rung)
    if name == "opencode" and "/" in bare:
        return f"opencode:{bare.split('/', 1)[0]}"
    return name


def window_s(text: str):
    for pattern, seconds in WINDOWS:
        m = re.search(pattern, text or "", re.I)
        if m:
            return seconds if seconds else int(m.group(1)) * 3600
    return None


def until(hit: dict, now: float, default_s: int) -> float:
    if hit.get("until"):
        return float(hit["until"])
    return now + (hit.get("window_s") or default_s)


def read(folder, now: float = None) -> dict:
    now = time.time() if now is None else now
    try:
        data = json.loads((Path(folder) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and float(v.get("until") or 0) > now} \
        if isinstance(data, dict) else {}


def save(folder, data: dict) -> None:
    path = Path(folder) / FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def clock(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))
```

Each adapter's `summary()` gains a `"limit"` key (`None` when no hit), read from this turn's lines:

- `opencode.py`: the last line with `type == "error"` whose `error.type` contains `quota` or whose `error.status`
  is 429. `why` = `error.message` plus ` (<limitName>)` when the response body (a JSON string) carries
  `metadata.limitName`; `window_s = limits.window_s(limitName)`; `until` None.
- `claude.py`: the last `{"type": "rate_limit_event"}` whose `rate_limit_info.status == "rejected"` (shape read in
  this machine's run streams: `status`, `resetsAt`, `rateLimitType`): `why` = `<rateLimitType with _ as space> limit`,
  `until = resetsAt`. Also a `result` line with `is_error` true whose `result` text matches `limits.TEXT` (why = the
  text cut at 160, `window_s` from it). The `rejected` status has no sample here: the live check confirms it.
- `codex.py`: an `error` or `turn.failed` line whose message (`message`, or `error.message`) matches `limits.TEXT`;
  `why` = the message cut at 160, `window_s` from it.
- `cmd.py`: `"limit": None` (no sample; out of scope).

`runs.result_record` copies `summary["limit"]` into the record as `limit` when set.

Tests: `tests/test_harness.py` +4 (opencode: the 99bd error line gives `why "Go usage limit exceeded (5 hour)"`,
`window_s 18000`; claude: a `rejected` event gives `until` = `resetsAt`, an `allowed` one gives None; codex: an
`error` "You've hit your usage limit" gives a hit; a plain error gives None). New `tests/test_limits.py` +3
(`provider`: `opus` -> `claude`, `opencode:opencode-go/glm-5.3` -> `opencode:opencode-go`, `codex:gpt-6-astra` ->
`codex`; `window_s` on `5 hour`, `seven_day`, `nothing`; `read` drops an expired entry and survives a broken file).
`tests/fake_opencode.py`: the word `QUOTA` prints the 99bd error line (metadata `limitName: "5 hour"`) and exits 1.

### Task 2: record the hit, name it, keep the provider out of routing (`console/server.py`, `console/paths.py`)

- `console/paths.py` defaults: `"limit_cooldown_s": 3600` after `"step_timeout_s"` (not on the Models page).
- `Hub.__init__`: `self.limits = limits.read(self.folder)`.
- `Hub.limited(rung) -> str`: prune `self.limits` by time, then `""` or
  `f"{provider}: {why}, until {limits.clock(until)}"`.
- `Hub.rung_ok`: first line after the docstring: `hit = self.limited(rung) if isinstance(rung, str) else ""`,
  `if hit: return hit`. This one gate reaches the balance pool, a pick, a pin, `start_step`'s check, the plan 36
  routes and GET /api/config `tiers[].why` (so the window's model lists drop the rung).
- `Hub.final_message`: split out `Hub._turn_summary(sid)` (the meta, the lines, `summary`), so `_ended` reads
  `summary["limit"]` without parsing twice; `final_message` keeps its return value for its other callers.
- `Hub._ended`, after `text, subtype = self.final_message(sid)` and before the question check: when the summary
  has a limit, `prov = limits.provider(cs["model"])`, `self.limits[prov] = {"until": limits.until(hit, now,
  self.cfg["limit_cooldown_s"]), "why": hit["why"]}`, `limits.save(self.folder, self.limits)` (an OSError is
  ignored: the entry still holds in memory), `cs["limit"] = prov`, and the run is not `ok`. The reason passed as
  `cap=` is `self.limited(cs["model"])`, so the chain and the stuck why read
  `opencode:opencode-go: Go usage limit exceeded (5 hour), until 01:39`. A question in a limited turn is ignored.
- `Hub.start_step`: `s.pop("limit", None)` with the other pops; a `manual_route` whose rung `self.limited` refuses
  is dropped for `_route_for` (note `manual route refused: <why> -> auto`), so an automatic retry of a plan 36 step
  moves too.

Tests (`tests/test_server.py` +4): a step picked on `opencode:...` with `QUOTA` in its goal: attempt 1's why names
the limit, attempt 2 ran on a claude rung and the task is done, `limits.json` holds `opencode:opencode-go`;
`rung_ok("opencode:opencode-go/glm-5.3")` names it while `kimi-k3` is limited; an expired entry lets it run again
(`until` in the past); GET /api/config `tiers` carries the why. Use the existing fake harness setup of
`test_step_timeout_reaches_the_retry_reason`.

### Task 3: Retry takes a model (`console/tasks.py`, `console/server.py`, `web/app.js`)

- `POST /api/task/retry {task, note, model}`: `model` optional; `""` means auto; any other value must pass
  `claude_cli.known_model(self.cfg, model)` (else 400 `unknown model`). `Hub.task_lever(task_id, lever, note, model)`
  passes it on for Retry only.
- `tasks.fred(..., model=None)` retry branch, inside `if s and s["state"] != "done":`: when `model is not None`,
  `s["pick"] = model`, `s.pop("manual_route", None)`, and the chain line reads `retry by Fred on <model or auto>`
  (then `: <note>` as today).
- `web/app.js`: `retryForm(t, cur, tid)` returns the note textarea, a `<select class="in" id="b-retrymodel">` of
  `modelOptions(cur.pick || "", true, cur.kind)` with the label `Model`, and the Retry button; the stuck box uses it
  in place of today's `note` + button. `taskAct` sends `model: $("b-retrymodel").value` with the note when the
  select is there. A limited rung is not listed (its `why` is set), so a limited pick shows `auto`.

Tests: `tests/test_tasks.py` +1 (retry with model sets `pick`, drops `manual_route`, names it on the chain);
`tests/test_server.py` +1 (400 on an unknown model; a stuck task retried on `sonnet` runs its step on sonnet);
`tests/test_web.py` +1 (the stuck box renders the select with `auto` and no limited rung).

### Task 4: the retry carries the failed attempt's chat (`console/tasks.py`, `console/server.py`)

- `tasks.ATTEMPT_MAX = 12000`; `tasks.attempt_text(items) -> str`: from an adapter's `chat()` items, skip the first
  `you` item (the step prompt), keep `claude` texts as `**Claude:** ...` and later `you` items as `**<you>:** ...`,
  join with blank lines, and keep the last `ATTEMPT_MAX` characters (cut at a line start, with `[earlier part cut]`).
- `Hub._step_files`, the `else` branch (an attempt that ends in a retry or stuck): write
  `tasks.attempt_text(runs.chat(stream, cwd, limit=10**6, harness=name))` of the whole session stream (every turn of the
  attempt) instead of `text`; fall back to `text` when it is empty.
- `tasks.step_prompt(..., tried="")`: when set, the retry paragraph adds: `Your earlier attempt wrote this before it
  stopped (its chat, newest last). Keep what still holds, and check the working tree for edits it already made
  before you redo them:` then the text in a fenced block. `Hub.start_step` reads the previous attempt's
  notes.<k>.md when `retry` is set and passes it; `received.md` lists `notes.<k>.md (the earlier attempt's chat)`.

Tests: `tests/test_tasks.py` +2 (`attempt_text` skips the prompt, labels both sides, cuts to the tail;
`step_prompt` with `tried` puts it in the retry paragraph); `tests/test_server.py` +1 (after a QUOTA attempt,
notes.1.md holds the fake reply text and the retry's prompt file contains it).

### Task 5: Hand off off after a limit, Retry from a handed task (`console/server.py`, `console/tasks.py`, `web/app.js`)

- `Hub.levers`, after the plan 36 / working-chain blocks: when `task` and `cs` and `cs["session"] == session_id`
  and `cs.get("limit")`: `out["handoff"] = base or "the run hit a usage limit: Retry on another model"`.
- `Hub.task_levers` retry and `tasks.fred` retry: also allowed when `state == "handed"`, `not
  task.get("handoff_note")` and the current step is `failed`. `fred` then moves the task to `running`, owner
  `service`, as for stuck (the retry_why is the last attempt's why).
- `web/app.js` `handedBox`: when `d.levers.retry === ""`, the box shows `retryForm(...)` under its text, and the
  no-note line reads `No handoff note: the step's run failed. Retry it on another model.`

Tests: `tests/test_server.py` +2 (Hand off off on a limited step with the reason; a handed task with no note and a
failed step: Retry 200 and the step runs); `tests/test_web.py` +1 (handedBox shows Retry when the lever allows it).

### Task 6: live check (Fred) and records

1. Restart the service when no task runs. Task 99bd shows `handed` with Retry and the model select: pick a claude
   rung (opus), Retry. The design step reruns with notes.1.md / notes.2.md in its prompt: the step's `received.md`
   names them. (notes.1.md of 99bd was written before this plan, so it holds only the final message: Fred's answer
   to the question is in the step's chat; paste it into the Retry note.)
2. While OpenCode Go is still limited: GET /api/config shows the opencode-go rungs with a `why`; a new design task
   balances away from them.
3. Claude and Codex limits: confirm the `rejected` `rate_limit_event` and Codex's error text the first time one is
   hit (the Usage page shows the run); correct the adapters' parsing then.
4. PLAN.md row 40 and a History line; this file's Status.

## 4. Not in this plan

A Clear limit button (D6), Command Code detection, reading a provider's remaining quota before a run (plan 35
measures load, not quotas), resuming the same session on another model (a session belongs to one CLI).

# Task 2: the needs items, their keys, the always list, sync and the queue order

> Contract: [README.md](README.md) 3.3, 3.4, 3.6 (sync), 3.8; golden tables 4.1 and 4.2. Decision D10.
> Reads the snapshot exactly as `Hub.snapshot` counts it (`console/server.py:575-580`); never rebuilds a group.

**Files**
- Modify: `console/superagent.py` (append this task's section; nothing above it changes)
- Modify: `tests/test_superagent.py` (`ItemsTest`, `SyncTest`, `QueueTest`)

Commit boundary: `feat: super agent items, always list and queue order (plan 58 T2)`.

## 2.1 `console/superagent.py`, part 2 (append)

```python
# -- items and the queue (Task 2) ---------------------------------------------------------------------------

def _event(values) -> str:
    """8 hex of the SHA-1 of a JSON list: the part of a key that changes with the state that raised the item."""
    return hashlib.sha1(json.dumps(values, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:8]


def always_reason(task: dict) -> str:
    """README 3.4: why an item of this task reaches the user whatever a pass says, the first that holds; "" when a
    pass may rank it, batch it or put it later."""
    why, state = str(task.get("why") or ""), task.get("state")
    sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
    pending = sup.get("pending") if isinstance(sup.get("pending"), dict) else {}
    decision = task.get("decision") if isinstance(task.get("decision"), dict) else {}
    cs = tasks.current_step(task) if task.get("current") else None
    if state == "waiting" and why == "confirm Fable":
        return "Fable confirm"
    if state == "stuck" and why.startswith("verify failed twice"):
        return "second verify FAIL"
    if why.startswith("supervisor work cap reached"):
        return "work cap"
    if pending.get("error") == "supervisor spend cap reached":
        return "spend cap"
    if tasks.held(task):
        return "pace hold"
    if cs and cs.get("limit"):
        return "usage limit"
    if pending.get("status") == "uncertain" or decision.get("taken") == "uncertain" or any(
            isinstance(m, dict) and m.get("status") == "uncertain" for m in task.get("messages") or []):
        return "uncertain dispatch"
    if state == "waiting" and why.startswith("asks: ") and not decision.get("taken") and not decision.get("default"):
        return "decision without a default"  # D10: a plain STOP question has no default either
    return ""


def task_kind(row: dict, task: dict) -> str:
    """The kind of a task's item, from its list row (server.task_row) and task.json, the first that holds:
    suggestion, decision (a question with options), question, hand_off, handed, failed_twice, stuck, hold (any other
    wait: a plan, Fable, a pace, a cap), chat (a chat task's turn), else the task state (README 3.3)."""
    state = task.get("state")
    if (row.get("supervisor") or {}).get("attention"):
        return "suggestion"
    if row.get("asks"):
        return "decision" if state == "waiting" and isinstance(task.get("decision"), dict) else "question"
    if row.get("hand_off"):
        return "hand_off"
    if state == "handed":
        return "handed"
    if state == "stuck":
        return "failed_twice" if str(task.get("why") or "").startswith("verify failed twice") else "stuck"
    if state == "waiting":
        return "hold"
    return "chat" if task.get("chat") else str(state or "")


def items(snap: dict, by_id: dict) -> list:
    """README 3.3, the needs set, from a Hub snapshot (pure): every task row in group needs whose task is in `by_id`
    (Hub.tasks, never changed), then every session row in group needs with neither task nor chat_task (a task's
    session counts as its task, as the snapshot's counts do). The key is "<type>:<id>:<event>"; the event changes
    when the state that raised the item changes, never with time, cost or `updated`."""
    out = []
    for row in snap.get("tasks") or []:
        task = by_id.get(row.get("id"))
        if row.get("group") != "needs" or not isinstance(task, dict):
            continue
        kind = task_kind(row, task)
        sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
        pending = sup.get("pending") if isinstance(sup.get("pending"), dict) else {}
        decision = task.get("decision") if isinstance(task.get("decision"), dict) else {}
        cs = tasks.current_step(task) if task.get("current") else None
        event = _event([kind, task.get("state"), task.get("why") or "", task.get("current") or 0,
                        len(tasks.attempts(cs)) if cs else 0, row.get("asks") or "", row.get("hand_off") or "",
                        pending.get("wake") if kind == "suggestion" else 0, decision.get("taken") or ""])
        out.append({"key": f"task:{task['id']}:{event}", "type": "task", "id": task["id"], "kind": kind,
                    "always": always_reason(task), "project": row.get("project") or "",
                    "project_dir": row.get("project_dir") or "", "title": row.get("title") or "",
                    "label": row.get("label") or task["id"]})
    for row in snap.get("sessions") or []:
        if row.get("group") != "needs" or row.get("task") or row.get("chat_task"):
            continue
        kind = (row["state"] if row.get("state") in NEEDS_YOU else "context" if row.get("ctx_tone") == "red"
                else "handed")
        event = _event([kind, row.get("state"), row.get("turn_ts"), row.get("handoff_by") or ""])
        out.append({"key": f"session:{row['id']}:{event}", "type": "session", "id": row["id"], "kind": kind,
                    "always": "", "project": row.get("project") or "", "project_dir": row.get("project_dir") or "",
                    "title": row.get("title") or "", "label": str(row["id"])[:8]})
    return out


def sync(state: dict, live: list, now: float) -> tuple:
    """Bring state.json's item memory to the live set (README 3.6): a new key is seen `now`; a key that left is
    forgotten with its annotation, and so is an annotation whose key is no longer seen; a later annotation whose until
    has passed is marked back, once. Returns (new keys, back keys, changed). Mutates `state`."""
    keys = {i["key"] for i in live}
    seen, ann = state["seen"], state["ann"]
    new = [i["key"] for i in live if i["key"] not in seen]
    for key in new:
        seen[key] = float(now)
    gone = [k for k in seen if k not in keys]
    for key in gone:
        del seen[key]
    stale = [k for k in ann if k not in keys]
    for key in stale:
        del ann[key]
    back = []
    for key, a in ann.items():
        until = a.get("until")
        if a.get("do") == "later" and _num(until) and until <= now and not a.get("back"):
            a["back"] = True
            back.append(key)
    return new, back, bool(new or gone or stale or back)


def _when(ts) -> str:
    """A timestamp as the local YYYY-MM-DDTHH:MM a pass writes; "" for none."""
    return time.strftime("%Y-%m-%dT%H:%M", time.localtime(ts)) if _num(ts) else ""


def last_at(state: dict) -> float:
    """When the last pass was claimed; 0.0 for no pass, or for a hand-edited `last` whose time is not a number (the
    queue and the sweep read it, and neither may raise)."""
    last = state.get("last")
    at = last.get("at") if isinstance(last, dict) else None
    return float(at) if _num(at) else 0.0


def queue(items_: list, state: dict, now: float, ranked: bool) -> dict:
    """README 3.8 as cards: {"queue": [{"batch", "rank", "items"}], "later": [item]}; every item comes back with
    age_s, new, do, rank, say, why, batch and until added. Ranked: always items first, oldest first; then annotated
    items by rank (ties oldest first); then unannotated items first seen before the last pass, oldest first; then
    newer ones, oldest first, marked new. A later item that is not always and whose until has not passed leaves for
    `later`. A batch is one card where its best-placed member sits; an always item is forward and never in a batch.
    Unranked: always items first, then the rest, both oldest first, no annotation field set. Pure."""
    seen = state.get("seen") or {}
    ann = (state.get("ann") or {}) if ranked else {}
    at = last_at(state)

    def first(row):
        return seen.get(row["key"], now), row["key"]

    rows, later = [], []
    for item in items_:
        a = ann.get(item["key"]) or {}
        until = a.get("until")
        rank = a.get("rank")
        row = dict(item, age_s=max(0, int(now - seen.get(item["key"], now))), new=False, do="", rank=None, say="",
                   why="", batch="", until="")
        if a:
            row.update(do="forward" if item["always"] else str(a.get("do") or ""),
                       rank=rank if isinstance(rank, int) and not isinstance(rank, bool) else None,
                       say=a["say"] if isinstance(a.get("say"), str) else "",
                       why=a["why"] if isinstance(a.get("why"), str) else "",
                       batch="" if item["always"] or not isinstance(a.get("batch"), str) else a["batch"],
                       until=_when(until))
        elif ranked and seen.get(item["key"], now) > at:
            row["new"] = True
        if row["do"] == "later" and not (_num(until) and until <= now):
            later.append(row)
        else:
            rows.append(row)

    def place(row):
        if row["always"]:
            return (0, 0) + first(row)
        if row["rank"] is not None:
            return (1, row["rank"]) + first(row)
        return (3 if row["new"] else 2, 0) + first(row)

    rows.sort(key=place)
    cards, batches = [], {}
    for row in rows:
        if row["batch"] and row["batch"] in batches:
            batches[row["batch"]]["items"].append(row)
            continue
        card = {"batch": row["batch"], "rank": row["rank"], "items": [row]}
        if row["batch"]:
            batches[row["batch"]] = card
        cards.append(card)
    later.sort(key=lambda row: (row["until"] or "9999",) + first(row))
    return {"queue": cards, "later": later}
```

## 2.2 Tests first (red before the code)

Fixture helpers at the top of `tests/test_superagent.py` (shared with Task 3):

```python
T0 = 1_800_000_000.0
DECISION = {"q": "Which file?", "options": [{"key": "1", "text": "style.css"}, {"key": "2", "text": "app.js"}],
            "default": "1", "step": 1, "asked": T0}


def make_task(tid, state, why="", **extra):
    """One code step (plus the verify plan_steps adds), current 1, done once with one attempt."""
    t = tasks.new_task("D:/proj", "proj", f"Task {tid[-4:]}", "goal",
                       tasks.plan_steps([{"kind": "code", "goal": "edit"}], 6), "normal", {}, "", "auto", T0, id_=tid)
    t["steps"][0].update(state="done", started=T0, ended=T0 + 60, dir="01-code", model="sonnet", effort="medium",
                         attempts=[{"session": "", "cost": 0.1, "started": T0, "ended": T0 + 60, "why": "",
                                    "final": True}])
    t.update(state=state, why=why, current=1, **extra)
    return t


def session_row(sid, group="needs", state="failed", task="", tone="green"):
    return {"id": sid, "group": group, "state": state, "task": task, "chat_task": "", "turn_ts": T0,
            "ctx_tone": tone, "handoff_by": "", "project": "proj", "project_dir": "D:/proj", "title": "a chat",
            "source": "vscode", "text": "Failed", "stop_question": ""}


def snap_of(*task_list, sessions=()):
    return {"tasks": [server.task_row(t) for t in task_list], "sessions": list(sessions)}
```

Task ids are `2027011N-080000-a0NN` (valid `tasks.safe_id` ids). A pending card is set as
`t["supervisor"] = supervisor.initial(paths.DEFAULTS, "D:/proj", T0)` then `t["supervisor"]["pending"] = {"wake": 3,
"status": "suggest", "decision": {"decision": "finish", "reason": "all checks pass"}, "error": ""}`.

`ItemsTest`
- `test_golden_items`: README table 4.1, one subTest per row, asserting the item's presence, `kind` and `always`
  exactly (rows 15, 16, 19 and 20 give no item); `type`, `id`, `project`, `title` and `label` (`tasks.label(id)` for
  a task, the first 8 characters for a session) come from the row.
- `test_keys_follow_the_state_never_time_or_cost`: row 1 built twice gives equal keys; changing `updated` or the step
  attempt's `cost` keeps the key; changing `why`, appending a second attempt to the current step, or moving row 10's
  pending card to wake 4 each change it; every key matches `^(task|session):[^:]+:[0-9a-f]{8}$`.
- `test_tasks_come_first_and_a_task_session_counts_once`: a snapshot with a session row whose `task` is set and a
  needs task gives the task item only; with a loose needs session as well, the task item comes before the session item.
- `test_items_never_change_their_inputs`: `copy.deepcopy` of the snapshot and of `by_id` before, equal after.

`SyncTest`
- `test_first_seen_forget_and_back_once`: live `[a, b]` at T0 gives new `[a, b]`, `seen` T0 for both, changed True;
  the same live set at T0+10 gives `([], [], False)`; with `ann` holding `a` (later, until T0+5) and `zz` (a key not
  live), live `[a]` at T0+10 gives new `[]`, back `[a]`, changed True, `b` and `zz` gone from `seen` and `ann`; once
  more gives back `[]`.

`QueueTest`
- `test_golden_order`: README table 4.2, the three cases, asserting the card order by item names, the batch card
  `[D, E]` with `batch` `acc` and `rank` 2, A's `do` `forward` and its say kept, F's `new` True, `later` `[H]` (case
  1) and empty (cases 2 and 3), and in the unranked case every `say` `""`, `rank` None, `new` False.
- `test_age_and_until_fields`: `age_s` is `now - seen` in whole seconds (0 for an item not yet seen); H's `until` is
  `time.strftime("%Y-%m-%dT%H:%M", time.localtime(T0 + 600))`.
- `test_hand_edited_annotations_are_ignored_safely`: an annotation with `rank` `"x"`, `say` 5 and `batch` `["a"]`
  sorts as unranked (no TypeError), with `say` and `batch` `""`; a `last` of `{"at": "x"}` reads as `last_at` 0.0, so
  every unannotated item is new.
- `test_queue_never_changes_state`: `copy.deepcopy(state)` before, equal after.

## 2.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent`: red for the missing functions.
- [ ] 2. Append 2.1 to `console/superagent.py`. Focused tests green.
- [ ] 3. Full suite green (report the count). Commit with the message above.

# Task 3: whole-task handoff — digest, haiku pass, Save and Create follow-up

> Contract: [README.md](README.md) 3.2, 3.3, 3.6. NAVIGATION.md "Hand off task". Decision 1 (haiku),
> decision 2 (`handed`), decision 6 (Save + Create).

**Files**
- Add: `console/handoff.py`
- Modify: `console/compact.py` (`_ask` takes an optional `model`, one line)
- Modify: `console/server.py` (`Hub.handoff_available`, `Hub.task_handoff`, `Handler._task_handoff`, the two
  routes, `GET /api/task` gains the handoff fields, `step_prompt`'s inherited-handoff branch)
- Modify: `console/paths.py` (the four `handoff_*` DEFAULTS)
- Modify: `web/app.js` (`handoffForm`, `taskHandoff`, the More entry, `handoffDraft`), `web/style.css`
- Modify: `tests/test_tasks.py`, `tests/test_server.py` (or its task test class), `tests/test_web.py`

## 3.1 `console/handoff.py`

Exactly the README 3.2 surface: `HANDOFF_SCHEMA`, `digest`, `build_prompt`, `render`, `check`, `fallback`,
`run`. `run(cfg, exe, home, task, instructions)`:

- `digest = digest(home, task, instructions)`; `prompt = build_prompt(task, instructions, digest)`.
- when `cfg["handoff_on"]` and an exe exists: one `compact._ask(cfg, exe, task["project_dir"], prompt,
  HANDOFF_SCHEMA, {"model": cfg["handoff_model"]})` (the pass runs in the project folder, as the brief does),
  then `check(render(fields, ...), cfg["handoff_max_words"])`; on success return
  `{"text", "cost", "words", "model", "fallback": ""}`.
- every failure (no exe, non-zero, parse miss, schema miss, over words, timeout) returns
  `{"text": fallback(...), "cost": 0, "words": words(text), "model": "", "fallback": why}`.
- `redact.mask` the returned text (as the brief does). Never raises.

`compact._ask(cfg, exe, project_dir, prompt, schema=BRIEF_SCHEMA, info=None)` gains `model: str = ""` (default
`cfg["brief_model"]`); the `brief_command(exe, model, schema)` call uses it. No other compact change.

## 3.2 The digest and the prompt

`digest` reads only saved files through `tasks.read_note` / `read_brief` / `read_facts` /
`read_step_file(..., "verdict.md")` / `open_questions` / `read_chain` and `plan.read` + `plan.read_part`. It
names every step `NN (kind, state)`; a step with no note and no reply is written "No saved result. Do not
assume this step completed." Failed attempts carry their `why`. The prompt's fixed text (under 1,000 tokens)
says: summarize honestly, cite step numbers, mark missing results unavailable, never claim verification
passed when it did not, and put the concrete next work in Next.

## 3.3 Server: availability and the endpoint

`Hub.handoff_available(task) -> str` (`""` = allowed):

- `tasks.pending_messages(task)` -> "Resolve pending guidance before handing off this task."
- any live step session (`self.runs.is_live(sid)` for `sid in tasks.sessions_of(task)`) -> "Wait for the
  current run to finish, or stop it first."
- `task.get("briefing") or task["id"] in self.briefing` -> "The step summary is still being saved."
- `task.get("handoff_to")` -> "This task already has a follow-up task."

`Hub.task_handoff(body, preview=False)` (under `self.tlock`, mirroring the interrupted attempt but with the
haiku pass):

- Validate: `tasks.safe_id(tid)`, `note` a string at most `tasks.STEP_GOAL_MAX`; on non-preview require
  `create` bool and `request_id` matching 32 hex.
- `preview`: run `handoff.run`; compute `revision = sha256(task + text + documents)`; return
  `{"task", "text", "revision", "cost", "model", "fallback"}`.
- Save (`create=False`): require the body's `revision` to match (409 "The task changed. Refresh the handoff
  preview before saving." otherwise); `paths.write_text_atomic(root / "task-handoff.md", text)`; return
  `{"task", "file"}`. No state change.
- Create (`create=True`): idempotent on `request_id` — a stable follow-up id
  `hashlib.sha256(f"{tid}:{request}".encode()).hexdigest()[:20]`; when a task with that id exists with the same
  `handoff_request`, return it (200). Otherwise validate `revision`, build the follow-up (3.4), write its
  files, save it, set the source `handed` + `handoff_to` + `handoff_note`, log a chain line
  `follow-up task: <id>`, `poll_once`, return `{"task": <follow-up id>, "source": tid}`. A `409` on any
  conflict re-checks the source under the lock.
- Any `OSError` returns 409 with a retryable message; the source stays usable.

Routes: `POST /api/task/handoff/preview` and `POST /api/task/handoff` (the `_task_handoff` handler), registered
with the other `/api/task/*` routes.

`GET /api/task` (`_task`) gains `"handoff_available": self.hub.handoff_available(task)`,
`"handoff_document": <task-handoff.md text or "">`, `"handoff_context": <inherited-handoff.md text or "">`
(through a small `_handoff_text(task, name)` reader, `OSError` -> `""`).

`step_prompt` (in `console/server.py`, the existing block that assembles `got`): when `n == 1 and
task.get("handoff_from")`, read `inherited-handoff.md`; on `OSError` raise `runs.RunError("Inherited handoff is
unavailable; restore it before starting this task")`; append the note line and `inherited-handoff.md` to `got`.

## 3.4 The follow-up task

- `goal = note.strip() or "Take over the remaining work using the inherited handoff. Check existing edits
  before repeating work."`; `steps = tasks.plan_steps([{"kind": "code", "goal": goal}], 1)`.
- `tasks.new_task(task["project_dir"], task["project"], "Continue: " + task["title"][:70], task.get("goal", ""),
  steps, task["type"], task["demand"], "", task["effort"], time.time(), id_=follow_up_id)`; then
  `new.update(owner="fred", progression="manual", handoff_from=tid, handoff_request={...})`.
- Write `dest / "inherited-handoff.md"` (the summary) and `dest / "handoff-source"/<name>` for each evidence
  copy (prompt.md, plan.md, plan parts, and each step's handoff/notes/facts/verdict) via
  `paths.write_text_atomic`; `tasks.save(self.folder, new)` last so the task becomes visible only once durable.

## 3.5 Frontend: More > Hand off task

- `taskButtons` puts `Hand off task` in More when `d.handoff_available === ""` (`data-tact="handofftask"`).
- `handoffDraft[tid] = {note, request, preview, saved, busy, open, error}`; `taskHandoff(action, tid)` handles
  `handofftask` (open the form), `handoffpreview` (POST preview, store `preview` + a fresh `uuid()` request),
  `handoffsave` (POST create=false, mark `saved`), `handoffcreate` (POST create=true, refresh `snap`, open the
  follow-up task), `handoffcancel` (close). A changed note invalidates `preview` until refreshed.
- `handoffForm(t)`: the note textarea (`id=b-handoff-note`, `data-tid`), the review fold (the preview text),
  the error/saved lines, and the buttons (Preview/Refresh, then Save document + Create follow-up task +
  Cancel). The draft survives snapshots (the `input` listener on `b-handoff-note`, `setHtml` preserves
  `<details data-key>` open state).
- `.handoff-form` and its children in `web/style.css`, following the existing `.askbox`/`.lr` tokens; the More
  `.action-list` already exists from Task 2.

## Steps

- [ ] 1. `console/handoff.py` + `compact._ask` model param + `paths.py` keys. Unit-test `digest`, `render`,
      `check`, `fallback`, and `run` with a fake exe (assert the haiku path and the fallback path). Test first.
- [ ] 2. Server: `handoff_available`, `task_handoff` (preview/save/create), routes, `GET /api/task` fields,
      `step_prompt` branch. Server tests for each `handoff_available` reason, the revision 409, idempotent
      create, and the `handed`/`handoff_to` transition.
- [ ] 3. Frontend: More entry, `handoffForm`, `taskHandoff`, CSS. `node --check`.
- [ ] 4. Tests below; whole suite green. Commit: `feat: whole-task handoff with a haiku summary and a linked follow-up (plan 44 nav T3)`.

## Tests

- `tests/test_tasks.py` (or `test_handoff.py`): `handoff.digest` includes every step and marks a missing note;
  `handoff.render` emits the six headings in order; `handoff.check` rejects a missing heading and an over-long
  block; `handoff.run` returns the fallback on a bad exe and the haiku text on a good one (fake claude).
- server: `handoff_available` reasons; preview 200 with a revision; save writes `task-handoff.md` and changes
  nothing; create makes one follow-up on repeated requests (same id), sets source `handed` + `handoff_to`, and
  leaves the source history; a changed task after preview -> 409.
- `tests/test_web.py`: `taskButtons` shows `Hand off task` only when `handoff_available === ""`; `handoffForm`
  shows Save + Create only after a preview; the note change invalidates the preview.

## Drift guards

- The haiku pass reads the digest only, never a transcript or the live context; the service writes every file.
- Save and Create both start nothing; Create is idempotent on the request id.
- A handoff never marks the source done; `handed` with `handoff_to` is distinct from the session-level
  `handed` (no `handoff_to`) — `taskShown` / `handedBox` / `startNext` keep both working.
- No path is written outside `~/.claude/console/tasks/` (the plan 28 mirror stays the one exception).

# Task 3: One source from launch to Handoff tab

Plan only. Future files: `console/server.py`, `console/runs.py`, `console/tasks.py`, `web/app.js`, their tests
and fake provider fixtures. Read Task 1's signatures and Task 2's adapter seam. F1/F3 edits are concurrent:
use the function anchors here, not the historical line numbers. No route, retry-count or supervisor rewrite.

## 1. Reserve before a launch; never recycle an ended turn's output

RunManager.start gains `handoff: dict = None`. This is a service-only argument with exact keys `task`, `step` and
`output`; it is not an HTTP option. The task path is relative to RunManager.folder. Do not infer the protocol
from whether any file happens to exist. Fresh worker starts use it; legacy, chat and tool-free passes do not.

Final Hub reservation helper (called under `tlock`):

```python
    def _handoff_launch(self, task: dict, step: dict) -> dict:
        rel = tasks.prepare_output(self.folder, task, step)
        self._commit(task)
        return {"task": task["id"], "step": step["n"], "output": rel}
```

Before `prepare_output`, check the resolved task root stays under `<home>/tasks` and has no linked/junction
components below that resolved tasks root (Task 1). This check belongs in prepare_output's implementation,
so all three callers below get it. Directory creation or reservation save failure stops before spawn, marks a
storage error through existing error handling, and never falls through into a legacy launch.

| Launch path | Exact integration |
|---|---|
| `Hub.start_step` | After route/hold/Fable/attachment/pending-guidance gates, before building the final prompt and spawning, reserve for `kind in FILE_KINDS`. Add the absolute path to `tasks.step_prompt(..., handoff_path=...)`. Pass `handoff=reservation` to `runs.start`. After `tasks.start_step`, copy output identity into the new attempt and commit normally. |
| `_guidance_tick` (find by `Apply this guidance to the same step before progressing`) | Read the old turn's handoff/gap before reserving the next one. A file-protocol current step gets a fresh reservation inside the dispatch callback, immediately before its start; a legacy step remains legacy. Append the new output instruction after the guidance. Carry the task/step association on a fork exactly as today. A saved `dispatching` message remains non-replayable on uncertainty. |
| `Hub._pull`, continue/STOP answer/decision default/Resume | Locate the owning non-chat current step by session, even when the local variable `task` is None because the task is waiting rather than stopped. Preserve the existing lever checks. If its **current run metadata** has handoff_output, reserve a fresh one and pass it; absence means legacy. Only Continue inherits this protocol, never standalone Verify/Handoff/Escalate or `/session-handoff`. |

Do not reserve on each polling tick, a refused action, a pending preview, a model de-escalation setting, or a
GET. Legacy Continue stays legacy for that in-flight attempt; fresh Retry re-enters `start_step` and upgrades.
The newer path is authoritative immediately after reservation. If spawn fails, an older result/file may not
complete the reserved turn. A genuine uncertain launch stays stuck for inspection; do not auto-replay it.

Final RunManager integration next to `common = dict(...)`:

```python
        handoff = handoff or {}
        if handoff:
            if (set(handoff) != {"task", "step", "output"} or not tasks.safe_id(handoff["task"])
                    or type(handoff["step"]) is not int):
                raise RunError("invalid handoff reservation")
            task = tasks.load(self.folder, handoff["task"])
            step = next((s for s in task["steps"] if s["n"] == handoff["step"]), None) if task else None
            if not step or step.get("handoff_output") != handoff["output"]:
                raise RunError("handoff reservation is no longer current")
            target = tasks.output_path(self.folder, task, step, handoff["output"])
            if target.exists():
                raise RunError("handoff output already exists before launch")
            common["handoff_path"] = str(target.absolute())
            if harness == "codex" and read_only:
                (target.parent / "tmp").mkdir(exist_ok=False)
```

Catch `ValueError`/`OSError` from path validation as RunError. Set `read_only = kind in tasks.SOURCE_READ_ONLY`
for new file workers in Hub.start_step; inherited read_only continues on resume. Also refuse a resume of a file-protocol task turn
without a fresh `handoff` argument when it is a step Continue, so a missed caller cannot reuse its old file.
Standalone handoff/verify forks are exempt and must not inherit the candidate path. Preserve inherited limits,
read_only, adapter identity, STOP_FOOTER, prompt file and shell PATH behavior.

The run metadata written for a file turn includes:

```python
        output_meta = ({"task": handoff["task"], "step": handoff["step"], "handoff_output": handoff["output"]}
                       if handoff else {})
```

Merge `output_meta` into the existing `_save_meta` dict. Never copy these keys automatically from `old`.
The task reservation is durable **before** `_spawn`; RunManager's ordinary process metadata save remains after
spawn. A crash between these saves is an uncertain launch, not evidence of a clean end. Existing process/job
reconciliation must not advance it from a complete-looking file alone.

After each successful new start/resume, update the current attempt's `handoff_output`. Keep earlier generation
directories for diagnosis. A chain retry appends its normal attempt record; a Continue does not add a fake
chain attempt or reset retry caps.

## 2. Select once at end and publish before success

In `_ended`, keep the run-live/meta-ended checks, error subtype/limit accounting and question-first handling.
Use the current turn summary, never last-good output. Verify `meta.handoff_output` equals the step's reservation
before taking an action for a file turn. A mismatch is an uncertain/stale completion, not a missing-note retry.

Replace the parser/manual exception pair with:

```python
        block, block_error = tasks.step_handoff(self.folder, task, cs, text, meta)
        if not cs.get("handoff_output") and manual and tasks.parse_handoff(text) is None:
            block_error = ""  # legacy manual steps keep their original optional-note behavior
```

Use this same `block` for `plan.gap`, lesson extraction, `replan.ask_line`, verdict Findings and publication.
The final reply remains the source of PLAN/SUBPLAN, VERDICT, STOP and DECISION. Do not move those parsers into
the file reader or make six headings in a reply an alternative acceptance path.

For a file turn, design's PLAN check must no longer erase a handoff error through `manual or not block_error`:

```python
        legacy_manual = manual and not cs.get("handoff_output")
        if cs["kind"] == "design" and ok and (legacy_manual or not block_error):
            # Keep the existing found/room/plan.check body here unchanged.
```

Before mutating chain state, compute its transition on a copy. This is the replacement around the existing
`tasks.on_step_ended(...)` call, with the same arguments and decision values already computed above it:

```python
        candidate = copy.deepcopy(task)
        action, lines = tasks.on_step_ended(
            candidate, ok=ok, block_error=block_error, verdict=verdict,
            verdict_detail=detail if verdict else "", question="", now=now,
            cap=self.limited(cs["model"]) or tasks.cap_reason(subtype, meta.get("limits")))
        proposed = tasks.step(candidate, cs["n"])
        accepted = action in ("next", "fix", "done", "manual")
        if accepted and block:
            try:
                if cs.get("handoff_output") and len(block.encode("utf-8")) > tasks.NOTE_MAX:
                    raise ValueError("handoff.md is over 20 KB after masking")
                tasks.write_note(self.folder, candidate, proposed, block)
            except (OSError, ValueError) as exc:
                why = "cannot save checked handoff.md: " + redact.clip(str(exc), 160)
                cs["handoff_error"] = why
                held_lines = []
                tasks._task_to(task, "stuck", why, now, cs, held_lines)
                task["owner"] = "fred"
                self._commit(task, held_lines)
                return "stuck"
            proposed["handoff_source"] = "file" if cs.get("handoff_output") else "reply"
        task.clear()
        task.update(candidate)
        cs = tasks.step(task, proposed["n"])
```

`server.py` already uses copy; retain/import it as needed. Continue with existing plan saving/rebuild/hold,
facts, cost sync, brief preparation and supervisor gates on this accepted task. The later duplicate
`if ended and block: tasks.write_note(...)` is removed. This copy covers only the transition before its durable
publication; do not duplicate `_facts` or a model pass. `accepted` includes a design which becomes a plan hold
later, since its pre-hold action was next/done/manual. Do not publish a failed verify's invalid handoff.

Before returning from a closed file turn, seal its output once (Task 1), including question, failure and
interruption paths. Save the original rejection reason in `cs.handoff_error` and attempt metadata before any
diagnostic rewrite. Sealing errors hold the task with an explicit storage error and never serve raw content.
A persisted `handoff_sealed` equal to that generation makes this idempotent after restart; it is cleared by
prepare_output. Successful canonical publication and sealing occur before the successful task commit. GET
does no sealing. Failed artifact diagnostics are never a replacement for the original acceptance result.

If the canonical write succeeds but the task save fails, no success is durable and no next step starts.
On restart reconcile the ended run and the recorded reservation; publication is idempotent and can be retried
locally. Do not launch the model again for a storage failure. If the save outcome cannot be determined, use
the existing recovery/uncertainty handling and keep Fred in control.

## 3. All five parse_handoff sites and both synthetic replies

1. **Guidance Plan gap (~1517).**

   ```python
        reply = self.final_message(sid)[0]
        handoff, handoff_error = tasks.step_handoff(self.folder, task, cs, reply, meta)
        gap = plan.gap(handoff or "") if task.get("plan") and not handoff_error else ""
   ```

   Do this before a new output reservation. Question/decision detection and queued message persistence remain.
   A missing handoff does not prevent a model from asking a legitimate STOP/DECISION question.

2. **`_next_package` (~2728).** Done worker sources first use `tasks.saved_handoff`, regardless of whether
   their final reply is empty. The saved note may be newer/more complete than an acknowledgment reply.

   ```python
        reply, _ = self.final_message(sid)
        if source["state"] == "done" and source.get("handoff"):
            block, error = tasks.saved_handoff(self.folder, task, source)
        else:
            block, error = tasks.step_handoff(self.folder, task, source, reply, meta or {})
        valid = block is not None and not error
   ```

   If a new file-mode worker source has no accepted note, refuse preview/source availability with its stored
   handoff_error; do not drop into the existing reply-built fallback. Historical/chat fallback stays. Update
   `Latest source reply: validated HANDOFF` to `Source handoff: checked file` / `legacy reply` / `reply fallback`.
   `data.handoff` is the accepted body, so the existing preview hash changes when the note changes. Keep
   current git facts separate from recorded facts. Preserve **real** `reply` as source-reply.md, including empty.

3. **`_chat_tick` (~3231).** Keep `tasks.parse_handoff(text)` as-is and add a comment that this is D7's legacy
   producer. No output reservation for chats. Clear or new chat turns must not adopt another worker's file.

4. **`_ended` (~3586).** Covered in section 2. Strict new file errors do not become empty strings in manual mode.

5. **`_step_files` (~3686).** Add optional final parameter `block: str = ""` and replace only its local parse:

   ```python
                tasks.write_step_file(self.folder, task, cs, "verdict.md",
                                      f"VERDICT: {verdict}" + (f" {detail}" if detail else "") + "\n\n## Findings\n"
                                      + (plan.section(block or "", "## Findings") or "(none)"))
   ```

   `_ended` passes `block=block or ""`. The reading-session rg found this sole caller; recheck at build time
   and pass a code-built note if another caller has landed. Failed-attempt chat capture and
   notes_of's PLAN stripping stay. `_step_files`'s best-effort diagnostic writes do not include canonical save.

6. **Synthetic reply in `_next_source` (~1629).** Read `notes.md` into reply only when the stream is absent as
   today, but never append fabricated HANDOFF markers. Track `saved, saved_error = tasks.saved_handoff(...)`
   separately; an older source is available if it has a real reply or a valid saved note, subject to existing
   gates. For new file workers specifically require the accepted note. Run reply_question only on the real
   reply; a saved Open questions section is not a pending STOP command.

7. **Synthetic reply in `_next_package` (~2727).** Delete the wrapper construction entirely; section 3.2 reads
   the saved body directly. No service-built markers for the file protocol.

Retain compact._sections/brief.build's parsing and old_ok behavior. `parse_handoff` and missing_block are not
deleted: they still implement legacy, chat, skill and historical contracts. `notes_of` still recognizes old
markers and PLAN; a new normal reply is stored whole, a design reply still saves its plan separately.

## 4. Live state and Handoff tab

At the beginning of `_live_note`, before its stream-size cache:

```python
        if (self.runs.meta(sid) or {}).get("handoff_output"):
            return "writing"
```

No file stats or reads from the snapshot loop. `tasks.live_note(text)` retains legacy writing/unchecked behavior.
`tasks.note_state` retains checked/ready/sent after acceptance. On a file-mode failed step, never return writing
just because an old file exists. The running check already happens in note_state; test that failure exits it.

Add three read-only fields to `task_row`'s per-step object, using `.get`: `handoff_source`, `handoff_error`, and
`handoff_output` (relative path only). In `_step_texts`, for file-mode steps include canonical `notes` only when
`state == done` and `handoff` names an accepted note; keep briefs/facts history. Never populate notes by reading
attempt directories. Old states and the existing special code-built note path continue to work.

In `handPane`, before the `!note` empty-state branch and after the running/planned branches:

```javascript
  if (s.handoff_error) return `<p class="note m">${esc(s.handoff_error)}</p>`;
```

For a file-protocol running worker, keep `Writing. Shows here when the run ends.`; do not label it unchecked
merely because the file now exists. A done accepted file uses the existing `handoffHtml`/brief Checks/facts;
prepend `Source: handoff.md` with existing note styles when `handoff_source === "file"`. Do not add a new
browser file parser, live file watcher or protocol-dependent action gates. The legacy reply chips stay for
chats/old transcripts; new replies need no chip to make the Handoff tab available.

Build-time UI cases: running before/after candidate creation, ended accepted, missing/invalid, Retry with an old
canonical note, paused question, legacy running/unchecked, cleared stream and saved note, raw chat, replan.
Check the plan 55/59 branch before editing the pane; preserve the same served fields if their layout has landed.

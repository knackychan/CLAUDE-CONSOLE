"""Task guidance uses real HTTP and the fake runner; the scheduler is advanced explicitly."""
import json
import threading
from unittest import mock

from console import plan, server, tasks
from tests.test_server import TaskServerTest as _TaskServerTest


class TaskMessageTest(_TaskServerTest):
    def message(self, tid, text="correction HANDOFF-OK", **changes):
        body = {"task": tid, "text": text, "request_id": "a" * 32,
                "target": tasks.message_target(self.hub.tasks[tid])}
        body.update(changes)
        return self.call("/api/task/message", body)

    def test_busy_messages_are_persisted_idempotent_and_run_in_order_before_advance(self):
        tid = self.make_task()
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        with mock.patch.object(self.hub.runs, "is_live", return_value=True):
            first = self.message(tid, "first correction HANDOFF-OK")
            second = self.message(tid, "second correction HANDOFF-OK", request_id="b" * 32)
            self.assertEqual((first[0], second[0]), (200, 200))
            self.assertEqual(first[1]["message"]["status"], "queued")
            self.assertEqual(self.message(tid, "first correction HANDOFF-OK")[1], first[1])
            self.assertEqual(self.message(tid, "different")[0], 409)
            self.hub.advance()
            self.assertEqual(self.hub.tasks[tid]["current"], 1)
        saved = tasks.load(self.folder, tid)
        self.assertEqual(len(saved["messages"]), 2)
        self.until(tid, lambda t: all(m["status"] == "dispatched" for m in t["messages"]), "messages delivered")
        self.wait_idle(sid)
        prompts = [i["text"] for i in self.hub.runs.chat_of(sid, limit=10000) if i["role"] == "you"]
        self.assertEqual(len(prompts), 3)
        self.assertIn("first correction", prompts[1])
        self.assertIn("second correction", prompts[2])
        self.assertIn("Rebuild your complete HANDOFF", prompts[2])
        task = self.until(tid, self.at(2), "next step starts after messages")
        self.assertIn("second correction", tasks.read_step_file(self.folder, task, task["steps"][0], "notes.md"))

    def test_planned_guidance_does_not_start_a_run_and_is_in_first_prompt(self):
        tid = self.make_task()
        self.wait_idle(self.hub.tasks[tid]["steps"][0]["session"])
        task = self.hub.tasks[tid]
        task.update(state="planned", current=0)
        task["steps"][0].update(state="planned", session="", attempts=[])
        with mock.patch.object(self.hub.runs, "start", wraps=self.hub.runs.start) as start:
            self.assertEqual(self.message(tid, "first-step guidance")[0], 200)
            start.assert_not_called()
            self.hub.advance()
            self.assertIn("first-step guidance", start.call_args.args[1])
        self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "dispatched")

    def test_stale_attempt_denied_project_invalid_files_and_disk_failure_keep_queue_empty(self):
        tid = self.make_task()
        target = dict(tasks.message_target(self.hub.tasks[tid]), session="old")
        status, data = self.message(tid, target=target)
        self.assertEqual(status, 409)
        self.assertEqual(data["target"], tasks.message_target(self.hub.tasks[tid]))
        self.hub.cfg["projects"] = []
        self.assertEqual(self.message(tid)[0], 409)
        self.hub.cfg["projects"] = [str(self.project)]
        self.assertEqual(self.message(tid, files=[{"name": "bad", "data": "!"}])[0], 400)
        with mock.patch.object(tasks, "save", side_effect=OSError("disk full")):
            self.assertEqual(self.message(tid)[0], 500)
        self.assertFalse(tasks.pending_messages(self.hub.tasks[tid]))

    def test_stop_keeps_guidance_and_retry_requires_explicit_carry(self):
        tid = self.make_task(words="HANDOFF-OK SLOW")
        self.assertEqual(self.message(tid)[0], 200)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.assertEqual(self.call("/api/task/stop", {"task": tid})[0], 200)
        self.wait_idle(sid)
        for action in ("retry", "stepdone", "done", "clear"):
            self.assertEqual(self.call("/api/task/" + action, {"task": tid})[0], 409, action)
        self.assertEqual(self.call("/api/task/retry", {"task": tid, "pending": "carry"})[0], 200)
        task = self.hub.tasks[tid]
        self.assertEqual(task["messages"][0]["target"]["session"], sid)
        self.assertEqual(task["messages"][0]["status"], "dispatched")
        self.assertIn("correction", self.prompt_of(task["steps"][0]["session"]))

    def test_paused_guidance_waits_until_resume_and_cancel_unblocks_actions(self):
        tid = self.make_task()
        self.call("/api/task/pause", {"task": tid})
        self.assertEqual(self.message(tid)[0], 200)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        with mock.patch.object(self.hub.runs, "start", wraps=self.hub.runs.start) as start:
            self.hub.advance()
            start.assert_not_called()
            self.assertEqual(self.call("/api/task/resume", {"task": tid})[0], 200)
            self.assertIn("correction", start.call_args.args[1])
        self.message(tid, "cancel me", request_id="b" * 32)
        self.assertEqual(self.call("/api/task/message", {"task": tid, "request_id": "b" * 32, "action": "cancel"})[0], 200)
        self.assertEqual(self.hub.tasks[tid]["messages"][1]["status"], "cancelled")

    def test_attachments_stay_in_task_storage_and_are_delivered_inline(self):
        tid = self.make_task()
        status, data = self.message(tid, files=[{"name": "a.txt", "data": "aGVsbG8="}])
        self.assertEqual(status, 200, data)
        self.assertNotIn('"data"', json.dumps(self.task(tid)[1]))
        message = tasks.load(self.folder, tid)["messages"][0]
        self.assertEqual(tasks.message_files(self.folder, self.hub.tasks[tid], message)[0]["data"], "hello")
        self.until(tid, lambda t: t["messages"][0]["status"] == "dispatched", "attachment sent")
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        self.assertIn("+document", self.hub.final_message(sid)[0])

    def test_restart_recovers_queue_and_never_replays_uncertain_dispatch(self):
        tid = self.make_task()
        self.message(tid)
        task = tasks.load(self.folder, tid)
        self.assertEqual(task["messages"][0]["status"], "queued")
        task["messages"][0]["status"] = "dispatching"
        tasks.save(self.folder, task)
        with mock.patch.object(server.Hub, "probe"):
            recovered = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        with mock.patch.object(recovered.runs, "start") as start:
            recovered.advance()
            start.assert_not_called()
        self.assertEqual(tasks.load(self.folder, tid)["messages"][0]["status"], "uncertain")

    def test_restart_delivers_a_saved_queue_once(self):
        tid = self.make_task()
        self.message(tid)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        with mock.patch.object(server.Hub, 'probe'):
            recovered = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        recovered.poll_once()
        with mock.patch.object(recovered.runs, 'start', wraps=recovered.runs.start) as start:
            recovered.advance()
            recovered.advance()
            self.assertEqual(start.call_count, 1)
        self.wait_idle(sid)
        self.assertEqual(tasks.load(self.folder, tid)['messages'][0]['status'], 'dispatched')

    def test_launch_error_is_visible_uncertain_and_is_not_replayed(self):
        tid = self.make_task()
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        with mock.patch.object(self.hub.runs, "start", side_effect=OSError("spawn failed")) as start:
            self.assertEqual(self.message(tid)[0], 200)
            self.hub.advance()
            self.hub.advance()
            self.assertEqual(start.call_count, 1)
        self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "uncertain")

    def test_answer_and_plan_gap_use_the_current_step_and_keep_files(self):
        tid = self.plan_task(goals={3: "write it PLAN-GAP"})
        task = self.until(tid, lambda t: t["state"] == "waiting", "plan gap waits")
        sid = tasks.current_step(task)["session"]
        status, data = self.message(tid, "config.json HANDOFF-OK", files=[{"name": "answer.txt", "data": "YQ=="}])
        self.assertEqual(status, 200, data)
        self.assertEqual(data["message"]["status"], "dispatched")
        self.assertEqual(data["message"]["session"], sid)
        self.assertIn("config.json HANDOFF-OK", plan.read(self.folder, self.hub.tasks[tid]))
        self.wait_idle(sid)
        self.assertIn("+document", self.hub.final_message(sid)[0])

    def test_guidance_queued_before_a_plan_gap_is_not_written_as_a_decision(self):
        tid = self.plan_task(goals={3: 'write it PLAN-GAP'})
        self.until(tid, self.at(3), 'code runs')
        with mock.patch.object(self.hub.runs, 'is_live', return_value=True):
            self.assertEqual(self.message(tid, 'ordinary correction HANDOFF-OK')[0], 200)
        self.until(tid, lambda t: t['messages'][0]['status'] == 'dispatched', 'guidance dispatched')
        self.assertNotIn('ordinary correction', plan.read(self.folder, self.hub.tasks[tid]))

    def test_paused_plan_gap_answer_waits_for_resume_before_changing_decisions(self):
        tid = self.plan_task(goals={3: 'write it PLAN-GAP'})
        self.until(tid, lambda t: t['state'] == 'waiting', 'plan gap waits')
        self.call('/api/task/pause', {'task': tid})
        self.assertEqual(self.message(tid, 'paused answer HANDOFF-OK')[0], 200)
        self.assertNotIn('paused answer', plan.read(self.folder, self.hub.tasks[tid]))
        self.assertEqual(self.call('/api/task/resume', {'task': tid})[0], 200)
        self.assertIn('paused answer', plan.read(self.folder, self.hub.tasks[tid]))

    def test_failed_turn_keeps_queue_and_prevents_automatic_retry(self):
        tid = self.make_task(words="HANDOFF-OK MAXTURNS")
        self.message(tid)
        self.until(tid, lambda t: t["state"] == "stuck", "failed run stops before retry")
        self.assertEqual(len(tasks.attempts(self.hub.tasks[tid]["steps"][0])), 1)
        self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "queued")

    def test_cold_dispatch_requires_confirmation_and_finished_step_rejects_delivery(self):
        tid = self.make_task()
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        with mock.patch.object(self.hub, "cold", return_value={"tokens": 50000, "idle_s": 3600, "cost": 1}):
            self.assertEqual(self.message(tid)[0], 409)
            status, _ = self.message(tid, confirm=True)
            self.assertEqual(status, 200)
            self.hub.advance()
            self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "dispatched")
        self.hub.tasks[tid]["steps"][0]["state"] = "done"
        self.assertEqual(self.message(tid, request_id="b" * 32)[0], 409)

    def test_external_conversation_is_only_forked(self):
        tid = self.make_task()
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        row = self.hub.session(sid)
        row.update(window=False, run_live=False, state="idle")
        info = {"continue": "", "fork": True, "harness": "claude"}
        with mock.patch.object(self.hub, "session", return_value=row), \
                mock.patch.object(self.hub.runs, "meta", return_value=None), \
                mock.patch.object(self.hub.runs, "is_live", return_value=False), \
                mock.patch.object(self.hub, "levers", return_value=info), \
                mock.patch.object(self.hub, "cold", return_value={"tokens": 50000, "idle_s": 3600, "cost": 1}), \
                mock.patch.object(self.hub.runs, "start", return_value="new-copy") as start:
            self.assertEqual(self.message(tid)[0], 409)
            start.assert_not_called()
            self.assertEqual(self.message(tid, confirm=True)[0], 200)
            self.assertIsNone(start.call_args.kwargs["resume"])
            self.assertEqual(start.call_args.kwargs["fork"], sid)

    def test_guidance_during_replan_is_processed_before_the_proposal(self):
        task = self.loose_task()
        task["steps"] = tasks.plan_steps([{"kind": "replan", "goal": "reconsider"},
                                          {"kind": "scout", "goal": "look"}], 6)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = server.replan.run_replan
        calls = []
        def run(*args):
            calls.append(args[4])
            if len(calls) == 1:
                entered.set()
                release.wait(10)
            return original(*args)
        with mock.patch.object(server.replan, "run_replan", side_effect=run):
            self.hub.advance()
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.message(task["id"], "replan correction")[0], 200)
            release.set()
            finished = self.until(task["id"], lambda t: t["state"] == "waiting" and t["why"].startswith("replanned:"), "guided replan proposal")
        self.assertEqual(len(calls), 2)
        self.assertIn("replan correction", calls[1])
        self.assertEqual(finished["messages"][0]["status"], "dispatched")
        self.assertEqual(len(tasks.attempts(finished["steps"][0])), 1)

    def test_stopped_plain_chat_can_explicitly_retry_with_saved_guidance(self):
        status, data = self.call('/api/run', {'project_dir': str(self.project), 'prompt': 'SLOW chat', 'model': 'sonnet', 'effort': 'low'})
        self.assertEqual(status, 200)
        tid, sid = data['task'], data['session']
        self.assertEqual(self.call('/api/task/stop', {'task': tid})[0], 200)
        self.wait_idle(sid)
        self.assertEqual(self.message(tid, 'continue with this context')[0], 200)
        with mock.patch.object(self.hub.runs, 'start', wraps=self.hub.runs.start) as start:
            self.hub.advance()
            start.assert_not_called()
            code, result = self.call('/api/task/retry', {'task': tid, 'pending': 'carry', 'model': 'sonnet'})
            self.assertEqual(code, 200, result)
            self.assertIn('continue with this context', start.call_args.args[1])
        self.assertEqual(self.hub.tasks[tid]['messages'][0]['status'], 'dispatched')

    def test_guidance_does_not_block_confirmation_of_its_first_step(self):
        task = self.loose_task()
        task['steps'][0]['pick'] = 'fable'
        self.hub.advance()
        self.assertEqual(task['why'], 'confirm Fable')
        self.assertEqual(self.message(task['id'])[0], 200)
        self.assertEqual(self.call('/api/task/confirm', {'task': task['id']})[0], 200)
        self.assertEqual(self.hub.tasks[task['id']]['messages'][0]['status'], 'dispatched')

    def test_missing_saved_attachment_fails_visibly_without_starting(self):
        task = self.loose_task()
        self.assertEqual(self.message(task['id'], files=[{'name': 'a.txt', 'data': 'YQ=='}])[0], 200)
        with mock.patch.object(tasks, 'message_files', side_effect=OSError('file missing')), \
                mock.patch.object(self.hub.runs, 'start') as start:
            self.hub.advance()
            start.assert_not_called()
        saved = tasks.load(self.folder, task['id'])
        self.assertEqual(saved['messages'][0]['status'], 'failed')
        self.assertIn('file missing', saved['messages'][0]['error'])


for _name in dir(_TaskServerTest):
    if _name.startswith("test_") and _name not in TaskMessageTest.__dict__:
        setattr(TaskMessageTest, _name, None)

del _TaskServerTest

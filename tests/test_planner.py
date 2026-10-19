"""Plan 47: the planner pass (console/planner.py) reviews a Prep card's scope and writes its step list. One bounded
read-only `claude -p`; any failure leaves Prep's own steps and sets the error, never raises."""
import copy
import json
import subprocess
import unittest
from unittest import mock

from console import claude_cli, kinds, paths, planner, tasks

ROUTE = {"type": "normal", "reasoning": "high", "volume": "low", "model": "opus", "effort": "high"}
FIELDS = {"goal": "Fix add() in calc.py", "where": "calc.py:2", "keep": "the signature", "done_when": "tests pass",
          "last_decisions": "", "question": "", "reason": "small", "route": ROUTE,
          "scouting": "calc.py:2 add(): the function to fix",
          "steps": [{"kind": "code", "goal": "fix add() and its test"}]}
CARD = {"raw": "fix add", "fields": FIELDS, "route": ROUTE}
GOOD = {"scope": "ok", "note": "the change is as small as Prep says",
        "steps": [{"kind": "scout", "goal": "find the callers"}, {"kind": "design", "goal": "decide the fix"},
                  {"kind": "code", "goal": "write it"}]}


def envelope(fields=None, cost=0.02, turns=4, is_error=False, subtype="success"):
    data = {"type": "result", "subtype": subtype, "is_error": is_error, "total_cost_usd": cost, "num_turns": turns}
    if fields is not None:
        data["structured_output"] = fields
        data["result"] = json.dumps(fields)
    return json.dumps(data)


class Done:
    def __init__(self, stdout: str, code: int = 0):
        self.stdout, self.stderr, self.returncode = stdout.encode("utf-8"), b"", code


def run(cfg=None, exe=("claude",), stdout=None, side_effect=None):
    cfg = cfg or copy.deepcopy(paths.DEFAULTS)
    with mock.patch.object(planner.subprocess, "run", side_effect=side_effect,
                           return_value=None if side_effect else Done(stdout)) as fake:
        out = planner.run(cfg, list(exe), "C:/proj", CARD, kinds.seed_text("planner"))
    return out, fake


class ShapeTest(unittest.TestCase):
    def test_schema_requires_the_three_keys(self):
        self.assertEqual(set(planner.SCHEMA["required"]), {"scope", "note", "steps"})
        self.assertEqual(planner.SCHEMA["properties"]["scope"]["enum"], ["ok", "too_big", "too_small", "unclear"])
        self.assertEqual(planner.SCHEMA["properties"]["steps"]["items"]["properties"]["kind"]["enum"],
                         list(tasks.PREP_KINDS))

    def test_shape_accepts_a_good_object_and_names_the_fault(self):
        self.assertEqual(planner.shape(GOOD), "")
        self.assertEqual(planner.shape(dict(GOOD, steps=[])), "")  # the planner may keep nothing: run says so
        self.assertNotEqual(planner.shape(dict(GOOD, scope="huge")), "")
        self.assertNotEqual(planner.shape(dict(GOOD, steps="code")), "")
        self.assertNotEqual(planner.shape(dict(GOOD, steps=[{"kind": "code", "goal": " "}])), "")
        self.assertNotEqual(planner.shape(dict(GOOD, note=3)), "")
        self.assertNotEqual(planner.shape("junk"), "")
        self.assertNotEqual(planner.shape({"scope": "ok", "steps": []}), "")  # note missing


class PromptTest(unittest.TestCase):
    def test_build_prompt_carries_the_card_as_evidence(self):
        text = planner.build_prompt(CARD, "Fred", kinds.seed_text("planner"))
        self.assertFalse(text.startswith("# planner"))  # the head line goes, like every kind file
        self.assertIn("Fred", text)
        self.assertIn("fix add", text)
        self.assertIn("Goal: Fix add() in calc.py", text)  # prep.format_prompt
        self.assertIn("opus/high", text)
        self.assertIn("reasoning high", text)
        self.assertIn("calc.py:2 add()", text)
        self.assertIn("- code: fix add() and its test", text)  # Prep's proposed steps, one line each
        self.assertNotIn("$You", text)
        none = planner.build_prompt({"raw": "x", "fields": {"goal": "x", "route": ROUTE}, "route": ROUTE}, "Fred",
                                    kinds.seed_text("planner"))
        self.assertIn("(none)", none)

    def test_planner_command_is_preps_with_a_turn_and_spend_cap(self):
        cmd = claude_cli.planner_command(["claude"], "opus", planner.SCHEMA, 0.5)
        self.assertEqual(cmd[:4], ["claude", "-p", "--model", "opus"])
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "12")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0.5")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertIn('{"disableAllHooks": true}', cmd)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), planner.SCHEMA)


class RunTest(unittest.TestCase):
    def test_good_answer_gives_validated_steps(self):
        out, fake = run(stdout=envelope(GOOD))
        self.assertEqual([s["kind"] for s in out["steps"]], ["scout", "design", "code", "verify"])
        self.assertEqual([s["n"] for s in out["steps"]], [1, 2, 3, 4])
        self.assertEqual((out["scope"], out["note"], out["cost"], out["turns"], out["model"], out["error"]),
                         ("ok", GOOD["note"], 0.02, 4, "opus", ""))
        call = fake.call_args
        self.assertEqual(call.kwargs["cwd"], "C:/proj")
        self.assertEqual(call.kwargs["timeout"], paths.DEFAULTS["planner_timeout_s"])
        self.assertIn(b"- code: fix add() and its test", call.kwargs["input"])
        cmd = call.args[0]
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], str(paths.DEFAULTS["planner_max_cost"]))

    def test_steps_are_cut_at_task_max_steps(self):
        cfg = dict(copy.deepcopy(paths.DEFAULTS), task_max_steps=2)
        out, _ = run(cfg=cfg, stdout=envelope(GOOD))
        self.assertEqual([s["kind"] for s in out["steps"]], ["scout", "design"])

    def test_no_valid_step_is_an_error(self):
        out, _ = run(stdout=envelope(dict(GOOD, steps=[])))
        self.assertEqual((out["steps"], out["error"], out["cost"]), ([], "no valid steps", 0.02))
        self.assertEqual((out["scope"], out["note"]), ("ok", GOOD["note"]))  # the card still shows what it said

    def test_failures_keep_the_cost_and_never_raise(self):
        out, _ = run(side_effect=subprocess.TimeoutExpired("claude", 120))
        self.assertEqual((out["steps"], out["cost"]), ([], None))
        self.assertIn("longer than", out["error"])
        out, _ = run(side_effect=OSError("gone"))
        self.assertEqual(out["steps"], [])
        self.assertIn("cannot start claude", out["error"])
        out, _ = run(stdout=envelope(None, cost=0.02, is_error=True, subtype="error_max_turns"))
        self.assertEqual((out["steps"], out["cost"]), ([], 0.02))
        self.assertIn("error_max_turns", out["error"])
        out, _ = run(stdout="not json")
        self.assertEqual((out["steps"], out["cost"]), ([], None))
        self.assertIn("no JSON", out["error"])
        out, _ = run(stdout=envelope(dict(GOOD, scope="huge"), cost=0.04))
        self.assertEqual((out["steps"], out["cost"]), ([], 0.04))
        self.assertNotEqual(out["error"], "")
        out, _ = run(stdout=envelope({"result": "x"}, cost=0.01))  # structured_output not an object of the schema
        self.assertEqual(out["steps"], [])
        self.assertNotEqual(out["error"], "")

    def test_no_exe_is_the_known_error_with_no_spend(self):
        out, fake = run(exe=[], stdout=envelope(GOOD))
        self.assertEqual((out["steps"], out["cost"], out["error"]), ([], 0, "claude.exe not found"))
        self.assertEqual(fake.call_count, 0)


if __name__ == "__main__":
    unittest.main()

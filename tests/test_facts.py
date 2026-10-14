"""Plan 23: the facts under the brief (console/facts.py): git numstat snapshots, the step's own lines, the last test."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from console import claude_cli, facts

OK_RUN = "....\n----------------------------------------------------------------------\nRan 23 tests in 0.412s\n\nOK"
FAIL_RUN = ("Exit code 1\n..F.\n======================================================================\n"
            "FAIL: test_add (tests.test_calc.CalcTest.test_add)\n-----\nTraceback (most recent call last):\n"
            "  File \"tests/test_calc.py\", line 6\nAssertionError: 3 != 4\n\nRan 4 tests in 0.010s\n\nFAILED (failures=1)")


def stream(command, output, error=False, other=()):
    """Claude stream-json lines: an assistant tool_use Bash and the user tool_result with its id."""
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{k}", "name": "Bash",
                                                            "input": {"command": c}}]}} for k, c in enumerate(other)]
    lines += [{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{k}", "content": "x"}]}}
              for k, _ in enumerate(other)]
    lines += [{"type": "assistant", "message": {"content": [
                  {"type": "text", "text": "running the tests"},
                  {"type": "tool_use", "id": "tt", "name": "Bash", "input": {"command": command}}]}},
              {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tt", "is_error": error,
                                                        "content": [{"type": "text", "text": output}]}]}}]
    return lines


class FactsTest(unittest.TestCase):
    def test_parse_numstat(self):
        text = "12\t3\tconsole/tasks.py\n-\t-\tassets/icon.png\n4\t0\tweb/{old.js => app.js}\n1\t1\ta.py => b.py\nbad line"
        self.assertEqual(facts.parse_numstat(text), {"console/tasks.py": [12, 3], "assets/icon.png": [0, 0],
                                                     "web/app.js": [4, 0], "b.py": [1, 1]})
        self.assertEqual(facts.parse_numstat(""), {})

    def test_snapshot_adds_untracked_files(self):
        snap = facts.snapshot("2\t1\tcalc.py\n", {"new.py": 30, "calc.py": 99})
        self.assertEqual(snap, {"calc.py": [2, 1], "new.py": [30, 0]})  # a tracked file keeps its numstat

    def test_delta_is_the_steps_own_lines(self):
        before = {"calc.py": [2, 1], "old.md": [5, 0]}  # an earlier step's uncommitted lines
        after = {"calc.py": [6, 2], "old.md": [5, 0], "new.py": [30, 0]}
        self.assertEqual(facts.delta(before, after), {"calc.py": [4, 1], "new.py": [30, 0]})
        self.assertEqual(facts.delta(after, after), {})
        self.assertEqual(facts.delta({"x.py": [3, 0]}, {}), {"x.py": [0, 0]})  # reverted: touched, no lines
        self.assertEqual(facts.facts({"calc.py": [4, 1], "new.py": [30, 0]}, None),
                         {"files": 2, "plus": 34, "minus": 1, "tests": ""})

    def test_last_test_reads_the_tool_result(self):
        lines = stream("py -m unittest discover -s tests", OK_RUN, other=["git status", "pytest -q"])
        test = facts.last_test(lines)
        self.assertEqual(test, {"command": "py -m unittest discover -s tests", "output": OK_RUN, "error": False})
        self.assertIsNone(facts.last_test(stream("git diff", "x")))  # not a test command
        self.assertIsNone(facts.last_test(stream("npm test", "x")[:1]))  # no result in the stream yet
        self.assertIsNone(facts.last_test([{"raw": "not json"}, {"type": "result"}]))
        for cmd in ("python -m pytest tests", "npm run test", "go test ./...", "cargo test", "make test",
                    "uv run pytest -x"):
            self.assertTrue(facts.TEST_CMD.search(cmd), cmd)
        for cmd in ("git status", "cat test_plan.py", "ls tests"):
            self.assertFalse(facts.TEST_CMD.search(cmd), cmd)

    def test_test_word(self):
        self.assertEqual(facts.test_word(None), "")
        self.assertEqual(facts.test_word({"command": "c", "output": OK_RUN, "error": False}), "23 OK")
        self.assertEqual(facts.test_word({"command": "c", "output": "== 7 passed in 0.5s ==", "error": False}), "7 OK")
        self.assertEqual(facts.test_word({"command": "c", "output": "all good", "error": False}), "OK")
        self.assertEqual(facts.test_word({"command": "c", "output": FAIL_RUN, "error": True}),
                         "FAIL FAIL: test_add (tests.test_calc.CalcTest.test_add)")
        self.assertEqual(facts.test_word({"command": "c", "output": "1 failed, 3 passed", "error": False}),
                         "FAIL 1 failed, 3 passed")
        self.assertEqual(facts.test_word({"command": "c", "output": "", "error": True}), "FAIL exit code not 0")

    def test_text(self):
        changed = {"console/tasks.py": [12, 3], "tests/test_tasks.py": [40, 0]}
        ok = facts.text("abc1234567", "def7654321", changed, {"command": "py -m unittest", "output": OK_RUN,
                                                              "error": False})
        self.assertEqual(ok.splitlines(), ["git diff --stat abc1234..def7654",
                                           " console/tasks.py    | +12 -3",
                                           " tests/test_tasks.py | +40 -0",
                                           "2 files changed, +52 -3",
                                           "Tests: py -m unittest",
                                           "Ran 23 tests in 0.412s", "OK"])
        self.assertEqual(facts.files_in(ok), ["console/tasks.py", "tests/test_tasks.py"])  # start_brief's touched
        failed = facts.text("abc1234567", "abc1234567", {}, {"command": "py -m unittest", "output": FAIL_RUN,
                                                             "error": True})
        self.assertEqual(failed.splitlines()[:3], ["git diff --stat abc1234..working tree", "no file changed",
                                                   "Tests: py -m unittest"])
        self.assertIn("FAIL: test_add (tests.test_calc.CalcTest.test_add)", failed)
        self.assertIn("AssertionError: 3 != 4", failed)
        self.assertNotIn("Traceback", failed)  # the failing lines only
        self.assertEqual(facts.text("", "", {}, None).splitlines(),
                         ["git: no repository here, or no start commit", "Tests: none ran in this step"])
        self.assertEqual(facts.text("", "", {}, None, git=False, read_tests=False).splitlines()[1], facts.NOT_READ)
        many = {f"f{k}.py": [1, 0] for k in range(35)}
        self.assertIn(" ... and 5 more", facts.text("a" * 40, "b" * 40, many, None))

    @unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
    def test_git_snapshot_on_a_real_repo(self):
        with tempfile.TemporaryDirectory() as repo:
            run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True)
            run("init", "-q")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start")
            (Path(repo) / "calc.py").write_text("a\nb\n", encoding="utf-8")
            run("add", "calc.py")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "calc")
            head = claude_cli.git_head(repo)
            before = claude_cli.git_snapshot(repo, head)
            self.assertEqual(before, {})
            (Path(repo) / "calc.py").write_text("a\nb\nc\n", encoding="utf-8")
            (Path(repo) / "new.py").write_text("x\ny\n", encoding="utf-8")
            after = claude_cli.git_snapshot(repo, head)
            self.assertEqual(after, {"calc.py": [1, 0], "new.py": [2, 0]})
            self.assertEqual(facts.delta(before, after), {"calc.py": [1, 0], "new.py": [2, 0]})
            self.assertEqual(claude_cli.git_status(repo), [" M calc.py", "?? new.py"])  # the index is untouched
            self.assertIsNone(claude_cli.git_snapshot(repo, ""))
            self.assertIsNone(claude_cli.git_snapshot(tempfile.gettempdir(), head))  # not this repo's commit


if __name__ == "__main__":
    unittest.main()

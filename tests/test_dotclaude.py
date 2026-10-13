"""The user-level skills and agent Fred copies to ~/.claude: they must agree with the console's code."""
import re
import tempfile
import time
import unittest
from pathlib import Path

import cc_events
from console import claude_cli, levers, paths, prep

ROOT = Path(__file__).resolve().parent.parent
DOT = ROOT / "dotclaude"
FILES = {"route-model": DOT / "skills" / "route-model" / "SKILL.md",
         "session-handoff": DOT / "skills" / "session-handoff" / "SKILL.md",
         "verifier": DOT / "agents" / "verifier.md"}


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(": ", 1) for line in m.group(1).splitlines()) if m else {}


def table(text: str) -> dict:
    """type -> (model, effort) from a route table whose cells are type | when | model | effort | ..."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] in prep.TYPES:
            rows[cells[0]] = (cells[2], cells[3])
    return rows


class DotClaudeTest(unittest.TestCase):
    def test_frontmatter(self):
        for name, path in FILES.items():
            meta = front(path)
            self.assertEqual(meta.get("name"), name, path)
            self.assertTrue(meta.get("description", "").startswith("Use "), path)
            self.assertNotIn(chr(0x2014), path.read_text(encoding="utf-8"), path)  # no em-dashes in prose
        agent = front(FILES["verifier"])
        self.assertEqual((agent["tools"], agent["model"], agent["effort"]), ("Bash, Read, Grep, Glob", "sonnet", "low"))

    def test_route_table_matches_prep(self):
        skill = table(FILES["route-model"].read_text(encoding="utf-8"))
        self.assertEqual(skill, table(prep.PROMPT_FILE.read_text(encoding="utf-8")))
        self.assertEqual(sorted(skill), sorted(prep.TYPES))
        self.assertEqual(skill["risky"], ("sonnet", "high"))  # code starts cheaper; the opus verifier checks it
        self.assertEqual(skill["vague"], ("opus", "high"))  # opus only for design and planning
        self.assertEqual(levers.escalate_step(*skill["risky"]), ("opus", "high"))  # a FAIL reroutes to opus
        for model, effort in skill.values():
            self.assertIn(model, claude_cli.MODELS)
            self.assertIn(effort, claude_cli.EFFORTS)

    def test_route_and_miss_lines_parse(self):
        text = FILES["route-model"].read_text(encoding="utf-8")
        self.assertIn("~/.claude/console/routing-misses.md", text)
        route = re.search(r"`(Route: [^`]+)`", text).group(1)
        self.assertEqual(cc_events.last_match(cc_events._ROUTE, route), "mechanical, low effort, cavecrew-builder on sonnet")
        example = next(line for line in text.splitlines() if re.match(r"- \d{4}-\d\d-\d\d - ", line))
        with tempfile.TemporaryDirectory() as tmp:
            levers.add_miss(Path(tmp), example)
            self.assertEqual(levers.read_misses(Path(tmp), "CLAUDE CONSOLE"), [example])
        day = time.mktime((2026, 10, 10, 12, 0, 0, 0, 0, -1))
        self.assertEqual(levers.miss_line("CLAUDE CONSOLE", "normal", "sonnet/medium", "sonnet/high",
                                          "tests/test_state.py:40 - KeyError: 'rules'", day), example)

    def test_handoff_lesson_line_parses(self):
        text = FILES["session-handoff"].read_text(encoding="utf-8")
        self.assertIn("~/.claude/console/lessons.md", text)
        example = next(line for line in text.splitlines() if re.match(r"- \d{4}-\d\d-\d\d - .* - chat: ", line))
        with tempfile.TemporaryDirectory() as tmp:
            levers.add_lesson(Path(tmp), example)
            self.assertEqual(levers.read_lessons(Path(tmp), "CLAUDE CONSOLE"), [example])
        day = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
        body = example.split(" - chat: ", 1)[1]
        self.assertEqual(levers.lesson_line("CLAUDE CONSOLE", "chat", body, day), example)
        self.assertIn("most chats teach nothing", text)

    def test_route_model_ignores_old_misses(self):
        text = FILES["route-model"].read_text(encoding="utf-8")
        self.assertIn("older than 14 days", text)
        self.assertEqual(paths.DEFAULTS["miss_floor_days"], 14)  # the skill's number is the console's

    def test_verifier_trusts_checks_over_reading(self):
        text = FILES["verifier"].read_text(encoding="utf-8")
        self.assertIn("never stands in for them", text)
        self.assertIn("not when the work looks right", text)


if __name__ == "__main__":
    unittest.main()

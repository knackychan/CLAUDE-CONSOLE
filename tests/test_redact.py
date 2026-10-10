import unittest

from console import redact


class MaskTest(unittest.TestCase):
    def test_masks_token_shapes(self):
        text = "curl -H 'Authorization: Bearer abcdefgh12345' sk-ant-1234567890 ghp_abcdefghijkl"
        out = redact.mask(text)
        self.assertNotIn("abcdefgh12345", out)
        self.assertNotIn("sk-ant-1234567890", out)
        self.assertNotIn("ghp_abcdefghijkl", out)

    def test_masks_key_value_but_keeps_the_name(self):
        self.assertEqual(redact.mask("OPENAI_API_KEY=xyz123 run"), "OPENAI_API_KEY=*** run")
        self.assertEqual(redact.mask('password: "hunter2"'), "password:***")

    def test_leaves_normal_text(self):
        self.assertEqual(redact.mask("py -m unittest discover -s tests"), "py -m unittest discover -s tests")


class ClipTest(unittest.TestCase):
    def test_collapses_whitespace_and_cuts(self):
        self.assertEqual(redact.clip("a  b\n c", 10), "a b c")
        self.assertEqual(redact.clip("abcdefghij", 5), "abcd\u2026")


class SummarizeTest(unittest.TestCase):
    def test_path_tools_are_relative_to_cwd(self):
        out = redact.summarize("Edit", {"file_path": "D:\\repo\\src\\a.py"}, "d:\\repo")
        self.assertEqual(out, "src/a.py")

    def test_bash_is_masked_and_clipped(self):
        out = redact.summarize("Bash", {"command": "export TOKEN=abc && " + "x" * 200})
        self.assertTrue(out.startswith("export TOKEN=*** &&"))
        self.assertEqual(len(out), 80)

    def test_agent_shows_type_and_description(self):
        out = redact.summarize("Agent", {"subagent_type": "verifier", "description": "run checks"})
        self.assertEqual(out, "verifier: run checks")

    def test_unknown_tool_gives_empty(self):
        self.assertEqual(redact.summarize("TodoWrite", {"todos": []}), "")


if __name__ == "__main__":
    unittest.main()

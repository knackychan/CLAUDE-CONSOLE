import json
import unittest

from console import review


PROPOSAL = {"kind": "remove", "target": "Always write tests first", "text": "",
            "why": "derivable: the Commands section already names the test command", "sources": ["Always write tests first"]}


class ReviewTest(unittest.TestCase):
    def test_schema_shape(self):
        self.assertEqual(set(review.SCHEMA["required"]), {"proposals", "summary"})
        item = review.SCHEMA["properties"]["proposals"]["items"]
        self.assertEqual(set(item["required"]), {"kind", "target", "text", "why", "sources"})
        self.assertEqual(item["properties"]["kind"]["enum"], review.KINDS)
        self.assertEqual(review.KINDS, ["remove", "demote", "rule", "procedure", "keep"])

    def test_build_prompt(self):
        text = review.build_prompt(["- m1"], ["- l1", "- l2"], 14)
        self.assertIn("in the last 14 days ", text)
        self.assertTrue(text.rstrip().endswith("Lessons in this project (newest last):\n- l1\n- l2"))
        self.assertIn("\n- m1\n", text)
        self.assertIn("at most 6 items", text)
        for kind in review.KINDS:
            self.assertIn(f"- {kind}:", text)
        self.assertIn("(none)", review.build_prompt())
        self.assertNotIn("$", review.build_prompt(["$HOME"]).replace("$HOME", ""))

    def test_parse_output(self):
        good = json.dumps({"is_error": False, "structured_output": {"proposals": [PROPOSAL], "summary": "fine"},
                           "total_cost_usd": 0.02, "num_turns": 4})
        out = review.parse_output(good)
        self.assertEqual((out["proposals"], out["summary"], out["cost"], out["turns"]), ([PROPOSAL], "fine", 0.02, 4))
        many = json.dumps({"structured_output": {"proposals": [PROPOSAL] * 9, "summary": ""}})
        self.assertEqual(len(review.parse_output(many)["proposals"]), review.MAX_PROPOSALS)
        for bad in ("nope", json.dumps({"is_error": True, "subtype": "error_max_turns", "errors": ["turns"]}),
                    json.dumps({"result": "x"}), json.dumps({"structured_output": {"proposals": "x", "summary": ""}})):
            with self.assertRaises(review.ReviewError, msg=bad):
                review.parse_output(bad)
        with self.assertRaises(review.ReviewError) as ctx:
            review.parse_output(json.dumps({"is_error": True, "subtype": "error_max_turns", "errors": ["turns"]}))
        self.assertIn("error_max_turns", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

import unittest

from console import levers, routing


def route(model="sonnet", effort="medium", reasoning="low", volume="low", type_="normal"):
    return {"type": type_, "model": model, "effort": effort, "reasoning": reasoning, "volume": volume}


class RoutingTest(unittest.TestCase):
    def test_heavy_reasoning_runs_on_opus_high(self):
        self.assertEqual(routing.pick(route("haiku", "low", reasoning="high")), ("opus", "high"))
        self.assertEqual(routing.pick(route("sonnet", "medium", reasoning="high", volume="high")), ("opus", "high"))
        self.assertEqual(routing.pick(route("fable", "max", reasoning="high")), ("fable", "max"))  # never lowered

    def test_heavy_volume_runs_on_haiku_or_sonnet(self):
        self.assertEqual(routing.pick(route("opus", "high", volume="high")), ("haiku", "low"))
        self.assertEqual(routing.pick(route("opus", "high", reasoning="medium", volume="high")), ("sonnet", "medium"))

    def test_otherwise_prep_keeps_its_pick(self):
        self.assertEqual(routing.pick(route("sonnet", "low", "medium", "medium")), ("sonnet", "low"))
        self.assertEqual(routing.pick({"type": "lookup", "model": "haiku", "effort": "low"}), ("haiku", "low"))

    def test_a_miss_of_the_same_type_is_a_floor(self):
        miss = levers.miss_line("APP", "lookup", "haiku/low", "haiku/medium", "test_x - KeyError: 'a'")
        other = levers.miss_line("APP", "normal", "sonnet/medium", "sonnet/high", "")
        bulk = route("opus", "high", volume="high", type_="lookup")
        self.assertEqual(routing.pick(bulk, [miss, other]), ("haiku", "medium"))
        self.assertEqual(routing.pick(dict(bulk, type="mechanical"), [miss, other]), ("haiku", "low"))
        heavy = route("sonnet", "low", reasoning="high", type_="lookup")
        self.assertEqual(routing.pick(heavy, [miss]), ("opus", "high"))  # already above the floor

    def test_newest_miss_wins_and_junk_is_ignored(self):
        old = levers.miss_line("APP", "normal", "sonnet/medium", "sonnet/high", "")
        new = levers.miss_line("APP", "normal", "sonnet/high", "opus/high", "")
        junk = "- 2026-10-12 - APP - normal: x failed; next time start at gpt/high."
        self.assertEqual(routing.floor([old, new, junk], "normal"), ("opus", "high"))
        self.assertIsNone(routing.floor([junk], "normal"))

    def test_parse(self):
        self.assertEqual(routing.parse("sonnet/medium"), ("sonnet", "medium"))
        for bad in ("", None, "sonnet", "gpt/high", "sonnet/turbo"):
            self.assertIsNone(routing.parse(bad))


if __name__ == "__main__":
    unittest.main()

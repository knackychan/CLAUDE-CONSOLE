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

    def test_floors_list_the_newest_miss_of_each_type_with_its_date(self):
        old = "- 2026-10-10 - APP - code: sonnet/medium failed (x); next time start at sonnet/high."
        new = "- 2026-10-12 - APP - code: sonnet/high failed (y); next time start at opus/high."
        other = "- 2026-10-11 - APP - debug: sonnet/medium failed (z); next time start at sonnet/high."
        junk = "- 2026-10-12 - APP - code: x failed; next time start at gpt/high."
        self.assertEqual(routing.floors([old, other, new, junk]),
                         {"code": {"route": "opus/high", "date": "2026-10-12"},
                          "debug": {"route": "sonnet/high", "date": "2026-10-11"}})
        self.assertEqual(routing.floors([]), {})

    def test_a_used_line_ends_the_floor_once(self):
        """Plan 32: Fred's case of 2026-10-15. One sonnet miss pinned every code step to opus/high for 14 days; the
        first step that passed on the floor ends it, and a later miss sets a floor again."""
        miss = "- 2026-10-12 - APP - code: sonnet/high failed (x); next time start at opus/high."
        debug = "- 2026-10-12 - APP - debug: sonnet/medium failed (z); next time start at sonnet/high."
        used = levers.used_line("APP", "code", "opus/high", "20261015-085403-e56d", 3)
        again = "- 2026-10-16 - APP - code: sonnet/medium failed (y); next time start at sonnet/high."
        self.assertEqual(routing.live([miss, debug, used]), [debug])
        self.assertIsNone(routing.floor([miss, debug, used], "code"))
        self.assertEqual(routing.floor([miss, debug, used], "debug"), ("sonnet", "high"))  # another kind keeps its own
        self.assertEqual(routing.floor([miss, used, again], "code"), ("sonnet", "high"))
        self.assertEqual(routing.floors([miss, debug, used]), {"debug": {"route": "sonnet/high", "date": "2026-10-12"}})
        self.assertEqual(routing.pick(route("sonnet", "medium", type_="code"), [miss, used]), ("sonnet", "medium"))

    def test_parse(self):
        self.assertEqual(routing.parse("sonnet/medium"), ("sonnet", "medium"))
        for bad in ("", None, "sonnet", "gpt/high", "sonnet/turbo"):
            self.assertIsNone(routing.parse(bad))

    def test_fresh_drops_misses_older_than_the_window(self):
        import time
        now = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
        old = "- 2026-09-20 - APP - code: sonnet/medium failed (x); next time start at opus/high."
        edge = "- 2026-09-29 - APP - code: sonnet/medium failed (x); next time start at sonnet/high."
        new = "- 2026-10-12 - APP - debug: sonnet/high failed (y); next time start at opus/high."
        undated = "misc line"
        self.assertEqual(routing.fresh([old, edge, new, undated], 14, now), [edge, new, undated])
        self.assertEqual(routing.fresh([old, new], 0, now), [old, new])  # 0 = no decay
        self.assertIsNone(routing.floor(routing.fresh([old], 14, now), "code"))
        self.assertEqual(routing.floors(routing.fresh([old, new], 14, now)), {"debug": {"route": "opus/high", "date": "2026-10-12"}})


if __name__ == "__main__":
    unittest.main()

"""Plan 18: usage fills per model and the balance pick (console/fills.py)."""
import unittest
from datetime import datetime

from console import fills

NOW = datetime(2026, 10, 14, 15, 0).timestamp()  # a Wednesday, 15:00 local
CFG = {
    "models": {"codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-luna": "haiku"},
               "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"},
               "cmd": {"deepseek/deepseek-v4.1-flash": "haiku"}},
    "tiers": {"think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "high"},
                        {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
              "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                        {"rung": "opus", "effort": "auto"},
                        {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"}],
              "read": [{"rung": "haiku", "effort": "auto"}, {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}]},
    "allowances": {"opus": {"day_usd": 10, "week_usd": 50, "month_usd": 150}},
    "balance_margin": 0.1, "cache_bonus": 0.1, "budget_warn_at": 0.8, "month_start_day": 1, "peak_hours": {},
}


def at(share):
    return {"share": share}


class NamesTest(unittest.TestCase):
    def test_model_key_names_one_fill(self):
        self.assertEqual(fills.model_key("opus"), "opus")
        self.assertEqual(fills.model_key("claude-opus-4-8"), "opus")
        self.assertEqual(fills.model_key("opencode:opencode-go/kimi-k3"), "kimi-k3")
        self.assertEqual(fills.model_key("cmd:deepseek/deepseek-v4.1-flash"), "deepseek-v4.1-flash")
        self.assertEqual(fills.model_key("opencode:opencode-go/deepseek-v4.1-flash"), "deepseek-v4.1-flash")
        self.assertEqual(fills.model_key("codex:gpt-6.1-sol"), "gpt-6.1-sol")
        self.assertEqual(fills.model_key("opencode:openrouter/anthropic/claude-sonnet-4-6"), "sonnet")

    def test_split_and_rank(self):
        self.assertEqual(fills.split_rung("codex:gpt-6.1-sol"), ("codex", "gpt-6.1-sol"))
        self.assertEqual(fills.split_rung("sonnet"), ("claude", "sonnet"))
        self.assertEqual(fills.rank_of("claude-haiku-4-5"), "haiku")
        self.assertEqual(fills.rank_of("codex:gpt-6-astra", CFG), "opus")
        self.assertEqual(fills.rank_of("codex:nope", CFG), "")
        self.assertEqual(fills.rank_of("codex:gpt-6-astra"), "")  # no models.json, no rank

    def test_tier_rungs_drops_bad_entries(self):
        cfg = {"tiers": {"read": ["haiku", {"rung": "haiku"}, {"rung": ""}, 3, {"rung": "codex:gpt-6-luna",
                                                                                 "effort": "ultra"}]}}
        self.assertEqual(fills.tier_rungs(cfg, "read"), [("haiku", "auto"), ("codex:gpt-6-luna", "auto")])
        self.assertEqual(fills.tier_rungs({}, "think"), [])

    def test_pool_keeps_rank_and_hard_only(self):
        rungs = lambda pool: [r for r, _ in pool]
        self.assertEqual(rungs(fills.pool(CFG, "sonnet")),
                         ["sonnet", "codex:gpt-6.1-sol", "opencode:opencode-go/deepseek-v4.1-flash"])
        self.assertEqual(rungs(fills.pool(CFG, "sonnet", hard=True)),
                         ["sonnet", "codex:gpt-6.1-sol", "opus", "opencode:opencode-go/deepseek-v4.1-flash"])
        self.assertEqual(rungs(fills.pool(CFG, "opus")), ["opus", "codex:gpt-6-astra", "opencode:opencode-go/kimi-k3"])
        self.assertIn("fable", rungs(fills.pool(CFG, "opus", hard=True)))
        self.assertEqual(rungs(fills.pool(CFG, "fable")), ["fable"])
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        self.assertEqual(rungs(fills.pool(CFG, "opus", refuse=off)), ["opus", "opencode:opencode-go/kimi-k3"])
        self.assertTrue(fills.hard_only("opus", "write") and fills.hard_only("fable", "think"))
        self.assertFalse(fills.hard_only("codex:gpt-6-astra", "think", CFG))

    def test_pool_for_checks_has_exact_rank_and_no_cheap_harness(self):
        rungs = lambda pool: [r for r, _ in pool]
        self.assertEqual(rungs(fills.pool(CFG, "opus", check=True)), ["opus", "codex:gpt-6-astra"])
        self.assertEqual(rungs(fills.pool(CFG, "sonnet", check=True)), ["sonnet", "codex:gpt-6.1-sol"])
        self.assertEqual(rungs(fills.pool(CFG, "haiku", check=True)), ["haiku"])


class WindowsTest(unittest.TestCase):
    def test_windows_day_week_month(self):
        w = fills.windows(NOW)
        self.assertEqual(w["day"], (datetime(2026, 10, 14).timestamp(), datetime(2026, 10, 15).timestamp()))
        self.assertEqual(w["week"], (datetime(2026, 10, 12).timestamp(), datetime(2026, 10, 19).timestamp()))
        self.assertEqual(w["month"], (datetime(2026, 10, 1).timestamp(), datetime(2026, 11, 1).timestamp()))
        self.assertEqual(fills.windows(NOW, 20)["month"],
                         (datetime(2026, 9, 20).timestamp(), datetime(2026, 10, 20).timestamp()))
        jan = datetime(2027, 1, 5, 9).timestamp()
        self.assertEqual(fills.windows(jan, 15)["month"],
                         (datetime(2026, 12, 15).timestamp(), datetime(2027, 1, 15).timestamp()))
        self.assertEqual(fills.windows(datetime(2026, 12, 20).timestamp(), 31)["month"][0],
                         datetime(2026, 11, 28).timestamp())  # 31 is clamped to 28

    def test_pace_is_linear_with_a_floor(self):
        start = datetime(2026, 10, 14).timestamp()
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 6 * 3600), 6)
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 60), 1)  # one hour at least
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 2 * 86400), 24)


class FillTest(unittest.TestCase):
    DAYS = {"2026-10-14": {"models": {"opus": 5.0, "sonnet": 1.0}},
            "2026-10-13": {"models": {"opus": 10.0}},
            "2026-10-01": {"models": {"opus": 20.0}},
            "2026-09-30": {"models": {"opus": 99.0}}}

    def test_fill_shares_and_binding(self):
        f = fills.fill(self.DAYS, {}, "opus", CFG["allowances"]["opus"], NOW)
        self.assertEqual(f["day"]["used_usd"], 5.0)
        self.assertAlmostEqual(f["day"]["pace_usd"], 10 * 15 / 24, places=3)
        self.assertAlmostEqual(f["day"]["share"], round(5 / (10 * 15 / 24), 4))
        self.assertEqual(f["week"]["used_usd"], 15.0)  # Monday 12th to today
        self.assertEqual(f["month"]["used_usd"], 35.0)  # September 30th is last month
        best = max(("day", "week", "month"), key=lambda w: f[w]["share"])
        self.assertEqual((f["binding"], f["share"]), (best, f[best]["share"]))
        self.assertEqual(f["unknown_runs"], 0)

    def test_no_allowance_has_no_share(self):
        f = fills.fill(self.DAYS, {}, "sonnet", None, NOW)
        self.assertEqual((f["share"], f["binding"], f["day"]["allowance_usd"], f["day"]["used_usd"]), (None, "", None, 1.0))
        f = fills.fill(self.DAYS, {}, "opus", {"month_usd": 150}, NOW)  # one window only: it binds
        self.assertEqual(f["binding"], "month")

    def test_other_harness_runs_count_and_unpriced_ones_make_it_unknown(self):
        other = {"2026-10-14": {"gpt-6.1-sol": {"cost": 2.0, "runs": 2, "unknown": 0, "tokens": [1, 2, 3]}}}
        f = fills.fill({}, other, "gpt-6.1-sol", {"day_usd": 8}, NOW)
        self.assertEqual(f["day"]["used_usd"], 2.0)
        self.assertIsNotNone(f["share"])
        other["2026-10-02"] = {"gpt-6.1-sol": {"cost": 0, "runs": 1, "unknown": 1, "tokens": [0, 0, 0]}}
        f = fills.fill({}, other, "gpt-6.1-sol", {"day_usd": 8}, NOW)
        self.assertEqual((f["share"], f["binding"], f["unknown_runs"]), (None, "", 1))
        self.assertIsNotNone(f["day"]["share"])  # today itself is priced

    def test_fills_lists_keys_and_via(self):
        out = fills.fills(self.DAYS, {"2026-10-14": {"kimi-k3": {"cost": 1.0, "runs": 1, "unknown": 0}}}, CFG, NOW)
        for key in ("opus", "sonnet", "haiku", "gpt-6-astra", "kimi-k3", "deepseek-v4.1-flash", "fable"):
            self.assertIn(key, out)
        self.assertEqual(out["opus"]["via"], ["claude"])
        self.assertEqual(out["deepseek-v4.1-flash"]["via"], ["opencode", "cmd"])
        self.assertIsNotNone(out["opus"]["share"])
        self.assertIsNone(out["kimi-k3"]["share"])

    def test_price_tokens(self):
        row = {"input": 2, "output": 10, "cache_read": 0.2}
        self.assertEqual(fills.price({"input": 1_000_000, "output": 100_000, "cache_read": 500_000}, row), 3.1)
        self.assertIsNone(fills.price(None, row))
        self.assertIsNone(fills.price({"input": 5}, None))
        self.assertEqual(fills.price({"input": 1_000_000}, {"input": 1, "output": 2}), 1.0)

    def test_merge_other_adds_priced_runs(self):
        days = {"2026-10-14": {"cost": 5.0, "tokens": [1, 1, 1, 1], "projects": {}, "models": {"opus": 5.0}}}
        other = {"2026-10-14": {"gpt-6.1-sol": {"cost": 1.5, "runs": 1, "unknown": 0},
                                "deepseek-v4.1-flash": {"cost": 0, "runs": 2, "unknown": 2}},
                 "2026-10-12": {"gpt-6.1-sol": {"cost": 1.0, "runs": 1, "unknown": 0}}}
        out = fills.merge_other(days, other)
        self.assertEqual(out["2026-10-14"]["cost"], 6.5)
        self.assertEqual(out["2026-10-14"]["models"], {"opus": 5.0, "gpt-6.1-sol": 1.5})
        self.assertEqual(out["2026-10-14"]["unknown"], {"deepseek-v4.1-flash": 2})
        self.assertEqual(out["2026-10-12"]["cost"], 1.0)
        self.assertEqual(days["2026-10-14"]["models"], {"opus": 5.0})  # a copy


class BalanceTest(unittest.TestCase):
    THINK = [("opus", "auto"), ("codex:gpt-6-astra", "high"), ("opencode:opencode-go/kimi-k3", "auto")]

    def test_balance_takes_the_lowest_share(self):
        got = fills.balance(self.THINK, {"opus": at(0.84), "gpt-6-astra": at(0.31), "kimi-k3": at(0.5)}, CFG,
                            tier="think", now=NOW)
        self.assertEqual((got["rung"], got["effort"], got["share"]), ("codex:gpt-6-astra", "high", 0.31))
        self.assertEqual(got["note"], "balance: opus 84 % -> codex:gpt-6-astra 31 %")
        got = fills.balance(self.THINK, {"opus": at(0.2), "gpt-6-astra": at(0.31)}, CFG, tier="think", now=NOW)
        self.assertEqual((got["rung"], got["note"]), ("opus", "balance: opus 20 %"))

    def test_balance_keeps_the_previous_rung_within_margin(self):
        budget = {"opus": at(0.40), "gpt-6-astra": at(0.31), "kimi-k3": at(0.9)}
        got = fills.balance(self.THINK, budget, CFG, tier="think", prev_rung="opus", now=NOW)
        self.assertEqual(got["rung"], "opus")  # 0.40 - 0.31 = 0.09, within 0.1
        self.assertEqual(got["note"], "balance: opus 40 % (previous rung kept: codex:gpt-6-astra 31 % is within the margin)")
        budget["opus"] = at(0.45)
        self.assertEqual(fills.balance(self.THINK, budget, CFG, prev_rung="opus", now=NOW)["rung"], "codex:gpt-6-astra")

    def test_cache_bonus_only_while_warm(self):
        budget = {"opus": at(0.48), "gpt-6-astra": at(0.31)}
        warm = fills.balance(self.THINK, budget, CFG, prev_rung="opus", prev_age=60, now=NOW)
        cold = fills.balance(self.THINK, budget, CFG, prev_rung="opus", prev_age=900, now=NOW)
        self.assertEqual((warm["rung"], cold["rung"]), ("opus", "codex:gpt-6-astra"))  # 0.48 - 0.1 - 0.31 = 0.07

    def test_no_allowance_sorts_after(self):
        got = fills.balance(self.THINK, {"opus": at(0.95), "gpt-6-astra": at(None)}, CFG, tier="think", now=NOW)
        self.assertEqual(got["rung"], "opus")  # the only one with a share, even over pace
        got = fills.balance(self.THINK, {}, CFG, tier="think", now=NOW)
        self.assertEqual((got["rung"], got["note"]), ("opus", "balance: no allowance set -> opus (list order)"))
        self.assertEqual(fills.balance([("haiku", "auto")], {}, CFG, now=NOW)["note"], "balance: haiku only")
        self.assertEqual(fills.balance([], {}, CFG, now=NOW)["rung"], "")

    def test_every_rung_over_pace(self):
        got = fills.balance(self.THINK, {"opus": at(1.1), "gpt-6-astra": at(0.92), "kimi-k3": at(0.95)}, CFG,
                            tier="think", now=NOW)
        self.assertTrue(got["over"])
        self.assertEqual(got["note"], "balance: every think rung over pace -> codex:gpt-6-astra 92 %")

    def test_peak_hours_add_in_their_hours(self):
        cfg = dict(CFG, peak_hours={"anthropic": {"hours": "14-19", "add": 0.2}})
        self.assertEqual(fills.peak_add(cfg, "opus", NOW), 0.2)
        self.assertEqual(fills.peak_add(cfg, "codex:gpt-6-astra", NOW), 0.0)
        self.assertEqual(fills.peak_add(cfg, "opus", datetime(2026, 10, 14, 9).timestamp()), 0.0)
        self.assertEqual(fills.peak_add(dict(CFG, peak_hours={"anthropic": {"hours": "x"}}), "opus", NOW), 0.0)
        got = fills.balance(self.THINK, {"opus": at(0.25), "gpt-6-astra": at(0.31)}, cfg, now=NOW)
        self.assertEqual(got["rung"], "codex:gpt-6-astra")  # 0.25 + 0.2 > 0.31


class FailHoursTest(unittest.TestCase):
    def test_fail_hours_counts_the_writer_hour(self):
        at14 = datetime(2026, 10, 13, 14, 20).timestamp()
        old = NOW - 40 * 86400

        def task(model, started, verdict):
            return {"steps": [{"n": 1, "kind": "code", "model": model, "started": started},
                              {"n": 2, "kind": "verify", "checked": 1, "verdict": verdict, "model": "opus"}]}
        tasks = {"a": task("sonnet", at14, "FAIL"), "b": task("claude-sonnet-4-6", at14, "PASS"),
                 "c": task("codex:gpt-6.1-sol", at14, "FAIL"), "d": task("sonnet", old, "FAIL"),
                 "e": task("sonnet", at14, "")}
        out = fills.fail_hours(tasks, CFG, NOW)
        self.assertEqual((out["sonnet"]["runs"][14], out["sonnet"]["fails"][14]), (2, 1))
        self.assertEqual(sum(out["sonnet"]["runs"]), 2)  # the old one and the one without a verdict are left out
        self.assertEqual((out["gpt-6.1-sol"]["fails"][14], out["gpt-6.1-sol"]["via"]), (1, ["codex"]))


if __name__ == "__main__":
    unittest.main()

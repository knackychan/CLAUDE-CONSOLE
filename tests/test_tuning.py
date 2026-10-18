"""Plan 26: the Models and tuning page's settings and the check of one Save (console/tuning.py)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from console import paths, tuning

CFG = dict(paths.DEFAULTS, projects=["D:/work", "C:/other"], models={
    "codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-luna": "haiku"},
    "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"},
    "cmd": {"deepseek/deepseek-v4.1-flash": "haiku"}})


def check(**changes):
    return tuning.validate(changes, CFG)


class ViewTest(unittest.TestCase):
    def test_every_key_has_its_default_range_and_group(self):
        view = tuning.view(dict(CFG, task_max_steps=8))
        self.assertEqual(list(view), list(tuning.TUNING))
        self.assertEqual(view["task_max_steps"], {"value": 8, "default": paths.DEFAULTS["task_max_steps"], "min": 1,
                                                  "max": 12, "unit": "steps", "group": "steps"})
        self.assertEqual((view["allowances"]["value"], view["allowances"]["default"]), ({}, {}))
        self.assertEqual(view["plan_hold"]["unit"], "bool")
        for key in tuning.TUNING:
            self.assertIn(key, paths.DEFAULTS, key)  # every key the page shows has a default in code

    def test_whitelist_is_the_contracts(self):
        self.assertEqual(set(tuning.KEYS), {
            "task_max_steps", "task_step_budget_usd", "step_timeout_s", "design_max_turns", "read_max_turns",
            "brief_max_words", "brief_timeout_s", "gauge_red_tokens", "gauge_yellow_tokens", "balance_margin",
            "cache_bonus", "budget_warn_at", "daily_budget_usd", "allowances", "plan_max_kb", "plan_max_parts",
            "plan_hold", "replan_auto", "prep_model", "brief_model", "review_model", "default_model", "kinds", "tiers",
            "user_name",
            "supervisor_mode", "supervisor_projects", "supervisor_model", "supervisor_stuck_model",
            "supervisor_debounce_s", "supervisor_parallel", "supervisor_timeout_s", "supervisor_stall_s",
            "supervisor_max_auto_steps", "supervisor_max_retries", "supervisor_work_usd", "supervisor_task_usd",
            "supervisor_day_usd"})


class NumbersTest(unittest.TestCase):
    def test_in_range_is_kept_and_whole_numbers_are_ints(self):
        clean, errors = check(task_max_steps=8.0, balance_margin=0.15, daily_budget_usd=0, plan_hold=True)
        self.assertEqual(errors, {})
        self.assertEqual(clean, {"task_max_steps": 8, "balance_margin": 0.15, "daily_budget_usd": 0, "plan_hold": True})
        self.assertIsInstance(clean["task_max_steps"], int)

    def test_reasons(self):
        clean, errors = check(balance_margin=0.6, task_max_steps=2.5, brief_max_words="500", plan_hold=1,
                              step_timeout_s=True, budget_warn_at=float("nan"))
        self.assertEqual(clean, {})
        self.assertEqual(errors, {"balance_margin": "between 0 and 0.5",
                                  "task_max_steps": "a whole number between 1 and 12",
                                  "brief_max_words": "a whole number between 100 and 2000",
                                  "plan_hold": "true or false",
                                  "step_timeout_s": "a whole number between 60 and 7200",
                                  "budget_warn_at": "a number between 0.1 and 2"})

    def test_a_huge_integer_is_refused_not_raised(self):
        """Plan 27 (B7): float(10**400) overflows; validate keeps its never-raises promise and gives the range."""
        clean, errors = check(task_max_steps=10 ** 400, budget_warn_at=-10 ** 400, daily_budget_usd=10 ** 400,
                              allowances={"opus": {"day_usd": 10 ** 400}})
        self.assertEqual(clean, {})
        self.assertEqual(errors, {"task_max_steps": "between 1 and 12", "budget_warn_at": "between 0.1 and 2",
                                  "daily_budget_usd": "between 0 and 1000",
                                  "allowances": "opus day_usd: between 0 and 100000"})

    def test_unknown_keys_and_empty_saves_are_refused(self):
        self.assertEqual(check(port=1)[1], {"port": "not a setting this page changes"})
        self.assertEqual(check(prices={})[1], {"prices": "not a setting this page changes"})
        self.assertEqual(tuning.validate({}, CFG), ({}, {"": "changes: an object of settings to save"}))
        self.assertEqual(tuning.validate([1], CFG)[1], {"": "changes: an object of settings to save"})

    def test_yellow_starts_under_red(self):
        self.assertEqual(check(gauge_yellow_tokens=300000)[1], {"gauge_yellow_tokens": "yellow must start under red"})
        self.assertEqual(check(gauge_red_tokens=100000)[1], {"gauge_red_tokens": "yellow must start under red"})
        self.assertEqual(check(gauge_yellow_tokens=100000, gauge_red_tokens=200000)[1], {})

    def test_models_of_the_passes(self):
        self.assertEqual(check(prep_model="sonnet", default_model="codex:gpt-6.1-sol")[1], {})
        self.assertEqual(check(brief_model="codex:gpt-6-luna")[1],
                         {"brief_model": "a Claude model: this pass runs on the Claude CLI"})
        self.assertEqual(check(default_model="codex:nope")[1], {"default_model": "unknown model: codex:nope"})
        self.assertEqual(check(review_model="claude-opus-9")[1], {"review_model": "unknown model: claude-opus-9"})

    def test_allowances(self):
        clean, errors = check(allowances={"opus": {"day_usd": 10, "month_usd": 150}, "kimi-k3": {}})
        self.assertEqual((clean["allowances"], errors), ({"opus": {"day_usd": 10, "month_usd": 150}, "kimi-k3": {}}, {}))
        self.assertEqual(check(allowances={"opus": {"day_usd": -1}})[1],
                         {"allowances": "opus day_usd: between 0 and 100000"})
        self.assertEqual(check(allowances={"opus": {"day_tokens": 1}})[1],
                         {"allowances": "opus: only day_usd, week_usd, month_usd"})
        self.assertEqual(check(allowances={"../x": {}})[1], {"allowances": "../x: not a model key"})
        self.assertEqual(check(allowances=[])[1], {"allowances": "an object: model key -> day_usd, week_usd, month_usd"})


class KindsTest(unittest.TestCase):
    def test_pins_are_kept_and_auto_is_dropped(self):
        clean, errors = check(kinds={"code": {"rung": "auto", "effort": "high"}, "test": {"rung": "codex:gpt-6-luna"},
                                     "scout": {"rung": "auto", "effort": "auto"}})
        self.assertEqual(errors, {})
        self.assertEqual(clean["kinds"], {"code": {"rung": "auto", "effort": "high"},
                                          "test": {"rung": "codex:gpt-6-luna", "effort": "auto"}})

    def test_reasons(self):
        self.assertEqual(check(kinds={"verify": {"rung": "opus"}})[1], {"kinds": "verify: set by the rule, not pinnable"})
        self.assertEqual(check(kinds={"fix": {"effort": "high"}})[1], {"kinds": "fix: set by the rule, not pinnable"})
        self.assertEqual(check(kinds={"nap": {}})[1], {"kinds": "unknown kind: nap"})
        self.assertEqual(check(kinds={"code": {"rung": "codex:nope"}})[1], {"kinds": "code: unknown model: codex:nope"})
        self.assertEqual(check(kinds={"code": {"effort": "huge"}})[1],
                         {"kinds": "code: effort: auto or low, medium, high, xhigh, max"})
        self.assertEqual(check(kinds={"code": {"model": "opus"}})[1], {"kinds": "code: rung and effort only"})
        self.assertEqual(check(kinds={"design": {"rung": "opencode:opencode-go/deepseek-v4.1-flash"}})[1],
                         {"kinds": "design: opencode: opencode-go/deepseek-v4.1-flash is not a think model"})
        self.assertEqual(check(kinds={"design": {"rung": "opencode:opencode-go/kimi-k3"}})[1], {})  # opus rank


class TiersTest(unittest.TestCase):
    def test_a_tier_is_normalized(self):
        clean, errors = check(tiers={"read": ["haiku", {"rung": "codex:gpt-6-luna", "effort": "high"}]})
        self.assertEqual(errors, {})
        self.assertEqual(clean["tiers"], {"read": [{"rung": "haiku", "effort": "auto"},
                                                   {"rung": "codex:gpt-6-luna", "effort": "high"}]})

    def test_reasons(self):
        self.assertEqual(check(tiers={"fast": ["haiku"]})[1], {"tiers": "unknown tier: fast"})
        self.assertEqual(check(tiers={"read": []})[1], {"tiers": "read: 1 to 12 rungs"})
        self.assertEqual(check(tiers={"read": ["haiku"] * 13})[1], {"tiers": "read: 1 to 12 rungs"})
        self.assertEqual(check(tiers={"read": ["haiku", "haiku"]})[1], {"tiers": "read 2: listed twice"})
        self.assertEqual(check(tiers={"write": ["sonnet", "codex:nope"]})[1], {"tiers": "write 2: unknown model: codex:nope"})
        self.assertEqual(check(tiers={"think": ["opus", "cmd:deepseek/deepseek-v4.1-flash"]})[1],
                         {"tiers": "think 2: cmd: deepseek/deepseek-v4.1-flash is not a think model"})
        self.assertEqual(check(tiers={"write": [{"rung": "sonnet", "effort": "max!"}]})[1],
                         {"tiers": "write 1: effort: auto or low, medium, high, xhigh, max"})
        self.assertEqual(check(tiers={"write": ["opus", "cmd:deepseek/deepseek-v4.1-flash"]})[1], {})  # D1 a, hard only


class SupervisorTuningTest(unittest.TestCase):
    def norm(self, path):
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def test_supervisor_mode_and_projects_round_trip(self):
        clean, errors = check(supervisor_mode="auto", supervisor_projects={"D:/work": "auto"})
        self.assertEqual(errors, {})
        self.assertEqual(clean, {"supervisor_mode": "auto", "supervisor_projects": {self.norm("D:/work"): "auto"}})
        self.assertEqual(check(supervisor_projects={"C:/other": "off"})[1], {})
        self.assertEqual(check(supervisor_projects={})[1], {})
        self.assertEqual(check(supervisor_mode="off")[1], {})
        self.assertEqual(check(supervisor_mode="turbo")[1], {"supervisor_mode": "off, suggest or auto"})
        self.assertEqual(check(supervisor_projects={"C:/nope": "auto"})[1],
                         {"supervisor_projects": "not a project listed in config.json: C:/nope"})
        self.assertEqual(check(supervisor_projects={"D:/work": "turbo"})[1],
                         {"supervisor_projects": "D:/work: off, suggest or auto"})
        self.assertEqual(check(supervisor_projects={"D:/work": "auto", "d:\\WORK": "off"})[1],
                         {"supervisor_projects": "d:\\WORK: listed twice"})
        self.assertEqual(check(supervisor_projects=[])[1],
                         {"supervisor_projects": "an object: project path -> off, suggest or auto"})

    def test_supervisor_models_refuse_external_and_higher_tiers(self):
        self.assertEqual(check(supervisor_model="haiku")[1], {})
        self.assertEqual(check(supervisor_stuck_model="sonnet")[1], {})
        self.assertEqual(check(supervisor_model="sonnet")[1], {"supervisor_model": "haiku only"})
        self.assertEqual(check(supervisor_model="opus")[1], {"supervisor_model": "haiku only"})
        self.assertEqual(check(supervisor_model="fable")[1], {"supervisor_model": "haiku only"})
        self.assertEqual(check(supervisor_model="codex:gpt-6-luna")[1], {"supervisor_model": "haiku only"})
        self.assertEqual(check(supervisor_stuck_model="haiku")[1], {"supervisor_stuck_model": "sonnet only"})
        self.assertEqual(check(supervisor_stuck_model="opus")[1], {"supervisor_stuck_model": "sonnet only"})

    def test_supervisor_numeric_bounds_and_zero(self):
        good = dict(supervisor_debounce_s=0, supervisor_parallel=4, supervisor_timeout_s=600,
                    supervisor_stall_s=7200, supervisor_max_auto_steps=0, supervisor_max_retries=0,
                    supervisor_work_usd=0, supervisor_task_usd=0, supervisor_day_usd=0)
        clean, errors = check(**good)
        self.assertEqual(errors, {})
        self.assertEqual(clean, good)
        for key, value in (("supervisor_debounce_s", 301), ("supervisor_parallel", 5),
                           ("supervisor_timeout_s", 9), ("supervisor_stall_s", 599),
                           ("supervisor_max_auto_steps", 13), ("supervisor_max_retries", 2),
                           ("supervisor_work_usd", 51), ("supervisor_task_usd", 11),
                           ("supervisor_day_usd", 101), ("supervisor_work_usd", float("nan")),
                           ("supervisor_parallel", 1.5)):
            self.assertIn(key, check(**{key: value})[1], (key, value))

    def test_mode_map_stay_out_of_legacy_numeric_view(self):
        self.assertIn("supervisor_mode", tuning.KEYS)
        self.assertIn("supervisor_projects", tuning.KEYS)
        view = tuning.view(CFG)
        self.assertNotIn("supervisor_mode", view)
        self.assertNotIn("supervisor_projects", view)
        for unit in (t["unit"] for t in view.values()):
            self.assertIn(unit, ("bool", "rung", "text", "steps", "s", "turns", "kb", "parts", "words", "tokens", "usd", "share"))
        self.assertEqual(check(task_max_steps=8)[1], {})  # unrelated number saves remain valid


class SetConfigTest(unittest.TestCase):
    def test_writes_the_keys_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"projects": ["x"], "tiers": {"write": ["sonnet"]}, "kinds": {"code": {}}}),
                            encoding="utf-8")
            paths.set_config(tmp, {"tiers": {"read": ["haiku"]}, "kinds": {}, "task_max_steps": 8})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"projects": ["x"], "tiers": {"write": ["sonnet"], "read": ["haiku"]}, "kinds": {},
                                    "task_max_steps": 8})  # tiers merge one level; kinds is replaced whole
            path.write_text("[1]", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.set_config(tmp, {"task_max_steps": 8})
            self.assertEqual(path.read_text(encoding="utf-8"), "[1]")
            path.unlink()
            paths.set_config(tmp, {"plan_hold": True})  # no file yet: only what was saved
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"plan_hold": True})


class NameTest(unittest.TestCase):
    """Plan 31: user_name is one line of text on the Tuning tab."""

    def test_the_name_is_collapsed_and_bounded(self):
        self.assertEqual(check(user_name="  Fred \t T.\n"), ({"user_name": "Fred T."}, {}))
        self.assertEqual(check(user_name=""), ({"user_name": ""}, {}))
        self.assertEqual(check(user_name="x" * 61)[1], {"user_name": "text of at most 60 characters"})
        self.assertEqual(check(user_name=7)[1], {"user_name": "text of at most 60 characters"})
        view = tuning.view(dict(CFG, user_name="Fred"))["user_name"]
        self.assertEqual((view["value"], view["default"], view["unit"], view["group"]), ("Fred", "", "text", "you"))


if __name__ == "__main__":
    unittest.main()

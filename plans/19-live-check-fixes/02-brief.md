# Task 2: The brief pass: three turns, never longer than what it compacts, open questions kept

> Contract: [README.md](README.md) 3.3 (D4 a). Finding A3.

**Files**
- Modify: `console/claude_cli.py` (`brief_command`), `console/compact.py`, `console/compact_prompt.md`
- Modify: `tests/test_claude_cli.py`, `tests/test_compact.py`, `tests/fake_claude.py` (a longer HANDOFF block)

## 2.1 What the live check showed (evidence)

- `error_max_turns` on 2 of 5 briefs, both the first brief of a task (chains of `20261012-122014-915f` and
  `20261012-124746-9a3e`). The code fallback ran, so the brief was the raw note.
- Reproduced 2026-10-12 with the real claude (haiku, `--tools ""`, `--max-turns 1`, `--json-schema`, the raw note
  of `20261012-124746-9a3e` step 2): three runs, all `success` with `num_turns: 2`, 0.0007 to 0.0035 USD each.
  A structured answer is a tool call plus its turn; the docs say the SDK re-prompts on a schema mismatch
  (code.claude.com/docs/en/agent-sdk/structured-outputs), and a re-prompt needs a turn that `--max-turns 1` does
  not leave. Hence `--max-turns 3`: the answer plus up to one re-prompt, still no tools.
- Briefs were longer than their raw note: `207 -> 249` words (step 2: it carried step 1's files forward),
  `166 -> 250` (step 3, the last: it carried the earlier brief). A rolling brief carrying the earlier brief is by
  design (plan 17 3.6b); adding past raw note plus earlier brief is not.
- One brief turned an open question into `(none)` and moved it to Next. The prompt said `questions (at most 5,
  only what blocks the next step)`, which invites dropping one.
- The brief prompt's `Task:` line is the 80-character title; one live brief spent a finding on "Task text is cut
  off". The task goal (Prep's prompt) names the task in full.

## 2.2 `console/claude_cli.py`

```python
def brief_command(exe: list, model: str, schema: dict) -> list:
    """Prep's command with no tools at all and three turns: the brief pass reads nothing and decides nothing. A
    structured answer takes 2 turns and a schema re-prompt one more (docs: agent-sdk/structured-outputs)."""
    cmd = prep_command(exe, model, schema)
    cmd[cmd.index("--tools") + 1] = ""
    return cmd + ["--max-turns", "3"]
```

`tests/test_claude_cli.py`: rename `test_brief_command_has_no_tools_and_one_turn` to
`test_brief_command_has_no_tools_and_three_turns`, assert `"3"`.

## 2.3 `console/compact.py`

```python
def words(text: str) -> int:
    return len(str(text or "").split())


def limit(raw: str, prev: str) -> int:
    """What a brief compacts: the raw note plus the earlier brief it carries forward (D4)."""
    return words(raw) + words(prev)


def budget(cfg: dict, raw: str, prev: str) -> int:
    """The word target the prompt asks for: 60 % of what it compacts, at least 60, at most brief_max_words."""
    return max(60, min(cfg["brief_max_words"], limit(raw, prev) * 6 // 10))


def _open(text: str) -> list:
    """The open questions of a note or a brief: the lines under `## Open questions` that are not a none."""
    lines = _sections(text).get("## Open questions", "").splitlines()
    out = [line.strip().lstrip("-* ").strip() for line in lines]
    return [q for q in out if q and q.strip("().").lower() not in ("none", "n/a", "")]


def check(block: str, max_words: int, raw: str = "", prev: str = "") -> str:
    """"" when the block has the four headings, fits max_words, is shorter than what it compacts and keeps the
    open questions; else the reason."""
    why = tasks.check_handoff(block)
    if why:
        return why
    n = words(block)
    if n > max_words:
        return f"over {max_words} words"
    if raw and n >= limit(raw, prev):
        return f"not shorter than what it compacts ({n} >= {limit(raw, prev)} words)"
    if (_open(raw) or _open(prev)) and not _open(block):
        return "dropped the open questions"
    return ""
```

- `build_prompt(task, step, next_step, prev_brief, raw, words_target=400)` substitutes `$task` =
  `redact.clip(task.get("goal") or task["title"], 400)` (replacing `$title`) and `$words` = `words_target`.
- `run_brief` computes `target = budget(cfg, raw, prev_brief)`, passes it to `build_prompt`, and calls
  `check(text, cfg["brief_max_words"], raw, prev_brief)`.
- `fallback` is unchanged (it keeps the raw note's questions as they are).

## 2.4 `console/compact_prompt.md` (final text)

```text
Compact the handoff note of a finished step into the brief the next step will read. The next step runs in a
fresh session and sees nothing else: keep what it needs, drop what it does not, carry forward from the earlier
brief what later steps still need. Do not add facts. Do not solve the next step.

Task: $task
Next step ($next_n of $m, $next_kind): $next_goal

Earlier brief (what the steps before already kept):
$prev

Raw handoff note of step $n ($kind):
$raw

Answer with the JSON object only, at most $words words in all: findings (short lines, file paths and line
numbers kept), files (the paths with what changed, the earlier brief's included), questions (every open
question of the raw note and of the earlier brief that is not answered yet, each in a few words; never drop one
and never move one into next), next (one line for the next step; keep a `Next model: m/e` note only if the raw
note had one).
```

## 2.5 Tests (`tests/test_compact.py`)

```python
    def test_check_rejects_a_first_brief_not_shorter_than_its_note(self):
        brief = compact.render(FIELDS)
        self.assertEqual(compact.check(brief, 400, RAW + " pad" * 40, ""), "")
        short_raw = "## Findings\nx\n## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\ngo"
        self.assertTrue(compact.check(brief, 400, short_raw, "").startswith("not shorter than what it compacts"))

    def test_check_lets_a_rolling_brief_carry_the_earlier_brief(self):
        prev = compact.render(dict(FIELDS, findings=["earlier step found " + "x " * 30]))
        brief = compact.render(dict(FIELDS, findings=FIELDS["findings"] + ["earlier step found it"]))
        self.assertGreater(compact.words(brief), compact.words(RAW))
        self.assertEqual(compact.check(brief, 400, RAW, prev), "")

    def test_check_rejects_a_brief_that_drops_open_questions(self):
        raw = RAW.replace("## Open questions\n- (none)", "## Open questions\n- Fred: green suite or no new failures?")
        raw += " pad" * 40
        dropped = compact.render(FIELDS)
        kept = compact.render(dict(FIELDS, questions=["Fred: green suite or no new failures?"]))
        self.assertEqual(compact.check(dropped, 400, raw, ""), "dropped the open questions")
        self.assertEqual(compact.check(kept, 400, raw, ""), "")

    def test_prompt_names_the_goal_and_a_word_target(self):
        task = make_task()
        task["goal"] = "Goal: " + "g" * 600
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW, 120)
        self.assertIn("Task: Goal: ggg", text)
        self.assertIn("at most 120 words in all", text)
        self.assertIn("never drop one", text)
        self.assertNotIn("$", text)
        self.assertEqual(compact.budget({"brief_max_words": 400}, "w " * 1000, ""), 400)
        self.assertEqual(compact.budget({"brief_max_words": 400}, "w " * 50, ""), 60)
```

`test_render_and_check` keeps its two-argument calls (no `raw`: the length rule is off). In
`test_run_brief_uses_the_fake` and `test_run_brief_falls_back_on_a_bad_answer`, `RAW` must stay longer than the
fake's brief (29 words): if it is not, lengthen `RAW`'s Findings in the test file (one more line), not the rule.

`tests/fake_claude.py`: `HANDOFF_BLOCK`'s Findings gets three lines (`add() is in calc.py:2`, `test_add in
tests/test_calc.py covers it and fails on a negative number`, `the callers in report.py and cli.py pass ints
only`), so a step's raw note (about 50 words with its head line) is longer than the fake brief and
`test_brief_runs_between_steps` keeps a real brief. Run the whole suite after this change.

## 2.6 Live check (Claude; about 0.01 USD in all)

After the tests pass: a scratch script (scratchpad, not the repo) runs `compact.run_brief` with the real claude
on the raw note of `~/.claude/console/tasks/20261012-124746-9a3e/steps/02-scout.md` 5 times (`cfg` from
`paths.load_config()`, exe from `claude_cli.find_exe`). Expected: 5 of 5 without fallback, each brief shorter than
the note. Write the counts and the cost in the PLAN.md History line. If a fallback still says `error_max_turns`,
stop and tell Fred before raising the cap further.

## 2.7 Order (one commit per step)

1. 2.2 test change, fails; code; suite; commit `fix: the brief pass gets three turns (plan 19 Task 2)`.
2. 2.5 check tests, fail; `words`, `limit`, `_open`, `check`; suite (see the fake note); fake block; commit.
3. Prompt test, fails; `budget`, `build_prompt`, prompt text, `run_brief`; suite; commit.
4. 2.6 live check; PLAN.md History line; commit.

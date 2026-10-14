# Plan 23: Handoff everywhere. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> section 5 (the context view and the handoff: mechanism 1, auto handoff for a long single session; mechanism 2,
> one wrap-up document everywhere; the drift guards; D-5) and 5.1 (facts under the brief; items 1, 4 and 5:
> `--strict-mcp-config` and `--tools` per kind, `read_max_turns`, the goal cut and lessons by kind). The interface doc
> [../../design/brainstorm/2026-10-13-interface.md](../../design/brainstorm/2026-10-13-interface.md) section 3 (the
> HANDED OFF session card), 4 (the Window runs group, ID-2), 6.1 (the `HANDOFF block` chip of a chat turn), 7 (the
> Task page's Handoff fold with its Facts, the auto hand off box), 12 (ID-2, ID-5, ID-9). Mock:
> [../../design/rework/locked/cells-board.html](../../design/rework/locked/cells-board.html): `fold`, `headingBlock`,
> the Task page view `tpage` (`taskPageHtml`, the `handoff` fold), the list's HANDED OFF card (`listHtml`),
> `settingsHtml` (the `Window runs` fold), the `.hchip` of `chatHtml`. Contracts this plan builds on:
> [../17-tasks/README.md](../17-tasks/README.md) (3.3 chain lines, 3.6b the brief) as plan 19 left it,
> [../05-harnesses/README.md](../05-harnesses/README.md), [../24-plan-and-replan/README.md](../24-plan-and-replan/README.md)
> 3.5. Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
>
> Build order: 5, 24, 23, 18, 26, 25. This plan's start state is "plan 24 placed". It is written against today's code
> (plan 22 placed, 326 tests on Linux, 328 on Fred's Windows) plus the contracts of plans 5 and 24; every place where
> one of them edits the same lines first has a **Lands on** line in the task file (3.13 lists them).

Status: written 2026-10-14, not started. Tasks 1 to 5 were run in a scratch copy of the working tree (today's code,
plans 5 and 24 not placed, so their lines are added there as their contracts pin them): the full suite gives 356
tests, 352 OK and the 4 failures the Linux baseline already has (`test_tray` import, `test_redact
test_path_tools_are_relative_to_cwd`, `test_usage test_sums_each_local_day_once_per_message`, `test_window
test_place_is_kept_only_while_on_a_screen`), so 30 new tests (Linux 326 -> 356; Fred's Windows 328 -> 358, plus
what plans 5 and 24 add first). The commit points were run too, each with the same 4 baseline failures only: after
Tasks 1 and 2, 340 tests; after Tasks 1 to 4, 350. The final code of Tasks 1 to 5 is in the task files, generated
from that run. Task 6
(window) is guided, not run. Open decisions D1 to D5: the plan is written for (a) on each.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-handoff-block.md](01-handoff-block.md) | The six-heading HANDOFF block: `tasks.HEADINGS`, `check_handoff(old_ok)`, the step prompt rewritten (harness-neutral wording, "What the earlier steps left you:", the `$lessons` slot, the goal cut to 600 after step 1), `tasks.received`, `prompt_goal`, `lessons_for`, the facts file helpers, the tools per kind (D3); `brief.build("next")` takes the block of a skill note; the dotclaude `session-handoff` skill ends with the block; the fake claude's block | nothing |
| 2 | [02-brief-pass.md](02-brief-pass.md) | The brief pass on six headings: `compact.BRIEF_SCHEMA` with `goal` and `troubleshooting`, `restore` (D2), `checks` with the two continuity checks (D5), findings cut first, the fallback, `brief_meta`; `compact_prompt.md`; `brief_max_words` 500. Tasks 1 and 2 are one commit | 1 |
| 3 | [03-facts.md](03-facts.md) | `console/facts.py` (numstat snapshots, the step's own lines (D1), the last test command from the stream, the facts text), `claude_cli.git_snapshot`, the fake claude's `TESTS-OK` / `TESTS-FAIL` | 1 |
| 4 | [04-lean-steps.md](04-lean-steps.md) | `--strict-mcp-config` on every step run (`claude_cli.run_command`, `runs.start` limits), config `read_max_turns` 15 and `handoff_auto` false, `paths.set_setting` | nothing |
| 5 | [05-service.md](05-service.md) | `Hub.start_step` (facts and lessons in the prompt, `git_base`, `read_max_turns`, strict MCP), `Hub._facts` (end_commit, facts, the facts file), `start_brief` passes the touched paths, `_brief_done` writes `brief_meta`; `task_row` and `GET /api/task` additions; `Hub.auto_steps` auto handoff at red; `Session.auto_handoff`; `POST /api/setting`; `/api/config` `handoff_auto` | 1 to 4 |
| 6 | [06-window.md](06-window.md) | Task page: the Handoff fold (six headings, cut lines, Facts fold) in place of the brief block; the `HANDOFF block` chip on a step's chat turn; the HANDED OFF card; the Window runs group in the picker's settings band | 5 |
| 7 | [07-live-check.md](07-live-check.md) | Fred's live check | 6 |
| 8 | [08-close.md](08-close.md) | PLAN.md, the design docs, CLAUDE.md line, this folder's state | 7 |

Tasks 1 to 5 are Python, tests first. Tasks 1 and 2 share one commit (the six headings and the brief pass that reads
them cannot be apart: a four-heading brief fails the six-heading check). Tasks 3, 4 and 5 end with their own commit.
Task 6 is browser code (`node --check web/app.js`, the full suite, headless Chromium at 400 and 340 px with the fake
claude). Task 7 is Fred's: Claude never starts a run. Other chats edit `web/app.js`, `PLAN.md` and the design docs in
parallel: anchored edits only, stage only this plan's lines.

## 2. Decisions

### 2.1 Taken (not reopened here)

| What | Source |
|---|---|
| One HANDOFF format for step, brief and skill, six headings: Goal, Findings, Files touched, Troubleshooting, Open questions, Next | brainstorm 5 mechanism 2, D-5 (Fred, 2026-10-13: "yes, with Goal and Troubleshooting in the block") |
| The brief keeps the six headings; Goal and Troubleshooting carried whole, Findings cut first; never longer than what it compacts | brainstorm 5 |
| Two continuity checks in the brief check: names a file of the earlier Files touched when that list is non-empty; no path the task's steps never touched | brainstorm 5, drift guards |
| `brief_max_words` 400 -> 500 | brainstorm 5; interface ID-5 |
| Facts under the brief: the git diff stat from the step's start to its end, the last test command's failing lines, never compacted | brainstorm 5.1 |
| `--strict-mcp-config` and `--tools` per kind on steps; `read_max_turns` 15 on scout and search; the goal in a step prompt cut to 600; lessons only for the step's own kind | brainstorm 5.1 items 1, 4, 5 |
| Auto handoff at red for window runs and VS Code chats, off by default (`handoff_auto`), a VS Code chat forked first; switched in a Window runs group next to Harnesses | brainstorm 5 mechanism 1; interface 4, ID-2 |
| Window words: Received / Handoff in the UI; "note" and "brief" stay code names; a handoff has no word cells | interface ID-9, ID-5 |

Pinned here, so the executor decides nothing (not open decisions):

- Step 1 reads the goal whole (up to `GOAL_MAX` 6000: it has no handoff yet); every later step reads it cut to
  `PROMPT_GOAL_MAX` 600 characters, ending in `…`.
- Lessons reach a step prompt only for the step's own kind, the newest `LESSONS_IN_PROMPT` 5 of its project; a
  chat's lesson (kind `chat`) reaches no step.
- The facts are read and written in `Hub._ended` when the step ends (the git tree is the step's exactly then), next to
  the note, not after the brief pass; the brief pass never reads the facts text, only the paths it lists (D5).
- Auto handoff: any non-task session whose context is at or over `gauge_red_tokens` when a turn ended after the
  service started (window runs resume in place; VS Code and terminal chats are forked, as `Hub.pull` already does);
  once per session (`Hub.auto_handed`); a red session in that list takes no Escalate or de-escalate.

### 2.2 Open (the docs do not settle them). Recommended option first; the plan is written for it

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | What "the step's diff" counts. A step may commit or not, and an earlier step may leave uncommitted lines. | (a) a snapshot of `git diff --numstat <base>` plus the untracked files at the first attempt's start and again at the end, both against the same base commit; the facts are the files whose counts changed (the step's own lines, committed or not, untracked files included; a reverted file counts as touched with 0 and 0); (b) `git diff --stat <start commit>..<end commit>` only (empty for a step that does not commit, which no step does today) | (a) |
| D2 | A brief pass that paraphrases the Goal or drops a Troubleshooting line. | (a) code puts the carried Goal (the raw note's, else the earlier brief's) and every Troubleshooting line (the earlier brief's, then the raw note's) back whole before the checks (`compact.restore`); the checks still run and catch a bug; (b) fail the check and use the code fallback | (a) |
| D3 | `--tools` per kind: today draft, proofread, edit, code, document, debug and fix pass none (the default set, which on Linux and macOS leaves out Glob and Grep, and includes every other built-in tool). | (a) an explicit list on every kind: draft, proofread, edit, document `Read,Edit,Write,Grep,Glob`; code, debug, fix `Bash,Read,Edit,Write,Grep,Glob`; scout, search, explain, test, design, verify unchanged; replan (plan 24) keeps `""` (it has no session); (b) keep the default set on the edit kinds and add only `--strict-mcp-config` | (a) |
| D4 | The `Next model:` hint once steps run on other CLIs (plan 5). | (a) keep `Next model: <tier>/<effort>` with the rank words `haiku`, `sonnet`, `opus` (described in the prompt as cheapest to strongest, whatever CLI runs the step); `tasks.next_hint` unchanged; (b) the job tier words `read`, `write`, `think`, which need plan 18's `TIER_RANK` and a `next_hint` change | (a) |
| D5 | What "a path the task's steps never touched" is. | (a) every path the brief names must appear in the raw note, the earlier brief, or a facts file's diff stat of steps 1 to n (a folder prefix may differ: `tasks.py` matches `console/tasks.py`); (b) only the Files touched lists of the notes | (a) |

A different answer changes only the lines the task files mark `D1` ... `D5`.

## 3. The contract

### 3.1 Files and places

```
console/tasks.py             HEADINGS (six), OLD_HEADINGS, check_handoff(old_ok), READ_CAPPED, PROMPT_GOAL_MAX,
                             LESSONS_IN_PROMPT, FIRST_STEP, facts_file / write_facts / read_facts, lessons_for,
                             received, prompt_goal, step_prompt(... facts, lessons), RULES tools (D3)
console/step_prompt.md       rewritten (Task 1)
console/compact.py           rewritten (Task 2)
console/compact_prompt.md    the answer paragraph (Task 2)
console/facts.py             new (Task 3)
console/claude_cli.py        run_command(strict_mcp), git_snapshot, UNTRACKED_READ_MAX
console/runs.py              start(strict_mcp); limits["strict_mcp"]
console/paths.py             DEFAULTS read_max_turns, handoff_auto, brief_max_words 500; SETTINGS; set_setting
console/brief.py             build("next"): a skill note's block alone
console/state.py             Session.auto_handoff; row "auto_handoff"; group "needs" while handed off by itself
console/server.py            Hub.start_step, _facts, start_brief, _brief_job, _brief_done, pull(auto), auto_steps;
                             task_row; Handler _step_texts, _setting, /api/config
dotclaude/skills/session-handoff/SKILL.md   steps 6 and 7: the exit line, then the HANDOFF block ends the message
~/.claude/console/tasks/<id>/steps/NN-<kind>.facts.md   the facts text (3.4), masked, never compacted
```

`tasks.clear(home, task, keep_last=True)` keeps the last good step's facts file with its note and brief.

### 3.2 The HANDOFF block (`tasks.check_handoff`)

```text
HANDOFF
## Goal
## Findings
## Files touched
## Troubleshooting
## Open questions
## Next
END HANDOFF
```

Reasons, the first failure wins (unchanged wording where the rule is old): `missing: ## X` (headings checked in the
order above), `headings out of order`, `Goal is empty`, `Findings is empty`. `check_handoff(block, old_ok=True)`
(read paths only: `brief.build("next")`) checks the four headings of a note from before plan 23 when the block has
neither `## Goal` nor `## Troubleshooting`; a block with either is checked on all six. The step's own block (Hub._ended)
and the brief check use `old_ok=False`. `tasks.next_hint` and `tasks.lesson_of` read the Next section as today; a
`Next model:` line keeps `haiku|sonnet|opus` (D4).

### 3.3 The brief pass (`compact.run_brief`)

- Schema `BRIEF_SCHEMA`: `{"goal": str, "findings": [str], "files": [str], "troubleshooting": [str],
  "questions": [str], "next": str}`, all required. `_fields_ok` needs the four lists and the two strings.
- After the answer: `restore(fields, raw, prev)` (D2 a), `render` (the six headings; the goal keeps its lines; an
  empty list is `- (none)`), then `checks`.
- `checks(block, max_words, raw, prev, touched) -> [{"name", "ok", "why"}]`, in this order, all of them always run:

| name | why when it fails |
|---|---|
| `headings` | the `check_handoff` reason |
| `words` | `over 500 words` (the configured number) |
| `shorter` | `not shorter than what it compacts (N >= M words)` |
| `questions` | `dropped the open questions` |
| `goal` | `cut the Goal` (a carried Goal line not in the brief's Goal) |
| `troubleshooting` | `cut the Troubleshooting` |
| `continuity` | `names no file of the earlier Files touched` (the earlier brief's list had a path, the brief names none of them) |
| `paths` | `names a path no step touched: <path>` (D5) |

  The last four run only when `raw` is given (the window and the tests may check a text alone).
- `over ...` or `not shorter ...` as the first failure: `cut` drops the last findings until it fits and the checks run
  again; any other failure, a CLI error or a malformed answer: `fallback(prev, raw)` (the carried Goal, the raw
  Findings cut at 1500 characters with `[cut]`, the raw Files touched then the earlier brief's, the carried
  Troubleshooting, the raw Open questions, the raw Next or else the earlier brief's).
- Returns `{"text", "cost", "words", "model", "cut": [finding items left out], "fallback": "" | reason, "checks",
  "turns"}`. `brief_meta(res, raw)` turns it into `s["brief_meta"]` (3.4).
- `touched` = every path `facts.files_in` reads from the facts files of steps 1 to n (D5 a).

### 3.4 Per-step fields (task.json; read with `.get`, `STEP_KEYS` unchanged)

```json
{"end_commit": "9b02f11c...",
 "git_base": {"commit": "c41e2a7d...", "files": {"console/tasks.py": [2, 1]}},
 "facts": {"files": 2, "plus": 34, "minus": 1, "tests": "23 OK"},
 "brief_meta": {"raw_w": 260, "sent_w": 230, "cut": ["finding 7 ..."],
                "checks": [{"name": "headings", "ok": true, "why": ""}],
                "by": "haiku", "cost": 0.004, "turns": 1, "fallback": ""}}
```

- `end_commit`: `git rev-parse HEAD` in the project folder when the step's note is written (`Hub._facts`); `""` without
  git.
- `git_base` (internal, not in `task_row`): set once, before the first attempt's run starts; `files` is None when git
  cannot tell (no repository, no commit). A retry keeps it, so the facts of a retried step count both attempts.
- `facts.tests`: `""` (no test command ran), `"23 OK"` / `"OK"`, `"FAIL <first failing line>"` (150 characters).
- `brief_meta` of step n is what step n + 1 received: `by` is the brief model, or `code` when the fallback ran;
  `fallback` its reason; `cut` the finding items left out (by `cut` or by the fallback's Findings cut).

The facts text, `steps/NN-<kind>.facts.md` (`facts.text`, masked by `tasks.write_facts`):

```text
git diff --stat c41e2a7..working tree
 console/tasks.py    | +12 -3
 tests/test_tasks.py | +40 -0
2 files changed, +52 -3
Tests: py -m unittest discover -s tests
Ran 23 tests in 0.412s
OK
```

The head says `<base7>..<end7>` when the step committed, `..working tree` when HEAD did not move; at most 30 file
lines then ` ... and N more`; `no file changed`; a failing run keeps its failing lines (at most 20: `FAIL:`,
`ERROR:`, `E ...`, a line naming an Error or Exception, `N failed`); a passing run its summary lines (`Ran N tests`,
`OK`, `N passed`, `Tests:`). Without git: `git: no repository here, or no start commit`. No test command: `Tests: none
ran in this step`; a harness whose stream the service cannot read (plan 5's codex, opencode, cmd): `Tests: not read
(this CLI's stream carries no tool result the service reads)`.

### 3.5 What a step prompt carries (`console/step_prompt.md`, `tasks.step_prompt`)

`tasks.step_prompt(task, step, prev_note, retry_reason="", special="", plan="", part="", facts="", lessons=())`.
In order: the intro; `Task:` and the goal (`prompt_goal`); `Step n of m: kind. goal`; `$special`; `$retry` (ends
`Start again from the handoff below.`); `$plan` (plan 24); `What the earlier steps left you:` then `$prev` =
`tasks.received(prev_note, facts)` (the previous brief, then a blank line, `Facts the service read when that step
ended (git and its last test run, not compacted):` and the facts text; `This is the first step: there is no handoff
note yet.` for step 1); `$lessons` (`Lessons from earlier <kind> steps in this project (use one only where it
applies):` and `- <day>: <sentence>` lines); `$part` (plan 24); the rules (harness-neutral: `Work alone: read what you
need yourself, as little as the step needs, and do not hand the work to another agent.`); the six-heading template;
`END HANDOFF` last.

### 3.6 Lean steps

| Kind | `--tools` (D3 a) | `--max-turns` |
|---|---|---|
| scout | `Read,Grep,Glob` | `read_max_turns` 15 |
| search | `Read,Grep,Glob,WebFetch,WebSearch` | `read_max_turns` 15 |
| draft, proofread, edit, document | `Read,Edit,Write,Grep,Glob` | none |
| code, debug, fix | `Bash,Read,Edit,Write,Grep,Glob` | none |
| explain | `Read,Grep,Glob` | none |
| test, verify | `Bash,Read,Grep,Glob` | none |
| design | `Read,Grep,Glob,WebFetch,WebSearch` | `design_max_turns` 30 (plan 24) |

Every Claude step run adds `--strict-mcp-config` (no `--mcp-config`: no MCP server loads; `--tools` does not cover MCP
tools, code.claude.com/docs/en/cli-reference, checked 2026-10-14). `runs.start` keeps it in `limits["strict_mcp"]`, so a
STOP answer or a retry that resumes the session keeps it. Window runs, Prep, the brief pass and the rules review are
unchanged (Prep already passes the flag).

### 3.7 Auto handoff (D-5 mechanism 1)

| State seen (each `Hub.auto_steps` pass) | Result |
|---|---|
| `handoff_auto` on; a session with no task; `ctx_tokens >= gauge_red_tokens`; state `replied`, `idle`, `verified` or `verify_failed`; no handoff running; not in `Hub.auto_handed`; its last turn ended at or after `Hub.auto_since` | `Hub.pull(sid, "handoff", auto=ctx_tokens)` (Hub.levers decides, the cold-cache rule holds); a window run resumes, a VS Code or terminal chat is forked; on 200 the sid joins `auto_handed`; no Escalate or de-escalate for it this pass |
| the handoff run's `run_started` carries `auto_handoff` | `Session.auto_handoff = tokens` on the session it hands off (the window run itself, or the forked chat's parent, or the PASS chat's `handoff_of`); every other `run_started` of that session sets it to 0 |
| the run ended `success` | `handed_off` (as today); the row's `group` is `needs` while `auto_handoff` and `handed_off` and not ended |
| Fred: Start next chat on the HANDED OFF card | the task box is seeded with `/api/brief?kind=next` as today, then `POST /api/done` (`marked_done` sets `auto_handoff` 0: the card leaves Needs you) |

Row field: `"auto_handoff": int` (0 or the tokens). Not for task steps (a chain's step never hands off; its red gauge
ends in the plan 17 retry).

### 3.8 Routes and rows

- `GET /api/task?id=` gains `notes`, `briefs`, `facts`: `{"<n>": text}` for every step that has one (string keys;
  absent = none), next to `note`, `brief`, `handoff`.
- `task_row` steps gain `end_commit` (str), `brief_meta` (dict or null), `facts` (dict or null).
- `GET /api/config` gains `handoff_auto` (bool).
- `POST /api/setting {key, value}` through `guard.py`: `paths.set_setting` (whitelist `paths.SETTINGS =
  ("handoff_auto",)`, a bool only); 400 with the reason (`not a setting: brief_on`, `handoff_auto takes true or false`,
  `cannot read <path>: fix it by hand`); 200 `{key, value}`; the live config takes it at once (`hub.cfg[key]`, the
  stream version bumps).
- The chain's brief line counts the cut findings: `brief: 260 -> 230 words, $0.00, cut 2 findings`.

### 3.9 Config keys (`console/paths.py` DEFAULTS)

| Key | Default | Meaning |
|---|---|---|
| `brief_max_words` | 500 (was 400) | the brief's cap; it never exceeds what it compacts |
| `read_max_turns` | 15 | `--max-turns` of a scout or search step (replaces plan 5's `READ_MAX_TURNS` constant) |
| `handoff_auto` | false | hand off a red window run or chat by itself; the Window runs switch writes it |

### 3.10 Hard rules

- `cc_events.py` is not touched. The service writes only `~/.claude/console/` (or `CC_CONSOLE_HOME`); `git_snapshot`
  reads (`git diff --numstat`, `git ls-files --others --exclude-standard`, file sizes) and writes no git object, index
  or file. The facts text is masked like a note.
- The facts are never compacted, cut by the brief pass or shown to it; the brief pass gets their path list only.
- A VS Code or terminal chat is only ever forked, never resumed in place; `Hub.levers` alone decides whether the auto
  handoff may run. The auto handoff never runs on a task step.
- `paths.set_setting` writes config.json only, one whitelisted boolean, every other key as written. Code never edits
  `~/.claude/settings.json`; the dotclaude skill edit is Fred's copy to `~/.claude`.
- No emojis or em-dashes in any prompt or skill text.

### 3.11 Drift guards for the executor

- `tasks.HEADINGS` is the one list of headings; `compact._sections`, `render`, `fallback`, the window's
  `handoffSections` and the dotclaude test read it or match it.
- `compact.checks` is the only validator of a brief; `run_brief` never parses the brief another way.
- The service never parses a facts text except through `facts.files_in`.
- `old_ok=True` only on read paths; a step's own block and a brief are checked on six headings.
- The fake claude answers from words in the prompt only (3.12); no test runs the real CLI or touches the user's git.
- `s["git_base"]`, `s["facts"]`, `s["end_commit"]`, `s["brief_meta"]` are read with `.get` everywhere.

### 3.12 The fake claude's words (`tests/fake_claude.py`)

| Word | Reply |
|---|---|
| `HANDOFF-OK` | the six-heading block (Goal `Fix add() in calc.py; this step: find add() and its callers`, Troubleshooting `- (none)`) |
| `TROUBLE` (with HANDOFF-OK) | the block's Troubleshooting is `- py -3.12 fails here: use py -3.14` |
| `TESTS-OK` / `TESTS-FAIL` | before the reply, a Bash `tool_use` (id `toolu_test`, command `py -m unittest discover -s tests`) and its `tool_result` (`Ran 23 tests ... OK`, or one `FAIL: test_add` with `is_error`) |
| brief pass | the schema answer gains `goal` `Fix add() in calc.py` and `troubleshooting` []; `HUGE` gives one 550-word finding |

### 3.13 Where this plan lands on plans 5 and 24

| Plan 23 task | Lands on | What |
|---|---|---|
| 1 | plan 24 Task 1 | `step_prompt.md` keeps `$plan` and `$part`; the anchor "Handoff note of the previous step:" becomes "What the earlier steps left you:" (plan 24's `test_step_prompt_carries_the_plan_and_the_part` changes its anchor); `tasks.step_prompt` keeps `special`, `plan`, `part` and adds `facts`, `lessons` |
| 1 | plan 24 Task 2 | `replan.note_block` writes the six headings |
| 1 | plan 5 README 5 | the harness-neutral rule line and Next model wording plan 5 left for this plan |
| 2 | plan 24 Task 2 | `compact._ask(..., schema, info=None)`: plan 24 added `schema`; plan 23 adds `info` (the turns); `_fields_ok` checks the six fields |
| 4 | plan 5 Task 4 | `strict_mcp` rides in the Claude adapter's `claude_only` dict next to `tools` and `disallow` |
| 5 | plan 5 Task 5, plan 24 Task 3 | `Hub.start_step`'s prompt and `max_turns` lines as those plans left them; `read_max_turns` replaces `READ_MAX_TURNS` |
| 6 | plan 24 Task 4 | `drawTask`: the brief block becomes the Handoff fold below the Plan row |

## 4. Verification at the end of every task

- `py -m unittest discover -s tests` all OK; the count is in the commit message (Linux scratch: 356 with plans 5 and
  24 absent; on Fred's machine add the tests plans 5 and 24 placed).
- Tasks 1 to 4: each module's new tests fail as written before the code and pass after it.
- Task 5: `tests/test_server.py` runs the fake claude on a `CC_CONSOLE_HOME` temp folder: facts on a temp git repo
  (`git init` in the test's project folder), `brief_meta`, the carried Troubleshooting, lessons by kind, auto handoff of
  a window run and of a VS Code chat, `POST /api/setting`.
- Task 6: `node --check web/app.js`; headless Chromium at 400 and 340 px on the fake runs: the Handoff fold closed and
  open, a cut line, the Facts fold (FAIL in red and open), the HANDED OFF card, the Window runs switch; no console
  errors.
- Task 7: Fred's live run (07-live-check.md).

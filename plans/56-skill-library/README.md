# Plan 56: Skill library. A step gets the skills that fit its work and nothing else. Guided implementation plan

> Design: [../44-supervisor/BRAINSTORM.md](../44-supervisor/BRAINSTORM.md) sections 14 and 15 (D14 a, D15 b, D16 a,
> D17 a, D18 no limit, taken by Fred 2026-10-17).
> Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
> Lands on plans 17 (chain), 23 (handoff), 24 (plan), 28 (kind files and step folders), 36 (next step), 44 (supervisor),
> 47 (planner). The window task depends on plan 55 (`../55-autopilot-ui/`, being written 2026-11-07).

Status: **written 2026-11-07, plan only, decisions open for Fred** (section 5; each is written for its recommended
option (a), the task files mark the lines another answer changes). Baseline `9b6f988` (1167 tests OK). Nothing is
implemented and no product file was touched by writing this plan.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-library.md](01-library.md) | `console/skills.py`: the folder, `ensure` (seeds), the hand-edited `index.json`, the validated registry, the two seed skills, `tests/test_skills.py` | none |
| 2 | [02-selection.md](02-selection.md) | `skills.pick` / `resolve` (pure), the tags and files a step is about, the golden table | 1 |
| 3 | [03-enforcement.md](03-enforcement.md) | the `$skills` slot, `skills.md`, `--disable-slash-commands` on task steps, `Hub.start_step`, received.md and chain lines, the handoff-contract and migration tests | 1, 2 |
| 4 | [04-tags.md](04-tags.md) | Prep's `tags`, the design step's `Tags:` line, `task["tags"]` | 2, 3 |
| 5 | [05-supervisor.md](05-supervisor.md) | the `skills` field of `add_next_step`, the digest block, the dispatch and its audit | 3 |
| 6 | [06-fred-picks.md](06-fred-picks.md) | Fred's pick on a Prep step row and on Add next step (`skills` in the request bodies, the preview preset) | 3, 5 |
| 7 | [07-routes.md](07-routes.md) | `GET /api/config` `skills`, `GET` and `POST /api/skill` | 1 |
| 8 | [08-window.md](08-window.md) | the data contract of the chip, the Received tab, the multi-selects and the Skills tab. **Depends on plan 55.** Contract only, no design | 4, 6, 7, plan 55 |
| 9 | [09-live-check-close.md](09-live-check-close.md) | Fred's live check on all four CLIs, docs, CLAUDE.md line, PLAN.md row | 1-8 |

Tests first in every task, one commit per task, `py -m unittest discover -s tests` at each boundary (about 10 minutes:
run it in the background and read the finished output), `node --check web/app.js` after any web change. Other chats edit
`PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, `web/app.js` and `console/__main__.py` in parallel: anchored edits, stage
explicit paths, stage only this plan's hunks (for `__main__.py`, whose one line is in Task 1, and CLAUDE.md: `git hash-object -w` plus `git update-index --cacheinfo`, since `git add -p` is interactive). Plan numbers
collide between chats: run `ls plans` before any new plan file.

## 1. Goal and scope

Steps should get the skills that fit their work and nothing else. Today a task step is one `claude -p` that passes
`--disallowedTools Agent`, `--tools`, `--strict-mcp-config`, caps and `--session-id`, and nothing about skills, so every
personal skill in `~/.claude/skills/` and every project skill in `<project>/.claude/skills/` puts its description in
every step's context whether the step needs it or not (`console/claude_cli.py:71`). Prep, the planner and the brief pass
already pass `--disable-slash-commands`.

This plan adds the Console's own library, `~/.claude/console/skills/`, picks skills by code from the step's kind, tags
and files, lets the supervisor and Fred add or override, inlines the chosen bodies whole in the step prompt, saves them
as `skills.md`, and turns Claude's own skill loading off for task steps. A step pays only for what was picked.

**Out of scope (checked against BRAINSTORM 13 and the plan 44 non-goals):**

- No on/off setting, no count limit and no size limit (D18): kind, tags, paths and `always` alone decide; nothing is
  trimmed, cut or refused for size by the library. The only size bounds are the transports' own (Command Code's
  argv cap, section 2; the window's request body of 256 KB, Task 7).
- No `--add-dir` staging mode and no `skills_load` setting (D5, recommended out).
- No skills for chats (`chat_task`, a chat-kind step), Prep, the planner, the brief pass, the replan pass, the rules
  review or the supervisor pass. A chat is Fred's session and keeps his personal skills; the passes already run with
  `--disable-slash-commands`.
- No move of `session-handoff` or `route-model` into the library (D2): they stay real Claude skills in `~/.claude/skills`.
- No deleting a skill from the window (the folder is deleted by hand; the registry then lists the entry as `no SKILL.md`).
- No reading of any file of a skill folder but `SKILL.md`: a skill is one self-contained file.
- Nothing is written in a project folder or outside `~/.claude/console/` (the CLAUDE.md data rule). The pointer
  entries of 3.2 only read `~/.claude/skills/<name>/SKILL.md`.
- No edit of `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.commandcode/settings.json`, `~/.codex/config.toml`
  or any other CLI's config or skills folder.

## 2. Facts checked 2026-11-07

**Docs (WebFetch, read today):**

- `--disable-slash-commands`: row in https://code.claude.com/docs/en/cli-reference, "Disable all skills and commands
  for this session", example `claude --disable-slash-commands`. It sits in the flag table with the print-mode flags
  (the Console's Prep and brief commands already pass it with `-p`, `console/claude_cli.py:50`, and run live).
- Unknown frontmatter: https://code.claude.com/docs/en/skills, "Claude Code ignores a field it doesn't recognize
  without reporting an error". A SKILL.md may therefore stay a plain Claude skill; the Console keeps its own fields in
  `index.json`, not in the file.
- Hiding: same page, "`disable-model-invocation: true` ... removes the skill from Claude's context entirely", and
  `skillOverrides` in settings. Neither is used (settings are Fred's; the flag above does the whole job for a step).
- Discovery on Claude: personal `~/.claude/skills/`, project `.claude/skills/` (also every parent up to the repository
  root), nested `<subdir>/.claude/skills/`, plugins, `--add-dir` folders.
- Command Code: https://commandcode.ai/docs/reference/cli, `--no-skills`: "Skip skill discovery; paths given via
  `--skill` still load."
- Codex: https://learn.chatgpt.com/docs/build-skills (the old developers.openai.com/codex/skills redirects there).
  Locations: `$CWD/.agents/skills` up to the repo root, `$HOME/.agents/skills`, `/etc/codex/skills`, bundled system
  skills. The only off switch the page names is config: `[[skills.config]]` entries with `enabled = false` in
  `~/.codex/config.toml`, and `[skills.bundled] enabled = false` in a trusted `.codex/config.toml`. The page names no
  CLI flag and does not say whether `codex exec` loads skills.
- OpenCode: https://opencode.ai/docs/skills/. Locations: `~/.config/opencode/skills`, `~/.claude/skills`,
  `~/.agents/skills`, `.opencode/skills`, `.claude/skills`, `.agents/skills`. The `skill` permission action with `deny`
  "Hides matching skills from the model and rejects loading". The page documents no environment variable and no way to
  turn the `.claude/skills` compatibility off. https://opencode.ai/docs/permissions/ lists `skill` as an action with the
  skill id as resource and does not document `OPENCODE_PERMISSION`.

**What the Console does per harness after this plan (no flag is invented):**

| Harness | Skill text | Native skill loading |
|---|---|---|
| Claude | inlined in the prompt (stdin) | off for task steps: `--disable-slash-commands` (new, 3.6) |
| Command Code | inlined in the prompt (argv, `CMD_PROMPT_MAX` 30,000 characters, D4) | already off: the adapter passes `--no-skills` on every run (`console/harness/cmd.py:44`); unchanged |
| Codex | inlined in the prompt (stdin) | not switched off: no CLI flag is documented; whatever Fred keeps in `~/.agents/skills` may still be listed. Config is Fred's file; the Console never writes it. Open item for the live check (Task 9) |
| OpenCode | inlined in the prompt file `runs/<sid>.prompt.md` | not switched off: `~/.claude/skills` and `.claude/skills` are discovered. A `skill` deny rule exists in OpenCode's permission model, but its env route is undocumented, so none is passed. Open item for the live check (Task 9) |

So the pick is **exact on Claude and Command Code** (the library is the only source of skill text) and **additive on
Codex and OpenCode** (the library text is always there; the CLI may also list its own skills). The plan states this on
the Board's chip title (Task 8) and does not claim exclusivity.

**Code facts the tasks depend on:**

- `runs.start` keeps a step's limits in the run meta (`disallow`, `tools`, `budget`, `max_turns`, `strict_mcp`) and a
  resumed turn given none reuses them (`console/runs.py:182`). A new `no_skills` limit would therefore be reused by the
  Hand off lever, which resumes a step's session with the text `/session-handoff` (`Hub._pull`, `console/server.py:820`;
  `levers.HANDOFF_TEXT`). With the flag on that turn the skill would not expand. Task 3 gives `runs.start` a per-turn
  `slash` override so Hand off leaves the flag off for its own turn and the saved limits are unchanged.
- `tasks.write_step_file` cuts every step file at `NOTE_MAX` = 20 KB (`console/tasks.py:1002`). D18 forbids cutting a
  skill, so `skills.md` is written by a `cut=False` form of the same function (Task 3).
- The step prompt is `console/step_prompt.md`; line 9 is `${role}$retry`. A chat-kind step also goes through
  `Hub.start_step` (`tasks.CHAT`, plan 36) with an empty role; it must carry no skills and keep slash commands.
- `supervisor.shape` refuses any field outside `SCHEMA["properties"]`, and plan 44 README section 1 says the backend
  rejects a `skills` field until a registry exists. Task 5 lifts that rule for `add_next_step` only.
- `tasks.whole` requires every key of `STEP_KEYS`, derived from `_blank`. The new step keys are never added to
  `_blank`, so a `task.json` from before this plan still loads.
- `kinds.ensure` seeds from `dotclaude/console/kinds/` and is called from `console/__main__.py:95` only, so the tests
  never seed. `skills.ensure` is called from the same place for the same reason: a test Hub has an empty library, no
  `always` skill, and every existing prompt assertion stays valid.

## 3. The contract

### 3.1 Files and places

```
console/skills.py                       new (Tasks 1, 2, 7): folder, ensure, registry, check_entry, body, lint, pick,
                                        resolve, inputs, prompt_block, save
dotclaude/console/skills/index.json     the seed registry (Task 1)
dotclaude/console/skills/handoff-quality/SKILL.md, ui-ux-review/SKILL.md   the seed skills (Task 1, D1)
~/.claude/console/skills/               the library (CC_CONSOLE_HOME/skills in tests): <name>/SKILL.md and index.json
~/.claude/console/tasks/<id>/steps/NN-<kind>/skills.md     what the step read (Task 3)
console/step_prompt.md                  `${role}${skills}$retry` (Task 3)
console/tasks.py                        step_prompt(skills=), STEP_FILES += skills.md, write_step_file(cut=)
console/claude_cli.py, console/harness/claude.py, console/runs.py      the flag and the limit (Task 3)
console/server.py                       Hub.skill_registry, start_step, _pull, create_task, preview_next / request_next,
                                        _supervisor_dispatch, Handler._config / _skill / _skill_save
console/supervisor.py, console/prep.py, console/plan.py (read only), console/__main__.py (one line)
tests/test_skills.py                    new; plus additions to test_claude_cli, test_runs, test_tasks, test_server,
                                        test_supervisor, test_prep, test_dotclaude, test_harness, test_web
```

`console/skills.py` imports `paths`, `redact`, `tasks`, `plan` and `facts`; `tasks`, `plan` and `kinds` never import it
(a test asserts the import direction). `supervisor.py` and `server.py` import it.

### 3.2 The library and `index.json` (BRAINSTORM 14.2, 14.3)

`<home>/skills/<name>/SKILL.md` for each skill, `<home>/skills/index.json` for the registry. A skill name is its folder
name: `NAME_RE = [a-z0-9][a-z0-9-]{0,63}`. `index.json` is one object keyed by name:

```json
{"ui-ux-review": {"description": "...", "kinds": ["design", "verify", "code"], "tags": ["ui-ux", "web"],
                  "paths": ["web/**"], "always": false},
 "my-notes": {"description": "A personal skill, not copied", "source": "~/.claude/skills/my-notes",
              "kinds": ["scout"], "tags": [], "paths": [], "always": false}}
```

| Field | Type | Rule |
|---|---|---|
| `description` | text, optional | shown on the Board and in the supervisor's digest; missing: the SKILL.md frontmatter `description:` (one line only), else the name |
| `kinds` | list of `tasks.KINDS` names | the step kinds the skill may ride with by code or by the supervisor; `[]` = any |
| `tags` | list of `TAG_RE = [a-z0-9][a-z0-9-]{0,31}` | matched against the step's tags |
| `paths` | list of relative globs, forward slashes, no `..`, no leading `/`, no drive letter, at most 200 characters each | matched against the files the step is about (3.5) |
| `always` | bool, default false | every step of its kinds, no tag needed |
| `source` | text `~/.claude/skills/<NAME_RE>` | a pointer: the body is read from `<user_home>/.claude/skills/<name>/SKILL.md`; no library folder is needed or used |

Unknown keys are ignored and kept (a save writes them back). Only `SKILL.md` is ever read.

`skills.ensure(home) -> list`: for each seed skill folder in `dotclaude/console/skills/`, copy its `SKILL.md` to
`<home>/skills/<name>/SKILL.md` when that file is missing (an edited file is never replaced); return the names copied.
Then the index: missing -> write the seed `index.json` whole; present and parseable -> add the seed entry of each skill
**copied in this run** (D3) and write only when something was added; present and unparseable -> leave it alone. Writes go
through `paths.write_text_atomic`. A write error skips that item (the next start retries); `ensure` never raises.
`__main__.py` calls it on the line after `kinds.ensure(paths.home())`.

### 3.3 The registry (`skills.registry`)

```python
def registry(home, user_home, cache: dict = None) -> dict:
    """{"skills": [row], "error": str, "tags": [vocabulary]}, rows in index order then unindexed folders by name.
    Pure reads. `cache` (the Hub keeps one dict) holds the last signature and the last good result: the signature is
    index.json's (mtime_ns, size) plus each SKILL.md's (mtime_ns, size) and the folder listing; an equal signature
    returns the cached result without reading a body."""
```

A row: `{"name", "description", "kinds", "tags", "paths", "always", "source", "kb", "why", "ok", "hand", "indexed"}`.
`kb` is the size in KB (one decimal) of the masked body the prompt would carry. `ok` = `why == ""`: code and the
supervisor may pick it. `hand` = the body is readable and passes the marker lint: Fred may pick it by hand even when it
is unindexed or its entry is invalid (the multi-select shows those dimmed). The first failing reason wins; the strings
are exact:

| `why` | When |
|---|---|
| `bad name` | an index key that is not `NAME_RE` (listed, no file is touched) |
| `index: entry is not an object` | the value is not an object |
| `index: kinds: unknown kind <x>` / `index: kinds must be a list of kind names` | `kinds` not a list of `tasks.KINDS` names |
| `index: tags must be a list of lower-case words` | `tags` fails `TAG_RE` |
| `index: paths must be a list of relative globs` | `paths` fails the table above |
| `index: always must be true or false` | `always` is not a bool |
| `index: source must be ~/.claude/skills/<name>` | `source` fails the form, or resolves outside `<user_home>/.claude/skills` |
| `no SKILL.md` | the file (the folder's, or the pointer's) does not exist |
| `unreadable: <reason>` | the file cannot be read as UTF-8 |
| `empty SKILL.md` | nothing is left after the frontmatter is stripped |
| `marker line: <marker>` | the lint of 3.7 |
| `not in index.json` | a folder with a SKILL.md and no entry |

An unparseable `index.json`: `error = "index.json invalid: <reason>"`; the last good rows stay (empty at a first read);
unindexed folders are still listed. A missing `skills/` folder: no rows, no error. Never raises.

`skills.body(path) -> (text, why)`: read UTF-8 (a leading BOM dropped), `\r\n` -> `\n`, strip a leading
`---\n...\n---\n` frontmatter, `redact.mask`, strip. This one function is the only reader of a skill body.

`vocabulary(reg) = sorted(set(BASE_TAGS) | {t for ok rows for t in row.tags})`, `BASE_TAGS = (backend, web, tests, docs,
data)`.

### 3.4 Selection (`skills.pick`, `skills.resolve`; BRAINSTORM 14.4)

```python
def pick(reg, kind: str, tags, files) -> list:
    """Names, deterministic. [] for a kind that is not in tasks.KINDS (a chat step). A row is picked when row.ok, and
    (row.kinds is empty or kind in row.kinds), and (row.always, or matches > 0) where matches = the number of the
    row's tags among `tags` + the number of `files` matched by at least one of the row's globs. Order: always rows
    first, then the rest by matches descending; ties keep index order. No count limit, no size limit."""

def resolve(reg, kind: str, tags, files, add=(), fred=None) -> dict:
    """{"names": [...], "by": "" | "code" | "supervisor" | "fred", "dropped": [{"name", "why"}]}.
    fred is not None: the final list is Fred's, in his order, deduplicated; only `hand` rows are kept, the rest are
    dropped with their why; kinds are ignored (D6); an empty list stays empty; by = "fred".
    Otherwise: pick(...) then the `add` names (the supervisor's) that are ok rows allowing `kind`, deduplicated, after
    the code's; by = "supervisor" when at least one added name was not already picked, else "code" (or "" when empty).
    A name that is unknown, not ok or not allowed for `kind` is dropped with why "unknown skill", the row's why, or
    "not for <kind> steps". A chat kind returns names [] and by ""."""
```

Glob test: `PurePosixPath(rel).full_match(glob, case_sensitive=False)` (Python 3.13+; the project runs 3.14.5, checked
2026-11-07: `web/**` matches `web/a/b.js` and `web/app.js`, not `webx/app.js`). Files are normalized before matching
(3.5). Tags are lower-cased and deduplicated before `pick` is called.

### 3.5 What a step is about (`skills.inputs`)

```python
def inputs(home, task: dict, step: dict, vocab) -> tuple:
    """(tags, files) for one step, in code, from saved data only (a read; no model, no network)."""
```

**Tags**, merged and deduplicated in this order, each lower-cased and kept only if it is in `vocab`:
1. `task.get("tags")` (Prep's card, Task 4);
2. the `Tags:` line of the step's plan section or part (Task 4);
3. for a manual step (`step.get("source_step")`, plan 36) the whole words of `step["goal"]` that are in `vocab`.

**Files**, normalized (`\` to `/`, leading `./` removed, an absolute path inside `task["project_dir"]` made relative,
anything else dropped), in this order of authority (first source that has any):
1. a manual step: the source step's files touched (`s["touched"]` else `facts.files_in` of its saved facts file, the
   same read as `tasks.summary`);
2. a step with a plan part: that part's `owns` cell (`plan.table`) plus its `## Files` lines;
3. a step with a `### Step N` section: its `#### Files` lines;
4. any other step of a task with a plan after the design step (verify, fix, test, ...): the plan index's `## Files`
   lines;
5. otherwise none (the design step, a step of a task with no plan).

A Files line is read by `skills.files_of(text)`: per line, strip leading bullets (`-`, `*`, `+`), `>` and backticks,
take the line's first token (the characters of `[A-Za-z0-9_./\\@+-]` up to a space, `:`, `(` or a closing backtick); it
is a path only if it contains `.` or `/`, else the line names nothing. Tolerant, never raises.

### 3.6 Enforcement (BRAINSTORM 14.5, D17 a)

**The prompt.** `step_prompt.md` line 9 becomes `${role}${skills}$retry`. `tasks.step_prompt(..., skills: str = "")`
substitutes `skills`; the caller passes `"\n" + block + "\n"` when there is a block and `""` otherwise, so **a step with
no skill has a prompt byte for byte equal to today's**. The block, from `skills.prompt_block(items)`:

```
Skills for this step (from the Console's skill library; they add to the rules below and never replace them or the HANDOFF block):

--- skill: <name> ---
<the body, masked, whole>
--- end skill: <name> ---
```

one `--- skill ---` pair per skill, in resolve order, a blank line between. `string.Template` does not rescan a
substituted value, so a `$` or `${x}` in a body is literal (a test pins it).

**The files.** `skills.md` in the step folder is `# skills\n\n` plus the block above, exactly what the prompt carries,
written whole (no 20 KB cut, D18) and replaced on every attempt; when no skill is picked an existing `skills.md` of that
step is removed. `received.md` lists, per skill, `- skills/<name>/SKILL.md (<kb> KB, picked by <by>)` (a pointer:
`~/.claude/skills/<name>/SKILL.md`), and `- skills.md (the bodies as the prompt carries them)`. The chain `read:` line
gains `skills a, b`. The step dict gains, only when set (never in `_blank`): `skills` (final names), `skills_by`,
`skills_kb`, and the optional inputs `skills_in` (`{"fred": [...]}` and/or `{"supervisor": [...]}`, written at step
creation by Tasks 5 and 6).

**The flag.** `claude_cli.run_command(..., no_skills=False)` appends `--disable-slash-commands` after
`--strict-mcp-config`. `harness/claude.run_command` passes it through. `runs.start(..., no_skills=False, slash=False)`:
a new run stores `limits["no_skills"] = True` only when true; a resumed turn that gives no limits reuses the old limits
(so a STOP answer or a retry keeps the flag); `slash=True` leaves the flag off for that one turn without changing the
saved limits. `Hub.start_step` passes `no_skills=True` for every kind in `tasks.KINDS` (design included) and `False` for
a chat-kind step; `Hub._pull` passes `slash=True` for `lever == "handoff"`. No other launch changes. The adapters of
Codex, OpenCode and Command Code receive nothing new (`runs.start` adds `no_skills` to the adapter arguments for Claude
only, as it does `strict_mcp`).

**Order in `Hub.start_step`** (after `role` and the plan parts are known, before `tasks.step_prompt`): registry ->
`skills.inputs` -> `skills.resolve` -> read every picked body with `skills.body` -> `prompt_block` -> step keys, `read:`
and `got` lines -> prompt. If `by == "fred"` and Fred's list had a dropped name, or any picked body cannot be read, the
step does not start: `tasks._task_to(task, "stuck", "skills: <name> <why>", ...)`, and Retry re-runs this section. A
code or supervisor name that is dropped only adds a `skills dropped <name>` note to `read:`. Any other exception in this
section is the same stuck with `skills: <ExceptionName>`. A retry re-resolves (D9): the library may have changed.

### 3.7 The handoff contract is not disturbed (plan 23)

`tasks.HEADINGS`, `parse_handoff`, `check_handoff`, `plan.parse` and the brief checks read the model's reply, but a
model can echo its prompt, and the fake claude's echo does (`tests/fake_claude.py`). Three guards:

1. **Position.** The block sits right after the role, before `$retry`, the plan, the earlier handoff and the rules. The
   rules, the six-heading template and `END HANDOFF` stay last and untouched; the slot adds no text after them.
2. **Lint.** `skills.lint(body) -> str` returns `marker line: <m>` when a body line, passed through `tasks._mark` (the
   dressing `plan.parse` also strips), equals `HANDOFF`, `END HANDOFF`, `PLAN`, `END PLAN`, `END SUBPLAN` or matches
   `plan._PART` (`SUBPLAN n kind title`). Such a skill is `ok = False` and `hand = False` everywhere: no pick, no
   supervisor add, no Fred pick (the POST refuses it with the same text). The seed `handoff-quality` talks about the
   block in prose and never has such a line.
3. **Golden test.** For every golden registry case, `tasks.parse_handoff(prompt_with_skills) ==
   tasks.parse_handoff(prompt_without_skills)` and `plan.parse(...)` agree, and the prompt ends with the template.

### 3.8 Redaction (`redact.mask`) at every landing

| Where skill text or a field of the library lands | Rule |
|---|---|
| the prompt block and `skills.md` | the body is masked once, in `skills.body`; nothing reads a raw body for a prompt |
| `received.md`, the chain `read:` line, `task.json`, `supervisor.jsonl` | names, kinds, sizes and `by` only, never a body |
| `GET /api/config` `skills`, the supervisor's digest | `description` through `redact.mask` (and clipped to 300 characters in the digest) |
| `GET /api/skill` | the raw file for Fred's own editor (same as `GET /api/kind`: a masked copy saved back would overwrite his text with `***`); the localhost guard applies. Every copy that leaves the editor is masked |
| a failing read's reason in `why` or a stuck line | `redact.clip(redact.mask(...), 120)` |

### 3.9 The supervisor (BRAINSTORM 14.4 item 3; Task 5)

`SCHEMA["properties"]["skills"]` = array of strings; `_OPTIONAL["skills"] = list`; `_FIELDS["add_next_step"]` gains
`skills`. `shape` accepts it for `add_next_step` only (any other decision: `skills is not a field of <decision>`) and
requires every item to be a `NAME_RE` string. `check` never refuses because of `skills`: `supervisor.clean_skills(raw,
kind, rows) -> (kept, dropped)` (pure) applies `resolve`'s add rule; the dispatch passes `kept` to `request_next` as
`skills`, which stores `step["skills_in"]["supervisor"]`. The digest gains a block `Skills available (an add_next_step
decision may list names from here in "skills"; leave it out when none fit)` with `- <name> [<kinds or any>]:
<description>` for every ok row. It is a low-priority block: omitted whole by the existing byte budget when it does not
fit. The audit lines (`phase: dispatching` and the outcome) carry `skills` and `skills_dropped`. The final list the step
started with is the step's own `skills` field and the chain `read:` line; `start_step` does not write the journal (a
deliberate narrowing of BRAINSTORM 14.6, section 3.12).

### 3.10 Routes (Task 7) and the window contract (Task 8)

| Route | Reads or writes | Why this route |
|---|---|---|
| `GET /api/config` | adds `skills` (the rows), `skills_error`, `skills_tags` (vocabulary) | the window already loads it |
| `GET /api/skill?name=` | one skill: raw text, path, entry, row, seed text | like `GET /api/kind` |
| `POST /api/skill` `{name, text?, entry?, reset?}` | `SKILL.md` and its `index.json` entry only | **new route**, not `POST /api/config/models`: that route is the config.json whitelist and "never writes models.json"; the library is files, as the Kinds tab's `POST /api/kind` is. Task 9 names it in the CLAUDE.md rules paragraph |
| `POST /api/task` | each step row may carry `skills: [names]` (Fred's pick) | Task 6 |
| `POST /api/task/next/preview`, `POST /api/task/next` | `skills` in the body; the preview returns the code's preset | Task 6 |

### 3.11 Migration

- A task started before the library has no `skills` keys and no `skills.md`. Every read uses `.get`; `STEP_KEYS` and
  `TASK_KEYS` are unchanged, so `tasks.whole` and `tasks.load_all` accept it; the Board shows no chip; Received shows
  the old `role.md` and `received.md` only. A step of such a task that is retried after the upgrade resolves skills like
  any new attempt (the library is empty until `skills.ensure` ran, so usually none) and gets `--disable-slash-commands`.
- A session started before the upgrade and resumed after it keeps the limits it was saved with (no `no_skills`), so a
  STOP answer on an old step runs as it always did.
- `request_next`'s idempotence hash adds `skills` to the signed payload only when the request has it, so a repeated
  request id from before the upgrade still matches.
- `dotclaude/console/kinds/*.md` are not edited by this plan: the Prep and design additions are code-appended (Task 4),
  so an edited kind file needs no Reset.
- First start after the upgrade: `skills.ensure` seeds the library (D1). From then on every step carries
  `handoff-quality` (`always`). The Kinds, Tiers and Tuning tabs are unchanged.
- **Behaviour change Fred should know:** with `--disable-slash-commands` a task step no longer sees personal skills,
  project skills, nor the project's `.claude/commands/`. A skill a step needs goes into the library, as a folder or a
  `source` pointer.

### 3.12 Differences from BRAINSTORM 14, all stricter or smaller

1. `ensure` adds a seed's index entry only when it copied that seed's folder in the same run (D3), so deleting an
   entry to turn a skill off sticks.
2. A marker-line lint (3.7) is new.
3. Fred's own pick ignores `kinds` and may name an unindexed skill (D6); code and the supervisor may not.
4. The Prep and design tag rules are appended by code, not slotted into the kind files.
5. `supervisor.jsonl` records the requested list at dispatch; the final list is on the step and in the chain line.
6. `skills.md` is exempt from the 20 KB step-file cut; `--disable-slash-commands` is not applied to chat-kind steps and
   is lifted for the Hand off lever's turn.
7. The `--add-dir` mode and `skills_load` of slice C are left out (D5).
8. On the Prep card the per-step control reads `Auto` (the code picks when the step starts) instead of a preset: the card
   has no source files or plan yet. Only Add next step shows the code's preset, because its preview has the source's
   files (Task 6). A planned step's skills cannot be edited after creation.

## 4. Golden selection table

The fixture registry (index order; every row except `handoff-quality`, `ui-ux-review`, `api-review`, `test-writing`,
`doc-style` and `sql-safety` is a trap that must never be picked):

| name | kinds | tags | paths | always | state |
|---|---|---|---|---|---|
| handoff-quality | any | - | - | true | ok |
| ui-ux-review | design, verify, code | ui-ux, web | `web/**` | false | ok |
| api-review | code, debug, verify | backend | `console/**/*.py` | false | ok |
| test-writing | test, code, fix | tests | `tests/**` | false | ok |
| doc-style | document, draft, edit, proofread | docs | - | false | ok |
| sql-safety | any | data | `migrations/**` | false | ok |
| bad-kinds | `reviewer` | web | - | false | `index: kinds: unknown kind reviewer` |
| no-folder | any | web | - | false | `no SKILL.md` |
| marker-skill | any | web | - | false | body has a line `END HANDOFF`: `marker line: END HANDOFF` |
| unindexed | (folder only) | | | | `not in index.json` |

`pick(kind, tags, files)` -> names (Task 2 asserts every row):

| # | kind | tags | files | expected |
|---|---|---|---|---|
| 1 | code | - | - | handoff-quality |
| 2 | code | web, ui-ux | - | handoff-quality, ui-ux-review |
| 3 | code | backend | console/server.py | handoff-quality, api-review |
| 4 | code | backend, tests | console/server.py, tests/test_x.py | handoff-quality, api-review, test-writing (two matches each: index order breaks the tie) |
| 5 | code | tests | console/a.py, console/b.py | handoff-quality, api-review, test-writing (api-review: 2 path matches; test-writing: 1 tag) |
| 6 | design | web | - | handoff-quality, ui-ux-review |
| 7 | scout | web | - | handoff-quality (ui-ux-review does not ride with scout) |
| 8 | document | docs | - | handoff-quality, doc-style |
| 9 | document | web | web/index.html | handoff-quality |
| 10 | verify | - | web/app.js | handoff-quality, ui-ux-review (a path alone picks) |
| 11 | fix | tests | tests/test_a.py | handoff-quality, test-writing |
| 12 | debug | data | migrations/001.sql | handoff-quality, sql-safety |
| 13 | chat | web | web/x.js | (empty: a chat step carries none) |
| 14 | code | unknown-tag | README.md | handoff-quality |
| 15 | code | - | `Web\app.js` | handoff-quality, ui-ux-review (backslash and case normalized) |
| 16 | code | web | - | never bad-kinds, no-folder, marker-skill or unindexed, although all carry the tag web |

`resolve` (Task 2): R1 `code`, tags web, add `[test-writing]` -> handoff-quality, ui-ux-review, test-writing, by
supervisor. R2 `scout`, add `[ui-ux-review]` -> handoff-quality, dropped `not for scout steps`, by code. R3 `code`, add
`[unindexed]` -> dropped `not in index.json`. R4 `code`, fred `[]` -> `[]`, by fred. R5 `code`, fred `[unindexed]` ->
`[unindexed]`, by fred. R6 `code`, fred `[marker-skill]` -> `[]`, dropped `marker line: END HANDOFF`, by fred. R7 `chat`,
fred `[ui-ux-review]` -> `[]`. R8 duplicates in `add` or `fred` collapse, first spelling's order kept.

## 5. Decisions for Fred

Recommended option first; the plan is written for it. The brainstorm closed D14 to D18; these are what it did not.

| # | Question | (a) recommended | (b) |
|---|---|---|---|
| D1 | Which skills ship in `dotclaude/console/skills/` | the two the brainstorm names (14.7): `handoff-quality` (any kind, `always`) and `ui-ux-review` (design, verify, code; tags ui-ux, web), with the short texts in Task 1 for your edit. `handoff-quality` adds about 250 words to every step, repeating only what the brief checks enforce | ship the machinery and an empty `index.json` only; you write the first skills; Task 1's seed tests use a test-only seed folder |
| D2 | Do `session-handoff` and `route-model` move into the library | no: they are real Claude skills used by VS Code chats, by the Hand off lever on chats (`levers.handoff_ready` reads `~/.claude/skills/session-handoff`) and by Prep's table. A step cannot run `/session-handoff` anyway (the step prompt says so) and never routes itself. A `source` pointer entry can add either later | move both as copies (they would then exist twice) |
| D3 | A deleted index entry of a seed skill | `ensure` re-adds a seed entry only when it also copies that seed's folder, so deleting the entry (or setting `always: false`) sticks. Stricter than BRAINSTORM 14.3, which re-adds any missing seed entry at every start | as written in 14.3: a deleted seed entry returns at the next start, and an `always` skill you disliked is back on every step |
| D4 | Command Code's argv cap (30,000 characters, `runs.CMD_PROMPT_MAX`) with no skill limit | the step does not start; the stuck reason names the skills: `prompt too long for cmd (N characters; skills M)`; you pick fewer skills or another rung. Nothing is trimmed (D18) | lift the cap for `cmd` by sending the prompt in a file (needs the CLI's flag; none is documented) |
| D5 | The `--add-dir` loading mode and `skills_load` (BRAINSTORM 14.5 rejected (b), 14.7 slice C keeps it as an option) | leave it out: Claude only, writes `.claude/` folders under the task folder, and with no size limit inlining already works | build it as a later plan if an `always` skill ever gets too heavy |
| D6 | Does your own pick obey `kinds` | no: your pick is explicit, so it may name any readable skill, indexed or not, for any step kind; code and the supervisor obey `kinds` and the index | your pick obeys `kinds` like the others |
| D7 | Skills in a chat-kind step and in chats | none, and chat-kind steps keep slash commands (a chat is yours, 14.5) | none, but chat-kind steps also get the flag |
| D8 | The window may create a skill (first save of a new name) but not delete one | yes | also a Delete button |
| D9 | A retry re-resolves skills | yes: each attempt reads the library as it is then | the first attempt's list is frozen on the step |

## 6. Verification at the end of every task

1. The task's tests were written first and failed for the intended reason before the code.
2. Focused: `py -m unittest tests.test_skills` plus the test modules the task names.
3. Full: `py -m unittest discover -s tests` in the background, read the finished output; report the real count.
4. `node --check web/app.js` after any web change.
5. `git diff --stat` shows only the task's files; stage explicit paths; the commit message is the one the task names.
6. No test calls a paid provider, touches port 47770, or writes `~/.claude`: tests use a scratch `CC_CONSOLE_HOME`, a
   scratch `Hub.user_home` and `tests/fake_claude.py`.

## 7. Status and history

- 2026-11-07: written (plan only) from BRAINSTORM 14 and 15 against `9b6f988`; the flag and the other CLIs' skill
  handling checked against their docs (section 2). Fred's decisions D1 to D9 open.
- 2026-11-07: one Opus review. Two fixes: `git add -p` (interactive, unavailable here) replaced by the
  `git hash-object -w` / `git update-index --cacheinfo` staging; Task 3 gains a step 0 gate (`claude --help` lists the
  flag, and Fred's Task 9.1 pairing check with `--input-format stream-json` passes) before any code, since a refused
  flag would break every task step. Golden table rows 1 to 16 and R1 to R8 re-derived by hand: consistent.

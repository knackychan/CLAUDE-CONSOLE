# Task 3: enforcement, the prompt slot, `skills.md` and the flag

> Contract: [README.md](README.md) 3.6, 3.7, 3.8, 3.11. Decisions D4, D7, D9. BRAINSTORM 14.5 and 14.6.
> After this task a task step carries what code picks (`always` skills and kind/tag/path matches). Tags come only from
> the task's saved `tags` and the plan until Task 4; Tasks 5 and 6 add the supervisor's and Fred's names.

**Files**
- Modify: `console/step_prompt.md` (line 9: `${role}${skills}$retry`)
- Modify: `console/tasks.py` (`step_prompt(..., skills="")`, `STEP_FILES`, `write_step_file(..., cut=True)`)
- Modify: `console/skills.py` (`read_picked`, `prompt_block`, `skills_md`, `manifest`)
- Modify: `console/claude_cli.py` (`run_command(no_skills=False)`), `console/harness/claude.py`, `console/runs.py`
- Modify: `console/server.py` (`Hub.skill_registry`, `Hub._skills_for`, `Hub.start_step`, `Hub._pull`)
- Modify: `tests/test_claude_cli.py`, `tests/test_runs.py`, `tests/test_tasks.py`, `tests/test_harness.py`,
  `tests/test_server.py`, `tests/test_skills.py` (`PromptTest`)

Commit boundary: `feat: task steps carry the picked skills and run without native skills (plan 56 T3)`.

## 3.1 Code

`console/step_prompt.md`: line 9 `${role}$retry` becomes `${role}${skills}$retry`.

`console/tasks.py`
- `step_prompt(task, step, prev_note, retry_reason="", role=None, plan="", part="", facts="", lessons=(), you="the user",
  note="", tried="", skills="")`: the new argument is substituted as `skills=skills`; it is the caller's finished slot
  text (empty or `"\n" + block + "\n"`). Nothing else in the function changes.
- `STEP_FILES` gains `"skills.md"` right after `"role.md"`.
- `write_step_file(home, task, step, name, text, head=False, cut=True)`: with `cut=False` the 20 KB cut is skipped
  (the mask still applies). Every existing caller keeps the default.

`console/skills.py`
```python
def read_picked(home, user_home, reg, names) -> tuple
    """([{"name", "body", "kb", "pointer": bool}], why): the bodies in `names` order through `body()`; why = "" or
    "<name> <reason>" for the first one that cannot be read (the rest are not read)."""

def prompt_block(items) -> str
    """README 3.6: the head line, then `--- skill: <name> ---`, the body, `--- end skill: <name> ---` per skill,
    blank line between; "" for []."""

def skills_md(block) -> str            # "# skills\n\n" + block, ending in one newline
def manifest(items, by) -> list        # received.md lines: `skills/<name>/SKILL.md (<kb> KB, picked by <by>)`, a pointer
                                       # `~/.claude/skills/<name>/SKILL.md (...)`, then `skills.md (the bodies as the
                                       # prompt carries them)`; [] for no items
```

`console/claude_cli.py` `run_command(..., strict_mcp=False, no_skills=False)`: after the `strict_mcp` block,
`if no_skills: cmd += ["--disable-slash-commands"]`. The flag is verified in README section 2. Prep, planner and brief
commands already pass it and are not touched.

`console/harness/claude.py` `run_command(..., strict_mcp=False, no_skills=False)` passes `no_skills` through.

`console/runs.py` `RunManager.start(..., strict_mcp=False, no_skills=False, slash=False)`:
- limits: `if no_skills: limits["no_skills"] = True` (the key is absent otherwise, so existing limits comparisons hold);
- the reuse condition becomes `resume and not (disallow or tools or budget or max_turns or strict_mcp or no_skills) and
  old.get("limits")`;
- for Claude, `common.update(..., no_skills=bool(limits.get("no_skills")) and not slash)`; no other harness receives
  the key (the existing `if harness == "claude"` branch);
- `slash=True` changes the command of this turn only; `_save_meta` stores `limits` as computed without it.

`console/server.py`
- `Hub.__init__`: `self.skill_cache = {}`. `Hub.skill_registry()` returns `skills.registry(self.folder, self.user_home,
  self.skill_cache)` (never raises).
- `Hub._skills_for(task, s, reg) -> dict`: `vocab = skills.vocabulary(reg)`; `tags, files = skills.inputs(self.folder,
  task, s, vocab)`; `inp = s.get("skills_in") if isinstance(s.get("skills_in"), dict) else {}`;
  `res = skills.resolve(reg, s["kind"], tags, files, add=inp.get("supervisor") or (), fred=inp.get("fred"))`;
  `items, why = skills.read_picked(...)`. Returns `{"names", "by", "items", "block", "kb", "dropped", "stuck"}` where
  `stuck` is `"skills: " + why` when a body cannot be read, or `"skills: <name> <reason>"` when `by == "fred"` and Fred's
  list had a dropped name, else `""`. Any exception is caught and returned as `stuck = "skills: <ExceptionName>"`.
- `start_step` (just before `prompt = tasks.step_prompt(...)`): `sk = self._skills_for(task, s, self.skill_registry())`;
  if `sk["stuck"]`, `tasks._task_to(task, "stuck", sk["stuck"], now, s, lines)` and `return self._commit(task, lines)`.
  Otherwise pass `skills=("\n" + sk["block"] + "\n") if sk["block"] else ""` to `tasks.step_prompt`; set
  `s["skills"], s["skills_by"], s["skills_kb"]` (or pop all three when empty, so a retry that picks none leaves no
  stale keys); `read.append("skills " + ", ".join(names))` and one `skills dropped <name>` note per code or supervisor
  drop (both before the line that joins `read` into the chain note); extend the `got` expression that follows the
  prompt with `skills.manifest(...)`, right after its `kinds/{kind}.md (as role.md)` item. After the existing `role.md` write: when `sk["block"]` write
  `skills.md` with `tasks.write_step_file(..., "skills.md", skills.skills_md(block), cut=False)`, else remove an existing
  `skills.md` of the step (`unlink`, ignoring `FileNotFoundError`/`OSError`). A manual step (`"source_step" in s`) keeps
  the `received.md` request_next wrote: read it, drop any line starting `- skills/` or `- skills.md`, append the new
  manifest lines, write it back. For `hname == "cmd"` and a non-empty block, a prompt over `runs.CMD_PROMPT_MAX` raises
  `runs.RunError(f"prompt too long for cmd ({len(prompt)} characters; skills {len(sk['block'])})")` before
  `runs.start`; the existing `except` makes the task stuck with that text (D4).
- `start_step`'s `self.runs.start(...)` gains `no_skills=(kind in tasks.KINDS)` (a chat-kind step: False, D7).
- `Hub._pull`: the `self.runs.start(...)` call gains `slash=(lever == "handoff")`.

## 3.2 Tests first (red before the code)

`tests/test_claude_cli.py`
- `test_no_skills_flag_only_when_asked`: `--disable-slash-commands` absent by default, present with `no_skills=True`,
  after `--strict-mcp-config` and before `--session-id`; the Prep, planner and brief commands are unchanged.

`tests/test_runs.py`
- `test_no_skills_is_a_limit_a_resume_keeps_and_a_slash_turn_drops`: a new run with `no_skills=True` saves
  `limits["no_skills"] is True` and the adapter kwargs show `no_skills=True`; a resume given no limits reuses it; a
  resume with `slash=True` shows `no_skills=False` while the saved meta still holds `True`; a plain run saves no
  `no_skills` key (the existing limits-equality assertions stay as they are); a Codex run's kwargs have no `no_skills`.

`tests/test_tasks.py`
- `test_step_prompt_without_skills_is_byte_identical`: the repo template with `${skills}` deleted, rendered the old way,
  equals `step_prompt(..., skills="")` for a code, a verify and a design step.
- `test_step_prompt_skills_slot`: with a slot the block sits between the role and `retry`; the text after
  `Rules for this step:` is unchanged; the prompt still ends with `END HANDOFF`.
- `test_write_step_file_cut`: default cuts at 20 KB with `[cut at 20 KB]`; `cut=False` keeps 100 KB whole, masked.
- `test_step_files_lists_skills_md_after_role_md` (and the assertions that spell the old tuple are updated: grep
  `STEP_FILES` and `"role.md", "received.md"` in `tests/`).

`tests/test_skills.py` `PromptTest`
- `test_prompt_block_shape_and_literal_dollars`: the exact block text for two skills; a body with `$you`, `${role}` and
  `$$` appears literally in `step_prompt` output (Template does not rescan); a 300 KB body is whole (D18).
- `test_manifest_lines`.
- `test_the_handoff_contract_is_undisturbed` (README 3.7 guard 3): for every golden `pick` case with the real seed
  skills plus the golden bodies, `tasks.parse_handoff(prompt_with)` equals `tasks.parse_handoff(prompt_without)`, the
  last `HANDOFF` line of the prompt is the template's, `plan.parse(prompt_with)` equals `plan.parse(prompt_without)`,
  and every `tasks.HEADINGS` line still appears once in the template part. The fake claude's echo is not used.

`tests/test_harness.py`
- `test_only_claude_gets_the_skills_flag`: Codex, OpenCode and Command Code commands built by their adapters contain no
  `--disable-slash-commands`; Command Code still has `--no-skills`; neither Codex nor OpenCode has any skills token.

`tests/test_server.py` (scratch `CC_CONSOLE_HOME`, `Hub.user_home` in a temp dir, `skills.ensure(home)` called by the test
because the Hub does not, fake claude)
- `test_task_step_carries_the_library`: a one-step code task: the `cc_prompt` line of the step's stream holds
  `--- skill: handoff-quality ---`; `skills.md` equals `# skills\n\n` + that block; `received.md` has the manifest; the
  chain start line's notes hold `read: ... skills handoff-quality`; the step dict has `skills == ["handoff-quality"]`,
  `skills_by == "code"`, `skills_kb > 0`; the run meta has `limits["no_skills"] is True`.
- `test_step_with_an_empty_library_is_unchanged`: no `skills/` folder: the stream prompt equals the template render with
  no slot, no `skills.md`, no `skills*` step key, and the flag is still on.
- `test_secret_in_a_skill_is_masked_everywhere`: a secret-shaped token in a skill body is `***` in the stream prompt,
  `skills.md` and every log line.
- `test_retry_reresolves_and_clears_a_stale_skills_md` (D9): edit the library between two attempts; the second attempt's
  `skills.md` reflects it; remove every skill and the file and the three step keys are gone.
- `test_chat_kind_step_has_no_skills_and_keeps_slash_commands` (D7): no block, `no_skills` False.
- `test_hand_off_turn_runs_without_the_flag`: Hand off on a task step's own session resumes with `/session-handoff` and the
  adapter kwargs `no_skills=False`; the step's saved limits still say `no_skills`.
- `test_an_unreadable_pick_makes_the_task_stuck_and_retry_works`: a Fred pick (set through `skills_in` on the step)
  of a skill whose file was deleted or carries a marker line: stuck with `skills: <name> <reason>`, no run started;
  after the fix, Retry starts it.
- `test_manual_step_received_md_gains_the_skills_lines_once`: a plan 36 step keeps request_next's `received.md` and two
  starts leave one set of skills lines.
- `test_cmd_prompt_over_the_cap_names_the_skills` (D4): a Command Code rung and a skill body over 30,000 characters:
  stuck with `prompt too long for cmd (N characters; skills M)`; nothing trimmed.
- `test_a_task_from_before_the_library_loads_and_runs`: a `task.json` fixture saved with no `skills*` key: `tasks.whole`
  is true, `tasks.load_all` keeps it, `GET /api/task` serves it, its next step starts and shows no chip data.

## 3.3 Steps and acceptance

- [ ] 0. Free gate before any code (no provider): `claude --help` must list `--disable-slash-commands`, and Fred runs Task 9.1's one-turn pairing check (the flag with `--input-format stream-json`) on a scratch project. If either fails, stop and ask Fred: the flag would break every task step. Record the result in README section 7.
- [ ] 1. Write the tests; run the focused modules red for the intended missing behaviour.
- [ ] 2. `claude_cli` and adapter flag, `runs` limit and `slash`, then `tasks` (template, files, cut), then `skills`
      functions, then the Hub wiring. Run each module's tests green as it lands.
- [ ] 3. Full suite green; `git diff --stat` shows the files above; commit with the message above.
- [ ] 4. Drift guards: no code outside `Hub.start_step` passes `no_skills=True`; the Prep, planner, brief, replan,
      supervisor and rules-review passes are unchanged (their tests stay green); `Hub._pull` passes `slash` for the
      Hand off lever only.
